"""Cross-check: Numba-JIT pricing (SubproblemPreferencesNumba) vs the exact
Python label-setting reference (SubproblemPreferencesDP) for Extension 3
(Worker Day-Off Preferences), across all LAMBDAS_P.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import random
import numpy as np
import pandas as pd
from core.base_case import get_wd_constraints
from core.worker_groups import create_groups_from_fractions
from core.subproblem_dp_extensions import SubproblemPreferencesDP
from core.subproblem_dp_extensions_numba import SubproblemPreferencesNumba
from Utils.demand import generate_demand
from extensions.preferences.loop_preferences import make_singleton_groups, LAMBDAS_P
from extensions.preferences.loop_preferences_labeling import run_cg

random.seed(7)
len_I, num_days, seed = 8, 14, 4
I = list(range(1, len_I + 1)); T = list(range(1, num_days + 1)); K = [1, 2, 3]
maxlen = max(len(I), len(T), len(K))
data = pd.DataFrame({'I': I + [np.nan]*(maxlen-len(I)),
                     'T': T + [np.nan]*(maxlen-len(T)),
                     'K': K + [np.nan]*(maxlen-len(K))})
demand_dict = generate_demand(num_days, 0.7, len_I, shift_probs=(50, 30, 20),
                              delta=0.25, seed=seed, prop_volatility=0.30)
base_groups = create_groups_from_fractions(I, "1/2,1/2", [(0.5, 0.5, 2, 7), (1.5, 1.5, 4, 21)])
singleton_groups = make_singleton_groups(I, base_groups)
Min_WD_i, Max_WD_i = get_wd_constraints(I)
pref_by_worker = {w: random.sample(T, random.randint(1, 2)) for w in I}

rng = np.random.default_rng(seed)
duals_ts = {(t, s): float(rng.uniform(0, 2)) for t in T for s in K}
duals_i = 0.3

print("\n" + "=" * 78)
print("Extension 3: direct subproblem cross-check (DP vs Numba)")
print("=" * 78)
group = next(iter(singleton_groups.values()))
wid = group.worker_ids[0]
for lam_pref in LAMBDAS_P:
    dp = SubproblemPreferencesDP(duals_i, duals_ts, data, wid, 0, 0.06, Min_WD_i, Max_WD_i,
                                  group.chi, pref_by_worker.get(wid, []), lam_pref)
    nb = SubproblemPreferencesNumba(duals_i, duals_ts, data, wid, 0, 0.06, Min_WD_i, Max_WD_i,
                                    group.chi, pref_by_worker.get(wid, []), lam_pref)
    for sp in (dp, nb):
        sp.gamma_C, sp.gamma_R, sp.alpha_R, sp.delta, sp.e_max = (
            group.gamma_C, group.gamma_R, group.alpha_R, group.delta, group.e_max)
        sp.buildModel()
        sp.solveModelOpt(30)

    obj_diff = abs(dp.model.objval - nb.model.objval)
    x_dp, x_nb = dp.getOptX(), nb.getOptX()
    x_match = all(abs(x_dp.get(k, 0) - x_nb.get(k, 0)) < 1e-6 for k in set(x_dp) | set(x_nb))
    print(f"  lambda_P={lam_pref:<5} DP={dp.model.objval:10.5f}  NB={nb.model.objval:10.5f}  "
          f"|diff|={obj_diff:.2e}  x_match={x_match}")
    assert x_match, f"lambda_P={lam_pref}: chosen schedule differs between DP and Numba"
    assert obj_diff < 2e-3, f"lambda_P={lam_pref}: reduced cost differs by more than quantization noise"

print("\n" + "=" * 78)
print("Extension 3: end-to-end run_cg('dp') vs run_cg('numba')")
print("=" * 78)
for mode in ("bap", "npp", "ecp"):
    for lam_pref in LAMBDAS_P:
        dp_res = run_cg(data, demand_dict, singleton_groups, pref_by_worker, lam_pref, mode, solver='dp')
        nb_res = run_cg(data, demand_dict, singleton_groups, pref_by_worker, lam_pref, mode, solver='numba')
        print(f"  {mode.upper():>4} lam={lam_pref:<4} | DP uc={dp_res[0]:7.2f} pl={dp_res[2]:7.2f} sat={dp_res[4]:.2f} | "
              f"NB uc={nb_res[0]:7.2f} pl={nb_res[2]:7.2f} sat={nb_res[4]:.2f}")

print("\nPreferences: per-subproblem checks PASSED (see end-to-end table above)\n")
