import gurobipy as gu
import numpy as np
from Utils.metrics import calculate_gini, compute_autocorrelation
from nonlinear_transitions import evaluate_schedule_nl


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

    def addLambda(self, itr, group_idx=None):
        """
        Add a new lambda variable for the given iteration.
        
        Args:
            itr: Iteration number (roster index will be itr + 1)
            group_idx: Group index for this lambda. If None, creates for all groups.
        """
        roster_idx = itr + 1
        
        # Determine which groups this lambda applies to
        groups = [group_idx] if group_idx is not None else list(self.group_info.keys())
        
        for g in groups:
            # Create new lambda variable
            self.lmbda[g, roster_idx] = self.model.addVar(
                vtype=gu.GRB.CONTINUOUS, lb=0, name=f'lmbda[{g},{roster_idx}]'
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
            round(uc, 5), 
            round(us, 5), 
            round(pl, 5), 
            round(co, 5), 
            round(co / (n * scale), 5),
            round(uc / (n * scale), 5),
            round(us / (n * scale), 5),
            round(pl / (n * scale), 5)
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
        
        perfloss = round(sum(1.0 - p for p in ls_perf if p > 0), 5)
        undercoverage = round(sum(self.u[t, k].X for t in self.days for k in self.shifts), 3)
        understaffing = round(max(0, undercoverage - perfloss), 5)

        return self._final_metrics_package(undercoverage, understaffing, perfloss, consistency, scale)

    def calc_naive(self, lst, ls_sc, ls_r, mue, scale, nl_spec=None):
        """Calculate metrics using naive (post-hoc) performance degradation."""
        if nl_spec is not None:
            # Non-linear evaluation
            return self._calc_naive_nl(lst, ls_sc, mue, scale, nl_spec)
        
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
            
            multiplied = [ (val * mue) * x_i_values[j * len(self.shifts) + s] * comp_result[j * len(self.shifts) + s] 
                          for j, val in enumerate(cumulative_sum) for s in range(len(self.shifts))]
            
            sum_all_doctors += sum(multiplied)
            cumulative_total = [cumulative_total[j] + multiplied[j] for j in range(len(cumulative_total))]
        
        metrics = self._final_metrics_package(u_results + sum_all_doctors, u_results, sum_all_doctors, consistency, scale)
        return (*metrics, perf_ls, cumulative_total)

    def _calc_naive_nl(self, lst, ls_sc, mue, scale, nl_spec):
        """Internal method for non-linear post-hoc evaluation."""
        consistency = sum(ls_sc)
        perf_ls = []
        n_nurses = len(self.nurses)
        sublist_length = len(lst) // n_nurses
        
        # Track real supply per shift
        real_supply_per_shift = [0.0] * (len(self.days) * len(self.shifts))
        x_values = [1.0 if val > 0 else 0.0 for val in lst]

        for idx in range(n_nurses):
            worker_x = x_values[idx * sublist_length : (idx + 1) * sublist_length]
            
            # Create x_dict for evaluate_schedule_nl
            x_dict = {}
            for d_idx, day in enumerate(self.days):
                for s_idx, shift in enumerate(self.shifts):
                    if worker_x[d_idx * len(self.shifts) + s_idx] > 0.5:
                        x_dict[(day, shift)] = 1.0
            
            perf_hist, _, _, _ = evaluate_schedule_nl(x_dict, self.days, self.shifts, nl_spec)
            
            # Reconstruct performance list for return
            worker_perf_ls = []
            for d_idx, day in enumerate(self.days):
                p = perf_hist[day]
                worker_perf_ls.append(p)
                for s_idx, shift in enumerate(self.shifts):
                    i = d_idx * len(self.shifts) + s_idx
                    if worker_x[i] > 0.5:
                        real_supply_per_shift[i] += p
            perf_ls.extend(worker_perf_ls)
            
        # Real undercoverage = sum(max(0, demand - real_supply))
        u_results = [max(0, self.demand_values[i] - real_supply_per_shift[i]) for i in range(len(self.demand_values))]
        total_undercoverage = sum(u_results)
        
        # For compatibility with _final_metrics_package, we need to separate
        # understaffing (nominal missing) and perfloss (missing due to p < 1).
        # Understaffing = sum(max(0, demand - nominal_supply))
        nominal_supply = [0.0] * (len(self.days) * len(self.shifts))
        for i in range(len(x_values)):
            if x_values[i] > 0.5:
                nominal_supply[i % len(nominal_supply)] += 1.0
        
        understaffing = sum(max(0, self.demand_values[i] - nominal_supply[i]) for i in range(len(self.demand_values)))
        perfloss = total_undercoverage - understaffing
            
        metrics = self._final_metrics_package(total_undercoverage, understaffing, perfloss, consistency, scale)
        return (*metrics, perf_ls, [0]*len(lst)) # cumulative_total not easily compatible here

    def getUndercoverage(self):
        return [self.u[t, k].X for t in self.days for k in self.shifts]


# Keep legacy class for backward compatibility if needed
class MasterProblemQC(MasterProblem):
    """Legacy class name for backward compatibility."""
    pass
