import gurobipy as gu
import math
from .base_case import DAYS_OFF, F_S, MIN_WD, MAX_WD

class Subproblem:
    def __init__(self, duals_i, duals_ts, df, i, iteration, eps, Min_WD_i, Max_WD_i, chi, model_type='nonlinear'):
        itr = iteration + 1
        self.days = df['T'].dropna().astype(int).unique().tolist()
        self.shifts = df['K'].dropna().astype(int).unique().tolist()
        self.duals_i = duals_i
        self.duals_ts = duals_ts
        self.model = gu.Model("Subproblem")
        self.index = i
        self.itr = itr
        self.End = len(self.days)
        self.mu = 0.1
        self.epsilon = eps
        self.mue = 0.1
        self.chi = chi
        self.omega = math.ceil(round(1 / self.epsilon, 6)) if self.epsilon > 1e-6 else 999
        self.M = len(self.days) + self.omega
        self.xi = 1 - self.epsilon * self.omega
        self.Days_Off = DAYS_OFF
        self.Min_WD = MIN_WD
        self.Max_WD = MAX_WD
        self.F_S = F_S
        self.Days = len(self.days)
        self.Min_WD_i = Min_WD_i
        self.Max_WD_i = Max_WD_i
        self.model_type = model_type

    def buildModel(self):
        self.generateVariables()
        self.generateConstraints()
        self.generateRegConstraints2()
        self.generateObjective()
        self.model.update()

    def buildIndividualModel(self):
        self.generateVariables()
        self.generateConstraints()
        self.generateRegConstraints()
        self.generateObjective()
        self.model.update()

    def generateVariables(self):
        self.x = self.model.addVars(self.days, self.shifts, vtype=gu.GRB.BINARY, name="x")
        self.y = self.model.addVars(self.days, vtype=gu.GRB.BINARY, name="y")
        self.o = self.model.addVars(self.days, self.shifts, vtype=gu.GRB.CONTINUOUS, name="o")
        self.u = self.model.addVars(self.days, self.shifts, vtype=gu.GRB.CONTINUOUS, name="u")
        self.sc = self.model.addVars(self.days, vtype=gu.GRB.BINARY, name="sc")
        self.v = self.model.addVars(self.days, vtype=gu.GRB.BINARY, name="v")
        self.q = self.model.addVars(self.days, self.shifts, vtype=gu.GRB.BINARY, name="q")
        self.rho = self.model.addVars(self.days, self.shifts, vtype=gu.GRB.BINARY, name="rho")
        self.z = self.model.addVars(self.days, self.shifts, vtype=gu.GRB.BINARY, name="z")
        self.performance = self.model.addVars(self.days, self.shifts, [self.itr], vtype=gu.GRB.CONTINUOUS,
                                              lb=0, ub=1, name="performance")
        self.p = self.model.addVars(self.days, vtype=gu.GRB.CONTINUOUS, lb=0, ub=1, name="p")
        self.n = self.model.addVars(self.days, vtype=gu.GRB.INTEGER, ub=self.End, lb=0, name="n")
        self.n_h = self.model.addVars(self.days, vtype=gu.GRB.INTEGER, lb=0, ub=self.End, name="n_h")
        self.h = self.model.addVars(self.days, vtype=gu.GRB.BINARY, name="h")
        self.e = self.model.addVars(self.days, vtype=gu.GRB.BINARY, name="e")
        self.kappa = self.model.addVars(self.days, vtype=gu.GRB.BINARY, name="kappa")
        self.b = self.model.addVars(self.days, vtype=gu.GRB.BINARY, name="b")
        self.phi = self.model.addVars(self.days, vtype=gu.GRB.BINARY, name="phi")
        self.r = self.model.addVars(self.days, vtype=gu.GRB.BINARY, name="r")
        self.f = self.model.addVars(self.days, vtype=gu.GRB.BINARY, name="f")
        self.ff = self.model.addVars(self.days, vtype=gu.GRB.BINARY, name="ff")
        self.gam = self.model.addVars(self.days, vtype=gu.GRB.BINARY, name="gam")

    def generateConstraints(self):
        for t in self.days:
            #self.model.addLConstr(gu.quicksum(self.x[t, k] for k in self.shifts) <= 1)
            self.model.addLConstr(gu.quicksum(self.x[t, k] for k in self.shifts) == self.y[t])
        for t in self.days:
            for k in self.shifts:
                self.model.addLConstr(
                    self.performance[t, k, self.itr] >= self.p[t] + self.x[t, k] - 1)
                self.model.addLConstr(
                    self.performance[t, k, self.itr] <= self.p[t])
                self.model.addLConstr(self.performance[t, k, self.itr] <= self.x[t, k])
        self.model.addLConstr(self.gam[1] == 1)
        for t in range(2, len(self.days) + 1):
            self.model.addLConstr(self.gam[t] <= self.gam[t - 1])
            self.model.addLConstr(self.gam[t] <= (1 - self.y[t - 1]))
            self.model.addLConstr(self.gam[t] >= (1 - self.y[t - 1]) + self.gam[t - 1] - 1)
        for k in self.shifts:
            for t in self.days:
                self.model.addLConstr(self.rho[t, k] <= 1 - self.q[t, k] - self.gam[t])
                self.model.addLConstr(self.rho[t, k] <= self.x[t, k])
                self.model.addLConstr(self.rho[t, k] >= (1 - self.q[t, k]) + self.x[t, k] - 1 - self.gam[t])
                self.model.addLConstr(self.z[t, k] <= self.q[t, k])
                self.model.addLConstr(self.z[t, k] <= (1 - self.y[t]))
                self.model.addLConstr(self.z[t, k] >= self.q[t, k] + (1 - self.y[t]) - 1)
            for t in range(1, len(self.days)):
                self.model.addLConstr(self.q[t + 1, k] == self.x[t, k] + self.z[t, k])
        for t in self.days:
            self.model.addLConstr(1 == gu.quicksum(self.x[t, k] for k in self.shifts) + (1 - self.y[t]))
            self.model.addLConstr(gu.quicksum(self.rho[t, k] for k in self.shifts) == self.sc[t])
        for t in range(2, len(self.days) - self.Days_Off + 2):
            for s in range(t + 1, t + self.Days_Off):
                self.model.addLConstr(1 + self.y[t] >= self.y[t - 1] + self.y[s])
        for k1, k2 in self.F_S:
            if k1 in self.shifts and k2 in self.shifts:
                for t in range(1, len(self.days)):
                    self.model.addLConstr(self.x[t, k1] + self.x[t + 1, k2] <= 1)
        
        # Performance Constraints
        if self.model_type == 'linear':
            # Window {t-chi+1,...,t} (chi days), matching Model.tex model:r1/model:r2.
            for t in range(self.chi, len(self.days) + 1):
                self.model.addLConstr(1 <= gu.quicksum(
                    self.sc[j] for j in range(t - self.chi + 1, t + 1)) + self.r[t])
                for k in range(t - self.chi + 1, t + 1):
                    self.model.addLConstr(self.sc[k] + self.r[t] <= 1)
            for t in range(1, self.chi):
                self.model.addLConstr(0 == self.r[t])
            self.model.update()
            self.model.addLConstr(0 == self.n[1])
            self.model.addLConstr(0 == self.sc[1])
            self.model.addLConstr(1 == self.p[1])
            self.model.addLConstr(0 == self.h[1])
            for t in self.days:
                self.model.addLConstr(
                    self.omega * self.kappa[t] <= gu.quicksum(self.sc[j] for j in range(1, t + 1)))
                self.model.addLConstr(gu.quicksum(self.sc[j] for j in range(1, t + 1)) <= len(self.days) + (
                            self.omega - 1 - len(self.days)) * (1 - self.kappa[t]))
            for t in range(2, len(self.days) + 1):
                self.model.addLConstr(self.ff[t] <= self.n[t])
                self.model.addLConstr(self.n[t] <= len(self.days) * self.ff[t])
                self.model.addLConstr(self.b[t] <= 1 - self.ff[t-1])
                self.model.addLConstr(self.b[t] <= 1 - self.sc[t])
                self.model.addLConstr(self.b[t] <= self.r[t])
                self.model.addLConstr(self.b[t] >= self.r[t] + (1 - self.ff[t-1]) + (1 - self.sc[t]) - 2)
                self.model.addLConstr(self.p[t] == 1 - self.epsilon * self.n[t] - self.xi * self.kappa[t])
                self.model.addLConstr(self.n[t] == (self.n[t - 1] + self.sc[t])-self.r[t]-self.e[t]+self.b[t])
                self.model.addLConstr(self.omega * self.h[t] <= self.n[t])
                self.model.addLConstr(self.n[t] <= ((self.omega - 1) + self.h[t]))
                self.model.addLConstr(self.e[t] <= self.sc[t])
                self.model.addLConstr(self.e[t] <= self.h[t - 1])
                self.model.addLConstr(self.e[t] >= self.sc[t] + self.h[t - 1] - 1)
        else:
            self.nlPerformance()

        self.model.update()

        # Add explicit constraints for threshold analysis
        if getattr(self, 'enforce_no_change', False):
            for t in self.days:
                self.model.addLConstr(self.sc[t] == 0)
        
        tau = getattr(self, 'enforce_performance_floor', None)
        if tau is not None:
            for t in self.days:
                self.model.addLConstr(self.p[t] >= tau)
        self.model.update()


    def nlPerformance(self):
        max_d = len(self.days)
        
        # Read or set non-linear parameters
        gamma_C = getattr(self, 'gamma_C', 1.25)
        gamma_R = getattr(self, 'gamma_R', 0.5)
        alpha_R = getattr(self, 'alpha_R', 0.04)
        e_max = getattr(self, 'e_max', 1.0)
        delta = getattr(self, 'delta', None)
        if delta is None:
            from core.worker_groups import get_default_delta
            delta = get_default_delta(self.epsilon)

        # h_hat and r_hat lookup tables
        h_hat = {n: (n**gamma_C - (n-1)**gamma_C) for n in range(1, max_d + 1)}
        h_hat[0] = 0.0
        
        # R(rho;gamma_R) = alpha_R[(rho-chi+1)^g - (rho-chi)^g], first eligible day rho=chi
        # (matches Model.tex model:phi and core/nonlinear_transitions.py::r_func).
        r_hat = {}
        for k in range(0, max_d + 1):
            if k < self.chi:
                r_hat[k] = 0.0
            else:
                r_hat[k] = alpha_R * ((k - self.chi + 1)**gamma_R - (k - self.chi)**gamma_R)
        
        M_nu = max_d + 1
        M_rho = max_d + 1
        
        max_delta = max([max(row) for row in delta])
        max_h = max(h_hat.values()) if max_d > 0 else 0
        max_r = max(r_hat.values()) if max_d > 0 else 0
        M_phi = 1.0 + max(max_delta * max_h, max_r)
            
        # Variables (no index i needed!)
        w_nl = self.model.addVars(self.days, self.shifts, self.shifts, vtype=gu.GRB.BINARY, name="w_nl")
        nu_nl = self.model.addVars(self.days, vtype=gu.GRB.INTEGER, lb=0, ub=max_d, name="nu_nl")
        a_nl = self.model.addVars(self.days, self.shifts, self.shifts, range(1, max_d + 1), vtype=gu.GRB.BINARY, name="a_nl")
        delta_nl = self.model.addVars(self.days, vtype=gu.GRB.CONTINUOUS, lb=0, name="delta_nl")
        rho_nl = self.model.addVars(self.days, vtype=gu.GRB.INTEGER, lb=0, ub=max_d, name="rho_nl")
        q_nl = self.model.addVars(self.days, range(0, max_d + 1), vtype=gu.GRB.BINARY, name="q_nl")
        g_nl = self.model.addVars(self.days, vtype=gu.GRB.CONTINUOUS, lb=0, name="g_nl")
        vartheta = self.model.addVars(self.days, vtype=gu.GRB.CONTINUOUS, lb=-gu.GRB.INFINITY, name="vartheta")
        phi_nl = self.model.addVars(self.days, vtype=gu.GRB.CONTINUOUS, lb=0, ub=1, name="phi_nl")
        b_minus = self.model.addVars(self.days, vtype=gu.GRB.BINARY, name="b_minus")
        b_zero = self.model.addVars(self.days, vtype=gu.GRB.BINARY, name="b_zero")
        b_plus = self.model.addVars(self.days, vtype=gu.GRB.BINARY, name="b_plus")

        self.model.update()

        # First day initializations
        self.model.addConstr(nu_nl[1] == self.sc[1])
        self.model.addConstr(rho_nl[1] == 1 - self.sc[1])
        self.model.addConstr(phi_nl[1] == 0)

        for t in self.days:
            # Transition Tracking (w_nl)
            for s in self.shifts:
                for s_prime in self.shifts:
                    if s != s_prime:
                        self.model.addConstr(w_nl[t, s, s_prime] <= self.q[t, s])
                        self.model.addConstr(w_nl[t, s, s_prime] <= self.x[t, s_prime])
                        self.model.addConstr(w_nl[t, s, s_prime] <= 1 - self.gam[t])
                        self.model.addConstr(w_nl[t, s, s_prime] >= self.q[t, s] + self.x[t, s_prime] - self.gam[t] - 1)
                    else:
                        self.model.addConstr(w_nl[t, s, s_prime] == 0)

            # Link w_nl to sc
            self.model.addConstr(self.sc[t] == gu.quicksum(w_nl[t, s, s_prime] for s in self.shifts for s_prime in self.shifts))

            # Change-sequence tracking
            self.model.addConstr(nu_nl[t] <= max_d * self.sc[t])
            if t > 1:
                self.model.addConstr(nu_nl[t] <= nu_nl[t-1] + 1 + M_nu * (1 - self.sc[t]))
                self.model.addConstr(nu_nl[t] >= nu_nl[t-1] + 1 - M_nu * (1 - self.sc[t]))

            # Lookup variables
            for s in self.shifts:
                for s_prime in self.shifts:
                    if s != s_prime:
                        self.model.addConstr(gu.quicksum(a_nl[t, s, s_prime, n] for n in range(1, max_d + 1)) == w_nl[t, s, s_prime])
            
            self.model.addConstr(nu_nl[t] == gu.quicksum(n * a_nl[t, s, s_prime, n] for s in self.shifts for s_prime in self.shifts for n in range(1, max_d + 1) if s != s_prime))

            # Degradation Amount
            self.model.addConstr(delta_nl[t] == gu.quicksum(delta[s, s_prime] * h_hat[n] * a_nl[t, s, s_prime, n] for s in self.shifts for s_prime in self.shifts for n in range(1, max_d + 1) if s != s_prime))

            # Stable-sequence tracking
            if t > 1:
                self.model.addConstr(rho_nl[t] <= rho_nl[t-1] + 1 + M_rho * self.sc[t])
                self.model.addConstr(rho_nl[t] >= rho_nl[t-1] + 1 - M_rho * self.sc[t])
            self.model.addConstr(rho_nl[t] <= max_d * (1 - self.sc[t]))

            # Recovery lookup
            self.model.addConstr(gu.quicksum(q_nl[t, k] for k in range(0, max_d + 1)) == 1)
            self.model.addConstr(rho_nl[t] == gu.quicksum(k * q_nl[t, k] for k in range(0, max_d + 1)))
            self.model.addConstr(g_nl[t] == gu.quicksum(r_hat[k] * q_nl[t, k] for k in range(0, max_d + 1)))

            # Nonlinear State Clipping
            if t > 1:
                self.model.addConstr(b_minus[t] + b_zero[t] + b_plus[t] == 1)
                self.model.addConstr(vartheta[t] == phi_nl[t-1] + delta_nl[t] - g_nl[t])
                
                self.model.addConstr(vartheta[t] <= M_phi * (1 - b_minus[t]))
                self.model.addConstr(vartheta[t] >= -M_phi * b_minus[t])
                
                self.model.addConstr(vartheta[t] <= e_max + M_phi * b_plus[t])
                self.model.addConstr(vartheta[t] >= e_max - M_phi * (1 - b_plus[t]))
                
                self.model.addConstr(phi_nl[t] <= e_max - b_minus[t] * e_max)
                self.model.addConstr(phi_nl[t] >= e_max * b_plus[t])
                
                self.model.addConstr(phi_nl[t] - vartheta[t] <= M_phi * (b_minus[t] + b_plus[t]))
                self.model.addConstr(vartheta[t] - phi_nl[t] <= M_phi * (b_minus[t] + b_plus[t]))

            # Effective Performance
            self.model.addConstr(self.p[t] == 1 - phi_nl[t])

        self.model.update()

    def generateRegConstraints(self):
        for i in [self.index]:
            for t in range(1, len(self.days) - self.Max_WD_i[i] + 1):
                self.model.addLConstr(
                    gu.quicksum(self.y[u] for u in range(t, t + 1 + self.Max_WD_i[i])) <= self.Max_WD_i[i])
            for t in range(2, len(self.days) - self.Min_WD_i[i] + 1):
                self.model.addLConstr(
                    gu.quicksum(self.y[u] for u in range(t + 1, t + self.Min_WD_i[i] + 1)) >= self.Min_WD_i[i] * (
                            self.y[t + 1] - self.y[t]))
        self.model.update()

    def generateRegConstraints2(self):
        for i in [self.index]:
            for t in range(1, len(self.days) - self.Max_WD + 1):
                self.model.addLConstr(
                    gu.quicksum(self.y[u] for u in range(t, t + 1 + self.Max_WD)) <= self.Max_WD)
            for t in range(1, len(self.days) - self.Min_WD + 1):
                self.model.addLConstr(
                    gu.quicksum(self.y[u] for u in range(t + 1, t + self.Min_WD + 1)) >= self.Min_WD * (
                            self.y[t + 1] - self.y[t]))
            
            # Constraint for start of horizon (t=0 transition to y[1])
            # If y[1]=1, must work Min_WD days
            if len(self.days) >= self.Min_WD:
                self.model.addLConstr(
                    gu.quicksum(self.y[u] for u in range(1, 1 + self.Min_WD)) >= self.Min_WD * self.y[1])
        self.model.update()

    def addECPConstraint(self, k):
        """Imposes an upper bound of k shift changes per rolling 7-day window."""
        for d in self.days:
            d_prime_range = range(max(1, d - 6), d + 1)
            self.model.addLConstr(
                gu.quicksum(self.sc[d_prime] for d_prime in d_prime_range) <= k,
                name=f"ecp_rolling_d{d}"
            )
        self.model.update()

    def generateObjective(self):
        self.model.setObjective(0 - gu.quicksum(self.performance[t, s, self.itr] * self.duals_ts[t, s] for t in self.days for s in self.shifts) - self.duals_i, sense=gu.GRB.MINIMIZE)

    def getNewSchedule(self):
        print(f'perf', self.model.getAttr("X", self.performance))
        print(f'x', self.model.getAttr("X", self.x))
        print(f'p', self.model.getAttr("X", self.p))
        print(f'r', self.model.getAttr("X", self.r))
        print(f'sc', self.model.getAttr("X", self.sc))

        return self.model.getAttr("X", self.performance)

    def getOptX(self):
        print(f'x', self.model.getAttr("X", self.x))
        return self.model.getAttr("X", self.x)

    def getOptP(self):
        return self.model.getAttr("X", self.p)

    def getOptC(self):
        print(f'sc', self.model.getAttr("X", self.sc))
        return self.model.getAttr("X", self.sc)

    def getOptF(self):
        return self.model.getAttr("X", self.ff)

    def getOptN(self):
        return self.model.getAttr("X", self.n)

    def getOptR(self):
        print(f'r', self.model.getAttr("X", self.r))
        return self.model.getAttr("X", self.r)

    def getOptEUp(self):
        return self.model.getAttr("X", self.e)

    def getOptElow(self):
        return self.model.getAttr("X", self.b)


    def getOptPerf(self):
        return self.model.getAttr("X", self.performance)
    def getStatus(self):
        return self.model.status

    def solveModelOpt(self, timeLimit):
        try:
            self.model.Params.TimeLimit = timeLimit
            self.model.Params.Threads = 0
            self.model.Params.OutputFlag = 0
            self.model.Params.MIPGap = 0.00001
            self.model.optimize()
        except gu.GurobiError as e:
            print('Error code ' + str(e.errno) + ': ' + str(e))

    def solveModelNOpt(self, timeLimit):
        try:
            self.model.Params.TimeLimit = timeLimit
            self.model.Params.Threads = 0
            self.model.Params.OutputFlag = 0
            self.model.Params.MIPGap = 0.05
            self.model.optimize()
        except gu.GurobiError as e:
            print('Error code ' + str(e.errno) + ': ' + str(e))