"""Seed sweep (1-25) for Extension 2 (off-day recovery, beta_g), base-case
group parameterization (chi_1=2, chi_2=4, 50:50 split), 100 workers, 28 days,
demand pulled from data/demand_data.xlsx (Pattern='Medium', matches instance
m=5 in Analysis.tex). All three paradigms (BAP/NPP/ECP), solved with the
Numba subproblem using BIDIRECTIONAL labeling, beta_g swept as integers 1-4.

CAVEAT: bidirectional labeling (_use_bidir=True, set automatically by
optimize_schedule() whenever solver='numba') was found earlier in this
project's testing to produce suboptimal (non-exact) reduced costs at
n_days>=8 combined with chi>=3 -- exactly the regime used here (n_days=28,
chi_2=4). Results from this script are therefore NOT guaranteed exact;
compare against a forward-only (_use_bidir=False) run before trusting them
for any paper-facing claim.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import numpy as np
import pandas as pd
from core.worker_groups import create_groups_from_fractions
from Utils.gcutil import read_demand
from extensions.offday_recovery.loop_offday_labeling import optimize_schedule, evaluate_pool

SEEDS = list(range(1, 26))
BETAS = [1, 2, 3, 4]
NUM_DAYS, LEN_I = 28, 100
DEMAND_FILE = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'demand_data.xlsx')
PATTERN = 'Medium'

T = list(range(1, NUM_DAYS + 1))
I = list(range(1, LEN_I + 1))
K = [1, 2, 3]
maxlen = max(len(I), len(T), len(K))

worker_groups = create_groups_from_fractions(I, "1/2,1/2", [(0.5, 0.5, 3, 7), (1.5, 1.5, 6, 21)])


def build_data():
    return pd.DataFrame({'I': I + [np.nan] * (maxlen - len(I)),
                          'T': T + [np.nan] * (maxlen - len(T)),
                          'K': K + [np.nan] * (maxlen - len(K))})


def run_all_seeds():
    rows = []
    for seed in SEEDS:
        demand_dict = read_demand(DEMAND_FILE, LEN_I, PATTERN, seed)
        if not demand_dict:
            print(f"seed={seed}: no demand data, skipping")
            continue
        data = build_data()

        # BAP: pricing depends on beta_g -> re-solve CG per beta
        for beta in BETAS:
            master, x_by_group = optimize_schedule(data, demand_dict, worker_groups, 'bap',
                                                     beta_g=beta, solver='numba')
            uc, us, pl, ch = evaluate_pool(master, x_by_group, worker_groups, demand_dict, beta, T, K)
            rows.append(dict(seed=seed, mode='bap', beta_g=beta, undercoverage=uc,
                              understaffing=us, perfloss=pl, changes=ch))
            print(f"seed={seed} bap    beta_g={beta} uc={uc:8.2f} us={us:8.2f} pl={pl:8.2f} ch={ch:6.1f}")

        # NPP/ECP: pricing is beta_g-invariant -> solve once at beta_g=1, evaluate per beta
        for mode in ('npp', 'ecp'):
            master, x_by_group = optimize_schedule(data, demand_dict, worker_groups, mode,
                                                     beta_g=1, solver='numba')
            for beta in BETAS:
                uc, us, pl, ch = evaluate_pool(master, x_by_group, worker_groups, demand_dict, beta, T, K)
                rows.append(dict(seed=seed, mode=mode, beta_g=beta, undercoverage=uc,
                                  understaffing=us, perfloss=pl, changes=ch))
                print(f"seed={seed} {mode:5s} beta_g={beta} uc={uc:8.2f} us={us:8.2f} pl={pl:8.2f} ch={ch:6.1f}")

    df = pd.DataFrame(rows)
    return df


if __name__ == "__main__":
    df = run_all_seeds()
    out_csv = os.path.join(os.path.dirname(__file__), 'seed_sweep_beta_bidir_results.csv')
    df.to_csv(out_csv, index=False)
    print(f"\nSaved {len(df)} rows to {out_csv}")

    summary = df.groupby(['mode', 'beta_g'])[['undercoverage', 'understaffing', 'perfloss', 'changes']].agg(['mean', 'std'])
    print("\n=== Summary across seeds ===")
    print(summary)
