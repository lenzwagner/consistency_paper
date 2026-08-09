import sys
import time

from .masterproblem import *
from .subproblem import *
from .subproblem_factory import create_subproblem
from Utils.gcutil import *
from Utils.compactsolver import *
from Utils.metrics import evaluate_inequality
from .worker_groups import create_homogeneous_group, get_worker_params


def generate_feasible_schedule_heuristic(T, K, eps=0.06):
    """
    Generate a simple feasible schedule heuristic.
    Pattern: 4 work days, 2 rest days, cycling through shifts.
    All workers use the same schedule (homogeneous starting point).
    
    Returns: dict with 'perf', 'x', 'p', 'c', 'r', 'eup', 'elow'
    """
    n_days = len(T)
    n_shifts = len(K)
    
    # Initialize all to 0
    x = {(t, s): 0.0 for t in T for s in K}
    perf = {(t, s): 0.0 for t in T for s in K}
    p = {t: 1.0 for t in T}          # Start with full performance
    c = {t: 0.0 for t in T}          # Consistency (shift changes)
    r = {t: 0.0 for t in T}          # Recovery days
    eup = {t: 0.0 for t in T}
    elow = {t: 0.0 for t in T}
    
    # Pattern: 4 work days, 2 rest days
    work_pattern = [1, 1, 1, 1, 0, 0]  # 4 on, 2 off
    current_shift = 1
    last_shift = None
    consecutive_changes = 0
    
    for day_idx, t in enumerate(T):
        pattern_idx = day_idx % len(work_pattern)
        is_work_day = work_pattern[pattern_idx]
        
        if is_work_day:
            # Assign to current shift
            x[t, current_shift] = 1.0
            
            # Track shift changes for consistency
            if last_shift is not None and last_shift != current_shift:
                c[t] = 1.0
                consecutive_changes += 1
            else:
                consecutive_changes = 0
            
            # Calculate performance based on consecutive changes
            # perf = 1 - eps * consecutive_changes
            perf[t, current_shift] = max(0.0, 1.0 - eps * consecutive_changes)
            p[t] = perf[t, current_shift]
            
            last_shift = current_shift
        else:
            # Rest day
            r[t] = 1.0
            last_shift = None
            consecutive_changes = 0
            p[t] = 1.0  # Recovery resets performance
    
    return {
        'perf': perf,
        'x': x,
        'p': p,
        'c': c,
        'r': r,
        'eup': eup,
        'elow': elow
    }

def column_generation_behavior(data, demand_dict, eps, Min_WD_i, Max_WD_i, time_cg_init, max_itr, output_len, chi, threshold, time_cg, I, T, K, scale, sp_solver='labeling_bidir', start_values=None, save_lp=False, worker_groups=None, use_heuristic_start=True, use_null_column=False, enforce_no_change=False, enforce_performance_floor=None, model_type='nonlinear'):
    # **** Column Generation ****
    # Prerequisites
    modelImprovable = True
    
    # Backward compatibility: create homogeneous group if none provided
    if worker_groups is None:
        worker_groups = create_homogeneous_group(I, eps, chi)

    # Get Starting Solutions (or use provided ones)
    if start_values is None:
        if use_null_column:
            print("Using NULL COLUMN for initial solution...")
            start_values_by_group = {}
            for group_name, group in worker_groups.items():
                start_values_by_group[group_name] = {
                    'perf': {(t, s): 0.0 for t in T for s in K},
                    'p': {t: 1.0 for t in T},
                    'x': {(t, s): 0.0 for t in T for s in K},
                    'c': {t: 0.0 for t in T},
                    'r': {t: 0.0 for t in T},
                    'eup': {t: 0.0 for t in T},
                    'elow': {t: 0.0 for t in T},
                    'worker_ids': group.worker_ids
                }
        elif use_heuristic_start:
            # Fast heuristic: generate simple feasible schedule for all workers
            print("Using HEURISTIC for initial solution...")
            heuristic_sol = generate_feasible_schedule_heuristic(T, K, eps)
            
            # Same start values for all groups
            start_values_by_group = {}
            for group_name, group in worker_groups.items():
                start_values_by_group[group_name] = {
                    'perf': heuristic_sol['perf'],
                    'p': heuristic_sol['p'],
                    'x': heuristic_sol['x'],
                    'c': heuristic_sol['c'],
                    'r': heuristic_sol['r'],
                    'eup': heuristic_sol['eup'],
                    'elow': heuristic_sol['elow'],
                    'worker_ids': group.worker_ids
                }
            
            # Print schedule summary
            work_days = sum(1 for k, v in heuristic_sol['x'].items() if v > 0.5)
            print(f"  Heuristic: {work_days} work days, pattern: 4 on / 2 off")
        else:
            # Use compact solver
            problem_start = Problem(data, demand_dict, eps, Min_WD_i, Max_WD_i, chi, worker_groups=worker_groups, model_type=model_type)
            problem_start.buildLinModel()
            problem_start.model.Params.MIPFocus = 1
            problem_start.model.Params.Heuristics = 1
            problem_start.model.Params.RINS = 10
            problem_start.model.Params.TimeLimit = time_cg_init
            problem_start.model.update()
            problem_start.model.optimize()
            
            # Debug: check solution status
            print(f"Compact Solver Status: {problem_start.model.Status} (2=Optimal)")
            print(f"Compact Solver ObjVal: {problem_start.model.ObjVal:.2f}")

            # Extract starting values per group from representative workers
            # This gives each group a starting column suited to its (epsilon, chi)
            start_values_by_group = {}
            for group_name, group in worker_groups.items():
                rep_worker = group.worker_ids[0]  # Representative worker for this group
                start_values_by_group[group_name] = {
                    'perf': {(t, s): problem_start.perf[rep_worker, t, s].X for t in T for s in K},
                    'p': {t: problem_start.p[rep_worker, t].X for t in T},
                    'x': {(t, s): problem_start.x[rep_worker, t, s].X for t in T for s in K},
                    'c': {t: problem_start.sc[rep_worker, t].X for t in T},
                    'r': {t: problem_start.r[rep_worker, t].X for t in T},
                    'eup': {t: problem_start.e[rep_worker, t].X for t in T},
                    'elow': {t: problem_start.b[rep_worker, t].X for t in T},
                    'worker_ids': group.worker_ids
                }
        
        # Print initial solutions per group
        print("\n" + "="*80)
        print("INITIAL SOLUTIONS PER GROUP")
        print("="*80)
        for group_name, sv in start_values_by_group.items():
            print(f"\n{group_name}:")
            print(f"  perf: {sv['perf']}")
            print(f"  x: {sv['x']}")
        print("="*80 + "\n")
        
        # For backward compatibility, use first group's values as default
        first_group = list(start_values_by_group.values())[0]
        start_values_perf = first_group['perf']
        start_values_p = first_group['p']
        start_values_x = first_group['x']
        start_values_c = first_group['c']
        start_values_r = first_group['r']
        start_values_eup = first_group['eup']
        start_values_elow = first_group['elow']
    else:
        # Use provided start values
        start_values_perf = start_values['perf']
        start_values_p = start_values['p']
        start_values_x = start_values['x']
        start_values_c = start_values['c']
        start_values_r = start_values['r']
        start_values_eup = start_values['eup']
        start_values_elow = start_values['elow']
        start_values_by_group = None

    # Initialize iterations
    itr = 0
    last_itr = 0

    # Create empty results lists
    histories = ["objValHistSP", "timeHist", "objValHistRMP", "avg_rc_hist", "lagrange_hist", "sum_rc_hist", "avg_sp_time", "rmp_time_hist"]
    histories_dict = {}
    for history in histories:
        histories_dict[history] = []
    objValHistSP, timeHist, objValHistRMP, avg_rc_hist, lagrange_hist, sum_rc_hist, avg_sp_time, rmp_time_hist = histories_dict.values()

    X_schedules = {}
    for index in I:
        X_schedules[f"Physician_{index}"] = []

    Perf_schedules = create_schedule_dict(start_values_perf, 1, T, K)
    Cons_schedules = create_schedule_dict(start_values_c, 1, T)
    Recovery_schedules = create_schedule_dict(start_values_r, 1, T)
    EUp_schedules = create_schedule_dict(start_values_eup, 1, T)
    ELow_schedules = create_schedule_dict(start_values_elow, 1, T)
    P_schedules = create_schedule_dict(start_values_p, 1, T)
    X1_schedules = create_schedule_dict(start_values_x, 1, T, K)

    # Per-group schedule storage (roster_idx -> schedule dict) for correct,
    # group-aware reconstruction of the final per-worker lists. The legacy
    # Physician_1 lists collapse all groups and are only correct for |G|=1.
    _group_names = list(worker_groups.keys())
    perf_by_group = {g: {} for g in _group_names}
    cons_by_group = {g: {} for g in _group_names}
    x_by_group = {g: {} for g in _group_names}
    p_by_group = {g: {} for g in _group_names}
    rec_by_group = {g: {} for g in _group_names}

    # Per-group SP timing/reduced-cost histories (one list per group, appended
    # every CG iteration). A "mean" series is added on top ONLY when there is
    # more than one group -- with a single group it would just duplicate that
    # group's own list. Replaces the old pooled sp_time_hist (summed wall-clock
    # across all groups' solves that iteration) / sp_min_rc_hist (min reduced
    # cost across groups), which discarded the per-group breakdown entirely.
    sp_time_hist_by_group = {g: [] for g in _group_names}
    sp_obj_hist_by_group = {g: [] for g in _group_names}
    if len(_group_names) > 1:
        sp_time_hist_by_group['mean'] = []
        sp_obj_hist_by_group['mean'] = []

    # Seed roster index 1 (the INITIAL heuristic column set via setStartSolution)
    # into the per-group stores. Roster 1 is never added through the CG loop, so
    # without this the final reconstruction (_expand) treats every worker that the
    # final IP assigns to roster 1 as an EMPTY schedule -- which both blanks their
    # displayed roster and inflates the post-hoc undercoverage_ab metric. The
    # per-(t,s)/(t,) key order here matches the CG columns and the demand order.
    if start_values_by_group is not None:
        for _gname, _sv in start_values_by_group.items():
            perf_by_group[_gname][1] = dict(_sv['perf'])
            cons_by_group[_gname][1] = dict(_sv['c'])
            p_by_group[_gname][1]    = dict(_sv['p'])
            rec_by_group[_gname][1]  = dict(_sv['r'])
            x_by_group[_gname][1]    = dict(_sv['x'])
    else:
        # No per-group start (flat start_values path): reuse the same initial
        # column for every group so roster 1 still reconstructs non-empty.
        for _gname in _group_names:
            perf_by_group[_gname][1] = dict(start_values_perf)
            cons_by_group[_gname][1] = dict(start_values_c)
            p_by_group[_gname][1]    = dict(start_values_p)
            rec_by_group[_gname][1]  = dict(start_values_r)
            x_by_group[_gname][1]    = dict(start_values_x)

    master = MasterProblem(data, demand_dict, max_itr, itr, last_itr, output_len, start_values_perf, 
                           start_by_group=start_values_by_group, worker_groups=worker_groups)
    master.buildModel()

    # Initialize and solve relaxed model
    master.setStartSolution()
    master.updateModel()
    
    master.solveRelaxModel()

    # Retrieve dual values
    duals_i0 = master.getDuals_i()
    duals_ts0 = master.getDuals_ts()

    # Start time count
    t0 = time.time()
    previous_reduced_cost = float('inf')

    while modelImprovable and itr < max_itr:
        print("*{:^{output_len}}*".format(f"Begin Column Generation Iteration {itr}", output_len=output_len))

        # Start
        itr += 1

        # Solve RMP
        rmp_start_time = time.time()
        master.current_iteration = itr + 1
        master.solveRelaxModel()
        rmp_end_time = time.time()
        rmp_time_hist.append(rmp_end_time - rmp_start_time)

        objValHistRMP.append(master.model.objval)
        current_obj = master.model.objval

        # Get and Print Duals
        duals_i = master.getDuals_i()  # Now returns dict: {worker_id: dual}
        duals_ts = master.getDuals_ts()

        # Solve SPs - one per worker group
        modelImprovable = False
        all_reduced_costs = []
        sub_start_time = time.time()
        
        for group_name, group in worker_groups.items():
            # Get group index for this group (1-based)
            group_idx = list(worker_groups.keys()).index(group_name) + 1
            representative_worker = group.worker_ids[0]
            
            # Get dual for this group's convexity constraint
            group_dual_i = duals_i.get(group_idx, 0.0)
            
            # Build SP with group-specific (epsilon, chi)
            group_sp_start = time.time()
            subproblem = create_subproblem(
                sp_solver, group_dual_i, duals_ts, data, representative_worker, itr,
                group.epsilon, Min_WD_i, Max_WD_i, group.chi,
                enforce_no_change=enforce_no_change,
                enforce_performance_floor=enforce_performance_floor,
                gamma_C=group.gamma_C,
                gamma_R=group.gamma_R,
                alpha_R=group.alpha_R,
                e_max=group.e_max,
                delta=group.delta,
                model_type=model_type
            )
            subproblem.buildModel()

            # Solve SP
            if previous_reduced_cost < -0.001:
                subproblem.solveModelNOpt(time_cg)
            else:
                subproblem.solveModelOpt(time_cg)
            sp_time_hist_by_group[group_name].append(time.time() - group_sp_start)

            # Check if SP is solvable
            status = subproblem.getStatus()
            if status != 2:
                print(f"Warning: Pricing-Problem for group {group_name} not optimal")
                sp_obj_hist_by_group[group_name].append(float('nan'))
                continue

            # Get reduced cost
            reducedCost = subproblem.model.objval
            all_reduced_costs.append(reducedCost)
            sp_obj_hist_by_group[group_name].append(reducedCost)
            print(f'Red. Cost for {group_name}: {reducedCost}')

            # Generate and add columns for this group
            if reducedCost < -threshold:
                Schedules = subproblem.getNewSchedule()
                
                # Debug: print schedule in first 5 iterations
                if itr <= 5:
                    col_list = sorted([(k[0], k[1]) for k, v in Schedules.items() if v > 0.5])
                    print(f"  [ITR {itr}] [{group_name}] Schedule: {col_list}")
                
                # Add lambda and column for this group (using group_idx)
                group_idx = list(worker_groups.keys()).index(group_name) + 1
                master.addLambda(itr, group_idx)
                master.addColumn(itr, Schedules, group_idx)
                
                modelImprovable = True
                
                # Track schedules (use Physician_1 for backward compatibility)
                index = 1
                keys = ["X", "Perf", "P", "C", "R", "EUp", "Elow", "X1"]
                methods = ["getOptX", "getOptPerf", "getOptP", "getOptC", "getOptR", "getOptEUp", "getOptElow", "getOptX"]
                schedules = [X_schedules, Perf_schedules, P_schedules, Cons_schedules, Recovery_schedules, EUp_schedules, ELow_schedules, X1_schedules]

                for key, method, schedule in zip(keys, methods, schedules):
                    value = getattr(subproblem, method)()
                    schedule[f"Physician_{index}"].append(value)

                # Group-aware storage keyed by roster index (= itr + 1, see addLambda).
                _r = itr + 1
                perf_by_group[group_name][_r] = subproblem.getOptPerf()
                cons_by_group[group_name][_r] = subproblem.getOptC()
                x_by_group[group_name][_r] = subproblem.getOptX()
                p_by_group[group_name][_r] = subproblem.getOptP()
                rec_by_group[group_name][_r] = subproblem.getOptR()
        
        sub_end_time = time.time()
        timeHist.append(sub_end_time - sub_start_time)

        # Aggregate reduced costs for history (drives the opt/noopt heuristic
        # and the Lagrangian bound -- unrelated to the per-group breakdown
        # below, so this still pools across groups by design).
        if all_reduced_costs:
            min_rc = min(all_reduced_costs)
            objValHistSP.append(min_rc)
            previous_reduced_cost = min_rc
        else:
            objValHistSP.append(0.0)
            previous_reduced_cost = 0.0

        # Per-group SP time/reduced-cost history for this iteration, plus a
        # cross-group mean -- only added when there is more than one group
        # (with a single group the mean would just duplicate that group's
        # own series).
        if len(_group_names) > 1:
            _times_this_itr = [sp_time_hist_by_group[g][-1] for g in _group_names if sp_time_hist_by_group[g]]
            _objs_this_itr = [sp_obj_hist_by_group[g][-1] for g in _group_names
                              if sp_obj_hist_by_group[g] and sp_obj_hist_by_group[g][-1] == sp_obj_hist_by_group[g][-1]]  # drop NaN
            sp_time_hist_by_group['mean'].append(sum(_times_this_itr) / len(_times_this_itr) if _times_this_itr else float('nan'))
            sp_obj_hist_by_group['mean'].append(sum(_objs_this_itr) / len(_objs_this_itr) if _objs_this_itr else float('nan'))

        # Increase latest used iteration
        last_itr = itr + 1
        master.updateModel()

        # Update Model
        master.updateModel()

        # Calculate Metrics
        avg_rc = sum(objValHistSP) / len(objValHistSP)
        lagrange = avg_rc + current_obj
        sum_rc = sum(objValHistSP)
        avg_rc_hist.append(avg_rc)
        sum_rc_hist.append(sum_rc)
        lagrange_hist.append(lagrange)
        objValHistSP.clear()
        avg_time = sum(timeHist) / len(timeHist)
        avg_sp_time.append(avg_time)

        timeHist.clear()

        if not modelImprovable:
            print("*" * (output_len + 2))
            break

    if modelImprovable and itr == max_itr:
        max_itr *= 2

    # Solve Master Problem with integrality restored
    time_ip1 = time.time()
    master.finalSolve(300)
    time_ip2 = time.time() - time_ip1
    objValHistRMP.append(master.model.objval)
    final_obj = master.model.objval
    final_lb = objValHistRMP[-2]

    if abs(final_obj) > 1e-6:
        integrality_gap_pct = ((final_obj - final_lb) / final_obj) * 100
    else:
        integrality_gap_pct = 0.0

    status = master.model.Status
    if status in (gu.GRB.INF_OR_UNBD, gu.GRB.INFEASIBLE, gu.GRB.UNBOUNDED):
        gu.sys.exit(1)

    if status != gu.GRB.OPTIMAL:
        gu.sys.exit(1)

    time_in_sps = sum(avg_sp_time)
    time_in_rmp = time.time()-time_in_sps-time_ip2-t0
    time_in_ip = time_ip2

    objValHistRMP.append(master.model.objval)
    lagranigan_bound = round((objValHistRMP[-2] + sum_rc_hist[-1]), 5)

    # Group-aware reconstruction: expand each group's rosters with ITS OWN schedules,
    # ordered by the group's worker blocks. Roster 1 is the null column (empty schedule).
    def _expand(sched_by_group, flat_len):
        out = []
        for _gi, _gname in enumerate(_group_names, start=1):
            for _r in master.active_roster_by_group.get(_gi, []):
                _cnt = round(master.lmbda[(_gi, _r)].X) if (_gi, _r) in master.lmbda else 0
                if _cnt <= 0:
                    continue
                _sched = sched_by_group[_gname].get(_r)
                _vals = list(_sched.values()) if _sched is not None else [0.0] * flat_len
                for _ in range(_cnt):
                    out.extend(_vals)
        return out

    _n_ts = len(T) * len(K)
    _n_t = len(T)
    ls_p = [round(x, 5) for x in _expand(p_by_group, _n_t)]
    ls_sc = [1.0 if x > 0.5 else 0.0 for x in _expand(cons_by_group, _n_t)]
    ls_perf = [round(x, 5) for x in _expand(perf_by_group, _n_ts)]
    ls_x = [1.0 if x > 0 else 0.0 for x in ls_perf]
    ls_rec = [1.0 if x > 0.5 else 0.0 for x in _expand(rec_by_group, _n_t)]

    # Inequality
    L_perf = [x * (1 - p) for x, p in zip(ls_x, ls_perf)]
    _, spread_sc, load_share_sc, gini_sc, disutility_sc, top10_sc = evaluate_inequality(ls_sc, len(master.days), len(master.nurses))
    _, spread_perf, load_share_perf, gini_perf, disutility_perf, top10_perf = evaluate_inequality([sum(L_perf[i:i + 3]) for i in range(0, len(L_perf), 3)], len(master.days), len(master.nurses))

    # shift blocks
    shift_blocks = analyze_and_plot_blocks(ls_x, len(master.nurses), len(master.days), len(master.shifts))

    undercoverage_ab, understaffing_ab, perfloss_ab, consistency_ab, consistency_norm_ab, undercoverage_norm_ab, understaffing_norm_ab, perfloss_norm_ab = master.calc_behavior(ls_perf, ls_sc, scale)

    return round(undercoverage_ab, 5), round(understaffing_ab, 5), round(perfloss_ab, 5), round(consistency_ab, 5), round(consistency_norm_ab, 5), round(undercoverage_norm_ab, 5), round(understaffing_norm_ab, 5), round(perfloss_norm_ab, 5),  round(final_obj, 5), round(final_lb, 5), itr, lagranigan_bound, integrality_gap_pct, time_in_sps, time_in_rmp, time_in_ip, ls_p, ls_sc, ls_perf, ls_x, ls_rec, [0.0 if abs(round(x, 5)) == 0 else round(x, 5) for x in master.getUndercoverage()], spread_sc, load_share_sc, gini_sc, disutility_sc, top10_sc, spread_perf, load_share_perf, gini_perf, disutility_perf, top10_perf, shift_blocks, objValHistRMP, sp_obj_hist_by_group, rmp_time_hist, sp_time_hist_by_group, lagrange_hist