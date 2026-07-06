"""Extension 4 (A+B): shadow price of the qualification-scarcity constraint.

Case A: the marginal value of training one more ICU-qualified worker is the
dual of that (resilience-group, qualification)-pair's OWN convexity
constraint in the master (sum Lambda_v = group size); increasing the RHS by 1
(one more worker in that group) relaxes the master by exactly this dual.

Case B: the qualification-specific demand rows Q_ds^q are explicit master
constraints (vshift-encoded); their summed dual for q=ICU (vshift%10==2) is
the aggregate shadow value of ICU-demand scarcity across the horizon.

Paper prediction (extensions.tex, Case A/B "Expected results"): this shadow
price should be substantially HIGHER under the NPP than under the BAP, since
NPP does not exploit behavioral routing flexibility and therefore relies more
on raw staffing levels.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import numpy as np
import pandas as pd
import gurobipy as gu
from core.base_case import get_wd_constraints, K_ECP
from core.masterproblem import MasterProblem
from core.worker_groups import WorkerGroup
from core.subproblem_dp_extensions import SubproblemQualificationsDP, SubproblemQualificationsOverlapDP
from core.solver_base import MAX_ITR, THRESHOLD, TIME_CG_INIT, TIME_CG_SP
from extensions.qualifications.loop_qualifications import make_qual_groups
from extensions.qualifications.loop_qualifications_case_b import (
    make_workers_case_b, build_demand_case_b, build_data_master, all_vshifts, SHIFT_TO_QUALIFICATIONS
)

MAX_ITR_TEST = 60


def shadow_price_case_a(data, demand_dict, qual_groups, mode):
    """Solve the LP relaxation and return the dual of the ICU-qualified
    groups' convexity constraints (icu_res, icu_sens), i.e. the marginal
    value of one additional ICU-eligible worker."""
    T = data['T'].dropna().astype(int).unique().tolist()
    K = data['K'].dropna().astype(int).unique().tolist()
    I = data['I'].dropna().astype(int).unique().tolist()
    Min_WD_i, Max_WD_i = get_wd_constraints(I)

    start_perf = {(t, s): 0.0 for t in T for s in K}
    master = MasterProblem(data, demand_dict, MAX_ITR_TEST, 0, 0, 100, start_perf, worker_groups=qual_groups)
    master.buildModel()
    master.setStartSolution()

    itr, col_idx, improvable = 0, 0, True
    while improvable and itr < MAX_ITR_TEST:
        master.model.Params.OutputFlag = 0
        master.model.optimize()
        duals_i, duals_ts = master.getDuals_i(), master.getDuals_ts()
        improvable = False
        for g_idx, (gname, group) in enumerate(qual_groups.items(), start=1):
            eps_sp = 0.06 if mode == 'bap' else 0.0
            sp = SubproblemQualificationsDP(duals_i.get(g_idx, 0.0), duals_ts, data, group.worker_ids[0],
                                            itr, eps_sp, Min_WD_i, Max_WD_i, group.chi, group.eligible_shifts)
            if mode == 'bap':
                sp.gamma_C, sp.gamma_R, sp.alpha_R, sp.delta, sp.e_max = (
                    group.gamma_C, group.gamma_R, group.alpha_R, group.delta, group.e_max)
            else:
                sp.gamma_C, sp.gamma_R, sp.alpha_R, sp.e_max = 1.0, 1.0, 1.0, 0.0
                sp.delta = np.zeros((4, 4))
            if mode == 'ecp':
                sp.addECPConstraint(K_ECP)
            sp.buildModel()
            sp.solveModelOpt(TIME_CG_INIT if itr == 0 else TIME_CG_SP)
            if sp.getStatus() != gu.GRB.OPTIMAL:
                continue
            rc = sp.model.objval
            if rc >= -THRESHOLD:
                continue
            col_idx += 1
            master.addLambda(col_idx - 1, g_idx)
            perf_vals = {(t, s): v for (t, s, _), v in sp.getNewSchedule().items()}
            col = {(t, s, col_idx): perf_vals[(t, s)] for t in T for s in K}
            master.addColumn(col_idx - 1, col, g_idx)
            improvable = True
        itr += 1

    # Final LP solve (relaxed) to read stable convexity duals.
    master.model.Params.OutputFlag = 0
    master.model.optimize()
    duals_i = master.getDuals_i()
    icu_group_idxs = [g_idx for g_idx, (gname, _) in enumerate(qual_groups.items(), start=1)
                      if gname.startswith("icu")]
    return sum(duals_i.get(g, 0.0) for g in icu_group_idxs)


def shadow_price_case_b(data_sp, data_master, demand_vshift, workers_b, mode):
    """Sum of duals for the ICU-demand rows (vshift % 10 == 2) at LP optimum."""
    T = data_sp['T'].dropna().astype(int).unique().tolist()
    K = data_sp['K'].dropna().astype(int).unique().tolist()
    I = data_sp['I'].dropna().astype(int).unique().tolist()
    VS = all_vshifts()
    Min_WD_i, Max_WD_i = get_wd_constraints(I)

    start_perf = {(t, vs): 0.0 for t in T for vs in VS}
    pseudo_groups = {}
    for wid in I:
        w = workers_b[wid]
        gname = f"worker_{wid}"
        pseudo_groups[gname] = WorkerGroup(name=gname, epsilon=w.epsilon, chi=w.chi, worker_ids=[wid],
                                           gamma_C=w.gamma_C, gamma_R=w.gamma_R, T_R=w.T_R, delta=w.delta)
        pseudo_groups[gname].e_max = w.e_max
        pseudo_groups[gname].alpha_R = w.alpha_R

    master = MasterProblem(data_master, demand_vshift, MAX_ITR_TEST, 0, 0, 100, start_perf,
                           worker_groups=pseudo_groups)
    master.buildModel()
    master.setStartSolution()

    itr, col_idx, improvable = 0, 0, True
    while improvable and itr < MAX_ITR_TEST:
        master.model.Params.OutputFlag = 0
        master.model.optimize()
        duals_i, duals_ts_vs = master.getDuals_i(), master.getDuals_ts()
        duals_ts_q = {}
        for (t, vs), pi in duals_ts_vs.items():
            s, q = vs // 10, vs % 10
            duals_ts_q[(t, s, q)] = pi

        improvable = False
        for g_idx, (gname, group) in enumerate(pseudo_groups.items(), start=1):
            wid = group.worker_ids[0]
            w = workers_b[wid]
            eps_sp = w.epsilon if mode == 'bap' else 0.0
            sp = SubproblemQualificationsOverlapDP(duals_i.get(g_idx, 0.0), duals_ts_q,
                                                    SHIFT_TO_QUALIFICATIONS, data_sp, wid, itr,
                                                    eps_sp, Min_WD_i, Max_WD_i, w.chi, w.eligible_qualifications)
            if mode == 'bap':
                sp.gamma_C, sp.gamma_R, sp.alpha_R, sp.delta, sp.e_max = w.gamma_C, w.gamma_R, w.alpha_R, w.delta, w.e_max
            else:
                sp.gamma_C, sp.gamma_R, sp.alpha_R, sp.e_max = 1.0, 1.0, 1.0, 0.0
                sp.delta = np.zeros((4, 4))
            if mode == 'ecp':
                sp.addECPConstraint(K_ECP)
            sp.buildModel()
            sp.solveModelOpt(TIME_CG_INIT if itr == 0 else TIME_CG_SP)
            if sp.getStatus() != gu.GRB.OPTIMAL:
                continue
            rc = sp.model.objval
            if rc >= -THRESHOLD:
                continue
            col_idx += 1
            master.addLambda(col_idx - 1, g_idx)
            sched = sp.getNewSchedule()
            perf_vals = {(t_, vs): v for (t_, vs, _), v in sched.items()}
            col = {(t_, vs, col_idx): perf_vals[(t_, vs)] for t_ in T for vs in VS}
            master.addColumn(col_idx - 1, col, g_idx)
            improvable = True
        itr += 1

    master.model.Params.OutputFlag = 0
    master.model.optimize()
    duals_ts_vs = master.getDuals_ts()
    return sum(pi for (t, vs), pi in duals_ts_vs.items() if vs % 10 == 2)


if __name__ == "__main__":
    # Larger instance + averaged over several seeds, to check whether the
    # earlier I=10/single-seed result (direction reversed at pi=0.5, LP
    # degeneracy tie at pi=0.2 in Case B) was noise rather than a genuine
    # qualitative disagreement with the paper's prediction.
    len_I, num_days = 16, 14
    SEEDS = [1, 2, 3]
    T = list(range(1, num_days + 1)); I = list(range(1, len_I + 1)); K = [1, 2, 3]
    data = pd.DataFrame({'I': I + [np.nan]*(max(len(I),len(T),len(K))-len(I)),
                        'T': T + [np.nan]*(max(len(I),len(T),len(K))-len(T)),
                        'K': K + [np.nan]*(max(len(I),len(T),len(K))-len(K))})

    print("="*78)
    print(f"Shadow price of qualification scarcity (Case A + Case B)")
    print(f"I={len_I}, days={num_days}, averaged over seeds={SEEDS}")
    print("="*78)

    from Utils.demand import generate_demand

    print("\n--- Case A: dual of ICU-group convexity constraints (mean over seeds) ---")
    print(f"  {'mode':>5} {'pi=0.20':>10} {'pi=0.50':>10}")
    for mode in ("bap", "npp", "ecp"):
        means = []
        for pi in (0.20, 0.50):
            vals = []
            for seed in SEEDS:
                demand_dict = generate_demand(num_days, 0.7, len_I, shift_probs=(25, 50, 25),
                                              delta=0.25, seed=seed, prop_volatility=0.30)
                qual_groups = make_qual_groups(I, pi)
                vals.append(shadow_price_case_a(data, demand_dict, qual_groups, mode))
            means.append(sum(vals) / len(vals))
            print(f"    [{mode} pi={pi}] per-seed = {[f'{v:.2f}' for v in vals]}", flush=True)
        print(f"  {mode:>5} {means[0]:10.3f} {means[1]:10.3f}", flush=True)

    print("\n--- Case B: sum of ICU-demand-row duals (mean over seeds) ---")
    print(f"  {'mode':>5} {'pi=0.20':>10} {'pi=0.50':>10}")
    for mode in ("bap", "npp", "ecp"):
        means = []
        for pi in (0.20, 0.50):
            vals = []
            for seed in SEEDS:
                data_master = build_data_master(I, T)
                demand_vshift = build_demand_case_b(num_days, 0.7, len_I, seed=seed)
                workers_b = make_workers_case_b(I, pi)
                vals.append(shadow_price_case_b(data, data_master, demand_vshift, workers_b, mode))
            means.append(sum(vals) / len(vals))
            print(f"    [{mode} pi={pi}] per-seed = {[f'{v:.2f}' for v in vals]}", flush=True)
        print(f"  {mode:>5} {means[0]:10.3f} {means[1]:10.3f}", flush=True)

    print("\n" + "="*78)
