"""
Base Case Parameterization for the Behavioral Model.
Based on the EJOR paper draft (Analysis.tex).

Contains:
- Directed change costs Delta(s, s') calibrated to circadian phase dynamics.
- Partitioning of the workforce into two resilience groups:
  - Concave group (Group 1): resilient, decelerating fatigue, early onset recovery.
  - Convex group (Group 2): sensitive, superlinear fatigue, delayed onset recovery.
- Neutral/homogeneous base case parameterization for comparison.
"""

import numpy as np
from typing import List, Dict, Tuple, Union
from core.worker_groups import WorkerGroup

# ── Run configuration ────────────────────────────────────────────────────────
LEN_I_RANGE  = [100]          # workforce sizes to sweep
SCENARIO_RANGE = range(1, 2)  # demand scenarios (1-indexed)
PATTERN      = 'Medium'       # demand pattern
CHI          = 3              # FALLBACK ONLY: used solely by create_homogeneous_group(I, eps, CHI)
                             # when NO worker_groups are supplied. Once explicit groups are passed
                             # (e.g. get_base_case_groups -> group1 chi=2, group2 chi=4), the pricing
                             # subproblem uses each group's OWN chi and this constant has NO effect.
                             # Changing it will NOT alter group-based runs (empirically verified).
MIN_WD       = 2              # minimum consecutive working days
MAX_WD       = 5              # maximum consecutive working days
# ── Regulatory scheduling constraints ────────────────────────────────────────
DAYS_OFF     = 2              # mandatory rest days after a working block
# Forbidden consecutive shift pairs (s_yesterday, s_today):
# N→E (3,1), N→L (3,2), L→E (2,1) — circadian phase-advance violations
F_S: List[Tuple[int, int]] = [(3, 1), (3, 2), (2, 1)]
# ECP: max shift changes per rolling 7-day window
K_ECP        = 2
# ─────────────────────────────────────────────────────────────────────────────


def get_wd_constraints(I: List[int], min_wd: int = MIN_WD, max_wd: int = MAX_WD):
    """Return per-worker Min_WD_i and Max_WD_i dicts for the given worker list."""
    return {i: min_wd for i in I}, {i: max_wd for i in I}


def get_base_case_delta() -> np.ndarray:
    """
    Builds the directed baseline shift change cost matrix Delta(s, s').
    Indices: 0 = Off, 1 = Early (E), 2 = Late (L), 3 = Night (N)

    Calibrated as follows:
    - Delta(N, E) = 0.20 (most disruptive phase advance)
    - Delta(E, N) = 0.13
    - Delta(L, E) = 0.11
    - Delta(N, L) = 0.10
    - Delta(L, N) = 0.08
    - Delta(E, L) = 0.06
    - Delta(s, s) = 0.0  for all s (no shift change cost for same shift)
    - All transitions involving 'Off' (0) have a cost of 0.0.
    """
    delta = np.zeros((4, 4), dtype=np.float64)

    # E -> ...
    delta[1, 2] = 0.06  # E -> L
    delta[1, 3] = 0.13  # E -> N

    # L -> ...
    delta[2, 1] = 0.11  # L -> E
    delta[2, 3] = 0.08  # L -> N

    # N -> ...
    delta[3, 1] = 0.20  # N -> E
    delta[3, 2] = 0.10  # N -> L

    return delta


def get_base_case_groups(I: List[int]) -> Dict[str, WorkerGroup]:
    """
    Partitions the workforce equally into two resilience groups as described in the paper:
    - Group 1 (concave / resilient): 50% split (first half of workers)
    - Group 2 (convex / sensitive): 50% split (second half of workers)

    Parameters:
    - Group 1: (gamma^C, gamma^R, chi, T^R) = (0.5, 0.5, 2, 7)
      -> alpha_R = T_R^{-gamma_R} = 7^{-0.5} ≈ 0.377964
    - Group 2: (gamma^C, gamma^R, chi, T^R) = (1.5, 1.5, 4, 21)
      -> alpha_R = T_R^{-gamma_R} = 21^{-1.5} ≈ 0.010394

    Args:
        I: List of worker IDs (e.g. list(range(1, 101)))

    Returns:
        Dict mapping group name to WorkerGroup objects.
    """
    n_workers = len(I)
    half = n_workers // 2

    worker_ids_g1 = I[:half]
    worker_ids_g2 = I[half:]

    delta = get_base_case_delta()

    # Group 1: Resilient Concave Group
    # (gamma_1^C, gamma_1^R, chi_1, T_1^R) = (0.5, 0.5, 2, 7)
    # alpha_R derived by WorkerGroup.__post_init__: alpha_R = T_R^{-gamma_R} = 7^{-0.5}
    group1 = WorkerGroup(
        name="group1",
        epsilon=0.0,
        chi=2,
        worker_ids=worker_ids_g1,
        gamma_C=0.5,
        gamma_R=0.5,
        T_R=7,
        e_max=1.0,
        delta=delta
    )

    # Group 2: Sensitive Convex Group
    # (gamma_2^C, gamma_2^R, chi_2, T_2^R) = (1.5, 1.5, 4, 21)
    # alpha_R derived by WorkerGroup.__post_init__: alpha_R = T_R^{-gamma_R} = 21^{-1.5}
    group2 = WorkerGroup(
        name="group2",
        epsilon=0.0,
        chi=4,
        worker_ids=worker_ids_g2,
        gamma_C=1.5,
        gamma_R=1.5,
        T_R=21,
        e_max=1.0,
        delta=delta
    )

    return {
        "group1": group1,
        "group2": group2
    }


def get_homogeneous_base_case_group(I: List[int]) -> Dict[str, WorkerGroup]:
    """
    Returns the homogeneous / neutral case group for comparison where all workers
    share the average/neutral parameters:
    - Neutral: (gamma^C, gamma^R, chi, T^R) = (1.0, 1.0, 3, 14)
      -> alpha_R = 1 / (14 - 3)^1.0 = 1 / 11 ≈ 0.090909

    Args:
        I: List of worker IDs.

    Returns:
        Dict with a single 'homogeneous' group.
    """
    delta = get_base_case_delta()
    alpha_R_neutral = 1.0 / (14.0 - 3.0)  # 1 / 11

    homogeneous_group = WorkerGroup(
        name="homogeneous",
        epsilon=0.0,
        chi=3,
        worker_ids=I,
        gamma_C=1.0,
        gamma_R=1.0,
        alpha_R=alpha_R_neutral,
        e_max=1.0,
        delta=delta
    )

    return {
        "homogeneous": homogeneous_group
    }
