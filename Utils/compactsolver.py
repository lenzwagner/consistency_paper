import gurobipy as gu
import math
import time

class Problem:
    def __init__(self, dfData, DemandDF, eps, Min_WD_i, Max_WD_i, chi, worker_groups=None, model_type='nonlinear'):
        self.I = dfData['I'].dropna().astype(int).unique().tolist()
        self.T = dfData['T'].dropna().astype(int).unique().tolist()
        self.K = dfData['K'].dropna().astype(int).unique().tolist()
        self.End = len(self.T)
        self.Week = int(len(self.T) / 7)
        self.Weeks = range(1, self.Week + 1)
        self.demand = DemandDF
        self.model = gu.Model("MasterProblem")
        self.mu = 0.1
        self.epsilon = eps  # Default epsilon
        self.mue = 0.1
        self.zeta = 0.1
        self.chi = chi  # Default chi
        self.omega = math.floor(1 / (self.epsilon + 1e-6))
        self.M = len(self.T) + self.omega
        self.xi = 1 - self.epsilon * self.omega
        self.Days_Off = 2
        self.Min_WD = 2
        self.Max_WD = 5
        self.F_S = [(3, 1), (3, 2), (2, 1)]
        self.Days = len(self.T)
        self.demand_values = [self.demand[key] for key in self.demand.keys()]
        self.Min_WD_i = Min_WD_i
        self.Max_WD_i = Max_WD_i
        self.model_type = model_type
        
        # Per-worker parameters for heterogeneous groups
        if worker_groups is not None:
            self.eps_by_worker = {}
            self.chi_by_worker = {}
            self.xi_by_worker = {}
            self.gamma_C_by_worker = {}
            self.gamma_R_by_worker = {}
            self.alpha_R_by_worker = {}
            self.e_max_by_worker = {}
            self.delta_by_worker = {}
            for group in worker_groups.values():
                omega_g = math.floor(1 / (group.epsilon + 1e-6))
                xi_g = 1 - group.epsilon * omega_g
                for w in group.worker_ids:
                    self.eps_by_worker[w] = group.epsilon
                    self.chi_by_worker[w] = group.chi
                    self.xi_by_worker[w] = xi_g
                    self.gamma_C_by_worker[w] = group.gamma_C
                    self.gamma_R_by_worker[w] = group.gamma_R
                    self.alpha_R_by_worker[w] = group.alpha_R
                    self.e_max_by_worker[w] = group.e_max
                    self.delta_by_worker[w] = group.delta
        else:
            # Homogeneous: all workers use same parameters
            from core.worker_groups import get_default_delta
            default_delta = get_default_delta(eps)
            self.eps_by_worker = {i: eps for i in self.I}
            self.chi_by_worker = {i: chi for i in self.I}
            self.xi_by_worker = {i: self.xi for i in self.I}
            self.gamma_C_by_worker = {i: 1.25 for i in self.I}
            self.gamma_R_by_worker = {i: 0.5 for i in self.I}
            self.alpha_R_by_worker = {i: 0.04 for i in self.I}
            self.e_max_by_worker = {i: 0.5 for i in self.I} # Wait, note: default e_max was 0.5 or 1.0? We keep same
            self.delta_by_worker = {i: default_delta for i in self.I}

    def buildLinModel(self):
        self.t0 = time.time()
        self.generateVariables()
        self.genGenCons()
        self.genChangesCons()
        self.genRegCons()
        self.model.update()
        if self.model_type == 'linear':
            self.linPerformance()
        else:
            self.nlPerformance()
        self.generateObjective()
        self.updateModel()


    def generateVariables(self):
        self.x = self.model.addVars(self.I, self.T, self.K, vtype=gu.GRB.BINARY, name="x")
        self.kk = self.model.addVars(self.I, self.Weeks, vtype=gu.GRB.BINARY, name="k")
        self.y = self.model.addVars(self.I, self.T, vtype=gu.GRB.BINARY, name="y")
        self.o = self.model.addVars(self.T, self.K, vtype=gu.GRB.CONTINUOUS, name="o")
        self.u = self.model.addVars(self.T, self.K, lb = 0, vtype=gu.GRB.CONTINUOUS, name="u")
        self.sc = self.model.addVars(self.I, self.T, vtype=gu.GRB.BINARY, name="sc")
        self.v = self.model.addVars(self.I, self.T, vtype=gu.GRB.BINARY, name="v")
        self.q = self.model.addVars(self.I, self.T, self.K, vtype=gu.GRB.BINARY, name="q")
        self.rho = self.model.addVars(self.I, self.T, self.K, vtype=gu.GRB.BINARY, name="rho")
        self.z = self.model.addVars(self.I, self.T, self.K, vtype=gu.GRB.BINARY, name="z")
        self.perf = self.model.addVars(self.I, self.T, self.K, vtype=gu.GRB.CONTINUOUS, lb=0, ub=1, name="perf")
        self.p = self.model.addVars(self.I, self.T, vtype=gu.GRB.CONTINUOUS, lb=0, ub=1, name="p")
        self.n = self.model.addVars(self.I, self.T, vtype=gu.GRB.INTEGER, ub=self.Days, lb=0, name="n")
        self.n_h = self.model.addVars(self.I, self.T, vtype=gu.GRB.INTEGER, lb=0, ub=self.Days, name="n_h")
        self.h = self.model.addVars(self.I, self.T, vtype=gu.GRB.BINARY, name="h")
        self.e = self.model.addVars(self.I, self.T, vtype=gu.GRB.BINARY, name="e")
        self.kappa = self.model.addVars(self.I, self.T, vtype=gu.GRB.BINARY, name="kappa")
        self.b = self.model.addVars(self.I, self.T, vtype=gu.GRB.BINARY, name="b")
        self.phi = self.model.addVars(self.I, self.T, vtype=gu.GRB.BINARY, name="phi")
        self.r = self.model.addVars(self.I, self.T, vtype=gu.GRB.BINARY, name="r")
        self.f = self.model.addVars(self.I, self.T, vtype=gu.GRB.BINARY, name="f")
        self.ff = self.model.addVars(self.I, self.T, vtype=gu.GRB.BINARY, name="ff")
        self.g = self.model.addVars(self.I, self.T, vtype=gu.GRB.BINARY, name="g")
        self.w = self.model.addVars(self.I, self.T, vtype=gu.GRB.BINARY, name="w")
        self.gg = self.model.addVars(self.I, self.T, vtype=gu.GRB.CONTINUOUS, lb=-gu.GRB.INFINITY, ub=gu.GRB.INFINITY,
                                     name="gg")
        self.gam = self.model.addVars(self.I, self.T, vtype=gu.GRB.BINARY, name="gam")


    def genGenCons(self):
        for i in self.I:
            for t in self.T:
                self.model.addLConstr(gu.quicksum(self.x[i, t, k] for k in self.K) <= 1)
                self.model.addLConstr(gu.quicksum(self.x[i, t, k] for k in self.K) == self.y[i, t])
        for t in self.T:
            for k in self.K:
                self.model.addLConstr(
                    gu.quicksum(self.perf[i, t, k] for i in self.I) + self.u[t, k] >= self.demand[t, k])
        for i in self.I:
            for t in self.T:
                for k in self.K:
                    self.model.addLConstr(self.x[i, t, k] + self.p[i, t] - 1 <= self.perf[i, t, k])
                    self.model.addLConstr(self.perf[i, t, k] <= self.p[i, t])
                    self.model.addLConstr(self.perf[i, t, k] <= self.x[i, t, k])
        self.model.update()

    def genChangesCons(self):
        for i in self.I:
            self.model.addLConstr(self.gam[i, 1] == 1)
            for t in range(2, len(self.T) + 1):
                self.model.addLConstr(self.gam[i, t] <= self.gam[i, t-1])
                self.model.addLConstr(self.gam[i, t] <= (1 - self.y[i, t - 1]))
                self.model.addLConstr(self.gam[i, t] >= (1 - self.y[i, t -1 ]) + self.gam[i, t-1] - 1)
            for k in self.K:
                for t in self.T:
                    self.model.addLConstr(self.rho[i, t, k] <= 1 - self.q[i, t, k]- self.gam[i, t])
                    self.model.addLConstr(self.rho[i, t, k] <= self.x[i, t, k])
                    self.model.addLConstr(self.rho[i, t, k] >= (1 - self.q[i, t, k]) + self.x[i, t, k] - 1- self.gam[i, t])
                    self.model.addLConstr(self.z[i, t, k] <= self.q[i, t, k])
                    self.model.addLConstr(self.z[i, t, k] <= (1 - self.y[i, t]))
                    self.model.addLConstr(self.z[i, t, k] >= self.q[i, t, k] + (1 - self.y[i, t]) - 1)
                for t in range(1, len(self.T)):
                    self.model.addLConstr(self.q[i, t + 1, k] == self.x[i, t, k] + self.z[i, t, k])
            for t in self.T:
                self.model.addLConstr(1 == gu.quicksum(self.x[i, t, k] for k in self.K) + (1 - self.y[i, t]))
                self.model.addLConstr(gu.quicksum(self.rho[i, t, k] for k in self.K) == self.sc[i, t])
        self.model.update()

    def genRegConsIndivudal(self):
        for i in self.I:
            for t in range(1, len(self.T) - self.Max_WD_i[i] + 1):
                self.model.addLConstr(
                    gu.quicksum(self.y[i, u] for u in range(t, t + 1 + self.Max_WD_i[i])) <= self.Max_WD_i[i])
            for t in range(2, len(self.T) - self.Min_WD_i[i] + 1):
                self.model.addLConstr(
                    gu.quicksum(self.y[i, u] for u in range(t + 1, t + self.Min_WD_i[i] + 1)) >= self.Min_WD_i[i] * (
                                self.y[i, t + 1] - self.y[i, t]))
            if len(self.T) >= self.Min_WD_i[i]:
                self.model.addLConstr(
                    gu.quicksum(self.y[i, u] for u in range(1, 1 + self.Min_WD_i[i])) >= self.Min_WD_i[i] * self.y[i, 1])
        for i in self.I:
            for t in range(2, len(self.T) - self.Days_Off + 2):
                for s in range(t + 1, t + self.Days_Off):
                    self.model.addLConstr(1 + self.y[i, t] >= self.y[i, t - 1] + self.y[i, s])
        for i in self.I:
            for k1, k2 in self.F_S:
                for t in range(1, len(self.T)):
                    self.model.addLConstr(self.x[i, t, k1] + self.x[i, t + 1, k2] <= 1)
        self.model.update()

    def genRegCons(self):
        for i in self.I:
            for t in range(1, len(self.T) - self.Max_WD + 1):
                self.model.addLConstr(
                    gu.quicksum(self.y[i, u] for u in range(t, t + 1 + self.Max_WD)) <= self.Max_WD)
            for t in range(1, len(self.T) - self.Min_WD + 1):
                self.model.addLConstr(
                    gu.quicksum(self.y[i, u] for u in range(t + 1, t + self.Min_WD + 1)) >= self.Min_WD * (
                                self.y[i, t + 1] - self.y[i, t]))
            if len(self.T) >= self.Min_WD:
                self.model.addLConstr(
                    gu.quicksum(self.y[i, u] for u in range(1, 1 + self.Min_WD)) >= self.Min_WD * self.y[i, 1])
        for i in self.I:
            for t in range(2, len(self.T) - self.Days_Off + 2):
                for s in range(t + 1, t + self.Days_Off):
                    self.model.addLConstr(1 + self.y[i, t] >= self.y[i, t - 1] + self.y[i, s])
        for i in self.I:
            for k1, k2 in self.F_S:
                for t in range(1, len(self.T)):
                    self.model.addLConstr(self.x[i, t, k1] + self.x[i, t + 1, k2] <= 1)
        self.model.update()

    def Recovery(self):
        for i in self.I:
            chi_i = self.chi_by_worker.get(i, self.chi)
            for t in range(1 + chi_i, len(self.T) + 1):
                self.model.addLConstr(1 <= gu.quicksum(
                    self.sc[i, j] for j in range(t - chi_i, t+1)) + self.r[i, t])
                for k in range(t - chi_i, t+1):
                    self.model.addLConstr(self.sc[i, k] + self.r[i, t] <= 1)
            for t in range(1, 1 + chi_i):
                self.model.addLConstr(0 == self.r[i, t])
        self.model.update()

    def linPerformance(self):
        for i in self.I:
            eps_i = self.eps_by_worker.get(i, self.epsilon)
            xi_i = self.xi_by_worker.get(i, self.xi)
            omega_i = math.floor(1 / (eps_i + 1e-6))
            
            self.model.addLConstr(0 == self.n[i, 1])
            self.model.addLConstr(0 == self.sc[i, 1])
            self.model.addLConstr(1 == self.p[i, 1])
            self.model.addLConstr(0 == self.h[i, 1])
            for t in self.T:
                self.model.addLConstr(
                    omega_i * self.kappa[i, t] <= gu.quicksum(self.sc[i, j] for j in range(1, t + 1)))
                self.model.addLConstr(gu.quicksum(self.sc[i, j] for j in range(1, t + 1)) <= len(self.T) + (
                        omega_i - 1 - len(self.T)) * (1 - self.kappa[i, t]))
            for t in range(2, len(self.T) + 1):
                self.model.addLConstr(self.ff[i, t] <= self.n[i, t])
                self.model.addLConstr(self.n[i, t] <= len(self.T) * self.ff[i, t])
                self.model.addLConstr(self.b[i, t] <= 1 - self.ff[i, t - 1])
                self.model.addLConstr(self.b[i, t] <= 1 - self.sc[i, t])
                self.model.addLConstr(self.b[i, t] <= self.r[i, t])
                self.model.addLConstr(self.b[i, t] >= self.r[i, t] + (1 - self.ff[i, t - 1]) + (1 - self.sc[i, t]) - 2)
                # Use per-worker epsilon and xi
                self.model.addLConstr(self.p[i, t] == 1 - eps_i * self.n[i, t] - xi_i * self.kappa[i, t])
                self.model.addLConstr(
                    self.n[i, t] == (self.n[i, t - 1] + self.sc[i, t]) - self.r[i, t] - self.e[i, t] + self.b[i, t])
                self.model.addLConstr(omega_i * self.h[i, t] <= self.n[i, t])
                self.model.addLConstr(self.n[i, t] <= ((omega_i - 1) + self.h[i, t]))
                self.model.addLConstr(self.e[i, t] <= self.sc[i, t])
                self.model.addLConstr(self.e[i, t] <= self.h[i, t - 1])
                self.model.addLConstr(self.e[i, t] >= self.sc[i, t] + self.h[i, t - 1] - 1)
        self.model.update()

    def generateObjective(self):
        self.model.setObjective(gu.quicksum(self.u[t, k] for k in self.K for t in self.T), sense=gu.GRB.MINIMIZE)

    def updateModel(self):
        self.model.update()

    def ModelParams(self):
        self.model.setParam('ConcurrentMIP', 2)
        self.model.setParam('Threads', 1)

    def solveModel(self):
        self.t1 = time.time()
        try:
            self.model.Params.MIPGap = 0
            self.model.optimize()
        except gu.GurobiError as e:
            print('Error code ' + str(e.errno) + ': ' + str(e))
    def get_final_values(self):
        dict = self.model.getAttr("X", self.x)
        liste = list(dict.values())
        final = [0.0 if x == -0.0 else x for x in liste]
        return final

    def setStart(self, start_dict):
        for key, value in start_dict.items():
            self.x[key].Start = value
        self.model.Params.MIPFocus = 3
        self.model.update()

    def getNewSchedule(self):
        return self.model.getAttr("X", self.perf)

    def nlPerformance(self):
        max_d = len(self.T)
        
        # h_hat and r_hat lookup tables per worker
        h_hat = {}
        r_hat = {}
        for i in self.I:
            gamma_C = self.gamma_C_by_worker[i]
            gamma_R = self.gamma_R_by_worker[i]
            alpha_R = self.alpha_R_by_worker[i]
            chi_i = self.chi_by_worker[i]
            
            h_hat[i] = {n: (n**gamma_C - (n-1)**gamma_C) for n in range(1, max_d + 1)}
            h_hat[i][0] = 0.0
            
            r_hat[i] = {}
            for k in range(0, max_d + 1):
                if k <= chi_i:
                    r_hat[i][k] = 0.0
                else:
                    r_hat[i][k] = alpha_R * ((k - chi_i)**gamma_R - (k - chi_i - 1)**gamma_R)
        
        M_nu = max_d + 1
        M_rho = max_d + 1
        
        M_phi = {}
        for i in self.I:
            delta = self.delta_by_worker[i]
            max_delta = max([max(row) for row in delta])
            max_h = max(h_hat[i].values()) if max_d > 0 else 0
            max_r = max(r_hat[i].values()) if max_d > 0 else 0
            M_phi[i] = 1.0 + max(max_delta * max_h, max_r)
            
        # Variables
        w_nl = self.model.addVars(self.I, self.T, self.K, self.K, vtype=gu.GRB.BINARY, name="w_nl")
        nu_nl = self.model.addVars(self.I, self.T, vtype=gu.GRB.INTEGER, lb=0, ub=max_d, name="nu_nl")
        a_nl = self.model.addVars(self.I, self.T, self.K, self.K, range(1, max_d + 1), vtype=gu.GRB.BINARY, name="a_nl")
        delta_nl = self.model.addVars(self.I, self.T, vtype=gu.GRB.CONTINUOUS, lb=0, name="delta_nl")
        rho_nl = self.model.addVars(self.I, self.T, vtype=gu.GRB.INTEGER, lb=0, ub=max_d, name="rho_nl")
        q_nl = self.model.addVars(self.I, self.T, range(0, max_d + 1), vtype=gu.GRB.BINARY, name="q_nl")
        g_nl = self.model.addVars(self.I, self.T, vtype=gu.GRB.CONTINUOUS, lb=0, name="g_nl")
        vartheta = self.model.addVars(self.I, self.T, vtype=gu.GRB.CONTINUOUS, lb=-gu.GRB.INFINITY, name="vartheta")
        phi_nl = self.model.addVars(self.I, self.T, vtype=gu.GRB.CONTINUOUS, lb=0, ub=1, name="phi_nl")
        b_minus = self.model.addVars(self.I, self.T, vtype=gu.GRB.BINARY, name="b_minus")
        b_zero = self.model.addVars(self.I, self.T, vtype=gu.GRB.BINARY, name="b_zero")
        b_plus = self.model.addVars(self.I, self.T, vtype=gu.GRB.BINARY, name="b_plus")

        self.model.update()

        for i in self.I:
            # First day initializations
            self.model.addConstr(nu_nl[i, 1] == self.sc[i, 1])
            self.model.addConstr(rho_nl[i, 1] == 1 - self.sc[i, 1])
            self.model.addConstr(phi_nl[i, 1] == 0)

            delta = self.delta_by_worker[i]
            e_max = self.e_max_by_worker[i]

            for t in self.T:
                # Transition Tracking (w_nl)
                for s in self.K:
                    for s_prime in self.K:
                        if s != s_prime:
                            self.model.addConstr(w_nl[i, t, s, s_prime] <= self.q[i, t, s])
                            self.model.addConstr(w_nl[i, t, s, s_prime] <= self.x[i, t, s_prime])
                            self.model.addConstr(w_nl[i, t, s, s_prime] <= 1 - self.gam[i, t])
                            self.model.addConstr(w_nl[i, t, s, s_prime] >= self.q[i, t, s] + self.x[i, t, s_prime] - self.gam[i, t] - 1)
                        else:
                            self.model.addConstr(w_nl[i, t, s, s_prime] == 0)

                # Link w_nl to sc
                self.model.addConstr(self.sc[i, t] == gu.quicksum(w_nl[i, t, s, s_prime] for s in self.K for s_prime in self.K))

                # Change-sequence tracking
                self.model.addConstr(nu_nl[i, t] <= max_d * self.sc[i, t])
                if t > 1:
                    self.model.addConstr(nu_nl[i, t] <= nu_nl[i, t-1] + 1 + M_nu * (1 - self.sc[i, t]))
                    self.model.addConstr(nu_nl[i, t] >= nu_nl[i, t-1] + 1 - M_nu * (1 - self.sc[i, t]))

                # Lookup variables
                for s in self.K:
                    for s_prime in self.K:
                        if s != s_prime:
                            self.model.addConstr(gu.quicksum(a_nl[i, t, s, s_prime, n] for n in range(1, max_d + 1)) == w_nl[i, t, s, s_prime])
                
                self.model.addConstr(nu_nl[i, t] == gu.quicksum(n * a_nl[i, t, s, s_prime, n] for s in self.K for s_prime in self.K for n in range(1, max_d + 1) if s != s_prime))

                # Degradation Amount
                self.model.addConstr(delta_nl[i, t] == gu.quicksum(delta[s, s_prime] * h_hat[i][n] * a_nl[i, t, s, s_prime, n] for s in self.K for s_prime in self.K for n in range(1, max_d + 1) if s != s_prime))

                # Stable-sequence tracking
                if t > 1:
                    self.model.addConstr(rho_nl[i, t] <= rho_nl[i, t-1] + 1 + M_rho * self.sc[i, t])
                    self.model.addConstr(rho_nl[i, t] >= rho_nl[i, t-1] + 1 - M_rho * self.sc[i, t])
                self.model.addConstr(rho_nl[i, t] <= max_d * (1 - self.sc[i, t]))

                # Recovery lookup
                self.model.addConstr(gu.quicksum(q_nl[i, t, k] for k in range(0, max_d + 1)) == 1)
                self.model.addConstr(rho_nl[i, t] == gu.quicksum(k * q_nl[i, t, k] for k in range(0, max_d + 1)))
                self.model.addConstr(g_nl[i, t] == gu.quicksum(r_hat[i][k] * q_nl[i, t, k] for k in range(0, max_d + 1)))

                # Nonlinear State Clipping
                if t > 1:
                    self.model.addConstr(b_minus[i, t] + b_zero[i, t] + b_plus[i, t] == 1)
                    self.model.addConstr(vartheta[i, t] == phi_nl[i, t-1] + delta_nl[i, t] - g_nl[i, t])
                    
                    self.model.addConstr(vartheta[i, t] <= M_phi[i] * (1 - b_minus[i, t]))
                    self.model.addConstr(vartheta[i, t] >= -M_phi[i] * b_minus[i, t])
                    
                    self.model.addConstr(vartheta[i, t] <= e_max + M_phi[i] * b_plus[i, t])
                    self.model.addConstr(vartheta[i, t] >= e_max - M_phi[i] * (1 - b_plus[i, t]))
                    
                    self.model.addConstr(phi_nl[i, t] <= e_max - b_minus[i, t] * e_max)
                    self.model.addConstr(phi_nl[i, t] >= e_max * b_plus[i, t])
                    
                    self.model.addConstr(phi_nl[i, t] - vartheta[i, t] <= M_phi[i] * (b_minus[i, t] + b_plus[i, t]))
                    self.model.addConstr(vartheta[i, t] - phi_nl[i, t] <= M_phi[i] * (b_minus[i, t] + b_plus[i, t]))

                # Effective Performance
                self.model.addConstr(self.p[i, t] == 1 - phi_nl[i, t])

        self.model.update()
