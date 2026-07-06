from core.cg_behavior import *
from core.cg_naive import column_generation_naive
from core.cg_ecp import column_generation_ecp
from Utils.Plots.plots import *
from Utils.aggundercover import *
from datetime import *
from Utils.demand import *
from core.base_case import get_base_case_groups, get_wd_constraints, LEN_I_RANGE, SCENARIO_RANGE, PATTERN, CHI
from core.solver_base import MAX_ITR, THRESHOLD, TIME_CG_INIT, TIME_CG, OUTPUT_LEN, SCALE
from Utils.metrics import evaluate_inequality
import time
import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))
os.makedirs("results/csv", exist_ok=True)
os.makedirs("results/xlsx", exist_ok=True)
os.makedirs("results/pkl", exist_ok=True)

# DataFrame
results = pd.DataFrame(columns=['I', 'T', 'K', 'pattern', 'scenario', 'prob', 'epsilon', 'chi', 'gap', 'lagrange', 'objval', 'lbound', 'iteration', 'time_sp', 'time_rmp',
                                'time_ip', 'undercover_behavior', 'undercover_norm_behavior', 'cons_behavior', 'cons_norm_behavior', 'perf_behavior',
                                'perf_norm_behavior', 'understaffing_behavior', 'understaffing_norm_behavior', 'undercover_naive', 'undercover_norm_naive', 'cons_naive',
                                'cons_norm_naive', 'perf_naive', 'perf_norm_naive', 'understaffing_naive', 'understaffing_norm_naive', 'shift_undercover_naive',
                                'shift_undercover_behavior', 'perf_list_behavior', 'perf_list_naive', 'cons_list_behavior', 'cons_list_naive', 'p_list_behavior', 'p_list_naive',
                                'x_list_behavior', 'x_list_naive', 'r_list_behavior', 'r_list_naive', 'daily_undercover_behavior', 'daily_undercover_naive', 'results_ineq_sc_behavior', 'results_ineq_sc_naive', 'spread_sc_behavior',
                                'spread_sc_naive', 'load_share_sc_behavior', 'load_share_sc_naive', 'gini_sc_behavior', 'gini_sc_naive', 'results_ineq_perf_behavior',
                                'results_ineq_perf_naive', 'spread_perf_behavior', 'spread_perf_naive', 'load_share_perf_behavior', 'load_share_perf_naive', 'gini_perf_behavior',
                                'gini_perf_naive', 'shift_blocks_behavior', 'shift_blocks_naive'])

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
         ls_r_behavior, undercoverage_per_shift_behavior, results_ineq_sc_behavior, spread_sc_behavior,
         load_share_sc_behavior, gini_sc_behavior, results_ineq_perf_behavior,
         spread_perf_behavior, load_share_perf_behavior, gini_perf_behavior,
         shift_blocks_behavior, rmp_obj_hist_behavior, sp_obj_hist_behavior,
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
        ls_r_naive, undercoverage_per_shift_naive, results_ineq_sc_naive, spread_sc_naive,
        load_share_sc_naive, gini_sc_naive, results_ineq_perf_naive,
        spread_perf_naive, load_share_perf_naive, gini_perf_naive, shift_blocks_naive) = column_generation_naive(
            data, demand_dict, 0, Min_WD_i, Max_WD_i, time_cg_init, max_itr, 100, CHI,
            threshold, time_cg, I, T, K, prob, sp_solver='labeling_bidir',
            worker_groups=worker_groups, use_null_column=True)

        # ECP: identical to NPP (100% performance in the labeling, same nonlinear ex-post
        # via worker_groups), but with the additional rolling shift-change cap k<=2 per
        # 7-day window enforced directly in the forward labeling.
        print('Doing ECP with labeling (k<=2)')
        (
        undercoverage_ecp, understaffing_ecp, perfloss_ecp, consistency_ecp, consistency_norm_ecp,
        undercoverage_norm_ecp, understaffing_norm_ecp,
        perfloss_norm_ecp, final_obj_ecp, ls_p_ecp, ls_sc_ecp, ls_perf_ecp, ls_x_ecp,
        ls_r_ecp, undercoverage_per_shift_ecp, results_ineq_sc_ecp, spread_sc_ecp,
        load_share_sc_ecp, gini_sc_ecp, results_ineq_perf_ecp,
        spread_perf_ecp, load_share_perf_ecp, gini_perf_ecp, shift_blocks_ecp) = column_generation_ecp(
            data, demand_dict, 0, Min_WD_i, Max_WD_i, time_cg_init, max_itr, 100, CHI,
            threshold, time_cg, I, T, K, prob, k=2, sp_solver='labeling_bidir',
            worker_groups=worker_groups, use_null_column=True)

        shift_undercover_behavior = create_dict_from_list(undercoverage_per_shift_behavior, len(T), len(K))
        shift_undercover_naive = create_dict_from_list(undercoverage_per_shift_naive, len(T), len(K))
        shift_undercover_ecp = create_dict_from_list(undercoverage_per_shift_ecp, len(T), len(K))

        daily_undercover_naive = dict_reducer(shift_undercover_naive)
        daily_undercover_behavior = dict_reducer(shift_undercover_behavior)
        daily_undercover_ecp = dict_reducer(shift_undercover_ecp)

        # Data frame
        result = pd.DataFrame([{
                        'I': len(I),
                        'T': len(T),
                        'K': len(K),
                        'pattern': PATTERN,
                        'scenario': scenario,
                        'prob': prob,
                        'gap': round(gap, 3),
                        'lagrange': round(lagrangeB, 3),
                        'objval': round(final_obj_behavior, 3),
                        'lbound': round(final_lb, 3),
                        'iteration': itr,
                        'time_sp': round(time_sps, 3),
                        'time_rmp': round(time_rmp, 3),
                        'time_ip': round(time_ip, 3),
                        'time_total': round(time_bidir, 3),
                        'undercover_behavior': undercoverage_behavior,
                        'undercover_norm_behavior': undercoverage_norm_behavior,
                        'cons_behavior': consistency_behavior,
                        'cons_norm_behavior': consistency_norm_behavior,
                        'perf_behavior': perfloss_behavior,
                        'perf_norm_behavior': perfloss_norm_behavior,
                        'understaffing_behavior': understaffing_behavior,
                        'understaffing_norm_behavior': understaffing_norm_behavior,
                        'objval_naive': final_obj_naive,
                        'undercover_naive': undercoverage_naive,
                        'undercover_norm_naive': undercoverage_norm_naive,
                        'cons_naive': consistency_naive,
                        'cons_norm_naive': consistency_norm_naive,
                        'perf_naive': perfloss_naive,
                        'perf_norm_naive': perfloss_norm_naive,
                        'understaffing_naive': understaffing_naive,
                        'understaffing_norm_naive': understaffing_norm_naive,
                        'shift_undercover_naive': shift_undercover_naive,
                        'shift_undercover_behavior': shift_undercover_behavior,
                        'perf_list_behavior': ls_perf_behavior,
                        'perf_list_naive': ls_perf_naive,
                        'cons_list_behavior': ls_sc_behavior,
                        'cons_list_naive': ls_sc_naive,
                        'x_list_behavior': ls_x_behavior,
                        'x_list_naive': ls_x_naive,
                        'r_list_behavior': ls_r_behavior,
                        'r_list_naive': ls_r_naive,
                        'p_list_behavior': ls_p_behavior,
                        'p_list_naive': ls_p_naive,
                        'daily_behavior': daily_undercover_behavior,
                        'daily_naive': daily_undercover_naive,
                        'results_ineq_sc_behavior': results_ineq_sc_behavior,
                        'results_ineq_sc_naive': results_ineq_sc_naive,
                        'spread_sc_behavior': spread_sc_behavior,
                        'spread_sc_naive': spread_sc_naive,
                        'load_share_sc_behavior': load_share_sc_behavior,
                        'load_share_sc_naive': load_share_sc_naive,
                        'gini_sc_behavior': gini_sc_behavior,
                        'gini_sc_naive': gini_sc_naive,
                        'results_ineq_perf_behavior': results_ineq_perf_behavior,
                        'results_ineq_perf_naive': results_ineq_perf_naive,
                        'spread_perf_behavior': spread_perf_behavior,
                        'spread_perf_naive': spread_perf_naive,
                        'load_share_perf_behavior': load_share_perf_behavior,
                        'load_share_perf_naive': load_share_perf_naive,
                        'gini_perf_behavior': gini_perf_behavior,
                        'gini_perf_naive': gini_perf_naive,
                        'shift_blocks_behavior': shift_blocks_behavior,
                        'rmp_obj_hist_behavior': rmp_obj_hist_behavior,
                        'sp_obj_hist_behavior': sp_obj_hist_behavior,
                        'rmp_time_hist_behavior': rmp_time_hist_behavior,
                        'sp_time_hist_behavior': sp_time_hist_behavior,
                        'lagrange_hist_behavior': lagrange_hist_behavior,
                        'shift_blocks_naive': shift_blocks_naive,
                        'undercover_ecp': undercoverage_ecp,
                        'undercover_norm_ecp': undercoverage_norm_ecp,
                        'cons_ecp': consistency_ecp,
                        'cons_norm_ecp': consistency_norm_ecp,
                        'perf_ecp': perfloss_ecp,
                        'perf_norm_ecp': perfloss_norm_ecp,
                        'understaffing_ecp': understaffing_ecp,
                        'understaffing_norm_ecp': understaffing_norm_ecp,
                        'objval_ecp': final_obj_ecp,
                        'shift_undercover_ecp': shift_undercover_ecp,
                        'perf_list_ecp': ls_perf_ecp,
                        'cons_list_ecp': ls_sc_ecp,
                        'x_list_ecp': ls_x_ecp,
                        'r_list_ecp': ls_r_ecp,
                        'p_list_ecp': ls_p_ecp,
                        'daily_ecp': daily_undercover_ecp,
                        'results_ineq_sc_ecp': results_ineq_sc_ecp,
                        'spread_sc_ecp': spread_sc_ecp,
                        'load_share_sc_ecp': load_share_sc_ecp,
                        'gini_sc_ecp': gini_sc_ecp,
                        'results_ineq_perf_ecp': results_ineq_perf_ecp,
                        'spread_perf_ecp': spread_perf_ecp,
                        'load_share_perf_ecp': load_share_perf_ecp,
                        'gini_perf_ecp': gini_perf_ecp,
                        'shift_blocks_ecp': shift_blocks_ecp,
                    }])

        results = pd.concat([results, result], ignore_index=True)

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
    'results_ineq_sc_behavior', 'results_ineq_sc_naive', 'results_ineq_sc_ecp',
    'spread_sc_behavior', 'spread_sc_naive', 'spread_sc_ecp',
    'load_share_sc_behavior', 'load_share_sc_naive', 'load_share_sc_ecp',
    'gini_sc_behavior', 'gini_sc_naive', 'gini_sc_ecp',
    
    # Inequality / Fairness metrics (performance)
    'results_ineq_perf_behavior', 'results_ineq_perf_naive', 'results_ineq_perf_ecp',
    'spread_perf_behavior', 'spread_perf_naive', 'spread_perf_ecp',
    'load_share_perf_behavior', 'load_share_perf_naive', 'load_share_perf_ecp',
    'gini_perf_behavior', 'gini_perf_naive', 'gini_perf_ecp',
    
    # Number of shift blocks
    'shift_blocks_behavior', 'shift_blocks_naive', 'shift_blocks_ecp',
    
    # Lists/Dicts (dropped in Excel, kept in CSV/Pickle)
    'shift_undercover_behavior', 'shift_undercover_naive', 'shift_undercover_ecp',
    'daily_behavior', 'daily_naive', 'daily_ecp',
    'perf_list_behavior', 'perf_list_naive', 'perf_list_ecp',
    'cons_list_behavior', 'cons_list_naive', 'cons_list_ecp',
    'x_list_behavior', 'x_list_naive', 'x_list_ecp',
    'r_list_behavior', 'r_list_naive', 'r_list_ecp',
    'p_list_behavior', 'p_list_naive', 'p_list_ecp',
    
    # Convergence history (BAP)
    'rmp_obj_hist_behavior', 'sp_obj_hist_behavior', 'rmp_time_hist_behavior', 'sp_time_hist_behavior', 'lagrange_hist_behavior'
]
# Retain only existing columns and sort the DataFrame
results = results[[c for c in ordered_cols if c in results.columns]]

_stamp = datetime.now().strftime("%d_%m_%Y_%H-%M")
results.to_pickle(f'results/pkl/Results_{_stamp}.pkl')
results.to_csv(f'results/csv/Results_{_stamp}.csv', index=False)

_EXCEL_CELL_LIMIT = 32767
_excel_df = results.copy()
_dropped = []
for _col in list(_excel_df.columns):
    _maxlen = _excel_df[_col].apply(lambda v: len(str(v))).max()
    if _maxlen is not None and _maxlen > _EXCEL_CELL_LIMIT:
        _dropped.append((_col, int(_maxlen)))
        _excel_df = _excel_df.drop(columns=[_col])
_excel_df.to_excel(f'results/xlsx/Results_{_stamp}.xlsx', index=False)
if _dropped:
    print(f"\n[Excel] Dropped {len(_dropped)} too long list columns from the .xlsx "
          f"(fully preserved in .pkl/.csv): {[c for c, _ in _dropped]}")

print(results)
print(f"")

print(f"\nTotal execution time: {time.time() - start_time:.2f} seconds")

# Summary
print("\n" + "=" * 80)
print("SUMMARY: CG+bidir Results")
print("=" * 80)
for idx, row in results.iterrows():
    print(f"Scenario {row['scenario']}: obj={row['objval']:.2f}, LB={row['lbound']:.2f}, gap={row['gap']:.2f}%, iter={row['iteration']}, time={row['time_total']:.1f}s")
print("=" * 80)

# Gini Statistics
print("\n" + "=" * 80)
print("GINI COEFFICIENT STATISTICS (Mean +/- Std Dev)")
print("=" * 80)
gini_cols = ['gini_sc_behavior', 'gini_perf_behavior', 'gini_sc_naive', 'gini_perf_naive']
for col in gini_cols:
    if col in results.columns:
        mean_val = results[col].mean()
        std_val = results[col].std()
        print(f"{col:25s}: {mean_val:.4f} +/- {std_val:.4f}")
print("=" * 80)