"""Labeling-algorithm (SPPRC) implementations of the four paper extensions,
see Datei/extensions.tex. Each class subclasses the pure-Python label-setting
solver core.subproblem_dp.SubproblemDP (not the Numba bit-packed variant),
extending exactly the label components / recursions / arc sets described in
each extension's "Labeling Implementation" paragraph.
"""
from dataclasses import dataclass, field
from typing import Optional, List
import gurobipy as gu
from .subproblem_dp import SubproblemDP, Label
from .nonlinear_transitions import r_func, h_func


def _cumulative_recovery(rho, chi, gamma_R, alpha_R):
    """CR(rho) = alpha_R * max(0, rho-chi+1)^gamma_R, the telescoping antiderivative
    of r_func: CR(rho)-CR(rho-1) == r_func(rho,...) for a single-day step. Used to
    correctly compute the TOTAL recovery earned when rho advances by more than one
    unit in a single transition (beta_g-multiplier off-days, ext:spell:off)."""
    if rho < chi - 1:
        return 0.0
    return alpha_R * (rho - chi + 1) ** gamma_R


# =============================================================================
# Extension 4 (Case A): Heterogeneous Worker Qualifications (clean partition)
# extensions.tex app:ext:qual, "Case A... The only modification is the set of
# feasible arcs: for the (g,q)-SP, shift arcs for s not in S_q are removed
# from the state-space graph entirely."
# =============================================================================
class SubproblemQualificationsDP(SubproblemDP):
    def __init__(self, duals_i, duals_ts, df, i, iteration, eps, Min_WD_i, Max_WD_i, chi,
                 eligible_shifts, model_type='nonlinear'):
        super().__init__(duals_i, duals_ts, df, i, iteration, eps, Min_WD_i, Max_WD_i, chi, model_type)
        self.eligible_shifts = set(eligible_shifts)

    def _is_shift_feasible(self, label, next_day, shift):
        if shift not in self.eligible_shifts:
            return False
        return super()._is_shift_feasible(label, next_day, shift)


# =============================================================================
# Extension 4 (Case B): Heterogeneous Worker Qualifications (overlapping)
# extensions.tex app:ext:qual, "Case B... On each working arc (t,s), the
# pricing problem branches over the qualification category q^arc in Q_s
# covered by shift s. The RC contribution of that arc differentiates by q^arc
# through the corresponding demand dual π^q_ds."
#
# Which qualification covers a given shift does not change the physiological
# state (e, rho, nu) or future eligibility (a worker's eligible_qualifications
# set is fixed), so base dominance grouping remains exact -- the extra
# q_history component only matters for reconstructing the qualification-
# specific column (needed by a master problem with per-(day,shift,qual)
# demand rows Q_ds^q), not for pruning.
# =============================================================================
@dataclass
class QualBLabel(Label):
    q_history: List[Optional[int]] = field(default_factory=list)  # chosen qualification per day (None = off)

    def copy(self):
        return QualBLabel(
            day=self.day, s_last=self.s_last, last_worked_shift=self.last_worked_shift,
            e=self.e, rho=self.rho, omega=self.omega, cost=self.cost,
            path=self.path.copy(), total_workdays=self.total_workdays,
            sc_history=self.sc_history.copy(), r_history=self.r_history.copy(),
            p_history=self.p_history.copy(), nu=self.nu,
            q_history=self.q_history.copy(),
        )


class SubproblemQualificationsOverlapDP(SubproblemDP):
    """Individual pricing subproblem for a worker with overlapping qualifications
    (Case B). One instance per worker (see extensions.tex: "this yields |I|
    pricing calls per iteration").

    Args:
        duals_i: Lambda (convexity) constraint dual for this worker.
        duals_ts_q: Dict (day, shift, qualification) -> dual value π_ds^q for
            the qualification-specific demand row.
        shift_to_qualifications: Dict shift -> set of qualifications Q_s that
            jointly demand coverage on that shift (overlap happens whenever
            |Q_s| > 1).
        eligible_qualifications: Set of qualifications this worker holds.
    """

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

    def _solve(self, timeLimit, optimal=True):
        """Same forward pass as the base labeling, only the initial label is a
        QualBLabel (adds q_history) and transitions branch over qualifications."""
        import time
        start_time = time.time()

        labels_by_day = {d: [] for d in self.days}
        initial_label = QualBLabel(
            day=0, s_last=None, last_worked_shift=None, e=0.0, rho=0, omega=0,
            cost=-self.duals_i, path=[], total_workdays=0, sc_history=[], r_history=[],
            p_history=[], nu=0, q_history=[],
        )
        labels_by_day[0] = [initial_label]

        days_to_process = [0] + self.days[:-1]
        for d in days_to_process:
            current_labels = labels_by_day[d]
            if not current_labels:
                continue
            for label in current_labels:
                next_day = d + 1
                new_labels = self._generate_transitions(label, next_day)
                if next_day not in labels_by_day:
                    labels_by_day[next_day] = []
                labels_by_day[next_day].extend(new_labels)

            next_day = d + 1
            is_final = (next_day == self.days[-1])
            labels_by_day[next_day] = self._prune_dominated(labels_by_day[next_day], is_final_day=is_final)

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

    def _generate_transitions(self, label: 'QualBLabel', next_day: int):
        """Branch over qualifications for each feasible shift: one label per
        (shift, q) pair where q ranges over Q_s (the shift's demand set)
        intersected with the worker's own eligible qualifications."""
        new_labels = []

        if self._is_day_off_feasible(label, next_day):
            off_label = self._create_day_off_label(label, next_day)
            if off_label:
                new_labels.append(off_label)

        for shift in self.shifts:
            if self._is_shift_feasible(label, next_day, shift):
                eligible_q = self.shift_to_qualifications.get(shift, set()) & self.eligible_qualifications
                for q in eligible_q:
                    new_label = self._create_shift_label_q(label, next_day, shift, q)
                    if new_label:
                        new_labels.append(new_label)

        return new_labels

    def _create_day_off_label(self, label: 'QualBLabel', next_day: int) -> Optional['QualBLabel']:
        new_label = super()._create_day_off_label(label, next_day)
        if new_label is not None:
            new_label.q_history.append(None)
        return new_label

    def _create_shift_label_q(self, label: 'QualBLabel', next_day: int, shift: int, q: int) -> Optional['QualBLabel']:
        """Create a label for working shift s to cover qualification q. Cost
        uses the qualification-specific dual π_ds^q instead of a generic π_ds."""
        new_label = label.copy()
        new_label.day = next_day
        new_label.total_workdays = label.total_workdays + 1

        c_new = 0
        if label.last_worked_shift is not None and label.last_worked_shift != shift:
            c_new = 1

        if getattr(self, 'enforce_no_change', False) and c_new > 0:
            return None

        if self._violates_ecp(label, c_new):
            return None

        new_label.s_last = shift
        new_label.last_worked_shift = shift

        if label.omega < 0:
            new_label.omega = 1
        else:
            new_label.omega = label.omega + 1

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

        # Cost contribution uses the qualification-specific dual pi_ds^q.
        dual_value = self.duals_ts_q.get((next_day, shift, q), 0.0)
        cost_contribution = -dual_value * p_new

        new_label.cost = label.cost + cost_contribution

        new_label.path.append((next_day, shift))
        new_label.sc_history.append(c_new)
        new_label.r_history.append(int(r_new))
        new_label.p_history.append(p_new)
        new_label.q_history.append(q)

        return new_label

    def _all_vshifts(self):
        """Virtual shift ids v = 10*s + q covering every (shift, qualification)
        pair actually demanded, used to key columns for the qualification-
        indexed master problem."""
        return sorted({10 * s + q for s, qs in self.shift_to_qualifications.items() for q in qs})

    def getNewSchedule(self):
        """Performance schedule keyed by (day, vshift, itr), vshift=10*shift+q,
        so the master's per-(day,shift,qualification) demand rows receive the
        correct coefficient."""
        if self.best_label is None:
            return {}
        schedule = {}
        all_vs = self._all_vshifts()
        for day in self.days:
            idx = day - 1
            shift = q = None
            perf = 0.0
            if idx < len(self.best_label.path):
                _, shift = self.best_label.path[idx]
                q = self.best_label.q_history[idx] if idx < len(self.best_label.q_history) else None
                perf = self.best_label.p_history[idx] if idx < len(self.best_label.p_history) else 0.0
            chosen_vs = (10 * shift + q) if (shift is not None and q is not None) else None
            for vs in all_vs:
                schedule[(day, vs, self.itr)] = perf if vs == chosen_vs else 0.0
        return schedule

    def getOptX(self):
        """Binary decisions keyed by (day, vshift): 1 if this worker covers
        qualification q on shift s=vshift//10 on that day."""
        if self.best_label is None:
            return {}
        x = {}
        all_vs = self._all_vshifts()
        for day in self.days:
            idx = day - 1
            shift = q = None
            if idx < len(self.best_label.path):
                _, shift = self.best_label.path[idx]
                q = self.best_label.q_history[idx] if idx < len(self.best_label.q_history) else None
            chosen_vs = (10 * shift + q) if (shift is not None and q is not None) else None
            for vs in all_vs:
                x[(day, vs)] = 1.0 if vs == chosen_vs else 0.0
        return x

    def getRealShiftSeq(self):
        """Real shift (not vshift) per day -- used for the shift-change
        consistency metric, which depends only on the physical shift, not on
        which qualification happened to be covered."""
        if self.best_label is None:
            return {}
        seq = {}
        for day in self.days:
            idx = day - 1
            shift = 0
            if idx < len(self.best_label.path):
                _, s = self.best_label.path[idx]
                shift = s if s is not None else 0
            seq[day] = shift
        return seq


# =============================================================================
# Extension 2: Off-Day Recovery (beta_g multiplier)
# extensions.tex app:ext:offday, ext:spell:off: the off-day arc increments the
# stable-day counter by beta_g instead of 1: rho^+ = rho_h + round(beta_g).
# "All working-day arcs, the label structure, the RC calculation, and the
# dominance relation remain identical to the base labeling."
# =============================================================================
class SubproblemOffdayDP(SubproblemDP):
    def __init__(self, duals_i, duals_ts, df, i, iteration, eps, Min_WD_i, Max_WD_i, chi,
                 beta_g=1, model_type='nonlinear'):
        super().__init__(duals_i, duals_ts, df, i, iteration, eps, Min_WD_i, Max_WD_i, chi, model_type)
        self.beta_g = beta_g

    def _create_day_off_label(self, label: Label, next_day: int) -> Optional[Label]:
        new_label = label.copy()
        new_label.day = next_day
        new_label.s_last = None

        if label.omega > 0:
            new_label.omega = -1
        else:
            new_label.omega = label.omega - 1

        c_new = 0
        new_label.nu = 0
        # ext:spell:off / model:phi: rho is simply REPLACED by the rescaled
        # counter rho_tilde ("The variable rho_id is then replaced by
        # rho_tilde_id in model:phi") -- a plain substitution into the
        # existing single-evaluation recovery formula, not a cumulative/
        # telescoping sum over the skipped intermediate rho values. An
        # off-day arc advances the counter by beta_g (rounded to the nearest
        # integer, since only integer beta_g is used here).
        new_label.rho = label.rho + round(self.beta_g)
        recov = r_func(new_label.rho, self.chi, self.gamma_R, self.alpha_R)
        new_label.e = max(0.0, label.e - recov)
        p_new = 1.0 - new_label.e
        r_new = 1.0 if (new_label.rho >= self.chi) else 0.0

        pf = getattr(self, 'enforce_performance_floor', None)
        if pf is not None and p_new < pf:
            return None

        new_label.cost = label.cost
        new_label.path.append((next_day, None))
        new_label.sc_history.append(c_new)
        new_label.r_history.append(int(r_new))
        new_label.p_history.append(p_new)
        return new_label


# =============================================================================
# Extension 3: Worker Day-Off Preferences
# extensions.tex app:ext:pref: "every working arc on a preferred day d in P_i
# incurs an additional cost +lambda^P in the reduced-cost accumulation, while
# off-day arcs and arcs on non-preferred days are unaffected... only the
# arc-cost lookup changes."
# =============================================================================
class SubproblemPreferencesDP(SubproblemDP):
    def __init__(self, duals_i, duals_ts, df, i, iteration, eps, Min_WD_i, Max_WD_i, chi,
                 pref_days, lam_pref, model_type='nonlinear'):
        super().__init__(duals_i, duals_ts, df, i, iteration, eps, Min_WD_i, Max_WD_i, chi, model_type)
        self.pref_days = set(pref_days)
        self.lam_pref = lam_pref

    def _create_shift_label(self, label: Label, next_day: int, shift: int) -> Optional[Label]:
        new_label = super()._create_shift_label(label, next_day, shift)
        if new_label is not None and next_day in self.pref_days:
            new_label.cost += self.lam_pref
        return new_label


# =============================================================================
# Extension 1: Fairness in Shift-Type Allocation
# extensions.tex app:ext:fairness: the label is extended by one resource f
# (accumulated burden along the partial path); on a shift-s arc f' = f + mu_s,
# on an off-day arc f' = f. The terminal RC adds lambda*|f - Fbar|.
#
# The paper's V-shaped below-/above-target dominance split is a compression
# optimization; we instead keep f as an exact dominance-relevant state
# component (require matching f before pruning), which is still exact -- just
# without the paper's state-space compression -- appropriate at this
# instance scale (a handful of workers, 2-4 week horizons).
# =============================================================================
@dataclass
class FairLabel(Label):
    f: float = 0.0
    lam: float = 0.0  # fairness weight; when 0, f-based dominance is inactive

    # Discretization bin width for the burden resource f, used only for the
    # dominance check (extensions.tex: "If f is discretized into B bins, the
    # state space grows by a factor of B relative to the base labeling").
    # Exact (unbinned) f is kept for the terminal penalty calculation. Without
    # binning, f is near-unique per path (few paths share cumulative mu_s sums),
    # so dominance collapses almost nothing and the state space blows up
    # exponentially over 2+ week horizons; binning restores tractable pruning
    # at the cost of a small, controlled discretization error in the
    # fairness-penalty terminal cost used purely for pricing (RC) decisions.
    # NOTE: when lam=0 (no fairness penalty), f is irrelevant and should not
    # affect dominance, saving state-space explosion from f-discretization noise.
    F_BIN = 1.0

    def copy(self):
        return FairLabel(
            day=self.day, s_last=self.s_last, last_worked_shift=self.last_worked_shift,
            e=self.e, rho=self.rho, omega=self.omega, cost=self.cost,
            path=self.path.copy(), total_workdays=self.total_workdays,
            sc_history=self.sc_history.copy(), r_history=self.r_history.copy(),
            p_history=self.p_history.copy(), nu=self.nu, f=self.f, lam=self.lam,
        )

    def _f_bin(self):
        return round(self.f / self.F_BIN)

    def dominates(self, other, is_final_day: bool = False, min_wd: int = 1) -> bool:
        if self is other:
            return True
        if is_final_day:
            # Terminal cost (incl. fairness penalty) is applied after the forward
            # pass in SubproblemFairnessDP._solve, so raw `cost` here is still
            # pre-penalty and comparable only among labels with equal f-bin.
            # BUT: only group by f-bin if lam > 0 (fairness is active); if lam=0,
            # f is irrelevant and should not prevent dominance.
            if self.lam > 1e-9 and self._f_bin() != other._f_bin():
                return False
            return self.cost < other.cost - 1e-9
        if self.day != other.day or self.s_last != other.s_last:
            return False
        if self.last_worked_shift != other.last_worked_shift:
            return False
        if round(self.e, 3) != round(other.e, 3):
            return False
        if self.rho != other.rho or self.omega != other.omega or self.nu != other.nu:
            return False
        # Only f-bin grouping when fairness is active (lam > 0); when lam=0,
        # f-tracking is wasted overhead and should not inflate state space.
        if self.lam > 1e-9 and self._f_bin() != other._f_bin():
            return False
        return self.cost < other.cost - 1e-9


class SubproblemFairnessDP(SubproblemDP):
    def __init__(self, duals_i, duals_ts, df, i, iteration, eps, Min_WD_i, Max_WD_i, chi,
                 mu_shift, lam, F_bar, model_type='nonlinear'):
        super().__init__(duals_i, duals_ts, df, i, iteration, eps, Min_WD_i, Max_WD_i, chi, model_type)
        self.mu_shift = mu_shift
        self.lam = lam
        self.F_bar = F_bar

    def _initial_label(self):
        return FairLabel(
            day=0, s_last=None, last_worked_shift=None, e=0.0, rho=0, omega=0,
            cost=-self.duals_i, path=[], total_workdays=0, sc_history=[], r_history=[],
            p_history=[], nu=0, f=0.0, lam=self.lam,
        )

    def _create_day_off_label(self, label: 'FairLabel', next_day: int):
        new_label = super()._create_day_off_label(label, next_day)
        if new_label is not None:
            new_label.f = label.f  # off-day arc: f' = f
        return new_label

    def _create_shift_label(self, label: 'FairLabel', next_day: int, shift: int):
        new_label = super()._create_shift_label(label, next_day, shift)
        if new_label is not None:
            new_label.f = label.f + self.mu_shift[shift]  # shift-s arc: f' = f + mu_s
        return new_label

    def _solve(self, timeLimit, optimal=True):
        import time
        start_time = time.time()

        labels_by_day = {d: [] for d in self.days}
        labels_by_day[0] = [self._initial_label()]

        days_to_process = [0] + self.days[:-1]
        for d in days_to_process:
            current_labels = labels_by_day[d]
            if not current_labels:
                continue
            for label in current_labels:
                next_day = d + 1
                new_labels = self._generate_transitions(label, next_day)
                if next_day not in labels_by_day:
                    labels_by_day[next_day] = []
                labels_by_day[next_day].extend(new_labels)

            next_day = d + 1
            is_final = (next_day == self.days[-1])
            labels_by_day[next_day] = self._prune_dominated(labels_by_day[next_day], is_final_day=is_final)

            if time.time() - start_time > timeLimit:
                self.status = gu.GRB.TIME_LIMIT
                self.objval = float('inf')
                return

        final_labels = labels_by_day[self.days[-1]]
        if not final_labels:
            self.status = gu.GRB.INFEASIBLE
            self.objval = float('inf')
            return

        # Apply the terminal fairness penalty lambda*|f - Fbar| only now, at
        # final selection -- during the forward pass, dominance required exact
        # f-matches, so pruning up to this point never discarded a label that
        # could later become optimal once the terminal term is added.
        def effective_cost(l):
            return l.cost + self.lam * abs(l.f - self.F_bar)

        self.best_label = min(final_labels, key=effective_cost)
        self.status = gu.GRB.OPTIMAL
        self.objval = effective_cost(self.best_label)

    def getBurden(self):
        return self.best_label.f if self.best_label is not None else 0.0

    def _prune_dominated(self, labels, is_final_day: bool = False):
        """Fine-grained grouping key (incl. f-bin) so within-group comparisons
        stay O(k) for small k, instead of the base O(n^2) scan over all labels
        sharing only (day, s_last) -- necessary once f is part of the state,
        since otherwise groups get far larger and pruning becomes the
        bottleneck."""
        if not labels:
            return []
        groups = {}
        for label in labels:
            if is_final_day:
                key = label._f_bin()
            else:
                key = (label.day, label.s_last, label.last_worked_shift,
                       round(label.e, 3), label.rho, label.omega, label.nu, label._f_bin())
            groups.setdefault(key, []).append(label)

        non_dominated = []
        for group_labels in groups.values():
            if len(group_labels) == 1:
                non_dominated.append(group_labels[0])
                continue
            best = min(group_labels, key=lambda l: l.cost)
            non_dominated.append(best)
        return non_dominated
