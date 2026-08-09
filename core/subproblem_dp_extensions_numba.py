"""Numba-JIT pricing subproblems for the four paper extensions (see
Datei/extensions.tex), mirroring core/subproblem_dp_extensions.py (the exact
Python label-setting versions) but backed by bit-packed njit kernels like
core/subproblem_dp_optimized.py's base-case forward_pass_numba.

Each extension gets its own specialized kernel (copied and modified from
forward_pass_numba) rather than a single flag-driven kernel, so the verified
base-case kernel and its pack_state layout stay untouched. Bidirectional
labeling (labeling_bidir) is intentionally not implemented for any extension
here -- the pure-Python DP extensions don't have it either.
"""
import numpy as np
import gurobipy as gu

from .subproblem_dp_optimized import (
    njit, NUMBA_AVAILABLE, pack_state, unpack_state, popcount6, SubproblemDPNumba,
    merge_bidirectional,
)
from .nonlinear_transitions import h_func, r_func


class _NumbaECPMixin:
    """Adds addECPConstraint(k), matching core.subproblem_dp.SubproblemDP's
    interface. SubproblemDPNumba lacks this method (it only ever reads
    getattr(self, 'ecp_k', -1)), but the loop_*_labeling.py driver scripts
    call sp.addECPConstraint(K_ECP) unconditionally for ECP mode."""

    def addECPConstraint(self, k):
        self.ecp_k = k


def _finalize_forward(sp, states, costs, paths, n_states):
    """Populate objval/best_path/all_optimal_paths/n_optimal/status from a
    forward-pass result. Mirrors the post-processing tail of
    SubproblemDPNumba._solve_forward_only (duplicated here, not called into,
    since these results come from the extension-specific kernels below)."""
    if n_states > 0:
        best_cost = np.min(costs[:n_states])
        sp.objval = best_cost
        tol = 1e-9
        sp.all_optimal_paths = []
        for idx in range(n_states):
            if abs(costs[idx] - best_cost) < tol:
                sp.all_optimal_paths.append(paths[idx].copy())
        sp.n_optimal = len(sp.all_optimal_paths)
        sp.best_path = sp.all_optimal_paths[0] if sp.all_optimal_paths else None
        sp.status = gu.GRB.OPTIMAL
    else:
        sp.objval = float('inf')
        sp.status = gu.GRB.INFEASIBLE
        sp.n_optimal = 0


# =============================================================================
# Extension 4 (Case A): Heterogeneous Worker Qualifications (clean partition)
# extensions.tex app:ext:qual: "the only modification is the set of feasible
# arcs: for the (g,q)-SP, shift arcs for s not in S_q are removed from the
# state-space graph entirely." Mirrors SubproblemQualificationsDP.
# =============================================================================
@njit(cache=True)
def forward_pass_qual_a(
    n_days, n_shifts, duals_flat, duals_i, chi, min_wd, max_wd, days_off,
    suffix_bounds, stop_day, enforce_no_change, enforce_performance_floor,
    gamma_R, gamma_C, alpha_R, delta_flat, e_max, ecp_k, eligible_mask,
):
    MAX_STATES = 200000

    curr_states = np.zeros(MAX_STATES, dtype=np.int64)
    curr_costs = np.zeros(MAX_STATES, dtype=np.float64)
    curr_paths = np.zeros((MAX_STATES, n_days + 1), dtype=np.int8)

    next_states = np.zeros(MAX_STATES, dtype=np.int64)
    next_costs = np.zeros(MAX_STATES, dtype=np.float64)
    next_paths = np.zeros((MAX_STATES, n_days + 1), dtype=np.int8)

    curr_states[0] = pack_state(0, 0, 0, 0.0, 0, 0, 1, 0)
    curr_costs[0] = -duals_i
    n_curr = 1

    best_cost = np.inf
    forbidden = np.array([[3, 1], [3, 2], [2, 1]], dtype=np.int32)

    for d in range(stop_day):
        next_day = d + 1
        n_next = 0
        days_remaining = n_days - next_day + 1

        for i in range(n_curr):
            state = curr_states[i]
            cost = curr_costs[i]

            if cost - suffix_bounds[next_day - 1] >= best_cost - 1e-9:
                continue

            omega, rho, nu, e, last_worked, s_last, first_flag, cw = unpack_state(state)
            has_worked = last_worked > 0

            can_off = True
            if omega > 0 and omega < min_wd:
                if days_remaining >= min_wd or first_flag == 1:
                    can_off = False

            if can_off and n_next < MAX_STATES:
                new_rho = rho + 1
                new_nu = 0
                new_cw_off = (cw << 1) & 0x3F
                recov = r_func(new_rho, chi, gamma_R, alpha_R)
                new_e = max(0.0, e - recov)
                p_new_off = 1.0 - new_e
                if enforce_performance_floor > 0.0 and p_new_off < enforce_performance_floor:
                    can_off = False
                if can_off:
                    next_states[n_next] = pack_state(-1 if omega > 0 else omega - 1, new_rho, new_nu, new_e, last_worked, 0, first_flag, new_cw_off)
                    next_costs[n_next] = cost
                    next_paths[n_next, :] = curr_paths[i, :]
                    next_paths[n_next, next_day] = -1
                    n_next += 1

            for shift in range(1, n_shifts + 1):
                # Qualifications Case A: shifts outside the (g,q) eligible set
                # are structurally infeasible arcs.
                if not ((eligible_mask >> (shift - 1)) & 1):
                    continue
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

                c_new = 1 if (last_worked > 0 and last_worked != shift) else 0

                if ecp_k >= 0 and (popcount6(cw) + c_new) > ecp_k:
                    continue
                new_cw = ((cw << 1) | c_new) & 0x3F

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
                    next_states[n_next] = pack_state(1 if omega <= 0 else omega + 1, new_rho, new_nu, new_e, shift, shift, new_first, new_cw)
                    next_costs[n_next] = new_cost
                    next_paths[n_next, :] = curr_paths[i, :]
                    next_paths[n_next, next_day] = shift
                    n_next += 1

                if next_day == n_days and new_cost < best_cost:
                    best_cost = new_cost

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


class SubproblemQualificationsNumba(_NumbaECPMixin, SubproblemDPNumba):
    def __init__(self, duals_i, duals_ts, df, i, iteration, eps, Min_WD_i, Max_WD_i, chi,
                 eligible_shifts, model_type='nonlinear'):
        super().__init__(duals_i, duals_ts, df, i, iteration, eps, Min_WD_i, Max_WD_i, chi, model_type)
        self.eligible_shifts = set(eligible_shifts)
        mask = 0
        for s in self.eligible_shifts:
            mask |= (1 << (s - 1))
        self.eligible_mask = mask

    def solveModelOpt(self, timeLimit):
        n_days = len(self.days)
        n_shifts = len(self.shifts)
        if not NUMBA_AVAILABLE:
            self.objval, self.status, self.n_optimal = float('inf'), gu.GRB.INFEASIBLE, 0
            return
        enc_nc = 1 if getattr(self, 'enforce_no_change', False) else 0
        enc_pf = getattr(self, 'enforce_performance_floor', None)
        enc_pf = float(enc_pf) if enc_pf is not None else 0.0
        gamma_C, gamma_R, alpha_R, delta_flat, e_max = self._prepare_jit_params()
        ecp_k = int(getattr(self, 'ecp_k', -1))

        states, costs, paths, n_states = forward_pass_qual_a(
            n_days, n_shifts, self.duals_flat, self.duals_i, self.chi,
            self.Min_WD, self.Max_WD, self.Days_Off, self.suffix_bounds, n_days,
            enc_nc, enc_pf, gamma_R, gamma_C, alpha_R, delta_flat, e_max, ecp_k,
            self.eligible_mask,
        )
        _finalize_forward(self, states, costs, paths, n_states)

    def solveModelNOpt(self, timeLimit):
        self.solveModelOpt(timeLimit)


# =============================================================================
# Extension 2: Off-Day Recovery (beta_g multiplier)
# extensions.tex app:ext:offday, ext:spell:off: the off-day arc increments the
# stable-day counter by beta_g instead of 1: rho^+ = rho + round(beta_g).
# Mirrors SubproblemOffdayDP.
#
# rho needs 8 bits here (not the shared pack_state's 6): beta_g in {1,2,3}
# (see BETAS in loop_offday.py) over a multi-week off-block can push rho past
# 63, silently wrapping in a 6-bit field and corrupting dominance grouping.
# Local pack/unpack variants below widen rho and keep the rest of the layout
# unchanged; the shared pack_state used by the base case and other extensions
# is untouched.
# =============================================================================
@njit(cache=True)
def pack_state_od(omega, rho, nu, e, last_worked, s_last, first_flag, cw):
    e_int = int(round(e * 100000))
    return np.int64(((omega + 10) & 0x1F) |
                    ((rho & 0xFF) << 5) |
                    ((nu & 0x3F) << 13) |
                    ((e_int & 0x1FFFF) << 19) |
                    ((last_worked & 0x7) << 36) |
                    ((s_last & 0x7) << 39) |
                    ((first_flag & 0x1) << 42) |
                    ((cw & 0x3F) << 43))


@njit(cache=True)
def unpack_state_od(state):
    omega = (state & 0x1F) - 10
    rho = (state >> 5) & 0xFF
    nu = (state >> 13) & 0x3F
    e_int = (state >> 19) & 0x1FFFF
    e = e_int / 100000.0
    last_worked = (state >> 36) & 0x7
    s_last = (state >> 39) & 0x7
    first_flag = (state >> 42) & 0x1
    cw = (state >> 43) & 0x3F
    return omega, rho, nu, e, last_worked, s_last, first_flag, cw


@njit(cache=True)
def forward_pass_offday(
    n_days, n_shifts, duals_flat, duals_i, chi, min_wd, max_wd, days_off,
    suffix_bounds, stop_day, enforce_no_change, enforce_performance_floor,
    gamma_R, gamma_C, alpha_R, delta_flat, e_max, ecp_k, beta_g,
):
    MAX_STATES = 200000

    curr_states = np.zeros(MAX_STATES, dtype=np.int64)
    curr_costs = np.zeros(MAX_STATES, dtype=np.float64)
    curr_paths = np.zeros((MAX_STATES, n_days + 1), dtype=np.int8)

    next_states = np.zeros(MAX_STATES, dtype=np.int64)
    next_costs = np.zeros(MAX_STATES, dtype=np.float64)
    next_paths = np.zeros((MAX_STATES, n_days + 1), dtype=np.int8)

    curr_states[0] = pack_state_od(0, 0, 0, 0.0, 0, 0, 1, 0)
    curr_costs[0] = -duals_i
    n_curr = 1

    best_cost = np.inf
    forbidden = np.array([[3, 1], [3, 2], [2, 1]], dtype=np.int32)

    for d in range(stop_day):
        next_day = d + 1
        n_next = 0
        days_remaining = n_days - next_day + 1

        for i in range(n_curr):
            state = curr_states[i]
            cost = curr_costs[i]

            if cost - suffix_bounds[next_day - 1] >= best_cost - 1e-9:
                continue

            omega, rho, nu, e, last_worked, s_last, first_flag, cw = unpack_state_od(state)
            has_worked = last_worked > 0

            can_off = True
            if omega > 0 and omega < min_wd:
                if days_remaining >= min_wd or first_flag == 1:
                    can_off = False

            if can_off and n_next < MAX_STATES:
                new_rho = rho + beta_g  # off-day arc: rho advances by beta_g (ext:spell:off)
                new_nu = 0
                new_cw_off = (cw << 1) & 0x3F
                recov = r_func(new_rho, chi, gamma_R, alpha_R)
                new_e = max(0.0, e - recov)
                p_new_off = 1.0 - new_e
                if enforce_performance_floor > 0.0 and p_new_off < enforce_performance_floor:
                    can_off = False
                if can_off:
                    next_states[n_next] = pack_state_od(-1 if omega > 0 else omega - 1, new_rho, new_nu, new_e, last_worked, 0, first_flag, new_cw_off)
                    next_costs[n_next] = cost
                    next_paths[n_next, :] = curr_paths[i, :]
                    next_paths[n_next, next_day] = -1
                    n_next += 1

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

                c_new = 1 if (last_worked > 0 and last_worked != shift) else 0

                if ecp_k >= 0 and (popcount6(cw) + c_new) > ecp_k:
                    continue
                new_cw = ((cw << 1) | c_new) & 0x3F

                # Work-continuation rho is unaffected by beta_g (only the
                # off-day arc is rescaled per extensions.tex).
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
                    next_states[n_next] = pack_state_od(1 if omega <= 0 else omega + 1, new_rho, new_nu, new_e, shift, shift, new_first, new_cw)
                    next_costs[n_next] = new_cost
                    next_paths[n_next, :] = curr_paths[i, :]
                    next_paths[n_next, next_day] = shift
                    n_next += 1

                if next_day == n_days and new_cost < best_cost:
                    best_cost = new_cost

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
def forward_pass_offday_from_states(
    n_days, n_shifts, duals_flat, chi, min_wd, max_wd, days_off,
    start_day, init_states, init_costs, n_init,
    enforce_no_change, enforce_performance_floor,
    gamma_R, gamma_C, alpha_R, delta_flat, e_max, ecp_k, beta_g,
):
    """Second half of the bidirectional pass for the off-day extension.

    Mirrors forward_pass_from_states (base case) but uses pack_state_od /
    unpack_state_od (8-bit rho) and advances rho by beta_g on off-day arcs.
    Tracks curr_init_idx so merge_bidirectional can stitch the two halves.
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

            omega, rho, nu, e, last_worked, s_last, first_flag, cw = unpack_state_od(state)
            has_worked = last_worked > 0

            can_off = True
            if omega > 0 and omega < min_wd:
                if days_remaining >= min_wd or first_flag == 1:
                    can_off = False

            if can_off and n_next < MAX_STATES:
                new_rho = rho + beta_g
                new_nu = 0
                new_cw_off = (cw << 1) & 0x3F
                recov = r_func(new_rho, chi, gamma_R, alpha_R)
                new_e = max(0.0, e - recov)
                p_new_off = 1.0 - new_e
                if enforce_performance_floor > 0.0 and p_new_off < enforce_performance_floor:
                    can_off = False
                if can_off:
                    next_states[n_next] = pack_state_od(-1 if omega > 0 else omega - 1, new_rho, new_nu, new_e, last_worked, 0, first_flag, new_cw_off)
                    next_costs[n_next] = cost
                    next_init_idx[n_next] = init_idx
                    next_paths[n_next, :] = curr_paths[i, :]
                    next_paths[n_next, next_day] = -1
                    n_next += 1

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

                c_new = 1 if (last_worked > 0 and last_worked != shift) else 0

                if ecp_k >= 0 and (popcount6(cw) + c_new) > ecp_k:
                    continue
                new_cw = ((cw << 1) | c_new) & 0x3F

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
                    next_states[n_next] = pack_state_od(1 if omega <= 0 else omega + 1, new_rho, new_nu, new_e, shift, shift, new_first, new_cw)
                    next_costs[n_next] = new_cost
                    next_init_idx[n_next] = init_idx
                    next_paths[n_next, :] = curr_paths[i, :]
                    next_paths[n_next, next_day] = shift
                    n_next += 1

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


class SubproblemOffdayNumba(_NumbaECPMixin, SubproblemDPNumba):
    def __init__(self, duals_i, duals_ts, df, i, iteration, eps, Min_WD_i, Max_WD_i, chi,
                 beta_g=1, model_type='nonlinear'):
        super().__init__(duals_i, duals_ts, df, i, iteration, eps, Min_WD_i, Max_WD_i, chi, model_type)
        self.beta_g = beta_g

    def solveModelOpt(self, timeLimit):
        n_days = len(self.days)
        n_shifts = len(self.shifts)
        if not NUMBA_AVAILABLE:
            self.objval, self.status, self.n_optimal = float('inf'), gu.GRB.INFEASIBLE, 0
            return
        enc_nc = 1 if getattr(self, 'enforce_no_change', False) else 0
        enc_pf = getattr(self, 'enforce_performance_floor', None)
        enc_pf = float(enc_pf) if enc_pf is not None else 0.0
        gamma_C, gamma_R, alpha_R, delta_flat, e_max = self._prepare_jit_params()
        ecp_k = int(getattr(self, 'ecp_k', -1))
        beta_g = round(self.beta_g)

        use_bidir = getattr(self, '_use_bidir', False)
        if use_bidir and n_days >= 8:
            mid_day = n_days // 2
            fwd_states, fwd_costs, fwd_paths, n_fwd = forward_pass_offday(
                n_days, n_shifts, self.duals_flat, self.duals_i, self.chi,
                self.Min_WD, self.Max_WD, self.Days_Off, self.suffix_bounds, mid_day,
                enc_nc, enc_pf, gamma_R, gamma_C, alpha_R, delta_flat, e_max, ecp_k, beta_g,
            )
            if n_fwd > 0:
                _, second_costs, second_init_idx, second_paths, n_second = \
                    forward_pass_offday_from_states(
                        n_days, n_shifts, self.duals_flat, self.chi,
                        self.Min_WD, self.Max_WD, self.Days_Off,
                        mid_day, fwd_states, fwd_costs, n_fwd,
                        enc_nc, enc_pf, gamma_R, gamma_C, alpha_R, delta_flat, e_max, ecp_k, beta_g,
                    )
                if n_second > 0:
                    best_cost, best_path = merge_bidirectional(
                        fwd_states, fwd_costs, fwd_paths, n_fwd,
                        second_costs, second_init_idx, second_paths, n_second,
                        n_days, mid_day,
                    )
                    if best_cost < np.inf:
                        self.objval = best_cost
                        self.best_path = best_path
                        self.all_optimal_paths = [best_path.copy()]
                        self.n_optimal = 1
                        self.status = gu.GRB.OPTIMAL
                        return
            # fallback to forward-only if bidir produced nothing
            states, costs, paths, n_states = forward_pass_offday(
                n_days, n_shifts, self.duals_flat, self.duals_i, self.chi,
                self.Min_WD, self.Max_WD, self.Days_Off, self.suffix_bounds, n_days,
                enc_nc, enc_pf, gamma_R, gamma_C, alpha_R, delta_flat, e_max, ecp_k, beta_g,
            )
            _finalize_forward(self, states, costs, paths, n_states)
        else:
            states, costs, paths, n_states = forward_pass_offday(
                n_days, n_shifts, self.duals_flat, self.duals_i, self.chi,
                self.Min_WD, self.Max_WD, self.Days_Off, self.suffix_bounds, n_days,
                enc_nc, enc_pf, gamma_R, gamma_C, alpha_R, delta_flat, e_max, ecp_k, beta_g,
            )
            _finalize_forward(self, states, costs, paths, n_states)

    def solveModelNOpt(self, timeLimit):
        self.solveModelOpt(timeLimit)

    def _reconstruct_state_history(self):
        """Override of SubproblemDPNumba._reconstruct_state_history: off-day
        arcs must advance rho by beta_g here too, otherwise getOptP/getOptC/
        getOptR (and hence getNewSchedule, which feeds the master problem
        column) would reconstruct performance for a DIFFERENT rho trajectory
        than the one forward_pass_offday actually optimized over."""
        if self.best_path is None:
            return None

        n_days = len(self.days)
        chi = self.chi
        gamma_C = getattr(self, 'gamma_C', 1.25)
        gamma_R = getattr(self, 'gamma_R', 0.5)
        alpha_R = getattr(self, 'alpha_R', 0.04)
        e_max = getattr(self, 'e_max', 1.0)
        delta = getattr(self, 'delta', None)
        if delta is None:
            from core.worker_groups import get_default_delta
            delta = get_default_delta(self.epsilon)
        beta_g = round(self.beta_g)

        c_history = []
        last_worked = 0
        for d_idx in range(n_days):
            shift = int(self.best_path[d_idx + 1])
            if shift > 0:
                c = 1 if (last_worked > 0 and last_worked != shift) else 0
                last_worked = shift
            else:
                c = 0
            c_history.append(c)

        p_history = []
        r_history = []
        e = 0.0
        rho = 0
        nu = 0
        last_worked_shift = None
        for d_idx in range(n_days):
            shift = int(self.best_path[d_idx + 1])
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
                rho += beta_g
                nu = 0
                recov = r_func(rho, chi, gamma_R, alpha_R)
                e = max(0.0, e - recov)

            p = 1.0 - e
            p_history.append(p)
            r_history.append(1.0 if rho >= chi else 0.0)

        return {
            'p': p_history,
            'sc': c_history,
            'r': r_history,
            'e_up': [0.0] * n_days,
            'e_low': [0.0] * n_days,
        }


# =============================================================================
# Extension 3: Worker Day-Off Preferences
# extensions.tex app:ext:pref: "every working arc on a preferred day d in P_i
# incurs an additional cost +lambda^P... only the arc-cost lookup changes."
# Mirrors SubproblemPreferencesDP. suffix_bounds is unaffected: it already
# bounds the maximum possible cost DECREASE per remaining day, and the
# surcharge can only make the actual achievable decrease smaller, never
# larger -- so reusing the base (surcharge-unaware) bound stays a valid
# (if occasionally loose) upper bound.
# =============================================================================
@njit(cache=True)
def forward_pass_preferences(
    n_days, n_shifts, duals_flat, duals_i, chi, min_wd, max_wd, days_off,
    suffix_bounds, stop_day, enforce_no_change, enforce_performance_floor,
    gamma_R, gamma_C, alpha_R, delta_flat, e_max, ecp_k, pref_mask, lam_pref,
):
    MAX_STATES = 200000

    curr_states = np.zeros(MAX_STATES, dtype=np.int64)
    curr_costs = np.zeros(MAX_STATES, dtype=np.float64)
    curr_paths = np.zeros((MAX_STATES, n_days + 1), dtype=np.int8)

    next_states = np.zeros(MAX_STATES, dtype=np.int64)
    next_costs = np.zeros(MAX_STATES, dtype=np.float64)
    next_paths = np.zeros((MAX_STATES, n_days + 1), dtype=np.int8)

    curr_states[0] = pack_state(0, 0, 0, 0.0, 0, 0, 1, 0)
    curr_costs[0] = -duals_i
    n_curr = 1

    best_cost = np.inf
    forbidden = np.array([[3, 1], [3, 2], [2, 1]], dtype=np.int32)

    for d in range(stop_day):
        next_day = d + 1
        n_next = 0
        days_remaining = n_days - next_day + 1

        for i in range(n_curr):
            state = curr_states[i]
            cost = curr_costs[i]

            if cost - suffix_bounds[next_day - 1] >= best_cost - 1e-9:
                continue

            omega, rho, nu, e, last_worked, s_last, first_flag, cw = unpack_state(state)
            has_worked = last_worked > 0

            can_off = True
            if omega > 0 and omega < min_wd:
                if days_remaining >= min_wd or first_flag == 1:
                    can_off = False

            if can_off and n_next < MAX_STATES:
                new_rho = rho + 1
                new_nu = 0
                new_cw_off = (cw << 1) & 0x3F
                recov = r_func(new_rho, chi, gamma_R, alpha_R)
                new_e = max(0.0, e - recov)
                p_new_off = 1.0 - new_e
                if enforce_performance_floor > 0.0 and p_new_off < enforce_performance_floor:
                    can_off = False
                if can_off:
                    next_states[n_next] = pack_state(-1 if omega > 0 else omega - 1, new_rho, new_nu, new_e, last_worked, 0, first_flag, new_cw_off)
                    next_costs[n_next] = cost
                    next_paths[n_next, :] = curr_paths[i, :]
                    next_paths[n_next, next_day] = -1
                    n_next += 1

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

                c_new = 1 if (last_worked > 0 and last_worked != shift) else 0

                if ecp_k >= 0 and (popcount6(cw) + c_new) > ecp_k:
                    continue
                new_cw = ((cw << 1) | c_new) & 0x3F

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
                if pref_mask[next_day - 1] == 1:
                    new_cost += lam_pref  # ext:obj:pref surcharge on preferred-day work arcs

                new_first = first_flag
                if not has_worked and next_day == 1:
                    new_first = 1

                if n_next < MAX_STATES:
                    next_states[n_next] = pack_state(1 if omega <= 0 else omega + 1, new_rho, new_nu, new_e, shift, shift, new_first, new_cw)
                    next_costs[n_next] = new_cost
                    next_paths[n_next, :] = curr_paths[i, :]
                    next_paths[n_next, next_day] = shift
                    n_next += 1

                if next_day == n_days and new_cost < best_cost:
                    best_cost = new_cost

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


class SubproblemPreferencesNumba(_NumbaECPMixin, SubproblemDPNumba):
    def __init__(self, duals_i, duals_ts, df, i, iteration, eps, Min_WD_i, Max_WD_i, chi,
                 pref_days, lam_pref, model_type='nonlinear'):
        super().__init__(duals_i, duals_ts, df, i, iteration, eps, Min_WD_i, Max_WD_i, chi, model_type)
        self.pref_days = set(pref_days)
        self.lam_pref = lam_pref
        n_days = len(self.days)
        pref_mask = np.zeros(n_days, dtype=np.int8)
        for d_idx, day in enumerate(self.days):
            if day in self.pref_days:
                pref_mask[d_idx] = 1
        self.pref_mask = pref_mask

    def solveModelOpt(self, timeLimit):
        n_days = len(self.days)
        n_shifts = len(self.shifts)
        if not NUMBA_AVAILABLE:
            self.objval, self.status, self.n_optimal = float('inf'), gu.GRB.INFEASIBLE, 0
            return
        enc_nc = 1 if getattr(self, 'enforce_no_change', False) else 0
        enc_pf = getattr(self, 'enforce_performance_floor', None)
        enc_pf = float(enc_pf) if enc_pf is not None else 0.0
        gamma_C, gamma_R, alpha_R, delta_flat, e_max = self._prepare_jit_params()
        ecp_k = int(getattr(self, 'ecp_k', -1))

        states, costs, paths, n_states = forward_pass_preferences(
            n_days, n_shifts, self.duals_flat, self.duals_i, self.chi,
            self.Min_WD, self.Max_WD, self.Days_Off, self.suffix_bounds, n_days,
            enc_nc, enc_pf, gamma_R, gamma_C, alpha_R, delta_flat, e_max, ecp_k,
            self.pref_mask, float(self.lam_pref),
        )
        _finalize_forward(self, states, costs, paths, n_states)

    def solveModelNOpt(self, timeLimit):
        self.solveModelOpt(timeLimit)


# =============================================================================
# Extension 1: Fairness in Shift-Type Allocation
# extensions.tex app:ext:fairness: label extended by burden resource f
# (f' = f + mu_s on shift-s arcs, f' = f on off-day arcs); terminal RC adds
# lambda*|f - Fbar|. Mirrors FairLabel/SubproblemFairnessDP.
#
# f_bin (round(f), matching FairLabel.F_BIN = 1.0) is packed into bits 47-54
# of the state (free in the shared pack_state layout, which uses bits 0-46)
# purely for dominance grouping -- mirrors the Python class keeping f exact
# for the terminal penalty but binning it only for the dominance key. The
# EXACT f is carried in a parallel float64 array alongside cost/path.
#
# No suffix-bound pruning here (unlike the other three extensions): that
# bound would need to lower-bound the eventual EFFECTIVE cost
# (raw cost + lambda*|f-Fbar|), but a raw-reduced-cost-only bound is NOT
# valid for that -- a partial label with worse raw cost can still win once a
# favorable terminal f is factored in, so bounding on raw cost alone can
# prune a label that would have become optimal. Dropped for correctness;
# dominance pruning (now keyed on state+f_bin) still bounds the state space.
# =============================================================================
@njit(cache=True)
def forward_pass_fairness(
    n_days, n_shifts, duals_flat, duals_i, chi, min_wd, max_wd, days_off,
    stop_day, enforce_no_change, enforce_performance_floor,
    gamma_R, gamma_C, alpha_R, delta_flat, e_max, ecp_k, mu_shift_flat,
):
    MAX_STATES = 200000

    curr_states = np.zeros(MAX_STATES, dtype=np.int64)
    curr_costs = np.zeros(MAX_STATES, dtype=np.float64)
    curr_f = np.zeros(MAX_STATES, dtype=np.float64)
    curr_paths = np.zeros((MAX_STATES, n_days + 1), dtype=np.int8)

    next_states = np.zeros(MAX_STATES, dtype=np.int64)
    next_costs = np.zeros(MAX_STATES, dtype=np.float64)
    next_f = np.zeros(MAX_STATES, dtype=np.float64)
    next_paths = np.zeros((MAX_STATES, n_days + 1), dtype=np.int8)

    curr_states[0] = pack_state(0, 0, 0, 0.0, 0, 0, 1, 0)
    curr_costs[0] = -duals_i
    curr_f[0] = 0.0
    n_curr = 1

    forbidden = np.array([[3, 1], [3, 2], [2, 1]], dtype=np.int32)

    for d in range(stop_day):
        next_day = d + 1
        n_next = 0
        days_remaining = n_days - next_day + 1

        for i in range(n_curr):
            state = curr_states[i]
            cost = curr_costs[i]
            f = curr_f[i]

            omega, rho, nu, e, last_worked, s_last, first_flag, cw = unpack_state(state)
            has_worked = last_worked > 0

            can_off = True
            if omega > 0 and omega < min_wd:
                if days_remaining >= min_wd or first_flag == 1:
                    can_off = False

            if can_off and n_next < MAX_STATES:
                new_rho = rho + 1
                new_nu = 0
                new_cw_off = (cw << 1) & 0x3F
                recov = r_func(new_rho, chi, gamma_R, alpha_R)
                new_e = max(0.0, e - recov)
                p_new_off = 1.0 - new_e
                if enforce_performance_floor > 0.0 and p_new_off < enforce_performance_floor:
                    can_off = False
                if can_off:
                    # off-day arc: f' = f (unchanged)
                    f_bin = np.int64(round(f)) & 0xFF
                    packed = pack_state(-1 if omega > 0 else omega - 1, new_rho, new_nu, new_e, last_worked, 0, first_flag, new_cw_off)
                    next_states[n_next] = packed | (f_bin << 47)
                    next_costs[n_next] = cost
                    next_f[n_next] = f
                    next_paths[n_next, :] = curr_paths[i, :]
                    next_paths[n_next, next_day] = -1
                    n_next += 1

            for shift in range(1, n_shifts + 1):
                if omega >= max_wd:
                    continue
                if omega < 0 and has_worked and -omega < days_off:
                    continue

                is_forbidden = False
                if s_last > 0:
                    for ff in range(3):
                        if forbidden[ff, 0] == s_last and forbidden[ff, 1] == shift:
                            is_forbidden = True
                            break
                if is_forbidden:
                    continue

                if enforce_no_change == 1 and last_worked > 0 and last_worked != shift:
                    continue

                c_new = 1 if (last_worked > 0 and last_worked != shift) else 0

                if ecp_k >= 0 and (popcount6(cw) + c_new) > ecp_k:
                    continue
                new_cw = ((cw << 1) | c_new) & 0x3F

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
                new_f = f + mu_shift_flat[shift]  # shift-s arc: f' = f + mu_s

                new_first = first_flag
                if not has_worked and next_day == 1:
                    new_first = 1

                if n_next < MAX_STATES:
                    f_bin = np.int64(round(new_f)) & 0xFF
                    packed = pack_state(1 if omega <= 0 else omega + 1, new_rho, new_nu, new_e, shift, shift, new_first, new_cw)
                    next_states[n_next] = packed | (f_bin << 47)
                    next_costs[n_next] = new_cost
                    next_f[n_next] = new_f
                    next_paths[n_next, :] = curr_paths[i, :]
                    next_paths[n_next, next_day] = shift
                    n_next += 1

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
                            curr_f[n_pruned] = next_f[kdx]
                            curr_paths[n_pruned, :] = next_paths[kdx, :]
                            n_pruned += 1
                i = j
            n_curr = n_pruned
        else:
            n_curr = 0
    return (curr_states[:n_curr].copy(), curr_costs[:n_curr].copy(),
            curr_f[:n_curr].copy(), curr_paths[:n_curr].copy(), n_curr)


class SubproblemFairnessNumba(_NumbaECPMixin, SubproblemDPNumba):
    def __init__(self, duals_i, duals_ts, df, i, iteration, eps, Min_WD_i, Max_WD_i, chi,
                 mu_shift, lam, F_bar, model_type='nonlinear'):
        super().__init__(duals_i, duals_ts, df, i, iteration, eps, Min_WD_i, Max_WD_i, chi, model_type)
        self.mu_shift = mu_shift
        self.lam = lam
        self.F_bar = F_bar
        n_shifts = len(self.shifts)
        mu_flat = np.zeros(n_shifts + 1, dtype=np.float64)
        for s in self.shifts:
            mu_flat[s] = mu_shift[s]
        self.mu_shift_flat = mu_flat
        self.best_f = 0.0

    def solveModelOpt(self, timeLimit):
        n_days = len(self.days)
        n_shifts = len(self.shifts)
        if not NUMBA_AVAILABLE:
            self.objval, self.status, self.n_optimal = float('inf'), gu.GRB.INFEASIBLE, 0
            return
        enc_nc = 1 if getattr(self, 'enforce_no_change', False) else 0
        enc_pf = getattr(self, 'enforce_performance_floor', None)
        enc_pf = float(enc_pf) if enc_pf is not None else 0.0
        gamma_C, gamma_R, alpha_R, delta_flat, e_max = self._prepare_jit_params()
        ecp_k = int(getattr(self, 'ecp_k', -1))

        states, costs, f_values, paths, n_states = forward_pass_fairness(
            n_days, n_shifts, self.duals_flat, self.duals_i, self.chi,
            self.Min_WD, self.Max_WD, self.Days_Off, n_days, enc_nc, enc_pf,
            gamma_R, gamma_C, alpha_R, delta_flat, e_max, ecp_k, self.mu_shift_flat,
        )

        if n_states > 0:
            # Terminal fairness penalty applied only now (post forward-pass),
            # exactly as SubproblemFairnessDP._solve does via effective_cost.
            effective = costs[:n_states] + self.lam * np.abs(f_values[:n_states] - self.F_bar)
            best_idx = int(np.argmin(effective))
            best_cost = effective[best_idx]
            tol = 1e-9
            self.all_optimal_paths = []
            for idx in range(n_states):
                if abs(effective[idx] - best_cost) < tol:
                    self.all_optimal_paths.append(paths[idx].copy())
            self.n_optimal = len(self.all_optimal_paths)
            self.best_path = paths[best_idx].copy()
            self.best_f = float(f_values[best_idx])
            self.objval = float(best_cost)
            self.status = gu.GRB.OPTIMAL
        else:
            self.objval, self.status, self.n_optimal = float('inf'), gu.GRB.INFEASIBLE, 0

    def solveModelNOpt(self, timeLimit):
        self.solveModelOpt(timeLimit)

    def getBurden(self):
        return self.best_f


# =============================================================================
# Extension 4 (Case B): Heterogeneous Worker Qualifications (overlapping)
# extensions.tex app:ext:qual, Case B: on each working arc (t,s), pricing
# branches over the qualification q in Q_s covered by shift s; the RC
# contribution differentiates by q through the qualification-specific demand
# dual pi_ds^q. Mirrors SubproblemQualificationsOverlapDP.
#
# Physiological state (e, rho, nu, omega, ...) is q-independent, so every
# (shift, q) branch for a fixed shift leads to the SAME packed state -- the
# existing dominance-pruning-by-state logic already picks the cheapest arc
# per state; a parallel path_q array (mirroring paths) is carried through the
# same copy/prune steps so the winning q is recoverable afterwards.
# =============================================================================
@njit(cache=True)
def forward_pass_qual_b(
    n_days, n_shifts, duals_q_flat, duals_i, chi, min_wd, max_wd, days_off,
    suffix_bounds, stop_day, enforce_no_change, enforce_performance_floor,
    gamma_R, gamma_C, alpha_R, delta_flat, e_max, ecp_k, eligible_q_mask, qmax,
):
    MAX_STATES = 200000

    curr_states = np.zeros(MAX_STATES, dtype=np.int64)
    curr_costs = np.zeros(MAX_STATES, dtype=np.float64)
    curr_paths = np.zeros((MAX_STATES, n_days + 1), dtype=np.int8)
    curr_path_q = np.zeros((MAX_STATES, n_days + 1), dtype=np.int8)

    next_states = np.zeros(MAX_STATES, dtype=np.int64)
    next_costs = np.zeros(MAX_STATES, dtype=np.float64)
    next_paths = np.zeros((MAX_STATES, n_days + 1), dtype=np.int8)
    next_path_q = np.zeros((MAX_STATES, n_days + 1), dtype=np.int8)

    curr_states[0] = pack_state(0, 0, 0, 0.0, 0, 0, 1, 0)
    curr_costs[0] = -duals_i
    n_curr = 1

    best_cost = np.inf
    forbidden = np.array([[3, 1], [3, 2], [2, 1]], dtype=np.int32)

    for d in range(stop_day):
        next_day = d + 1
        n_next = 0
        days_remaining = n_days - next_day + 1

        for i in range(n_curr):
            state = curr_states[i]
            cost = curr_costs[i]

            if cost - suffix_bounds[next_day - 1] >= best_cost - 1e-9:
                continue

            omega, rho, nu, e, last_worked, s_last, first_flag, cw = unpack_state(state)
            has_worked = last_worked > 0

            can_off = True
            if omega > 0 and omega < min_wd:
                if days_remaining >= min_wd or first_flag == 1:
                    can_off = False

            if can_off and n_next < MAX_STATES:
                new_rho = rho + 1
                new_nu = 0
                new_cw_off = (cw << 1) & 0x3F
                recov = r_func(new_rho, chi, gamma_R, alpha_R)
                new_e = max(0.0, e - recov)
                p_new_off = 1.0 - new_e
                if enforce_performance_floor > 0.0 and p_new_off < enforce_performance_floor:
                    can_off = False
                if can_off:
                    next_states[n_next] = pack_state(-1 if omega > 0 else omega - 1, new_rho, new_nu, new_e, last_worked, 0, first_flag, new_cw_off)
                    next_costs[n_next] = cost
                    next_paths[n_next, :] = curr_paths[i, :]
                    next_paths[n_next, next_day] = -1
                    next_path_q[n_next, :] = curr_path_q[i, :]
                    next_path_q[n_next, next_day] = 0
                    n_next += 1

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

                c_new = 1 if (last_worked > 0 and last_worked != shift) else 0

                if ecp_k >= 0 and (popcount6(cw) + c_new) > ecp_k:
                    continue
                new_cw = ((cw << 1) | c_new) & 0x3F

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

                new_first = first_flag
                if not has_worked and next_day == 1:
                    new_first = 1

                # Physiological next-state is identical for every q on this
                # shift -- only the dual (hence cost) and recorded q differ.
                new_state = pack_state(1 if omega <= 0 else omega + 1, new_rho, new_nu, new_e, shift, shift, new_first, new_cw)
                qmask = eligible_q_mask[shift]

                for qbit in range(qmax):
                    if not ((qmask >> qbit) & 1):
                        continue
                    q = qbit + 1
                    dual_val = duals_q_flat[(next_day - 1) * n_shifts * qmax + (shift - 1) * qmax + qbit]
                    new_cost = cost - dual_val * p_new

                    if n_next < MAX_STATES:
                        next_states[n_next] = new_state
                        next_costs[n_next] = new_cost
                        next_paths[n_next, :] = curr_paths[i, :]
                        next_paths[n_next, next_day] = shift
                        next_path_q[n_next, :] = curr_path_q[i, :]
                        next_path_q[n_next, next_day] = q
                        n_next += 1

                    if next_day == n_days and new_cost < best_cost:
                        best_cost = new_cost

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
                            curr_path_q[n_pruned, :] = next_path_q[kdx, :]
                            n_pruned += 1
                i = j
            n_curr = n_pruned
        else:
            n_curr = 0
    return (curr_states[:n_curr].copy(), curr_costs[:n_curr].copy(),
            curr_paths[:n_curr].copy(), curr_path_q[:n_curr].copy(), n_curr)


class SubproblemQualificationsOverlapNumba(_NumbaECPMixin, SubproblemDPNumba):
    """Individual pricing subproblem for a worker with overlapping
    qualifications (Case B), one instance per worker."""

    def __init__(self, duals_i, duals_ts_q, shift_to_qualifications, df, i, iteration, eps,
                 Min_WD_i, Max_WD_i, chi, eligible_qualifications, model_type='nonlinear'):
        days = df['T'].dropna().astype(int).unique().tolist()
        shifts = df['K'].dropna().astype(int).unique().tolist()
        duals_ts_dummy = {(t, s): 0.0 for t in days for s in shifts}
        super().__init__(duals_i, duals_ts_dummy, df, i, iteration, eps, Min_WD_i, Max_WD_i,
                         chi, model_type)
        self.duals_ts_q = duals_ts_q
        self.shift_to_qualifications = shift_to_qualifications
        self.eligible_qualifications = set(eligible_qualifications)
        self.best_path_q = None
        self._prepare_qual_b()

    def _prepare_qual_b(self):
        n_days = len(self.days)
        n_shifts = len(self.shifts)
        all_q = sorted({q for qs in self.shift_to_qualifications.values() for q in qs})
        self.qmax = max(all_q) if all_q else 1

        eligible_q_mask = np.zeros(n_shifts + 1, dtype=np.int64)
        for shift in self.shifts:
            qs = self.shift_to_qualifications.get(shift, set()) & self.eligible_qualifications
            mask = 0
            for q in qs:
                mask |= (1 << (q - 1))
            eligible_q_mask[shift] = mask
        self.eligible_q_mask = eligible_q_mask

        duals_q_flat = np.zeros(n_days * n_shifts * self.qmax, dtype=np.float64)
        for d_idx, day in enumerate(self.days):
            for s_idx, shift in enumerate(self.shifts):
                for q in range(1, self.qmax + 1):
                    duals_q_flat[d_idx * n_shifts * self.qmax + s_idx * self.qmax + (q - 1)] = \
                        self.duals_ts_q.get((day, shift, q), 0.0)
        self.duals_q_flat = duals_q_flat

        suffix_bounds = np.zeros(n_days + 2, dtype=np.float64)
        for d_idx in range(n_days - 1, -1, -1):
            day = self.days[d_idx]
            max_dual = 0.0
            for shift in self.shifts:
                qs = self.shift_to_qualifications.get(shift, set()) & self.eligible_qualifications
                for q in qs:
                    v = self.duals_ts_q.get((day, shift, q), 0.0)
                    if v > max_dual:
                        max_dual = v
            suffix_bounds[d_idx] = suffix_bounds[d_idx + 1] + max_dual
        self.suffix_bounds_q = suffix_bounds

    def solveModelOpt(self, timeLimit):
        n_days = len(self.days)
        n_shifts = len(self.shifts)
        if not NUMBA_AVAILABLE:
            self.objval, self.status, self.n_optimal = float('inf'), gu.GRB.INFEASIBLE, 0
            return
        enc_nc = 1 if getattr(self, 'enforce_no_change', False) else 0
        enc_pf = getattr(self, 'enforce_performance_floor', None)
        enc_pf = float(enc_pf) if enc_pf is not None else 0.0
        gamma_C, gamma_R, alpha_R, delta_flat, e_max = self._prepare_jit_params()
        ecp_k = int(getattr(self, 'ecp_k', -1))

        states, costs, paths, path_q, n_states = forward_pass_qual_b(
            n_days, n_shifts, self.duals_q_flat, self.duals_i, self.chi,
            self.Min_WD, self.Max_WD, self.Days_Off, self.suffix_bounds_q, n_days,
            enc_nc, enc_pf, gamma_R, gamma_C, alpha_R, delta_flat, e_max, ecp_k,
            self.eligible_q_mask, self.qmax,
        )

        if n_states > 0:
            best_cost = np.min(costs[:n_states])
            self.objval = best_cost
            tol = 1e-9
            self.all_optimal_paths = []
            all_optimal_path_q = []
            for idx in range(n_states):
                if abs(costs[idx] - best_cost) < tol:
                    self.all_optimal_paths.append(paths[idx].copy())
                    all_optimal_path_q.append(path_q[idx].copy())
            self.n_optimal = len(self.all_optimal_paths)
            self.best_path = self.all_optimal_paths[0] if self.all_optimal_paths else None
            self.best_path_q = all_optimal_path_q[0] if all_optimal_path_q else None
            self.status = gu.GRB.OPTIMAL
        else:
            self.objval, self.status, self.n_optimal = float('inf'), gu.GRB.INFEASIBLE, 0

    def solveModelNOpt(self, timeLimit):
        self.solveModelOpt(timeLimit)

    def _all_vshifts(self):
        return sorted({10 * s + q for s, qs in self.shift_to_qualifications.items() for q in qs})

    def getNewSchedule(self):
        if self.best_path is None:
            return {}
        p_values = self.getOptP()
        schedule = {}
        all_vs = self._all_vshifts()
        for d_idx, day in enumerate(self.days):
            shift = int(self.best_path[d_idx + 1])
            q = int(self.best_path_q[d_idx + 1]) if self.best_path_q is not None else 0
            perf = p_values.get(day, 1.0) if shift > 0 else 0.0
            chosen_vs = (10 * shift + q) if (shift > 0 and q > 0) else None
            for vs in all_vs:
                schedule[(day, vs, self.itr)] = perf if vs == chosen_vs else 0.0
        return schedule

    def getOptX(self):
        if self.best_path is None:
            return {}
        x = {}
        all_vs = self._all_vshifts()
        for d_idx, day in enumerate(self.days):
            shift = int(self.best_path[d_idx + 1])
            q = int(self.best_path_q[d_idx + 1]) if self.best_path_q is not None else 0
            chosen_vs = (10 * shift + q) if (shift > 0 and q > 0) else None
            for vs in all_vs:
                x[(day, vs)] = 1.0 if vs == chosen_vs else 0.0
        return x

    def getRealShiftSeq(self):
        if self.best_path is None:
            return {}
        seq = {}
        for d_idx, day in enumerate(self.days):
            shift = int(self.best_path[d_idx + 1])
            seq[day] = shift if shift > 0 else 0
        return seq
