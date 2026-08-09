"""Extension 1: Pareto frontier comparison -- at a MATCHED fairness level
(Gini(F)), which policy achieves lower undercoverage? This isolates the pure
efficiency effect of the BAP from the trivial observation that different
lambda values trace out different points on each policy's own curve.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import numpy as np
import pandas as pd
from core.worker_groups import create_groups_from_fractions
from Utils.demand import generate_demand
from extensions.fairness.loop_fairness_labeling import run_cg as run_fair

len_I, num_days, chi, prob, seed = 10, 14, 3, 0.7, 1
T = list(range(1, num_days + 1)); I = list(range(1, len_I + 1)); K = [1, 2, 3]
maxlen = max(len(I), len(T), len(K))
data = pd.DataFrame({'I': I + [np.nan]*(maxlen-len(I)),
                     'T': T + [np.nan]*(maxlen-len(T)),
                     'K': K + [np.nan]*(maxlen-len(K))})
demand_dict = generate_demand(num_days, prob, len_I, shift_probs=(25, 50, 25),
                              delta=0.25, seed=seed, prop_volatility=0.30)
worker_groups = create_groups_from_fractions(I, "1/2,1/2", [(0.5, 0.5, 2, 7), (1.5, 1.5, 4, 21)])

LAMBDA_GRID = [0.0, 0.1, 0.25, 0.5, 1.0, 1.5, 2.0, 3.0]
MAX_ITR_TEST = 60

if __name__ == "__main__":
    print("="*78)
    print(f"Extension 1: Pareto frontier (Gini, UC) per mode, I={len_I}, days={num_days}")
    print("="*78)

    curves = {}
    for mode in ("bap", "npp", "ecp"):
        _, _, _, _, F_bar, _ = run_fair(data, demand_dict, worker_groups, chi, prob, 0.0, 0.0, mode,
                                        max_itr=MAX_ITR_TEST)
        pts = []
        for lam in LAMBDA_GRID:
            uc, us, pl, cons, _, g = run_fair(data, demand_dict, worker_groups, chi, prob, lam, F_bar, mode,
                                              max_itr=MAX_ITR_TEST)
            pts.append((g, uc, lam))
            print(f"  {mode:>5} lambda={lam:<5.2f} Gini={g:.4f}  UC={uc:.2f}", flush=True)
        curves[mode] = pts

    # For a few target Gini levels, interpolate/find nearest point on each
    # policy's own curve and compare UC at that matched fairness level.
    print("\n" + "-"*78)
    print("Gini-matched comparison (nearest point on each policy's curve)")
    print("-"*78)
    target_ginis = [0.15, 0.05, 0.01]
    print(f"  {'target_Gini':>12} {'bap_UC':>9} {'npp_UC':>9} {'ecp_UC':>9}")
    for tg in target_ginis:
        row = []
        for mode in ("bap", "npp", "ecp"):
            pts = curves[mode]
            nearest = min(pts, key=lambda p: abs(p[0] - tg))
            row.append(nearest[1])
        print(f"  {tg:>12.3f} {row[0]:9.2f} {row[1]:9.2f} {row[2]:9.2f}", flush=True)

    print("\n" + "="*78)
