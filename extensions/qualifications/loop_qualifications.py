"""Extension 4, Case A: Heterogeneous Worker Qualifications (clean partition).
Solves BAP, NPP, and ECP via Column Generation with one pricing SP per
(resilience group, qualification) pair (Datei/extensions.tex, app:ext:qual).
Sweeps the ICU-certified proportion pi in {0.20, 0.35, 0.50, 0.65}; night-shift
demand is held constant to create a qualification bottleneck at low pi.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from dataclasses import dataclass
from typing import List
import numpy as np
import pandas as pd
import gurobipy as gu
from core.base_case import get_wd_constraints
from core.masterproblem import MasterProblem
from core.worker_groups import get_calibrated_delta, compute_alpha_R
from Utils.demand import generate_demand
from extensions.qualifications.subproblem_qualifications import SubproblemQualifications

from core.base_case import K_ECP
from core.solver_base import MAX_ITR, THRESHOLD, TIME_CG_INIT, TIME_CG_SP
PI_VALUES = [0.20, 0.35, 0.50, 0.65]
S_GENERAL = {1, 2}       # q1: general ward, eligible for E and L only
S_ICU = {1, 2, 3}        # q2: ICU-certified, eligible for E, L, N


@dataclass
class QualGroup:
    name: str
    worker_ids: List[int]
    chi: int
    gamma_C: float
    gamma_R: float
    T_R: int
    eligible_shifts: set
    delta: object = None
    e_max: float = 1.0

    def __post_init__(self):
        if self.delta is None:
            self.delta = get_calibrated_delta()
        self.alpha_R = compute_alpha_R(self.T_R, self.gamma_R)


def make_qual_groups(I, pi):
    """Partition workers into (resilience x qualification) groups. pi = fraction ICU."""
    n = len(I)
    n_icu = max(1, round(pi * n))
    icu_ids, gen_ids = I[:n_icu], I[n_icu:]
    groups = {}
    # Split each qualification class evenly into resilient/sensitive archetypes.
    for label, ids in (("icu", icu_ids), ("gen", gen_ids)):
        if not ids:
            continue
        half = max(1, len(ids) // 2)
        res_ids, sens_ids = ids[:half], ids[half:]
        elig = S_ICU if label == "icu" else S_GENERAL
        if res_ids:
            groups[f"{label}_res"] = QualGroup(f"{label}_res", res_ids, chi=2, gamma_C=0.5,
                                                gamma_R=0.5, T_R=7, eligible_shifts=elig)
        if sens_ids:
            groups[f"{label}_sens"] = QualGroup(f"{label}_sens", sens_ids, chi=4, gamma_C=1.5,
                                                 gamma_R=1.5, T_R=21, eligible_shifts=elig)
    return groups


def run_cg(data, demand_dict, qual_groups, mode, max_itr=MAX_ITR, threshold=THRESHOLD,
           time_cg_init=TIME_CG_INIT, time_cg=TIME_CG_SP):
    T = data['T'].dropna().astype(int).unique().tolist()
    K = data['K'].dropna().astype(int).unique().tolist()
    I = data['I'].dropna().astype(int).unique().tolist()
    Min_WD_i, Max_WD_i = get_wd_constraints(I)

    start_perf = {(t, s): 0.0 for t in T for s in K}
    master = MasterProblem(data, demand_dict, max_itr, 0, 0, 100, start_perf, worker_groups=qual_groups)
    master.buildModel()
    master.setStartSolution()

    group_names = list(qual_groups.keys())
    perf_by_group, x_by_group = {g: {} for g in group_names}, {g: {} for g in group_names}

    itr, col_idx, improvable = 0, 0, True
    while improvable and itr < max_itr:
        master.model.Params.OutputFlag = 0
        master.model.optimize()
        duals_i, duals_ts = master.getDuals_i(), master.getDuals_ts()
        improvable = False
        for g_idx, (gname, group) in enumerate(qual_groups.items(), start=1):
            eps_sp = 0.06 if mode == 'bap' else 0.0
            sp = SubproblemQualifications(duals_i.get(g_idx, 0.0), duals_ts, data, group.worker_ids[0], itr,
                                           eps_sp, Min_WD_i, Max_WD_i, group.chi, group.eligible_shifts)
            if mode == 'bap':
                sp.gamma_C, sp.gamma_R, sp.alpha_R, sp.delta, sp.e_max = (
                    group.gamma_C, group.gamma_R, group.alpha_R, group.delta, group.e_max)
            else:
                sp.gamma_C, sp.gamma_R, sp.alpha_R, sp.e_max = 1.0, 1.0, 1.0, 0.0
                sp.delta = np.zeros((4, 4))
            sp.buildModel()
            if mode == 'ecp':
                sp.addECPConstraint(K_ECP)
                sp.model.update()
            sp.model.Params.OutputFlag = 0
            sp.model.Params.MIPGap = 1e-6
            sp.model.Params.PoolSearchMode = 2
            sp.model.Params.PoolSolutions = 10
            sp.model.Params.PoolGap = 1e100
            sp.model.Params.TimeLimit = time_cg_init if itr == 0 else time_cg
            sp.model.optimize()
            if sp.model.SolCount == 0:
                continue
            for psi in range(sp.model.SolCount):
                sp.model.Params.SolutionNumber = psi
                if sp.model.PoolObjVal >= -threshold:
                    continue
                col_idx += 1
                master.addLambda(col_idx - 1, g_idx)
                perf_vals = {(t, s): sp.performance[t, s, sp.itr].Xn for t in T for s in K}
                x_vals = {(t, s): sp.x[t, s].Xn for t in T for s in K}
                col = {(t, s, col_idx): perf_vals[(t, s)] for t in T for s in K}
                master.addColumn(col_idx - 1, col, g_idx)
                perf_by_group[gname][col_idx] = {(t, s, col_idx): perf_vals[(t, s)] for t in T for s in K}
                x_by_group[gname][col_idx] = x_vals
                improvable = True
        itr += 1

    # Restore integrality and pool-average (paper: NPP/ECP-style metrics are averaged
    # ex post across the optimal pool to remove the arbitrary schedule<->worker pairing).
    master.model.Params.OutputFlag = 0
    for v in master.lmbda.values():
        v.VType = gu.GRB.INTEGER
    master.model.Params.PoolSearchMode = 2
    master.model.Params.PoolSolutions = 50
    master.model.Params.PoolGap = 0.0
    master.model.optimize()

    def _reconstruct(get_count):
        understaffing, undercoverage = 0.0, 0.0
        nominal = {(t, s): 0.0 for t in T for s in K}
        effective = {(t, s): 0.0 for t in T for s in K}
        consistency = 0
        for g_idx, (gname, group) in enumerate(qual_groups.items(), start=1):
            for r in master.active_roster_by_group.get(g_idx, []):
                cnt = get_count(g_idx, r)
                if cnt <= 0:
                    continue
                x_sched = x_by_group[gname].get(r, {})
                perf_sched = perf_by_group[gname].get(r, {})
                for _ in range(cnt):
                    last = None
                    for t in T:
                        worked = 0
                        for s in K:
                            if x_sched.get((t, s), 0) > 0.5:
                                worked = s
                                nominal[(t, s)] += 1.0
                                effective[(t, s)] += perf_sched.get((t, s, r), 0.0)
                                break
                        if worked != 0 and last is not None and last != 0 and worked != last:
                            consistency += 1
                        last = worked

        for t in T:
            for s in K:
                q = demand_dict[(t, s)]
                understaffing += max(0.0, q - nominal[(t, s)])
                undercoverage += max(0.0, q - effective[(t, s)])
        return undercoverage, understaffing, undercoverage - understaffing, consistency

    best_obj = master.model.ObjVal
    n_pool = master.model.SolCount
    agg = [0.0, 0.0, 0.0, 0.0]
    cnt_sols = 0
    for si in range(n_pool):
        master.model.Params.SolutionNumber = si
        if abs(master.model.PoolObjVal - best_obj) > 1e-6:
            continue
        lam = {(g, r): round(master.lmbda[(g, r)].Xn) for (g, r) in master.lmbda}
        res = _reconstruct(lambda g, r: lam.get((g, r), 0))
        for j in range(4):
            agg[j] += res[j]
        cnt_sols += 1
    master.model.Params.SolutionNumber = 0

    if cnt_sols == 0:
        lam = {(g, r): round(master.lmbda[(g, r)].X) for (g, r) in master.lmbda}
        return _reconstruct(lambda g, r: lam.get((g, r), 0))

    return tuple(a / cnt_sols for a in agg)


if __name__ == "__main__":
    len_I, num_days, prob = 8, 14, 1.0
    T = list(range(1, num_days + 1)); I = list(range(1, len_I + 1)); K = [1, 2, 3]
    data = pd.DataFrame({'I': I + [np.nan] * (max(len(I), len(T), len(K)) - len(I)),
                          'T': T + [np.nan] * (max(len(I), len(T), len(K)) - len(T)),
                          'K': K + [np.nan] * (max(len(I), len(T), len(K)) - len(K))})
    demand_dict = generate_demand(num_days, prob, len_I, shift_probs=(50, 30, 20), delta=0.25, seed=5)

    print(f"Extension 4 Case A (Qualifications): {len_I} workers, {num_days} days")
    for mode in ("bap", "npp", "ecp"):
        print(f"\n--- {mode.upper()} ---")
        for pi in PI_VALUES:
            qual_groups = make_qual_groups(I, pi)
            uc, us, pl, cons = run_cg(data, demand_dict, qual_groups, mode)
            print(f"  pi(ICU)={pi:<5} undercover={uc:7.2f}  understaff={us:7.2f}  "
                  f"perfloss={pl:7.2f}  changes={cons:4.0f}")
