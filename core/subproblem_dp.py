"""
Dynamic Programming-based Subproblem Solver for Staff Scheduling

This module implements a label-setting algorithm to solve the Resource Constrained
Shortest Path Problem (RCSPP) arising in the column generation subproblem.
"""

import math
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass
import gurobipy as gu
from .nonlinear_transitions import h_func, r_func
from .base_case import DAYS_OFF, F_S, K_ECP



@dataclass
class Label:
    """
    Represents a partial schedule state on day d.

    Attributes:
        day: Current day index
        s_last: Last worked shift type (None if no shift worked yet or on day off)
        last_worked_shift: Most recently worked shift (persists through off days)
        e: Current performance level (float for continuous, or int/float)
        rho: Recovery counter (consecutive days without shift change)
        omega: Consecutive workdays counter
        cost: Accumulated reduced cost
        path: List of decisions [(day, shift)] for reconstruction
        total_workdays: Total workdays counter
        sc_history: Shift change history
        r_history: Recovery history
        p_history: Performance history
        nu: Consecutive shift change counter
    """
    day: int
    s_last: Optional[int]  # None means no shift worked yet (or day off)
    last_worked_shift: Optional[int]  # Most recently worked shift (for SC on resume)
    e: float  # Performance level (continuous or discretized)
    rho: int  # Recovery counter
    omega: int  # Consecutive workdays
    cost: float
    path: List[Tuple[int, Optional[int]]]  # (day, shift) - None means day off
    total_workdays: int  # Total number of workdays so far
    sc_history: List[int]  # Shift change history
    r_history: List[int]   # Recovery history
    p_history: List[float]  # Performance history
    nu: int = 0  # Consecutive shift change counter

    def copy(self):
        """Create a deep copy of this label."""
        return Label(
            day=self.day,
            s_last=self.s_last,
            last_worked_shift=self.last_worked_shift,
            e=self.e,
            rho=self.rho,
            omega=self.omega,
            cost=self.cost,
            path=self.path.copy(),
            total_workdays=self.total_workdays,
            sc_history=self.sc_history.copy(),
            r_history=self.r_history.copy(),
            p_history=self.p_history.copy(),
            nu=self.nu
        )

    def dominates(self, other: 'Label', is_final_day: bool = False, min_wd: int = 1) -> bool:
        """
        Check if this label dominates the other label.
        
        Conservative dominance: Only dominate if all state variables match
        AND cost is strictly better. This prevents incorrectly pruning
        paths that could lead to better solutions in the future.
        
        Args:
            other: The other label to compare against
            is_final_day: Whether this is the final day (allows relaxed dominance)
            min_wd: Minimum consecutive workdays (for omega dominance)
            
        Returns:
            True if this label dominates other, False otherwise
        """
        if self is other:
            return True

        if is_final_day:
            # At the final day, only accumulated cost matters
            return self.cost < other.cost - 1e-9
        else:
            # Conservative dominance: require same full state
            # Only cost can differ
            if self.day != other.day:
                return False
            if self.s_last != other.s_last:
                return False
            if self.last_worked_shift != other.last_worked_shift:
                return False
            if round(self.e, 3) != round(other.e, 3):
                return False
            if self.rho != other.rho:
                return False
            if self.omega != other.omega:
                return False
            if self.nu != other.nu:
                return False
            
            # All state variables match - dominate if cost is strictly better
            return self.cost < other.cost - 1e-9


class SubproblemDP:
    """
    Dynamic Programming-based solver for the staff scheduling subproblem.

    This class provides the same interface as the MIP-based Subproblem class
    but uses a label-setting algorithm for improved efficiency.
    """

    def __init__(self, duals_i, duals_ts, df, i, iteration, eps, Min_WD_i, Max_WD_i, chi, model_type='nonlinear'):
        """
        Initialize the DP subproblem solver.

        Args:
            duals_i: Dual value for lambda constraint
            duals_ts: Dual values for demand constraints (dict with (day, shift) keys)
            df: DataFrame with problem data
            i: Staff member index
            iteration: Current CG iteration
            eps: Epsilon parameter for performance degradation
            Min_WD_i: Minimum workdays constraint
            Max_WD_i: Maximum workdays constraint
            chi: Recovery threshold (days without shift change)
            model_type: 'linear' or 'nonlinear'
        """
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
        self.model_type = model_type
        
        # Non-linear default parameters (can be set by factory)
        self.gamma_C = 1.25
        self.gamma_R = 0.5
        self.alpha_R = 0.04
        self.e_max = 1.0
        self.delta = None

        # Regulatory constraints
        self.Days_Off = DAYS_OFF
        # Per-worker Min/Max consecutive working days (mirrors subproblem.py lines 280-285)
        self.Min_WD = Min_WD_i[i] if isinstance(Min_WD_i, dict) else Min_WD_i
        self.Max_WD = Max_WD_i[i] if isinstance(Max_WD_i, dict) else Max_WD_i
        self.F_S = F_S
        self.k_ecp = None  # activate via addECPConstraint(K_ECP) where K_ECP from base_case

        # Solution storage
        self.best_label: Optional[Label] = None
        self.status = None
        self.objval = None

        # MockModel for compatibility with cg_behavior.py (uses model.objval)
        self.model = self._MockModel(self)
    
    class _MockModel:
        """Mock Gurobi model for interface compatibility."""
        def __init__(self, parent):
            self._parent = parent
        
        @property
        def objval(self):
            return self._parent.objval

    def buildModel(self):
        """Build model (no-op for DP, kept for interface compatibility)."""
        pass

    def addECPConstraint(self, k):
        """Imposes an upper bound of k shift changes per rolling 7-day window
        (mirrors core/subproblem.py's MIP addECPConstraint, model:ecp)."""
        self.k_ecp = k

    def _violates_ecp(self, label: 'Label', c_new: int) -> bool:
        """True if appending c_new to the rolling 7-day sc-window would exceed k_ecp."""
        if self.k_ecp is None:
            return False
        window = label.sc_history[-6:] + [c_new]
        return sum(window) > self.k_ecp

    def solveModelOpt(self, timeLimit):
        """Solve with tight optimality (main solve method)."""
        self._solve(timeLimit, optimal=True)

    def solveModelNOpt(self, timeLimit):
        """Solve with relaxed optimality (same as optimal for DP)."""
        self._solve(timeLimit, optimal=True)

    def _solve(self, timeLimit, optimal=True):
        """
        Main label-setting algorithm.

        Args:
            timeLimit: Maximum time for solving (not strictly enforced in DP)
            optimal: If True, use exact dominance rules
        """
        import time
        start_time = time.time()

        # Initialize labels BEFORE day 1 (day 0)
        labels_by_day: Dict[int, List[Label]] = {d: [] for d in self.days}
        labels_by_day[0] = []  # Special: day before start

        # Initial label: BEFORE the planning horizon starts (day 0)
        # This represents the state at the end of day 0 (before day 1)
        initial_label = Label(
            day=0,
            s_last=None,  # No work history yet
            last_worked_shift=None,  # No shift worked yet
            e=0.0,  # Performance level 0 means p = 1.0
            rho=0,
            omega=0,
            cost=-self.duals_i,  # Initial cost is just the dual of lambda constraint
            path=[],
            total_workdays=0,  # Maintained for info, but not constrained
            sc_history=[],
            r_history=[],
            p_history=[],
            nu=0
        )

        labels_by_day[0] = [initial_label]

        # Forward pass: propagate labels day by day
        # Start from day 0 and generate decisions for days 1, 2, ..., T
        days_to_process = [0] + self.days[:-1]  # [0, 1, 2, ..., T-1]
        
        for d in days_to_process:
            current_labels = labels_by_day[d]

            if not current_labels:
                continue

            for label in current_labels:
                # Generate all possible transitions to next day
                next_day = d + 1
                new_labels = self._generate_transitions(label, next_day)

                # Add to next day
                if next_day not in labels_by_day:
                    labels_by_day[next_day] = []
                labels_by_day[next_day].extend(new_labels)

            # Prune dominated labels at day d+1
            next_day = d + 1
            # Check if this is the final day
            is_final = (next_day == self.days[-1])
            labels_by_day[next_day] = self._prune_dominated(labels_by_day[next_day], is_final_day=is_final)

            # Check time limit
            if time.time() - start_time > timeLimit:
                self.status = gu.GRB.TIME_LIMIT
                self.objval = float('inf')
                return

        # Find best label at final day
        final_labels = labels_by_day[self.days[-1]]

        if not final_labels:
            self.status = gu.GRB.INFEASIBLE
            self.objval = float('inf')
            return

        # No total workdays constraint in MIP (as per analysis)
        # So all final labels are feasible (assuming step-by-step constraints met)
        feasible_labels = final_labels

        if not feasible_labels:
            self.status = gu.GRB.INFEASIBLE
            self.objval = float('inf')
            return

        self.best_label = min(feasible_labels, key=lambda l: l.cost)
        self.status = gu.GRB.OPTIMAL
        self.objval = self.best_label.cost

    def _generate_transitions(self, label: Label, next_day: int) -> List[Label]:
        """
        Generate all feasible transitions from a label to the next day.

        Args:
            label: Current label
            next_day: Next day index

        Returns:
            List of new labels for the next day
        """
        new_labels = []

        # Option 1: Day off
        if self._is_day_off_feasible(label, next_day):
            new_label = self._create_day_off_label(label, next_day)
            if new_label:
                new_labels.append(new_label)

        # Option 2: Work each shift
        for shift in self.shifts:
            if self._is_shift_feasible(label, next_day, shift):
                new_label = self._create_shift_label(label, next_day, shift)
                if new_label:
                    new_labels.append(new_label)

        return new_labels

    def _is_day_off_feasible(self, label: Label, next_day: int) -> bool:
        """Check if taking a day off is feasible."""
        # Check minimum consecutive workdays
        # Only enforce if there are enough days remaining to satisfy Min_WD
        # This matches the MIP formulation where the constraint only applies
        # when t is not too close to the end of the planning horizon
        if label.omega > 0 and label.omega < self.Min_WD:
            # Check if there are enough days left in the horizon
            remaining_days = len(self.days) - next_day + 1
            if remaining_days >= self.Min_WD:
                return False

        # Start-of-Horizon Min_WD constraint (matches MIP line 161-163):
        # If y[1]=1 (started working on day 1), must work at least Min_WD days
        # Check if the first workday was day 1 and we're still in the initial block
        if label.omega > 0 and label.omega < self.Min_WD:
            # Check if work started on day 1
            first_work_day = None
            for d, s in label.path:
                if s is not None:
                    first_work_day = d
                    break
            if first_work_day == 1:
                # Must continue working until Min_WD is reached
                return False

        return True

    def _is_shift_feasible(self, label: Label, next_day: int, shift: int) -> bool:
        """Check if working a shift is feasible."""
        # Check maximum consecutive workdays
        # Only relevant if currently working (omega > 0)
        # If omega < 0 (off), this check passes (-X < Max_WD)
        if label.omega >= self.Max_WD:
            return False
        
        # Check Min Consecutive Days Off
        # If we are currently OFF (omega < 0), we must satisfy Days_Off before returning to work
        # UNLESS we haven't worked yet (Late Start case)
        if label.omega < 0:
            # Check if we have ever worked
            has_worked = False
            for d, s in label.path:
                if s is not None:
                    has_worked = True
                    break
            
            if has_worked:
                consecutive_off = abs(label.omega)
                if consecutive_off < self.Days_Off:
                    return False
        
        # Check forbidden shift sequences
        # Only relevant if we worked yesterday (s_last is not None)
        if label.s_last is not None and label.path:
            for (forbidden_shift1, forbidden_shift2) in self.F_S:
                if label.s_last == forbidden_shift1 and shift == forbidden_shift2:
                    return False

        return True

    def _create_day_off_label(self, label: Label, next_day: int) -> Optional[Label]:
        """Create a new label for taking a day off."""
        new_label = label.copy()
        new_label.day = next_day
        # s_last remains the same (conceptually, though usually ignored if day off)
        # Actually s_last should be None?
        # Existing code kept s_last same? No.
        # Check Label definition: "s_last: Optional[int] # None means no shift worked yet (or day off)"
        # But if we take day off, s_last should probably reflect LAST shift before today?
        # The dominance uses s_last.
        # If s_last is None, we are in OFF state.
        # But wait, original code did NOT set s_last = None in _create_day_off_label?
        # Original: "s_last remains the same".
        # If s_last remains same, then next day we know what shift we returned from?
        # But dominance checks s_last equality.
        # If I worked S1 yesterday, then take Day Off. s_last=1?
        # Then another label Worked S2 yesterday, then Day Off. s_last=2?
        # Do they separate?
        # No, "Day Off" state should merge regardless of previous shift (if history satisfied).
        # Unless S_last limits future shifts? NO.
        # But SC (Shift Change) logic?
        # If I work S1, Off, S2. SC=1?
        # If I work S1, Off, S1. SC=0?
        # If standard says "Reset after Off", then SC=1 always?
        # Code: "c_new = 1 in _create_shift_label if label.s_last is not None..."
        # So we NEED to know previous shift even through Day Off?
        # NO. "s_last is None" implies Day Off.
        # If Day Off, s_last should be None to allow merging?
        
        # Let's check original code:
        # "new_label = label.copy()" -> Copies s_last.
        # DOMINANCE: "if self.s_last != other.s_last: return False".
        # So labels with different previous shifts DO NOT MERGE even if currently OFF.
        # This keeps history for SC calculation?
        # IF SC is relevant across days off.
        # Usually SC resets if Off.
        # If SC resets, then s_last can limit merging unnecessarily.
        
        # In _create_shift_label:
        # "if label.s_last is None and len(label.path) > 0:" -> First shift after Off.
        # "last_worked_shift = ... find in path".
        # So it looks back in PATH to find last shift!
        # It does NOT use s_last if s_last is None.
        
        # So, if we take Day Off, we SHOULD set s_last = None.
        # Original code comment said "s_last remains same".
        # BUT _create_day_off_label did NOT modify it.
        # If label came from Shift, s_last=1.
        # New label Day Off, s_last=1.
        # Dominance s_last != s_last.
        
        # Wait, if s_last is not None, then _is_shift_feasible checks forbidden sequences?
        # "if label.s_last is not None...".
        # If I am OFF, I shouldn't trigger forbidden sequence from PREVIOUS work?
        # Usually forbidden sequence is (today, tomorrow).
        # Not (yesterday, today_off, tomorrow).
        
        # So s_last MUST be None for Day Off!
        
        # Let's fix this too if it wasn't clear.
        # But main task is Omega.
        
    def _create_day_off_label(self, label: Label, next_day: int) -> Optional[Label]:
        """Create a new label for taking a day off."""
        new_label = label.copy()
        new_label.day = next_day
        new_label.s_last = None  # Explicitly set to None for Day Off
        
        # Update omega (Signed: Negative for consecutive off)
        if label.omega > 0:
            new_label.omega = -1  # Switching from Work to Off
        else:
            new_label.omega = label.omega - 1 # Extending Off block (e.g. 0 -> -1, -1 -> -2)
            
        # total_workdays unchanged (day off)
        c_new = 0

        if self.model_type == 'linear':
            new_label.nu = 0
            rho_temp = label.rho + 1
            r_new = 1 if rho_temp >= self.chi else 0
            new_label.rho = rho_temp
            e_new = max(0.0, min(float(label.e + c_new - r_new), float(self.omega_max)))
            new_label.e = e_new
            kappa = 1 if new_label.e >= self.omega_max else 0
            p_new = 1.0 - self.epsilon * new_label.e - self.xi * kappa
        else:
            new_label.nu = 0
            new_label.rho = label.rho + 1
            recov = r_func(new_label.rho, self.chi, self.gamma_R, self.alpha_R)
            new_label.e = max(0.0, label.e - recov)
            p_new = 1.0 - new_label.e
            r_new = 1.0 if (new_label.rho >= self.chi) else 0.0
            
        pf = getattr(self, 'enforce_performance_floor', None)
        if pf is not None and p_new < pf:
            return None

        # No cost contribution (no work)
        new_label.cost = label.cost

        # Update path
        new_label.path.append((next_day, None))
        new_label.sc_history.append(c_new)
        new_label.r_history.append(int(r_new))
        new_label.p_history.append(p_new)

        return new_label


    def _create_shift_label(self, label: Label, next_day: int, shift: int) -> Optional[Label]:
        """Create a new label for working a specific shift."""
        new_label = label.copy()
        new_label.day = next_day
        new_label.total_workdays = label.total_workdays + 1  # Increment workdays

        # Shift change detection - use last_worked_shift for consistency
        c_new = 0
        if label.last_worked_shift is not None and label.last_worked_shift != shift:
            c_new = 1
            
        if getattr(self, 'enforce_no_change', False) and c_new > 0:
            return None

        if self._violates_ecp(label, c_new):
            return None

        # Update shift tracking
        new_label.s_last = shift
        new_label.last_worked_shift = shift  # Update last worked shift
        
        # Update omega (Signed: Positive for consecutive work)
        if label.omega < 0:
            new_label.omega = 1  # Switching from Off to Work
        else:
            new_label.omega = label.omega + 1 # Extending Work block

        if self.model_type == 'linear':
            new_label.nu = 0
            rho_temp = label.rho + 1 if c_new == 0 else 0
            r_new = 1 if rho_temp >= self.chi else 0
            new_label.rho = rho_temp
            e_new = max(0.0, min(float(label.e + c_new - r_new), float(self.omega_max)))
            new_label.e = e_new
            kappa = 1 if new_label.e >= self.omega_max else 0
            p_new = 1.0 - self.epsilon * new_label.e - self.xi * kappa
        else:
            delta = self.delta
            if delta is None:
                from core.worker_groups import get_default_delta
                delta = get_default_delta(self.epsilon)
            
            if c_new == 1:
                new_label.nu = label.nu + 1
                new_label.rho = 0
                degrad = delta[label.last_worked_shift, shift] * h_func(new_label.nu, self.gamma_C)
                new_label.e = min(self.e_max, label.e + degrad)
                r_new = 0.0
            else:
                new_label.nu = 0
                new_label.rho = label.rho + 1
                recov = r_func(new_label.rho, self.chi, self.gamma_R, self.alpha_R)
                new_label.e = max(0.0, label.e - recov)
                r_new = 1.0 if (new_label.rho >= self.chi) else 0.0

            p_new = 1.0 - new_label.e

        pf = getattr(self, 'enforce_performance_floor', None)
        if pf is not None and p_new < pf:
            return None

        # Calculate cost contribution (reduced cost)
        dual_value = self.duals_ts.get((next_day, shift), 0.0)
        cost_contribution = -dual_value * p_new

        new_label.cost = label.cost + cost_contribution

        # Update path
        new_label.path.append((next_day, shift))
        new_label.sc_history.append(c_new)
        new_label.r_history.append(int(r_new))
        new_label.p_history.append(p_new)

        return new_label

    def _prune_dominated(self, labels: List[Label], is_final_day: bool =  False) -> List[Label]:
        """
        Remove dominated labels from a list.

        Args:
            labels: List of labels to prune
            is_final_day: If True, only compare cost and total_workdays (no future flexibility needed)

        Returns:
            List of non-dominated labels
        """
        if not labels:
            return []

        # Group by the FULL dominance-relevant state (not just day, s_last):
        # within such a group every label is state-identical by construction,
        # so the lowest-cost member is trivially the sole non-dominated
        # survivor -- O(n) instead of the O(n^2) pairwise dominates() scan
        # this replaces, which becomes the bottleneck once label counts grow
        # (e.g. multi-day beta_g jumps in the off-day extension).
        if is_final_day:
            # For the final day only accumulated cost matters (base dominates()),
            # so a single global min suffices.
            return [min(labels, key=lambda l: l.cost)]

        label_groups: Dict[tuple, List[Label]] = {}
        for label in labels:
            key = (label.day, label.s_last, label.last_worked_shift,
                   round(label.e, 3), label.rho, label.omega, label.nu)
            label_groups.setdefault(key, []).append(label)

        non_dominated = []
        for group_labels in label_groups.values():
            if len(group_labels) == 1:
                non_dominated.append(group_labels[0])
            else:
                non_dominated.append(min(group_labels, key=lambda l: l.cost))

        return non_dominated

    # Interface methods for compatibility with MIP-based Subproblem

    def getStatus(self):
        """Get solution status (GRB.OPTIMAL, GRB.INFEASIBLE, etc.)."""
        return self.status if self.status is not None else gu.GRB.LOADED

    def getNewSchedule(self):
        """Get the performance schedule (for adding to master problem)."""
        if self.best_label is None:
            return {}

        schedule = {}
        for day in self.days:
            for shift in self.shifts:
                # Find performance for this day/shift combination
                if day <= len(self.best_label.path):
                    path_day, path_shift = self.best_label.path[day - 1]
                    if path_shift == shift:
                        perf = self.best_label.p_history[day - 1]
                    else:
                        perf = 0.0
                else:
                    perf = 0.0
                schedule[(day, shift, self.itr)] = perf

        return schedule

    def getOptX(self):
        """Get binary decision variables (shift assignments)."""
        if self.best_label is None:
            return {}

        x = {}
        for day in self.days:
            for shift in self.shifts:
                if day <= len(self.best_label.path):
                    path_day, path_shift = self.best_label.path[day - 1]
                    x[(day, shift)] = 1.0 if path_shift == shift else 0.0
                else:
                    x[(day, shift)] = 0.0

        return x

    def getOptP(self):
        """Get performance values by day."""
        if self.best_label is None:
            return {}

        p = {}
        for i, day in enumerate(self.days):
            if i < len(self.best_label.p_history):
                p[day] = self.best_label.p_history[i]
            else:
                p[day] = 1.0

        return p

    def getOptC(self):
        """Get shift change indicators."""
        if self.best_label is None:
            return {}

        sc = {}
        for i, day in enumerate(self.days):
            if i < len(self.best_label.sc_history):
                sc[day] = float(self.best_label.sc_history[i])
            else:
                sc[day] = 0.0

        return sc

    def getOptR(self):
        """Get recovery indicators."""
        if self.best_label is None:
            return {}

        r = {}
        for i, day in enumerate(self.days):
            if i < len(self.best_label.r_history):
                r[day] = float(self.best_label.r_history[i])
            else:
                r[day] = 0.0

        return r

    def getOptEUp(self):
        """Get performance level increase indicators."""
        if self.best_label is None:
            return {}

        # e_up is when we have a shift change at max performance
        e_up = {}
        for i, day in enumerate(self.days):
            if i > 0 and i < len(self.best_label.sc_history):
                # Check if this is a shift change while at high performance level
                e_up[day] = 0.0  # Simplified for now
            else:
                e_up[day] = 0.0

        return e_up

    def getOptElow(self):
        """Get performance level decrease indicators (recovery effects)."""
        if self.best_label is None:
            return {}

        # e_low is when recovery brings performance back up
        e_low = {}
        for i, day in enumerate(self.days):
            if i < len(self.best_label.r_history):
                # When recovery happens without shift change
                if i > 0:
                    r_val = self.best_label.r_history[i]
                    sc_val = self.best_label.sc_history[i]
                    e_low[day] = 1.0 if (r_val == 1 and sc_val == 0) else 0.0
                else:
                    e_low[day] = 0.0
            else:
                e_low[day] = 0.0

        return e_low

    def getOptPerf(self):
        """Get performance schedule (same as getNewSchedule but different format)."""
        return self.getNewSchedule()
