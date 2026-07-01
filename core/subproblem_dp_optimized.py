"""
Fully Optimized Dynamic Programming-based Subproblem Solver

Implements all 4 optimizations:
1. Hash-based Dominance (O(1) lookup)
2. Lower Bound Pruning
3. Numba JIT Compilation
4. Bi-directional DP (for T >= 16)

Author: Extended version of subproblem_dp.py
"""

import math
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from .nonlinear_transitions import h_func, r_func


try:
    from numba import njit, prange
    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False
    def njit(*args, **kwargs):
        def decorator(func):
            return func
        return decorator if not args else decorator(args[0])
    prange = range


# =============================================================================
# NUMBA JIT-COMPILED FUNCTIONS
# =============================================================================

# Remove compute_performance_numba as it's replaced by pi_k array


@njit(cache=True)
def pack_state(omega: int, rho: int, nu: int, e: float, last_worked: int, s_last: int, 
               first_flag: int) -> np.int64:
    """Pack state variables into single int64."""
    # We discretize e for packing if needed, but here we might just pack it as an int if it's small or use a different approach.
    # Actually, in the linear case e was an int. In NL it's a float.
    # Let's pack e as int(e * 1000) to keep some precision, or just use a larger bit range.
    e_int = int(round(e * 1000))
    return np.int64(((omega + 10) & 0x1F) |
                    ((rho & 0x3F) << 5) |
                    ((nu & 0x3F) << 11) |
                    ((e_int & 0x3FF) << 17) | # Up to 1.023 with 0.001 precision
                    ((last_worked & 0x7) << 27) |
                    ((s_last & 0x7) << 30) |
                    ((first_flag & 0x1) << 33))


@njit(cache=True)
def unpack_state(state: np.int64) -> Tuple[int, int, int, float, int, int, int]:
    """Unpack state from int64."""
    omega = (state & 0x1F) - 10
    rho = (state >> 5) & 0x3F
    nu = (state >> 11) & 0x3F
    e_int = (state >> 17) & 0x3FF
    e = e_int / 1000.0
    last_worked = (state >> 27) & 0x7
    s_last = (state >> 30) & 0x7
    first_flag = (state >> 33) & 0x1
    return omega, rho, nu, e, last_worked, s_last, first_flag


@njit(cache=True)
def forward_pass_numba(
    n_days: int,
    n_shifts: int,
    duals_flat: np.ndarray,
    duals_i: float,
    epsilon: float,
    chi: int,
    omega_max: int,
    xi: float,
    min_wd: int,
    max_wd: int,
    days_off: int,
    suffix_bounds: np.ndarray,
    stop_day: int,
    enforce_no_change: int,
    enforce_performance_floor: float,
    gamma_R: float,
    gamma_C: float,
    alpha_R: float,
    delta_flat: np.ndarray,
    e_max: float
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, int]:
    """
    Forward DP pass with support for Linear and Non-linear Dynamics.
    """

    MAX_STATES = 200000
    
    curr_states = np.zeros(MAX_STATES, dtype=np.int64)
    curr_costs = np.zeros(MAX_STATES, dtype=np.float64)
    curr_paths = np.zeros((MAX_STATES, n_days + 1), dtype=np.int8)
    
    next_states = np.zeros(MAX_STATES, dtype=np.int64)
    next_costs = np.zeros(MAX_STATES, dtype=np.float64)
    next_paths = np.zeros((MAX_STATES, n_days + 1), dtype=np.int8)
    
    # Initial state
    # pack_state(omega, rho, nu, e, last_worked, s_last, first_flag)
    curr_states[0] = pack_state(0, 0, 0, 0.0, 0, 0, 1)
    curr_costs[0] = -duals_i
    n_curr = 1
    
    best_cost = np.inf
    
    # Forbidden pairs: (3,1), (3,2), (2,1)
    forbidden = np.array([[3, 1], [3, 2], [2, 1]], dtype=np.int32)
    
    for d in range(stop_day):
        next_day = d + 1
        n_next = 0
        days_remaining = n_days - next_day + 1
        
        for i in range(n_curr):
            state = curr_states[i]
            cost = curr_costs[i]
            
            # Lower bound pruning
            if cost - suffix_bounds[next_day - 1] >= best_cost - 1e-9:
                continue
            
            omega, rho, nu, e, last_worked, s_last, first_flag = unpack_state(state)
            has_worked = last_worked > 0
            
            # Option 1: Day off
            can_off = True
            if omega > 0 and omega < min_wd:
                if days_remaining >= min_wd or first_flag == 1:
                    can_off = False
            
            if can_off and n_next < MAX_STATES:
                # State transition
                new_rho = rho + 1
                new_nu = 0
                
                recov = r_func(new_rho, chi, gamma_R, alpha_R)
                new_e = max(0.0, e - recov)
                
                # Check performance floor if needed
                p_new_off = 1.0 - new_e
                if enforce_performance_floor > 0.0 and p_new_off < enforce_performance_floor:
                    can_off = False
                
                if can_off:
                    next_states[n_next] = pack_state(-1 if omega > 0 else omega - 1, new_rho, new_nu, new_e, last_worked, 0, first_flag)
                    next_costs[n_next] = cost
                    next_paths[n_next, :] = curr_paths[i, :]
                    next_paths[n_next, next_day] = -1  # Day off
                    n_next += 1
            
            # Option 2: Work each shift
            for shift in range(1, n_shifts + 1):
                if omega >= max_wd:
                    continue
                if omega < 0 and has_worked and -omega < days_off:
                    continue
                
                # Check forbidden
                is_forbidden = False
                if s_last > 0:
                    for f in range(3):
                        if forbidden[f, 0] == s_last and forbidden[f, 1] == shift:
                            is_forbidden = True
                            break
                if is_forbidden:
                    continue
                
                if enforce_no_change == 1 and last_worked > 0 and last_worked != shift:
                    continue
                
                # State transition
                c_new = 1 if (last_worked > 0 and last_worked != shift) else 0
                new_rho = rho + 1 if c_new == 0 else 0
                new_nu = nu + 1 if c_new == 1 else 0
                
                if c_new == 1:
                    degrad = delta_flat[last_worked * 4 + shift] * h_func(new_nu, gamma_C)
                    new_e = min(e_max, e + degrad)
                else:
                    recov = r_func(new_rho, chi, gamma_R, alpha_R)
                    new_e = max(0.0, e - recov)
                p_new = 1.0 - new_e
                
                if enforce_performance_floor > 0.0 and p_new < enforce_performance_floor:
                    continue
                    
                dual_val = duals_flat[(next_day - 1) * n_shifts + (shift - 1)]
                new_cost = cost - dual_val * p_new
                
                new_first = first_flag
                if not has_worked and next_day == 1:
                    new_first = 1
                
                if n_next < MAX_STATES:
                    next_states[n_next] = pack_state(1 if omega <= 0 else omega + 1, new_rho, new_nu, new_e, shift, shift, new_first)
                    next_costs[n_next] = new_cost
                    next_paths[n_next, :] = curr_paths[i, :]
                    next_paths[n_next, next_day] = shift
                    n_next += 1
                
                if next_day == n_days and new_cost < best_cost:
                    best_cost = new_cost
        
        # Dominance pruning
        if n_next > 0:
            sort_idx = np.argsort(next_states[:n_next])
            n_pruned = 0
            i = 0
            tol = 1e-9
            while i < n_next:
                idx = sort_idx[i]
                current_state = next_states[idx]
                best_c = next_costs[idx]
                j = i + 1
                while j < n_next and next_states[sort_idx[j]] == current_state:
                    jdx = sort_idx[j]
                    if next_costs[jdx] < best_c:
                        best_c = next_costs[jdx]
                    j += 1
                for k in range(i, j):
                    kdx = sort_idx[k]
                    if abs(next_costs[kdx] - best_c) < tol:
                        if n_pruned < MAX_STATES:
                            curr_states[n_pruned] = current_state
                            curr_costs[n_pruned] = next_costs[kdx]
                            curr_paths[n_pruned, :] = next_paths[kdx, :]
                            n_pruned += 1
                i = j
            n_curr = n_pruned
        else:
            n_curr = 0
    return curr_states[:n_curr].copy(), curr_costs[:n_curr].copy(), curr_paths[:n_curr].copy(), n_curr


@njit(cache=True)
def forward_pass_from_states(
    n_days: int,
    n_shifts: int,
    duals_flat: np.ndarray,
    epsilon: float,
    chi: int,
    omega_max: int,
    xi: float,
    min_wd: int,
    max_wd: int,
    days_off: int,
    start_day: int,
    init_states: np.ndarray,
    init_costs: np.ndarray,
    n_init: int,
    enforce_no_change: int,
    enforce_performance_floor: float,
    gamma_R: float,
    gamma_C: float,
    alpha_R: float,
    delta_flat: np.ndarray,
    e_max: float
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, int]:
    """
    Forward DP pass from start_day to end, starting from given states (Linear version).
    """
    MAX_STATES = 200000
    
    curr_states = np.zeros(MAX_STATES, dtype=np.int64)
    curr_costs = np.zeros(MAX_STATES, dtype=np.float64)
    curr_init_idx = np.zeros(MAX_STATES, dtype=np.int32)
    curr_paths = np.zeros((MAX_STATES, n_days + 1), dtype=np.int8)
    
    next_states = np.zeros(MAX_STATES, dtype=np.int64)
    next_costs = np.zeros(MAX_STATES, dtype=np.float64)
    next_init_idx = np.zeros(MAX_STATES, dtype=np.int32)
    next_paths = np.zeros((MAX_STATES, n_days + 1), dtype=np.int8)
    
    # Initialize with provided states
    n_curr = min(n_init, MAX_STATES)
    for i in range(n_curr):
        curr_states[i] = init_states[i]
        curr_costs[i] = init_costs[i]
        curr_init_idx[i] = i
    
    forbidden = np.array([[3, 1], [3, 2], [2, 1]], dtype=np.int32)
    
    for d in range(start_day, n_days):
        next_day = d + 1
        n_next = 0
        days_remaining = n_days - next_day + 1
        
        for i in range(n_curr):
            state = curr_states[i]
            cost = curr_costs[i]
            init_idx = curr_init_idx[i]
            
            omega, rho, nu, e, last_worked, s_last, first_flag = unpack_state(state)
            has_worked = last_worked > 0
            
            # Option 1: Day off
            can_off = True
            if omega > 0 and omega < min_wd:
                if days_remaining >= min_wd or first_flag == 1:
                    can_off = False
            
            if can_off and n_next < MAX_STATES:
                # Non-linear recovery
                new_rho = rho + 1
                new_nu = 0
                recov = r_func(new_rho, chi, gamma_R, alpha_R)
                new_e = max(0.0, e - recov)
                
                p_new_off = 1.0 - new_e
                if enforce_performance_floor > 0.0 and p_new_off < enforce_performance_floor:
                    can_off = False
                
                if can_off:
                    next_states[n_next] = pack_state(-1 if omega > 0 else omega - 1, new_rho, new_nu, new_e, last_worked, 0, first_flag)
                    next_costs[n_next] = cost
                    next_init_idx[n_next] = init_idx
                    next_paths[n_next, :] = curr_paths[i, :]
                    next_paths[n_next, next_day] = -1
                    n_next += 1
            
            # Option 2: Work each shift
            for shift in range(1, n_shifts + 1):
                if omega >= max_wd:
                    continue
                if omega < 0 and has_worked and -omega < days_off:
                    continue
                
                is_forbidden = False
                if s_last > 0:
                    for f in range(3):
                        if forbidden[f, 0] == s_last and forbidden[f, 1] == shift:
                            is_forbidden = True
                            break
                if is_forbidden:
                    continue
                
                if enforce_no_change == 1 and last_worked > 0 and last_worked != shift:
                    continue
                    
                # Non-linear transition
                c_new = 1 if (last_worked > 0 and last_worked != shift) else 0
                new_rho = rho + 1 if c_new == 0 else 0
                new_nu = nu + 1 if c_new == 1 else 0
                
                if c_new == 1:
                    degrad = delta_flat[last_worked * 4 + shift] * h_func(new_nu, gamma_C)
                    new_e = min(e_max, e + degrad)
                else:
                    recov = r_func(new_rho, chi, gamma_R, alpha_R)
                    new_e = max(0.0, e - recov)
                
                p_new = 1.0 - new_e
                
                if enforce_performance_floor > 0.0 and p_new < enforce_performance_floor:
                    continue
                    
                dual_val = duals_flat[(next_day - 1) * n_shifts + (shift - 1)]
                new_cost = cost - dual_val * p_new
                
                new_first = first_flag
                if not has_worked and next_day == start_day + 1:
                    new_first = 1
                
                if n_next < MAX_STATES:
                    next_states[n_next] = pack_state(1 if omega <= 0 else omega + 1, new_rho, new_nu, new_e, shift, shift, new_first)
                    next_costs[n_next] = new_cost
                    next_init_idx[n_next] = init_idx
                    next_paths[n_next, :] = curr_paths[i, :]
                    next_paths[n_next, next_day] = shift
                    n_next += 1
        
        # Dominance
        if n_next > 0:
            sort_idx = np.argsort(next_states[:n_next])
            n_pruned = 0
            i = 0
            while i < n_next:
                idx = sort_idx[i]
                current_state = next_states[idx]
                best_c = next_costs[idx]
                best_idx = idx
                j = i + 1
                while j < n_next and next_states[sort_idx[j]] == current_state:
                    jdx = sort_idx[j]
                    if next_costs[jdx] < best_c:
                        best_c = next_costs[jdx]
                        best_idx = jdx
                    j += 1
                curr_states[n_pruned] = current_state
                curr_costs[n_pruned] = best_c
                curr_init_idx[n_pruned] = next_init_idx[best_idx]
                curr_paths[n_pruned, :] = next_paths[best_idx, :]
                n_pruned += 1
                i = j
            n_curr = n_pruned
        else:
            n_curr = 0
    return (curr_states[:n_curr].copy(), curr_costs[:n_curr].copy(), 
            curr_init_idx[:n_curr].copy(), curr_paths[:n_curr].copy(), n_curr)


@njit(cache=True)
def merge_bidirectional(
    fwd_states: np.ndarray,
    fwd_costs: np.ndarray,
    fwd_paths: np.ndarray,
    n_fwd: int,
    second_costs: np.ndarray,
    second_init_idx: np.ndarray,
    second_paths: np.ndarray,
    n_second: int,
    n_days: int,
    mid_day: int,
) -> Tuple[float, np.ndarray]:
    """
    Merge first and second forward passes.
    
    The second pass tracked which init_idx (= index into first pass results)
    each path came from, so we combine:
    - fwd_paths[init_idx] for days 0..mid_day
    - second_paths for days mid_day+1..n_days
    
    Returns best_cost and combined best_path.
    """
    best_cost = np.inf
    best_path = np.zeros(n_days + 1, dtype=np.int8)
    
    for i in range(n_second):
        total_cost = second_costs[i]  # Already includes fwd cost via init_costs
        
        if total_cost < best_cost:
            best_cost = total_cost
            init_idx = second_init_idx[i]
            
            # Combine paths: first half from fwd_paths, second half from second_paths
            for d in range(mid_day + 1):
                best_path[d] = fwd_paths[init_idx, d]
            for d in range(mid_day + 1, n_days + 1):
                best_path[d] = second_paths[i, d]
    
    return best_cost, best_path


@njit(cache=True)
def merge_bidir(
    fwd_states: np.ndarray,
    fwd_costs: np.ndarray,
    fwd_paths: np.ndarray,
    n_fwd: int,
    bwd_states: np.ndarray,
    bwd_costs: np.ndarray,
    bwd_paths: np.ndarray,
    n_bwd: int,
    n_days: int,
    mid_day: int,
) -> Tuple[float, np.ndarray]:
    """
    Merge forward and backward labels at midpoint.
    
    Returns:
        best_cost: Optimal objective value
        best_path: Optimal path decisions
    """
    best_cost = np.inf
    best_path = np.zeros(n_days + 1, dtype=np.int8)
    
    # For each forward state, find matching backward states
    for i in range(n_fwd):
        fwd_state = fwd_states[i]
        fwd_cost = fwd_costs[i]
        
        for j in range(n_bwd):
            if bwd_states[j] == fwd_state:
                total_cost = fwd_cost + bwd_costs[j]
                if total_cost < best_cost:
                    best_cost = total_cost
                    # Combine paths
                    for d in range(mid_day + 1):
                        best_path[d] = fwd_paths[i, d]
                    for d in range(mid_day + 1, n_days + 1):
                        best_path[d] = bwd_paths[j, d]
    
    return best_cost, best_path


# =============================================================================
# PYTHON WRAPPER CLASSES
# =============================================================================

from subproblem_dp import Label, SubproblemDP


class SubproblemDPOptimized(SubproblemDP):
    """
    Optimized DP with hash-based dominance and lower bound pruning.
    Falls back to Python implementation.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.suffix_bounds = None
        self.best_known_cost = float('inf')
        self._precompute_suffix_bounds()

    def _precompute_suffix_bounds(self):
        n_days = len(self.days)
        n_shifts = len(self.shifts)
        
        self.suffix_bounds = np.zeros(n_days + 2, dtype=np.float64)
        for d_idx in range(n_days - 1, -1, -1):
            day = self.days[d_idx]
            max_dual = max(self.duals_ts.get((day, k), 0.0) for k in self.shifts)
            self.suffix_bounds[d_idx] = self.suffix_bounds[d_idx + 1] + max_dual
        
        self.duals_flat = np.zeros(n_days * n_shifts, dtype=np.float64)
        for d_idx, day in enumerate(self.days):
            for k_idx, shift in enumerate(self.shifts):
                self.duals_flat[d_idx * n_shifts + k_idx] = self.duals_ts.get((day, shift), 0.0)

    def _get_state_key(self, label: Label) -> tuple:
        return (label.day, label.s_last, label.last_worked_shift, 
                label.e, label.rho, label.omega)

    def _prune_dominated_optimized(self, labels: List[Label], is_final_day: bool = False) -> List[Label]:
        if not labels:
            return []
        if is_final_day:
            return [min(labels, key=lambda l: l.cost)]

        state_best: Dict[tuple, Label] = {}
        for label in labels:
            key = self._get_state_key(label)
            if key not in state_best or label.cost < state_best[key].cost:
                state_best[key] = label
        return list(state_best.values())

    def _prune_with_lower_bound(self, labels: List[Label], day_idx: int) -> List[Label]:
        if self.best_known_cost >= float('inf'):
            return labels
        max_future_gain = self.suffix_bounds[day_idx + 1]
        return [l for l in labels if l.cost - max_future_gain < self.best_known_cost - 1e-9]

    def _solve(self, timeLimit, optimal=True):
        import time
        start_time = time.time()

        labels_by_day: Dict[int, List[Label]] = {d: [] for d in self.days}
        labels_by_day[0] = []

        initial_label = Label(
            day=0, s_last=None, last_worked_shift=None,
            e=0, rho=0, omega=0, cost=-self.duals_i,
            path=[], total_workdays=0,
            sc_history=[], r_history=[], p_history=[]
        )
        labels_by_day[0] = [initial_label]
        self.best_known_cost = float('inf')

        days_to_process = [0] + self.days[:-1]
        
        for d_idx, d in enumerate(days_to_process):
            current_labels = labels_by_day[d]
            if not current_labels:
                continue

            if d > 0:
                current_labels = self._prune_with_lower_bound(current_labels, d_idx - 1)
                if not current_labels:
                    continue

            for label in current_labels:
                next_day = d + 1
                new_labels = self._generate_transitions(label, next_day)

                if next_day not in labels_by_day:
                    labels_by_day[next_day] = []
                labels_by_day[next_day].extend(new_labels)
                
                if next_day == self.days[-1]:
                    for nl in new_labels:
                        if nl.cost < self.best_known_cost:
                            self.best_known_cost = nl.cost

            next_day = d + 1
            is_final = (next_day == self.days[-1])
            labels_by_day[next_day] = self._prune_dominated_optimized(
                labels_by_day[next_day], is_final_day=is_final
            )

            if time.time() - start_time > timeLimit:
                self.status = gu.GRB.TIME_LIMIT
                self.objval = float('inf')
                return

        final_labels = labels_by_day[self.days[-1]]
        if not final_labels:
            self.status = gu.GRB.INFEASIBLE
            self.objval = float('inf')
            return

        self.best_label = min(final_labels, key=lambda l: l.cost)
        self.status = gu.GRB.OPTIMAL
        self.objval = self.best_label.cost


class SubproblemDPNumba:
    """Pure Numba implementation for maximum speed."""
    
    def __init__(self, duals_i, duals_ts, df, i, iteration, eps, Min_WD_i, Max_WD_i, chi):
        self.itr = iteration + 1
        self.days = df['T'].dropna().astype(int).unique().tolist()
        self.shifts = df['K'].dropna().astype(int).unique().tolist()
        self.duals_i = duals_i
        self.duals_ts = duals_ts
        self.index = i
        self.epsilon = eps
        self.chi = chi
        self.omega_max = math.ceil(round(1 / self.epsilon, 6)) if self.epsilon > 1e-6 else 999
        self.xi = 1 - self.epsilon * self.omega_max
        
        self.Days_Off = 2
        self.Min_WD = 2
        self.Max_WD = 5
        
        self.status = None
        self.objval = None
        self.best_path = None
        self.all_optimal_paths = []
        self.n_optimal = 0
        
        # Mock model for compatibility with cg_behavior.py (uses model.objval)
        self.model = self._MockModel(self)
        
        self._prepare()
    
    class _MockModel:
        """Mock Gurobi model for interface compatibility."""
        def __init__(self, parent):
            self._parent = parent
        
        @property
        def objval(self):
            return self._parent.objval
    
    def _prepare(self):
        n_days = len(self.days)
        n_shifts = len(self.shifts)
        
        self.duals_flat = np.zeros(n_days * n_shifts, dtype=np.float64)
        for d_idx, day in enumerate(self.days):
            for k_idx, shift in enumerate(self.shifts):
                self.duals_flat[d_idx * n_shifts + k_idx] = self.duals_ts.get((day, shift), 0.0)
        
        self.suffix_bounds = np.zeros(n_days + 2, dtype=np.float64)
        for d_idx in range(n_days - 1, -1, -1):
            max_dual = max(self.duals_flat[d_idx * n_shifts:(d_idx + 1) * n_shifts])
            self.suffix_bounds[d_idx] = self.suffix_bounds[d_idx + 1] + max_dual
            
        # No longer using non-linear transitions
        pass

    def buildModel(self):
        pass

    def solveModelOpt(self, timeLimit):
        n_days = len(self.days)
        n_shifts = len(self.shifts)
        
        if NUMBA_AVAILABLE:
            # Check if bidirectional mode is explicitly requested
            use_bidir = getattr(self, '_use_bidir', False)
            
            if use_bidir and n_days >= 8:  # Bidir only useful for T >= 8
                # Bidirectional DP: forward to midpoint, continue forward to end, merge
                mid_day = n_days // 2
                
                enc_nc = 1 if getattr(self, 'enforce_no_change', False) else 0
                enc_pf = getattr(self, 'enforce_performance_floor', None)
                enc_pf = float(enc_pf) if enc_pf is not None else 0.0

                # Prepare JIT non-linear parameters
                gamma_C = getattr(self, 'gamma_C', 1.25)
                gamma_R = getattr(self, 'gamma_R', 0.5)
                alpha_R = getattr(self, 'alpha_R', 0.04)
                e_max = getattr(self, 'e_max', 0.5)
                delta_flat = np.zeros(16, dtype=np.float64)
                if getattr(self, 'delta', None) is not None:
                    delta_flat = self.delta.flatten().astype(np.float64)

                # Forward pass 1: day 0 to mid_day
                fwd_states, fwd_costs, fwd_paths, n_fwd = forward_pass_numba(
                    n_days, n_shifts, self.duals_flat, self.duals_i,
                    self.epsilon, self.chi, self.omega_max, self.xi,
                    self.Min_WD, self.Max_WD, self.Days_Off,
                    self.suffix_bounds, mid_day, enc_nc, enc_pf,
                    gamma_R, gamma_C, alpha_R, delta_flat, e_max
                )
                
                if n_fwd > 0:
                    # Forward pass 2: mid_day to n_days, starting from states in fwd_states
                    _, second_costs, second_init_idx, second_paths, n_second = forward_pass_from_states(
                        n_days, n_shifts, self.duals_flat,
                        self.epsilon, self.chi, self.omega_max, self.xi,
                        self.Min_WD, self.Max_WD, self.Days_Off,
                        mid_day, fwd_states, fwd_costs, n_fwd, enc_nc, enc_pf,
                        gamma_R, gamma_C, alpha_R, delta_flat, e_max
                    )
                    
                    if n_second > 0:
                        # Merge the two passes
                        best_cost, best_path = merge_bidirectional(
                            fwd_states, fwd_costs, fwd_paths, n_fwd,
                            second_costs, second_init_idx, second_paths, n_second,
                            n_days, mid_day
                        )
                        
                        if best_cost < np.inf:
                            self.objval = best_cost
                            self.best_path = best_path
                            self.all_optimal_paths = [best_path.copy()]
                            self.n_optimal = 1
                            self.status = gu.GRB.OPTIMAL
                        else:
                            self._solve_forward_only(n_days, n_shifts)
                    else:
                        self._solve_forward_only(n_days, n_shifts)
                else:
                    self._solve_forward_only(n_days, n_shifts)
            else:
                # Standard forward-only DP for smaller horizons
                self._solve_forward_only(n_days, n_shifts)
        else:
            self.objval = float('inf')
            self.status = gu.GRB.INFEASIBLE
            self.n_optimal = 0

    def _solve_forward_only(self, n_days, n_shifts):
        """Standard forward-only DP solve."""
        enc_nc = 1 if getattr(self, 'enforce_no_change', False) else 0
        enc_pf = getattr(self, 'enforce_performance_floor', None)
        enc_pf = float(enc_pf) if enc_pf is not None else 0.0
        
        # Prepare JIT non-linear parameters
        gamma_C = getattr(self, 'gamma_C', 1.25)
        gamma_R = getattr(self, 'gamma_R', 0.5)
        alpha_R = getattr(self, 'alpha_R', 0.04)
        e_max = getattr(self, 'e_max', 0.5)
        delta_flat = np.zeros(16, dtype=np.float64)
        if getattr(self, 'delta', None) is not None:
            delta_flat = self.delta.flatten().astype(np.float64)

        states, costs, paths, n_states = forward_pass_numba(
            n_days, n_shifts, self.duals_flat, self.duals_i,
            self.epsilon, self.chi, self.omega_max, self.xi,
            self.Min_WD, self.Max_WD, self.Days_Off,
            self.suffix_bounds, n_days, enc_nc, enc_pf,
            gamma_R, gamma_C, alpha_R, delta_flat, e_max
        )
        
        if n_states > 0:
            # Find best cost across ALL end-states
            best_cost = np.min(costs[:n_states])
            self.objval = best_cost
            
            # Collect ALL paths with optimal cost (from ANY end-state)
            tol = 1e-9
            self.all_optimal_paths = []
            for i in range(n_states):
                if abs(costs[i] - best_cost) < tol:
                    self.all_optimal_paths.append(paths[i].copy())
            
            # n_optimal = count of distinct paths with best cost
            # Note: This counts paths across different end-states
            # Due to dominance pruning, there may be MORE optimal paths
            # that were pruned (same state, same cost, different schedule)
            self.n_optimal = len(self.all_optimal_paths)
            self.best_path = self.all_optimal_paths[0] if self.all_optimal_paths else None
            self.status = gu.GRB.OPTIMAL
        else:
            self.objval = float('inf')
            self.status = gu.GRB.INFEASIBLE
            self.n_optimal = 0

    def solveModelNOpt(self, timeLimit):
        self.solveModelOpt(timeLimit)

    def getStatus(self):
        return self.status if self.status else gu.GRB.LOADED

    def getNewSchedule(self):
        """Return performance schedule for MP column generation.
        
        Returns performance values (p * x), not just binary 0/1.
        This matches the MIP subproblem which returns self.performance.
        """
        if self.best_path is None:
            return {}
        
        # Get performance values for each day
        p_values = self.getOptP()
        
        schedule = {}
        for d_idx, day in enumerate(self.days):
            for shift in self.shifts:
                if self.best_path[d_idx + 1] == shift:
                    # Performance value when working this shift
                    schedule[(day, shift, self.itr)] = p_values.get(day, 1.0)
                else:
                    schedule[(day, shift, self.itr)] = 0.0
        return schedule

    def getOptimalCount(self):
        """Return the number of equally optimal paths found."""
        return getattr(self, 'n_optimal', 1)

    def getAllOptimalSchedules(self):
        """Return all equally optimal schedules (with same reduced cost).
        
        Returns a list of schedule dicts, each formatted for column addition.
        Currently only returns the first one for actual use, but stores all.
        """
        if not hasattr(self, 'all_optimal_paths') or not self.all_optimal_paths:
            return [self.getNewSchedule()]
        
        schedules = []
        for idx, path in enumerate(self.all_optimal_paths):
            schedule = self._path_to_schedule(path, self.itr + idx)
            schedules.append(schedule)
        return schedules

    def _path_to_schedule(self, path, col_idx):
        """Convert a path to a schedule dict with the given column index."""
        # Reconstruct p_values for this path
        p_values = self._reconstruct_p_for_path(path)
        
        schedule = {}
        for d_idx, day in enumerate(self.days):
            for shift in self.shifts:
                if path[d_idx + 1] == shift:
                    schedule[(day, shift, col_idx)] = p_values.get(day, 1.0)
                else:
                    schedule[(day, shift, col_idx)] = 0.0
        return schedule

    def _reconstruct_p_for_path(self, path):
        """Reconstruct performance values for a specific path using non-linear math."""
        n_days = len(self.days)
        p_values = {}
        e = 0.0
        rho = 0
        nu = 0
        last_worked_shift = None
        
        gamma_C = getattr(self, 'gamma_C', 1.25)
        gamma_R = getattr(self, 'gamma_R', 0.5)
        alpha_R = getattr(self, 'alpha_R', 0.04)
        e_max = getattr(self, 'e_max', 0.5)
        delta = getattr(self, 'delta', None)
        if delta is None:
            from core.worker_groups import get_default_delta
            delta = get_default_delta(self.epsilon)
            
        for d_idx in range(n_days):
            shift = int(path[d_idx + 1])
            day = self.days[d_idx]
            
            if shift > 0:  # Working day
                if last_worked_shift is not None and last_worked_shift != shift:
                    nu += 1
                    rho = 0
                    degrad = delta[last_worked_shift, shift] * h_func(nu, gamma_C)
                    e = min(e_max, e + degrad)
                else:
                    rho += 1
                    nu = 0
                    recov = r_func(rho, self.chi, gamma_R, alpha_R)
                    e = max(0.0, e - recov)
                last_worked_shift = shift
            else:  # Off day
                rho += 1
                nu = 0
                recov = r_func(rho, self.chi, gamma_R, alpha_R)
                e = max(0.0, e - recov)
                
            p = 1.0 - e
            p_values[day] = p
            
        return p_values

    def getAllSchedules(self, start_col_idx):
        """Return all optimal schedules for multi-column addition.
        
        Args:
            start_col_idx: Starting column index for addColumn (itr argument)
            
        Returns:
            List of (schedule_dict, col_idx) tuples where schedule keys use col_idx+1
            (matching addColumn's rosterIndex = itr + 1 behavior)
        """
        if not hasattr(self, 'all_optimal_paths') or not self.all_optimal_paths:
            # Fallback to single schedule
            if self.best_path is not None:
                return [(self.getNewSchedule(), start_col_idx)]
            return []
        
        schedules = []
        for i, path in enumerate(self.all_optimal_paths):
            col_idx = start_col_idx + i
            roster_idx = col_idx + 1  # addColumn expects schedule[t,s,itr+1]
            schedule = self._path_to_schedule(path, roster_idx)
            schedules.append((schedule, col_idx))
        
        return schedules

    def getNumOptimalSolutions(self):
        """Return number of optimal solutions found."""
        return getattr(self, 'n_optimal', 1)

    def getOptX(self):
        if self.best_path is None:
            return {}
        x = {}
        for d_idx, day in enumerate(self.days):
            for shift in self.shifts:
                x[(day, shift)] = 1.0 if self.best_path[d_idx + 1] == shift else 0.0
        return x

    def _reconstruct_state_history(self):
        """Reconstruct all state variables from the path using non-linear math."""
        if self.best_path is None:
            return None
        
        n_days = len(self.days)
        chi = self.chi
        gamma_C = getattr(self, 'gamma_C', 1.25)
        gamma_R = getattr(self, 'gamma_R', 0.5)
        alpha_R = getattr(self, 'alpha_R', 0.04)
        e_max = getattr(self, 'e_max', 0.5)
        delta = getattr(self, 'delta', None)
        if delta is None:
            from core.worker_groups import get_default_delta
            delta = get_default_delta(self.epsilon)

        c_history = []
        last_worked = 0
        for d_idx in range(n_days):
            shift = int(self.best_path[d_idx + 1])
            if shift > 0:  # Working day
                c = 1 if (last_worked > 0 and last_worked != shift) else 0
                last_worked = shift
            else:
                c = 0
            c_history.append(c)

        r_history = []
        for d_idx in range(n_days):
            day = d_idx + 1  # 1-indexed
            if day <= chi + 1:
                r = 0
            else:
                # Sum of c from d-χ to d (inclusive)
                start = d_idx - chi
                sum_c = sum(c_history[start:d_idx + 1])
                r = 1 if sum_c == 0 else 0
            r_history.append(r)

        p_history = []
        e = 0.0
        rho = 0
        nu = 0
        last_worked_shift = None
        for d_idx in range(n_days):
            shift = int(self.best_path[d_idx + 1])
            c = c_history[d_idx]
            
            if shift > 0:
                if last_worked_shift is not None and last_worked_shift != shift:
                    nu += 1
                    rho = 0
                    degrad = delta[last_worked_shift, shift] * h_func(nu, gamma_C)
                    e = min(e_max, e + degrad)
                else:
                    rho += 1
                    nu = 0
                    recov = r_func(rho, chi, gamma_R, alpha_R)
                    e = max(0.0, e - recov)
                last_worked_shift = shift
            else:
                rho += 1
                nu = 0
                recov = r_func(rho, chi, gamma_R, alpha_R)
                e = max(0.0, e - recov)
                
            p = 1.0 - e
            p_history.append(p)

        return {
            'p': p_history,
            'sc': c_history,
            'r': r_history,
            'e_up': [0.0]*n_days,
            'e_low': [0.0]*n_days
        }

    def getOptP(self):
        """Get performance values by day."""
        if self.best_path is None:
            return {}
        history = self._reconstruct_state_history()
        if history is None:
            return {}
        return {day: history['p'][i] for i, day in enumerate(self.days)}

    def getOptC(self):
        """Get shift change indicators."""
        if self.best_path is None:
            return {}
        history = self._reconstruct_state_history()
        if history is None:
            return {}
        return {day: float(history['sc'][i]) for i, day in enumerate(self.days)}

    def getOptR(self):
        """Get recovery indicators."""
        if self.best_path is None:
            return {}
        history = self._reconstruct_state_history()
        if history is None:
            return {}
        return {day: float(history['r'][i]) for i, day in enumerate(self.days)}

    def getOptEUp(self):
        """Get e upper indicators."""
        if self.best_path is None:
            return {}
        history = self._reconstruct_state_history()
        if history is None:
            return {}
        return {day: history['e_up'][i] for i, day in enumerate(self.days)}

    def getOptElow(self):
        """Get e lower indicators."""
        if self.best_path is None:
            return {}
        history = self._reconstruct_state_history()
        if history is None:
            return {}
        return {day: history['e_low'][i] for i, day in enumerate(self.days)}

    def getOptPerf(self):
        """Get performance schedule (same as getNewSchedule)."""
        return self.getNewSchedule()

