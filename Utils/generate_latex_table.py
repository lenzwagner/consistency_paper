import pandas as pd
import numpy as np
import sys
import os

def generate_latex_table(cg_file, compact_file):
    # Load data
    df_cg = pd.read_excel(cg_file)
    
    # Load compact data (check if csv or excel)
    if compact_file.endswith('.csv'):
        df_comp = pd.read_csv(compact_file)
    else:
        df_comp = pd.read_excel(compact_file)
    
    # Sort configurations
    # Rows: 1..9 correspond to combinations of I (50, 100, 150) and pattern ('Low', 'Medium', 'High')
    configs = [
        (50, 'Low'), (50, 'Medium'), (50, 'High'),
        (100, 'Low'), (100, 'Medium'), (100, 'High'),
        (150, 'Low'), (150, 'Medium'), (150, 'High')
    ]
    
    print("% Generated LaTeX table code")
    print("\\begin{table}[pos=ht]")
    print("\\footnotesize")
    print("\\centering")
    print("    \\caption{Computational results for the compact model and the \\ac{cg} approach.}")
    print("    \\label{tab:initial_ress}")
    print("\\begin{tblr}[]{colsep = 3pt,")
    print("colspec = {@{} c *{10}{Q[c]} @{}},")
    print("  cell{1}{1} = {r=2}{},")
    print("  cell{1}{2} = {c=3}{},")
    print("  cell{1}{5} = {c=7}{}")
    print("}")
    print("\\toprule ")
    print("$m$ & Compact Model & & & Column Generation & & & & & & \\\\")
    print("\\cmidrule[lr]{2-4}")
    print("\\cmidrule[lr]{5-11} ")
    print("& LB / UB & {Gap \\\\ (\\%)\\hyperlink{tab_a}{\\textsuperscript{a}}} & {Time \\\\ (s)\\hyperlink{tab_b}{\\textsuperscript{b}}} & LB / UB & {Gap \\\\ (\\%)\\hyperlink{tab_c}{\\textsuperscript{c}}} & {Time \\\\ (s)} & {Time MP \\\\ (s)} & {Time SP \\\\ (s)} & {Time IP \\\\ (s)} & \\# Iterations \\\\")
    print("\\midrule")
    
    for m_idx, (len_I, pattern) in enumerate(configs, 1):
        # Filter CG and Compact datasets for this configuration
        sub_cg = df_cg[(df_cg['I'] == len_I) & (df_cg['pattern'] == pattern)]
        sub_comp = df_comp[(df_comp['I'] == len_I) & (df_comp['pattern'] == pattern)]
        
        # Calculate stats for Compact model
        if not sub_comp.empty:
            comp_lb_mean = sub_comp['lower_bound'].mean()
            comp_lb_std = sub_comp['lower_bound'].std()
            comp_ub_mean = sub_comp['incumbent'].mean()
            comp_ub_std = sub_comp['incumbent'].std()
            comp_gap_mean = sub_comp['gap'].mean() * 100.0 if 'gap' in sub_comp.columns else 0.0
            comp_gap_std = sub_comp['gap'].std() * 100.0 if 'gap' in sub_comp.columns else 0.0
            
            # Format nicely
            comp_lb_ub = f"{{{comp_lb_mean:.1f} / {comp_ub_mean:.1f} \\\\ ({comp_lb_std:.1f}) / ({comp_ub_std:.1f})}}"
            comp_gap = f"{{{comp_gap_mean:.2f} \\\\ ({comp_gap_std:.2f})}}"
            comp_time = "\\emph{TLR}" # Usually Time Limit Reached (TLR) for larger instances
        else:
            comp_lb_ub = "N/A"
            comp_gap = "N/A"
            comp_time = "N/A"
            
        # Calculate stats for Column Generation (BAP model)
        if not sub_cg.empty:
            cg_lb_mean = sub_cg['lbound'].mean()
            cg_lb_std = sub_cg['lbound'].std()
            cg_ub_mean = sub_cg['objval'].mean()
            cg_ub_std = sub_cg['objval'].std()
            cg_gap_mean = sub_cg['gap'].mean()
            cg_gap_std = sub_cg['gap'].std()
            cg_time_mean = sub_cg['time_total'].mean()
            cg_time_std = sub_cg['time_total'].std()
            cg_mp_mean = sub_cg['time_rmp'].mean()
            cg_mp_std = sub_cg['time_rmp'].std()
            cg_sp_mean = sub_cg['time_sp'].mean()
            cg_sp_std = sub_cg['time_sp'].std()
            cg_ip_mean = sub_cg['time_ip'].mean()
            cg_ip_std = sub_cg['time_ip'].std()
            cg_iter_mean = sub_cg['iteration'].mean()
            cg_iter_std = sub_cg['iteration'].std()
            
            cg_lb_ub = f"{{{cg_lb_mean:.1f} / {cg_ub_mean:.1f} \\\\ ({cg_lb_std:.1f}) / ({cg_ub_std:.1f})}}"
            cg_gap = f"{{{cg_gap_mean:.2f} \\\\ ({cg_gap_std:.2f})}}"
            cg_time = f"{{{cg_time_mean:.2f} \\\\ ({cg_time_std:.2f})}}"
            cg_mp = f"{{{cg_mp_mean:.2f} \\\\ ({cg_mp_std:.2f})}}"
            cg_sp = f"{{{cg_sp_mean:.2f} \\\\ ({cg_sp_std:.2f})}}"
            cg_ip = f"{{{cg_ip_mean:.2f} \\\\ ({cg_ip_std:.2f})}}"
            cg_iter = f"{{{cg_iter_mean:.1f} \\\\ ({cg_iter_std:.1f})}}"
        else:
            cg_lb_ub = "N/A"
            cg_gap = "N/A"
            cg_time = "N/A"
            cg_mp = "N/A"
            cg_sp = "N/A"
            cg_ip = "N/A"
            cg_iter = "N/A"
            
            # Use TLR if compact model timed out
            if comp_time == "N/A":
                comp_time = "\\emph{TLR}"
            
        print(f"{m_idx} & {comp_lb_ub} & {comp_gap} & {comp_time} & {cg_lb_ub} & {cg_gap} & {cg_time} & {cg_mp} & {cg_sp} & {cg_ip} & {cg_iter} \\\\")
        
    print("\\bottomrule")
    print("\\end{tblr}")
    print("\\vspace{0.2cm}")
    print("\\parbox{0.95\\linewidth}{\\scriptsize%")
    print("\\flushleft{\\emph{Aggregated values are reported as mean (std. dev) across all scenarios per instance. For \\ac{cg}, the reported \\ac{lb} is computed as the terminal \\ac{rmp}-\\ac{lp} value plus $\\left|\\mathcal{I}\\right|\\min\\{0,\\bar z^{\\mathrm{SP}}\\}$, where $\\bar z^{\\mathrm{SP}}$ is the best reduced cost returned by the generic pricing problem. At termination, this correction is zero up to numerical tolerance because no column with reduced cost below the convergence tolerance is found. The reported \\ac{ub} is the corresponding value of the final \\ac{rmp}-\\ac{ip}.}}\\\\")
    print("\\hypertarget{tab_a}{\\textsuperscript{a}} \\ac{mip}-Gap: Relative difference between the incumbent and the current best \\ac{lb}. \\quad")
    print("\\hypertarget{tab_b}{\\textsuperscript{b}} No scenario reached an optimal solution within the two-hour time limit, and results are therefore reported as \\emph{TLR} (time limit reached). \\quad \\hypertarget{tab_c}{\\textsuperscript{c}} Integrality Gap: Relative difference between the final \\ac{rmp}-\\ac{ip} solution and its \\ac{rmp}-\\ac{lp} relaxation. This is an internal indicator of how close the final \\ac{rmp} is to integrality and does not represent a gap to the global \\ac{mip} optimum.}")
    print("")
    print("\\end{table}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python generate_latex_table.py <cg_results_excel> <compact_results_excel_or_csv>")
        sys.exit(1)
    
    cg_path = sys.argv[1]
    comp_path = sys.argv[2]
    generate_latex_table(cg_path, comp_path)
