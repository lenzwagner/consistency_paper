"""Pricing subproblem for Extension 3 (Worker Day-Off Preferences), see
Datei/extensions.tex \\subsection{Worker Day-Off Preferences}.

Copy of core/subproblem.py with a per-worker preference-day cost surcharge
added to the pricing objective (ext:obj:pref): every working arc on a
preferred day d in P_i incurs an additional lambda_P penalty. Since
preferences are worker-specific, pricing is individual (one SP per worker),
matching the paper's "Labeling Implementation" paragraph.
"""
import gurobipy as gu
from core.subproblem import Subproblem


class SubproblemPreferences(Subproblem):
    def __init__(self, duals_i, duals_ts, df, i, iteration, eps, Min_WD_i, Max_WD_i, chi,
                 pref_days, lam_pref, model_type='nonlinear'):
        super().__init__(duals_i, duals_ts, df, i, iteration, eps, Min_WD_i, Max_WD_i, chi, model_type)
        self.pref_days = set(pref_days)  # P_i: preferred off-days for this worker
        self.lam_pref = lam_pref

    def generateObjective(self):
        pref_penalty = self.lam_pref * gu.quicksum(self.y[d] for d in self.days if d in self.pref_days)
        self.model.setObjective(
            0 - gu.quicksum(self.performance[t, s, self.itr] * self.duals_ts[t, s]
                             for t in self.days for s in self.shifts)
            - self.duals_i
            + pref_penalty,
            sense=gu.GRB.MINIMIZE
        )
