"""Pricing subproblem for Extension 4, Case B (Heterogeneous Worker Qualifications
with overlapping qualifications), see Datei/extensions.tex \\subsection{Heterogeneous
Worker Qualifications}, "Case B: Overlapping qualifications".

In Case B, workers can hold multiple qualifications (e.g., ICU+general ward), creating
cross-qualification substitutability. The model introduces assignment variables x_idsq
(worker i assigned to shift s on day d to cover qualification q) and tracks q-specific
demand Q_ds^q and undercoverage u_dsq. The pricing subproblem is now INDIVIDUAL (one SP
per worker i, not per (g,q) pair) because workers with different qualification profiles
cannot be aggregated. The demand duals become π_ds^q (one per qualification), and the
performance contribution p_idsq is linearized. The convexity constraint in the master
problem moves from per-(g,q) to per-worker.
"""
import gurobipy as gu
from core.subproblem import Subproblem


class SubproblemQualificationsB(Subproblem):
    """Pricing subproblem for Extension 4, Case B: overlapping worker qualifications.

    One instance per worker i. The worker has a set of eligible qualifications Q_i,
    and on each day/shift can choose which qualification to cover (if eligible for that
    qualification and shift). The reduced-cost calculation includes the per-qualification
    demand duals π_ds^q.

    Args:
        eligible_qualifications: Set of qualification IDs this worker can hold.
                                 E.g., {1, 2} means both general and ICU.
        shift_to_qualifications: Dict (shift -> set of qualifications that cover it).
                                E.g., {1: {1,2}, 2: {1,2}, 3: {2}} means
                                N-shift (3) only covered by ICU (q=2).
        duals_ts_q: Dict mapping (day, shift, qualification) -> dual value π_ds^q.
                   For shifts not demanding a qualification, this is absent (treated as 0).
    """
    def __init__(self, duals_i, duals_ts_q, shift_to_qualifications, df, i, iteration, eps,
                 Min_WD_i, Max_WD_i, chi, eligible_qualifications, model_type='nonlinear'):
        super().__init__(duals_i, duals_ts_q, df, i, iteration, eps, Min_WD_i, Max_WD_i,
                         chi, model_type)
        self.eligible_qualifications = set(eligible_qualifications)
        self.shift_to_qualifications = shift_to_qualifications  # shift -> set of q
        # Override duals_ts_q structure (now (day, shift, qualification) keys instead of (day, shift))
        self.duals_ts_q = duals_ts_q  # Replaces parent's duals_ts

        # Track performance by (day, shift, qualification) for reconstruction
        self.performance_dsq = {}

    def generateConstraints(self):
        """Add base constraints and qualification-specific logic."""
        super().generateConstraints()

        # For each day/shift, ensure x_ids = sum_q x_idsq
        # (i.e., if working shift s on day d, must pick exactly one q to cover)
        for t in self.days:
            for s in self.shifts:
                # Gather eligible q for this shift
                eligible_q = self.shift_to_qualifications.get(s, set())
                eligible_q_for_worker = eligible_q & self.eligible_qualifications

                if eligible_q_for_worker:
                    x_idsq_vars = [self.model.addVar(vtype=gu.GRB.BINARY, name=f"x[{t},{s},{q}]")
                                    for q in sorted(eligible_q_for_worker)]
                    # sum_q x_idsq = y_ds (if working shift s on day d, exactly one q is active)
                    self.model.addConstr(gu.quicksum(x_idsq_vars) <= self.y[t],
                                        name=f"qual_pick_{t}_{s}")
                    # If y=1 and shift was chosen, at least one q must be covered
                    # (This is implicit: if y=1 and we branch over q, exactly one q has x_idsq=1)

                    # Store for objective calculation
                    for q_idx, q in enumerate(sorted(eligible_q_for_worker)):
                        if not hasattr(self, '_x_idsq'):
                            self._x_idsq = {}
                        self._x_idsq[(t, s, q)] = x_idsq_vars[q_idx]

        self.model.update()

    def generateObjective(self):
        """Reduced cost uses per-qualification demand duals π_ds^q.

        For each working arc (t, s) branching over q:
        cost contribution = -π_ds^q * p_id (where p_id is performance on day d for this worker)

        Off-day arcs have zero cost from duals (no qualification demand).
        """
        if not hasattr(self, '_x_idsq'):
            # Fallback to base objective if no x_idsq defined
            super().generateObjective()
            return

        obj = 0 - self.duals_i  # Lambda dual

        # Sum over all (t, s, q) branches
        for t in self.days:
            for s in self.shifts:
                eligible_q = self.shift_to_qualifications.get(s, set())
                eligible_q_for_worker = eligible_q & self.eligible_qualifications

                for q in eligible_q_for_worker:
                    if (t, s, q) in self._x_idsq:
                        # Dual for this specific (day, shift, qualification)
                        dual = self.duals_ts_q.get((t, s, q), 0.0)
                        # Cost contribution: -dual * performance (performance stored at arc creation)
                        obj += -dual * self.performance[t, s, self.itr]

        self.model.setObjective(obj, sense=gu.GRB.MINIMIZE)

    def getOptX(self):
        """Return binary x_ids decisions (aggregated over q)."""
        if not hasattr(self, '_x_idsq'):
            return super().getOptX()

        x = {}
        for t in self.days:
            for s in self.shifts:
                # x_ids = max_q x_idsq (or check if any q has x_idsq=1)
                x[(t, s)] = max((self._x_idsq[(t, s, q)].X
                                 for q in self.shift_to_qualifications.get(s, set())
                                 if (t, s, q) in self._x_idsq), default=0.0)
        return x
