import os
import argparse
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

def parse_args():
    parser = argparse.ArgumentParser(description="Analyze sensitivity study CSV results.")
    parser.add_argument(
        "--file", 
        type=str, 
        default="sensitivity_results_100.csv", 
        help="Path to the CSV file to analyze (default: sensitivity_results_100.csv)"
    )
    parser.add_argument(
        "--output-dir", 
        type=str, 
        default="plots", 
        help="Directory to save generated plots (default: plots)"
    )
    parser.add_argument(
        "--report", 
        type=str, 
        default="sensitivity_analysis_report.md", 
        help="Path to save the Markdown report (default: sensitivity_analysis_report.md)"
    )
    return parser.parse_args()

def analyze_data(file_path, output_dir, report_path):
    if not os.path.exists(file_path):
        print(f"Error: File {file_path} not found.")
        return
        
    print(f"Loading data from {file_path}...")
    
    # We only load the columns we need to save memory and processing time
    cols_to_load = [
        'seed', 'matrix', 'chi', 'alpha', 'type', 'gamma_r', 'gamma_c', 
        'bap_obj', 'npp_nom', 'npp_expost', 'improvement_pct', 'time',
        'undercover_behavior', 'undercover_norm_behavior', 
        'cons_behavior', 'cons_norm_behavior', 
        'perf_behavior', 'perf_norm_behavior',
        'understaffing_behavior', 'understaffing_norm_behavior',
        'undercover_naive', 'undercover_norm_naive', 
        'cons_naive', 'cons_norm_naive', 
        'perf_naive', 'perf_norm_naive',
        'understaffing_naive', 'understaffing_norm_naive',
        'gini_sc_behavior', 'gini_sc_naive',
        'gini_perf_behavior', 'gini_perf_naive'
    ]
    
    try:
        # Read headers first to see if any expected column is missing
        header_df = pd.read_csv(file_path, nrows=0)
        available_cols = [c for c in cols_to_load if c in header_df.columns]
        missing_cols = [c for c in cols_to_load if c not in header_df.columns]
        if missing_cols:
            print(f"Warning: The following expected columns are missing from the CSV: {missing_cols}")
            
        df = pd.read_csv(file_path, usecols=available_cols)
    except Exception as e:
        print(f"Failed to load CSV file: {e}")
        return
        
    print(f"Loaded {len(df)} rows.")
    
    # Clean and preprocess columns
    # Round float parameters to avoid float representation issues
    if 'chi' in df.columns:
        df['chi'] = df['chi'].round(2)
    if 'alpha' in df.columns:
        df['alpha'] = df['alpha'].round(4)
        
    # Re-calculate improvement percentage if missing or for verification
    # improvement_pct = (npp_expost - bap_obj) / npp_expost * 100
    if 'bap_obj' in df.columns and 'npp_expost' in df.columns:
        # Avoid division by zero
        df['calc_improvement_pct'] = np.where(
            df['npp_expost'] > 1e-5,
            (df['npp_expost'] - df['bap_obj']) / df['npp_expost'] * 100,
            0.0
        )
        # Use calculated improvement as primary metric
        df['improvement_pct'] = df['calc_improvement_pct']
        
    # Let's ensure directories exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Report lists
    report_lines = []
    report_lines.append("# Sensitivity Study Analysis Report")
    report_lines.append(f"**Analyzed File:** `{file_path}`  ")
    report_lines.append(f"**Total Runs (Configurations & Seeds):** {len(df)}  ")
    report_lines.append(f"**Date:** {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # --- 1. OVERALL SUMMARY ---
    report_lines.append("## 1. Executive Summary")
    report_lines.append("This section compares the Behavior-Aware Column Generation (BAP) model against the Naive model (ex-post evaluation under the true nonlinear fatigue dynamics).")
    
    summary_metrics = {
        "Metric": [
            "Objective Value",
            "Undercoverage (Total)",
            "Undercoverage (Norm)",
            "Consistency / Shift Changes (Total)",
            "Consistency / Shift Changes (Norm)",
            "Understaffing (Norm)",
            "Gini Index (Shift Changes)",
            "Gini Index (Performance/Fatigue)"
        ],
        "BAP (Behavior-Aware)": [
            df['bap_obj'].mean() if 'bap_obj' in df.columns else np.nan,
            df['undercover_behavior'].mean() if 'undercover_behavior' in df.columns else np.nan,
            df['undercover_norm_behavior'].mean() if 'undercover_norm_behavior' in df.columns else np.nan,
            df['cons_behavior'].mean() if 'cons_behavior' in df.columns else np.nan,
            df['cons_norm_behavior'].mean() if 'cons_norm_behavior' in df.columns else np.nan,
            df['understaffing_norm_behavior'].mean() if 'understaffing_norm_behavior' in df.columns else np.nan,
            df['gini_sc_behavior'].mean() if 'gini_sc_behavior' in df.columns else np.nan,
            df['gini_perf_behavior'].mean() if 'gini_perf_behavior' in df.columns else np.nan
        ],
        "Naive (Ex-Post)": [
            df['npp_expost'].mean() if 'npp_expost' in df.columns else np.nan,
            df['undercover_naive'].mean() if 'undercover_naive' in df.columns else np.nan,
            df['undercover_norm_naive'].mean() if 'undercover_norm_naive' in df.columns else np.nan,
            df['cons_naive'].mean() if 'cons_naive' in df.columns else np.nan,
            df['cons_norm_naive'].mean() if 'cons_norm_naive' in df.columns else np.nan,
            df['understaffing_norm_naive'].mean() if 'understaffing_norm_naive' in df.columns else np.nan,
            df['gini_sc_naive'].mean() if 'gini_sc_naive' in df.columns else np.nan,
            df['gini_perf_naive'].mean() if 'gini_perf_naive' in df.columns else np.nan
        ]
    }
    
    summary_df = pd.DataFrame(summary_metrics)
    summary_df['Relative Difference (%)'] = np.where(
        summary_df['Naive (Ex-Post)'] > 1e-5,
        ((summary_df['BAP (Behavior-Aware)'] - summary_df['Naive (Ex-Post)']) / summary_df['Naive (Ex-Post)'] * 100),
        0.0
    )
    
    # Format table for output
    summary_table_md = summary_df.to_markdown(index=False, floatfmt=".4f")
    report_lines.append(summary_table_md)
    report_lines.append("\n")
    
    avg_imp = df['improvement_pct'].mean()
    max_imp = df['improvement_pct'].max()
    min_imp = df['improvement_pct'].min()
    
    report_lines.append(f"- **Average Outperformance of BAP over Naive ex-post:** {avg_imp:.2f}%")
    report_lines.append(f"- **Maximum Outperformance:** {max_imp:.2f}%")
    report_lines.append(f"- **Minimum Outperformance:** {min_imp:.2f}%\n")
    
    # --- 2. ANALYSIS BY MATRIX ---
    if 'matrix' in df.columns:
        report_lines.append("## 2. Sensitivity to Matrix Scaling (Delta)")
        matrix_group = df.groupby('matrix').agg(
            bap_obj_mean=('bap_obj', 'mean'),
            naive_obj_mean=('npp_expost', 'mean'),
            imp_mean=('improvement_pct', 'mean'),
            undercover_bap_mean=('undercover_norm_behavior', 'mean'),
            undercover_naive_mean=('undercover_norm_naive', 'mean'),
            cons_bap_mean=('cons_norm_behavior', 'mean'),
            cons_naive_mean=('cons_norm_naive', 'mean'),
            count=('seed', 'count')
        ).reset_index()
        
        matrix_table = matrix_group.to_markdown(index=False, floatfmt=".4f")
        report_lines.append(matrix_table)
        report_lines.append("\n")
        
    # --- 3. ANALYSIS BY CHI (FATIGUE SCALING) ---
    if 'chi' in df.columns:
        report_lines.append("## 3. Sensitivity to Fatigue Scaling (Chi)")
        chi_group = df.groupby('chi').agg(
            bap_obj_mean=('bap_obj', 'mean'),
            naive_obj_mean=('npp_expost', 'mean'),
            imp_mean=('improvement_pct', 'mean'),
            undercover_bap_mean=('undercover_norm_behavior', 'mean'),
            undercover_naive_mean=('undercover_norm_naive', 'mean'),
            cons_bap_mean=('cons_norm_behavior', 'mean'),
            cons_naive_mean=('cons_norm_naive', 'mean')
        ).reset_index()
        
        chi_table = chi_group.to_markdown(index=False, floatfmt=".4f")
        report_lines.append(chi_table)
        report_lines.append("\n")
        
    # --- 4. ANALYSIS BY ALPHA (RECOVERY RATE) ---
    if 'alpha' in df.columns:
        report_lines.append("## 4. Sensitivity to Recovery Rate (Alpha)")
        alpha_group = df.groupby('alpha').agg(
            bap_obj_mean=('bap_obj', 'mean'),
            naive_obj_mean=('npp_expost', 'mean'),
            imp_mean=('improvement_pct', 'mean'),
            undercover_bap_mean=('undercover_norm_behavior', 'mean'),
            undercover_naive_mean=('undercover_norm_naive', 'mean'),
            cons_bap_mean=('cons_norm_behavior', 'mean'),
            cons_naive_mean=('cons_norm_naive', 'mean')
        ).reset_index()
        
        alpha_table = alpha_group.to_markdown(index=False, floatfmt=".4f")
        report_lines.append(alpha_table)
        report_lines.append("\n")
        
    # --- 5. ANALYSIS BY TYPE (CONVEXITY/CONCAVITY) ---
    if 'type' in df.columns:
        report_lines.append("## 5. Sensitivity to Fatigue Model Type (Convex/Concave Transitions)")
        type_group = df.groupby('type').agg(
            bap_obj_mean=('bap_obj', 'mean'),
            naive_obj_mean=('npp_expost', 'mean'),
            imp_mean=('improvement_pct', 'mean'),
            undercover_bap_mean=('undercover_norm_behavior', 'mean'),
            undercover_naive_mean=('undercover_norm_naive', 'mean'),
            cons_bap_mean=('cons_norm_behavior', 'mean'),
            cons_naive_mean=('cons_norm_naive', 'mean')
        ).reset_index()
        
        type_table = type_group.to_markdown(index=False, floatfmt=".4f")
        report_lines.append(type_table)
        report_lines.append("\n")

    # --- 6. INEQUALITY ANALYSIS ---
    report_lines.append("## 6. Inequality and Workload Distribution")
    report_lines.append("Comparison of Gini coefficients showing the distribution inequality of shift changes (schedule consistency) and performance loss (fatigue-based productivity reduction) among workers.")
    
    gini_sc_bap = df['gini_sc_behavior'].mean() if 'gini_sc_behavior' in df.columns else np.nan
    gini_sc_naive = df['gini_sc_naive'].mean() if 'gini_sc_naive' in df.columns else np.nan
    gini_perf_bap = df['gini_perf_behavior'].mean() if 'gini_perf_behavior' in df.columns else np.nan
    gini_perf_naive = df['gini_perf_naive'].mean() if 'gini_perf_naive' in df.columns else np.nan

    report_lines.append(f"- **Gini Index (Consistency - BAP):** {gini_sc_bap:.4f}" if not np.isnan(gini_sc_bap) else "- **Gini Index (Consistency - BAP):** N/A")
    report_lines.append(f"- **Gini Index (Consistency - Naive):** {gini_sc_naive:.4f}" if not np.isnan(gini_sc_naive) else "- **Gini Index (Consistency - Naive):** N/A")
    report_lines.append(f"- **Gini Index (Fatigue - BAP):** {gini_perf_bap:.4f}" if not np.isnan(gini_perf_bap) else "- **Gini Index (Fatigue - BAP):** N/A")
    report_lines.append(f"- **Gini Index (Fatigue - Naive):** {gini_perf_naive:.4f}" if not np.isnan(gini_perf_naive) else "- **Gini Index (Fatigue - Naive):** N/A")
    report_lines.append("")

    # Write report
    with open(report_path, "w") as f:
        f.write("\n".join(report_lines))
    print(f"Markdown report written to {report_path}")
    
    # Print the Executive Summary table to stdout
    print("\n" + "="*50)
    print("EXECUTIVE SUMMARY: BAP vs NAIVE OVERALL AVERAGES")
    print("="*50)
    print(summary_df.to_string(index=False))
    print("="*50)
    print(f"Average outperformance of BAP over Naive ex-post: {avg_imp:.2f}%")
    print(f"Maximum outperformance: {max_imp:.2f}%")
    print("="*50 + "\n")
    
    # --- VISUALIZATIONS ---
    print("Generating visualization plots...")
    
    # Styling configurations
    plt.rcParams.update({
        'font.size': 11,
        'axes.labelsize': 12,
        'axes.titlesize': 14,
        'xtick.labelsize': 10,
        'ytick.labelsize': 10,
        'figure.titlesize': 16,
        'grid.alpha': 0.3
    })
    
    # Custom colors: BAP (Teal/Indigo), Naive (Coral/Amber)
    c_bap = '#1f77b4' # Rich Blue
    c_naive = '#ff7f0e' # Bright Orange
    
    # 1. Undercoverage by Chi and Fatigue Type
    if 'chi' in df.columns and 'type' in df.columns:
        fig, axes = plt.subplots(2, 2, figsize=(14, 10), sharex=True, sharey=True)
        axes = axes.flatten()
        types = sorted(df['type'].unique())
        
        for i, t in enumerate(types[:4]):
            ax = axes[i]
            df_t = df[df['type'] == t]
            
            # Group by chi
            grouped = df_t.groupby('chi').agg(
                uc_bap=('undercover_norm_behavior', 'mean'),
                uc_naive=('undercover_norm_naive', 'mean')
            ).reset_index()
            
            # Plot
            x = np.arange(len(grouped['chi']))
            width = 0.35
            
            ax.bar(x - width/2, grouped['uc_bap'], width, label='BAP', color=c_bap, alpha=0.85)
            ax.bar(x + width/2, grouped['uc_naive'], width, label='Naive (Ex-Post)', color=c_naive, alpha=0.85)
            
            ax.set_title(f"Fatigue Type: {t.upper()}")
            ax.set_xticks(x)
            ax.set_xticklabels(grouped['chi'])
            ax.grid(True, linestyle='--', alpha=0.5)
            
            if i in [0, 2]:
                ax.set_ylabel("Norm. Undercoverage")
            if i in [2, 3]:
                ax.set_xlabel("Fatigue Scaling (Chi)")
            if i == 0:
                ax.legend()
                
        fig.suptitle("Normalized Undercoverage by Chi and Fatigue Transition Type", y=0.98)
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, "bap_vs_naive_undercoverage.png"), dpi=300)
        plt.close()
        print(f"Saved: {os.path.join(output_dir, 'bap_vs_naive_undercoverage.png')}")
        
    # 2. Consistency vs Undercoverage Tradeoff Curve
    if 'cons_norm_behavior' in df.columns and 'undercover_norm_behavior' in df.columns:
        plt.figure(figsize=(10, 7))
        
        # Group by matrix, chi, alpha, type
        grouped_all = df.groupby(['matrix', 'chi', 'alpha', 'type']).agg(
            uc_bap=('undercover_norm_behavior', 'mean'),
            uc_naive=('undercover_norm_naive', 'mean'),
            cons_bap=('cons_norm_behavior', 'mean'),
            cons_naive=('cons_norm_naive', 'mean')
        ).reset_index()
        
        plt.scatter(
            grouped_all['cons_bap'], 
            grouped_all['uc_bap'], 
            color=c_bap, 
            alpha=0.6, 
            label='BAP (Behavior-Aware)', 
            edgecolors='none', 
            s=40
        )
        plt.scatter(
            grouped_all['cons_naive'], 
            grouped_all['uc_naive'], 
            color=c_naive, 
            alpha=0.6, 
            label='Naive (Ex-Post)', 
            edgecolors='none', 
            s=40
        )
        
        # Draw arrows connecting matching configurations to show change direction
        # Limit to a subset if there are too many, or just plot to show movement
        # Let's draw arrows for a representative subset
        if len(grouped_all) <= 50:
            for idx, row in grouped_all.iterrows():
                plt.annotate(
                    "", 
                    xy=(row['cons_bap'], row['uc_bap']), 
                    xytext=(row['cons_naive'], row['uc_naive']),
                    arrowprops=dict(arrowstyle="->", color='gray', lw=0.5, alpha=0.5)
                )
                
        plt.title("Performance Trade-off: Consistency vs Undercoverage")
        plt.xlabel("Schedule Consistency Metric (Higher = More shift changes/Less consistent)")
        plt.ylabel("Normalized Undercoverage (Lower is better)")
        plt.legend(frameon=True)
        plt.grid(True, linestyle='--', alpha=0.5)
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, "consistency_vs_undercoverage_tradeoff.png"), dpi=300)
        plt.close()
        print(f"Saved: {os.path.join(output_dir, 'consistency_vs_undercoverage_tradeoff.png')}")
        
    # 3. Gini Inequality Index Comparison
    if 'gini_sc_behavior' in df.columns:
        plt.figure(figsize=(8, 6))
        
        metrics = ['Consistency Gini', 'Fatigue Gini']
        bap_gini = [df['gini_sc_behavior'].mean(), df['gini_perf_behavior'].mean()]
        naive_gini = [df['gini_sc_naive'].mean(), df['gini_perf_naive'].mean()]
        
        x = np.arange(len(metrics))
        width = 0.35
        
        plt.bar(x - width/2, bap_gini, width, label='BAP', color=c_bap, alpha=0.85)
        plt.bar(x + width/2, naive_gini, width, label='Naive (Ex-Post)', color=c_naive, alpha=0.85)
        
        plt.title("Gini Inequality Index Comparison (Lower is more equal)")
        plt.xticks(x, metrics)
        plt.ylabel("Gini Coefficient")
        plt.legend()
        plt.grid(True, linestyle='--', alpha=0.5)
        
        # Add labels on top of bars
        for idx, val in enumerate(bap_gini):
            plt.text(idx - width/2, val + 0.005, f"{val:.4f}", ha='center', va='bottom', fontsize=9)
        for idx, val in enumerate(naive_gini):
            plt.text(idx + width/2, val + 0.005, f"{val:.4f}", ha='center', va='bottom', fontsize=9)
            
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, "inequality_comparison.png"), dpi=300)
        plt.close()
        print(f"Saved: {os.path.join(output_dir, 'inequality_comparison.png')}")
        
    print("\nAnalysis complete! All outputs generated successfully.")

if __name__ == "__main__":
    args = parse_args()
    analyze_data(args.file, args.output_dir, args.report)
