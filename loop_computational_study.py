import pandas as pd
import numpy as np
import time
import os
import random
from cg_behavior import column_generation_behavior
from worker_groups import create_homogeneous_group
from nonlinear_transitions import get_default_nl_spec, evaluate_schedule_nl

def generate_stochastic_demand(I_size, scarcity, seed, T_days=28):
    """
    Generates stochastic demand as described in Appendix D.
    I_size: number of workers (50, 100, 150)
    scarcity: 0.9 (Low), 1.0 (Medium), 1.1 (High)
    """
    random.seed(seed)
    np.random.seed(seed)
    
    T = list(range(1, T_days + 1))
    K = [1, 2, 3] # E, L, N
    
    demand_dict = {}
    total_q_theoretical = I_size * scarcity
    
    for t in T:
        # +/- 25% range around theoretical mean
        q_t = int(round(total_q_theoretical * np.random.uniform(0.75, 1.25)))
        
        # Distribution: L ~ 50%, E ~ 25%, N ~ 25%
        z_L = np.random.uniform(0, 1)
        q_L = int(round(z_L * q_t))
        
        z_N = np.random.uniform(0, 1)
        q_N = int(round(z_N * (q_t - q_L)))
        
        q_E = q_t - q_L - q_N
        
        demand_dict[(t, 1)] = max(0, q_E)
        demand_dict[(t, 2)] = max(0, q_L)
        demand_dict[(t, 3)] = max(0, q_N)
        
    return demand_dict

def run_instance(I_size, scarcity_label, scarcity_val, seed, epsilon=0.06, chi=3):
    """Runs a single instance with both BAP and NPP."""
    T_days = 28
    T = list(range(1, T_days + 1))
    K = [1, 2, 3]
    I = list(range(1, I_size + 1))
    
    demand = generate_stochastic_demand(I_size, scarcity_val, seed, T_days)
    
    # Data for DF
    data_list = []
    for t in T:
        for k in K:
            data_list.append({'T': t, 'K': k, 'I': 1}) # Placeholder
    df = pd.DataFrame(data_list)
    
    # Non-linear spec
    nl_spec = get_default_nl_spec(epsilon, chi)
    
    print(f"\n--- Instance: I={I_size}, Demand={scarcity_label}, Seed={seed} ---")
    
    # 1. BAP (Behavior-Aware Paradigm)
    print("Running BAP...")
    bap_res = column_generation_behavior(
        df, demand, epsilon, 4, 6, 30, 200, 40, chi, 0.0001, 30, I, T, K, 1.0,
        sp_solver="labeling", nl_spec=nl_spec
    )
    bap_obj = bap_res[8]
    bap_gap = bap_res[12]
    
    # 2. NPP (Naive Performance Paradigm)
    print("Running NPP...")
    npp_res = column_generation_behavior(
        df, demand, 0.0, 4, 6, 30, 200, 40, chi, 0.0001, 30, I, T, K, 1.0,
        sp_solver="labeling", nl_spec=None 
    )
    npp_obj_nominal = npp_res[8]
    
    # 3. Ex-post evaluate NPP with NL dynamics
    print("Evaluating NPP ex-post...")
    n_nurses = len(I)
    n_days = len(T)
    n_shifts = len(K)
    ls_x = npp_res[19]
    
    # Track real performance per shift
    real_supply_per_shift = [0.0] * (n_days * n_shifts)
    
    for idx in range(n_nurses):
        worker_x = ls_x[idx * (n_days * n_shifts) : (idx + 1) * (n_days * n_shifts)]
        x_dict = {}
        for d_idx, day in enumerate(T):
            for s_idx, shift in enumerate(K):
                if worker_x[d_idx * n_shifts + s_idx] > 0.5:
                    x_dict[(day, shift)] = 1.0
        
        perf_hist, _, _, _ = evaluate_schedule_nl(x_dict, T, K, nl_spec)
        
        for d_idx, day in enumerate(T):
            p = perf_hist[day]
            for s_idx, shift in enumerate(K):
                i = d_idx * n_shifts + s_idx
                if worker_x[i] > 0.5:
                    real_supply_per_shift[i] += p
    
    # Final ex-post undercoverage: sum(max(0, q - real_supply))
    demand_values = [demand.get((t, k), 0) for t in T for k in K]
    total_undercoverage_expost = sum(max(0, demand_values[i] - real_supply_per_shift[i]) for i in range(len(demand_values)))
    
    npp_obj_expost = total_undercoverage_expost
    
    return {
        'I': I_size,
        'scarcity': scarcity_label,
        'seed': seed,
        'bap_obj': bap_obj,
        'npp_obj_nominal': npp_obj_nominal,
        'npp_obj_expost': npp_obj_expost,
        'bap_gap': bap_gap
    }

def main():
    I_sizes = [50]
    scarcities = [('Low', 0.9)]
    seeds = range(1, 2) # Start with 1 seed for testing
    
    results = []
    for i_size in I_sizes:
        for s_label, s_val in scarcities:
            for seed in seeds:
                res = run_instance(i_size, s_label, s_val, seed)
                results.append(res)
    
    df_res = pd.DataFrame(results)
    print("\nFinal Aggregated Results:")
    print(df_res.groupby(['I', 'scarcity']).mean())

if __name__ == "__main__":
    main()
