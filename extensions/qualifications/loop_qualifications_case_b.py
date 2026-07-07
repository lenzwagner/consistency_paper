"""Extension 4, Case B: Heterogeneous Worker Qualifications (overlapping).
Solves BAP, NPP, and ECP via Column Generation with individual per-worker
pricing AND genuine qualification-specific demand rows Q_ds^q
(Datei/extensions.tex, app:ext:qual, Case B, eq. ext:qual:overlap).

Key mechanism: shifts E and L are jointly demanded by BOTH qualifications
(q1=general, q2=ICU) -- e.g. day/evening ICU patients still need ICU-certified
staff, while the ward simultaneously needs general coverage. Night (N) remains
ICU-only. A worker holding BOTH qualifications therefore faces a genuine
routing choice on E/L: which qualification's demand row to cover. This is
implemented by encoding each (shift, qualification) pair as a virtual shift
vshift = 10*shift + qualification, and building the MASTER PROBLEM's demand
constraints over these virtual shifts (not over shifts alone) -- i.e. the
master literally gets one demand row per (day, shift, qualification), exactly
Q_ds^q from the paper. The existing generic MasterProblem class needs no
modification: it is generic over its "shift" index, so passing vshift ids as
the shift dimension is sufficient.

Pricing (SubproblemQualificationsOverlapDP, core/subproblem_dp_extensions.py)
branches over q on every working arc using the qualification-specific dual
pi_ds^q, and returns columns already keyed by vshift.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from dataclasses import dataclass
from typing import Dict, List
import numpy as np
import pandas as pd
import gurobipy as gu
from core.base_case import get_wd_constraints
from core.masterproblem import MasterProblem
from core.worker_groups import get_calibrated_delta, compute_alpha_R, WorkerGroup
from core.subproblem_dp_extensions import SubproblemQualificationsOverlapDP
from core.subproblem_dp_extensions_numba import SubproblemQualificationsOverlapNumba
from core.nonlinear_transitions import evaluate_schedule_nl
from Utils.demand import generate_demand

from core.base_case import K_ECP
from core.solver_base import MAX_ITR, THRESHOLD, TIME_CG_INIT, TIME_CG_SP

PI_VALUES = [0.20, 0.35, 0.50, 0.65]

# Shift -> set of qualifications that JOINTLY demand coverage on that shift.
# E (1) and L (2): overlap -- both general (q1) and ICU (q2) demand exist.
# N (3): ICU-only, no overlap (mirrors Case A's bottleneck structure).
SHIFT_TO_QUALIFICATIONS: Dict[int, set] = {1: {1, 2}, 2: {1, 2}, 3: {2}}


def all_vshifts():
    """Every (shift, qualification) pair actually demanded, encoded as
    vshift = 10*shift + qualification."""
    return sorted({10 * s + q for s, qs in SHIFT_TO_QUALIFICATIONS.items() for q in qs})


def build_demand_case_b(num_days, prob, demand, seed, split_q1=0.6):
    """Build the qualification-indexed demand dict {(day, vshift): Q_ds^q}.

    A shift's baseline total demand Q_ds (from the same generator used
    elsewhere) is split across its demanded qualifications: on overlapping
    shifts (E, L), a fraction split_q1 goes to the general-ward row (q1) and
    the rest to the ICU row (q2); on ICU-only shifts (N), all demand goes to q2.
    """
    base = generate_demand(num_days, prob, demand, shift_probs=(50, 30, 20),
                           delta=0.25, seed=seed, prop_volatility=0.0)
    demand_vshift = {}
    for day in range(1, num_days + 1):
        for shift, quals in SHIFT_TO_QUALIFICATIONS.items():
            q_tot = base[(day, shift)]
            if len(quals) == 1:
                q = next(iter(quals))
                demand_vshift[(day, 10 * shift + q)] = q_tot
            else:
                q1_val = int(round(split_q1 * q_tot))
                q2_val = q_tot - q1_val
                demand_vshift[(day, 10 * shift + 1)] = q1_val
                demand_vshift[(day, 10 * shift + 2)] = q2_val
    return demand_vshift


def build_data_master(I, T):
    """DataFrame for the master problem: 'K' = virtual shifts (shift*10+qual),
    NOT real shifts, so MasterProblem's generic demand-constraint machinery
    creates one row per (day, shift, qualification)."""
    vs = all_vshifts()
    maxlen = max(len(I), len(T), len(vs))
    return pd.DataFrame({
        'I': I + [np.nan] * (maxlen - len(I)),
        'T': T + [np.nan] * (maxlen - len(T)),
        'K': vs + [np.nan] * (maxlen - len(vs)),
    })


@dataclass
class WorkerQualB:
    """Individual worker spec for Case B (overlapping qualifications)."""
    worker_id: int
    chi: int
    gamma_C: float
    gamma_R: float
    T_R: int
    eligible_qualifications: set  # Set of q IDs this worker can hold
    delta: object = None
    e_max: float = 1.0
    epsilon: float = 0.06

    def __post_init__(self):
        if self.delta is None:
            self.delta = get_calibrated_delta()
        self.alpha_R = compute_alpha_R(self.T_R, self.gamma_R)


def make_workers_case_b(I, pi):
    """Partition workers into individual specs with overlapping qualifications.
    pi = fraction of ICU-certified workers; ~half of ICU workers are ALSO
    general-ward qualified (the genuine overlap case)."""
    n = len(I)
    n_icu = max(1, round(pi * n))
    icu_ids, gen_ids = I[:n_icu], I[n_icu:]
    workers = {}

    for i, wid in enumerate(gen_ids):
        is_resilient = (i % 2 == 0)
        chi, gamma_C, gamma_R, T_R = (2, 0.5, 0.5, 7) if is_resilient else (4, 1.5, 1.5, 21)
        workers[wid] = WorkerQualB(worker_id=wid, chi=chi, gamma_C=gamma_C, gamma_R=gamma_R,
                                   T_R=T_R, eligible_qualifications={1}, epsilon=0.06)

    for i, wid in enumerate(icu_ids):
        is_resilient = (i % 2 == 0)
        chi, gamma_C, gamma_R, T_R = (2, 0.5, 0.5, 7) if is_resilient else (4, 1.5, 1.5, 21)
        also_general = (i % 2 == 1)  # ~50% of ICU workers also general-qualified
        qual_set = {1, 2} if also_general else {2}
        workers[wid] = WorkerQualB(worker_id=wid, chi=chi, gamma_C=gamma_C, gamma_R=gamma_R,
                                   T_R=T_R, eligible_qualifications=qual_set, epsilon=0.06)
    return workers


def run_cg(data_sp, data_master, demand_vshift, workers_case_b, mode, max_itr=MAX_ITR,
           threshold=THRESHOLD, time_cg_init=TIME_CG_INIT, time_cg=TIME_CG_SP, solver='dp'):
    """Column generation with individual worker pricing and qualification-
    indexed master demand rows (Case B).

    solver: 'dp' (exact Python label-setting, default) or 'numba' (JIT-compiled,
    same recursion -- see core.subproblem_dp_extensions_numba.SubproblemQualificationsOverlapNumba).

    Args:
        data_sp: DataFrame with real shifts (K=[1,2,3]) for pricing subproblems.
        data_master: DataFrame with virtual shifts (K=vshift ids) for the master.
        demand_vshift: {(day, vshift): Q_ds^q}.
        workers_case_b: Dict worker_id -> WorkerQualB.

    Returns:
        (undercoverage, understaffing, perfloss, consistency) -- aggregated
        over all (day, shift, qualification) demand rows; consistency counts
        REAL shift changes (qualification choice is irrelevant to it).
    """
    SubproblemCls = SubproblemQualificationsOverlapNumba if solver == 'numba' else SubproblemQualificationsOverlapDP
    T = data_sp['T'].dropna().astype(int).unique().tolist()
    K = data_sp['K'].dropna().astype(int).unique().tolist()  # real shifts, for ex-post nl evaluation
    I = data_sp['I'].dropna().astype(int).unique().tolist()
    VS = all_vshifts()
    Min_WD_i, Max_WD_i = get_wd_constraints(I)

    start_perf = {(t, vs): 0.0 for t in T for vs in VS}

    pseudo_groups = {}
    for wid in I:
        w = workers_case_b[wid]
        gname = f"worker_{wid}"
        pseudo_groups[gname] = WorkerGroup(name=gname, epsilon=w.epsilon, chi=w.chi,
                                           worker_ids=[wid], gamma_C=w.gamma_C, gamma_R=w.gamma_R,
                                           T_R=w.T_R, delta=w.delta)
        pseudo_groups[gname].e_max = w.e_max
        pseudo_groups[gname].alpha_R = w.alpha_R

    master = MasterProblem(data_master, demand_vshift, max_itr, 0, 0, 100, start_perf,
                           worker_groups=pseudo_groups)
    master.buildModel()
    master.setStartSolution()

    x_by_worker = {wid: {} for wid in I}          # (day, vshift) -> 0/1
    perf_by_worker = {wid: {} for wid in I}        # (day, vshift, roster) -> perf
    realshift_by_worker = {wid: {} for wid in I}   # roster -> {day: real shift}

    itr, col_idx, improvable = 0, 0, True
    while improvable and itr < max_itr:
        master.model.Params.OutputFlag = 0
        master.model.optimize()

        duals_i = master.getDuals_i()
        duals_ts_vs = master.getDuals_ts()  # {(t, vshift): pi}
        duals_ts_q = {}
        for (t, vs), pi in duals_ts_vs.items():
            s, q = vs // 10, vs % 10
            duals_ts_q[(t, s, q)] = pi

        improvable = False
        for g_idx, (gname, group) in enumerate(pseudo_groups.items(), start=1):
            wid = group.worker_ids[0]
            w = workers_case_b[wid]
            eps_sp = w.epsilon if mode == 'bap' else 0.0

            sp = SubproblemCls(
                duals_i.get(g_idx, 0.0), duals_ts_q, SHIFT_TO_QUALIFICATIONS,
                data_sp, wid, itr, eps_sp, Min_WD_i, Max_WD_i, w.chi,
                w.eligible_qualifications
            )
            if mode == 'bap':
                sp.gamma_C, sp.gamma_R, sp.alpha_R, sp.delta, sp.e_max = (
                    w.gamma_C, w.gamma_R, w.alpha_R, w.delta, w.e_max
                )
            else:
                sp.gamma_C, sp.gamma_R, sp.alpha_R, sp.e_max = 1.0, 1.0, 1.0, 0.0
                sp.delta = np.zeros((4, 4))
            if mode == 'ecp':
                sp.addECPConstraint(K_ECP)

            sp.buildModel()
            sp.solveModelOpt(time_cg_init if itr == 0 else time_cg)

            if sp.getStatus() != gu.GRB.OPTIMAL:
                continue
            reduced_cost = sp.model.objval
            if reduced_cost >= -threshold:
                continue

            col_idx += 1
            master.addLambda(col_idx - 1, g_idx)

            sched = sp.getNewSchedule()  # {(t, vshift, sp.itr): perf}
            perf_vals = {(t_, vs): v for (t_, vs, _), v in sched.items()}
            col = {(t_, vs, col_idx): perf_vals[(t_, vs)] for t_ in T for vs in VS}
            master.addColumn(col_idx - 1, col, g_idx)

            perf_by_worker[wid][col_idx] = col
            x_by_worker[wid][col_idx] = sp.getOptX()
            realshift_by_worker[wid][col_idx] = sp.getRealShiftSeq()

            improvable = True
        itr += 1

    master.model.Params.OutputFlag = 0
    for v in master.lmbda.values():
        v.VType = gu.GRB.INTEGER
    master.model.Params.PoolSearchMode = 2
    master.model.Params.PoolSolutions = 50
    master.model.Params.PoolGap = 0.0
    master.model.optimize()

    def _reconstruct(get_count):
        nominal = {(t, vs): 0.0 for t in T for vs in VS}
        effective = {(t, vs): 0.0 for t in T for vs in VS}
        consistency = 0

        for g_idx, (gname, group) in enumerate(pseudo_groups.items(), start=1):
            wid = group.worker_ids[0]
            for r in master.active_roster_by_group.get(g_idx, []):
                cnt = get_count(g_idx, r)
                if cnt <= 0:
                    continue
                x_sched = x_by_worker[wid].get(r, {})
                real_seq = realshift_by_worker[wid].get(r, {})

                # Ex-post re-evaluation under the group's TRUE behavioral params
                # (mirrors Ext. 2's evaluate_schedule_beta), so NPP/ECP are charged
                # for real degradation instead of the SP's own eps=0 bookkeeping.
                # Uses the REAL shift sequence (vshift//10), since degradation
                # depends on the physical shift transition, not the qualification.
                x_dict_real = {(t, real_seq[t]): 1.0 for t in T if real_seq.get(t, 0)}
                nl_spec = {'epsilon': getattr(group, 'epsilon', 0.06), 'chi': group.chi,
                           'gamma_R': group.gamma_R, 'gamma_C': group.gamma_C,
                           'alpha_R': group.alpha_R, 'delta': group.delta, 'e_max': group.e_max}
                perf_hist, *_ = evaluate_schedule_nl(x_dict_real, T, K, nl_spec)

                for _ in range(cnt):
                    last = None
                    for t in T:
                        for vs in VS:
                            if x_sched.get((t, vs), 0) > 0.5:
                                nominal[(t, vs)] += 1.0
                                effective[(t, vs)] += perf_hist[t]
                        worked = real_seq.get(t, 0)
                        if worked != 0 and last is not None and last != 0 and worked != last:
                            consistency += 1
                        last = worked

        understaffing, undercoverage = 0.0, 0.0
        for t in T:
            for vs in VS:
                q = demand_vshift.get((t, vs), 0.0)
                understaffing += max(0.0, q - nominal[(t, vs)])
                undercoverage += max(0.0, q - effective[(t, vs)])
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
    T = list(range(1, num_days + 1))
    I = list(range(1, len_I + 1))
    K = [1, 2, 3]

    data_sp = pd.DataFrame({
        'I': I + [np.nan] * (max(len(I), len(T), len(K)) - len(I)),
        'T': T + [np.nan] * (max(len(I), len(T), len(K)) - len(T)),
        'K': K + [np.nan] * (max(len(I), len(T), len(K)) - len(K))
    })
    data_master = build_data_master(I, T)
    demand_vshift = build_demand_case_b(num_days, prob, len_I, seed=5)

    print(f"Extension 4 Case B (Overlapping Qualifications): {len_I} workers, {num_days} days")
    print(f"  vshifts (shift*10+qual): {all_vshifts()}  (11/12: E general/ICU, "
          f"21/22: L general/ICU, 32: N ICU-only)")

    for mode in ("bap", "npp", "ecp"):
        print(f"\n--- {mode.upper()} ---")
        for pi in PI_VALUES:
            workers = make_workers_case_b(I, pi)
            uc, us, pl, cons = run_cg(data_sp, data_master, demand_vshift, workers, mode)
            print(f"  pi(ICU)={pi:<5} undercover={uc:7.2f}  understaff={us:7.2f}  "
                  f"perfloss={pl:7.2f}  changes={cons:4.0f}")
