"""Pricing subproblem for Extension 2 (Performance Recovery on Off-Days), see
Datei/extensions.tex \\subsection{Performance Recovery on Off-Days}.

Copy of core/subproblem.py's nonlinear performance block, modified so that the
stable-spell counter rho advances by beta_g (instead of 1) on off-days:
    tilde_rho_id = (1-c_id) * (tilde_rho_i(d-1) + y_id + beta_g*(1-y_id))   [ext:spell:off]
For beta_g = 1 this collapses to the base model (model:spell_recovery1).
"""
import gurobipy as gu
from core.subproblem import Subproblem


class SubproblemOffday(Subproblem):
    def __init__(self, duals_i, duals_ts, df, i, iteration, eps, Min_WD_i, Max_WD_i, chi,
                 beta_g=1, model_type='nonlinear'):
        self.beta_g = beta_g
        super().__init__(duals_i, duals_ts, df, i, iteration, eps, Min_WD_i, Max_WD_i, chi, model_type)

    def nlPerformance(self):
        max_d = len(self.days)
        beta = self.beta_g
        rho_ub = max_d * beta  # domain expands: off-days can advance rho by beta per day

        gamma_C = getattr(self, 'gamma_C', 1.25)
        gamma_R = getattr(self, 'gamma_R', 0.5)
        alpha_R = getattr(self, 'alpha_R', 0.04)
        e_max = getattr(self, 'e_max', 1.0)
        delta = getattr(self, 'delta', None)
        if delta is None:
            from core.worker_groups import get_default_delta
            delta = get_default_delta(self.epsilon)

        h_hat = {n: (n**gamma_C - (n - 1)**gamma_C) for n in range(1, max_d + 1)}
        h_hat[0] = 0.0

        r_hat = {}
        for k in range(0, rho_ub + 1):
            if k < self.chi:
                r_hat[k] = 0.0
            else:
                r_hat[k] = alpha_R * ((k - self.chi + 1)**gamma_R - (k - self.chi)**gamma_R)

        M_nu = max_d + 1
        M_rho = rho_ub + 1
        max_delta = max([max(row) for row in delta])
        max_h = max(h_hat.values()) if max_d > 0 else 0
        max_r = max(r_hat.values()) if rho_ub > 0 else 0
        M_phi = 1.0 + max(max_delta * max_h, max_r)

        w_nl = self.model.addVars(self.days, self.shifts, self.shifts, vtype=gu.GRB.BINARY, name="w_nl")
        nu_nl = self.model.addVars(self.days, vtype=gu.GRB.INTEGER, lb=0, ub=max_d, name="nu_nl")
        a_nl = self.model.addVars(self.days, self.shifts, self.shifts, range(1, max_d + 1), vtype=gu.GRB.BINARY, name="a_nl")
        delta_nl = self.model.addVars(self.days, vtype=gu.GRB.CONTINUOUS, lb=0, name="delta_nl")
        rho_nl = self.model.addVars(self.days, vtype=gu.GRB.INTEGER, lb=0, ub=rho_ub, name="rho_nl")
        q_nl = self.model.addVars(self.days, range(0, rho_ub + 1), vtype=gu.GRB.BINARY, name="q_nl")
        g_nl = self.model.addVars(self.days, vtype=gu.GRB.CONTINUOUS, lb=0, name="g_nl")
        vartheta = self.model.addVars(self.days, vtype=gu.GRB.CONTINUOUS, lb=-gu.GRB.INFINITY, name="vartheta")
        phi_nl = self.model.addVars(self.days, vtype=gu.GRB.CONTINUOUS, lb=0, ub=1, name="phi_nl")
        b_minus = self.model.addVars(self.days, vtype=gu.GRB.BINARY, name="b_minus")
        b_zero = self.model.addVars(self.days, vtype=gu.GRB.BINARY, name="b_zero")
        b_plus = self.model.addVars(self.days, vtype=gu.GRB.BINARY, name="b_plus")
        self.model.update()

        # Effective daily increment when no shift change occurs: y_t + beta*(1-y_t).
        def stable_increment(t):
            return beta - (beta - 1) * self.y[t]

        self.model.addConstr(nu_nl[1] == self.sc[1])
        self.model.addConstr(rho_nl[1] == stable_increment(1) * (1 - self.sc[1]))
        self.model.addConstr(phi_nl[1] == 0)

        for t in self.days:
            for s in self.shifts:
                for s_prime in self.shifts:
                    if s != s_prime:
                        self.model.addConstr(w_nl[t, s, s_prime] <= self.q[t, s])
                        self.model.addConstr(w_nl[t, s, s_prime] <= self.x[t, s_prime])
                        self.model.addConstr(w_nl[t, s, s_prime] <= 1 - self.gam[t])
                        self.model.addConstr(w_nl[t, s, s_prime] >= self.q[t, s] + self.x[t, s_prime] - self.gam[t] - 1)
                    else:
                        self.model.addConstr(w_nl[t, s, s_prime] == 0)

            self.model.addConstr(self.sc[t] == gu.quicksum(w_nl[t, s, s_prime] for s in self.shifts for s_prime in self.shifts))

            self.model.addConstr(nu_nl[t] <= max_d * self.sc[t])
            if t > 1:
                self.model.addConstr(nu_nl[t] <= nu_nl[t - 1] + 1 + M_nu * (1 - self.sc[t]))
                self.model.addConstr(nu_nl[t] >= nu_nl[t - 1] + 1 - M_nu * (1 - self.sc[t]))

            for s in self.shifts:
                for s_prime in self.shifts:
                    if s != s_prime:
                        self.model.addConstr(gu.quicksum(a_nl[t, s, s_prime, n] for n in range(1, max_d + 1)) == w_nl[t, s, s_prime])
            self.model.addConstr(nu_nl[t] == gu.quicksum(
                n * a_nl[t, s, s_prime, n] for s in self.shifts for s_prime in self.shifts
                for n in range(1, max_d + 1) if s != s_prime))
            self.model.addConstr(delta_nl[t] == gu.quicksum(
                delta[s, s_prime] * h_hat[n] * a_nl[t, s, s_prime, n]
                for s in self.shifts for s_prime in self.shifts for n in range(1, max_d + 1) if s != s_prime))

            # Stable-spell counter with the beta_g off-day multiplier (ext:spell:off).
            if t > 1:
                self.model.addConstr(rho_nl[t] <= rho_nl[t - 1] + stable_increment(t) + M_rho * self.sc[t])
                self.model.addConstr(rho_nl[t] >= rho_nl[t - 1] + stable_increment(t) - M_rho * self.sc[t])
            self.model.addConstr(rho_nl[t] <= rho_ub * (1 - self.sc[t]))

            self.model.addConstr(gu.quicksum(q_nl[t, k] for k in range(0, rho_ub + 1)) == 1)
            self.model.addConstr(rho_nl[t] == gu.quicksum(k * q_nl[t, k] for k in range(0, rho_ub + 1)))
            self.model.addConstr(g_nl[t] == gu.quicksum(r_hat[k] * q_nl[t, k] for k in range(0, rho_ub + 1)))

            if t > 1:
                self.model.addConstr(b_minus[t] + b_zero[t] + b_plus[t] == 1)
                self.model.addConstr(vartheta[t] == phi_nl[t - 1] + delta_nl[t] - g_nl[t])
                self.model.addConstr(vartheta[t] <= M_phi * (1 - b_minus[t]))
                self.model.addConstr(vartheta[t] >= -M_phi * b_minus[t])
                self.model.addConstr(vartheta[t] <= e_max + M_phi * b_plus[t])
                self.model.addConstr(vartheta[t] >= e_max - M_phi * (1 - b_plus[t]))
                self.model.addConstr(phi_nl[t] <= e_max - b_minus[t] * e_max)
                self.model.addConstr(phi_nl[t] >= e_max * b_plus[t])
                self.model.addConstr(phi_nl[t] - vartheta[t] <= M_phi * (b_minus[t] + b_plus[t]))
                self.model.addConstr(vartheta[t] - phi_nl[t] <= M_phi * (b_minus[t] + b_plus[t]))

            self.model.addConstr(self.p[t] == 1 - phi_nl[t])

        self.model.update()
