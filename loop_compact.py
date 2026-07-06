from Utils.compactsolver_exact import ProblemExact
from core.base_case import get_base_case_groups, get_wd_constraints, LEN_I_RANGE, SCENARIO_RANGE, PATTERN
from core.solver_base import TIME_LIMIT_COMPACT_PROD
from datetime import datetime
from Utils.gcutil import *
import pandas as pd
import numpy as np
import time
import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))
os.makedirs("results", exist_ok=True)

# DataFrame for results
results = pd.DataFrame(columns=['I', 'T', 'K', 'pattern', 'scenario', 'prob',
                                'incumbent', 'lower_bound', 'gap', 'total_time', 'undercoverage', 'status'])

# Times and Parameters
time_Limit = TIME_LIMIT_COMPACT_PROD

start_time = time.time()

for len_I in LEN_I_RANGE:
    for scenario in SCENARIO_RANGE:
        prob = {'Medium': 1.0, 'High': 1.1, 'Low': 0.9}.get(PATTERN)

        T = list(range(1, 29))
        I = list(range(1, len_I + 1))
        K = [1, 2, 3]

        data = pd.DataFrame({
            'I': I + [np.nan] * (max(len(I), len(T), len(K)) - len(I)),
            'T': T + [np.nan] * (max(len(I), len(T), len(K)) - len(T)),
            'K': K + [np.nan] * (max(len(I), len(T), len(K)) - len(K))
        })

        demand_dict = read_demand('data/demand_data.xlsx', len(I), PATTERN, scenario)

        print(f"")
        print(f"Iteration: I: {len(I)} - Pattern: {PATTERN} - Scenario: {scenario}")
        print(f"")

        Min_WD_i, Max_WD_i = get_wd_constraints(I)
        worker_groups = get_base_case_groups(I)
        compact_model = ProblemExact(data, demand_dict, Min_WD_i, Max_WD_i, worker_groups)
        compact_model.buildModel()
        compact_model.model.setParam('OutputFlag', 1)
        compact_model.model.setParam('TimeLimit', time_Limit)

        solve_start = time.time()
        compact_model.solveModel()
        solve_time = time.time() - solve_start

        try:
            lower_bound = compact_model.model.ObjBound
            incumbent = compact_model.model.ObjVal
            gap = compact_model.model.MIPGap
            undercoverage = sum(compact_model.u[t, k].X for t in T for k in K)
            status = compact_model.model.Status
            print(f"Lower Bound: {lower_bound:.3f}, Incumbent: {incumbent:.3f}, Gap: {gap:.3%}, Time: {solve_time:.2f}s")
        except Exception as e:
            print(f"Error retrieving solution: {e}")
            lower_bound = incumbent = gap = undercoverage = status = None

        result = pd.DataFrame([{
            'I': len(I),
            'T': len(T),
            'K': len(K),
            'pattern': PATTERN,
            'scenario': scenario,
            'prob': prob,
            'incumbent': round(incumbent, 3) if incumbent is not None else None,
            'lower_bound': round(lower_bound, 3) if lower_bound is not None else None,
            'gap': round(gap, 3) if gap is not None else None,
            'total_time': round(solve_time, 3),
            'undercoverage': round(undercoverage, 3) if undercoverage is not None else None,
            'status': status
        }])

        results = pd.concat([results, result], ignore_index=True)

print(results)

results.to_csv('results/Results_Compact.csv', index=False)
results.to_excel(f'results/Results_Compact_{datetime.now().strftime("%d_%m_%Y_%H-%M")}.xlsx', index=False)

print(f"\nTotal execution time: {time.time() - start_time:.2f} seconds")
