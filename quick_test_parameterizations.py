import pandas as pd
import numpy as np
import time
import os
from Utils.setup import Min_WD_i, Max_WD_i
from Utils.gcutil import generate_dict_from_excel
from core.cg_behavior import column_generation_behavior
from core.worker_groups import WorkerGroup, get_default_delta

# Create results directory if it doesn't exist
os.makedirs("results", exist_ok=True)
csv_path = "results/parameterization_comparison_raw.csv"

# Input parameters
pattern = 'Medium'
prob = 1.0
K = [1, 2, 3]

# Define the 4 parameterizations with group-specific exponents:
# each is (gamma_C, gamma_R, alpha_R, e_max)
parameterizations = {
    'Linear': (
        (1.0, 1.0, 0.04, 1.0), # group1
        (1.0, 1.0, 0.04, 1.0)  # group2
    ),
    'Convex (Paper Default)': (
        (1.25, 0.5, 0.04, 1.0), # group1
        (1.5, 0.3, 0.04, 1.0)   # group2 (more convex)
    ),
    'Concave (Moderate)': (
        (0.85, 1.25, 0.04, 1.0), # group1
        (0.75, 1.5, 0.04, 1.0)   # group2 (moderate concave)
    ),
    'Concave (Extreme)': (
        (0.75, 1.5, 0.04, 1.0), # group1
        (0.6, 1.8, 0.04, 1.0)   # group2 (extreme concave)
    )
}

raw_results = []

# Archive old raw results for a clean fresh run
if os.path.exists(csv_path):
    archive_path = f"results/parameterization_comparison_raw_archive_{int(time.time())}.csv"
    print(f"Archiving old raw results to {archive_path}")
    try:
        os.rename(csv_path, archive_path)
    except Exception as e:
        print(f"Failed to archive: {e}")

# Helper to check if a run is already completed
def is_already_done(size, seed, param_name):
    for r in raw_results:
        if r.get('Size') == size and r.get('Seed') == seed and r.get('Parameterization') == param_name:
            return True
    return False

# Workforce sizes loop
for len_I in [50, 100, 150]:
    I = list(range(1, len_I + 1))
    T = list(range(1, 29))
    
    data = pd.DataFrame({
        'I': I + [np.nan] * (max(len(I), len(T), len(K)) - len(I)),
        'T': T + [np.nan] * (max(len(I), len(T), len(K)) - len(T)),
        'K': K + [np.nan] * (max(len(I), len(T), len(K)) - len(K))
    })

    # Seeds loop
    for scenario in range(1, 26):
        print("\n" + "=" * 90)
        print(f"Workforce Size: {len_I} | Seed: {scenario} / 25")
        print("=" * 90)
        
        try:
            demand_dict = generate_dict_from_excel('data/demand_data.xlsx', len(I), pattern, scenario)
        except Exception as e:
            print(f"Error loading demand data for size {len_I} seed {scenario}: {e}. Skipping.")
            continue

        # Parameterizations loop
        for name, (g1_specs, g2_specs) in parameterizations.items():
            if is_already_done(len_I, scenario, name):
                print(f"  Already completed: Size {len_I} | Seed {scenario} | {name}. Skipping.")
                continue
                
            g1_C, g1_R, a1_R, e1_max = g1_specs
            g2_C, g2_R, a2_R, e2_max = g2_specs
            
            print("-" * 80)
            print(f"Size {len_I} | Seed {scenario} | Parameterization: {name}")
            print(f"  group1 (IDs 1-{len_I//2}): g_C={g1_C}, g_R={g1_R}")
            print(f"  group2 (IDs {len_I//2 + 1}-{len_I}): g_C={g2_C}, g_R={g2_R}")
            print("-" * 80)
            
            # Create group1 (epsilon=0.04, chi=2) - 50% split
            group1 = WorkerGroup(
                name="group1",
                epsilon=0.04,
                chi=2,
                worker_ids=list(range(1, len_I // 2 + 1)),
                gamma_C=g1_C,
                gamma_R=g1_R,
                alpha_R=a1_R,
                e_max=e1_max,
                delta=get_default_delta(0.04)
            )
            
            # Create group2 (epsilon=0.08, chi=4) - 50% split
            group2 = WorkerGroup(
                name="group2",
                epsilon=0.08,
                chi=4,
                worker_ids=list(range(len_I // 2 + 1, len_I + 1)),
                gamma_C=g2_C,
                gamma_R=g2_R,
                alpha_R=a2_R,
                e_max=e2_max,
                delta=get_default_delta(0.08)
            )
            
            worker_groups = {"group1": group1, "group2": group2}
            
            t0 = time.time()
            try:
                (undercoverage_behavior, understaffing_behavior, perfloss_behavior, consistency_behavior, 
                 consistency_norm_behavior, undercoverage_norm_behavior, understaffing_norm_behavior,
                 perfloss_norm_behavior, final_obj_behavior, final_lb, itr, lagrangeB, gap, time_sps, time_rmp, 
                 time_ip, ls_p_behavior, ls_sc_behavior, ls_perf_behavior, ls_x_behavior,
                 ls_r_behavior, undercoverage_per_shift_behavior, results_ineq_sc_behavior, spread_sc_behavior, 
                 load_share_sc_behavior, gini_sc_behavior, results_ineq_perf_behavior,
                 spread_perf_behavior, load_share_perf_behavior, gini_perf_behavior, 
                 shift_blocks_behavior) = column_generation_behavior(
                    data, demand_dict, 0.06, Min_WD_i, Max_WD_i, 10, 200, 100, 3,
                    6e-5, 7200, I, T, K, prob, sp_solver='labeling_bidir',
                    worker_groups=worker_groups, save_lp=False, use_heuristic_start=False,
                    use_null_column=True
                )
                t_cg = time.time() - t0
                
                print(f"Size {len_I} | Seed {scenario} ({name}) Obj: {final_obj_behavior:.2f} in {t_cg:.2f}s")
                
                result_item = {
                    'Size': len_I,
                    'Seed': scenario,
                    'Parameterization': name,
                    'CG Obj': final_obj_behavior,
                    'CG Time (s)': t_cg,
                    'CG Iterations': itr,
                    'Gap (%)': gap
                }
                raw_results.append(result_item)
                
                # Save raw progress to CSV incrementally
                pd.DataFrame(raw_results).to_csv(csv_path, index=False)
                
            except Exception as e:
                print(f"Failed to solve Size {len_I} Seed {scenario} under {name}: {e}")

# Compute averages and print final summary table
if raw_results:
    print("\n" + "=" * 90)
    print("AVERAGE METRICS BY SIZE AND PARAMETERIZATION (DEEP HETEROGENEITY)")
    print("=" * 90)
    df_raw = pd.DataFrame(raw_results)
    
    df_avg = df_raw.groupby(['Size', 'Parameterization']).agg({
        'CG Obj': 'mean',
        'CG Time (s)': 'mean',
        'CG Iterations': 'mean',
        'Gap (%)': 'mean'
    }).reset_index()
    
    # Sort for beautiful output
    df_avg = df_avg.sort_values(by=['Size', 'CG Obj'])
    print(df_avg.to_string(index=False))
else:
    print("No runs completed successfully.")