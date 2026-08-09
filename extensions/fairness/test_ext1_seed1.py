"""Test Extension 1 (Fairness) with I=100, num_days=28, seed=1, all modes."""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import pandas as pd
import numpy as np
from core.base_case import get_wd_constraints
from core.masterproblem import MasterProblem
from core.worker_groups import create_groups_from_fractions
from Utils.demand import generate_demand
from extensions.fairness.loop_fairness_labeling import run_cg, MU, LAMBDAS, gini

if __name__ == "__main__":
    len_I = 20
    num_days = 14
    chi = 3
    prob = 1.0
    seed = 1

    # Create data
    I = list(range(1, len_I + 1))
    T = list(range(1, num_days + 1))
    K = [1, 2, 3]

    maxlen = max(len(I), len(T), len(K))
    data = pd.DataFrame({
        'I': I + [np.nan] * (maxlen - len(I)),
        'T': T + [np.nan] * (maxlen - len(T)),
        'K': K + [np.nan] * (maxlen - len(K))
    })

    # Generate demand with seed=1
    demand_dict = generate_demand(num_days, prob, len_I, shift_probs=(50, 30, 20), delta=0.25, seed=seed)

    # Worker groups: 50/50 split into resilient/sensitive
    worker_groups = create_groups_from_fractions(I, "1/2,1/2", [(0.5, 0.5, 2, 7), (1.5, 1.5, 4, 21)])

    print("\n" + "="*80)
    print(f"Extension 1 (Fairness, DP-Labeling): I={len_I}, days={num_days}, seed={seed}")
    print("="*80 + "\n")

    # Run for each mode
    for mode in ("bap", "npp", "ecp"):
        print("\n" + "-"*80)
        print(f"MODE: {mode.upper()}")
        print("-"*80)

        # Step 1: preprocessing solve at lambda=0 to fix F_bar
        print("\n  [Preprocessing at lambda=0 to compute F_bar...]")
        _, _, _, _, F_bar, _ = run_cg(data, demand_dict, worker_groups, chi, prob, 0.0, 0.0, mode)
        print(f"  OK F_bar (mean burden) = {F_bar:.4f}\n")

        # Step 2: solve for each lambda value
        print(f"  {'lambda':>6} {'UC':>9} {'US':>9} {'PL':>9} {'Changes':>8} {'Gini(F)':>10}")
        print("  " + "-"*60)

        for lam in LAMBDAS:
            uc, us, pl, cons, _, g = run_cg(data, demand_dict, worker_groups, chi, prob, lam, F_bar, mode)
            print(f"  {lam:<6.1f} {uc:9.2f} {us:9.2f} {pl:9.2f} {cons:8.0f} {g:10.4f}")

    print("\n" + "="*80 + "\n")
