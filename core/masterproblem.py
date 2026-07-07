import gurobipy as gu
import numpy as np
from Utils.metrics import calculate_gini, compute_autocorrelation
from .nonlinear_transitions import evaluate_schedule_nl



class MasterProblem:
    """
    Master Problem for Column Generation using LINEAR constraints.
    
    Performance values are treated as COEFFICIENTS (not variables) in the demand constraints.
    This allows proper column generation where new columns are added with fixed coefficients.
    """
    
    def __init__(self, df, Demand, max_iteration, current_iteration, last, nr, start, start_by_group=None, worker_groups=None):
        self.iteration = current_iteration
        self.max_iteration = max_iteration
        self.nurses = df['I'].dropna().astype(int).unique().tolist()
        self.days = df['T'].dropna().astype(int).unique().tolist()
        self.shifts = df['K'].dropna().astype(int).unique().tolist()
        self._current_iteration = current_iteration
        self.roster = [i for i in range(1, self.max_iteration + 2)]
        self.rosterinitial = [1]  # Initial roster has just one element
        self.demand = Demand
        self.model = gu.Model("MasterProblem")
        self.cons_demand = {}
        self.newvar = {}
        self.last_itr = last
        self.max_itr = max_iteration
        self.cons_lmbda = {}  # Per-group convexity constraints
        self.output_len = nr
        self.demand_values = [self.demand[key] for key in self.demand.keys()]
        self.start = start  # Default start values (backward compatibility)
        self.start_by_group = start_by_group  # Per-group start values
        
        # Worker groups configuration
        self.worker_groups = worker_groups
        if worker_groups is not None:
            # Group-based indexing: group_idx -> (group_name, group_size)
            self.group_info = {}
            for idx, (name, group) in enumerate(worker_groups.items(), start=1):
                self.group_info[idx] = {'name': name, 'size': len(group.worker_ids), 'worker_ids': group.worker_ids}
            self.n_groups = len(self.group_info)
        else:
            # Default: 1 group with all workers
            self.group_info = {1: {'name': 'all', 'size': len(self.nurses), 'worker_ids': self.nurses}}
            self.n_groups = 1
        
        # Track all added schedules: (group_idx, roster_idx) -> schedule dict
        self.all_schedules = {}
        # Track active rosters per group: {group_idx: [roster_indices]}
        self.active_roster_by_group = {g: [1] for g in self.group_info}
        self.active_roster = [1]  # Global roster list

    def buildModel(self):
        self.generateVariables()
        self.generateConstraints()
        self.model.update()
        self.generateObjective()
        self.model.update()

    def generateVariables(self):
        # Understaffing variables
        self.u = self.model.addVars(self.days, self.shifts, vtype=gu.GRB.CONTINUOUS, lb=0, name='u')
        
        # Lambda variables: lmbda[group_idx, roster_idx]
        # Initially create for all groups with roster index 1
        self.lmbda = {}
        for g in self.group_info:
            for r in self.rosterinitial:
                self.lmbda[g, r] = self.model.addVar(
                    vtype=gu.GRB.CONTINUOUS, lb=0, name=f'lmbda[{g},{r}]'
                )

    def generateConstraints(self):
        # Per-group convexity constraints: sum of lambdas for each group = group_size
        self.cons_lmbda = {}
        for g, info in self.group_info.items():
            self.cons_lmbda[g] = self.model.addConstr(
                gu.quicksum(self.lmbda[g, r] for r in self.rosterinitial) == info['size'],
                name=f"conv_g{g}"
            )
        
        # Demand constraints: LINEAR constraints with performance as coefficients
        for t in self.days:
            for s in self.shifts:
                # Initially, constraint is just: u[t,s] >= demand[t,s]
                # The lmbda terms will be added via setStartSolution and addColumn
                self.cons_demand[t, s] = self.model.addConstr(
                    self.u[t, s] >= self.demand[t, s],
                    name=f"demand({t},{s})"
                )

    def generateObjective(self):
        self.model.setObjective(
            gu.quicksum(self.u[t, s] for t in self.days for s in self.shifts),
            sense=gu.GRB.MINIMIZE
        )

    def getDuals_i(self):
        """Get dual for the per-group convexity constraints."""
        return {g: self.cons_lmbda[g].Pi for g in self.group_info}

    def getDuals_ts(self):
        """Get duals for demand constraints."""
        return {(t, s): self.cons_demand[t, s].Pi for t in self.days for s in self.shifts}

    def updateModel(self):
        self.model.update()

    def setStartSolution(self):
        """Set the initial solution coefficients for roster index 1.
        
        Uses per-group start values if available, otherwise uses default start values.
        Lambda[g,r] represents COUNT of workers in group g using roster r.
        Coefficient is just perf value - the count is embedded in the lambda variable.
        """
        if self.start_by_group is not None:
            # Use per-group start values
            for group_idx, info in self.group_info.items():
                group_name = info['name']
                if group_name in self.start_by_group:
                    perf = self.start_by_group[group_name]['perf']
                    for t in self.days:
                        for s in self.shifts:
                            if (t, s) in perf:
                                # Coefficient = just perf value (lambda carries the count)
                                coeff = perf[t, s]
                                self.model.chgCoeff(self.cons_demand[t, s], self.lmbda[group_idx, 1], coeff)
        else:
            # Backward compatible: use same start values for all groups
            for group_idx, info in self.group_info.items():
                for t in self.days:
                    for s in self.shifts:
                        if (t, s) in self.start:
                            coeff = self.start[t, s]
                            self.model.chgCoeff(self.cons_demand[t, s], self.lmbda[group_idx, 1], coeff)
        self.model.update()

    def addColumn(self, itr, schedule, group_idx=None):
        """
        Add a new column (schedule) to the master problem.
        
        Args:
            itr: Iteration number (column index will be itr + 1)
            schedule: Dictionary {(day, shift, roster_idx): performance_value}
            group_idx: Group index for this column. If None, applies to all groups.
        
        The coefficient for each lambda is just the perf value.
        Lambda[g,r] carries the COUNT of workers using that roster.
        """
        roster_idx = itr + 1
        
        # Determine which groups this column applies to
        groups = [group_idx] if group_idx is not None else list(self.group_info.keys())
        
        for g in groups:
            # Store the schedule
            self.all_schedules[(g, roster_idx)] = schedule
            
            # Build the column coefficients for each constraint
            for t in self.days:
                for s in self.shifts:
                    # Get the performance coefficient for this (day, shift, roster_idx)
                    coeff = schedule.get((t, s, roster_idx), 0.0)
                    if coeff > 0:
                        # Coefficient = just perf value (lambda carries the count)
                        self.model.chgCoeff(self.cons_demand[t, s], self.lmbda[g, roster_idx], coeff)
        
        self.model.update()

    def addLambda(self, itr, group_idx=None, extra_cost=0.0):
        """
        Add a new lambda variable for the given iteration.

        Args:
            itr: Iteration number (roster index will be itr + 1)
            group_idx: Group index for this lambda. If None, creates for all groups.
            extra_cost: Fixed per-column objective coefficient (e.g. the fairness
                penalty lambda*|F_v-Fbar| or preference penalty lambda_P*sum(y_id)
                of this specific schedule). Must match the pricing SP's reduced-cost
                formula so master and subproblem optimize the same combined objective.
        """
        roster_idx = itr + 1

        # Determine which groups this lambda applies to
        groups = [group_idx] if group_idx is not None else list(self.group_info.keys())

        for g in groups:
            # Create new lambda variable
            self.lmbda[g, roster_idx] = self.model.addVar(
                vtype=gu.GRB.CONTINUOUS, lb=0, obj=extra_cost, name=f'lmbda[{g},{roster_idx}]'
            )
            
            # Track active roster for this group
            if g not in self.active_roster_by_group:
                self.active_roster_by_group[g] = []
            self.active_roster_by_group[g].append(roster_idx)
            
            # Add to per-group convexity constraint
            self.model.chgCoeff(self.cons_lmbda[g], self.lmbda[g, roster_idx], 1.0)
        
        # Track in global active_roster
        if roster_idx not in self.active_roster:
            self.active_roster.append(roster_idx)
        
        self.model.update()

    def printLambdas(self):
        """Get lambda values by roster index (summed across all groups).
        
        Returns dict: {roster_idx: total workers using this roster}
        This maintains backward compatibility with plotPerformanceList.
        """
        vals = {}
        for r in self.active_roster:
            roster_sum = 0
            for g in self.group_info:
                if (g, r) in self.lmbda:
                    roster_sum += round(self.lmbda[g, r].X)
            if roster_sum > 0:
                vals[r] = roster_sum
        return vals

    def printLambdasPool(self):
        """Like printLambdas, but reads the currently selected pool solution (.Xn)
        instead of the incumbent (.X). Set model.Params.SolutionNumber first."""
        vals = {}
        for r in self.active_roster:
            roster_sum = 0
            for g in self.group_info:
                if (g, r) in self.lmbda:
                    roster_sum += round(self.lmbda[g, r].Xn)
            if roster_sum > 0:
                vals[r] = roster_sum
        return vals

    def finalSolve(self, timeLimit):
        try:
            self.model.Params.IntegralityFocus = 1
            self.model.Params.FeasibilityTol = 1e-6
            self.model.Params.BarConvTol = 0.0
            self.model.Params.MIPGap = 0.05
            self.model.Params.OutputFlag = 1
            self.model.Params.TimeLimit = timeLimit
            
            # Set lambda variables to integer (per-group indexing)
            for g in self.group_info:
                rosters = self.active_roster_by_group.get(g, [1])
                for r in rosters:
                    if (g, r) in self.lmbda:
                        self.lmbda[g, r].VType = gu.GRB.INTEGER
            
            self.model.update()
            self.model.optimize()
            
            if self.model.status == gu.GRB.OPTIMAL:
                print("*" * (self.output_len + 2))
                print("*{:^{output_len}}*".format("***** Integer solution found *****", output_len=self.output_len))
                print("*" * (self.output_len + 2))
            else:
                print("*" * (self.output_len + 2))
                print("*{:^{output_len}}*".format("***** No solution found *****", output_len=self.output_len))
                print("*" * (self.output_len + 2))
        except gu.GurobiError as e:
            print('Error code ' + str(e.errno) + ': ' + str(e))

    def solveModel(self, timeLimit):
        try:
            self.model.setParam('TimeLimit', timeLimit)
            self.model.Params.OutputFlag = 0
            self.model.Params.IntegralityFocus = 1
            self.model.Params.FeasibilityTol = 1e-7
            self.model.Params.BarConvTol = 0.0
            self.model.Params.MIPGap = 1e-5
            self.model.setParam('ConcurrentMIP', 2)
            self.model.optimize()
        except gu.GurobiError as e:
            print('Error code ' + str(e.errno) + ': ' + str(e))

    def solveRelaxModel(self):
        try:
            self.model.Params.OutputFlag = 0
            self.model.Params.MIPGap = 1e-6
            self.model.Params.Method = 2
            self.model.Params.Crossover = 0
            
            # Ensure all variables are continuous
            for v in self.model.getVars():
                v.VType = gu.GRB.CONTINUOUS
                v.LB = 0.0
            
            self.model.optimize()
        except gu.GurobiError as e:
            print('Error code ' + str(e.errno) + ': ' + str(e))

    def decoy_f(self):
        return None

    def branch_var(self):
        if self.model.status != gu.GRB.OPTIMAL:
            raise Exception("Master problem could not find an optimal solution.")

        lambda_vars = self.model.getVars()

        max_frac = 0
        most_frac_var = None
        for var in lambda_vars:
            try:
                if 'lmbda' in var.VarName:
                    frac = abs(var.X - round(var.X))
                    if frac > max_frac:
                        max_frac = frac
                        most_frac_var = var
            except Exception:
                pass
        return most_frac_var

    def printSolution(self):
        for t in self.days:
            for s in self.shifts:
                print(f"u[{t},{s}] = {self.u[t, s].X}")

    def get_objective(self):
        return self.model.ObjVal

    def _final_metrics_package(self, uc, us, pl, co, scale):
        """Unified return structure for both calc methods."""
        n = len(self.nurses)
        return (
            round(uc, 6),
            round(us, 6),
            round(pl, 6),
            round(co, 6),
            round(co / (n * scale), 6),
            round(uc / (n * scale), 6),
            round(us / (n * scale), 6),
            round(pl / (n * scale), 6)
        )

    def calc_behavior(self, ls_perf, ls_sc, scale):
        """Calculate behavior metrics from performance values."""
        consistency = sum(ls_sc)
        
        # Expected length: n_workers * n_days * n_shifts
        expected_length = len(self.nurses) * len(self.days) * len(self.shifts)
        
        # Validate and fix length mismatch
        if len(ls_perf) != expected_length:
            if len(ls_perf) < expected_length:
                ls_perf = list(ls_perf) + [0.0] * (expected_length - len(ls_perf))
            else:
                ls_perf = ls_perf[:expected_length]
        
        # Paper-consistent decomposition (matches U^Inherent / U^Perf and the NPP/ECP path).
        # Per shift-day cell:  u^0_ds = max(0, Q_ds - sum_i x_ids)   (nominal headcount)
        #                      u_ds   = max(0, Q_ds - sum_i p_ids)   (effective performance)
        # U^Inherent = sum u^0_ds ;  U^Perf = sum (u_ds - u^0_ds) ;  U = U^Inherent + U^Perf.
        n_days = len(self.days)
        n_shifts = len(self.shifts)
        n_cells = n_days * n_shifts
        nominal_supply = [0.0] * n_cells
        effective_supply = [0.0] * n_cells
        for w in range(len(self.nurses)):
            base = w * n_cells
            for c in range(n_cells):
                p = ls_perf[base + c]
                if p > 0:
                    nominal_supply[c] += 1.0
                    effective_supply[c] += p
        understaffing = sum(max(0.0, self.demand_values[c] - nominal_supply[c]) for c in range(n_cells))
        undercoverage = sum(max(0.0, self.demand_values[c] - effective_supply[c]) for c in range(n_cells))
        perfloss = undercoverage - understaffing

        return self._final_metrics_package(undercoverage, understaffing, perfloss, consistency, scale)

    def calc_naive(self, lst, ls_sc, ls_r, scale, worker_groups=None):
        """Calculate metrics using naive (post-hoc) performance degradation."""
        if worker_groups is not None:
            return self._calc_naive_nl(lst, ls_sc, scale, worker_groups)
        
        consistency = sum(ls_sc)
        perf_ls = []
        n_nurses = len(self.nurses)
        
        sublist_length = len(lst) // n_nurses
        sublist_length_short = len(ls_sc) // n_nurses
        
        p_values = [lst[i * sublist_length:(i + 1) * sublist_length] for i in range(n_nurses)]
        sc_values2 = [ls_sc[i * sublist_length_short:(i + 1) * sublist_length_short] for i in range(n_nurses)]
        r_values2 = [ls_r[i * sublist_length_short:(i + 1) * sublist_length_short] for i in range(n_nurses)]
        x_values = [[1.0 if value > 0 else 0.0 for value in sublist] for sublist in p_values]
        
        u_results = sum(self.u[t, k].X for t in self.days for k in self.shifts)
        sum_xWerte = [sum(row[i] for row in x_values) for i in range(len(x_values[0]))]
        
        sum_all_doctors = 0
        cumulative_total = [0] * (len(self.days) * len(self.shifts))
        # Cell-wise (per worker, per day-shift-cell) performance, matching ls_x's layout
        # (see _calc_naive_nl for the same fix in the nonlinear/group-aware path).
        perf_cellwise = []

        comp_result = [0 if self.demand_values[i] < sum_xWerte[i] else 1 for i in range(len(self.demand_values))]

        for idx in range(n_nurses):
            doctor_values = sc_values2[idx]
            r_values = r_values2[idx]
            x_i_values = x_values[idx]

            cumulative_sum = [0]
            for i in range(1, len(doctor_values)):
                if r_values[i] == 1 and cumulative_sum[-1] > 0:
                    reduction = 1 if doctor_values[i] == 0 else 0
                    cumulative_sum.append(max(0, cumulative_sum[-1] - reduction))
                else:
                    cumulative_sum.append(cumulative_sum[-1] + doctor_values[i])

            perf_vals = [round(1 - (val * mue), 2) for val in cumulative_sum]
            perf_ls.extend(perf_vals)
            for p in perf_vals:
                perf_cellwise.extend([p] * len(self.shifts))

            multiplied = [ (val * mue) * x_i_values[j * len(self.shifts) + s] * comp_result[j * len(self.shifts) + s]
                          for j, val in enumerate(cumulative_sum) for s in range(len(self.shifts))]

            sum_all_doctors += sum(multiplied)
            cumulative_total = [cumulative_total[j] + multiplied[j] for j in range(len(cumulative_total))]

        metrics = self._final_metrics_package(u_results + sum_all_doctors, u_results, sum_all_doctors, consistency, scale)
        # NOTE: this linear (non-group) fallback path is currently never exercised by
        # loop_cg.py (worker_groups is always passed), so an exact cell-wise reconstruction
        # is not implemented here; the RMP's own nominal per-cell values are used as a
        # reasonable approximation should this path ever be invoked without worker_groups.
        undercover_cellwise = self.getUndercoverage()
        return (*metrics, perf_ls, cumulative_total, perf_cellwise, undercover_cellwise)

    def _calc_naive_nl(self, lst, ls_sc, scale, worker_groups):
        """Internal method for non-linear post-hoc evaluation using worker groups."""
        consistency = sum(ls_sc)
        perf_ls = []
        n_nurses = len(self.nurses)
        sublist_length = len(lst) // n_nurses
        
        # Track real supply per shift
        real_supply_per_shift = [0.0] * (len(self.days) * len(self.shifts))
        x_values = [1.0 if val > 0 else 0.0 for val in lst]

        worker_specs = {}
        for group in worker_groups.values():
            group_spec = {
                'epsilon': group.epsilon,
                'chi': group.chi,
                'gamma_R': group.gamma_R,
                'gamma_C': group.gamma_C,
                'alpha_R': group.alpha_R,
                'delta': group.delta,
                'e_max': group.e_max
            }
            for w in group.worker_ids:
                worker_specs[w] = group_spec

        all_workers_perf = []
        all_workers_x = []

        for idx, nurse in enumerate(self.nurses):
            try:
                w_id = int(str(nurse).replace("Physician_", "").replace("Nurse_", "").replace("Nurse", ""))
            except ValueError:
                w_id = idx + 1
                
            nl_spec = worker_specs.get(w_id, {
                'epsilon': 0.06, 'chi': 3, 'gamma_R': 0.5, 'gamma_C': 1.25,
                'alpha_R': 0.04, 'delta': np.zeros((4,4)), 'e_max': 1.0
            })
            if isinstance(nl_spec['delta'], np.ndarray) and np.all(nl_spec['delta'] == 0):
                from core.worker_groups import get_default_delta
                nl_spec['delta'] = get_default_delta(nl_spec['epsilon'])

            worker_x = x_values[idx * sublist_length : (idx + 1) * sublist_length]
            all_workers_x.append(worker_x)
            
            x_dict = {}
            for d_idx, day in enumerate(self.days):
                for s_idx, shift in enumerate(self.shifts):
                    if worker_x[d_idx * len(self.shifts) + s_idx] > 0.5:
                        x_dict[(day, shift)] = 1.0
            
            perf_hist, _, _, _, _, _ = evaluate_schedule_nl(x_dict, self.days, self.shifts, nl_spec)
            
            worker_perf_ls = []
            for d_idx, day in enumerate(self.days):
                p = perf_hist[day]
                worker_perf_ls.append(p)
                for s_idx, shift in enumerate(self.shifts):
                    i = d_idx * len(self.shifts) + s_idx
                    if worker_x[i] > 0.5:
                        real_supply_per_shift[i] += p
            perf_ls.extend(worker_perf_ls)
            all_workers_perf.append(worker_perf_ls)
            
        u_results = [max(0, self.demand_values[i] - real_supply_per_shift[i]) for i in range(len(self.demand_values))]
        total_undercoverage = sum(u_results)
        
        nominal_supply = [0.0] * (len(self.days) * len(self.shifts))
        for i in range(len(x_values)):
            if x_values[i] > 0.5:
                nominal_supply[i % len(nominal_supply)] += 1.0
        
        understaffing = sum(max(0, self.demand_values[i] - nominal_supply[i]) for i in range(len(self.demand_values)))
        perfloss = total_undercoverage - understaffing
        
        comp_result = [0 if self.demand_values[i] < nominal_supply[i] else 1 for i in range(len(self.demand_values))]
        cumulative_total = [0.0] * len(self.demand_values)
        # Cell-wise (per worker, per day-shift-cell) real nonlinear performance, matching
        # the layout of ls_x/ls_perf_ so downstream code (spread/gini/disutility on L_perf)
        # can zip it 1:1 instead of the day-level perf_ls (which is only n_days long per worker
        # and silently misaligns with the n_days*n_shifts-long ls_x when zipped).
        perf_cellwise = []

        for idx in range(n_nurses):
            worker_x = all_workers_x[idx]
            worker_perf = all_workers_perf[idx]
            multiplied = []
            for d_idx, p in enumerate(worker_perf):
                phi = 1.0 - p
                for s_idx in range(len(self.shifts)):
                    cell_idx = d_idx * len(self.shifts) + s_idx
                    val = phi * worker_x[cell_idx] * comp_result[cell_idx]
                    multiplied.append(val)
                    perf_cellwise.append(p)
            cumulative_total = [cumulative_total[j] + multiplied[j] for j in range(len(cumulative_total))]

        metrics = self._final_metrics_package(total_undercoverage, understaffing, perfloss, consistency, scale)
        # u_results is the cell-wise effective undercoverage (max(0, demand - real_supply)),
        # i.e. exactly what sums to total_undercoverage. Returning it directly avoids
        # reconstructing it downstream from cumulative_total + master.getUndercoverage(),
        # which mixes the performance-loss component of one schedule with the nominal
        # RMP-incumbent component of a possibly different (pool) schedule.
        return (*metrics, perf_ls, cumulative_total, perf_cellwise, u_results)



    def getUndercoverage(self):
        return [self.u[t, k].X for t in self.days for k in self.shifts]


# Keep legacy class for backward compatibility if needed
class MasterProblemQC(MasterProblem):
    """Legacy class name for backward compatibility."""
    pass
