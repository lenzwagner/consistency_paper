"""Cross-check: Numba-JIT pricing (SubproblemFairnessNumba) vs the exact
Python label-setting reference (SubproblemFairnessDP) for Extension 1
(Fairness), across all LAMBDAS.

Unlike the other three extensions, exact objval equality is NOT the pass
criterion here: DP's final-day dominance pruning collapses candidates by
f_bin ALONE (SubproblemFairnessDP._prune_dominated, is_final_day branch),
discarding all but the min-raw-cost label per f_bin BEFORE the terminal
lambda*|f-Fbar| penalty is applied -- looser than its own docstring claims.
Numba does not special-case the final day, so it can find a strictly better
(never worse) effective cost; verified against brute-force enumeration on a
tiny instance during development. So the pass condition is objval_numba <=
objval_dp (+tolerance), not equality.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import numpy as np
import pandas as pd
from core.base_case import get_wd_constraints
from core.worker_groups import create_groups_from_fractions
from core.subproblem_dp_extensions import SubproblemFairnessDP
from core.subproblem_dp_extensions_numba import SubproblemFairnessNumba
from Utils.demand import generate_demand
from extensions.fairness.loop_fairness import MU, LAMBDAS
from extensions.fairness.loop_fairness_labeling import run_cg

len_I, num_days, chi, seed = 8, 14, 3, 5
I = list(range(1, len_I + 1)); T = list(range(1, num_days + 1)); K = [1, 2, 3]
maxlen = max(len(I), len(T), len(K))
data = pd.DataFrame({'I': I + [np.nan]*(maxlen-len(I)),
                     'T': T + [np.nan]*(maxlen-len(T)),
                     'K': K + [np.nan]*(maxlen-len(K))})
demand_dict = generate_demand(num_days, 0.7, len_I, shift_probs=(50, 30, 20),
                              delta=0.25, seed=seed, prop_volatility=0.30)
worker_groups = create_groups_from_fractions(I, "1/2,1/2", [(0.5, 0.5, 2, 7), (1.5, 1.5, 4, 21)])
Min_WD_i, Max_WD_i = get_wd_constraints(I)

rng = np.random.default_rng(seed)
duals_ts = {(t, s): float(rng.uniform(0, 2)) for t in T for s in K}
duals_i = 0.3
F_bar = 20.0

print("\n" + "=" * 78)
print("Extension 1: direct subproblem cross-check (DP vs Numba)")
print("=" * 78)
group = next(iter(worker_groups.values()))
for lam in LAMBDAS:
    dp = SubproblemFairnessDP(duals_i, duals_ts, data, group.worker_ids[0], 0, 0.06,
                               Min_WD_i, Max_WD_i, group.chi, MU, lam, F_bar)
    nb = SubproblemFairnessNumba(duals_i, duals_ts, data, group.worker_ids[0], 0, 0.06,
                                 Min_WD_i, Max_WD_i, group.chi, MU, lam, F_bar)
    for sp in (dp, nb):
        sp.gamma_C, sp.gamma_R, sp.alpha_R, sp.delta, sp.e_max = (
            group.gamma_C, group.gamma_R, group.alpha_R, group.delta, group.e_max)
        sp.buildModel()
        sp.solveModelOpt(30)

    ok = nb.model.objval <= dp.model.objval + 2e-3
    print(f"  lambda={lam:<5} DP={dp.model.objval:10.5f}  NB={nb.model.objval:10.5f}  "
          f"(nb<=dp)={ok}  burden_dp={dp.getBurden():.2f}  burden_nb={nb.getBurden():.2f}")
    assert ok, f"lambda={lam}: Numba is worse than DP -- likely a real bug"

print("\n" + "=" * 78)
print("Extension 1: end-to-end run_cg('dp') vs run_cg('numba')")
print("=" * 78)
for mode in ("bap", "npp", "ecp"):
    for lam in LAMBDAS:
        dp_res = run_cg(data, demand_dict, worker_groups, chi, 1.0, lam, F_bar, mode, solver='dp')
        nb_res = run_cg(data, demand_dict, worker_groups, chi, 1.0, lam, F_bar, mode, solver='numba')
        print(f"  {mode.upper():>4} lam={lam:<4} | DP uc={dp_res[0]:7.2f} pl={dp_res[2]:7.2f} gini={dp_res[5]:.3f} | "
              f"NB uc={nb_res[0]:7.2f} pl={nb_res[2]:7.2f} gini={nb_res[5]:.3f}")

print("\nFairness: per-subproblem checks PASSED (see end-to-end table above)\n")
