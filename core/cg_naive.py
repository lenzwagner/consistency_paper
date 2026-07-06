import numpy as np
from .masterproblem import *
from .subproblem import *
from .subproblem_factory import create_subproblem
from Utils.gcutil import *
from Utils.compactsolver import *
from Utils.metrics import evaluate_inequality

def column_generation_naive(data, demand_dict, eps, Min_WD_i, Max_WD_i, time_cg_init, max_itr, output_len, chi, threshold, time_cg, I, T, K, scale, sp_solver='labeling_bidir', use_null_column=False, worker_groups=None):
    # **** Column Generation ****
    # Prerequisites
    modelImprovable = True

    # Get Starting Solutions
    if use_null_column:
        print("Using NULL COLUMN for initial solution...")
        start_values_perf = {(t, s): 0.0 for t in T for s in K}
        start_values_p = {t: 1.0 for t in T}
        start_values_x = {(t, s): 0.0 for t in T for s in K}
        start_values_r = {t: 0.0 for t in T}
        start_values_c = {t: 0.0 for t in T}
    else:
        problem_start = Problem(data, demand_dict, eps, Min_WD_i, Max_WD_i, chi)
        problem_start.buildLinModel()
        problem_start.model.Params.MIPFocus = 1
        problem_start.model.Params.Heuristics = 1
        problem_start.model.Params.RINS = 10
        problem_start.model.Params.TimeLimit = time_cg_init
        problem_start.model.update()
        problem_start.model.optimize()

        # Schedules
        # Create
        start_values_perf = {(t, s): problem_start.perf[1, t, s].x for t in T for s in K}
        start_values_p = {(t): problem_start.p[1, t].x for t in T}
        start_values_x = {(t, s): problem_start.x[1, t, s].x for t in T for s in K}
        start_values_r = {(t): problem_start.r[1, t].x for t in T}
        start_values_c = {(t): problem_start.sc[1, t].x for t in T}

    # Initialize iterations
    itr = 0
    last_itr = 0

    # Create empty results lists
    histories = ["objValHistSP", "timeHist", "objValHistRMP", "avg_rc_hist", "lagrange_hist", "sum_rc_hist", "avg_sp_time", "rmp_time_hist", "sp_time_hist"]
    histories_dict = {}
    for history in histories:
        histories_dict[history] = []
    objValHistSP, timeHist, objValHistRMP, avg_rc_hist, lagrange_hist, sum_rc_hist, avg_sp_time, rmp_time_hist, sp_time_hist = histories_dict.values()

    X_schedules = {}
    for index in I:
        X_schedules[f"Physician_{index}"] = []

    Perf_schedules = create_schedule_dict(start_values_perf, 1, T, K)
    Cons_schedules = create_schedule_dict(start_values_c, 1, T)
    P_schedules = create_schedule_dict(start_values_p, 1, T)
    Recovery_schedules = create_schedule_dict(start_values_r, 1, T)
    X1_schedules = create_schedule_dict(start_values_x, 1, T, K)

    master = MasterProblem(data, demand_dict, max_itr, itr, last_itr, output_len, start_values_perf)
    master.buildModel()

    # Initialize and solve relaxed model
    master.setStartSolution()
    master.updateModel()
    master.solveRelaxModel()

    # Retrieve dual values
    duals_i0 = master.getDuals_i()
    duals_ts0 = master.getDuals_ts()
    ##print(f"{duals_i0, duals_ts0}")

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
        duals_i_dict = master.getDuals_i()  # Returns dict: {worker_id: dual}
        # For naive (homogeneous), use first worker's dual as representative
        duals_i = duals_i_dict.get(1, list(duals_i_dict.values())[0] if duals_i_dict else 0.0)
        duals_ts = master.getDuals_ts()

        # Solve SPs
        modelImprovable = False

        # Build SP.
        # NPP assumes full 100% performance during optimization: force zero directed cost
        # (delta = 0) so the labeling never applies degradation. The real performance is
        # recomputed ex post via evaluate_schedule_nl, replaying the exact same transitions.
        subproblem = create_subproblem(sp_solver, duals_i, duals_ts, data, 1, itr, eps, Min_WD_i, Max_WD_i, chi)
        subproblem.delta = np.zeros((4, 4), dtype=float)
        subproblem.e_max = 0.0
        subproblem.buildModel()

        # Save time to solve SP
        sub_start_time = time.time()
        if sp_solver.lower() in ['dp', 'labeling', 'labeling_bidir']:
            print("*{:^{output_len}}*".format(f"Solving SP with {sp_solver} in Iteration {itr}", output_len=output_len))
            subproblem.solveModelOpt(time_cg)
        elif previous_reduced_cost < -0.001:
            print("*{:^{output_len}}*".format(f"Use MIP-Gap > 0 in Iteration {itr}", output_len=output_len))
            subproblem.solveModelNOpt(time_cg)
        else:
            print("*{:^{output_len}}*".format(f"Use MIP-Gap = 0 in Iteration {itr}", output_len=output_len))
            subproblem.solveModelOpt(time_cg)
        sub_end_time = time.time()
        sp_time_hist.append(sub_end_time - sub_start_time)

        sub_totaltime = sub_end_time - sub_start_time
        timeHist.append(sub_totaltime)
        index = 1

        keys = ["X", "Perf", "P", "C", "X1", "Recovery"]
        methods = ["getOptX", "getOptPerf", "getOptP", "getOptC", "getOptX", "getOptR"]
        schedules = [X_schedules, Perf_schedules, P_schedules, Cons_schedules, X1_schedules, Recovery_schedules]

        for key, method, schedule in zip(keys, methods, schedules):
            value = getattr(subproblem, method)()
            schedule[f"Physician_{index}"].append(value)

        # Check if SP is solvable
        status = subproblem.getStatus()
        if status != 2:
            raise Exception("*{:^{output_len}}*".format("Pricing-Problem can not reach optimality!", output_len=output_len))

        # Save ObjVal History
        reducedCost = subproblem.model.objval
        objValHistSP.append(reducedCost)

        # Update previous_reduced_cost for the next iteration
        previous_reduced_cost = reducedCost
        #print("*{:^{output_len}}*".format(f"Reduced Costs in Iteration {itr}: {reducedCost}", output_len=output_len))

        # Increase latest used iteration
        last_itr = itr + 1

        # Generate and add columns with reduced cost
        if reducedCost < -threshold:
            Schedules = subproblem.getNewSchedule()
            master.addLambda(itr)  # Must be called BEFORE addColumn
            master.addColumn(itr, Schedules)
            master.updateModel()
            modelImprovable = True

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
            #print("*" * (output_len + 2))
            break

    if modelImprovable and itr == max_itr:
        max_itr *= 2

    # Solve Master Problem with integrality restored
    master.model.setParam('PoolSearchMode', 2)
    master.model.setParam('PoolSolutions', 100)
    master.model.setParam('PoolGap', 0.05)
    master.finalSolve(time_cg)

    status = master.model.Status
    if status in (gu.GRB.INF_OR_UNBD, gu.GRB.INFEASIBLE, gu.GRB.UNBOUNDED):
        ##print("The model cannot be solved because it is infeasible or unbounded")
        gu.sys.exit(1)

    if status != gu.GRB.OPTIMAL:
        ##print(f"Optimization was stopped with status {status}")
        gu.sys.exit(1)


    ls_p = [round(x, 5) for x in plotPerformanceList(P_schedules, master.printLambdas())]
    ls_sc = [1.0 if x > 0.5 else 0.0 for x in plotPerformanceList(Cons_schedules, master.printLambdas())]
    ls_perf_ = [round(x, 5) for x in plotPerformanceList(Perf_schedules, master.printLambdas())]
    ls_x = [1.0 if x > 0 else 0.0 for x in ls_perf_]
    ls_rec = process_recovery(ls_sc, chi, len(T))



    undercoverage_, understaffing_, perfloss_, consistency_, consistency_norm_, undercoverage_norm_, understaffing_norm_, perfloss_norm_, ls_perf, cumulative_total_ = master.calc_naive(ls_perf_, ls_sc, ls_rec, scale, worker_groups=worker_groups)
    consistency_ = compute_consistency_from_ls_x(ls_x, len(I), len(T))
    consistency_norm_ = round(consistency_ / (len(master.nurses) * scale), 5)

    # ---- Average the scalar decomposition over the optimal solution pool ----
    # The NPP schedule choice is degenerate (performance-blind), so the specific
    # schedule -> worker(group) pairing is arbitrary. We average the ex-post
    # decomposition over all optimal pool solutions to remove this dependence.
    try:
        best_obj = master.model.ObjVal
        n_pool = master.model.SolCount
    except Exception:
        n_pool = 0
    pool_dist = None  # pool-averaged distributional scalars (set below)
    if n_pool and n_pool > 1:
        agg = [0.0] * 8
        agg_d = [0.0] * 6  # spread_sc, load_share_sc, gini_sc, spread_perf, load_share_perf, gini_perf
        sols = []          # (undercoverage, perfloss, lam) per optimal pool solution
        cnt = 0
        nd, nn = len(master.days), len(master.nurses)
        for si in range(n_pool):
            master.model.Params.SolutionNumber = si
            if abs(master.model.PoolObjVal - best_obj) > 1e-6:
                continue  # only truly optimal solutions
            lam = master.printLambdasPool()
            sc_i = [1.0 if x > 0.5 else 0.0 for x in plotPerformanceList(Cons_schedules, lam)]
            perf_i = [round(x, 5) for x in plotPerformanceList(Perf_schedules, lam)]
            rec_i = process_recovery(sc_i, chi, len(T))
            r_i = master.calc_naive(perf_i, sc_i, rec_i, scale, worker_groups=worker_groups)
            x_i = [1.0 if p > 0 else 0.0 for p in perf_i]
            co_i = compute_consistency_from_ls_x(x_i, nn, nd)
            r_i = list(r_i)
            r_i[3] = round(co_i, 5)
            r_i[4] = round(co_i / (nn * scale), 5)
            for j in range(8):
                agg[j] += r_i[j]
            # distributional scalars for this pool solution (worker_totals dict is not averaged)
            x_i = [1.0 if p > 0 else 0.0 for p in perf_i]
            Lp_i = [x * (1 - p) for x, p in zip(x_i, perf_i)]
            _, sp_sc, lsh_sc, gi_sc = evaluate_inequality(sc_i, nd, nn)
            _, sp_pf, lsh_pf, gi_pf = evaluate_inequality(
                [sum(Lp_i[j:j + 3]) for j in range(0, len(Lp_i), 3)], nd, nn)
            for j, v in enumerate((sp_sc, lsh_sc, gi_sc, sp_pf, lsh_pf, gi_pf)):
                agg_d[j] += v
            sols.append((r_i[0], r_i[2], lam))
            cnt += 1
        master.model.Params.SolutionNumber = 0  # restore incumbent
        if cnt > 0:
            avg8 = [a / cnt for a in agg]
            (undercoverage_, understaffing_, perfloss_, consistency_,
             consistency_norm_, undercoverage_norm_, understaffing_norm_,
             perfloss_norm_) = avg8
            pool_dist = [a / cnt for a in agg_d]
            # Representative solution: the optimal pool solution closest to the pool
            # average (undercoverage, perfloss). Its schedule provides the raw per-worker
            # lists so that the stored lists match the averaged scalars.
            uc_avg, pl_avg = avg8[0], avg8[2]
            rep_lam = min(sols, key=lambda s: abs(s[0] - uc_avg) + abs(s[1] - pl_avg))[2]
            ls_p = [round(x, 5) for x in plotPerformanceList(P_schedules, rep_lam)]
            ls_sc = [1.0 if x > 0.5 else 0.0 for x in plotPerformanceList(Cons_schedules, rep_lam)]
            ls_perf_ = [round(x, 5) for x in plotPerformanceList(Perf_schedules, rep_lam)]
            ls_x = [1.0 if x > 0 else 0.0 for x in ls_perf_]
            ls_rec = process_recovery(ls_sc, chi, len(T))
            _, _, _, _, _, _, _, _, ls_perf, cumulative_total_ = master.calc_naive(
                ls_perf_, ls_sc, ls_rec, scale, worker_groups=worker_groups)
            # scalar metrics stay as pool average (avg8); only lists come from rep solution
            consistency_ = avg8[3]
            consistency_norm_ = avg8[4]
            print(f"  NPP: averaged decomposition (+ inequality) over {cnt} optimal pool solutions; representative lists selected")
    # ------------------------------------------------------------------------

    undercoverage_naive = master.getUndercoverage()
    #print(ls_p, ls_sc, ls_perf, ls_x, ls_rec, sep="\n")
    # Print each value with description
    #print("Undercoverage:", undercoverage_)
    #print("Understaffing:", understaffing_)
    #print("Performance loss:", perfloss_)
    #print("Consistency:", consistency_)
    #print("Normalized consistency:", consistency_norm_)
    #print("Normalized undercoverage:", undercoverage_norm_)
    #print("Normalized understaffing:", understaffing_norm_)
    #print("Normalized performance loss:", perfloss_norm_)
    #print("Performance local search:", ls_perf)
    #print("Cumulative total:", cumulative_total_)
    cumulative_with_naive = [cumulative_total_[j] + undercoverage_naive[j] for j in range(len(cumulative_total_))]
    #print("Cumulative total + naive undercoverage:", cumulative_with_naive)

    # Inequality
    L_perf = [x * (1 - p) for x, p in zip(ls_x, ls_perf)]
    results_ineq_sc, spread_sc, load_share_sc, gini_sc = evaluate_inequality(ls_sc, len(master.days),
                                                                             len(master.nurses))
    results_ineq_perf, spread_perf, load_share_perf, gini_perf = evaluate_inequality(
        [sum(L_perf[i:i + 3]) for i in range(0, len(L_perf), 3)], len(master.days), len(master.nurses))

    # Replace the incumbent distributional scalars by their pool average (skew-free);
    # the per-worker worker_totals dicts (results_ineq_*) stay from the incumbent.
    if pool_dist is not None:
        spread_sc, load_share_sc, gini_sc, spread_perf, load_share_perf, gini_perf = pool_dist

    # shift blocks
    shift_blocks = analyze_and_plot_blocks(ls_x, len(master.nurses), len(master.days), len(master.shifts))

    # Return all values
    return (
        undercoverage_,
        understaffing_,
        perfloss_,
        consistency_,
        consistency_norm_,
        undercoverage_norm_,
        understaffing_norm_,
        perfloss_norm_,
        master.model.objval,
        ls_p,
        ls_sc,
        ls_perf,
        ls_x,
        ls_rec,
        cumulative_with_naive,
        results_ineq_sc,
        spread_sc,
        load_share_sc,
        gini_sc,
        results_ineq_perf,
        spread_perf,
        load_share_perf,
        gini_perf,
        shift_blocks
    )