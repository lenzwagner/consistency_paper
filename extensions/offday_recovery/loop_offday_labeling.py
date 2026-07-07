"""Extension 2 (Off-Day Recovery, beta_g) solved with the exact SPPRC labeling
algorithm (core.subproblem_dp_extensions.SubproblemOffdayDP), matching
extensions.tex's ext:spell:off recursion: off-day arcs advance rho by beta_g.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import gurobipy as gu
import numpy as np
import pandas as pd
from core.base_case import get_wd_constraints
from core.masterproblem import MasterProblem
from core.worker_groups import create_groups_from_fractions
from core.subproblem_dp_extensions import SubproblemOffdayDP
from core.subproblem_dp_extensions_numba import SubproblemOffdayNumba
from Utils.demand import generate_demand
from extensions.offday_recovery.loop_offday import evaluate_schedule_beta, BETAS

from core.base_case import K_ECP
from core.solver_base import MAX_ITR, THRESHOLD, TIME_CG_INIT, TIME_CG_SP


def optimize_schedule(data, demand_dict, worker_groups, mode, beta_g=1, max_itr=MAX_ITR,
                       threshold=THRESHOLD, time_cg=TIME_CG_SP, solver='dp'):
    """Solve the CG/labeling master once for the given mode.

    For NPP/ECP (extensions.tex:80: "since the NPP ignores performance
    entirely, it does not use the multiplier in scheduling"), pricing is
    provably beta_g-invariant (e_max=0 forces p=1 regardless of rho), so this
    should be solved ONCE and reused across all beta_g evaluations -- solving
    it separately per beta_g only adds tie-breaking noise among the many
    reduced-cost-equal schedules (rho, carried for bookkeeping even when
    irrelevant to cost, perturbs the label-dominance grouping and hence which
    tied-optimal schedule survives). For BAP, beta_g genuinely affects pricing
    and must be re-solved per beta_g.

    solver: 'dp' (exact Python label-setting, default) or 'numba' (JIT-compiled,
    same recursion -- see core.subproblem_dp_extensions_numba.SubproblemOffdayNumba).
    """
    SubproblemCls = SubproblemOffdayNumba if solver == 'numba' else SubproblemOffdayDP
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
            sp = SubproblemCls(duals_i.get(g_idx, 0.0), duals_ts, data, group.worker_ids[0], itr,
                               eps_sp, Min_WD_i, Max_WD_i, group.chi, beta_g=beta_g)
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
            x_vals = sp.getOptX()
            perf_vals = {(t, s): v for (t, s, _), v in sp.getNewSchedule().items()}
            col = {(t, s, col_idx): perf_vals[(t, s)] for t in T for s in K}
            master.addColumn(col_idx - 1, col, g_idx)
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
    return master, x_by_group


def evaluate_pool(master, x_by_group, worker_groups, demand_dict, beta_g, T, K):
    """Pool-averaged ex-post evaluation of an already-solved master under a
    given beta_g (paper: NPP/ECP metrics are averaged across the optimal pool
    to remove the arbitrary schedule<->worker pairing)."""

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
        return _reconstruct(lambda g, r_: lam.get((g, r_), 0))
    return tuple(a / cnt_sols for a in agg)


def run_cg(data, demand_dict, worker_groups, beta_g, mode, max_itr=MAX_ITR, threshold=THRESHOLD, time_cg=TIME_CG_SP,
           solver='dp'):
    """Convenience wrapper: solve once and evaluate at the same beta_g. Correct
    for BAP (pricing depends on beta_g); for NPP/ECP prefer optimize_schedule()
    once + evaluate_pool() per beta_g (see optimize_schedule docstring)."""
    T = data['T'].dropna().astype(int).unique().tolist()
    K = data['K'].dropna().astype(int).unique().tolist()
    master, x_by_group = optimize_schedule(data, demand_dict, worker_groups, mode, beta_g=beta_g,
                                            max_itr=max_itr, threshold=threshold, time_cg=time_cg,
                                            solver=solver)
    return evaluate_pool(master, x_by_group, worker_groups, demand_dict, beta_g, T, K)


if __name__ == "__main__":
    len_I, num_days, prob = 6, 14, 1.0
    T = list(range(1, num_days + 1)); I = list(range(1, len_I + 1)); K = [1, 2, 3]
    maxlen = max(len(I), len(T), len(K))
    data = pd.DataFrame({'I': I + [np.nan] * (maxlen - len(I)),
                          'T': T + [np.nan] * (maxlen - len(T)),
                          'K': K + [np.nan] * (maxlen - len(K))})
    demand_dict = generate_demand(num_days, prob, len_I, shift_probs=(50, 30, 20), delta=0.25, seed=3)
    worker_groups = create_groups_from_fractions(I, "1/2,1/2", [(0.5, 0.5, 2, 7), (1.5, 1.5, 4, 21)])

    print(f"Extension 2 (Off-Day Recovery, LABELING): {len_I} workers, {num_days} days")
    for mode in ("bap", "npp", "ecp"):
        print(f"\n--- {mode.upper()} ---")
        if mode == "bap":
            # BAP's pricing genuinely depends on beta_g -> re-solve per beta.
            for beta in BETAS:
                uc, us, pl, cons = run_cg(data, demand_dict, worker_groups, beta, mode)
                print(f"  beta_g={beta}  undercover={uc:7.2f}  understaff={us:7.2f}  "
                      f"perfloss={pl:7.2f}  changes={cons:4.0f}")
        else:
            # NPP/ECP pricing is beta_g-invariant (e_max=0) -> solve ONCE,
            # evaluate ex-post per beta (extensions.tex:80).
            master, x_by_group = optimize_schedule(data, demand_dict, worker_groups, mode, beta_g=1)
            for beta in BETAS:
                uc, us, pl, cons = evaluate_pool(master, x_by_group, worker_groups, demand_dict, beta, T, K)
                print(f"  beta_g={beta}  undercover={uc:7.2f}  understaff={us:7.2f}  "
                      f"perfloss={pl:7.2f}  changes={cons:4.0f}")
