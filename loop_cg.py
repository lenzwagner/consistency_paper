from Utils.setup import Min_WD_i, Max_WD_i
from cg_behavior import *
from cg_naive import column_generation_naive
from Utils.Plots.plots import *
from Utils.aggundercover import *
from datetime import *
from Utils.demand import *
from worker_groups import create_groups_from_fractions, create_homogeneous_group
from Utils.metrics import evaluate_inequality
import time
import os
os.makedirs("results", exist_ok=True)

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
time_cg, time_cg_init = 7200, 5
max_itr, threshold = 200, 6e-5

start_time = time.time()

# ========== HETEROGENEOUS WORKER GROUPS CONFIGURATION ==========
# Set to True to use heterogeneous worker groups, False for homogeneous
use_heterogeneous = False

# Fraction string defining group proportions (must sum to 1)
group_fractions = "1/3,1/3,1/3"

# Parameters for each group: (epsilon, chi)
# Must have same number of tuples as fractions
group_params = [
    (0.04, 2),
    (0.06, 3),
    (0.08, 4),
]
# ================================================================

# Loop
for epsilon in [0.06]:
    for chi in [3]:
        for len_I in [100]:
            for pattern in ['Medium']:
                for scenario in range(1, 6):
                    prob = {'Medium': 1.0, 'High': 1.1, 'Low': 0.9}.get(pattern)

                    # Data
                    T = list(range(1, 29))
                    I = list(range(1, len_I + 1))
                    K = [1, 2, 3]

                    data = pd.DataFrame({
                        'I': I + [np.nan] * (max(len(I), len(T), len(K)) - len(I)),
                        'T': T + [np.nan] * (max(len(I), len(T), len(K)) - len(T)),
                        'K': K + [np.nan] * (max(len(I), len(T), len(K)) - len(K))
                    })

                    demand_dict = generate_dict_from_excel('data/demand_data.xlsx', len(I), pattern, scenario=scenario)

                    # Create worker groups based on configuration
                    if use_heterogeneous:
                        worker_groups = create_groups_from_fractions(I, group_fractions, group_params)
                        print(f"Using heterogeneous groups: {[(g.name, len(g.worker_ids), g.epsilon, g.chi) for g in worker_groups.values()]}")
                    else:
                        worker_groups = create_homogeneous_group(I, epsilon, chi)
                        print(f"Using homogeneous group: epsilon={epsilon}, chi={chi}")

                    print(f"")
                    print(f"Iteration: Eps: {epsilon} - Chi: {chi} - I: {len(I)} - Pattern: {pattern} - K: {scenario}")
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
                     shift_blocks_behavior) = column_generation_behavior(
                        data, demand_dict, epsilon, Min_WD_i, Max_WD_i, time_cg_init, max_itr, 100, chi,
                        threshold, time_cg, I, T, K, prob, sp_solver='labeling_bidir',
                        worker_groups=worker_groups, save_lp=True, use_heuristic_start=False
                    )
                    time_bidir = time.time() - t0_bidir
                    print(f'  --> CG+bidir: obj={final_obj_behavior:.2f}, iter={itr}, gap={gap:.2f}%, time={time_bidir:.1f}s')

                    # Naive (with bidir solver)
                    print('Doing naive with labeling_bidir')
                    (
                    undercoverage_naive, understaffing_naive, perfloss_naive, consistency_naive, consistency_norm_naive,
                    undercoverage_norm_naive, understaffing_norm_naive,
                    perfloss_norm_naive, final_obj_naive, ls_p_naive, ls_sc_naive, ls_perf_naive, ls_x_naive,
                    ls_r_naive, undercoverage_per_shift_naive, results_ineq_sc_naive, spread_sc_naive,
                    load_share_sc_naive, gini_sc_naive, results_ineq_perf_naive,
                    spread_perf_naive, load_share_perf_naive, gini_perf_naive, shift_blocks_naive) = column_generation_naive(data, demand_dict, 0, Min_WD_i, Max_WD_i, time_cg_init, max_itr, 100, chi,
                                                threshold, time_cg, I, T, K, epsilon, prob, sp_solver='labeling_bidir')


                    shift_undercover_behavior = create_dict_from_list(undercoverage_per_shift_behavior, len(T), len(K))
                    shift_undercover_naive = create_dict_from_list(undercoverage_per_shift_naive, len(T), len(K))


                    daily_undercover_naive = dict_reducer(shift_undercover_naive)
                    daily_undercover_behavior = dict_reducer(shift_undercover_behavior)


                    # Data frame
                    result = pd.DataFrame([{
                        'I': len(I),
                        'T': len(T),
                        'K': len(K),
                        'pattern': pattern,
                        'scenario': scenario,
                        'prob': prob,
                        'epsilon': epsilon,
                        'chi': chi,
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
                        'shift_blocks_naive': shift_blocks_naive,
                    }])

                    results = pd.concat([results, result], ignore_index=True)

results.to_excel(f'results/Results_{datetime.now().strftime("%d_%m_%Y_%H-%M")}.xlsx', index=False)

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