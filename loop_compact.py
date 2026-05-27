from Utils.setup import Min_WD_i, Max_WD_i
from Utils.compactsolver import Problem
from datetime import datetime
from Utils.gcutil import *
import pandas as pd
import numpy as np
import time

# DataFrame for results
results = pd.DataFrame(columns=['I', 'T', 'K', 'pattern', 'scenario', 'prob', 'epsilon', 'chi',
                                'incumbent', 'lower_bound', 'total_time', 'undercoverage'])

# Times and Parameters
time_Limit = 3600

start_time = time.time()

# Loop - same instance configuration as in loop.py
for epsilon in [0.06]:
    for chi in [3]:
        for len_I in [50]:
            for pattern in ['Medium']:
                for scenario in range(1, 3):
                    if pattern == 'Medium':
                        prob = 1.0
                    elif pattern == 'High':
                        prob = 1.1
                    elif pattern == 'Low':
                        prob = 0.9

                    # Data - same as in loop.py
                    T = list(range(1, 29))
                    I = list(range(1, len_I + 1))
                    K = [1, 2, 3]

                    data = pd.DataFrame({
                        'I': I + [np.nan] * (max(len(I), len(T), len(K)) - len(I)),
                        'T': T + [np.nan] * (max(len(I), len(T), len(K)) - len(T)),
                        'K': K + [np.nan] * (max(len(I), len(T), len(K)) - len(K))
                    })

                    demand_dict = generate_dict_from_excel('data/demand_data.xlsx', len(I), pattern, scenario)
                    eps = epsilon
                    print('demand_dict', demand_dict)


                    print(f"")
                    print(f"Iteration: Eps: {epsilon} - Chi: {chi} - I: {len(I)} - Pattern: {pattern} - Scenario: {scenario}")
                    print(f"")

                    # Solve with Compact Model
                    print('Solving with compact model...')

                    # Create and build the compact model
                    compact_model = Problem(data, demand_dict, eps, Min_WD_i, Max_WD_i, chi)
                    compact_model.buildLinModel()
                    compact_model.ModelParams()

                    # Set time limit
                    compact_model.model.setParam('TimeLimit', time_Limit)

                    # Solve the model
                    solve_start = time.time()
                    compact_model.solveModel()
                    solve_time = time.time() - solve_start

                    # Get results
                    try:
                        lower_bound = compact_model.model.ObjBound
                        incumbent = compact_model.model.ObjVal
                        gap = compact_model.model.MIPGap

                        # Calculate undercoverage from u variables
                        undercoverage = sum(compact_model.u[t, k].X for t in T for k in K)

                        status = compact_model.model.Status

                        print(f"Lower Bound: {lower_bound:.3f}")
                        print(f"Incumbent: {incumbent:.3f}")
                        print(f"MIP Gap: {gap:.3%}")
                        print(f"Solve Time: {solve_time:.2f}s")
                        print(f"Status: {status}")

                    except Exception as e:
                        print(f"Error retrieving solution: {e}")
                        lower_bound = None
                        incumbent = None
                        gap = None
                        undercoverage = None
                        status = None

                    # Store results
                    result = pd.DataFrame([{
                        'I': len(I),
                        'T': len(T),
                        'K': len(K),
                        'pattern': pattern,
                        'scenario': scenario,
                        'prob': prob,
                        'epsilon': eps,
                        'chi': chi,
                        'incumbent': round(incumbent, 3) if incumbent is not None else None,
                        'lower_bound': round(lower_bound, 3) if lower_bound is not None else None,
                        'gap': round(gap, 3) if gap is not None else None,
                        'total_time': round(solve_time, 3),
                        'undercoverage': round(undercoverage, 3) if undercoverage is not None else None,
                        'status': status
                    }])

                    results = pd.concat([results, result], ignore_index=True)

print(results)

# Save results
results.to_csv('results/Results_Compact.csv', index=False)
results.to_excel(f'results/Results_Compact_50_low_1-5.xlsx', index=False)

print(f"\nTotal execution time: {time.time() - start_time:.2f} seconds")
print(f"Results saved to results/Results_Compact.csv")
