"""Test Extension 2 (Off-Day Recovery, beta_g) with I=20, num_days=14, seed=1,
beta in {1,2,3}, all modes (BAP/NPP/ECP). Uses the exact SPPRC labeling solver.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import pandas as pd
import numpy as np
from core.worker_groups import create_groups_from_fractions
from Utils.demand import generate_demand
from extensions.offday_recovery.loop_offday_labeling import optimize_schedule, evaluate_pool, run_cg

BETAS = [1, 2, 3]

if __name__ == "__main__":
    len_I = 20
    num_days = 14
    prob = 1.0
    seed = 1

    I = list(range(1, len_I + 1))
    T = list(range(1, num_days + 1))
    K = [1, 2, 3]

    maxlen = max(len(I), len(T), len(K))
    data = pd.DataFrame({
        'I': I + [np.nan] * (maxlen - len(I)),
        'T': T + [np.nan] * (maxlen - len(T)),
        'K': K + [np.nan] * (maxlen - len(K))
    })

    # Demand with a day-to-day varying shift MIX (prop_volatility>0) and more slack
    # (prob<1) so that (a) BAP has a genuine shift-change incentive and (b) the
    # regime is not purely structurally understaffed.
    demand_prob = 0.7
    prop_vol = 0.30
    demand_dict = generate_demand(num_days, demand_prob, len_I, shift_probs=(50, 30, 20),
                                  delta=0.25, seed=seed, prop_volatility=prop_vol)
    worker_groups = create_groups_from_fractions(I, "1/2,1/2", [(0.5, 0.5, 2, 7), (1.5, 1.5, 4, 21)])

    total_demand = sum(demand_dict.values())
    print("\n" + "="*78)
    print(f"Extension 2 (Off-Day Recovery, DP-Labeling): I={len_I}, days={num_days}, seed={seed}")
    print(f"  demand_prob={demand_prob}, prop_volatility={prop_vol}, total_demand={total_demand}")
    print(f"  (capacity ~= {len_I} workers x 10 workdays = 200 worker-days)")
    print("="*78 + "\n")

    for mode in ("bap", "npp", "ecp"):
        print("\n" + "-"*78)
        print(f"MODE: {mode.upper()}")
        print("-"*78)
        print(f"  {'beta':>5} {'UC':>9} {'US':>9} {'PL':>9} {'Changes':>8}")
        print("  " + "-"*46)
        if mode == "bap":
            # BAP pricing genuinely depends on beta_g -> re-solve per beta.
            for beta in BETAS:
                uc, us, pl, cons = run_cg(data, demand_dict, worker_groups, beta, mode)
                print(f"  {beta:>5} {uc:9.2f} {us:9.2f} {pl:9.2f} {cons:8.0f}")
        else:
            # NPP/ECP pricing is beta_g-invariant -> solve once, evaluate ex-post per beta.
            master, x_by_group = optimize_schedule(data, demand_dict, worker_groups, mode, beta_g=1)
            for beta in BETAS:
                uc, us, pl, cons = evaluate_pool(master, x_by_group, worker_groups, demand_dict, beta, T, K)
                print(f"  {beta:>5} {uc:9.2f} {us:9.2f} {pl:9.2f} {cons:8.0f}")

    print("\n" + "="*78 + "\n")
