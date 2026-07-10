"""Ad-hoc sweep: Extension 1 (Fairness), random instance, 50 workers / 28 days,
demand pattern 25/50/25 (E/L/N), for BAP/NPP/ECP across lambda in {0,5,10,50}.
Reports undercoverage and total shift changes only.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import numpy as np
import pandas as pd
from core.worker_groups import create_groups_from_fractions
from Utils.demand import generate_demand
from extensions.fairness.loop_fairness_labeling import run_cg

LAMBDAS_SWEEP = [0.0, 5.0, 10.0, 50.0]


def main(lambdas):
    len_I, num_days, chi, prob, seed = 50, 28, 3, 1.0, 1
    T = list(range(1, num_days + 1)); I = list(range(1, len_I + 1)); K = [1, 2, 3]
    maxlen = max(len(I), len(T), len(K))
    data = pd.DataFrame({'I': I + [np.nan] * (maxlen - len(I)),
                          'T': T + [np.nan] * (maxlen - len(T)),
                          'K': K + [np.nan] * (maxlen - len(K))})
    demand_dict = generate_demand(num_days, prob, len_I, shift_probs=(25, 50, 25), delta=0.25, seed=seed)
    worker_groups = create_groups_from_fractions(I, "1/2,1/2", [(0.5, 0.5, 2, 7), (1.5, 1.5, 4, 21)])

    print(f"Extension 1 (Fairness): {len_I} workers, {num_days} days, demand=25/50/25, lambdas={lambdas}")
    for mode in ("bap", "npp", "ecp"):
        _, _, _, _, F_bar, _ = run_cg(data, demand_dict, worker_groups, chi, prob, 0.0, 0.0, mode, solver='numba')
        print(f"\n--- {mode.upper()} ---  F_bar (preprocessing) = {F_bar:.2f}")
        for lam in lambdas:
            uc, us, pl, cons, _, g = run_cg(data, demand_dict, worker_groups, chi, prob, lam, F_bar, mode, solver='numba')
            print(f"  lambda={lam:<5} undercoverage={uc:8.2f}  total_shift_changes={cons:5.0f}")


if __name__ == "__main__":
    only_lambda0 = "--lambda0-only" in sys.argv
    main([0.0] if only_lambda0 else LAMBDAS_SWEEP)
