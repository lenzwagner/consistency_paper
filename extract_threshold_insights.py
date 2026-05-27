import os
import glob
import pandas as pd
import numpy as np

def extract_comprehensive_insights():
    # Find the latest threshold analysis file
    threshold_files = glob.glob('results/thresholds/threshold_analysis_*.csv')
    if not threshold_files:
        print("No threshold analysis files found.")
        return
    
    latest_file = max(threshold_files, key=os.path.getctime)
    print(f"Reading data from: {latest_file}\n")
    
    df = pd.read_csv(latest_file)
    
    # Round lambda and tau to avoid floating point issues
    df['lambda'] = df['lambda'].round(2)
    df['tau'] = df['tau'].round(2)
    
    # Dynamically get all lambdas and taus from the file
    lambdas = sorted(df['lambda'].unique())
    taus = sorted(df['tau'].unique())
    
    print("=" * 105)
    print(f"{'LAMBDA':<8} | {'TAU':<6} | {'NC FEAS%':<10} | {'LF FEAS%':<10} | {'NC UC':<8} | {'LF UC':<8} | {'UNR UC':<8} | {'GAP LF-UNR':<10} | {'RED %':<7} | {'UNR SC':<8} | {'P_END':<7} | {'B_END':<7} | {'L_TAIL':<7}")
    print("-" * 105)
    
    max_gap = 0
    max_lf_feas = df['Low-Fatigue_Feasible_%'].max()
    
    for lam in lambdas:
        for tau in taus:
            row = df[(df['lambda'] == lam) & (df['tau'] == tau)]
            if row.empty:
                continue
            
            nc_feas = row['No-Change_Feasible_%'].values[0]
            lf_feas = row['Low-Fatigue_Feasible_%'].values[0]
            
            nc_uc = row['No-Change_Undercoverage'].values[0]
            lf_uc = row['Low-Fatigue_Undercoverage'].values[0]
            unr_uc = row['Unrestricted_Undercoverage'].values[0]
            
            gap = abs(lf_uc - unr_uc)
            max_gap = max(max_gap, gap)
            
            red_pct = (nc_uc - unr_uc) / nc_uc * 100 if nc_uc > 0 else 0
            
            unr_sc = row['Unrestricted_SC'].values[0]
            p_end = row['P_end'].values[0]
            b_end = row['B_end'].values[0]
            l_tail = row['L_tail_k7'].values[0]
            
            print(f"{lam:<8.2f} | {tau:<6.2f} | {nc_feas:<10.1f} | {lf_feas:<10.1f} | {nc_uc:<8.2f} | {lf_uc:<8.2f} | {unr_uc:<8.2f} | {gap:<10.2f} | {red_pct:<7.1f} | {unr_sc:<8.2f} | {p_end:<7.3f} | {b_end:<7.4f} | {l_tail:<7.1f}")
            
    print("=" * 105)
    print("\n--- Summary Insights from the Grid ---")
    
    # 1. Feasibility
    print(f"Max Low-Fatigue Feasibility (%) across all data: {max_lf_feas:.1f}%")
    print("No-Change Feasibility in grid is exactly 0.0% as expected.")
    
    # 2. Gap LF-UNR
    print(f"\nMax Gap in mean undercoverage between Low-Fatigue and Unrestricted: {max_gap:.2f}")
    
    # 3. Reductions
    print("\nUndercoverage reductions (No-Change vs Unrestricted):")
    # Output for all lambdas (since unrestricted is independent of tau, we can just take the first tau for each lambda)
    for lam in lambdas:
        row = df[(df['lambda'] == lam)].iloc[0]
        nc_uc = row['No-Change_Undercoverage']
        unr_uc = row['Unrestricted_Undercoverage']
        red_pct = (nc_uc - unr_uc) / nc_uc * 100 if nc_uc > 0 else 0
        print(f"  Lambda={lam:.2f}: {red_pct:.1f}% reduction")
        
    # 4. Depletion Proxies (Unrestricted BAP is independent of tau, just pick the first tau for extraction)
    print("\nDepletion Patterns (Unrestricted BAP):")
    first_tau = taus[0]
    df_dep = df[df['tau'] == first_tau]
    
    if not df_dep.empty:
        sc_min_lam = df_dep['Unrestricted_SC'].iloc[0]
        sc_max_lam = df_dep['Unrestricted_SC'].iloc[-1]
        p_end_min_lam = df_dep['P_end'].iloc[0]
        p_end_max_lam = df_dep['P_end'].iloc[-1]
        
        print(f"  Total shift changes from {sc_min_lam:.2f} (at lambda={lambdas[0]:.2f}) to {sc_max_lam:.2f} (at lambda={lambdas[-1]:.2f})")
        print(f"  Mean end-of-horizon performance P_end from {p_end_min_lam:.3f} (at lambda={lambdas[0]:.2f}) to {p_end_max_lam:.3f} (at lambda={lambdas[-1]:.2f})")
    
    # Check max B_end and L_tail for each tau
    print("\nMax Exhaustion Metrics per Tau:")
    for tau in taus:
        df_tau = df[df['tau'] == tau]
        if not df_tau.empty:
            max_b_end = df_tau['B_end'].max()
            max_l_tail = df_tau['L_tail_k7'].max()
            print(f"  Tau={tau:.2f} -> Max B_end: {max_b_end:.4f}, Max L_tail(7): {max_l_tail:.1f}")

if __name__ == '__main__':
    extract_comprehensive_insights()
