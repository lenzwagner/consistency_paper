import gurobipy as gu
import math
import time
from core.base_case import DAYS_OFF, F_S


def _project_to_grid(phi_val, phi_k):
    """Project phi_val to nearest loss-grid index; conservative (round up on ties)."""
    best_idx = 0
    best_dist = abs(phi_val - phi_k[0])
    for idx, pk in enumerate(phi_k):
        dist = abs(phi_val - pk)
        if dist < best_dist or (dist == best_dist and idx > best_idx):
            best_dist = dist
            best_idx = idx
    return best_idx


class Problem:
    def __init__(self, dfData, DemandDF, Min_WD_i, Max_WD_i, worker_groups, K_max=10):
        self.I = dfData['I'].dropna().astype(int).unique().tolist()
        self.T = dfData['T'].dropna().astype(int).unique().tolist()
        self.K = dfData['K'].dropna().astype(int).unique().tolist()
        self.End = len(self.T)
        self.Week = int(len(self.T) / 7)
        self.Weeks = range(1, self.Week + 1)
        self.demand = DemandDF
        self.model = gu.Model("CompactModel")
        self.Days_Off = DAYS_OFF
        self.Days = len(self.T)
        self.demand_values = [self.demand[key] for key in self.demand.keys()]
        self.Min_WD_i = Min_WD_i
        self.Max_WD_i = Max_WD_i
        self.F_S = F_S
        self.K_max_disc = K_max               # loss-grid resolution

        # Per-worker parameters from worker groups
        self.chi_by_worker = {}
        self.gamma_C_by_worker = {}
        self.gamma_R_by_worker = {}
        self.alpha_R_by_worker = {}
        self.e_max_by_worker = {}
        self.delta_by_worker = {}
        for group in worker_groups.values():
            for w in group.worker_ids:
                self.chi_by_worker[w] = group.chi
                self.gamma_C_by_worker[w] = group.gamma_C
                self.gamma_R_by_worker[w] = group.gamma_R
                self.alpha_R_by_worker[w] = group.alpha_R
                self.e_max_by_worker[w] = group.e_max
                self.delta_by_worker[w] = group.delta

    def buildModel(self):
        self.t0 = time.time()
        self.generateVariables()
        self.genGenCons()           # model:demand:full, model:begin, model:perf1/2
        self.genChangesCons()       # model:q, model:z, model:z_pre, model:l1/2
        self.nlPerformanceDiscrete()# finite-state discretization (Appendix app:nonlinear:linearization)
        self.genRegConsIndividual() # Appendix app:reg:cons
        self.generateObjective()    # model:objective
        self.model.update()

    # ------------------------------------------------------------------
    # Variables
    # ------------------------------------------------------------------
    def generateVariables(self):
        # Core scheduling
        self.x   = self.model.addVars(self.I, self.T, self.K, vtype=gu.GRB.BINARY,     name="x")
        self.y   = self.model.addVars(self.I, self.T, vtype=gu.GRB.BINARY,             name="y")
        self.u   = self.model.addVars(self.T, self.K, lb=0, vtype=gu.GRB.CONTINUOUS,   name="u")
        # Shift-change tracking (model:q, model:z, model:l1/2)
        self.o   = self.model.addVars(self.I, self.T, self.K, vtype=gu.GRB.BINARY,     name="o")   # o_ids
        self.z   = self.model.addVars(self.I, self.T, self.K, vtype=gu.GRB.BINARY,     name="z")   # z_ids
        self.l   = self.model.addVars(self.I, self.T, vtype=gu.GRB.BINARY,             name="l")   # l_id
        self.c   = self.model.addVars(self.I, self.T, vtype=gu.GRB.BINARY,             name="c")   # c_id
        # Performance
        self.p   = self.model.addVars(self.I, self.T, vtype=gu.GRB.CONTINUOUS, lb=0, ub=1, name="p")    # p̄_id
        self.psh = self.model.addVars(self.I, self.T, self.K, vtype=gu.GRB.CONTINUOUS, lb=0, ub=1, name="psh")  # p_ids
        self.model.update()

    # ------------------------------------------------------------------
    # General constraints: model:demand:full, model:begin, model:perf1/2
    # ------------------------------------------------------------------
    def genGenCons(self):
        for t in self.T:
            for k in self.K:
                # model:demand:full
                self.model.addLConstr(
                    gu.quicksum(self.psh[i, t, k] for i in self.I) + self.u[t, k] >= self.demand[t, k])
        for i in self.I:
            for t in self.T:
                # model:begin
                self.model.addLConstr(gu.quicksum(self.x[i, t, k] for k in self.K) == self.y[i, t])
                for k in self.K:
                    # model:perf1: p_ids >= (x_ids - 1) + p̄_id
                    self.model.addLConstr(self.psh[i, t, k] >= self.x[i, t, k] + self.p[i, t] - 1)
                    # model:perf2 linearized: p_ids <= p̄_id, p_ids <= x_ids
                    self.model.addLConstr(self.psh[i, t, k] <= self.p[i, t])
                    self.model.addLConstr(self.psh[i, t, k] <= self.x[i, t, k])
        self.model.update()

    # ------------------------------------------------------------------
    # Shift-change detection: model:q, model:z, model:z_pre, model:l1/2
    # ------------------------------------------------------------------
    def genChangesCons(self):
        for i in self.I:
            # model:z_pre: o_{i1s} = 0
            for k in self.K:
                self.model.addLConstr(self.o[i, 1, k] == 0)

            # model:l1: l_{i1} = 1
            self.model.addLConstr(self.l[i, 1] == 1)

            for t in range(2, len(self.T) + 1):
                # model:q: o_ids = x_{i(d-1)s} + z_{i(d-1)s}
                for k in self.K:
                    self.model.addLConstr(self.o[i, t, k] == self.x[i, t - 1, k] + self.z[i, t - 1, k])

                # model:l2 linearized: l_id = l_{i(d-1)} * (1 - y_{i(d-1)})
                self.model.addLConstr(self.l[i, t] <= self.l[i, t - 1])
                self.model.addLConstr(self.l[i, t] <= 1 - self.y[i, t - 1])
                self.model.addLConstr(self.l[i, t] >= self.l[i, t - 1] + (1 - self.y[i, t - 1]) - 1)

            for t in self.T:
                for k in self.K:
                    # model:z linearized: z_ids = o_ids * (1 - y_id)
                    self.model.addLConstr(self.z[i, t, k] <= self.o[i, t, k])
                    self.model.addLConstr(self.z[i, t, k] <= 1 - self.y[i, t])
                    self.model.addLConstr(self.z[i, t, k] >= self.o[i, t, k] + (1 - self.y[i, t]) - 1)

        self.model.update()

    # ------------------------------------------------------------------
    # Precompute finite-state transition maps for one worker group
    # (Appendix app:nonlinear:linearization)
    # ------------------------------------------------------------------
    def _precompute_group(self, chi, gamma_C, gamma_R, alpha_R, e_max, delta, K_max, H_max):
        S = self.K  # shift indices (1-indexed)

        # Loss grid: uniform on [0, e_max]
        phi_k    = [e_max * k / K_max for k in range(K_max + 1)]
        p_tilde  = [1.0 - phi for phi in phi_k]

        # History-state enumeration: (rho, nu) with rho * nu = 0
        # (0,0): start; (rho>0, 0): stable; (0, nu>0): change-spell
        H_states = [(0, 0)]
        for rho in range(1, H_max + 1):
            H_states.append((rho, 0))
        for nu in range(1, H_max + 1):
            H_states.append((0, nu))
        H_idx = {state: idx for idx, state in enumerate(H_states)}
        n_h   = len(H_states)

        # Transition class enumeration
        T_chg   = [(s, sp) for s in S for sp in S if s != sp]  # directed changes
        T_same  = [('same',  s) for s in S]                    # σ_s
        T_first = [('first', s) for s in S]                    # ι_s
        T_off   = [('off',)]                                    # ω
        transitions = T_chg + T_same + T_first + T_off

        n_chg   = len(T_chg)
        n_same  = len(T_same)
        n_first = len(T_first)
        tau_chg_idx   = set(range(n_chg))
        tau_same_idx  = set(range(n_chg, n_chg + n_same))
        tau_first_idx = set(range(n_chg + n_same, n_chg + n_same + n_first))
        tau_off_idx   = len(transitions) - 1
        n_tau         = len(transitions)

        # C(nu; gamma_C) = nu^gamma_C - (nu-1)^gamma_C
        def C_func(nu):
            if nu <= 0:
                return 0.0
            return nu ** gamma_C - (nu - 1) ** gamma_C

        # R(rho; gamma_R) = alpha_R * [(rho-chi+1)^gamma_R - (rho-chi)^gamma_R]  for rho >= chi
        def R_func(rho):
            if rho < chi:
                return 0.0
            return alpha_R * ((rho - chi + 1) ** gamma_R - (rho - chi) ** gamma_R)

        # Precompute Gamma_F[(k, h_idx, tau_idx)] and Gamma_H[(h_idx, tau_idx)]
        gamma_F = {}
        gamma_H = {}

        for h_i, (rho_h, nu_h) in enumerate(H_states):
            for tau_i, tau in enumerate(transitions):
                # Successor counters (eq:nl_rho_successor, eq:nl_nu_successor)
                if tau_i in tau_chg_idx:
                    rho_plus = 0
                    nu_plus  = min(nu_h + 1, H_max)
                else:
                    rho_plus = min(rho_h + 1, H_max)
                    nu_plus  = 0

                gamma_H[(h_i, tau_i)] = H_idx[(rho_plus, nu_plus)]

                # Loss update per k (eq:nl_loss_update_cases)
                for k in range(K_max + 1):
                    if tau_i in tau_chg_idx:
                        s, sp     = tau
                        delta_val = float(delta[s, sp])
                        C_val     = C_func(nu_plus)
                        phi_new   = min(e_max, phi_k[k] + delta_val * C_val)
                    elif rho_plus >= chi:
                        R_val   = R_func(rho_plus)
                        phi_new = max(0.0, phi_k[k] - R_val)
                    else:
                        phi_new = phi_k[k]

                    gamma_F[(k, h_i, tau_i)] = _project_to_grid(phi_new, phi_k)

        # Reverse lookup: (k', h') -> list of (k, h_i, tau_i) arcs leading there
        w_sources = {}
        for k in range(K_max + 1):
            for h_i in range(n_h):
                for tau_i in range(n_tau):
                    kp = gamma_F[(k, h_i, tau_i)]
                    hp = gamma_H[(h_i, tau_i)]
                    w_sources.setdefault((kp, hp), []).append((k, h_i, tau_i))

        return {
            'K_max':          K_max,
            'H_max':          H_max,
            'H_states':       H_states,
            'H_idx':          H_idx,
            'n_h':            n_h,
            'transitions':    transitions,
            'n_tau':          n_tau,
            'tau_chg_idx':    tau_chg_idx,
            'tau_same_idx':   tau_same_idx,
            'tau_first_idx':  tau_first_idx,
            'tau_off_idx':    tau_off_idx,
            'T_chg':          T_chg,
            'T_same':         T_same,
            'T_first':        T_first,
            'phi_k':          phi_k,
            'p_tilde':        p_tilde,
            'gamma_F':        gamma_F,
            'gamma_H':        gamma_H,
            'w_sources':      w_sources,
        }

    # ------------------------------------------------------------------
    # Finite-state discretization: eq:nl_performance_lookup,
    # eq:nl_arc_out, eq:nl_arc_class, eq:nl_state_update,
    # eq:nl_transition_change1/2, eq:nl_transition_same/first/unique
    # ------------------------------------------------------------------
    def nlPerformanceDiscrete(self):
        K_MAX = self.K_max_disc
        H_MAX = len(self.T)  # cap both rho and nu counters at horizon length

        # Precompute transition maps per group (cached by parameter fingerprint)
        group_cache  = {}
        worker_gd    = {}
        for i in self.I:
            key = (self.chi_by_worker[i],
                   round(self.gamma_C_by_worker[i], 12),
                   round(self.gamma_R_by_worker[i], 12),
                   round(self.alpha_R_by_worker[i], 12),
                   round(self.e_max_by_worker[i],   12))
            if key not in group_cache:
                group_cache[key] = self._precompute_group(
                    self.chi_by_worker[i],
                    self.gamma_C_by_worker[i],
                    self.gamma_R_by_worker[i],
                    self.alpha_R_by_worker[i],
                    self.e_max_by_worker[i],
                    self.delta_by_worker[i],
                    K_MAX, H_MAX)
            worker_gd[i] = group_cache[key]

        # MIP variables: w_state, g_arc, t_trans (stored as Python dicts)
        self.w_state = {}   # (i, d, k, h)       d = 0..T
        self.g_arc   = {}   # (i, d, k, h, tau)  d in T
        self.t_trans = {}   # (i, d, tau)         d in T

        for i in self.I:
            gd    = worker_gd[i]
            K_max = gd['K_max']
            n_h   = gd['n_h']
            n_tau = gd['n_tau']

            # w[i, d, k, h] for d = 0..T (d=0 is initialization, not a planning day)
            for d in range(0, len(self.T) + 1):
                for k in range(K_max + 1):
                    for h in range(n_h):
                        self.w_state[i, d, k, h] = self.model.addVar(
                            vtype=gu.GRB.BINARY, name=f"w_{i}_{d}_{k}_{h}")

            # g[i, d, k, h, tau] and t[i, d, tau] for d in T
            for d in self.T:
                for k in range(K_max + 1):
                    for h in range(n_h):
                        for tau in range(n_tau):
                            self.g_arc[i, d, k, h, tau] = self.model.addVar(
                                vtype=gu.GRB.BINARY, name=f"g_{i}_{d}_{k}_{h}_{tau}")
                for tau in range(n_tau):
                    self.t_trans[i, d, tau] = self.model.addVar(
                        vtype=gu.GRB.BINARY, name=f"t_{i}_{d}_{tau}")

        self.model.update()

        # Initialization: w[i, 0, 0, 0] = 1, all others = 0
        for i in self.I:
            gd    = worker_gd[i]
            K_max = gd['K_max']
            n_h   = gd['n_h']
            for k in range(K_max + 1):
                for h in range(n_h):
                    rhs = 1 if (k == 0 and h == 0) else 0
                    self.model.addConstr(self.w_state[i, 0, k, h] == rhs)

        for i in self.I:
            gd          = worker_gd[i]
            K_max       = gd['K_max']
            n_h         = gd['n_h']
            n_tau       = gd['n_tau']
            transitions = gd['transitions']
            tau_chg     = gd['tau_chg_idx']
            tau_same    = gd['tau_same_idx']
            tau_first   = gd['tau_first_idx']
            tau_off     = gd['tau_off_idx']
            gamma_F     = gd['gamma_F']
            gamma_H     = gd['gamma_H']
            w_sources   = gd['w_sources']
            p_tilde     = gd['p_tilde']

            for d in self.T:
                # --- Transition class linking constraints (eqs 90–94) ---

                # eq:nl_transition_change1/2: t_{id,ss'} ↔ o_{ids} ∧ x_{ids'} ∧ ¬l_{id}
                for tau_i in sorted(tau_chg):
                    s, sp  = transitions[tau_i]
                    t_var  = self.t_trans[i, d, tau_i]
                    self.model.addConstr(t_var <= self.o[i, d, s])
                    self.model.addConstr(t_var <= self.x[i, d, sp])
                    self.model.addConstr(t_var <= 1 - self.l[i, d])
                    self.model.addConstr(
                        t_var >= self.o[i, d, s] + self.x[i, d, sp] - self.l[i, d] - 1)

                # eq:nl_transition_same: t_{id,σ_s} ↔ o_{ids} ∧ x_{ids}
                for tau_i in sorted(tau_same):
                    _, s  = transitions[tau_i]
                    t_var = self.t_trans[i, d, tau_i]
                    self.model.addConstr(t_var <= self.o[i, d, s])
                    self.model.addConstr(t_var <= self.x[i, d, s])
                    self.model.addConstr(t_var >= self.o[i, d, s] + self.x[i, d, s] - 1)

                # eq:nl_transition_first: t_{id,ι_s} ↔ l_{id} ∧ x_{ids}
                for tau_i in sorted(tau_first):
                    _, s  = transitions[tau_i]
                    t_var = self.t_trans[i, d, tau_i]
                    self.model.addConstr(t_var <= self.l[i, d])
                    self.model.addConstr(t_var <= self.x[i, d, s])
                    self.model.addConstr(t_var >= self.l[i, d] + self.x[i, d, s] - 1)

                # eq:nl_transition_unique: t_{id,ω} = 1 - y_{id},  Σ_τ t_{idτ} = 1
                self.model.addConstr(self.t_trans[i, d, tau_off] == 1 - self.y[i, d])
                self.model.addConstr(
                    gu.quicksum(self.t_trans[i, d, tau] for tau in range(n_tau)) == 1)

                # model:diragg: c_{id} = Σ_{s≠s'} t_{id,ss'}
                self.model.addConstr(
                    self.c[i, d] == gu.quicksum(
                        self.t_trans[i, d, tau] for tau in sorted(tau_chg)))

                # --- Arc-flow constraints (eqs 100–102) ---

                # eq:nl_arc_out: Σ_τ g_{idkhτ} = w_{i(d-1)kh}
                for k in range(K_max + 1):
                    for h in range(n_h):
                        self.model.addConstr(
                            gu.quicksum(self.g_arc[i, d, k, h, tau] for tau in range(n_tau))
                            == self.w_state[i, d - 1, k, h])

                # eq:nl_arc_class: Σ_{k,h} g_{idkhτ} = t_{idτ}
                for tau in range(n_tau):
                    self.model.addConstr(
                        gu.quicksum(self.g_arc[i, d, k, h, tau]
                                    for k in range(K_max + 1) for h in range(n_h))
                        == self.t_trans[i, d, tau])

                # eq:nl_state_update: w_{idk'h'} = Σ_{k,h,τ: Γ_F=k', Γ_H=h'} g_{idkhτ}
                for kp in range(K_max + 1):
                    for hp in range(n_h):
                        sources = w_sources.get((kp, hp), [])
                        self.model.addConstr(
                            self.w_state[i, d, kp, hp]
                            == gu.quicksum(self.g_arc[i, d, k, h, tau]
                                           for k, h, tau in sources))

                # eq:nl_performance_lookup: Σ_{k,h} w_{idkh} = 1, p̄_{id} = Σ_{k,h} p̃_k w_{idkh}
                self.model.addConstr(
                    gu.quicksum(self.w_state[i, d, k, h]
                                for k in range(K_max + 1) for h in range(n_h)) == 1)
                self.model.addConstr(
                    self.p[i, d] == gu.quicksum(
                        p_tilde[k] * self.w_state[i, d, k, h]
                        for k in range(K_max + 1) for h in range(n_h)))

        self.model.update()

    # ------------------------------------------------------------------
    # Regulatory constraints (Appendix app:reg:cons) — individual bounds
    # ------------------------------------------------------------------
    def genRegConsIndividual(self):
        for i in self.I:
            max_wd = self.Max_WD_i[i]
            min_wd = self.Min_WD_i[i]
            # Max consecutive working days
            for t in range(1, len(self.T) - max_wd + 1):
                self.model.addLConstr(
                    gu.quicksum(self.y[i, u] for u in range(t, t + 1 + max_wd)) <= max_wd)
            # Min consecutive working days
            for t in range(1, len(self.T) - min_wd + 1):
                self.model.addLConstr(
                    gu.quicksum(self.y[i, u] for u in range(t + 1, t + min_wd + 1)) >=
                    min_wd * (self.y[i, t + 1] - self.y[i, t]))
            if len(self.T) >= min_wd:
                self.model.addLConstr(
                    gu.quicksum(self.y[i, u] for u in range(1, 1 + min_wd)) >= min_wd * self.y[i, 1])
            # Min consecutive days off
            for t in range(2, len(self.T) - self.Days_Off + 2):
                for s in range(t + 1, t + self.Days_Off):
                    self.model.addLConstr(1 + self.y[i, t] >= self.y[i, t - 1] + self.y[i, s])
            # Forbidden consecutive shift pairs (forward rotation)
            for k1, k2 in self.F_S:
                for t in range(1, len(self.T)):
                    self.model.addLConstr(self.x[i, t, k1] + self.x[i, t + 1, k2] <= 1)
        self.model.update()

    def generateObjective(self):
        self.model.setObjective(
            gu.quicksum(self.u[t, k] for k in self.K for t in self.T),
            sense=gu.GRB.MINIMIZE)

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
        d = self.model.getAttr("X", self.x)
        lst = list(d.values())
        return [0.0 if x == -0.0 else x for x in lst]
