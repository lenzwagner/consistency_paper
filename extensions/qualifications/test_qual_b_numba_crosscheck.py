"""Cross-check: Numba-JIT pricing (SubproblemQualificationsOverlapNumba) vs
the exact Python label-setting reference (SubproblemQualificationsOverlapDP)
for Extension 4 Case B (overlapping qualifications), across PI_VALUES.
Verifies objval, the real-shift path (getRealShiftSeq), and the vshift-keyed
decisions (getOptX) -- i.e. that the extra q-branching/path_q bookkeeping in
the Numba kernel reconstructs the same (shift, qualification) choice per day.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import numpy as np
import pandas as pd
from core.base_case import get_wd_constraints
from core.subproblem_dp_extensions import SubproblemQualificationsOverlapDP
from core.subproblem_dp_extensions_numba import SubproblemQualificationsOverlapNumba
from extensions.qualifications.loop_qualifications_case_b import (
    SHIFT_TO_QUALIFICATIONS, PI_VALUES, make_workers_case_b, build_demand_case_b,
    build_data_master, all_vshifts, run_cg,
)

len_I, num_days, seed = 12, 14, 6
I = list(range(1, len_I + 1)); T = list(range(1, num_days + 1)); K = [1, 2, 3]
maxlen = max(len(I), len(T), len(K))
data_sp = pd.DataFrame({'I': I + [np.nan]*(maxlen-len(I)),
                        'T': T + [np.nan]*(maxlen-len(T)),
                        'K': K + [np.nan]*(maxlen-len(K))})
Min_WD_i, Max_WD_i = get_wd_constraints(I)

rng = np.random.default_rng(seed)
duals_ts_q = {}
for t in T:
    for s in K:
        for q in SHIFT_TO_QUALIFICATIONS[s]:
            duals_ts_q[(t, s, q)] = float(rng.uniform(0, 2))
duals_i = 0.3

print("\n" + "=" * 78)
print("Extension 4 Case B: direct subproblem cross-check (DP vs Numba)")
print("=" * 78)
for pi in PI_VALUES:
    workers = make_workers_case_b(I, pi)
    w = next(w for w in workers.values() if len(w.eligible_qualifications) > 1) if \
        any(len(w.eligible_qualifications) > 1 for w in workers.values()) else next(iter(workers.values()))

    dp = SubproblemQualificationsOverlapDP(duals_i, duals_ts_q, SHIFT_TO_QUALIFICATIONS, data_sp,
                                           w.worker_id, 0, 0.06, Min_WD_i, Max_WD_i, w.chi,
                                           w.eligible_qualifications)
    nb = SubproblemQualificationsOverlapNumba(duals_i, duals_ts_q, SHIFT_TO_QUALIFICATIONS, data_sp,
                                              w.worker_id, 0, 0.06, Min_WD_i, Max_WD_i, w.chi,
                                              w.eligible_qualifications)
    for sp in (dp, nb):
        sp.gamma_C, sp.gamma_R, sp.alpha_R, sp.delta, sp.e_max = (
            w.gamma_C, w.gamma_R, w.alpha_R, w.delta, w.e_max)
        sp.buildModel()
        sp.solveModelOpt(30)

    obj_diff = abs(dp.model.objval - nb.model.objval)
    x_dp, x_nb = dp.getOptX(), nb.getOptX()
    x_match = all(abs(x_dp.get(k, 0) - x_nb.get(k, 0)) < 1e-6 for k in set(x_dp) | set(x_nb))
    seq_dp, seq_nb = dp.getRealShiftSeq(), nb.getRealShiftSeq()
    seq_match = seq_dp == seq_nb
    print(f"  pi={pi:<5} qual={sorted(w.eligible_qualifications)}  DP={dp.model.objval:10.5f}  "
          f"NB={nb.model.objval:10.5f}  |diff|={obj_diff:.2e}  x_match={x_match}  seq_match={seq_match}")
    assert x_match, f"pi={pi}: vshift decisions differ between DP and Numba"
    assert seq_match, f"pi={pi}: real shift sequence differs between DP and Numba"
    assert obj_diff < 2e-3, f"pi={pi}: reduced cost differs by more than quantization noise"

print("\n" + "=" * 78)
print("Extension 4 Case B: end-to-end run_cg('dp') vs run_cg('numba')")
print("=" * 78)
pi = PI_VALUES[1]
workers = make_workers_case_b(I, pi)
demand_vshift = build_demand_case_b(num_days, 1.0, len_I, seed)
data_master = build_data_master(I, T)
for mode in ("bap", "npp", "ecp"):
    dp_res = run_cg(data_sp, data_master, demand_vshift, workers, mode, solver='dp')
    nb_res = run_cg(data_sp, data_master, demand_vshift, workers, mode, solver='numba')
    print(f"  {mode.upper():>4} | DP uc={dp_res[0]:7.2f} pl={dp_res[2]:7.2f} chg={dp_res[3]:4.0f} | "
          f"NB uc={nb_res[0]:7.2f} pl={nb_res[2]:7.2f} chg={nb_res[3]:4.0f}")

print("\nQualifications Case B: per-subproblem checks PASSED (see end-to-end table above)\n")
