"""
run_test_cg_compact.py
======================
Compares the exact compact model (ProblemExact, MILP) against
Column Generation + bidirectional Labeling (BAP) on randomly
generated demand patterns.

Configuration settings at the top:
    SEED_START / SEED_END  -> Seed range (e.g., 1 to 10)
    NUM_WORKERS            -> Number of workers
    NUM_DAYS               -> Number of days (planning horizon)

When running (e.g., in PyCharm), it asks in the console whether
the schedule of each worker should be displayed for each run
(true/false).

At the end: Comparison table of Compact vs. Labeling (BAP) with
objective value and runtime per seed.
"""

import os
import sys
import time

import numpy as np
import pandas as pd

# --- Add project directory to path to enable imports in PyCharm ---
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)
os.chdir(_THIS_DIR)

from core.base_case import get_base_case_groups, get_wd_constraints
from core.cg_behavior import column_generation_behavior
from Utils.compactsolver_exact import ProblemExact
from Utils.demand import generate_demand


# =============================================================================
# CONFIGURATION  --  set parameters here
# =============================================================================
SEED_START  = 1      # first seed (inclusive)
SEED_END    = 10     # last seed (inclusive)
NUM_WORKERS = 10     # number of workers
NUM_DAYS    = 10     # number of days / planning horizon

# Solver parameters
COMPACT_TIME_LIMIT = 300    # seconds for the compact MILP
BAP_TIME_LIMIT     = 300    # seconds for the IP in the master problem
BAP_MAX_ITR        = 2000   # max. CG iterations
EPS                = 0.06   # performance degradation per shift change
CHI                = 2      # resilience threshold (base case parameter)
THRESHOLD          = 0.5
SHIFT_PROBS        = (50, 30, 20)   # distribution of shift types in the demand
DEMAND_DELTA       = 0.25
# =============================================================================

SHIFTS = [1, 2, 3]
SHIFT_LABEL = {0: "-", 1: "F", 2: "S", 3: "N"}   # F=Early, S=Late, N=Night, -=off


def _fmt_perf(p):
    """Performance compact and clear: '1.00', '0.94', day off -> '  . '."""
    if p is None or p <= 1e-9:
        return "  . "
    return f"{p:4.2f}"


# -----------------------------------------------------------------------------
# Helper functions for schedule visualization
# -----------------------------------------------------------------------------
def _print_compact_schedule(compact_model, I, T, K):
    """Displays the schedule of each worker from the compact model."""
    print("\n  >> COMPACT Schedule (F=Early, S=Late, N=Night, -=off):")
    header = "     Worker | " + " ".join(f"T{t:<2}" for t in T)
    print(header)
    print("     " + "-" * (len(header) - 5))
    for i in I:
        row = []
        for t in T:
            assigned = "-"
            for k in K:
                if compact_model.x[i, t, k].X > 0.5:
                    assigned = SHIFT_LABEL.get(k, str(k))
                    break
            # Performance on this day (if assigned > 0)
            row.append(f"{assigned:<3}")
        # Performance row (1 - e), trajectory including recovery on days off
        perf_str = " ".join(_fmt_perf(compact_model.p[i, t].X) for t in T)
        print(f"     {i:>6} | " + " ".join(row))
        print(f"       perf | " + perf_str)


def _print_bap_schedule(ls_x, ls_perf, n_workers, n_days, n_shifts):
    """Displays the schedule of each worker from the BAP reconstruction (ls_x/ls_perf)."""
    print("\n  >> LABELING/BAP Schedule (F=Early, S=Late, N=Night, -=off):")
    T = list(range(1, n_days + 1))
    header = "     Worker | " + " ".join(f"T{t:<2}" for t in T)
    print(header)
    print("     " + "-" * (len(header) - 5))
    # ls_x / ls_perf are flat: worker-major, then day, then shift
    total_expected = n_workers * n_days * n_shifts
    if len(ls_x) < total_expected:
        print(f"     [Note] Reconstruction incomplete "
              f"({len(ls_x)}/{total_expected} entries) - showing available workers.")
    n_avail = len(ls_x) // (n_days * n_shifts)
    for w in range(n_avail):
        row = []
        perf_row = []
        for d in range(n_days):
            assigned = "-"
            p_day = 0.0
            for s in range(n_shifts):
                idx = w * (n_days * n_shifts) + d * n_shifts + s
                if idx < len(ls_x) and ls_x[idx] > 0.5:
                    assigned = SHIFT_LABEL.get(s + 1, str(s + 1))
                    p_day = ls_perf[idx] if idx < len(ls_perf) else 0.0
                    break
            row.append(f"{assigned:<3}")
            perf_row.append(_fmt_perf(p_day))
        print(f"     {w + 1:>6} | " + " ".join(row))
        print(f"       perf | " + " ".join(perf_row))


# -----------------------------------------------------------------------------
# Solver wrappers
# -----------------------------------------------------------------------------
def solve_compact(data, demand_dict, Min_WD_i, Max_WD_i, worker_groups):
    """Solves the exact compact MILP. Returns (obj, time, gap, model)."""
    t0 = time.time()
    model = ProblemExact(data, demand_dict, Min_WD_i, Max_WD_i, worker_groups)
    model.buildModel()
    model.model.setParam("OutputFlag", 0)
    model.model.setParam("TimeLimit", COMPACT_TIME_LIMIT)
    model.solveModel()
    elapsed = time.time() - t0

    if model.model.SolCount > 0:
        obj = model.model.ObjVal
        gap = model.model.MIPGap
    else:
        obj = None
        gap = None
    return obj, elapsed, gap, model


def solve_bap(data, demand_dict, Min_WD_i, Max_WD_i, I, T, K):
    """Solves via CG + labeling_bidir. Returns (obj, time, ls_x, ls_perf).

    Important: the TRUE objective value is res[8] = final_obj
    (Master-IP-Objective = sum u[t,s]). res[0] is an incorrect
    post-hoc recalculation and is NOT used.
    """
    t0 = time.time()
    res = column_generation_behavior(
        data, demand_dict, EPS, Min_WD_i, Max_WD_i,
        60, BAP_MAX_ITR, 100, CHI, THRESHOLD, BAP_TIME_LIMIT,
        I, T, K, 1.0, sp_solver="labeling_bidir",
        use_null_column=False, enforce_no_change=False,
        enforce_performance_floor=None,
    )
    elapsed = time.time() - t0

    final_obj = res[8]     # TRUE objective function (sum u[t,s])
    ls_perf   = res[18]    # reconstructed performance per worker-day-shift
    ls_x      = res[19]    # reconstructed assignment per worker-day-shift
    return final_obj, elapsed, ls_x, ls_perf


# -----------------------------------------------------------------------------
# Main program
# -----------------------------------------------------------------------------
def main():
    # --- Interactive query in the PyCharm console ---
    answer = input(
        "Display schedule of each worker per run? (true/false): "
    ).strip().lower()
    show_schedules = answer in ("true", "t", "1", "yes", "y", "ja", "j")

    print("\n" + "=" * 78)
    print(f"TEST RUN  Compact (MILP)  vs.  Labeling/BAP")
    print(f"  Seeds {SEED_START}..{SEED_END} | {NUM_WORKERS} Workers | {NUM_DAYS} Days")
    print(f"  Show schedules: {show_schedules}")
    print("=" * 78)

    I = list(range(1, NUM_WORKERS + 1))
    T = list(range(1, NUM_DAYS + 1))
    K = SHIFTS
    maxlen = max(len(I), len(T), len(K))
    data = pd.DataFrame({
        "I": I + [np.nan] * (maxlen - len(I)),
        "T": T + [np.nan] * (maxlen - len(T)),
        "K": K + [np.nan] * (maxlen - len(K)),
    })

    Min_WD_i, Max_WD_i = get_wd_constraints(I)
    worker_groups = get_base_case_groups(I)

    rows = []

    for seed in range(SEED_START, SEED_END + 1):
        print("\n" + "-" * 78)
        print(f"SEED {seed}")
        print("-" * 78)

        # --- Generate demand pattern for this seed ---
        demand_dict = generate_demand(
            NUM_DAYS, 1.0, NUM_WORKERS,
            shift_probs=SHIFT_PROBS, delta=DEMAND_DELTA, seed=seed,
        )

        # --- Compact ---
        print("  [Compact] solving exact MILP ...")
        c_obj, c_time, c_gap, c_model = solve_compact(
            data, demand_dict, Min_WD_i, Max_WD_i, worker_groups
        )
        gap_str = f"{c_gap:.2%}" if c_gap is not None else "n/a"
        print(f"  [Compact] obj={c_obj}  gap={gap_str}  time={c_time:.2f}s")

        # --- BAP / Labeling ---
        print("  [Labeling] solving CG + labeling_bidir ...")
        b_obj, b_time, ls_x, ls_perf = solve_bap(
            data, demand_dict, Min_WD_i, Max_WD_i, I, T, K
        )
        print(f"  [Labeling] obj={b_obj}  time={b_time:.2f}s")

        # --- Optional schedule display ---
        if show_schedules:
            if c_model is not None and c_model.model.SolCount > 0:
                _print_compact_schedule(c_model, I, T, K)
            _print_bap_schedule(ls_x, ls_perf, NUM_WORKERS, NUM_DAYS, len(K))

        rows.append({
            "seed":           seed,
            "compact_obj":    round(c_obj, 4) if c_obj is not None else None,
            "labeling_obj":   round(b_obj, 4) if b_obj is not None else None,
            "compact_time":   round(c_time, 3),
            "labeling_time":  round(b_time, 3),
        })

    # --- Results table ---
    df = pd.DataFrame(rows, columns=[
        "seed", "compact_obj", "labeling_obj", "compact_time", "labeling_time"
    ])

    print("\n" + "=" * 78)
    print("COMPARISON  Compact vs. Labeling")
    print("=" * 78)
    print(df.to_string(index=False))

    # Compact summary
    valid = df.dropna(subset=["compact_obj", "labeling_obj"])
    if not valid.empty:
        gap_abs = (valid["labeling_obj"] - valid["compact_obj"]).abs()
        print("\nSummary:")
        print(f"  mean |Obj difference| (Labeling - Compact): {gap_abs.mean():.4f}")
        print(f"  Compact  mean time: {valid['compact_time'].mean():.2f}s")
        print(f"  Labeling mean time: {valid['labeling_time'].mean():.2f}s")
        exact_matches = int((gap_abs < 1e-6).sum())
        print(f"  exact matches: {exact_matches}/{len(valid)}")

    results_dir = os.path.join(_THIS_DIR, "results")
    os.makedirs(results_dir, exist_ok=True)
    stamp = time.strftime("%d_%m_%Y_%H-%M")

    out_csv = os.path.join(results_dir, "run_test_cg_compact.csv")
    df.to_csv(out_csv, index=False)
    print(f"\nResults saved (CSV):   {out_csv}")

    out_xlsx = os.path.join(results_dir, f"run_test_cg_compact_{stamp}.xlsx")
    try:
        df.to_excel(out_xlsx, index=False)
        print(f"Results saved (Excel): {out_xlsx}")
    except Exception as e:
        print(f"[Note] Excel export failed ({e}). "
              f"Maybe run 'pip install openpyxl'. CSV was saved successfully.")


if __name__ == "__main__":
    main()
