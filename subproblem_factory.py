"""
Factory module for creating subproblem solvers.

This module provides a unified interface to create either MIP-based or DP-based
subproblem solvers for the column generation algorithm.
"""

from subproblem import Subproblem
from subproblem_dp import SubproblemDP

# Try to import Numba-optimized version
try:
    from subproblem_dp_optimized import SubproblemDPNumba, SubproblemDPNumba as SubproblemDPBidir, NUMBA_AVAILABLE
except ImportError:
    NUMBA_AVAILABLE = False
    SubproblemDPNumba = None
    SubproblemDPBidir = None


def create_subproblem(solver_type: str, duals_i, duals_ts, df, i, iteration,
                     eps, Min_WD_i, Max_WD_i, chi, use_bidir=False,
                     enforce_no_change=False, enforce_performance_floor=None,
                     nl_spec=None):
    """
    Factory function to create a subproblem solver.

    Args:
        solver_type: 
            - 'mip': Gurobi MIP solver (robust, slower)
            - 'dp': Python DP solver (correct, medium speed)
            - 'labeling': Numba DP solver (forward-only, fast)
            - 'labeling_bidir': Numba DP solver (bidirectional, for T >= 16)
        duals_i: Dual value for lambda constraint
        duals_ts: Dual values for demand constraints
        df: DataFrame with problem data
        i: Staff member index
        iteration: Current CG iteration
        eps: Epsilon parameter for performance degradation
        Min_WD_i: Minimum workdays constraint
        Max_WD_i: Maximum workdays constraint
        chi: Recovery threshold (days without shift change)
        use_bidir: Force bidirectional mode (only for 'labeling' type)

    Returns:
        Subproblem solver instance

    Raises:
        ValueError: If solver_type is not recognized
    """
    solver = solver_type.lower()
    
    if solver == 'mip':
        sp = Subproblem(duals_i, duals_ts, df, i, iteration, eps, Min_WD_i, Max_WD_i, chi)
        sp.enforce_no_change = enforce_no_change
        sp.enforce_performance_floor = enforce_performance_floor
        sp.nl_spec = nl_spec

        return sp
    
    elif solver == 'dp':
        sp = SubproblemDP(duals_i, duals_ts, df, i, iteration, eps, Min_WD_i, Max_WD_i, chi)
        sp.enforce_no_change = enforce_no_change
        sp.enforce_performance_floor = enforce_performance_floor
        sp.nl_spec = nl_spec

        return sp
    
    elif solver == 'labeling':
        if not NUMBA_AVAILABLE or SubproblemDPNumba is None:
            print("Warning: Numba not available, falling back to Python DP")
            sp = SubproblemDP(duals_i, duals_ts, df, i, iteration, eps, Min_WD_i, Max_WD_i, chi)
            sp.enforce_no_change = enforce_no_change
            sp.enforce_performance_floor = enforce_performance_floor

            return sp
        sp = SubproblemDPNumba(duals_i, duals_ts, df, i, iteration, eps, Min_WD_i, Max_WD_i, chi)
        sp._use_bidir = use_bidir  # Flag for bidirectional mode
        sp.enforce_no_change = enforce_no_change
        sp.enforce_performance_floor = enforce_performance_floor
        sp.nl_spec = nl_spec

        return sp
    
    elif solver == 'labeling_bidir':
        if not NUMBA_AVAILABLE or SubproblemDPNumba is None:
            print("Warning: Numba not available, falling back to Python DP")
            sp = SubproblemDP(duals_i, duals_ts, df, i, iteration, eps, Min_WD_i, Max_WD_i, chi)
            sp.enforce_no_change = enforce_no_change
            sp.enforce_performance_floor = enforce_performance_floor
            sp.nl_spec = nl_spec

            return sp
        sp = SubproblemDPNumba(duals_i, duals_ts, df, i, iteration, eps, Min_WD_i, Max_WD_i, chi)
        sp._use_bidir = True  # Force bidirectional mode
        sp.enforce_no_change = enforce_no_change
        sp.enforce_performance_floor = enforce_performance_floor
        sp.nl_spec = nl_spec

        return sp
    
    else:
        raise ValueError(f"Unknown solver type: {solver_type}. Use 'mip', 'dp', 'labeling', or 'labeling_bidir'.")


