"""Extension 3 (Worker Day-Off Preferences) solved with the exact SPPRC
labeling algorithm (core.subproblem_dp_extensions.SubproblemPreferencesDP),
matching extensions.tex: preference penalty enters as a day-specific arc
surcharge, individual per-worker pricing (singleton groups).
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import random
import gurobipy as gu
import numpy as np
import pandas as pd
from core.base_case import get_wd_constraints
from core.masterproblem import MasterProblem
from core.worker_groups import create_groups_from_fractions
from core.subproblem_dp_extensions import SubproblemPreferencesDP
from core.subproblem_dp_extensions_numba import SubproblemPreferencesNumba
from Utils.demand import generate_demand
from extensions.preferences.loop_preferences import make_singleton_groups, LAMBDAS_P
from core.nonlinear_transitions import evaluate_schedule_nl

from core.base_case import K_ECP
from core.solver_base import MAX_ITR, THRESHOLD, TIME_CG_INIT, TIME_CG_SP


def run_cg(data, demand_dict, singleton_groups, pref_by_worker, lam_pref, mode,
           max_itr=MAX_ITR, threshold=THRESHOLD, time_cg=TIME_CG_SP, solver='dp'):
    """solver: 'dp' (exact Python label-setting, default) or 'numba' (JIT-compiled,
    same recursion -- see core.subproblem_dp_extensions_numba.SubproblemPreferencesNumba)."""
    SubproblemCls = SubproblemPreferencesNumba if solver == 'numba' else SubproblemPreferencesDP
    T = data['T'].dropna().astype(int).unique().tolist()
    K = data['K'].dropna().astype(int).unique().tolist()
    I = data['I'].dropna().astype(int).unique().tolist()
    Min_WD_i, Max_WD_i = get_wd_constraints(I)

    start_perf = {(t, s): 0.0 for t in T for s in K}
    master = MasterProblem(data, demand_dict, max_itr, 0, 0, 100, start_perf, worker_groups=singleton_groups)
    master.buildModel()
    master.setStartSolution()

    group_names = list(singleton_groups.keys())
    perf_by_group, x_by_group = {g: {} for g in group_names}, {g: {} for g in group_names}

    itr, col_idx, improvable = 0, 0, True
    while improvable and itr < max_itr:
        master.model.Params.OutputFlag = 0
        master.model.optimize()
        duals_i, duals_ts = master.getDuals_i(), master.getDuals_ts()
        improvable = False
        for g_idx, (gname, group) in enumerate(singleton_groups.items(), start=1):
            wid = group.worker_ids[0]
            eps_sp = group.epsilon if mode == 'bap' else 0.0
            sp = SubproblemCls(duals_i.get(g_idx, 0.0), duals_ts, data, wid, itr,
                               eps_sp, Min_WD_i, Max_WD_i, group.chi,
                               pref_by_worker.get(wid, []), lam_pref)
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
            perf_vals = {(t, s): v for (t, s, _), v in sp.getNewSchedule().items()}
            x_vals = sp.getOptX()
            prefs = pref_by_worker.get(wid, [])
            worked_on_pref = sum(1 for t in prefs if any(x_vals.get((t, s), 0) > 0.5 for s in K))
            col_cost = lam_pref * worked_on_pref
            master.addLambda(col_idx - 1, g_idx, extra_cost=col_cost)
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
        understaffing, undercoverage, satisfied, total_pref = 0.0, 0.0, 0, 0
        nominal = {(t, s): 0.0 for t in T for s in K}
        effective = {(t, s): 0.0 for t in T for s in K}
        consistency = 0
        for g_idx, (gname, group) in enumerate(singleton_groups.items(), start=1):
            wid = group.worker_ids[0]
            for r in master.active_roster_by_group.get(g_idx, []):
                rcnt = get_count(g_idx, r)
                if rcnt <= 0:
                    continue
                x_sched = x_by_group[gname].get(r, {})
                # Ex-post re-evaluation under the group's TRUE behavioral params
                # (mirrors Ext. 2's evaluate_schedule_beta), so NPP/ECP are charged
                # for real degradation instead of the SP's own eps=0 bookkeeping.
                nl_spec = {'epsilon': getattr(group, 'epsilon', 0.06), 'chi': group.chi,
                           'gamma_R': group.gamma_R, 'gamma_C': group.gamma_C,
                           'alpha_R': group.alpha_R, 'delta': group.delta, 'e_max': group.e_max}
                perf_hist, *_ = evaluate_schedule_nl(x_sched, T, K, nl_spec)
                prefs = pref_by_worker.get(wid, [])
                total_pref += len(prefs)
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
                    if worked == 0 and t in prefs:
                        satisfied += 1
                    last = worked

        for t in T:
            for s in K:
                q = demand_dict[(t, s)]
                understaffing += max(0.0, q - nominal[(t, s)])
                undercoverage += max(0.0, q - effective[(t, s)])
        perfloss = undercoverage - understaffing
        satisfaction_rate = satisfied / total_pref if total_pref else 0.0
        return undercoverage, understaffing, perfloss, consistency, satisfaction_rate

    best_obj = master.model.ObjVal
    n_pool = master.model.SolCount
    agg = [0.0, 0.0, 0.0, 0.0, 0.0]
    cnt_sols = 0
    for si in range(n_pool):
        master.model.Params.SolutionNumber = si
        if abs(master.model.PoolObjVal - best_obj) > 1e-6:
            continue
        lam = {(g, r): round(master.lmbda[(g, r)].Xn) for (g, r) in master.lmbda}
        res = _reconstruct(lambda g, r: lam.get((g, r), 0))
        for j in range(5):
            agg[j] += res[j]
        cnt_sols += 1
    master.model.Params.SolutionNumber = 0

    if cnt_sols == 0:
        lam = {(g, r): round(master.lmbda[(g, r)].X) for (g, r) in master.lmbda}
        return _reconstruct(lambda g, r: lam.get((g, r), 0))
    return tuple(a / cnt_sols for a in agg)


if __name__ == "__main__":
    random.seed(11)
    len_I, num_days, prob = 6, 14, 1.0
    T = list(range(1, num_days + 1)); I = list(range(1, len_I + 1)); K = [1, 2, 3]
    maxlen = max(len(I), len(T), len(K))
    data = pd.DataFrame({'I': I + [np.nan] * (maxlen - len(I)),
                          'T': T + [np.nan] * (maxlen - len(T)),
                          'K': K + [np.nan] * (maxlen - len(K))})
    demand_dict = generate_demand(num_days, prob, len_I, shift_probs=(50, 30, 20), delta=0.25, seed=3)
    base_groups = create_groups_from_fractions(I, "1/2,1/2", [(0.5, 0.5, 2, 7), (1.5, 1.5, 4, 21)])
    singleton_groups = make_singleton_groups(I, base_groups)

    pref_by_worker = {w: random.sample(T, random.randint(1, 2)) for w in I}
    print(f"Extension 3 (Preferences, LABELING): {len_I} workers, {num_days} days")
    print("Preferred off-days per worker:", pref_by_worker)

    for mode in ("bap", "npp", "ecp"):
        print(f"\n--- {mode.upper()} ---")
        for lam in LAMBDAS_P:
            uc, us, pl, cons, sat = run_cg(data, demand_dict, singleton_groups, pref_by_worker, lam, mode)
            print(f"  lambda_P={lam:<5} undercover={uc:7.2f}  understaff={us:7.2f}  "
                  f"perfloss={pl:7.2f}  changes={cons:4.0f}  pref_satisfaction={sat:.2f}")
