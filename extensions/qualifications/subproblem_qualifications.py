"""Pricing subproblem for Extension 4, Case A (Heterogeneous Worker
Qualifications, clean partition), see Datei/extensions.tex
\\subsection{Heterogeneous Worker Qualifications}.

Copy of core/subproblem.py restricted to a worker's eligible shift set S_q:
shift arcs for s not in S_q are removed from the state-space graph. One SP
is solved per (g,q) pair. No master-problem modification is required: since
ineligible shifts are structurally infeasible (x_ids=0), their column
coefficient is 0 in the (unmodified) demand constraints, so core.masterproblem
already supports qualification-restricted columns without change.
"""
import gurobipy as gu
from core.subproblem import Subproblem


class SubproblemQualifications(Subproblem):
    def __init__(self, duals_i, duals_ts, df, i, iteration, eps, Min_WD_i, Max_WD_i, chi,
                 eligible_shifts, model_type='nonlinear'):
        self.eligible_shifts = set(eligible_shifts)
        super().__init__(duals_i, duals_ts, df, i, iteration, eps, Min_WD_i, Max_WD_i, chi, model_type)

    def generateConstraints(self):
        super().generateConstraints()
        # Restrict arcs to S_q: shifts outside the qualification profile are infeasible.
        for t in self.days:
            for s in self.shifts:
                if s not in self.eligible_shifts:
                    self.model.addConstr(self.x[t, s] == 0, name=f"qual_ineligible_{t}_{s}")
        self.model.update()
