"""
Heterogeneity Robustness Analysis Loop

Dimensions of Robustness:
1. Performance Parameters (epsilon, chi)
2. Workforce Size (N)
3. Horizon Length (T)
4. Heterogeneity Composition
"""

import os
import time
import pandas as pd
import numpy as np
from datetime import datetime

# Import definitions from your existing modules
from Utils.setup import Min_WD_i, Max_WD_i
from cg_behavior import column_generation_behavior
from cg_naive import column_generation_naive
from Utils.aggundercover import *
from Utils.demand import *
from Utils.gcutil import generate_dict_from_excel
from worker_groups import create_groups_from_fractions, create_homogeneous_group
from Utils.metrics import calculate_group_metrics
from loop_heterogeneity_analysis import save_detailed_stats_csv

# ============================================================================
# EXPERIMENT CONFIGURATIONS
# ============================================================================

ROBUSTNESS_SCENARIOS = {
    # --- DIMENSION 1: Performance Parameters ---
    # Baseline comparison (0.06, 3) is covered in loop_heterogeneity_analysis.py
    'dim1_mild_homo': {
        'name': 'Dim 1: Mild (Homogeneous)',
        'team': 'homogeneous',
        'fractions': None,
        'group_params': [(0.04, 2)],
        'n_workers': 100,
        'n_days': 28,
    },
    'dim1_mild_hetero': {
        'name': 'Dim 1: Mild (Heterogeneous)',
        'team': 'mixed',
        'fractions': "1/3,1/3,1/3",
        'group_params': [(0.02, 1), (0.04, 2), (0.06, 3)],
        'n_workers': 100,
        'n_days': 28,
    },
    'dim1_restrictive_homo': {
        'name': 'Dim 1: Restrictive (Homogeneous)',
        'team': 'homogeneous',
        'fractions': None,
        'group_params': [(0.08, 4)],
        'n_workers': 100,
        'n_days': 28,
    },
    'dim1_restrictive_hetero': {
        'name': 'Dim 1: Restrictive (Heterogeneous)',
        'team': 'mixed',
        'fractions': "1/3,1/3,1/3",
        'group_params': [(0.06, 3), (0.08, 4), (0.10, 5)],
        'n_workers': 100,
        'n_days': 28,
    },
    'dim1_no_behavior_homo': {
        'name': 'Dim 1: No-Behavior (Homogeneous)',
        'team': 'homogeneous',
        'fractions': None,
        'group_params': [(0.00, 0)],
        'n_workers': 100,
        'n_days': 28,
    },

    # --- DIMENSION 2: Workforce Size ---
    'dim2_small_N80': {
        'name': 'Dim 2: Small Workforce (N=80, Heterogeneous)',
        'team': 'mixed',
        'fractions': "1/3,1/3,1/3",
        'group_params': [(0.04, 2), (0.06, 3), (0.08, 4)],
        'n_workers': 80,
        'n_days': 28,
    },
    'dim2_large_N120': {
        'name': 'Dim 2: Large Workforce (N=120, Heterogeneous)',
        'team': 'mixed',
        'fractions': "1/3,1/3,1/3",
        'group_params': [(0.04, 2), (0.06, 3), (0.08, 4)],
        'n_workers': 120,
        'n_days': 28,
    },

    # --- DIMENSION 3: Horizon Length ---
    'dim3_short_T14': {
        'name': 'Dim 3: Short Horizon (T=14, Heterogeneous)',
        'team': 'mixed',
        'fractions': "1/3,1/3,1/3",
        'group_params': [(0.04, 2), (0.06, 3), (0.08, 4)],
        'n_workers': 100,
        'n_days': 14,
    },
    'dim3_mid_T21': {
        'name': 'Dim 3: Mid Horizon (T=21, Heterogeneous)',
        'team': 'mixed',
        'fractions': "1/3,1/3,1/3",
        'group_params': [(0.04, 2), (0.06, 3), (0.08, 4)],
        'n_workers': 100,
        'n_days': 21,
    },

    # --- DIMENSION 4: Alternative Heterogeneity Compositions ---
    'dim4_extremes_heavy': {
        'name': 'Dim 4: Extremes-Heavy (40/20/40)',
        'team': 'mixed',
        'fractions': "4/10,2/10,4/10",
        'group_params': [(0.04, 2), (0.06, 3), (0.08, 4)],
        'n_workers': 100,
        'n_days': 28,
    },
    'dim4_average_heavy': {
        'name': 'Dim 4: Average-Heavy (10/80/10)',
        'team': 'mixed',
        'fractions': "1/10,8/10,1/10",
        'group_params': [(0.04, 2), (0.06, 3), (0.08, 4)],
        'n_workers': 100,
        'n_days': 28,
    },
}

# ============================================================================
# RUN PARAMETERS
# ============================================================================
time_cg, time_cg_init = 7200, 10
max_itr, threshold = 2000, 6e-5
N_SEEDS = 25

def run_single_robustness_scenario(scenario_key, scenario_config, seeds=range(1, 26), run_naive=True):
    """Run a single robustness scenario across multiple seeds with dynamic dimensions."""
    print("\n" + "="*80)
    print(f"ROBUSTNESS SCENARIO: {scenario_config['name']}")
    print("="*80)
    
    results = []
    
    n_days = scenario_config.get('n_days', 28)
    n_workers = scenario_config.get('n_workers', 100)
    
    T = list(range(1, n_days + 1))
    K = [1, 2, 3]
    I = list(range(1, n_workers + 1))
    
    # Base dataset padding
    data = pd.DataFrame({
        'I': I + [np.nan] * (max(len(I), len(T), len(K)) - len(I)),
        'T': T + [np.nan] * (max(len(I), len(T), len(K)) - len(T)),
        'K': K + [np.nan] * (max(len(I), len(T), len(K)) - len(K))
    })
    
    # Create worker groups
    if scenario_config['team'] == 'mixed':
        worker_groups = create_groups_from_fractions(
            I, scenario_config['fractions'], scenario_config['group_params']
        )
    else:
        eps, chi = scenario_config['group_params'][0]
        worker_groups = create_homogeneous_group(I, eps, chi)
    
    print(f"Worker groups: {[(g.name, len(g.worker_ids), g.epsilon, g.chi) for g in worker_groups.values()]}")
    
    for seed in seeds:
        print(f"\n--- Seed {seed}/{max(seeds)} ---")
        
        # Pull generated demand dictionary
        try:
            full_demand_dict = generate_dict_from_excel(
                'data/demand_data.xlsx', n_workers, 'Medium', scenario=seed
            )
            # Filter demand dictionary for given T horizon
            demand_dict = {k: v for k, v in full_demand_dict.items() if k[0] <= n_days}
        except Exception as e:
            print(f"Failed to pull demand data for N={n_workers}, Seed={seed}. Please ensure demand_data.xlsx contains entries for I={n_workers}! Error: {e}")
            continue
            
        eps = scenario_config['group_params'][0][0]
        chi = scenario_config['group_params'][0][1]
        
        # ===== BSV (Behavior Model) =====
        t0 = time.time()
        try:
            (undercoverage_bsv, understaffing_bsv, perfloss_bsv, 
             consistency_bsv, consistency_norm_bsv, undercoverage_norm_bsv, 
             understaffing_norm_bsv, perfloss_norm_bsv, obj_bsv, 
             lb_bsv, itr_bsv, lagrange_bsv, gap_bsv, time_sp, time_rmp, time_ip, 
             ls_p_bsv, ls_sc_bsv, ls_perf_bsv, ls_x_bsv,
             ls_r_bsv, undercover_shift_bsv, ineq_sc_bsv, 
             spread_sc_bsv, load_sc_bsv, gini_sc_bsv, 
             ineq_perf_bsv, spread_perf_bsv, load_perf_bsv, 
             gini_perf_bsv, blocks_bsv) = column_generation_behavior(
                data, demand_dict, eps, Min_WD_i, Max_WD_i, time_cg_init, max_itr, 
                100, chi, threshold, time_cg, I, T, K, 1.0, 
                sp_solver='labeling_bidir', worker_groups=worker_groups, 
                save_lp=False, use_heuristic_start=False
            )
            time_bsv = time.time() - t0
            
            # Calculate detailed group metrics
            group_metrics, fairness = calculate_group_metrics(
                ls_sc_bsv, ls_perf_bsv, worker_groups, len(T), len(K)
            )
            
            result = {
                'scenario': scenario_key,
                'scenario_name': scenario_config['name'],
                'seed': seed,
                'model': 'BSV',
                'undercoverage': undercoverage_bsv,
                'undercover_norm': undercoverage_norm_bsv,
                'understaffing': understaffing_bsv,
                'understaffing_norm': understaffing_norm_bsv,
                'perf_loss_total': perfloss_bsv,
                'perf_norm': perfloss_norm_bsv,
                'shift_changes_total': consistency_bsv,
                'cons_norm': consistency_norm_bsv,
                'spread_sc': spread_sc_bsv,
                'load_share_sc': load_sc_bsv,
                'gini_sc': gini_sc_bsv,
                'top10_sc': ineq_sc_bsv,
                'objective': obj_bsv,
                'lb': lb_bsv,
                'gap': gap_bsv,
                'iterations': itr_bsv,
                'time': time_bsv,
                'gini_perf_loss': fairness['gini_perf_loss'],
                'gini_shift_changes': fairness['gini_shift_changes'],
                'cv_perf_loss': fairness['cv_perf_loss'],
                'ratio_90_10_perf': fairness['ratio_90_10_perf'],
                'group_metrics': group_metrics,
            }
            results.append(result)
            print(f"  BSV: obj={obj_bsv:.2f}, perfloss={perfloss_bsv:.2f}, sc={consistency_bsv:.0f}")
            
        except Exception as e:
            print(f"  BSV ERROR: {e}")
            continue
            
        # ===== MLSV (Naive Model) =====
        if run_naive:
            try:
                (undercoverage_mlsv, understaffing_mlsv, perfloss_mlsv, 
                 consistency_mlsv, consistency_norm_mlsv, undercoverage_norm_mlsv, 
                 understaffing_norm_mlsv, perfloss_norm_mlsv, obj_mlsv, 
                 ls_p_mlsv, ls_sc_mlsv, ls_perf_mlsv, ls_x_mlsv,
                 ls_r_mlsv, undercover_shift_mlsv, ineq_sc_mlsv, 
                 spread_sc_mlsv, load_sc_mlsv, gini_sc_mlsv, 
                 ineq_perf_mlsv, spread_perf_mlsv, load_perf_mlsv, 
                 gini_perf_mlsv, blocks_mlsv) = column_generation_naive(
                    data, demand_dict, 0, Min_WD_i, Max_WD_i, time_cg_init, max_itr, 
                    100, chi, threshold, time_cg, I, T, K, eps, 1.0, 
                    sp_solver='labeling_bidir'
                )
                
                group_metrics_mlsv, fairness_mlsv = calculate_group_metrics(
                    ls_sc_mlsv, ls_perf_mlsv, worker_groups, len(T), len(K)
                )
                
                result_mlsv = {
                    'scenario': scenario_key,
                    'scenario_name': scenario_config['name'],
                    'seed': seed,
                    'model': 'MLSV',
                    'undercoverage': undercoverage_mlsv,
                    'undercover_norm': undercoverage_norm_mlsv,
                    'understaffing': understaffing_mlsv,
                    'understaffing_norm': understaffing_norm_mlsv,
                    'perf_loss_total': perfloss_mlsv,
                    'perf_norm': perfloss_norm_mlsv,
                    'shift_changes_total': consistency_mlsv,
                    'cons_norm': consistency_norm_mlsv,
                    'spread_sc': spread_sc_mlsv,
                    'load_share_sc': load_sc_mlsv,
                    'gini_sc': gini_sc_mlsv,
                    'top10_sc': ineq_sc_mlsv,
                    'objective': obj_mlsv,
                    'lb': 0, 'gap': 0, 'iterations': 0, 'time': 0,
                    'gini_perf_loss': fairness_mlsv['gini_perf_loss'],
                    'gini_shift_changes': fairness_mlsv['gini_shift_changes'],
                    'cv_perf_loss': fairness_mlsv['cv_perf_loss'],
                    'ratio_90_10_perf': fairness_mlsv['ratio_90_10_perf'],
                    'group_metrics': group_metrics_mlsv,
                }
                results.append(result_mlsv)
                print(f"  MLSV: obj={obj_mlsv:.2f}, perfloss={perfloss_mlsv:.2f}, sc={consistency_mlsv:.0f}")
                
            except Exception as e:
                print(f"  MLSV ERROR: {e}")
                
    return results

if __name__ == "__main__":
    start_time = time.time()
    
    all_results = {}
    
    # Make sure output directory exists
    os.makedirs('results/robustness', exist_ok=True)
    
    for scenario_key, config in ROBUSTNESS_SCENARIOS.items():
        # Execute scenario
        res = run_single_robustness_scenario(scenario_key, config, seeds=range(1, N_SEEDS + 1), run_naive=True)
        all_results[scenario_key] = res
        
        # Save exact results per scenario
        if res:
            df = pd.DataFrame(res)
            # Remove objects that cannot be saved to Excel (like dicts) before Excel dump
            df_safe = df.drop(columns=['group_metrics', 'top10_sc'], errors='ignore')
            df_safe.to_excel(f'results/robustness/analysis_{scenario_key}_{datetime.now().strftime("%d_%m_%Y_%H-%M")}.xlsx', index=False)
            
    # Output the exact detailed stats tables the same way loop_heterogeneity_analysis.py does
    print("\nGenerating Detailed Statistics Summaries...")
    save_detailed_stats_csv(all_results)
    
    print(f"\nAll Robustness Execution complete! Time: {time.time() - start_time:.2f} seconds")
    print("Detailed stats files and complete trace results have been written to 'results/robustness/' / 'results/'.")
