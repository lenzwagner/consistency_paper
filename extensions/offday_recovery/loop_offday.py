"""Extension 2: Performance Recovery on Off-Days.
Solves BAP, NPP, and ECP via Column Generation with the beta_g off-day
recovery multiplier (Datei/extensions.tex, app:ext:offday), for a small
example instance and a sweep of beta_g values.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import numpy as np
import pandas as pd
import gurobipy as gu
from core.base_case import get_wd_constraints
from core.masterproblem import MasterProblem
from core.worker_groups import create_groups_from_fractions
from core.nonlinear_transitions import h_func, r_func
from Utils.demand import generate_demand
from extensions.offday_recovery.subproblem_offday import SubproblemOffday

from core.base_case import K_ECP
from core.solver_base import MAX_ITR, THRESHOLD, TIME_CG_INIT, TIME_CG_SP
BETAS = [1, 2, 3]


def evaluate_schedule_beta(x_dict, days, shifts, nl_spec, beta_g):
    """Ex-post evaluation with the beta_g off-day recovery multiplier (ext:spell:off)."""
    chi, gamma_R, gamma_C, alpha_R = nl_spec['chi'], nl_spec['gamma_R'], nl_spec['gamma_C'], nl_spec['alpha_R']
    delta, e_max = nl_spec['delta'], nl_spec.get('e_max', 1.0)
    e, rho, nu, last_worked = 0.0, 0, 0, None
    perf_history = {}
    for day in days:
        curr = 0
        for s in shifts:
            if x_dict.get((day, s), 0) > 0.5:
                curr = s
                break
        if curr > 0:
            if last_worked is not None and curr != last_worked:
                nu += 1; rho = 0
                e = min(e_max, e + delta[last_worked, curr] * h_func(nu, gamma_C))
            else:
                nu = 0; rho += 1
                e = max(0.0, e - r_func(rho, chi, gamma_R, alpha_R))
            last_worked = curr
        else:
            nu = 0
            rho += beta_g  # off-day advances the stable counter by beta_g
            # model:phi / ext:spell:off: rho is simply replaced by the rescaled
            # counter -- a plain substitution into the existing single-evaluation
            # recovery formula, not a cumulative/telescoping sum.
            e = max(0.0, e - r_func(rho, chi, gamma_R, alpha_R))
        perf_history[day] = 1.0 - e
    return perf_history


def run_cg(data, demand_dict, worker_groups, beta_g, mode, max_itr=MAX_ITR, threshold=THRESHOLD,
           time_cg_init=TIME_CG_INIT, time_cg=TIME_CG_SP):
    T = data['T'].dropna().astype(int).unique().tolist()
    K = data['K'].dropna().astype(int).unique().tolist()
    I = data['I'].dropna().astype(int).unique().tolist()
    Min_WD_i, Max_WD_i = get_wd_constraints(I)

    start_perf = {(t, s): 0.0 for t in T for s in K}
    master = MasterProblem(data, demand_dict, max_itr, 0, 0, 100, start_perf, worker_groups=worker_groups)
    master.buildModel()
    master.setStartSolution()

    group_names = list(worker_groups.keys())
    x_by_group = {g: {} for g in group_names}

    itr, col_idx, improvable = 0, 0, True
    while improvable and itr < max_itr:
        master.model.Params.OutputFlag = 0
        master.model.optimize()
        duals_i, duals_ts = master.getDuals_i(), master.getDuals_ts()
        improvable = False
        for g_idx, (gname, group) in enumerate(worker_groups.items(), start=1):
            eps_sp = group.epsilon if mode == 'bap' else 0.0
            sp = SubproblemOffday(duals_i.get(g_idx, 0.0), duals_ts, data, group.worker_ids[0], itr,
                                   eps_sp, Min_WD_i, Max_WD_i, group.chi, beta_g=beta_g)
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
            # Pool search: extract ALL improving near-optimal schedules per pricing
            # call for column diversity (mirrors the labeling's implicit Pareto set).
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
                x_vals = {(t, s): sp.x[t, s].Xn for t in T for s in K}
                perf_vals = {(t, s): sp.performance[t, s, sp.itr].Xn for t in T for s in K}
                col = {(t, s, col_idx): perf_vals[(t, s)] for t in T for s in K}
                master.addColumn(col_idx - 1, col, g_idx)
                x_by_group[gname][col_idx] = x_vals
                improvable = True
        itr += 1

    # Restore integrality and build the optimal solution pool (paper: NPP/ECP-style
    # metrics are averaged ex post across the optimal pool to remove the arbitrary
    # schedule<->worker pairing).
    master.model.Params.OutputFlag = 0
    for v in master.lmbda.values():
        v.VType = gu.GRB.INTEGER
    master.model.Params.PoolSearchMode = 2
    master.model.Params.PoolSolutions = 50
    master.model.Params.PoolGap = 0.0
    master.model.optimize()

    def _reconstruct(get_count):
        ls_x_by_worker = []
        for g_idx, (gname, group) in enumerate(worker_groups.items(), start=1):
            for r in master.active_roster_by_group.get(g_idx, []):
                cnt = get_count(g_idx, r)
                if cnt <= 0:
                    continue
                x_sched = x_by_group[gname].get(r, {})
                x_dict = {(t, s): x_sched.get((t, s), 0) for t in T for s in K}
                for _ in range(cnt):
                    ls_x_by_worker.append((gname, group, x_dict))

        nominal = {(t, s): 0.0 for t in T for s in K}
        effective = {(t, s): 0.0 for t in T for s in K}
        consistency = 0
        for gname, group, x_dict in ls_x_by_worker:
            nl_spec = {'chi': group.chi, 'gamma_R': group.gamma_R, 'gamma_C': group.gamma_C,
                       'alpha_R': group.alpha_R, 'delta': group.delta, 'e_max': group.e_max}
            perf_history = evaluate_schedule_beta(x_dict, T, K, nl_spec, beta_g)
            last = None
            for t in T:
                worked_shift = 0
                for s in K:
                    if x_dict.get((t, s), 0) > 0.5:
                        worked_shift = s
                        nominal[(t, s)] += 1.0
                        effective[(t, s)] += perf_history[t]
                        break
                if worked_shift != 0 and last is not None and last != 0 and worked_shift != last:
                    consistency += 1
                last = worked_shift

        understaffing, undercoverage = 0.0, 0.0
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
        r = _reconstruct(lambda g, r_: lam.get((g, r_), 0))
        for j in range(4):
            agg[j] += r[j]
        cnt_sols += 1
    master.model.Params.SolutionNumber = 0

    if cnt_sols == 0:
        lam = {(g, r): round(master.lmbda[(g, r)].X) for (g, r) in master.lmbda}
        undercoverage, understaffing, perfloss, consistency = _reconstruct(lambda g, r_: lam.get((g, r_), 0))
    else:
        undercoverage, understaffing, perfloss, consistency = [a / cnt_sols for a in agg]
    return undercoverage, understaffing, perfloss, consistency


if __name__ == "__main__":
    len_I, num_days, prob = 6, 14, 1.0
    T = list(range(1, num_days + 1)); I = list(range(1, len_I + 1)); K = [1, 2, 3]
    data = pd.DataFrame({'I': I + [np.nan] * (max(len(I), len(T), len(K)) - len(I)),
                          'T': T + [np.nan] * (max(len(I), len(T), len(K)) - len(T)),
                          'K': K + [np.nan] * (max(len(I), len(T), len(K)) - len(K))})
    demand_dict = generate_demand(num_days, prob, len_I, shift_probs=(50, 30, 20), delta=0.25, seed=3)
    worker_groups = create_groups_from_fractions(I, "1/2,1/2", [(0.5, 0.5, 2, 7), (1.5, 1.5, 4, 21)])

    print(f"Extension 2 (Off-Day Recovery): {len_I} workers, {num_days} days")
    for mode in ("bap", "npp", "ecp"):
        print(f"\n--- {mode.upper()} ---")
        for beta in BETAS:
            uc, us, pl, cons = run_cg(data, demand_dict, worker_groups, beta, mode)
            print(f"  beta_g={beta}  undercover={uc:7.2f}  understaff={us:7.2f}  "
                  f"perfloss={pl:7.2f}  changes={cons:4.0f}")
