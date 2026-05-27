import gurobipy as gu
import math

class Subproblem:
    def __init__(self, duals_i, duals_ts, df, i, iteration, eps, Min_WD_i, Max_WD_i, chi):
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
        self.Days_Off = 2
        self.Min_WD = 2
        self.Max_WD = 5
        self.F_S = [(3, 1), (3, 2), (2, 1)]
        self.Days = len(self.days)
        self.Min_WD_i = Min_WD_i
        self.Max_WD_i = Max_WD_i

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
        for t in range(1 + self.chi, len(self.days) + 1):
            self.model.addLConstr(1 <= gu.quicksum(
                self.sc[j] for j in range(t - self.chi, t+1)) + self.r[t])
            for k in range(t - self.chi, t + 1):
                self.model.addLConstr(self.sc[k] + self.r[t] <= 1)
        for t in range(1, 1 + self.chi):
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