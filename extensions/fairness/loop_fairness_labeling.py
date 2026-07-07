"""Extension 1 (Fairness in Shift-Type Allocation) solved with the exact SPPRC
labeling algorithm (core.subproblem_dp_extensions.SubproblemFairnessDP),
matching extensions.tex: burden resource f tracked per label, terminal
penalty lambda*|f-Fbar| applied at final selection.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import gurobipy as gu
import numpy as np
import pandas as pd
from core.base_case import get_wd_constraints
from core.masterproblem import MasterProblem
from core.worker_groups import create_groups_from_fractions
from core.subproblem_dp_extensions import SubproblemFairnessDP
from core.subproblem_dp_extensions_numba import SubproblemFairnessNumba
from Utils.demand import generate_demand
from extensions.fairness.loop_fairness import MU, LAMBDAS, gini, _shift_of
from core.nonlinear_transitions import evaluate_schedule_nl

from core.base_case import K_ECP
from core.solver_base import MAX_ITR, THRESHOLD, TIME_CG_INIT, TIME_CG_SP


def run_cg(data, demand_dict, worker_groups, chi, prob, lam, F_bar, mode,
           max_itr=MAX_ITR, threshold=THRESHOLD, time_cg=TIME_CG_SP, solver='dp'):
    """solver: 'dp' (exact Python label-setting, default) or 'numba' (JIT-compiled,
    same recursion -- see core.subproblem_dp_extensions_numba.SubproblemFairnessNumba;
    Numba's final-day dominance is not collapsed by f_bin alone like DP's, so it can
    find a strictly better -- never worse -- effective cost, see that module's docstring)."""
    SubproblemCls = SubproblemFairnessNumba if solver == 'numba' else SubproblemFairnessDP
    T = data['T'].dropna().astype(int).unique().tolist()
    K = data['K'].dropna().astype(int).unique().tolist()
    I = data['I'].dropna().astype(int).unique().tolist()
    Min_WD_i, Max_WD_i = get_wd_constraints(I)
    n_cells = len(T) * len(K)

    start_perf = {(t, s): 0.0 for t in T for s in K}
    master = MasterProblem(data, demand_dict, max_itr, 0, 0, 100, start_perf, worker_groups=worker_groups)
    master.buildModel()
    master.setStartSolution()

    group_names = list(worker_groups.keys())
    perf_by_group, x_by_group = {g: {} for g in group_names}, {g: {} for g in group_names}

    itr, col_idx, improvable = 0, 0, True
    while improvable and itr < max_itr:
        master.model.Params.OutputFlag = 0
        master.model.optimize()
        duals_i, duals_ts = master.getDuals_i(), master.getDuals_ts()
        improvable = False
        for g_idx, (gname, group) in enumerate(worker_groups.items(), start=1):
            eps_sp = group.epsilon if mode == 'bap' else 0.0
            sp = SubproblemCls(duals_i.get(g_idx, 0.0), duals_ts, data, group.worker_ids[0], itr,
                               eps_sp, Min_WD_i, Max_WD_i, group.chi, MU, lam, F_bar)
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
            roster_idx = col_idx
            perf_vals = {(t, s): v for (t, s, _), v in sp.getNewSchedule().items()}
            x_vals = sp.getOptX()
            f_v = sp.getBurden()
            col_cost = lam * abs(f_v - F_bar)
            master.addLambda(col_idx - 1, g_idx, extra_cost=col_cost)
            col = {(t, s, roster_idx): perf_vals[(t, s)] for t in T for s in K}
            master.addColumn(col_idx - 1, col, g_idx)
            perf_by_group[gname][roster_idx] = {(t, s, roster_idx): perf_vals[(t, s)] for t in T for s in K}
            x_by_group[gname][roster_idx] = x_vals
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
        ls_x, ls_perf = [], []
        burden = {}
        for g_idx, (gname, group) in enumerate(worker_groups.items(), start=1):
            for r in master.active_roster_by_group.get(g_idx, []):
                cnt = get_count(g_idx, r)
                if cnt <= 0:
                    continue
                x_sched = x_by_group[gname].get(r, {})
                # Ex-post re-evaluation under the group's TRUE gamma_C/gamma_R/chi
                # (not the SP's own eps=0 override for NPP/ECP), so BAP/NPP/ECP are
                # compared on real behavioral cost rather than the SP's fictitious
                # p=1 bookkeeping (mirrors Ext. 2's evaluate_schedule_beta pattern).
                nl_spec = {'epsilon': getattr(group, 'epsilon', 0.06), 'chi': group.chi,
                           'gamma_R': group.gamma_R, 'gamma_C': group.gamma_C,
                           'alpha_R': group.alpha_R, 'delta': group.delta, 'e_max': group.e_max}
                perf_hist, *_ = evaluate_schedule_nl(x_sched, T, K, nl_spec)
                perf_vals = [perf_hist[t] if x_sched.get((t, s), 0) > 0.5 else 0.0 for t in T for s in K]
                x_vals = [1.0 if x_sched.get((t, s), 0) > 0.5 else 0.0 for t in T for s in K]
                fi = sum(MU[s] * x_sched.get((t, s), 0) for t in T for s in K)
                for c in range(cnt):
                    ls_perf.extend(perf_vals)
                    ls_x.extend(x_vals)
                    burden[f"{gname}_{r}_{c}"] = fi

        understaffing, undercoverage = 0.0, 0.0
        for ti, t in enumerate(T):
            for si, s in enumerate(K):
                nominal = sum(1.0 if ls_x[w * n_cells + ti * len(K) + si] > 0.5 else 0.0 for w in range(len(I)))
                effective = sum(ls_perf[w * n_cells + ti * len(K) + si] for w in range(len(I)))
                q = demand_dict[(t, s)]
                understaffing += max(0.0, q - nominal)
                undercoverage += max(0.0, q - effective)
        perfloss = undercoverage - understaffing
        consistency = sum(1 for w in range(len(I)) for d in range(1, len(T))
                           if _shift_of(ls_x, w, d, len(T), len(K)) != 0
                           and _shift_of(ls_x, w, d - 1, len(T), len(K)) != 0
                           and _shift_of(ls_x, w, d, len(T), len(K)) != _shift_of(ls_x, w, d - 1, len(T), len(K)))
        return undercoverage, understaffing, perfloss, consistency, burden

    best_obj = master.model.ObjVal
    n_pool = master.model.SolCount
    agg = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    cnt_sols = 0
    for si in range(n_pool):
        master.model.Params.SolutionNumber = si
        if abs(master.model.PoolObjVal - best_obj) > 1e-6:
            continue
        lam2 = {(g, r): round(master.lmbda[(g, r)].Xn) for (g, r) in master.lmbda}
        uc, us, pl, cons, burden = _reconstruct(lambda g, r: lam2.get((g, r), 0))
        bvals = list(burden.values())
        mean_b = sum(bvals) / len(bvals) if bvals else 0.0
        agg[0] += uc; agg[1] += us; agg[2] += pl; agg[3] += cons
        agg[4] += mean_b; agg[5] += gini(bvals)
        cnt_sols += 1
    master.model.Params.SolutionNumber = 0

    if cnt_sols == 0:
        lam2 = {(g, r): round(master.lmbda[(g, r)].X) for (g, r) in master.lmbda}
        uc, us, pl, cons, burden = _reconstruct(lambda g, r: lam2.get((g, r), 0))
        bvals = list(burden.values())
        mean_b = sum(bvals) / len(bvals) if bvals else 0.0
        return uc, us, pl, cons, mean_b, gini(bvals)

    undercoverage, understaffing, perfloss, consistency, mean_burden, gini_burden = [a / cnt_sols for a in agg]
    return undercoverage, understaffing, perfloss, consistency, mean_burden, gini_burden


if __name__ == "__main__":
    len_I, num_days, chi, prob = 6, 14, 3, 1.0
    T = list(range(1, num_days + 1)); I = list(range(1, len_I + 1)); K = [1, 2, 3]
    maxlen = max(len(I), len(T), len(K))
    data = pd.DataFrame({'I': I + [np.nan] * (maxlen - len(I)),
                          'T': T + [np.nan] * (maxlen - len(T)),
                          'K': K + [np.nan] * (maxlen - len(K))})
    demand_dict = generate_demand(num_days, prob, len_I, shift_probs=(50, 30, 20), delta=0.25, seed=3)
    worker_groups = create_groups_from_fractions(I, "1/2,1/2", [(0.5, 0.5, 2, 7), (1.5, 1.5, 4, 21)])

    print(f"Extension 1 (Fairness, LABELING): {len_I} workers, {num_days} days, mu={MU}")
    for mode in ("bap", "npp", "ecp"):
        _, _, _, _, F_bar, _ = run_cg(data, demand_dict, worker_groups, chi, prob, 0.0, 0.0, mode)
        print(f"\n--- {mode.upper()} ---  F_bar (preprocessing) = {F_bar:.2f}")
        for lam in LAMBDAS:
            uc, us, pl, cons, _, g = run_cg(data, demand_dict, worker_groups, chi, prob, lam, F_bar, mode)
            print(f"  lambda={lam:<5} undercover={uc:7.2f}  understaff={us:7.2f}  "
                  f"perfloss={pl:7.2f}  changes={cons:4.0f}  gini(F)={g:.3f}")
