"""Extension 3: Worker Day-Off Preferences.
Solves BAP, NPP, and ECP via Column Generation with individual per-worker
pricing and a preference-day cost surcharge (Datei/extensions.tex,
app:ext:pref). Since preferences break within-group homogeneity, each worker
is treated as its own singleton group (reusing the master's per-group
convexity mechanism with group size 1), matching the paper's statement that
pricing calls increase from |G| to |I|.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import random
import numpy as np
import pandas as pd
import gurobipy as gu
from core.base_case import get_wd_constraints
from core.masterproblem import MasterProblem
from core.worker_groups import create_groups_from_fractions, WorkerGroup
from Utils.demand import generate_demand
from extensions.preferences.subproblem_preferences import SubproblemPreferences

from core.base_case import K_ECP
from core.solver_base import MAX_ITR, THRESHOLD, TIME_CG_INIT, TIME_CG_SP
LAMBDAS_P = [0.0, 0.5, 2.0]


def make_singleton_groups(I, base_groups):
    """Split each resilience group's workers into singleton per-worker groups,
    inheriting that worker's group parameters."""
    group_of = {}
    for gname, g in base_groups.items():
        for w in g.worker_ids:
            group_of[w] = g
    singles = {}
    for w in I:
        base = group_of[w]
        singles[f"w{w}"] = WorkerGroup(f"w{w}", base.epsilon, base.chi, [w],
                                        gamma_C=base.gamma_C, gamma_R=base.gamma_R,
                                        T_R=base.T_R, delta=base.delta)
    return singles


def run_cg(data, demand_dict, singleton_groups, pref_by_worker, lam_pref, mode,
           max_itr=MAX_ITR, threshold=THRESHOLD, time_cg_init=TIME_CG_INIT, time_cg=TIME_CG_SP):
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
            sp = SubproblemPreferences(duals_i.get(g_idx, 0.0), duals_ts, data, wid, itr,
                                        eps_sp, Min_WD_i, Max_WD_i, group.chi,
                                        pref_by_worker.get(wid, []), lam_pref)
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
                perf_vals = {(t, s): sp.performance[t, s, sp.itr].Xn for t in T for s in K}
                x_vals = {(t, s): sp.x[t, s].Xn for t in T for s in K}
                # Fixed per-column preference-penalty cost lambda_P*sum_{d in P_i} y_id
                # (y_id=1 means WORKING on day d, i.e. NOT honoring the preferred off-day),
                # matching the SP's day-specific arc surcharge. Must be carried by the
                # master so the true combined objective drives the final integer choice.
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

    # Restore integrality and pool-average (paper: NPP/ECP-style metrics are averaged
    # ex post across the optimal pool). With singleton per-worker groups there is no
    # cross-worker column-sharing degeneracy, but ties among equally optimal day-off
    # placements can still occur, so pooling remains the principled choice.
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
                perf_sched = perf_by_group[gname].get(r, {})
                prefs = pref_by_worker.get(wid, [])
                total_pref += len(prefs)
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

    undercoverage, understaffing, perfloss, consistency, satisfaction_rate = [a / cnt_sols for a in agg]
    return undercoverage, understaffing, perfloss, consistency, satisfaction_rate


if __name__ == "__main__":
    random.seed(11)
    len_I, num_days, prob = 6, 14, 1.0
    T = list(range(1, num_days + 1)); I = list(range(1, len_I + 1)); K = [1, 2, 3]
    data = pd.DataFrame({'I': I + [np.nan] * (max(len(I), len(T), len(K)) - len(I)),
                          'T': T + [np.nan] * (max(len(I), len(T), len(K)) - len(T)),
                          'K': K + [np.nan] * (max(len(I), len(T), len(K)) - len(K))})
    demand_dict = generate_demand(num_days, prob, len_I, shift_probs=(50, 30, 20), delta=0.25, seed=3)
    base_groups = create_groups_from_fractions(I, "1/2,1/2", [(0.5, 0.5, 2, 7), (1.5, 1.5, 4, 21)])
    singleton_groups = make_singleton_groups(I, base_groups)

    # Random preference scenario: each worker prefers 1-2 random off-days.
    pref_by_worker = {w: random.sample(T, random.randint(1, 2)) for w in I}
    print(f"Extension 3 (Preferences): {len_I} workers, {num_days} days")
    print("Preferred off-days per worker:", pref_by_worker)

    for mode in ("bap", "npp", "ecp"):
        print(f"\n--- {mode.upper()} ---")
        for lam in LAMBDAS_P:
            uc, us, pl, cons, sat = run_cg(data, demand_dict, singleton_groups, pref_by_worker, lam, mode)
            print(f"  lambda_P={lam:<5} undercover={uc:7.2f}  understaff={us:7.2f}  "
                  f"perfloss={pl:7.2f}  changes={cons:4.0f}  pref_satisfaction={sat:.2f}")
