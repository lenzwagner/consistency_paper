"""Extension 2 (Off-Day Recovery): base parametrization, 100 workers, 28 days,
demand 25/50/25, prop_volatility=0.30, chi=2/4, seeds 1-25, beta in {1,2,3,4}.
BAP re-solved per beta. NPP/ECP solved once per seed, evaluated per beta."""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import numpy as np
import pandas as pd
from core.worker_groups import create_groups_from_fractions
from Utils.demand import generate_demand
from extensions.offday_recovery.loop_offday_labeling import optimize_schedule, evaluate_pool, run_cg

BETAS   = [1, 2, 3, 4]
MODES   = ["bap", "npp", "ecp"]
SEEDS   = [1]
LEN_I   = 100
NDAYS   = 28
PROB    = 1.0

I = list(range(1, LEN_I + 1))
T = list(range(1, NDAYS + 1))
K = [1, 2, 3]
maxlen = max(len(I), len(T), len(K))
data = pd.DataFrame({
    'I': I + [np.nan] * (maxlen - len(I)),
    'T': T + [np.nan] * (maxlen - len(T)),
    'K': K + [np.nan] * (maxlen - len(K)),
})
worker_groups = create_groups_from_fractions(
    I, "1/2,1/2", [(0.5, 0.5, 3, 7), (1.5, 1.5, 6, 21)])

# accumulators: results[mode][beta] = list of (uc, us, pl, cons)
results = {m: {b: [] for b in BETAS} for m in MODES}

for seed in SEEDS:
    demand_dict = generate_demand(
        NDAYS, PROB, LEN_I, shift_probs=(25, 50, 25),
        delta=0.25, seed=seed, prop_volatility=0.30)

    for mode in MODES:
        if mode == "bap":
            for beta in BETAS:
                uc, us, pl, cons = run_cg(
                    data, demand_dict, worker_groups, beta, mode, solver='numba')
                results[mode][beta].append((uc, us, pl, cons))
        else:
            master, x_by_group = optimize_schedule(
                data, demand_dict, worker_groups, mode, beta_g=1, solver='numba')
            for beta in BETAS:
                uc, us, pl, cons = evaluate_pool(
                    master, x_by_group, worker_groups, demand_dict, beta, T, K)
                results[mode][beta].append((uc, us, pl, cons))

    print(f"seed {seed:2d} done", flush=True)

print()
print(f"Average over {len(SEEDS)} seed(s)  |  I={LEN_I}, days={NDAYS}, demand=25/50/25, "
      f"vola=0.30, chi=3/6")
print(f"{'mode':>5} {'beta':>5} {'UC':>9} {'US':>9} {'PL':>9} {'Chg':>7}")
for mode in MODES:
    for beta in BETAS:
        vals = results[mode][beta]
        n = len(vals)
        avg = [sum(v[i] for v in vals) / n for i in range(4)]
        print(f"{mode:>5} {beta:>5}  {avg[0]:9.2f}  {avg[1]:9.2f}  {avg[2]:9.2f}  {avg[3]:7.1f}")
