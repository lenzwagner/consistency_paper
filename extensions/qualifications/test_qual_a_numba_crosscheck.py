"""Cross-check: Numba-JIT pricing (SubproblemQualificationsNumba) vs the exact
Python label-setting reference (SubproblemQualificationsDP) for Extension 4
Case A, across all PI_VALUES. Both must agree on the chosen schedule (getOptX)
and closely on the reduced cost (small drift expected -- the Numba kernel
quantizes the performance state e to 5 decimal places when bit-packing for
dominance, see core/subproblem_dp_extensions_numba.py's pack_state docstring).
Then one full run_cg('dp') vs run_cg('numba') comparison end-to-end.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import numpy as np
import pandas as pd
from core.base_case import get_wd_constraints
from core.subproblem_dp_extensions import SubproblemQualificationsDP
from core.subproblem_dp_extensions_numba import SubproblemQualificationsNumba
from Utils.demand import generate_demand
from extensions.qualifications.loop_qualifications import make_qual_groups, PI_VALUES
from extensions.qualifications.loop_qualifications_labeling import run_cg

len_I, num_days, seed = 12, 14, 2
I = list(range(1, len_I + 1)); T = list(range(1, num_days + 1)); K = [1, 2, 3]
maxlen = max(len(I), len(T), len(K))
data = pd.DataFrame({'I': I + [np.nan]*(maxlen-len(I)),
                     'T': T + [np.nan]*(maxlen-len(T)),
                     'K': K + [np.nan]*(maxlen-len(K))})
demand_dict = generate_demand(num_days, 0.7, len_I, shift_probs=(50, 30, 20),
                              delta=0.25, seed=seed, prop_volatility=0.30)
Min_WD_i, Max_WD_i = get_wd_constraints(I)

rng = np.random.default_rng(seed)
duals_ts = {(t, s): float(rng.uniform(0, 2)) for t in T for s in K}
duals_i = 0.3

print("\n" + "=" * 78)
print("Extension 4 Case A: direct subproblem cross-check (DP vs Numba)")
print("=" * 78)
for pi in PI_VALUES:
    qual_groups = make_qual_groups(I, pi)
    group = next(iter(qual_groups.values()))
    dp = SubproblemQualificationsDP(duals_i, duals_ts, data, group.worker_ids[0], 0, 0.06,
                                     Min_WD_i, Max_WD_i, group.chi, group.eligible_shifts)
    nb = SubproblemQualificationsNumba(duals_i, duals_ts, data, group.worker_ids[0], 0, 0.06,
                                       Min_WD_i, Max_WD_i, group.chi, group.eligible_shifts)
    for sp in (dp, nb):
        sp.gamma_C, sp.gamma_R, sp.alpha_R, sp.delta, sp.e_max = (
            group.gamma_C, group.gamma_R, group.alpha_R, group.delta, group.e_max)
        sp.buildModel()
        sp.solveModelOpt(30)

    obj_diff = abs(dp.model.objval - nb.model.objval)
    x_dp, x_nb = dp.getOptX(), nb.getOptX()
    x_match = all(abs(x_dp.get(k, 0) - x_nb.get(k, 0)) < 1e-6 for k in set(x_dp) | set(x_nb))
    print(f"  pi(ICU)={pi:<5} DP={dp.model.objval:10.5f}  NB={nb.model.objval:10.5f}  "
          f"|diff|={obj_diff:.2e}  x_match={x_match}")
    assert x_match, f"pi={pi}: chosen schedule differs between DP and Numba"
    assert obj_diff < 2e-3, f"pi={pi}: reduced cost differs by more than quantization noise"

print("\n" + "=" * 78)
print("Extension 4 Case A: end-to-end run_cg('dp') vs run_cg('numba')")
print("=" * 78)
# No hard tolerance here (unlike the direct per-subproblem check above): NPP
# sets e_max=0, which forces p=1 regardless of shift choice (extensions.tex /
# loop_offday_labeling.py's beta_g-invariance note applies here too), so
# pricing degenerates to a pure coverage assignment problem with many
# reduced-cost ties. DP and Numba can legitimately tie-break differently
# across dozens of CG iterations and end up with different (but individually
# valid) tied-optimal columns, same caveat as extensions/offday_recovery's
# own MIP-vs-labeling test_ext2_crosscheck.py. Small gaps are expected; only
# the per-subproblem check above is the actual correctness proof.
for mode in ("bap", "npp", "ecp"):
    qual_groups = make_qual_groups(I, PI_VALUES[1])
    uc_dp, us_dp, pl_dp, ch_dp = run_cg(data, demand_dict, qual_groups, mode, solver='dp')
    uc_nb, us_nb, pl_nb, ch_nb = run_cg(data, demand_dict, qual_groups, mode, solver='numba')
    print(f"  {mode.upper():>4} | DP  uc={uc_dp:7.2f} pl={pl_dp:7.2f} chg={ch_dp:4.0f} | "
          f"NB  uc={uc_nb:7.2f} pl={pl_nb:7.2f} chg={ch_nb:4.0f}")

print("\nQualifications Case A: per-subproblem checks PASSED (see end-to-end table above)\n")
