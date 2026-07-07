from core.cg_behavior import *
from core.cg_naive import column_generation_naive
from core.cg_ecp import column_generation_ecp
from Utils.Plots.plots import *
from Utils.aggundercover import *
from datetime import *
from Utils.demand import *
from core.base_case import get_base_case_groups, get_wd_constraints, LEN_I_RANGE, SCENARIO_RANGE, PATTERN, CHI, K_ECP
from core.solver_base import MAX_ITR, THRESHOLD, TIME_CG_INIT, TIME_CG, OUTPUT_LEN, SCALE
from Utils.metrics import evaluate_inequality, compute_horizon_stability_metrics
import time
import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))
os.makedirs("results/csv", exist_ok=True)
os.makedirs("results/xlsx", exist_ok=True)
os.makedirs("results/pkl", exist_ok=True)


def _worker_total_stats(lst, T_len, n_workers):
    """Non-group-specific (pooled across the whole workforce) mean/min/max/std
    of per-worker totals. Reuses evaluate_inequality's own worker_totals --
    every existing call site discards it via `_` and only keeps
    spread/load_share/gini/disutility/top10, so this is a free by-product,
    not a second aggregation pass."""
    worker_totals, *_ = evaluate_inequality(lst, T_len, n_workers)
    vals = list(worker_totals.values())
    if not vals:
        return 0.0, 0.0, 0.0, 0.0
    arr = np.array(vals, dtype=np.float64)
    return float(arr.mean()), float(arr.min()), float(arr.max()), float(arr.std())


def _perf_loss_worker_stats(ls_x, ls_perf, n_shifts, T_len, n_workers):
    """Same as _worker_total_stats, but for performance-loss totals -- mirrors
    the L_perf = x*(1-p) / per-day-sum-over-shifts transform that
    core/cg_behavior.py applies before its own evaluate_inequality(perf) call."""
    L_perf = [x * (1.0 - p) for x, p in zip(ls_x, ls_perf)]
    daily = [sum(L_perf[i:i + n_shifts]) for i in range(0, len(L_perf), n_shifts)]
    return _worker_total_stats(daily, T_len, n_workers)


# DataFrame
results = pd.DataFrame(columns=['I', 'T', 'K', 'pattern', 'scenario', 'prob', 'epsilon', 'chi', 'gap', 'lagrange', 'objval', 'lbound', 'iteration', 'time_sp', 'time_rmp',
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
        worker_groups = get_base_case_groups(I)
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
        spread_perf_naive, load_share_perf_naive, gini_perf_naive, disutility_perf_naive, top10_perf_naive, shift_blocks_naive) = column_generation_naive(
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
        spread_perf_ecp, load_share_perf_ecp, gini_perf_ecp, disutility_perf_ecp, top10_perf_ecp, shift_blocks_ecp) = column_generation_ecp(
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
        mean_sc_behavior, min_sc_behavior, max_sc_behavior, std_sc_behavior = _worker_total_stats(ls_sc_behavior, len(T), len(I))
        mean_sc_naive, min_sc_naive, max_sc_naive, std_sc_naive = _worker_total_stats(ls_sc_naive, len(T), len(I))
        mean_sc_ecp, min_sc_ecp, max_sc_ecp, std_sc_ecp = _worker_total_stats(ls_sc_ecp, len(T), len(I))
        mean_perf_behavior, min_perf_behavior, max_perf_behavior, std_perf_behavior = _perf_loss_worker_stats(
            ls_x_behavior, ls_perf_behavior, len(K), len(T), len(I))
        mean_perf_naive, min_perf_naive, max_perf_naive, std_perf_naive = _perf_loss_worker_stats(
            ls_x_naive, ls_perf_naive, len(K), len(T), len(I))
        mean_perf_ecp, min_perf_ecp, max_perf_ecp, std_perf_ecp = _perf_loss_worker_stats(
            ls_x_ecp, ls_perf_ecp, len(K), len(T), len(I))

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
        horizon_stats_behavior = compute_horizon_stability_metrics(ls_p_behavior, len(I), len(T), tau=0.9, k=7)
        horizon_stats_naive = compute_horizon_stability_metrics(ls_perf_naive, len(I), len(T), tau=0.9, k=7)
        horizon_stats_ecp = compute_horizon_stability_metrics(ls_perf_ecp, len(I), len(T), tau=0.9, k=7)

        # Data frame -- every metric that exists for all three paradigms is
        # grouped as a behavior/naive/ecp triple, in the same order as
        # ordered_cols below (which just reindexes this, so the two should
        # never drift apart).
        result = pd.DataFrame([{
                        # Metadata
                        'I': len(I),
                        'T': len(T),
                        'K': len(K),
                        'pattern': PATTERN,
                        'scenario': scenario,
                        'prob': prob,

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

                        # Non-group-specific (pooled) descriptive stats for performance loss
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
                    }])

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
ordered_cols = [
    # Metadata
    'I', 'T', 'K', 'pattern', 'scenario', 'prob',
    
    # BAP-specific optimization metrics
    'gap', 'lagrange', 'lbound', 'iteration', 'time_sp', 'time_rmp', 'time_ip', 'time_total',
    
    # Metrics (behavior, naive, ecp sequentially)
    'reduction_naive',
    'reduction_ecp',
    'p_end_behavior', 'p_end_naive', 'p_end_ecp', 'b_end_tau_behavior', 'b_end_tau_naive', 'b_end_tau_ecp',
    'l_tail_tau_behavior', 'l_tail_tau_naive', 'l_tail_tau_ecp',
    'p_bar_d_behavior', 'p_bar_d_naive', 'p_bar_d_ecp',
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
    'min_sc_behavior', 'min_sc_naive', 'min_sc_ecp',
    'max_sc_behavior', 'max_sc_naive', 'max_sc_ecp',
    'std_sc_behavior', 'std_sc_naive', 'std_sc_ecp',

    # Inequality / Fairness metrics (performance)
    'spread_perf_behavior', 'spread_perf_naive', 'spread_perf_ecp',
    'load_share_perf_behavior', 'load_share_perf_naive', 'load_share_perf_ecp',
    'gini_perf_behavior', 'gini_perf_naive', 'gini_perf_ecp',
    'disutility_perf_behavior', 'disutility_perf_naive', 'disutility_perf_ecp',
    'top10_perf_behavior', 'top10_perf_naive', 'top10_perf_ecp',

    # Non-group-specific (pooled) descriptive stats for performance loss
    'mean_perf_behavior', 'mean_perf_naive', 'mean_perf_ecp',
    'min_perf_behavior', 'min_perf_naive', 'min_perf_ecp',
    'max_perf_behavior', 'max_perf_naive', 'max_perf_ecp',
    'std_perf_behavior', 'std_perf_naive', 'std_perf_ecp',

    # Number of shift blocks
    'shift_blocks_behavior', 'shift_blocks_naive', 'shift_blocks_ecp',
    'num_blocks_behavior', 'num_blocks_naive', 'num_blocks_ecp',
    'mean_block_len_behavior', 'mean_block_len_naive', 'mean_block_len_ecp',
    'min_block_len_behavior', 'min_block_len_naive', 'min_block_len_ecp',
    'max_block_len_behavior', 'max_block_len_naive', 'max_block_len_ecp',
    'std_block_len_behavior', 'std_block_len_naive', 'std_block_len_ecp',
    
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