"""
Exact compact solver: replaces the K_max discretization of the performance state
with a continuous variable e_{i,d}, using an exact big-M / binary-indicator
linearization of the two clamp operations (max(.,0) and min(.,e_max)) to model
the clamped transitions exactly as a standard MILP (see Appendix,
"Exact Continuous Performance-State Compact Model").

No K_max parameter — performance is tracked continuously in [0, e_max].
"""
import gurobipy as gu
import time
from core.base_case import DAYS_OFF, F_S


class ProblemExact:
    def __init__(self, dfData, DemandDF, Min_WD_i, Max_WD_i, worker_groups):
        self.I    = dfData['I'].dropna().astype(int).unique().tolist()
        self.T    = dfData['T'].dropna().astype(int).unique().tolist()
        self.K    = dfData['K'].dropna().astype(int).unique().tolist()
        self.End  = len(self.T)
        self.Week = int(len(self.T) / 7)
        self.demand    = DemandDF
        self.model     = gu.Model("CompactExact")
        self.Days_Off  = DAYS_OFF
        self.F_S       = F_S
        self.Min_WD_i  = Min_WD_i
        self.Max_WD_i  = Max_WD_i

        # Per-worker parameters from worker groups
        self.chi_by_worker    = {}
        self.gamma_C_by_worker = {}
        self.gamma_R_by_worker = {}
        self.alpha_R_by_worker = {}
        self.e_max_by_worker  = {}
        self.delta_by_worker  = {}
        for group in worker_groups.values():
            for w in group.worker_ids:
                self.chi_by_worker[w]     = group.chi
                self.gamma_C_by_worker[w] = group.gamma_C
                self.gamma_R_by_worker[w] = group.gamma_R
                self.alpha_R_by_worker[w] = group.alpha_R
                self.e_max_by_worker[w]   = group.e_max
                self.delta_by_worker[w]   = group.delta

    # ------------------------------------------------------------------
    # Precompute H-state transitions (no K_max needed)
    # ------------------------------------------------------------------
    def _precompute_group(self, chi, gamma_C, gamma_R, alpha_R, e_max, delta, H_max):
        S = self.K

        H_states = [(0, 0)]
        for rho in range(1, H_max + 1):
            H_states.append((rho, 0))
        for nu in range(1, H_max + 1):
            H_states.append((0, nu))
        H_idx = {state: idx for idx, state in enumerate(H_states)}
        n_h   = len(H_states)

        T_chg   = [(s, sp) for s in S for sp in S if s != sp]
        T_same  = [('same',  s) for s in S]
        T_first = [('first', s) for s in S]
        T_off   = [('off',)]
        transitions = T_chg + T_same + T_first + T_off

        n_chg         = len(T_chg)
        n_same        = len(T_same)
        tau_chg_idx   = set(range(n_chg))
        tau_first_idx = set(range(n_chg + n_same, n_chg + n_same + len(T_first)))
        n_tau         = len(transitions)

        def C_func(nu):
            if nu <= 0: return 0.0
            return nu ** gamma_C - (nu - 1) ** gamma_C

        def R_func(rho):
            if rho < chi: return 0.0
            return alpha_R * ((rho - chi + 1) ** gamma_R - (rho - chi) ** gamma_R)

        # Exact (unclamped) delta_e and successor h-state per arc (h_i, tau_i)
        delta_e  = {}   # (h_i, tau_i) -> exact change in e (before clamping)
        gamma_H  = {}   # (h_i, tau_i) -> successor h-index

        for h_i, (rho_h, nu_h) in enumerate(H_states):
            for tau_i, tau in enumerate(transitions):
                if tau_i in tau_chg_idx:
                    rho_plus = 0
                    nu_plus  = min(nu_h + 1, H_max)
                    s, sp    = tau
                    de       = float(delta[s, sp]) * C_func(nu_plus)
                else:
                    rho_plus = min(rho_h + 1, H_max)
                    nu_plus  = 0
                    de       = -R_func(rho_plus)

                gamma_H[(h_i, tau_i)]  = H_idx[(rho_plus, nu_plus)]
                delta_e[(h_i, tau_i)]  = de

        # Reverse lookup h' -> list of (h_i, tau_i) arcs
        h_sources = {}
        for h_i in range(n_h):
            for tau_i in range(n_tau):
                hp = gamma_H[(h_i, tau_i)]
                h_sources.setdefault(hp, []).append((h_i, tau_i))

        return {
            'H_states':       H_states,
            'n_h':            n_h,
            'transitions':    transitions,
            'n_tau':          n_tau,
            'tau_chg_idx':    tau_chg_idx,
            'tau_first_idx':  tau_first_idx,
            'T_chg':          T_chg,
            'T_same':         T_same,
            'T_first':        T_first,
            'delta_e':        delta_e,
            'gamma_H':        gamma_H,
            'h_sources':      h_sources,
            'e_max':          e_max,
        }

    # ------------------------------------------------------------------
    # Build model
    # ------------------------------------------------------------------
    def buildModel(self):
        self.t0 = time.time()
        self._generateVariables()
        self._genGenCons()
        self._genChangesCons()
        self._nlPerformanceExact()
        self._genRegConsIndividual()
        self._generateObjective()
        self.model.update()

    def _generateVariables(self):
        self.x   = self.model.addVars(self.I, self.T, self.K, vtype=gu.GRB.BINARY,     name="x")
        self.y   = self.model.addVars(self.I, self.T, vtype=gu.GRB.BINARY,             name="y")
        self.u   = self.model.addVars(self.T, self.K, lb=0, vtype=gu.GRB.CONTINUOUS,   name="u")
        self.o   = self.model.addVars(self.I, self.T, self.K, vtype=gu.GRB.BINARY,     name="o")
        self.z   = self.model.addVars(self.I, self.T, self.K, vtype=gu.GRB.BINARY,     name="z")
        self.l   = self.model.addVars(self.I, self.T, vtype=gu.GRB.BINARY,             name="l")
        self.c   = self.model.addVars(self.I, self.T, vtype=gu.GRB.BINARY,             name="c")
        self.p   = self.model.addVars(self.I, self.T, vtype=gu.GRB.CONTINUOUS, lb=0, ub=1, name="p")
        self.psh = self.model.addVars(self.I, self.T, self.K, vtype=gu.GRB.CONTINUOUS, lb=0, ub=1, name="psh")
        self.model.update()

    def _genGenCons(self):
        for t in self.T:
            for k in self.K:
                self.model.addLConstr(
                    gu.quicksum(self.psh[i, t, k] for i in self.I) + self.u[t, k] >= self.demand[t, k])
        for i in self.I:
            for t in self.T:
                self.model.addLConstr(gu.quicksum(self.x[i, t, k] for k in self.K) == self.y[i, t])
                for k in self.K:
                    self.model.addLConstr(self.psh[i, t, k] >= self.x[i, t, k] + self.p[i, t] - 1)
                    self.model.addLConstr(self.psh[i, t, k] <= self.p[i, t])
                    self.model.addLConstr(self.psh[i, t, k] <= self.x[i, t, k])
        self.model.update()

    def _genChangesCons(self):
        for i in self.I:
            for k in self.K:
                self.model.addLConstr(self.o[i, 1, k] == 0)
            self.model.addLConstr(self.l[i, 1] == 1)
            for t in range(2, len(self.T) + 1):
                for k in self.K:
                    self.model.addLConstr(self.o[i, t, k] == self.x[i, t - 1, k] + self.z[i, t - 1, k])
                self.model.addLConstr(self.l[i, t] <= self.l[i, t - 1])
                self.model.addLConstr(self.l[i, t] <= 1 - self.y[i, t - 1])
                self.model.addLConstr(self.l[i, t] >= self.l[i, t - 1] + (1 - self.y[i, t - 1]) - 1)
            for t in self.T:
                for k in self.K:
                    self.model.addLConstr(self.z[i, t, k] <= self.o[i, t, k])
                    self.model.addLConstr(self.z[i, t, k] <= 1 - self.y[i, t])
                    self.model.addLConstr(self.z[i, t, k] >= self.o[i, t, k] + (1 - self.y[i, t]) - 1)
        self.model.update()

    # ------------------------------------------------------------------
    # Exact performance tracking via continuous e_{i,d} + GenConstrs
    # ------------------------------------------------------------------
    def _nlPerformanceExact(self):
        H_MAX = len(self.T)

        # Cache group data per unique parameter combo
        group_cache = {}
        worker_gd   = {}
        for i in self.I:
            key = (self.chi_by_worker[i], self.gamma_C_by_worker[i],
                   self.gamma_R_by_worker[i], self.alpha_R_by_worker[i],
                   self.e_max_by_worker[i], id(self.delta_by_worker[i]))
            if key not in group_cache:
                group_cache[key] = self._precompute_group(
                    self.chi_by_worker[i], self.gamma_C_by_worker[i],
                    self.gamma_R_by_worker[i], self.alpha_R_by_worker[i],
                    self.e_max_by_worker[i], self.delta_by_worker[i], H_MAX)
            worker_gd[i] = group_cache[key]

        # Continuous performance loss state: e[i,d] in [0, e_max], d=0..T
        self.e_state  = {}   # e[i, d]  — d=0 is initial (=0)
        self.e_temp   = {}   # unclamped e before applying [0, e_max]
        self.e_clamp0 = {}   # after lower clamp (max(0, e_temp))
        self.clamp_lo = {}   # binary indicator: lower clamp at 0 active (e_temp >= 0)
        self.clamp_hi = {}   # binary indicator: upper clamp at e_max active
        self.w_h      = {}   # w_h[i, d, h]: h-state indicator
        self.g_h      = {}   # g_h[i, d, h, tau]: arc variable

        for i in self.I:
            gd    = worker_gd[i]
            n_h   = gd['n_h']
            n_tau = gd['n_tau']
            e_max = gd['e_max']

            # e_{i,0} = 0 (initial)
            self.e_state[i, 0] = self.model.addVar(lb=0, ub=0, name=f"e_{i}_0")

            for d in range(0, len(self.T) + 1):
                for h in range(n_h):
                    self.w_h[i, d, h] = self.model.addVar(vtype=gu.GRB.BINARY, name=f"wh_{i}_{d}_{h}")

            for d in self.T:
                # e_{i,d}: continuous, clamped to [0, e_max]
                self.e_state[i, d]  = self.model.addVar(lb=0, ub=e_max, name=f"e_{i}_{d}")
                # Auxiliary: unclamped value
                self.e_temp[i, d]   = self.model.addVar(lb=-e_max, ub=2*e_max, name=f"etemp_{i}_{d}")
                # Auxiliary: after lower clamp max(0, e_temp)
                self.e_clamp0[i, d] = self.model.addVar(lb=0, ub=2*e_max, name=f"eclamp0_{i}_{d}")
                # Big-M indicator binaries for the two linearized clamps
                self.clamp_lo[i, d] = self.model.addVar(vtype=gu.GRB.BINARY, name=f"zlo_{i}_{d}")
                self.clamp_hi[i, d] = self.model.addVar(vtype=gu.GRB.BINARY, name=f"zhi_{i}_{d}")

                for h in range(n_h):
                    for tau in range(n_tau):
                        self.g_h[i, d, h, tau] = self.model.addVar(
                            vtype=gu.GRB.BINARY, name=f"gh_{i}_{d}_{h}_{tau}")

        self.model.update()

        for i in self.I:
            gd        = worker_gd[i]
            n_h       = gd['n_h']
            n_tau     = gd['n_tau']
            e_max     = gd['e_max']
            delta_e   = gd['delta_e']
            gamma_H   = gd['gamma_H']
            h_sources = gd['h_sources']
            tau_chg_idx   = gd['tau_chg_idx']
            tau_first_idx = gd['tau_first_idx']
            transitions   = gd['transitions']
            T_chg   = gd['T_chg']
            T_same  = gd['T_same']
            T_first = gd['T_first']

            # Initial h-state: w_h[i,0,0] = 1
            for h in range(n_h):
                self.model.addLConstr(self.w_h[i, 0, h] == (1 if h == 0 else 0))

            for d in self.T:
                # (1) Arc out: Σ_tau g_h[i,d,h,tau] = w_h[i,d-1,h]
                for h in range(n_h):
                    self.model.addLConstr(
                        gu.quicksum(self.g_h[i, d, h, tau] for tau in range(n_tau))
                        == self.w_h[i, d - 1, h])

                # (2) H-state update: w_h[i,d,h'] = Σ sources g_h[i,d,h,tau]
                for hp in range(n_h):
                    srcs = h_sources.get(hp, [])
                    self.model.addLConstr(
                        self.w_h[i, d, hp]
                        == gu.quicksum(self.g_h[i, d, h, tau] for (h, tau) in srcs))

                # (3) Exactly one h-state active
                self.model.addLConstr(
                    gu.quicksum(self.w_h[i, d, h] for h in range(n_h)) == 1)

                # (4) Exact unclamped e transition
                #     e_temp[i,d] = e[i,d-1] + Σ_{h,tau} delta_e(h,tau) * g_h[i,d,h,tau]
                self.model.addLConstr(
                    self.e_temp[i, d]
                    == self.e_state[i, d - 1]
                    + gu.quicksum(
                        delta_e[(h, tau)] * self.g_h[i, d, h, tau]
                        for h in range(n_h) for tau in range(n_tau)))

                # (5) Clamp to [0, e_max] via exact big-M linearization of the two
                #     clamps (Appendix eq:exact:clamp_lower_ge/le, clamp_upper_le/ge):
                #     e_clamp0 = max(0, e_temp)      → lower clamp, indicator clamp_lo
                #     e[i,d]   = min(e_max, e_clamp0) → upper clamp, indicator clamp_hi
                M = 2.0 * e_max
                zlo = self.clamp_lo[i, d]
                zhi = self.clamp_hi[i, d]
                # Lower clamp: e_clamp0 = max(e_temp, 0)
                self.model.addLConstr(self.e_clamp0[i, d] >= self.e_temp[i, d])
                self.model.addLConstr(self.e_clamp0[i, d] >= 0)
                self.model.addLConstr(self.e_clamp0[i, d] <= self.e_temp[i, d] + M * (1 - zlo))
                self.model.addLConstr(self.e_clamp0[i, d] <= M * zlo)
                # Upper clamp: e[i,d] = min(e_clamp0, e_max)
                self.model.addLConstr(self.e_state[i, d] <= self.e_clamp0[i, d])
                self.model.addLConstr(self.e_state[i, d] <= e_max)
                self.model.addLConstr(self.e_state[i, d] >= self.e_clamp0[i, d] - M * (1 - zhi))
                self.model.addLConstr(self.e_state[i, d] >= e_max - M * zhi)

                # (6) p[i,d] = 1 - e[i,d]
                self.model.addLConstr(self.p[i, d] == 1.0 - self.e_state[i, d])

                # (7) Tie arc transitions to scheduling variables
                #     shift-change arcs → c[i,d]=1, x[i,d,s']=1
                for tau_i, tau in enumerate(transitions):
                    t_var = gu.quicksum(self.g_h[i, d, h, tau_i] for h in range(n_h))
                    if tau_i in tau_chg_idx:
                        s, sp = tau
                        self.model.addLConstr(
                            t_var <= self.x[i, d, sp])
                        self.model.addLConstr(
                            t_var <= self.c[i, d])
                    elif tau_i in tau_first_idx:
                        _, s = tau
                        self.model.addLConstr(
                            t_var <= self.x[i, d, s])
                        self.model.addLConstr(
                            t_var <= self.l[i, d])
                    elif tau == ('off',):
                        self.model.addLConstr(
                            t_var <= 1 - self.y[i, d])
                    else:  # same
                        _, s = tau
                        self.model.addLConstr(
                            t_var <= self.x[i, d, s])

        self.model.update()

    def _genRegConsIndividual(self):
        for i in self.I:
            max_wd = self.Max_WD_i[i]
            min_wd = self.Min_WD_i[i]
            for t in range(1, len(self.T) - max_wd + 1):
                self.model.addLConstr(
                    gu.quicksum(self.y[i, u] for u in range(t, t + 1 + max_wd)) <= max_wd)
            for t in range(1, len(self.T) - min_wd + 1):
                self.model.addLConstr(
                    gu.quicksum(self.y[i, u] for u in range(t + 1, t + min_wd + 1)) >=
                    min_wd * (self.y[i, t + 1] - self.y[i, t]))
            if len(self.T) >= min_wd:
                self.model.addLConstr(
                    gu.quicksum(self.y[i, u] for u in range(1, 1 + min_wd)) >= min_wd * self.y[i, 1])
            for t in range(2, len(self.T) - self.Days_Off + 2):
                for s in range(t + 1, t + self.Days_Off):
                    self.model.addLConstr(1 + self.y[i, t] >= self.y[i, t - 1] + self.y[i, s])
            for k1, k2 in self.F_S:
                for t in range(1, len(self.T)):
                    self.model.addLConstr(self.x[i, t, k1] + self.x[i, t + 1, k2] <= 1)
        self.model.update()

    def _generateObjective(self):
        self.model.setObjective(
            gu.quicksum(self.u[t, k] for k in self.K for t in self.T),
            sense=gu.GRB.MINIMIZE)

    def solveModel(self):
        try:
            self.model.optimize()
        except gu.GurobiError as e:
            print(f'Gurobi error {e.errno}: {e}')
