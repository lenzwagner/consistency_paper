import pandas as pd
import numpy as np
import time
from Utils.setup import Min_WD_i, Max_WD_i
from Utils.gcutil import generate_dict_from_excel
from Utils.compactsolver import Problem
from core.cg_behavior import column_generation_behavior
from core.worker_groups import WorkerGroup, get_default_delta

# Input parameters
epsilon = 0.06
chi = 3
len_I = 50
pattern = 'Medium'
scenario = 1
prob = 1.0

# Base data sets
T = list(range(1, 29))
I = list(range(1, len_I + 1))
K = [1, 2, 3]

data = pd.DataFrame({
    'I': I + [np.nan] * (max(len(I), len(T), len(K)) - len(I)),
    'T': T + [np.nan] * (max(len(I), len(T), len(K)) - len(T)),
    'K': K + [np.nan] * (max(len(I), len(T), len(K)) - len(K))
})

demand_dict = generate_dict_from_excel('data/demand_data.xlsx', len(I), pattern, scenario)

# Define the 3 parameterizations:
# Name: (gamma_C, gamma_R, alpha_R, e_max)
parameterizations = {
    'Linear': (1.0, 1.0, 0.04, 0.5),
    'Convex (Paper Default)': (1.25, 0.5, 0.04, 0.5),
    'Concave': (0.75, 1.5, 0.04, 0.5)
}

results_summary = []

for name, (g_C, g_R, a_R, e_max) in parameterizations.items():
    print("=" * 80)
    print(f"RUNNING PARAMETERIZATION: {name} (gamma_C={g_C}, gamma_R={g_R}, alpha_R={a_R})")
    print("=" * 80)
    
    # Create homogeneous group with custom non-linear parameters
    group = WorkerGroup(
        name="all",
        epsilon=epsilon,
        chi=chi,
        worker_ids=I,
        gamma_C=g_C,
        gamma_R=g_R,
        alpha_R=a_R,
        e_max=e_max,
        delta=get_default_delta(epsilon)
    )
    worker_groups = {"all": group}
    
    # --- 1. Solve Compact Model ---
    print("\n--- 1. Solving Compact Model ---")
    compact_model = Problem(data, demand_dict, epsilon, Min_WD_i, Max_WD_i, chi, worker_groups=worker_groups)
    compact_model.buildLinModel()
    compact_model.ModelParams()
    compact_model.model.setParam('TimeLimit', 300) # 5 minutes max
    
    t0 = time.time()
    compact_model.solveModel()
    t_compact = time.time() - t0
    
    try:
        compact_obj = compact_model.model.ObjVal
    except AttributeError:
        compact_obj = None
    
    # --- 2. Solve CG Model ---
    print("\n--- 2. Solving CG Model ---")
    t0 = time.time()
    (undercoverage_behavior, understaffing_behavior, perfloss_behavior, consistency_behavior, 
     consistency_norm_behavior, undercoverage_norm_behavior, understaffing_norm_behavior,
     perfloss_norm_behavior, final_obj_behavior, final_lb, itr, lagrangeB, gap, time_sps, time_rmp, 
     time_ip, ls_p_behavior, ls_sc_behavior, ls_perf_behavior, ls_x_behavior,
     ls_r_behavior, undercoverage_per_shift_behavior, results_ineq_sc_behavior, spread_sc_behavior, 
     load_share_sc_behavior, gini_sc_behavior, results_ineq_perf_behavior,
     spread_perf_behavior, load_share_perf_behavior, gini_perf_behavior, 
     shift_blocks_behavior) = column_generation_behavior(
        data, demand_dict, epsilon, Min_WD_i, Max_WD_i, 10, 200, 100, chi,
        6e-5, 7200, I, T, K, prob, sp_solver='labeling_bidir',
        worker_groups=worker_groups, save_lp=False, use_heuristic_start=False
    )
    t_cg = time.time() - t0
    
    print(f"\nRESULTS FOR {name}:")
    print(f"  Compact Model Obj: {compact_obj} (solved in {t_compact:.2f}s)")
    print(f"  CG Model Obj: {final_obj_behavior} (solved in {t_cg:.2f}s, iterations: {itr}, gap: {gap}%)")
    
    results_summary.append({
        'Parameterization': name,
        'gamma_C': g_C,
        'gamma_R': g_R,
        'Compact Obj': compact_obj,
        'Compact Time': t_compact,
        'CG Obj': final_obj_behavior,
        'CG Time': t_cg,
        'CG Iterations': itr
    })

print("\n" + "="*80)
print("FINAL SUMMARY TABLE")
print("="*80)
df_summary = pd.DataFrame(results_summary)
print(df_summary.to_string(index=False))
