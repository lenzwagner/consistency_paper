"""
Solver Configuration for Column Generation and Compact Model.
All tuning knobs in one place — import from here instead of hardcoding.
"""

# ── Compact model ─────────────────────────────────────────────────────────────
K_MAX               = 20      # loss-grid resolution (K_max)
TIME_LIMIT_COMPACT  = 120     # Gurobi time limit for compact MIP (seconds)

# ── Column Generation (BAP) ───────────────────────────────────────────────────
MAX_ITR             = 200     # maximum CG iterations
THRESHOLD           = 5e-6    # reduced-cost convergence threshold
TIME_CG_INIT        = 15      # time limit for heuristic start solution (seconds)
TIME_CG             = 7200    # total time limit for full CG run (seconds; 2 h for production)
TIME_CG_SP          = 100     # per-subproblem time limit inside extension loops (seconds)
TIME_LIMIT_BAP      = 120     # time limit for the final BAP integer program (seconds)
OUTPUT_LEN          = 50      # width of CG iteration output lines
SCALE               = 1.0     # demand scaling factor

# ── Compact model (production loop) ──────────────────────────────────────────
TIME_LIMIT_COMPACT_PROD = 3600  # Gurobi time limit for compact MIP in loop_compact (seconds)
