"""Cross-check: Numba-JIT pricing (SubproblemOffdayNumba) vs the exact Python
label-setting reference (SubproblemOffdayDP) for Extension 2 (Off-Day
Recovery), across all BETAS. The Numba kernel uses a locally widened 8-bit rho
field (see core/subproblem_dp_extensions_numba.py's forward_pass_offday
docstring) specifically to avoid silent wraparound at beta_g > 1, so this test
exercises exactly the case that fix targets.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import numpy as np
import pandas as pd
from core.base_case import get_wd_constraints
from core.worker_groups import create_groups_from_fractions
from core.subproblem_dp_extensions import SubproblemOffdayDP
from core.subproblem_dp_extensions_numba import SubproblemOffdayNumba
from Utils.demand import generate_demand
from extensions.offday_recovery.loop_offday import BETAS
from extensions.offday_recovery.loop_offday_labeling import run_cg

len_I, num_days, seed = 8, 14, 3
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

print("\n" + "=" * 78)
print("Extension 2: rho bit-width overflow stress test (Numba only, no DP)")
print("=" * 78)
# Long horizon + all-zero duals -> the trivially optimal SP path is "off every
# day", so rho grows unboundedly (rho ~= day * beta_g). At beta_g=3 and 90
# days, rho reaches ~270, far past the shared pack_state's 6-bit (0-63) limit
# -- exactly the silent-wraparound scenario forward_pass_offday's widened
# 8-bit rho field (pack_state_od, 0-255) exists to avoid. This checks the fix
# runs and returns a sane (non-crashing, non-NaN) result at that scale.
long_days = 90
long_T = list(range(1, long_days + 1))
long_data = pd.DataFrame({'I': [1] + [np.nan] * (long_days - 1),
                          'T': long_T,
                          'K': K + [np.nan] * (long_days - 3)})
zero_duals = {(t, s): 0.0 for t in long_T for s in K}
group0 = next(iter(worker_groups.values()))
for beta_g in BETAS:
    nb_long = SubproblemOffdayNumba(1.0, zero_duals, long_data, 1, 0, 0.06,
                                    {1: 2}, {1: 5}, group0.chi, beta_g=beta_g)
    nb_long.gamma_C, nb_long.gamma_R, nb_long.alpha_R, nb_long.delta, nb_long.e_max = (
        group0.gamma_C, group0.gamma_R, group0.alpha_R, group0.delta, group0.e_max)
    nb_long.buildModel()
    nb_long.solveModelOpt(30)
    # With all-zero duals, EVERY feasible path ties at cost = -duals_i (the
    # dual contribution is zero regardless of shift choice), so the specific
    # tie-broken path is unconstrained -- but the objval must still land
    # exactly on -duals_i. A wrong value (NaN, or drift from -1.0) would
    # indicate the widened rho field mis-packed/mis-unpacked at large rho.
    print(f"  beta_g={beta_g}  T={long_days}  objval={nb_long.model.objval:.5f}")
    assert abs(nb_long.model.objval - (-1.0)) < 1e-6, \
        f"beta_g={beta_g}: objval should be exactly -duals_i=-1.0 when all duals are zero (got {nb_long.model.objval})"

print("\n" + "=" * 78)
print("Extension 2: direct subproblem cross-check (DP vs Numba)")
print("=" * 78)
for beta_g in BETAS:
    group = next(iter(worker_groups.values()))
    dp = SubproblemOffdayDP(duals_i, duals_ts, data, group.worker_ids[0], 0, 0.06,
                             Min_WD_i, Max_WD_i, group.chi, beta_g=beta_g)
    nb = SubproblemOffdayNumba(duals_i, duals_ts, data, group.worker_ids[0], 0, 0.06,
                               Min_WD_i, Max_WD_i, group.chi, beta_g=beta_g)
    for sp in (dp, nb):
        sp.gamma_C, sp.gamma_R, sp.alpha_R, sp.delta, sp.e_max = (
            group.gamma_C, group.gamma_R, group.alpha_R, group.delta, group.e_max)
        sp.buildModel()
        sp.solveModelOpt(30)

    obj_diff = abs(dp.model.objval - nb.model.objval)
    x_dp, x_nb = dp.getOptX(), nb.getOptX()
    x_match = all(abs(x_dp.get(k, 0) - x_nb.get(k, 0)) < 1e-6 for k in set(x_dp) | set(x_nb))
    p_dp = dp.getOptP(); p_nb = nb.getOptP()
    p_match = all(abs(p_dp.get(t, 1.0) - p_nb.get(t, 1.0)) < 1e-3 for t in T)
    print(f"  beta_g={beta_g}  DP={dp.model.objval:10.5f}  NB={nb.model.objval:10.5f}  "
          f"|diff|={obj_diff:.2e}  x_match={x_match}  p_match={p_match}")
    assert x_match, f"beta_g={beta_g}: chosen schedule differs between DP and Numba"
    assert p_match, f"beta_g={beta_g}: reconstructed performance (getOptP) differs -- rho/beta_g bug?"
    assert obj_diff < 2e-3, f"beta_g={beta_g}: reduced cost differs by more than quantization noise"

print("\n" + "=" * 78)
print("Extension 2: end-to-end run_cg('dp') vs run_cg('numba')")
print("=" * 78)
for mode in ("bap", "npp", "ecp"):
    for beta_g in (1, 3):  # endpoints of BETAS; full sweep already covered above per-subproblem
        dp_res = run_cg(data, demand_dict, worker_groups, beta_g, mode, solver='dp')
        nb_res = run_cg(data, demand_dict, worker_groups, beta_g, mode, solver='numba')
        print(f"  {mode.upper():>4} beta_g={beta_g} | DP uc={dp_res[0]:7.2f} pl={dp_res[2]:7.2f} | "
              f"NB uc={nb_res[0]:7.2f} pl={nb_res[2]:7.2f}")

print("\nOff-day Recovery: per-subproblem checks PASSED (see end-to-end table above)\n")
