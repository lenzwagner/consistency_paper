"""Pricing subproblem for Extension 1 (Fairness in Shift-Type Allocation), see
Datei/extensions.tex \\subsection{Fairness in Shift-Type Allocation}.

Copy of core/subproblem.py, extended with the burden resource F_i = sum mu_s x_ids
and the linearized fairness penalty lambda*|F_i - Fbar| in the pricing objective
(ext:obj:fair). Fbar is fixed as a parameter before each CG iteration (computed
from the current incumbent), consistent with the paper's labeling description.
"""
import gurobipy as gu
from core.subproblem import Subproblem


class SubproblemFairness(Subproblem):
    def __init__(self, duals_i, duals_ts, df, i, iteration, eps, Min_WD_i, Max_WD_i, chi,
                 mu, lam, F_bar, model_type='nonlinear'):
        super().__init__(duals_i, duals_ts, df, i, iteration, eps, Min_WD_i, Max_WD_i, chi, model_type)
        self.mu_shift = mu          # dict: shift -> burden weight mu_s
        self.lam = lam              # fairness weight lambda
        self.F_bar = F_bar          # fixed mean burden target for this CG iteration

    def generateVariables(self):
        super().generateVariables()
        self.a_plus = self.model.addVar(vtype=gu.GRB.CONTINUOUS, lb=0, name="a_plus")
        self.a_minus = self.model.addVar(vtype=gu.GRB.CONTINUOUS, lb=0, name="a_minus")

    def generateConstraints(self):
        super().generateConstraints()
        # F_i = sum_{t,s} mu_s * x[t,s];  F_i - Fbar = a_plus - a_minus
        F_i = gu.quicksum(self.mu_shift[s] * self.x[t, s] for t in self.days for s in self.shifts)
        self.model.addConstr(F_i - self.F_bar == self.a_plus - self.a_minus, name="burden_dev")
        self.model.update()

    def generateObjective(self):
        # Base reduced cost, plus the fairness penalty lambda*(a_plus + a_minus) = lambda*|F_i - Fbar|.
        self.model.setObjective(
            0 - gu.quicksum(self.performance[t, s, self.itr] * self.duals_ts[t, s]
                             for t in self.days for s in self.shifts)
            - self.duals_i
            + self.lam * (self.a_plus + self.a_minus),
            sense=gu.GRB.MINIMIZE
        )

    def getBurden(self):
        x_vals = self.model.getAttr("X", self.x)
        return sum(self.mu_shift[s] * x_vals[t, s] for t in self.days for s in self.shifts)
