import os
import time
import pandas as pd
import numpy as np
from datetime import datetime

from Utils.setup import Min_WD_i, Max_WD_i
from cg_behavior import column_generation_behavior
from Utils.gcutil import generate_dict_from_excel

def run_threshold_analysis():
    print("="*80)
    print("DEMAND REGIMES AND THRESHOLD EFFECTS ANALYSIS")
    print("="*80)
    
    n_days = 28
    n_workers = 100
    eps = 0.06
    chi = 3
    
    T = list(range(1, n_days + 1))
    K = [1, 2, 3]
    I = list(range(1, n_workers + 1))
    
    data = pd.DataFrame({
        'I': I + [np.nan] * (max(len(I), len(T), len(K)) - len(I)),
        'T': T + [np.nan] * (max(len(I), len(T), len(K)) - len(T)),
        'K': K + [np.nan] * (max(len(I), len(T), len(K)) - len(K))
    })
    
    # Grid of lambda and tau values
    lambdas = np.arange(0.1, 2.1, 0.1).tolist()
    taus = np.arange(0.5, 1.1, 0.1).tolist()
    seeds = range(1, 26)
    
    results = []
    
    for lam in lambdas:
        print(f"\n{'='*40}")
        print(f"--- Testing Lambda = {lam:.2f} ---")
        print(f"{'='*40}")
        
        lam_tau_results = {
            tau: {
                'No-Change_Feasible': [],
                'No-Change_Undercoverage': [],
                'Low-Fatigue_Feasible': [],
                'Low-Fatigue_Undercoverage': [],
                'Unrestricted_Undercoverage': [],
                'Unrestricted_SC': [],
                'P_end': [],
                'B_end': [],
                'L_tail_k7': []
            } for tau in taus
        }
        
        for seed in seeds:
            print(f"\n  >> Seed {seed}/25")
            try:
                base_demand_dict = generate_dict_from_excel(
                    'data/demand_data.xlsx', n_workers, 'Medium', scenario=seed
                )
                base_demand_dict = {k: v for k, v in base_demand_dict.items() if k[0] <= n_days}
            except Exception as e:
                print(f"Failed to pull base demand for seed {seed}: {e}")
                continue
                
            # Scale demand
            scaled_demand_dict = {k: int(round(v * lam)) for k, v in base_demand_dict.items()}
            
            # 1. No-Change Feasibility Run (Independent of tau)
            try:
                res_nc = column_generation_behavior(
                    data, scaled_demand_dict, eps, Min_WD_i, Max_WD_i, 10, 2000, 
                    100, chi, 6e-5, 600, I, T, K, 1.0,
                    sp_solver='labeling_bidir', use_null_column=False,
                    enforce_no_change=True, enforce_performance_floor=None
                )
                uc_nc = res_nc[0]
                feasible_nc = (uc_nc <= 1e-3)
            except Exception as e:
                feasible_nc = False
                uc_nc = np.nan
                
            # 3. Unrestricted BAP (Baseline, Independent of tau except for proxies)
            try:
                res_unr = column_generation_behavior(
                    data, scaled_demand_dict, eps, Min_WD_i, Max_WD_i, 10, 2000, 
                    100, chi, 6e-5, 600, I, T, K, 1.0,
                    sp_solver='labeling_bidir', use_null_column=False,
                    enforce_no_change=False, enforce_performance_floor=None
                )
                uc_unr = res_unr[0]
                sc_unr = res_unr[3]
                ls_p = res_unr[16]
                
                end_day_indices = [(i * n_days) + (n_days - 1) for i in range(n_workers)]
                p_end_vals = [ls_p[idx] for idx in end_day_indices if idx < len(ls_p)]
                P_end_unr = sum(p_end_vals) / len(p_end_vals) if p_end_vals else 0
            except Exception as e:
                uc_unr = np.nan
                sc_unr = np.nan
                ls_p = []
                p_end_vals = []
                P_end_unr = np.nan

            # Now iterate over taus for Low-Fatigue and exhaustion proxies
            for tau in taus:
                # Store Unrestricted and No-Change results which are reused
                lam_tau_results[tau]['No-Change_Feasible'].append(feasible_nc)
                lam_tau_results[tau]['No-Change_Undercoverage'].append(uc_nc)
                lam_tau_results[tau]['Unrestricted_Undercoverage'].append(uc_unr)
                lam_tau_results[tau]['Unrestricted_SC'].append(sc_unr)
                lam_tau_results[tau]['P_end'].append(P_end_unr)
                
                # Compute tau-dependent Unrestricted proxies
                if p_end_vals:
                    B_end = sum(1 for p in p_end_vals if p < tau) / len(p_end_vals)
                else:
                    B_end = np.nan
                lam_tau_results[tau]['B_end'].append(B_end)
                
                if ls_p:
                    k_val = 7
                    tail_duration = 0
                    for d in range(n_days - k_val + 1, n_days + 1):
                        day_idx = d - 1
                        p_day_vals = [ls_p[i * n_days + day_idx] for i in range(n_workers) if (i * n_days + day_idx) < len(ls_p)]
                        P_d = sum(p_day_vals) / len(p_day_vals) if p_day_vals else 1.0
                        if P_d < tau:
                            tail_duration += 1
                    lam_tau_results[tau]['L_tail_k7'].append(tail_duration)
                else:
                    lam_tau_results[tau]['L_tail_k7'].append(np.nan)

                # 2. Low-Fatigue Feasibility Run
                print(f"    -> Low-Fatigue with tau = {tau}")
                try:
                    res_lf = column_generation_behavior(
                        data, scaled_demand_dict, eps, Min_WD_i, Max_WD_i, 10, 2000, 
                        100, chi, 6e-5, 600, I, T, K, 1.0,
                        sp_solver='labeling_bidir', use_null_column=False,
                        enforce_no_change=False, enforce_performance_floor=tau
                    )
                    uc_lf = res_lf[0]
                    feasible_lf = (uc_lf <= 1e-3)
                    lam_tau_results[tau]['Low-Fatigue_Feasible'].append(feasible_lf)
                    lam_tau_results[tau]['Low-Fatigue_Undercoverage'].append(uc_lf)
                except Exception as e:
                    lam_tau_results[tau]['Low-Fatigue_Feasible'].append(False)
                    lam_tau_results[tau]['Low-Fatigue_Undercoverage'].append(np.nan)
                
        # Average and Standard Deviation over all 25 seeds for each tau at this lambda
        for tau in taus:
            avg_res = {
                'lambda': lam,
                'tau': tau,
                'No-Change_Feasible_%': np.nanmean(lam_tau_results[tau]['No-Change_Feasible']) * 100,
                'No-Change_Undercoverage': np.nanmean(lam_tau_results[tau]['No-Change_Undercoverage']),
                'No-Change_Undercoverage_std': np.nanstd(lam_tau_results[tau]['No-Change_Undercoverage']),
                'Low-Fatigue_Feasible_%': np.nanmean(lam_tau_results[tau]['Low-Fatigue_Feasible']) * 100,
                'Low-Fatigue_Undercoverage': np.nanmean(lam_tau_results[tau]['Low-Fatigue_Undercoverage']),
                'Low-Fatigue_Undercoverage_std': np.nanstd(lam_tau_results[tau]['Low-Fatigue_Undercoverage']),
                'Unrestricted_Undercoverage': np.nanmean(lam_tau_results[tau]['Unrestricted_Undercoverage']),
                'Unrestricted_Undercoverage_std': np.nanstd(lam_tau_results[tau]['Unrestricted_Undercoverage']),
                'Unrestricted_SC': np.nanmean(lam_tau_results[tau]['Unrestricted_SC']),
                'Unrestricted_SC_std': np.nanstd(lam_tau_results[tau]['Unrestricted_SC']),
                'P_end': np.nanmean(lam_tau_results[tau]['P_end']),
                'P_end_std': np.nanstd(lam_tau_results[tau]['P_end']),
                'B_end': np.nanmean(lam_tau_results[tau]['B_end']),
                'B_end_std': np.nanstd(lam_tau_results[tau]['B_end']),
                'L_tail_k7': np.nanmean(lam_tau_results[tau]['L_tail_k7']),
                'L_tail_k7_std': np.nanstd(lam_tau_results[tau]['L_tail_k7'])
            }
            results.append(avg_res)
            
            print(f"\n--- Averaged Results for Lambda={lam:.2f}, Tau={tau:.2f} ---")
            print(avg_res)
        
    df = pd.DataFrame(results)
    os.makedirs('results/thresholds', exist_ok=True)
    out_path = f'results/thresholds/threshold_analysis_{datetime.now().strftime("%d_%m_%Y_%H-%M")}.csv'
    df.to_csv(out_path, index=False)
    print(f"\nAnalysis complete. Results saved to {out_path}")
    print(df.to_string())

if __name__ == "__main__":
    run_threshold_analysis()
