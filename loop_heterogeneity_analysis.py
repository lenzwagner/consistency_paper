"""
Heterogeneity Analysis Loop

4 Hauptanalysen:
1. Baseline Comparison: Homogen vs. Heterogen
2. Worker-Type Specific Impact: Performance/Shift Changes per Typ
3. Fairness Analysis: Gini-Koeffizient
4. Sensitivity Analysis: Variation of Heterogeneity Levels
"""

from Utils.setup import Min_WD_i, Max_WD_i
from cg_behavior import *
from cg_naive import column_generation_naive
from Utils.Plots.plots import *
from Utils.aggundercover import *
from datetime import *
from Utils.demand import *
from worker_groups import create_groups_from_fractions, create_homogeneous_group
import time
from scipy import stats
import numpy as np

# ============================================================================
# EXPERIMENT CONFIGURATIONS
# ============================================================================

SCENARIOS = {
    # Analyse 1 & 2: Baseline vs Heterogen
    'homogen': {
        'name': 'Homogen (Baseline)',
        'team': 'homogeneous',
        'fractions': None,
        'group_params': [(0.06, 3)],
        'n_workers': 100,
    },
    'heterogen_3cluster': {
        'name': 'Heterogen (3 Cluster)',
        'description': '33% Resilient, 34% Average, 33% Sensitive',
        'team': 'mixed',
        'fractions': "1/3,1/3,1/3",  # 33%, 34%, 33%
        'group_params': [
            (0.04, 2),  # Resilient
            (0.06, 3),  # Average
            (0.08, 4),  # Sensitive
        ],
        'n_workers': 100,
    },
    
    # Analyse 4: Sensitivity - Heterogeneity Levels
    'none': {
        'name': 'None (All Identical)',
        'team': 'homogeneous',
        'fractions': None,
        'group_params': [(0.06, 3)],
        'n_workers': 100,
    },
    'low': {
        'name': 'Low (2 Cluster)',
        'description': '70% Average, 30% Sensitive',
        'team': 'mixed',
        'fractions': "7/10,3/10",
        'group_params': [
            (0.06, 3),  # Average
            (0.08, 4),  # Sensitive
        ],
        'n_workers': 100,
    },
    'moderate': {
        'name': 'Moderate (3 Cluster)',
        'team': 'mixed',
        'fractions': "1/3,1/3,1/3",
        'group_params': [
            (0.04, 2),  # Resilient
            (0.06, 3),  # Average
            (0.08, 4),  # Sensitive
        ],
        'n_workers': 100,
    },
    'high': {
        'name': 'High (5 Cluster)',
        'description': '15% Very Resilient, 25% Resilient, 30% Average, 20% Sensitive, 10% Very Sensitive',
        'team': 'mixed',
        'fractions': "15/100,25/100,30/100,20/100,10/100",
        'group_params': [
            (0.02, 1),  # Very Resilient
            (0.04, 2),  # Resilient
            (0.06, 3),  # Average
            (0.08, 4),  # Sensitive
            (0.10, 5),  # Very Sensitive
        ],
        'n_workers': 100,
    },
}

# ============================================================================
# PARAMETERS
# ============================================================================

time_cg, time_cg_init = 7200, 10
max_itr, threshold = 2000, 6e-5
N_SEEDS = 25

# Which analysis to run
RUN_ANALYSIS = 'all'  # 'baseline', 'sensitivity', or 'all'

# ============================================================================
# METRIC FUNCTIONS
# ============================================================================

def calculate_gini(values):
    """Calculate Gini coefficient (0 = equal, 1 = unequal)."""
    values = np.array(values)
    if len(values) == 0 or values.sum() == 0:
        return 0.0
    sorted_values = np.sort(values)
    n = len(values)
    cumulative = np.cumsum(sorted_values)
    return (2 * np.sum((np.arange(1, n+1) * sorted_values)) - (n + 1) * cumulative[-1]) / (n * cumulative[-1])


def calculate_90_10_ratio(values):
    """Calculate ratio of 90th to 10th percentile."""
    values = np.array(values)
    if len(values) == 0:
        return 0.0
    p90 = np.percentile(values, 90)
    p10 = np.percentile(values, 10)
    return p90 / p10 if p10 > 0 else float('inf')


def calculate_cv(values):
    """Calculate coefficient of variation (std/mean)."""
    values = np.array(values)
    if len(values) == 0 or np.mean(values) == 0:
        return 0.0
    return np.std(values) / np.mean(values)


def calculate_group_metrics(ls_sc, ls_perf, worker_groups, n_days, n_shifts=3):
    """Calculate detailed metrics per worker group."""
    group_metrics = {}
    all_perf_losses = []
    all_shift_changes = []
    
    for group_name, group in worker_groups.items():
        group_sc = []
        group_perf_loss = []
        
        for worker_id in group.worker_ids:
            w_idx = worker_id - 1
            
            # Shift changes (indexed by worker * n_days)
            sc_start = w_idx * n_days
            sc_end = sc_start + n_days
            if sc_end <= len(ls_sc):
                worker_sc = sum(ls_sc[sc_start:sc_end])
                group_sc.append(worker_sc)
                all_shift_changes.append(worker_sc)
            
            # Performance loss (indexed by worker * n_days * n_shifts)
            perf_start = w_idx * n_days * n_shifts
            perf_end = perf_start + n_days * n_shifts
            if perf_end <= len(ls_perf):
                # Performance loss = sum of (1 - perf) for working shifts
                worker_perf = ls_perf[perf_start:perf_end]
                perf_loss = sum(1 - p for p in worker_perf if p > 0)
                group_perf_loss.append(perf_loss)
                all_perf_losses.append(perf_loss)
        
        group_metrics[group_name] = {
            'epsilon': group.epsilon,
            'chi': group.chi,
            'n_workers': len(group.worker_ids),
            'total_shift_changes': sum(group_sc),
            'avg_shift_changes': np.mean(group_sc) if group_sc else 0,
            'std_shift_changes': np.std(group_sc) if group_sc else 0,
            'min_shift_changes': min(group_sc) if group_sc else 0,
            'max_shift_changes': max(group_sc) if group_sc else 0,
            'total_perf_loss': sum(group_perf_loss),
            'avg_perf_loss': np.mean(group_perf_loss) if group_perf_loss else 0,
            'std_perf_loss': np.std(group_perf_loss) if group_perf_loss else 0,
            'min_perf_loss': min(group_perf_loss) if group_perf_loss else 0,
            'max_perf_loss': max(group_perf_loss) if group_perf_loss else 0,
        }
    
    # Fairness metrics (across all workers)
    fairness_metrics = {
        'gini_perf_loss': calculate_gini(all_perf_losses),
        'gini_shift_changes': calculate_gini(all_shift_changes),
        'cv_perf_loss': calculate_cv(all_perf_losses),
        'cv_shift_changes': calculate_cv(all_shift_changes),
        'ratio_90_10_perf': calculate_90_10_ratio(all_perf_losses),
        'ratio_90_10_sc': calculate_90_10_ratio(all_shift_changes),
    }
    
    return group_metrics, fairness_metrics


def run_single_scenario(scenario_key, scenario_config, seeds=range(1, 26), run_naive=True):
    """Run a single scenario configuration across multiple seeds."""
    
    print("\n" + "="*80)
    print(f"SCENARIO: {scenario_config['name']}")
    print("="*80)
    
    results = []
    T = list(range(1, 29))
    K = [1, 2, 3]
    n_workers = scenario_config['n_workers']
    I = list(range(1, n_workers + 1))
    
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
        
        demand_dict = generate_dict_from_excel(
            'data/demand_data.xlsx', len(I), 'Medium', scenario=seed
        )
        
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
                # Global metrics
                'undercoverage': undercoverage_bsv,
                'understaffing': understaffing_bsv,
                'perf_loss_total': perfloss_bsv,
                'perf_norm': perfloss_norm_bsv,
                'shift_changes_total': consistency_bsv,
                'cons_norm': consistency_norm_bsv,
                'undercover_norm': undercoverage_norm_bsv,
                'understaffing_norm': understaffing_norm_bsv,
                'spread_sc': spread_sc_bsv,
                'load_share_sc': load_sc_bsv,
                'gini_sc': gini_sc_bsv,
                'top10_sc': ineq_sc_bsv,
                'objective': obj_bsv,
                'lb': lb_bsv,
                'gap': gap_bsv,
                'iterations': itr_bsv,
                'time': time_bsv,
                # Fairness metrics
                'gini_perf_loss': fairness['gini_perf_loss'],
                'gini_shift_changes': fairness['gini_shift_changes'],
                'cv_perf_loss': fairness['cv_perf_loss'],
                'ratio_90_10_perf': fairness['ratio_90_10_perf'],
                'group_metrics': group_metrics,
            }
            
            # Add per-group columns
            for g_name, g_m in group_metrics.items():
                result[f'{g_name}_eps'] = g_m['epsilon']
                result[f'{g_name}_chi'] = g_m['chi']
                result[f'{g_name}_n'] = g_m['n_workers']
                result[f'{g_name}_avg_perf_loss'] = g_m['avg_perf_loss']
                result[f'{g_name}_avg_sc'] = g_m['avg_shift_changes']
                result[f'{g_name}_std_perf_loss'] = g_m['std_perf_loss']
                result[f'{g_name}_std_sc'] = g_m['std_shift_changes']
            
            results.append(result)
            print(f"  BSV: obj={obj_bsv:.2f}, gap={gap_bsv:.2f}%, perf_loss={perfloss_bsv:.2f}, sc={consistency_bsv:.0f}")
            
        except Exception as e:
            print(f"  BSV ERROR: {e}")
            import traceback
            traceback.print_exc()
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
                
                # Calculate fairness for MLSV
                group_metrics_mlsv, fairness_mlsv = calculate_group_metrics(
                    ls_sc_mlsv, ls_perf_mlsv, worker_groups, len(T), len(K)
                )
                
                result_mlsv = {
                    'scenario': scenario_key,
                    'scenario_name': scenario_config['name'],
                    'seed': seed,
                    'model': 'MLSV',
                    'undercoverage': undercoverage_mlsv,
                    'understaffing': understaffing_mlsv,
                    'understaffing_norm': understaffing_norm_mlsv,
                    'perf_loss_total': perfloss_mlsv,
                    'perf_norm': perfloss_norm_mlsv,
                    'shift_changes_total': consistency_mlsv,
                    'cons_norm': consistency_norm_mlsv,
                    'undercover_norm': undercoverage_norm_mlsv,
                    'spread_sc': spread_sc_mlsv,
                    'load_share_sc': load_sc_mlsv,
                    'gini_sc': gini_sc_mlsv,
                    'top10_sc': ineq_sc_mlsv,
                    'objective': obj_mlsv,
                    'lb': 0,
                    'gap': 0,
                    'iterations': 0,
                    'time': 0,
                    'gini_perf_loss': fairness_mlsv['gini_perf_loss'],
                    'gini_shift_changes': fairness_mlsv['gini_shift_changes'],
                    'cv_perf_loss': fairness_mlsv['cv_perf_loss'],
                    'ratio_90_10_perf': fairness_mlsv['ratio_90_10_perf'],
                    'group_metrics': group_metrics_mlsv,
                }
                
                for g_name, g_m in group_metrics_mlsv.items():
                    result_mlsv[f'{g_name}_eps'] = g_m['epsilon']
                    result_mlsv[f'{g_name}_chi'] = g_m['chi']
                    result_mlsv[f'{g_name}_n'] = g_m['n_workers']
                    result_mlsv[f'{g_name}_avg_perf_loss'] = g_m['avg_perf_loss']
                    result_mlsv[f'{g_name}_avg_sc'] = g_m['avg_shift_changes']
                
                results.append(result_mlsv)
                print(f"  MLSV: obj={obj_mlsv:.2f}, perf_loss={perfloss_mlsv:.2f}, sc={consistency_mlsv:.0f}")
                
            except Exception as e:
                print(f"  MLSV ERROR: {e}")
    
    # Print scenario summary
    print("\n" + "-"*60)
    print(f"SCENARIO SUMMARY: {scenario_config['name']}")
    print("-"*60)
    
    bsv_results = [r for r in results if r['model'] == 'BSV']
    mlsv_results = [r for r in results if r['model'] == 'MLSV']
    
    if bsv_results:
        print(f"{'BSV Model (n={})'.format(len(bsv_results)):<25}")
        print(f"  Undercoverage:    mean={np.mean([r['undercoverage'] for r in bsv_results]):.2f}, "
              f"std={np.std([r['undercoverage'] for r in bsv_results]):.2f}")
        print(f"  Perf Loss:        mean={np.mean([r['perf_loss_total'] for r in bsv_results]):.2f}, "
              f"std={np.std([r['perf_loss_total'] for r in bsv_results]):.2f}")
        print(f"  Shift Changes:    mean={np.mean([r['shift_changes_total'] for r in bsv_results]):.2f}, "
              f"std={np.std([r['shift_changes_total'] for r in bsv_results]):.2f}")
        print(f"  Gap:              mean={np.mean([r['gap'] for r in bsv_results]):.2f}%")
        print(f"  Time:             mean={np.mean([r['time'] for r in bsv_results]):.1f}s")
        print(f"  Gini (Perf Loss): mean={np.mean([r['gini_perf_loss'] for r in bsv_results]):.4f}, "
              f"std={np.std([r['gini_perf_loss'] for r in bsv_results]):.4f}")
    
    if mlsv_results:
        print(f"\n{'MLSV Model (n={})'.format(len(mlsv_results)):<25}")
        print(f"  Undercoverage:    mean={np.mean([r['undercoverage'] for r in mlsv_results]):.2f}")
        print(f"  Perf Loss:        mean={np.mean([r['perf_loss_total'] for r in mlsv_results]):.2f}")
        print(f"  Shift Changes:    mean={np.mean([r['shift_changes_total'] for r in mlsv_results]):.2f}")
    
    print("-"*60)
    
    return results


def print_analysis_tables(all_results):
    """Generate analysis tables for the paper."""
    
    print("\n" + "="*80)
    print("ANALYSIS TABLES")
    print("="*80)
    
    # ===== Table 1: Baseline Comparison =====
    if 'homogen' in all_results and 'heterogen_3cluster' in all_results:
        print("\n" + "-"*60)
        print("Table X: Comparison of homogeneous vs. heterogeneous workforce")
        print("-"*60)
        
        homo_bsv = [r for r in all_results['homogen'] if r['model'] == 'BSV']
        hetero_bsv = [r for r in all_results['heterogen_3cluster'] if r['model'] == 'BSV']
        
        if homo_bsv and hetero_bsv:
            metrics = [
                ('Total Undercoverage', 'undercoverage'),
                ('Perf. Loss (Total)', 'perf_loss_total'),
                ('Shift Changes', 'shift_changes_total'),
                ('Computation Time', 'time'),
                ('Gap (%)', 'gap'),
            ]
            
            print(f"{'Metric':<22} {'Homogeneous':>12} {'Heterogeneous':>14} {'Δ (%)':>10}")
            print("-"*60)
            
            for label, key in metrics:
                homo_val = np.mean([r[key] for r in homo_bsv])
                hetero_val = np.mean([r[key] for r in hetero_bsv])
                delta = ((hetero_val - homo_val) / homo_val * 100) if homo_val != 0 else 0
                print(f"{label:<22} {homo_val:>12.2f} {hetero_val:>14.2f} {delta:>+10.1f}%")
    
    # ===== Table 2: Worker-Type Impact =====
    if 'heterogen_3cluster' in all_results:
        print("\n" + "-"*60)
        print("Table Y: Performance and shift changes by worker type")
        print("-"*60)
        
        hetero_bsv = [r for r in all_results['heterogen_3cluster'] if r['model'] == 'BSV']
        
        if hetero_bsv:
            # Get group names from first result
            sample = hetero_bsv[0]['group_metrics']
            print(f"{'Worker Type':<15} {'ε':>6} {'χ':>4} {'Avg Perf Loss':>14} {'Avg Shift Ch.':>14} {'n':>6}")
            print("-"*60)
            
            for g_name in sample.keys():
                eps = sample[g_name]['epsilon']
                chi = sample[g_name]['chi']
                n = sample[g_name]['n_workers']
                avg_perf = np.mean([r['group_metrics'][g_name]['avg_perf_loss'] for r in hetero_bsv])
                avg_sc = np.mean([r['group_metrics'][g_name]['avg_shift_changes'] for r in hetero_bsv])
                print(f"{g_name:<15} {eps:>6.2f} {chi:>4d} {avg_perf:>14.2f} {avg_sc:>14.2f} {n:>6d}")
    
    # ===== Table 3: Fairness Metrics =====
    print("\n" + "-"*60)
    print("Table Z: Fairness metrics across model variants")
    print("-"*60)
    
    print(f"{'Model Variant':<20} {'Gini Mean':>10} {'Gini Std':>10} {'90/10 Mean':>12} {'90/10 Std':>10} {'CV':>8}")
    print("-"*60)
    
    for scenario_key in ['homogen', 'heterogen_3cluster']:
        if scenario_key not in all_results:
            continue
        for model in ['BSV', 'MLSV']:
            runs = [r for r in all_results[scenario_key] if r['model'] == model]
            if runs:
                name = f"{scenario_key[:8]}-{model}"
                gini_mean = np.mean([r['gini_perf_loss'] for r in runs])
                gini_std = np.std([r['gini_perf_loss'] for r in runs])
                
                ratios = [r.get('ratio_90_10_perf', 0) for r in runs]
                ratio_mean = np.mean(ratios)
                ratio_std = np.std(ratios)
                
                cv = np.mean([r['cv_perf_loss'] for r in runs])
                print(f"{name:<20} {gini_mean:>10.4f} {gini_std:>10.4f} {ratio_mean:>12.2f} {ratio_std:>10.2f} {cv:>8.4f}")
    
    # ===== Table 4: Sensitivity Analysis =====
    sensitivity_scenarios = ['none', 'low', 'moderate', 'high']
    sens_results = {k: all_results.get(k, []) for k in sensitivity_scenarios}
    
    if any(sens_results.values()):
        print("\n" + "-"*60)
        print("Table: Sensitivity to heterogeneity level")
        print("-"*60)
        
        print(f"{'Level':<12} {'Undercover':>12} {'Perf Loss':>12} {'Shift Ch.':>12} {'Gini':>8}")
        print("-"*60)
        
        for level in sensitivity_scenarios:
            runs = [r for r in sens_results.get(level, []) if r.get('model') == 'BSV']
            if runs:
                uc = np.mean([r['undercoverage'] for r in runs])
                pl = np.mean([r['perf_loss_total'] for r in runs])
                sc = np.mean([r['shift_changes_total'] for r in runs])
                gini = np.mean([r['gini_perf_loss'] for r in runs])
                print(f"{level:<12} {uc:>12.2f} {pl:>12.2f} {sc:>12.0f} {gini:>8.4f}")


def save_summary_csv(all_results):
    """Save key metrics for the paper text in a vertical CSV format with stats."""
    summary_data = []
    
    def add_stats(metric_name, values):
        if not values: return
        summary_data.append({
            'metric': metric_name,
            'min': round(np.min(values), 3),
            'max': round(np.max(values), 3),
            'median': round(np.median(values), 3),
            'mean': round(np.mean(values), 3),
            'std': round(np.std(values), 3)
        })

    # 1. Baseline vs Heterogeneous (Homogen vs Heterogen 3-Cluster)
    if 'homogen' in all_results and 'heterogen_3cluster' in all_results:
        homo_bsv = [r for r in all_results['homogen'] if r['model'] == 'BSV']
        hetero_bsv = [r for r in all_results['heterogen_3cluster'] if r['model'] == 'BSV']
        
        if homo_bsv and hetero_bsv:
            # Undercoverage
            h0_uc = [r['undercoverage'] for r in homo_bsv]
            h1_uc = [r['undercoverage'] for r in hetero_bsv]
            add_stats('baseline_undercoverage', h0_uc)
            add_stats('heterogeneous_undercoverage', h1_uc)
            
            # Reduction per seed
            reductions = [((u0 - u1) / u0 * 100) if u0 > 0 else 0 for u0, u1 in zip(h0_uc, h1_uc)]
            add_stats('undercoverage_reduction_pct', reductions)
            
            # Shift Changes
            h0_sc = [r['shift_changes_total'] for r in homo_bsv]
            h1_sc = [r['shift_changes_total'] for r in hetero_bsv]
            add_stats('baseline_shift_changes', h0_sc)
            add_stats('heterogeneous_shift_changes', h1_sc)
            
            # Perf Loss
            h0_pl = [r['perf_loss_total'] for r in homo_bsv]
            h1_pl = [r['perf_loss_total'] for r in hetero_bsv]
            add_stats('baseline_perf_loss', h0_pl)
            add_stats('heterogeneous_perf_loss', h1_pl)
            
            # Gini
            h0_gini = [r['gini_perf_loss'] for r in homo_bsv]
            h1_gini = [r['gini_perf_loss'] for r in hetero_bsv]
            add_stats('baseline_gini_perf_loss', h0_gini)
            add_stats('heterogeneous_gini_perf_loss', h1_gini)
            
            # Group specific (Worker-Type impact)
            sample_g = hetero_bsv[0]['group_metrics']
            mapping = {
                'group_1': 'resilient',
                'group_2': 'average',
                'group_3': 'sensitive'
            }
            for g_id, label in mapping.items():
                if g_id in sample_g:
                    avg_perf_vals = [r['group_metrics'][g_id]['avg_perf_loss'] for r in hetero_bsv]
                    avg_sc_vals = [r['group_metrics'][g_id]['avg_shift_changes'] for r in hetero_bsv]
                    add_stats(f'avg_perf_loss_{label}', avg_perf_vals)
                    add_stats(f'avg_shift_changes_{label}', avg_sc_vals)

    # 2. High Heterogeneity
    if 'high' in all_results:
        high_bsv = [r for r in all_results['high'] if r['model'] == 'BSV']
        if high_bsv:
            high_uc = [r['undercoverage'] for r in high_bsv]
            high_gini = [r['gini_perf_loss'] for r in high_bsv]
            add_stats('high_heterogeneity_undercoverage', high_uc)
            add_stats('high_heterogeneity_gini', high_gini)

    df_summary = pd.DataFrame(summary_data)
    if not df_summary.empty:
        df_summary = df_summary[['metric', 'min', 'max', 'median', 'mean', 'std']]
    filename = f'results/paper_text_metrics_{datetime.now().strftime("%d_%m_%Y_%H-%M")}.csv'
    df_summary.to_csv(filename, index=False)
    print(f"\nSummary CSV for paper text saved to: {filename}")


def save_detailed_stats_csv(all_results):
    """Save detailed min/max/median/mean/std stats for the scenarios, matching the requested CSV format."""
    for scenario_key, results in all_results.items():
        if not results: continue
        bsv_results = [r for r in results if r['model'] == 'BSV']
        mlsv_results = [r for r in results if r['model'] == 'MLSV']
        
        # We only generate this table if we ran BOTH models
        if not bsv_results or not mlsv_results: continue
        
        metrics_mapping = [
            ('undercover', 'undercoverage'),
            ('undercover_norm', 'undercover_norm'),
            ('cons', 'shift_changes_total'),
            ('cons_norm', 'cons_norm'),
            ('perf', 'perf_loss_total'),
            ('perf_norm', 'perf_norm'),
            ('understaffing', 'understaffing'),
            ('understaffing_norm', 'understaffing_norm'),
            ('spread_sc', 'spread_sc'),
            ('load_share_sc', 'load_share_sc'),
            ('gini_sc', 'gini_sc'),
            ('top10_sc', 'top10_sc')
        ]
        
        csv_rows = []
        for metric_name, dict_key in metrics_mapping:
            # Behavioral values
            vals_bsv = []
            for r in bsv_results:
                if dict_key in r and r[dict_key] is not None:
                    val = r[dict_key]
                    if isinstance(val, dict):
                        v_list = sorted(list(val.values()), reverse=True)
                        tot = sum(v_list)
                        if tot > 0:
                            vals_bsv.append( (sum(v_list[:max(1, len(v_list)//10)]) / tot) * 100 )
                    else:
                        vals_bsv.append(val)
            
            if vals_bsv:
                csv_rows.append({
                    'metric': f'{metric_name}_behavior',
                    'min': round(np.min(vals_bsv), 2),
                    'max': round(np.max(vals_bsv), 2),
                    'median': round(np.median(vals_bsv), 2),
                    'mean': round(np.mean(vals_bsv), 2),
                    'std': round(np.std(vals_bsv), 2)
                })
            # Naive values
            vals_mlsv = []
            for r in mlsv_results:
                if dict_key in r and r[dict_key] is not None:
                    val = r[dict_key]
                    if isinstance(val, dict):
                        v_list = sorted(list(val.values()), reverse=True)
                        tot = sum(v_list)
                        if tot > 0:
                            vals_mlsv.append( (sum(v_list[:max(1, len(v_list)//10)]) / tot) * 100 )
                    else:
                        vals_mlsv.append(val)
                        
            if vals_mlsv:
                csv_rows.append({
                    'metric': f'{metric_name}_naive',
                    'min': round(np.min(vals_mlsv), 2),
                    'max': round(np.max(vals_mlsv), 2),
                    'median': round(np.median(vals_mlsv), 2),
                    'mean': round(np.mean(vals_mlsv), 2),
                    'std': round(np.std(vals_mlsv), 2)
                })
                
        # Calculate reduction % (Undercoverage)
        vals_uc_bsv = [r['undercoverage'] for r in bsv_results if 'undercoverage' in r]
        vals_uc_mlsv = [r['undercoverage'] for r in mlsv_results if 'undercoverage' in r]
        if vals_uc_bsv and vals_uc_mlsv:
            uc_bsv_mean = np.mean(vals_uc_bsv)
            uc_mlsv_mean = np.mean(vals_uc_mlsv)
            if uc_mlsv_mean > 0:
                reduction = (uc_mlsv_mean - uc_bsv_mean) / uc_mlsv_mean * 100
            else:
                reduction = 0
            
            csv_rows.append({
                'metric': 'reduction',
                'min': round(reduction, 2),
                'max': '',
                'median': '',
                'mean': '',
                'std': ''
            })
            
        df_stats = pd.DataFrame(csv_rows)
        # Enforce column order to exactly match request
        df_stats = df_stats[['metric', 'min', 'max', 'median', 'mean', 'std']]
        
        filename = f'results/detailed_stats_{scenario_key}_{datetime.now().strftime("%d_%m_%Y_%H-%M")}.csv'
        df_stats.to_csv(filename, index=False)
        print(f"\nDetailed stats CSV for '{scenario_key}' saved to: {filename}")



# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    start_time = time.time()
    
    all_results = {}
    
    if RUN_ANALYSIS in ['baseline', 'all']:
        print("\n" + "#"*80)
        print("# ANALYSIS 1-3: BASELINE COMPARISON, WORKER-TYPE IMPACT, FAIRNESS")
        print("#"*80)
        
        for scenario_key in ['homogen', 'heterogen_3cluster']:
            results = run_single_scenario(
                scenario_key, SCENARIOS[scenario_key], 
                seeds=range(1, N_SEEDS + 1), run_naive=True
            )
            all_results[scenario_key] = results
            
            df = pd.DataFrame(results)
            df.to_excel(f'results/analysis_{scenario_key}_{datetime.now().strftime("%d_%m_%Y_%H-%M")}.xlsx', index=False)
    
    if RUN_ANALYSIS in ['sensitivity', 'all']:
        print("\n" + "#"*80)
        print("# ANALYSIS 4: SENSITIVITY ANALYSIS")
        print("#"*80)
        
        for scenario_key in ['none', 'low', 'moderate', 'high']:
            results = run_single_scenario(
                scenario_key, SCENARIOS[scenario_key], 
                seeds=range(1, N_SEEDS + 1), run_naive=False  # Skip MLSV for sensitivity
            )
            all_results[scenario_key] = results
            
            df = pd.DataFrame(results)
            df.to_excel(f'results/sensitivity_{scenario_key}_{datetime.now().strftime("%d_%m_%Y_%H-%M")}.xlsx', index=False)
    
    # Print analysis tables
    print_analysis_tables(all_results)
    
    # Save all results
    all_flat = []
    for results in all_results.values():
        all_flat.extend(results)
    
    df_all = pd.DataFrame(all_flat)
    df_all.to_excel(f'results/analysis_ALL_{datetime.now().strftime("%d_%m_%Y_%H-%M")}.xlsx', index=False)
    
    # Save summary CSV for paper text comparison
    save_summary_csv(all_results)
    
    # Save the custom detailed stats CSV format
    save_detailed_stats_csv(all_results)
    
    print(f"\nTotal execution time: {time.time() - start_time:.2f} seconds")
    print("="*80)
