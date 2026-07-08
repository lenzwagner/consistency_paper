from core.cg_behavior import *
from core.cg_naive import column_generation_naive
from core.cg_ecp import column_generation_ecp
from Utils.Plots.plots import *
from Utils.aggundercover import *
from datetime import *
from Utils.demand import *
from core.base_case import get_base_case_groups, get_homogeneous_base_case_group, get_wd_constraints, get_base_case_delta, LEN_I_RANGE, SCENARIO_RANGE, PATTERN, CHI, K_ECP
from core.worker_groups import WorkerGroup
from core.solver_base import MAX_ITR, THRESHOLD, TIME_CG_INIT, TIME_CG, OUTPUT_LEN, SCALE
from Utils.metrics import evaluate_inequality, compute_horizon_stability_metrics
import time
import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))
os.makedirs("results/csv", exist_ok=True)
os.makedirs("results/xlsx", exist_ok=True)
os.makedirs("results/pkl", exist_ok=True)


def _get_worker_totals_sc(lst, T_len, n_workers):
    worker_totals, *_ = evaluate_inequality(lst, T_len, n_workers)
    return worker_totals


def _get_worker_totals_perf(ls_x, ls_perf, n_shifts, T_len, n_workers):
    L_perf = [x * (1.0 - p) for x, p in zip(ls_x, ls_perf)]
    daily = [sum(L_perf[i:i + n_shifts]) for i in range(0, len(L_perf), n_shifts)]
    worker_totals, *_ = evaluate_inequality(daily, T_len, n_workers)
    return worker_totals


def _compute_stats(worker_totals, worker_ids=None):
    if worker_ids is None:
        vals = list(worker_totals.values())
    else:
        vals = [worker_totals[wid] for wid in worker_ids if wid in worker_totals]
    if not vals:
        return 0.0, 0.0, 0.0, 0.0
    arr = np.array(vals, dtype=np.float64)
    return float(arr.mean()), float(arr.min()), float(arr.max()), float(arr.std())





def _compute_group_block_lengths(ls_x, n_days, n_shifts, worker_ids, n_workers):
    sublist_len = n_days * n_shifts
    group_blocks = []
    for wid in worker_ids:
        idx = wid - 1
        if idx >= n_workers:
            continue
        worker_x = ls_x[idx * sublist_len : (idx + 1) * sublist_len]
        
        # Decode daily schedules (0 = off, 1..N = shift type)
        schedule = []
        for d in range(n_days):
            day_data = worker_x[d * n_shifts : (d + 1) * n_shifts]
            shift_id = 0
            for s_idx, val in enumerate(day_data):
                if val > 0.5:
                    shift_id = s_idx + 1
                    break
            schedule.append(shift_id)
            
        # Identify block lengths of the same shift type
        current_len = 0
        last_shift = -1
        for shift in schedule:
            if shift == 0:
                if current_len > 0:
                    group_blocks.append(current_len)
                current_len = 0
                last_shift = -1
                continue
            if shift == last_shift:
                current_len += 1
            else:
                if current_len > 0:
                    group_blocks.append(current_len)
                current_len = 1
                last_shift = shift
        if current_len > 0:
            group_blocks.append(current_len)
            
    if not group_blocks:
        return 0.0
    return float(np.mean(group_blocks))


# DataFrame
results = pd.DataFrame(columns=['I', 'T', 'K', 'pattern', 'scenario', 'prob', 'num_groups', 'epsilon', 'chi', 'gap', 'lagrange', 'objval', 'lbound', 'iteration', 'time_sp', 'time_rmp',
                                'time_ip', 'undercover_behavior', 'undercover_norm_behavior', 'cons_behavior', 'cons_norm_behavior', 'perf_behavior',
                                'perf_norm_behavior', 'understaffing_behavior', 'understaffing_norm_behavior', 'undercover_naive', 'undercover_norm_naive', 'cons_naive',
                                'cons_norm_naive', 'perf_naive', 'perf_norm_naive', 'understaffing_naive', 'understaffing_norm_naive', 'shift_undercover_naive',
                                'shift_undercover_behavior', 'cons_list_behavior', 'cons_list_naive', 'p_list_behavior', 'p_list_naive',
                                'x_list_behavior', 'x_list_naive', 'r_list_behavior', 'r_list_naive', 'daily_undercover_behavior', 'daily_undercover_naive', 'spread_sc_behavior',
                                'spread_sc_naive', 'load_share_sc_behavior', 'load_share_sc_naive', 'gini_sc_behavior', 'gini_sc_naive', 'disutility_sc_behavior', 'disutility_sc_naive',
                                'top10_sc_behavior', 'top10_sc_naive',
                                'spread_perf_behavior', 'spread_perf_naive', 'load_share_perf_behavior', 'load_share_perf_naive', 'gini_perf_behavior',
                                'gini_perf_naive', 'disutility_perf_behavior', 'disutility_perf_naive', 'top10_perf_behavior', 'top10_perf_naive',
                                'shift_blocks_behavior', 'shift_blocks_naive',
                                'num_blocks_behavior', 'num_blocks_naive', 'mean_block_len_behavior', 'mean_block_len_naive', 'reduction_naive', 'reduction_ecp'])

def prompt_user_for_groups():
    print("\n" + "=" * 80)
    print("WORKER GROUPS CONFIGURATION")
    print("=" * 80)

    # 1. Number of groups
    ans_g = input("How many groups? (Default: 2): ").strip()
    if not ans_g:
        num_groups = 2
    else:
        try:
            num_groups = int(ans_g)
        except ValueError:
            print("Invalid input. Using default value: 2")
            num_groups = 2

    # Default parameters for 2 groups
    default_params = [
        (0.0, 2, 0.5, 0.5, 7.0),
        (0.0, 4, 1.5, 1.5, 21.0)
    ]

    group_params = []

    # If 2 groups, ask if they want the default parameters
    if num_groups == 2:
        ans_p = input("Use default parameters for 2 groups? (Group 1: chi=2, T_R=7 | Group 2: chi=4, T_R=21) [Y/n]: ").strip().lower()
        if ans_p in ('', 'y', 'yes', 'j', 'ja'):
            group_params = default_params

    # If custom parameters or custom number of groups:
    if not group_params:
        for i in range(1, num_groups + 1):
            while True:
                # Show fallback example based on group index
                example = "0.0, 2, 0.5, 0.5, 7" if i == 1 else ("0.0, 4, 1.5, 1.5, 21" if i == 2 else "0.0, 3, 1.0, 1.0, 14")
                ans_val = input(f"Parameters for Group {i} as tuple (epsilon, chi, gamma_C, gamma_R, T_R)\n(e.g., {example}): ").strip()
                # Remove brackets/parentheses if present
                clean_val = ans_val.replace('(', '').replace(')', '').replace('[', '').replace(']', '')
                parts = [p.strip() for p in clean_val.split(',') if p.strip()]
                if len(parts) == 5:
                    try:
                        eps = float(parts[0])
                        chi = int(parts[1])
                        g_C = float(parts[2])
                        g_R = float(parts[3])
                        T_R = float(parts[4])
                        group_params.append((eps, chi, g_C, g_R, T_R))
                        break
                    except ValueError:
                        print("Error converting values to numbers. Please try again.")
                else:
                    print("Please enter exactly 5 comma-separated values.")

    # 3. Worker distribution / split
    while True:
        default_dist = ", ".join([str(round(1.0 / num_groups, 3)) for _ in range(num_groups)])
        ans_dist = input(f"Worker distribution fractions (comma-separated, e.g., {default_dist}) [Leave blank for equal distribution]: ").strip()
        if not ans_dist:
            ratios = [1.0 / num_groups] * num_groups
            break
        else:
            parts = [p.strip() for p in ans_dist.split(',') if p.strip()]
            if len(parts) == num_groups:
                try:
                    ratios = [float(p) for p in parts]
                    tot = sum(ratios)
                    if tot > 0:
                        ratios = [r / tot for r in ratios]
                        break
                    else:
                        print("Sum of fractions must be greater than 0.")
                except ValueError:
                    print("Invalid numbers. Please try again.")
            else:
                print(f"Please enter exactly {num_groups} fractions (comma-separated).")

    print("=" * 80)
    print("Configuration successfully applied.")
    print("=" * 80 + "\n")
    return num_groups, group_params, ratios

# Prompt configuration
num_groups, group_params, ratios = prompt_user_for_groups()

# Times and Parameter
time_cg, time_cg_init = TIME_CG, TIME_CG_INIT
max_itr, threshold = MAX_ITR, THRESHOLD

start_time = time.time()

# Loop
for len_I in LEN_I_RANGE:
    for scenario in SCENARIO_RANGE:
        prob = {'Medium': 1.0, 'High': 1.1, 'Low': 0.9}.get(PATTERN)

        # Data
        T = list(range(1, 29))
        I = list(range(1, len_I + 1))
        K = [1, 2, 3]

        data = pd.DataFrame({
            'I': I + [np.nan] * (max(len(I), len(T), len(K)) - len(I)),
            'T': T + [np.nan] * (max(len(I), len(T), len(K)) - len(T)),
            'K': K + [np.nan] * (max(len(I), len(T), len(K)) - len(K))
        })

        demand_dict = read_demand('data/demand_data_vol.xlsx', len(I), PATTERN, scenario=scenario)

        Min_WD_i, Max_WD_i = get_wd_constraints(I)
        
        # Partition I based on user-configured ratios
        n_workers = len(I)
        split_sizes = []
        accumulated = 0
        for i in range(num_groups - 1):
            sz = int(round(ratios[i] * n_workers))
            split_sizes.append(sz)
            accumulated += sz
        split_sizes.append(max(0, n_workers - accumulated))
        
        worker_groups = {}
        delta = get_base_case_delta()
        
        current_idx = 0
        for i in range(num_groups):
            sz = split_sizes[i]
            g_workers = I[current_idx : current_idx + sz]
            current_idx += sz
            
            eps, chi, g_C, g_R, T_R = group_params[i]
            g_name = f"group{i+1}"
            
            worker_groups[g_name] = WorkerGroup(
                name=g_name,
                epsilon=eps,
                chi=chi,
                worker_ids=g_workers,
                gamma_C=g_C,
                gamma_R=g_R,
                T_R=T_R,
                e_max=1.0,
                delta=delta
            )
            
        print(f"Worker groups: {[(g.name, len(g.worker_ids), g.chi) for g in worker_groups.values()]}")

        print(f"")
        print(f"Iteration: I: {len(I)} - Pattern: {PATTERN} - Scenario: {scenario}")
        print(f"")

        ## Column Generation - CG+bidir (Labeling subproblem)
        print('Doing behaviour with CG+Labeling (bidir SP)')
        t0_bidir = time.time()
        (undercoverage_behavior, understaffing_behavior, perfloss_behavior, consistency_behavior,
         consistency_norm_behavior, undercoverage_norm_behavior, understaffing_norm_behavior,
         perfloss_norm_behavior, final_obj_behavior, final_lb, itr, lagrangeB, gap, time_sps, time_rmp,
         time_ip, ls_p_behavior, ls_sc_behavior, ls_perf_behavior, ls_x_behavior,
         ls_r_behavior, undercoverage_per_shift_behavior, spread_sc_behavior,
         load_share_sc_behavior, gini_sc_behavior, disutility_sc_behavior, top10_sc_behavior,
         spread_perf_behavior, load_share_perf_behavior, gini_perf_behavior, disutility_perf_behavior, top10_perf_behavior,
         shift_blocks_behavior, rmp_obj_hist_behavior, sp_obj_hist_behavior,
         # sp_obj_hist_behavior/sp_time_hist_behavior: dict keyed by worker-group
         # name -> per-iteration list (reduced cost / solve time), plus a 'mean'
         # key across groups when there is more than one (see cg_behavior.py).
         rmp_time_hist_behavior, sp_time_hist_behavior,
         lagrange_hist_behavior) = column_generation_behavior(
            data, demand_dict, 0.0, Min_WD_i, Max_WD_i, time_cg_init, max_itr, 100, CHI,
            threshold, time_cg, I, T, K, prob, sp_solver='labeling_bidir',
            worker_groups=worker_groups, save_lp=True,
            use_heuristic_start=False, use_null_column=True
        )
        time_bidir = time.time() - t0_bidir
        print(f'  --> CG+bidir: obj={final_obj_behavior:.2f}, iter={itr}, gap={gap:.2f}%, time={time_bidir:.1f}s')

        # NPP: full 100% performance in the labeling; the real performance loss is
        # recomputed ex post via the SAME nonlinear counter-based transitions as the
        # model (directed Delta, gamma_C/gamma_R/alpha_R/T_R) by passing worker_groups.
        print('Doing naive with labeling_bidir')
        (
        undercoverage_naive, understaffing_naive, perfloss_naive, consistency_naive, consistency_norm_naive,
        undercoverage_norm_naive, understaffing_norm_naive,
        perfloss_norm_naive, final_obj_naive, ls_p_naive, ls_sc_naive, ls_perf_naive, ls_x_naive,
        ls_r_naive, undercoverage_per_shift_naive, spread_sc_naive,
        load_share_sc_naive, gini_sc_naive, disutility_sc_naive, top10_sc_naive,
        spread_perf_naive, load_share_perf_naive, gini_perf_naive, disutility_perf_naive, top10_perf_naive, shift_blocks_naive, ls_perf_cellwise_naive) = column_generation_naive(
            data, demand_dict, 0, Min_WD_i, Max_WD_i, time_cg_init, max_itr, 100, CHI,
            threshold, time_cg, I, T, K, prob, sp_solver='labeling_bidir',
            worker_groups=worker_groups, use_null_column=True)

        # ECP: identical to NPP (100% performance in the labeling, same nonlinear ex-post
        # via worker_groups), but with the additional rolling shift-change cap k<=2 per
        # 7-day window enforced directly in the forward labeling.
        print(f'Doing ECP with labeling (k<={K_ECP})')
        (
        undercoverage_ecp, understaffing_ecp, perfloss_ecp, consistency_ecp, consistency_norm_ecp,
        undercoverage_norm_ecp, understaffing_norm_ecp,
        perfloss_norm_ecp, final_obj_ecp, ls_p_ecp, ls_sc_ecp, ls_perf_ecp, ls_x_ecp,
        ls_r_ecp, undercoverage_per_shift_ecp, spread_sc_ecp,
        load_share_sc_ecp, gini_sc_ecp, disutility_sc_ecp, top10_sc_ecp,
        spread_perf_ecp, load_share_perf_ecp, gini_perf_ecp, disutility_perf_ecp, top10_perf_ecp, shift_blocks_ecp, ls_perf_cellwise_ecp) = column_generation_ecp(
            data, demand_dict, 0, Min_WD_i, Max_WD_i, time_cg_init, max_itr, 100, CHI,
            threshold, time_cg, I, T, K, prob, k=K_ECP, sp_solver='labeling_bidir',
            worker_groups=worker_groups, use_null_column=True)

        shift_undercover_behavior = create_dict_from_list(undercoverage_per_shift_behavior, len(T), len(K))
        shift_undercover_naive = create_dict_from_list(undercoverage_per_shift_naive, len(T), len(K))
        shift_undercover_ecp = create_dict_from_list(undercoverage_per_shift_ecp, len(T), len(K))

        daily_undercover_naive = dict_reducer(shift_undercover_naive)
        daily_undercover_behavior = dict_reducer(shift_undercover_behavior)
        daily_undercover_ecp = dict_reducer(shift_undercover_ecp)

        # Fragmentation of shift-consistency blocks: sum(shift_blocks) = total worked
        # (worker, day) cells (identical across paradigms, since coverage need is fixed),
        # while the number/mean length of blocks differs by how the workload is chunked.
        num_blocks_behavior = len(shift_blocks_behavior)
        num_blocks_naive = len(shift_blocks_naive)
        num_blocks_ecp = len(shift_blocks_ecp)
        mean_block_len_behavior = float(np.mean(shift_blocks_behavior)) if shift_blocks_behavior else 0.0
        mean_block_len_naive = float(np.mean(shift_blocks_naive)) if shift_blocks_naive else 0.0
        mean_block_len_ecp = float(np.mean(shift_blocks_ecp)) if shift_blocks_ecp else 0.0
        min_block_len_behavior = float(np.min(shift_blocks_behavior)) if shift_blocks_behavior else 0.0
        max_block_len_behavior = float(np.max(shift_blocks_behavior)) if shift_blocks_behavior else 0.0
        std_block_len_behavior = float(np.std(shift_blocks_behavior)) if shift_blocks_behavior else 0.0
        min_block_len_naive = float(np.min(shift_blocks_naive)) if shift_blocks_naive else 0.0
        max_block_len_naive = float(np.max(shift_blocks_naive)) if shift_blocks_naive else 0.0
        std_block_len_naive = float(np.std(shift_blocks_naive)) if shift_blocks_naive else 0.0
        min_block_len_ecp = float(np.min(shift_blocks_ecp)) if shift_blocks_ecp else 0.0
        max_block_len_ecp = float(np.max(shift_blocks_ecp)) if shift_blocks_ecp else 0.0
        std_block_len_ecp = float(np.std(shift_blocks_ecp)) if shift_blocks_ecp else 0.0

        # Non-group-specific (pooled across the whole workforce) descriptive
        # stats for shift changes and performance loss -- complements the
        # existing gini/spread/disutility/top10 inequality metrics (which
        # already pool across all workers) with the plain mean/min/max/std
        # one would report first.
        n_sched_behavior = len(ls_sc_behavior) // len(T)
        n_sched_naive = len(ls_sc_naive) // len(T)
        n_sched_ecp = len(ls_sc_ecp) // len(T)

        wt_sc_behavior = _get_worker_totals_sc(ls_sc_behavior, len(T), n_sched_behavior)
        wt_sc_naive = _get_worker_totals_sc(ls_sc_naive, len(T), n_sched_naive)
        wt_sc_ecp = _get_worker_totals_sc(ls_sc_ecp, len(T), n_sched_ecp)

        wt_perf_behavior = _get_worker_totals_perf(ls_x_behavior, ls_perf_behavior, len(K), len(T), n_sched_behavior)
        wt_perf_naive = _get_worker_totals_perf(ls_x_naive, ls_perf_cellwise_naive, len(K), len(T), n_sched_naive)
        wt_perf_ecp = _get_worker_totals_perf(ls_x_ecp, ls_perf_cellwise_ecp, len(K), len(T), n_sched_ecp)

        mean_sc_behavior, min_sc_behavior, max_sc_behavior, std_sc_behavior = _compute_stats(wt_sc_behavior)
        mean_sc_naive, min_sc_naive, max_sc_naive, std_sc_naive = _compute_stats(wt_sc_naive)
        mean_sc_ecp, min_sc_ecp, max_sc_ecp, std_sc_ecp = _compute_stats(wt_sc_ecp)

        mean_perf_behavior, min_perf_behavior, max_perf_behavior, std_perf_behavior = _compute_stats(wt_perf_behavior)
        mean_perf_naive, min_perf_naive, max_perf_naive, std_perf_naive = _compute_stats(wt_perf_naive)
        mean_perf_ecp, min_perf_ecp, max_perf_ecp, std_perf_ecp = _compute_stats(wt_perf_ecp)

        group_results = {}
        for g_name, g_obj in worker_groups.items():
            g_ids = g_obj.worker_ids
            m_sc_bev, min_sc_bev, max_sc_bev, std_sc_bev = _compute_stats(wt_sc_behavior, g_ids)
            m_sc_nai, min_sc_nai, max_sc_nai, std_sc_nai = _compute_stats(wt_sc_naive, g_ids)
            m_sc_ecp_val, min_sc_ecp_val, max_sc_ecp_val, std_sc_ecp_val = _compute_stats(wt_sc_ecp, g_ids)
            
            group_results[f'mean_sc_{g_name}_behavior'] = m_sc_bev
            group_results[f'mean_sc_{g_name}_naive'] = m_sc_nai
            group_results[f'mean_sc_{g_name}_ecp'] = m_sc_ecp_val
            
            group_results[f'min_sc_{g_name}_behavior'] = min_sc_bev
            group_results[f'min_sc_{g_name}_naive'] = min_sc_nai
            group_results[f'min_sc_{g_name}_ecp'] = min_sc_ecp_val
            
            group_results[f'max_sc_{g_name}_behavior'] = max_sc_bev
            group_results[f'max_sc_{g_name}_naive'] = max_sc_nai
            group_results[f'max_sc_{g_name}_ecp'] = max_sc_ecp_val
            
            group_results[f'std_sc_{g_name}_behavior'] = std_sc_bev
            group_results[f'std_sc_{g_name}_naive'] = std_sc_nai
            group_results[f'std_sc_{g_name}_ecp'] = std_sc_ecp_val

            m_perf_bev, min_perf_bev, max_perf_bev, std_perf_bev = _compute_stats(wt_perf_behavior, g_ids)
            m_perf_nai, min_perf_nai, max_perf_nai, std_perf_nai = _compute_stats(wt_perf_naive, g_ids)
            m_perf_ecp_val, min_perf_ecp_val, max_perf_ecp_val, std_perf_ecp_val = _compute_stats(wt_perf_ecp, g_ids)
            
            group_results[f'mean_perf_{g_name}_behavior'] = m_perf_bev
            group_results[f'mean_perf_{g_name}_naive'] = m_perf_nai
            group_results[f'mean_perf_{g_name}_ecp'] = m_perf_ecp_val
            
            group_results[f'min_perf_{g_name}_behavior'] = min_perf_bev
            group_results[f'min_perf_{g_name}_naive'] = min_perf_nai
            group_results[f'min_perf_{g_name}_ecp'] = min_perf_ecp_val
            
            group_results[f'max_perf_{g_name}_behavior'] = max_perf_bev
            group_results[f'max_perf_{g_name}_naive'] = max_perf_nai
            group_results[f'max_perf_{g_name}_ecp'] = max_perf_ecp_val
            
            group_results[f'std_perf_{g_name}_behavior'] = std_perf_bev
            group_results[f'std_perf_{g_name}_naive'] = std_perf_nai
            group_results[f'std_perf_{g_name}_ecp'] = std_perf_ecp_val

            # Block lengths of the same shift type
            mean_block_bev = _compute_group_block_lengths(ls_x_behavior, len(T), len(K), g_ids, n_sched_behavior)
            mean_block_nai = _compute_group_block_lengths(ls_x_naive, len(T), len(K), g_ids, n_sched_naive)
            mean_block_ecp = _compute_group_block_lengths(ls_x_ecp, len(T), len(K), g_ids, n_sched_ecp)
            
            group_results[f'mean_block_len_{g_name}_behavior'] = mean_block_bev
            group_results[f'mean_block_len_{g_name}_naive'] = mean_block_nai
            group_results[f'mean_block_len_{g_name}_ecp'] = mean_block_ecp


        # Relative reduction in total undercoverage achieved by the BAP vs. the NPP / ECP (%).
        reduction_naive = ((undercoverage_naive - undercoverage_behavior) / undercoverage_naive * 100
                            if undercoverage_naive else 0.0)
        reduction_ecp = ((undercoverage_ecp - undercoverage_behavior) / undercoverage_ecp * 100
                          if undercoverage_ecp else 0.0)

        # End-of-horizon performance stability (demand-regime / exhaustion analysis):
        # mean daily performance trajectory, end-of-horizon performance, share of
        # workers below a floor at the end, and low-performance days in the final window.
        # BAP: ls_p_behavior is the genuine performance trajectory (BAP optimizes with
        # real degradation, so P_schedules already reflects it).
        # NPP/ECP: ls_p_naive/ls_p_ecp would be wrong here -- during pricing NPP/ECP force
        # zero degradation (delta=0/e_max=0), so P_schedules is trivially 1.0 always. The
        # correctly recomputed ex-post per-day performance is ls_perf_naive/ls_perf_ecp
        # (from calc_naive/_calc_naive_nl's evaluate_schedule_nl reconstruction), not ls_p_*.
        horizon_stats_behavior = compute_horizon_stability_metrics(ls_p_behavior, n_sched_behavior, len(T), tau=0.9, k=7)
        horizon_stats_naive = compute_horizon_stability_metrics(ls_perf_naive, n_sched_naive, len(T), tau=0.9, k=7)
        horizon_stats_ecp = compute_horizon_stability_metrics(ls_perf_ecp, n_sched_ecp, len(T), tau=0.9, k=7)

        # Data frame -- every metric that exists for all three paradigms is
        # grouped as a behavior/naive/ecp triple, in the same order as
        # ordered_cols below (which just reindexes this, so the two should
        # never drift apart).
        result_dict = {
                        # Metadata
                        'I': len(I),
                        'T': len(T),
                        'K': len(K),
                        'pattern': PATTERN,
                        'scenario': scenario,
                        'prob': prob,
                        'num_groups': num_groups,

                        # BAP-specific optimization metrics
                        'gap': gap,
                        'lagrange': lagrangeB,
                        'lbound': final_lb,
                        'iteration': itr,
                        'time_sp': time_sps,
                        'time_rmp': time_rmp,
                        'time_ip': time_ip,
                        'time_total': time_bidir,

                        # Metrics (behavior, naive, ecp sequentially)
                        'reduction_naive': reduction_naive,
                        'reduction_ecp': reduction_ecp,
                        'objval': final_obj_behavior,
                        'objval_naive': final_obj_naive,
                        'objval_ecp': final_obj_ecp,
                        'undercover_behavior': undercoverage_behavior,
                        'undercover_naive': undercoverage_naive,
                        'undercover_ecp': undercoverage_ecp,
                        'undercover_norm_behavior': undercoverage_norm_behavior,
                        'undercover_norm_naive': undercoverage_norm_naive,
                        'undercover_norm_ecp': undercoverage_norm_ecp,
                        'cons_behavior': consistency_behavior,
                        'cons_naive': consistency_naive,
                        'cons_ecp': consistency_ecp,
                        'cons_norm_behavior': consistency_norm_behavior,
                        'cons_norm_naive': consistency_norm_naive,
                        'cons_norm_ecp': consistency_norm_ecp,
                        'perf_behavior': perfloss_behavior,
                        'perf_naive': perfloss_naive,
                        'perf_ecp': perfloss_ecp,
                        'perf_norm_behavior': perfloss_norm_behavior,
                        'perf_norm_naive': perfloss_norm_naive,
                        'perf_norm_ecp': perfloss_norm_ecp,
                        'understaffing_behavior': understaffing_behavior,
                        'understaffing_naive': understaffing_naive,
                        'understaffing_ecp': understaffing_ecp,
                        'understaffing_norm_behavior': understaffing_norm_behavior,
                        'understaffing_norm_naive': understaffing_norm_naive,
                        'understaffing_norm_ecp': understaffing_norm_ecp,

                        # Inequality / Fairness metrics (consistency)
                        'spread_sc_behavior': spread_sc_behavior,
                        'spread_sc_naive': spread_sc_naive,
                        'spread_sc_ecp': spread_sc_ecp,
                        'load_share_sc_behavior': load_share_sc_behavior,
                        'load_share_sc_naive': load_share_sc_naive,
                        'load_share_sc_ecp': load_share_sc_ecp,
                        'gini_sc_behavior': gini_sc_behavior,
                        'gini_sc_naive': gini_sc_naive,
                        'gini_sc_ecp': gini_sc_ecp,
                        'disutility_sc_behavior': disutility_sc_behavior,
                        'disutility_sc_naive': disutility_sc_naive,
                        'disutility_sc_ecp': disutility_sc_ecp,
                        'top10_sc_behavior': top10_sc_behavior,
                        'top10_sc_naive': top10_sc_naive,
                        'top10_sc_ecp': top10_sc_ecp,

                        # Non-group-specific (pooled) descriptive stats for shift changes
                        'mean_sc_behavior': mean_sc_behavior,
                        'mean_sc_naive': mean_sc_naive,
                        'mean_sc_ecp': mean_sc_ecp,
                        'min_sc_behavior': min_sc_behavior,
                        'min_sc_naive': min_sc_naive,
                        'min_sc_ecp': min_sc_ecp,
                        'max_sc_behavior': max_sc_behavior,
                        'max_sc_naive': max_sc_naive,
                        'max_sc_ecp': max_sc_ecp,
                        'std_sc_behavior': std_sc_behavior,
                        'std_sc_naive': std_sc_naive,
                        'std_sc_ecp':  std_sc_ecp,

                        # Inequality / Fairness metrics (performance)
                        'spread_perf_behavior': spread_perf_behavior,
                        'spread_perf_naive': spread_perf_naive,
                        'spread_perf_ecp': spread_perf_ecp,
                        'load_share_perf_behavior': load_share_perf_behavior,
                        'load_share_perf_naive': load_share_perf_naive,
                        'load_share_perf_ecp': load_share_perf_ecp,
                        'gini_perf_behavior': gini_perf_behavior,
                        'gini_perf_naive': gini_perf_naive,
                        'gini_perf_ecp': gini_perf_ecp,
                        'disutility_perf_behavior': disutility_perf_behavior,
                        'disutility_perf_naive': disutility_perf_naive,
                        'disutility_perf_ecp': disutility_perf_ecp,
                        'top10_perf_behavior': top10_perf_behavior,
                        'top10_perf_naive': top10_perf_naive,
                        'top10_perf_ecp': top10_perf_ecp,

                        # (Pooled) descriptive stats for performance loss
                        'mean_perf_behavior': mean_perf_behavior,
                        'mean_perf_naive': mean_perf_naive,
                        'mean_perf_ecp': mean_perf_ecp,
                        'min_perf_behavior': min_perf_behavior,
                        'min_perf_naive': min_perf_naive,
                        'min_perf_ecp': min_perf_ecp,
                        'max_perf_behavior': max_perf_behavior,
                        'max_perf_naive': max_perf_naive,
                        'max_perf_ecp': max_perf_ecp,
                        'std_perf_behavior': std_perf_behavior,
                        'std_perf_naive': std_perf_naive,
                        'std_perf_ecp': std_perf_ecp,

                        # Number of shift blocks
                        'shift_blocks_behavior': shift_blocks_behavior,
                        'shift_blocks_naive': shift_blocks_naive,
                        'shift_blocks_ecp': shift_blocks_ecp,
                        'num_blocks_behavior': num_blocks_behavior,
                        'num_blocks_naive': num_blocks_naive,
                        'num_blocks_ecp': num_blocks_ecp,
                        'mean_block_len_behavior': mean_block_len_behavior,
                        'mean_block_len_naive': mean_block_len_naive,
                        'mean_block_len_ecp': mean_block_len_ecp,
                        'min_block_len_behavior': min_block_len_behavior,
                        'min_block_len_naive': min_block_len_naive,
                        'min_block_len_ecp': min_block_len_ecp,
                        'max_block_len_behavior': max_block_len_behavior,
                        'max_block_len_naive': max_block_len_naive,
                        'max_block_len_ecp': max_block_len_ecp,
                        'std_block_len_behavior': std_block_len_behavior,
                        'std_block_len_naive': std_block_len_naive,
                        'std_block_len_ecp': std_block_len_ecp,

                        # Demand regimes
                        'p_end_behavior': horizon_stats_behavior['p_end'],
                        'p_end_naive': horizon_stats_naive['p_end'],
                        'p_end_ecp': horizon_stats_ecp['p_end'],
                        'b_end_tau_behavior': horizon_stats_behavior['b_end_tau'],
                        'b_end_tau_naive': horizon_stats_naive['b_end_tau'],
                        'b_end_tau_ecp': horizon_stats_ecp['b_end_tau'],
                        'l_tail_tau_behavior': horizon_stats_behavior['l_tail_tau'],
                        'l_tail_tau_naive': horizon_stats_naive['l_tail_tau'],
                        'l_tail_tau_ecp': horizon_stats_ecp['l_tail_tau'],
                        'p_bar_d_behavior': horizon_stats_behavior['p_bar_d'],
                        'p_bar_d_naive': horizon_stats_naive['p_bar_d'],
                        'p_bar_d_ecp': horizon_stats_ecp['p_bar_d'],

                        # Lists/Dicts (dropped in Excel, kept in CSV/Pickle)
                        'shift_undercover_behavior': shift_undercover_behavior,
                        'shift_undercover_naive': shift_undercover_naive,
                        'shift_undercover_ecp': shift_undercover_ecp,
                        'daily_undercover_behavior': daily_undercover_behavior,
                        'daily_undercover_naive': daily_undercover_naive,
                        'daily_undercover_ecp': daily_undercover_ecp,

                        # Convergence history (BAP)
                        'rmp_obj_hist': rmp_obj_hist_behavior,
                        'sp_obj_hist': sp_obj_hist_behavior,
                        'rmp_time_hist': rmp_time_hist_behavior,
                        'sp_time_hist': sp_time_hist_behavior,
                        'lagrange_hist': lagrange_hist_behavior,
        }
        for i in range(num_groups):
            eps, chi, g_C, g_R, T_R = group_params[i]
            tr_val = int(T_R) if isinstance(T_R, (int, float)) and float(T_R).is_integer() else T_R
            val_str = f"({tr_val})" # wait, let's keep the parameter tuple intact: (chi, g_C, g_R, tr_val)
            val_str = f"({chi}, {g_C}, {g_R}, {tr_val})"
            result_dict[f'group{i+1}_params'] = val_str
            
        result_dict.update(group_results)
        result = pd.DataFrame([result_dict])

        results = pd.concat([results, result], ignore_index=True)

def recursive_round(val, decimals=4):
    if isinstance(val, (float, np.floating)):
        return round(val, decimals)
    elif isinstance(val, list):
        return [recursive_round(x, decimals) for x in val]
    elif isinstance(val, tuple):
        return tuple(recursive_round(x, decimals) for x in val)
    elif isinstance(val, dict):
        return {k: recursive_round(v, decimals) for k, v in val.items()}
    else:
        return val

# Round all float values in results (including inside lists/dicts) to 4 decimal places
for col in results.columns:
    results[col] = results[col].apply(lambda x: recursive_round(x, 4))

# ---------------------------------------------------------------------------
# Save WITHOUT data loss.
#   - Pickle: lossless, preserves lists/dicts as native Python objects
#     (for programmatic loading: pd.read_pickle(...)).
#   - CSV:    lossless for numbers; long lists are stored as strings
#     (NO 32767 character cell truncation as in Excel).
#   - Excel:  only excel-compatible (short) columns, to prevent large list
#     columns from being silently truncated to 32767 characters.
#     Cells that would exceed this limit are excluded.
# ---------------------------------------------------------------------------
# Sort columns: behavior, naive, ecp for each metric
group_param_cols = [f'group{i+1}_params' for i in range(num_groups)]

# Build dynamic group columns for sc, perf, and shift block lengths
group_names = [f'group{i+1}' for i in range(num_groups)]
sc_group_cols = {}
perf_group_cols = {}
for stat in ['mean', 'min', 'max', 'std']:
    sc_group_cols[stat] = []
    perf_group_cols[stat] = []
    for g in group_names:
        sc_group_cols[stat].extend([f'{stat}_sc_{g}_behavior', f'{stat}_sc_{g}_naive', f'{stat}_sc_{g}_ecp'])
        perf_group_cols[stat].extend([f'{stat}_perf_{g}_behavior', f'{stat}_perf_{g}_naive', f'{stat}_perf_{g}_ecp'])

block_group_cols = []
for g in group_names:
    block_group_cols.extend([f'mean_block_len_{g}_behavior', f'mean_block_len_{g}_naive', f'mean_block_len_{g}_ecp'])

ordered_cols = [
    # Metadata
    'I', 'T', 'K', 'pattern', 'scenario', 'prob', 'num_groups',
] + group_param_cols + [
    
    # BAP-specific optimization metrics
    'gap', 'lagrange', 'lbound', 'iteration', 'time_sp', 'time_rmp', 'time_ip', 'time_total',
    
    # Metrics (behavior, naive, ecp sequentially)
    'reduction_naive',
    'reduction_ecp',
    'objval', 'objval_naive', 'objval_ecp',
    'undercover_behavior', 'undercover_naive', 'undercover_ecp',
    'undercover_norm_behavior', 'undercover_norm_naive', 'undercover_norm_ecp',
    'cons_behavior', 'cons_naive', 'cons_ecp',
    'cons_norm_behavior', 'cons_norm_naive', 'cons_norm_ecp',
    'perf_behavior', 'perf_naive', 'perf_ecp',
    'perf_norm_behavior', 'perf_norm_naive', 'perf_norm_ecp',
    'understaffing_behavior', 'understaffing_naive', 'understaffing_ecp',
    'understaffing_norm_behavior', 'understaffing_norm_naive', 'understaffing_norm_ecp',
    
    # Inequality / Fairness metrics (consistency)
    'spread_sc_behavior', 'spread_sc_naive', 'spread_sc_ecp',
    'load_share_sc_behavior', 'load_share_sc_naive', 'load_share_sc_ecp',
    'gini_sc_behavior', 'gini_sc_naive', 'gini_sc_ecp',
    'disutility_sc_behavior', 'disutility_sc_naive', 'disutility_sc_ecp',
    'top10_sc_behavior', 'top10_sc_naive', 'top10_sc_ecp',

    # Non-group-specific (pooled) descriptive stats for shift changes
    'mean_sc_behavior', 'mean_sc_naive', 'mean_sc_ecp',
] + sc_group_cols['mean'] + [
    'min_sc_behavior', 'min_sc_naive', 'min_sc_ecp',
] + sc_group_cols['min'] + [
    'max_sc_behavior', 'max_sc_naive', 'max_sc_ecp',
] + sc_group_cols['max'] + [
    'std_sc_behavior', 'std_sc_naive', 'std_sc_ecp',
] + sc_group_cols['std'] + [

    # Inequality / Fairness metrics (performance)
    'spread_perf_behavior', 'spread_perf_naive', 'spread_perf_ecp',
    'load_share_perf_behavior', 'load_share_perf_naive', 'load_share_perf_ecp',
    'gini_perf_behavior', 'gini_perf_naive', 'gini_perf_ecp',
    'disutility_perf_behavior', 'disutility_perf_naive', 'disutility_perf_ecp',
    'top10_perf_behavior', 'top10_perf_naive', 'top10_perf_ecp',

    # Non-group-specific (pooled) descriptive stats for performance loss
    'mean_perf_behavior', 'mean_perf_naive', 'mean_perf_ecp',
] + perf_group_cols['mean'] + [
    'min_perf_behavior', 'min_perf_naive', 'min_perf_ecp',
] + perf_group_cols['min'] + [
    'max_perf_behavior', 'max_perf_naive', 'max_perf_ecp',
] + perf_group_cols['max'] + [
    'std_perf_behavior', 'std_perf_naive', 'std_perf_ecp',
] + perf_group_cols['std'] + [

    # Number of shift blocks
    'shift_blocks_behavior', 'shift_blocks_naive', 'shift_blocks_ecp',
    'num_blocks_behavior', 'num_blocks_naive', 'num_blocks_ecp',
    'mean_block_len_behavior', 'mean_block_len_naive', 'mean_block_len_ecp',
] + block_group_cols + [
    'min_block_len_behavior', 'min_block_len_naive', 'min_block_len_ecp',
    'max_block_len_behavior', 'max_block_len_naive', 'max_block_len_ecp',
    'std_block_len_behavior', 'std_block_len_naive', 'std_block_len_ecp',

    # Demand regimes
    'p_end_behavior', 'p_end_naive', 'p_end_ecp', 'b_end_tau_behavior', 'b_end_tau_naive', 'b_end_tau_ecp',
    'l_tail_tau_behavior', 'l_tail_tau_naive', 'l_tail_tau_ecp',
    'p_bar_d_behavior', 'p_bar_d_naive', 'p_bar_d_ecp',
    
    # Lists/Dicts (dropped in Excel, kept in CSV/Pickle)
    'shift_undercover_behavior', 'shift_undercover_naive', 'shift_undercover_ecp',
    'daily_behavior', 'daily_naive', 'daily_ecp',
    'perf_list_behavior', 'perf_list_naive', 'perf_list_ecp',

    # Convergence history (BAP)
    'rmp_obj_hist', 'sp_obj_hist', 'rmp_time_hist', 'sp_time_hist', 'lagrange_hist'
]
# Retain only existing columns and sort the DataFrame
results = results[[c for c in ordered_cols if c in results.columns]]

_stamp = datetime.now().strftime("%d_%m_%Y_%H-%M")
results.to_pickle(f'results/pkl/Results_{_stamp}.pkl')
results.to_csv(f'results/csv/Results_{_stamp}.csv', index=False)


_EXCEL_CELL_LIMIT = 32767
_excel_df = results.copy()
for _col in _excel_df.columns:
    _excel_df[_col] = _excel_df[_col].apply(
        lambda v: str(v)[:_EXCEL_CELL_LIMIT] if len(str(v)) > _EXCEL_CELL_LIMIT else v
    )
_excel_df.to_excel(f'results/xlsx/Results_{_stamp}.xlsx', index=False)

print(results)
print(f"")

print(f"\nTotal execution time: {time.time() - start_time:.2f} seconds")

# Summary
print("\n" + "=" * 80)
print("SUMMARY: CG+bidir Results")
print("=" * 80)
for idx, row in results.iterrows():
    print(f"Scenario {row['scenario']}: obj={row['objval']:.4f}, LB={row['lbound']:.4f}, gap={row['gap']:.4f}%, iter={row['iteration']}, time={row['time_total']:.4f}s")
print("=" * 80)

# Gini Statistics
print("\n" + "=" * 80)
print("GINI COEFFICIENT STATISTICS (Mean +/- Std Dev)")
print("=" * 80)
gini_cols = ['gini_sc_behavior', 'gini_perf_behavior', 'gini_sc_naive', 'gini_perf_naive',
             'disutility_sc_behavior', 'disutility_perf_behavior', 'disutility_sc_naive', 'disutility_perf_naive']
for col in gini_cols:
    if col in results.columns:
        mean_val = results[col].mean()
        std_val = results[col].std()
        print(f"{col:25s}: {mean_val:.4f} +/- {std_val:.4f}")
print("=" * 80)