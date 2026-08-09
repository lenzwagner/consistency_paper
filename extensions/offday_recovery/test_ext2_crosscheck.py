"""Cross-validation test for Extension 2: MIP pricing (loop_offday.run_cg) vs
exact SPPRC labeling (loop_offday_labeling.run_cg), same instance
(I=20, 14 days, seed=1, varying shift-mix). If both formulations agree, the
extension is correctly implemented in both solvers.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import pandas as pd
import numpy as np
from core.worker_groups import create_groups_from_fractions
from Utils.demand import generate_demand
from extensions.offday_recovery.loop_offday import run_cg as run_mip
from extensions.offday_recovery.loop_offday_labeling import run_cg as run_lab

BETAS = [1, 2, 3]

len_I, num_days, seed = 20, 14, 1
I = list(range(1, len_I + 1)); T = list(range(1, num_days + 1)); K = [1, 2, 3]
maxlen = max(len(I), len(T), len(K))
data = pd.DataFrame({'I': I + [np.nan]*(maxlen-len(I)),
                     'T': T + [np.nan]*(maxlen-len(T)),
                     'K': K + [np.nan]*(maxlen-len(K))})
demand_dict = generate_demand(num_days, 0.7, len_I, shift_probs=(50,30,20),
                              delta=0.25, seed=seed, prop_volatility=0.30)
worker_groups = create_groups_from_fractions(I, "1/2,1/2", [(0.5,0.5,2,7),(1.5,1.5,4,21)])

print("\n" + "="*82)
print(f"Extension 2 CROSS-CHECK (MIP vs Labeling): I={len_I}, days={num_days}, seed={seed}")
print(f"  total_demand={sum(demand_dict.values())}")
print("="*82)

for mode in ("bap", "npp", "ecp"):
    print("\n" + "-"*82)
    print(f"MODE: {mode.upper()}")
    print("-"*82)
    print(f"  {'beta':>4} | {'MIP UC':>8} {'MIP PL':>8} {'MIP Chg':>8} | "
          f"{'LAB UC':>8} {'LAB PL':>8} {'LAB Chg':>8} | {'dUC':>7} {'dPL':>7}")
    print("  " + "-"*78)
    for beta in BETAS:
        m_uc, m_us, m_pl, m_ch = run_mip(data, demand_dict, worker_groups, beta, mode)
        l_uc, l_us, l_pl, l_ch = run_lab(data, demand_dict, worker_groups, beta, mode)
        print(f"  {beta:>4} | {m_uc:8.2f} {m_pl:8.2f} {m_ch:8.0f} | "
              f"{l_uc:8.2f} {l_pl:8.2f} {l_ch:8.0f} | {abs(m_uc-l_uc):7.2f} {abs(m_pl-l_pl):7.2f}")

print("\n" + "="*82)
print("Note: small dUC/dPL are expected (MIP pool search vs labeling Pareto set pick")
print("different but equally-optimal tie-broken schedules). Large gaps would signal a bug.")
print("="*82 + "\n")
