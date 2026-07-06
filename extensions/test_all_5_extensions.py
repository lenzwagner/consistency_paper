"""Compact cross-extension test: Extensions 1, 2, 3, 4A, 4B on I=10, 14 days.

Extensions 1/2/3/4A share the SAME base instance/demand (a regime with a
day-to-day varying shift mix, prop_volatility>0, so a fixed shift-type
assignment cannot cover demand and shift changes are structurally required).

Extension 4B (overlapping qualifications) uses its OWN demand pattern, since
it is qualification- rather than shift-indexed; kept small and separate.

Note (known limitation, see conversation): 4B's master problem still uses the
base per-(day,shift) demand row, not the paper's per-(day,shift,qualification)
row Q_ds^q. With the current 1:1 shift->qualification mapping (E,L->q1,
N->q2), no shift is ever jointly demanded by two qualifications, so the
q-branching mechanism never actually branches. Numbers for 4B should be read
with this caveat; they confirm the code RUNS, not that overlapping-demand
routing is exercised.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Monkeypatch platform to prevent win32_ver/uname/machine from hanging on Augsburg Uni Windows environment
import platform
platform.win32_ver = lambda *args: ('10', '10.0.26100', '', 'multiprocessor')
platform.uname = lambda *args: platform.uname_result('Windows', 'wiwi-sif-ws06', '10', '10.0.26100', 'AMD64', 'Intel64 Family 6 Model 85 Stepping 7, GenuineIntel')
platform.machine = lambda *args: 'AMD64'

# Disable Numba to avoid compilation/initialization hangs
os.environ["DISABLE_NUMBA"] = "1"

import numpy as np
import pandas as pd
from core.worker_groups import create_groups_from_fractions
from Utils.demand import generate_demand

len_I, num_days, seed = 10, 14, 1
I = list(range(1, len_I + 1)); T = list(range(1, num_days + 1)); K = [1, 2, 3]
maxlen = max(len(I), len(T), len(K))
data = pd.DataFrame({'I': I + [np.nan]*(maxlen-len(I)),
                     'T': T + [np.nan]*(maxlen-len(T)),
                     'K': K + [np.nan]*(maxlen-len(K))})

# Shared demand for Ext 1/2/3/4A: varying shift mix (forces shift changes) +
# moderate slack (prob=0.7) so the regime isn't purely structurally understaffed.
demand_dict = generate_demand(num_days, 0.7, len_I, shift_probs=(25, 50, 25),
                              delta=0.25, seed=seed, prop_volatility=0.30)
worker_groups = create_groups_from_fractions(I, "1/2,1/2", [(0.5, 0.5, 2, 7), (1.5, 1.5, 4, 21)])

print("="*88)
print(f"Cross-extension test: I={len_I}, days={num_days}, seed={seed}")
print(f"Shared demand (Ext 1/2/3/4A): total={sum(demand_dict.values())}, prop_volatility=0.30")
print("="*88)

MODES = ("bap", "npp", "ecp")

# Default MAX_ITR is 200 (core/solver_base.py); at I=10 that is massive overkill
# and, combined with no per-combo progress output, makes the script look hung.
# Cap iterations for this smoke test and print a "running..." line (flushed
# immediately) before every CG call so progress is visible in real time.
MAX_ITR_TEST = 60


def hdr(title):
    print("\n" + "-"*88, flush=True)
    print(title, flush=True)
    print("-"*88, flush=True)


def running(label):
    print(f"  ... running {label}", end="\r", flush=True)


# --------------------------------------------------------------------------
# Extension 1: Fairness
# --------------------------------------------------------------------------
hdr("EXTENSION 1: Fairness in Shift-Type Allocation (lambda sweep)")
from extensions.fairness.loop_fairness_labeling import run_cg as run_fair, MU

print(f"  {'mode':>5} {'lambda':>7} {'UC':>8} {'PL':>8} {'Chg':>5} {'Gini(F)':>9}")
for mode in MODES:
    running(f"{mode} preprocessing (F_bar)")
    _, _, _, _, F_bar, _ = run_fair(data, demand_dict, worker_groups, 3, 0.7, 0.0, 0.0, mode,
                                    max_itr=MAX_ITR_TEST)
    for lam in (0.0, 0.5, 2.0):
        running(f"{mode} lambda={lam}")
        uc, us, pl, cons, _, g = run_fair(data, demand_dict, worker_groups, 3, 0.7, lam, F_bar, mode,
                                          max_itr=MAX_ITR_TEST)
        print(f"  {mode:>5} {lam:>7.1f} {uc:8.2f} {pl:8.2f} {cons:5.0f} {g:9.4f}", flush=True)

# --------------------------------------------------------------------------
# Extension 2: Off-Day Recovery
# --------------------------------------------------------------------------
hdr("EXTENSION 2: Performance Recovery on Off-Days (beta sweep)")
from extensions.offday_recovery.loop_offday_labeling import run_cg as run_offday, optimize_schedule, evaluate_pool

print(f"  {'mode':>5} {'beta':>5} {'UC':>8} {'PL':>8} {'Chg':>5}")
for mode in MODES:
    if mode == "bap":
        for beta in (1, 2, 3):
            running(f"{mode} beta={beta}")
            uc, us, pl, cons = run_offday(data, demand_dict, worker_groups, beta, mode, max_itr=MAX_ITR_TEST)
            print(f"  {mode:>5} {beta:>5} {uc:8.2f} {pl:8.2f} {cons:5.0f}", flush=True)
    else:
        running(f"{mode} single solve")
        master, x_by_group = optimize_schedule(data, demand_dict, worker_groups, mode, beta_g=1,
                                               max_itr=MAX_ITR_TEST)
        for beta in (1, 2, 3):
            uc, us, pl, cons = evaluate_pool(master, x_by_group, worker_groups, demand_dict, beta, T, K)
            print(f"  {mode:>5} {beta:>5} {uc:8.2f} {pl:8.2f} {cons:5.0f}", flush=True)

# --------------------------------------------------------------------------
# Extension 3: Preferences
# --------------------------------------------------------------------------
hdr("EXTENSION 3: Worker Day-Off Preferences (lambda_P sweep)")
import random
from extensions.preferences.loop_preferences_labeling import run_cg as run_pref
from extensions.preferences.loop_preferences import make_singleton_groups

random.seed(11)
singleton_groups = make_singleton_groups(I, worker_groups)
pref_by_worker = {w: random.sample(T, random.randint(1, 2)) for w in I}

print(f"  {'mode':>5} {'lam_P':>6} {'UC':>8} {'PL':>8} {'Chg':>5} {'Satisf.':>8}")
for mode in MODES:
    for lam in (0.0, 0.5, 2.0):
        running(f"{mode} lambda_P={lam}")
        uc, us, pl, cons, sat = run_pref(data, demand_dict, singleton_groups, pref_by_worker, lam, mode,
                                         max_itr=MAX_ITR_TEST)
        print(f"  {mode:>5} {lam:>6.1f} {uc:8.2f} {pl:8.2f} {cons:5.0f} {sat:8.2f}", flush=True)

# --------------------------------------------------------------------------
# Extension 4A: Qualifications (clean partition)
# --------------------------------------------------------------------------
hdr("EXTENSION 4A: Heterogeneous Qualifications, Case A (pi sweep)")
from extensions.qualifications.loop_qualifications_labeling import run_cg as run_qualA
from extensions.qualifications.loop_qualifications import make_qual_groups

print(f"  {'mode':>5} {'pi(ICU)':>8} {'UC':>8} {'PL':>8} {'Chg':>5}")
for mode in MODES:
    for pi in (0.20, 0.50):
        running(f"{mode} pi={pi}")
        qual_groups = make_qual_groups(I, pi)
        uc, us, pl, cons = run_qualA(data, demand_dict, qual_groups, mode, max_itr=MAX_ITR_TEST)
        print(f"  {mode:>5} {pi:>8.2f} {uc:8.2f} {pl:8.2f} {cons:5.0f}", flush=True)

# --------------------------------------------------------------------------
# Extension 4B: Overlapping Qualifications -- OWN demand pattern
# --------------------------------------------------------------------------
hdr("EXTENSION 4B: Overlapping Qualifications (own demand pattern; pi sweep)")
print("  Genuine qualification-indexed demand: E/L jointly demanded by q1+q2,")
print("  N is q2-only. Master gets real per-(day,shift,qual) rows via the")
print("  vshift=10*shift+qual encoding (see extensions.tex Case B setup).")
print("  NPP/ECP performance is now re-evaluated ex-post under the group's")
print("  TRUE gamma_C/gamma_R on the REAL shift sequence (mirrors Ext. 2's")
print("  evaluate_schedule_beta), so PL reflects genuine behavioral cost.")

from extensions.qualifications.loop_qualifications_case_b import (
    make_workers_case_b, run_cg as run_qualB, build_demand_case_b, build_data_master, all_vshifts
)

data_master_4b = build_data_master(I, T)
demand_vshift_4b = build_demand_case_b(num_days, 0.7, len_I, seed=seed)
print(f"  4B vshifts = {all_vshifts()}, total demand = {sum(demand_vshift_4b.values())}")

print(f"  {'mode':>5} {'pi(ICU)':>8} {'UC':>8} {'PL':>8} {'Chg':>5}")
for mode in MODES:
    for pi in (0.20, 0.50):
        running(f"{mode} pi={pi}")
        workers_b = make_workers_case_b(I, pi)
        uc, us, pl, cons = run_qualB(data, data_master_4b, demand_vshift_4b, workers_b, mode,
                                     max_itr=MAX_ITR_TEST)
        print(f"  {mode:>5} {pi:>8.2f} {uc:8.2f} {pl:8.2f} {cons:5.0f}", flush=True)

print("\n" + "="*88 + "\n")
