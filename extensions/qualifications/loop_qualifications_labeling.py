"""Extension 4, Case A (Qualifications) solved with the exact SPPRC labeling
algorithm (core.subproblem_dp_extensions.SubproblemQualificationsDP), matching
extensions.tex's "Labeling Implementation" paragraph for Case A: the arc set
is restricted to S_q, all other recursions/dominance are unchanged.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import gurobipy as gu
import pandas as pd
import numpy as np
from core.base_case import get_wd_constraints
from core.masterproblem import MasterProblem
from core.subproblem_dp_extensions import SubproblemQualificationsDP
from core.subproblem_dp_extensions_numba import SubproblemQualificationsNumba
from Utils.demand import generate_demand
from extensions.qualifications.loop_qualifications import make_qual_groups, PI_VALUES
from core.nonlinear_transitions import evaluate_schedule_nl

from core.base_case import K_ECP
from core.solver_base import MAX_ITR, THRESHOLD, TIME_CG_INIT, TIME_CG_SP


def run_cg(data, demand_dict, qual_groups, mode, max_itr=MAX_ITR, threshold=THRESHOLD, time_cg=TIME_CG_SP,
           solver='dp'):
    """solver: 'dp' (exact Python label-setting, default) or 'numba' (JIT-compiled,
    same recursion -- see core.subproblem_dp_extensions_numba.SubproblemQualificationsNumba)."""
    SubproblemCls = SubproblemQualificationsNumba if solver == 'numba' else SubproblemQualificationsDP
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
            sp = SubproblemCls(duals_i.get(g_idx, 0.0), duals_ts, data, group.worker_ids[0], itr,
                               eps_sp, Min_WD_i, Max_WD_i, group.chi, group.eligible_shifts)
            if mode == 'bap':
                sp.gamma_C, sp.gamma_R, sp.alpha_R, sp.delta, sp.e_max = (
                    group.gamma_C, group.gamma_R, group.alpha_R, group.delta, group.e_max)
            else:
                sp.gamma_C, sp.gamma_R, sp.alpha_R, sp.e_max = 1.0, 1.0, 1.0, 0.0
                sp.delta = np.zeros((4, 4))
            if mode == 'ecp':
                sp.addECPConstraint(K_ECP)
            sp.buildModel()
            sp.solveModelOpt(time_cg)
            if sp.getStatus() != gu.GRB.OPTIMAL:
                continue
            reduced_cost = sp.model.objval
            if reduced_cost >= -threshold:
                continue
            col_idx += 1
            master.addLambda(col_idx - 1, g_idx)
            perf_vals = {(t, s): v for (t, s, _), v in sp.getNewSchedule().items()}
            x_vals = sp.getOptX()
            col = {(t, s, col_idx): perf_vals[(t, s)] for t in T for s in K}
            master.addColumn(col_idx - 1, col, g_idx)
            perf_by_group[gname][col_idx] = {(t, s, col_idx): perf_vals[(t, s)] for t in T for s in K}
            x_by_group[gname][col_idx] = x_vals
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
                # Ex-post re-evaluation under the group's TRUE behavioral params
                # (mirrors Ext. 2's evaluate_schedule_beta), so NPP/ECP are charged
                # for real degradation instead of the SP's own eps=0 bookkeeping.
                nl_spec = {'epsilon': getattr(group, 'epsilon', 0.06), 'chi': group.chi,
                           'gamma_R': group.gamma_R, 'gamma_C': group.gamma_C,
                           'alpha_R': group.alpha_R, 'delta': group.delta, 'e_max': group.e_max}
                perf_hist, *_ = evaluate_schedule_nl(x_sched, T, K, nl_spec)
                for _ in range(cnt):
                    last = None
                    for t in T:
                        worked = 0
                        for s in K:
                            if x_sched.get((t, s), 0) > 0.5:
                                worked = s
                                nominal[(t, s)] += 1.0
                                effective[(t, s)] += perf_hist[t]
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
    maxlen = max(len(I), len(T), len(K))
    data = pd.DataFrame({'I': I + [np.nan] * (maxlen - len(I)),
                          'T': T + [np.nan] * (maxlen - len(T)),
                          'K': K + [np.nan] * (maxlen - len(K))})
    demand_dict = generate_demand(num_days, prob, len_I, shift_probs=(50, 30, 20), delta=0.25, seed=5)

    print(f"Extension 4 Case A (Qualifications, LABELING): {len_I} workers, {num_days} days")
    for mode in ("bap", "npp", "ecp"):
        print(f"\n--- {mode.upper()} ---")
        for pi in PI_VALUES:
            qual_groups = make_qual_groups(I, pi)
            uc, us, pl, cons = run_cg(data, demand_dict, qual_groups, mode)
            print(f"  pi(ICU)={pi:<5} undercover={uc:7.2f}  understaff={us:7.2f}  "
                  f"perfloss={pl:7.2f}  changes={cons:4.0f}")
