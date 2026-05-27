from Utils.setup import Min_WD_i, Max_WD_i
from Utils.compactsolver import Problem
from Utils.gcutil import generate_dict_from_excel
from nonlinear_transitions import get_default_nl_spec
import pandas as pd
import numpy as np
import time

len_I = 50
T = list(range(1, 29))
I = list(range(1, len_I + 1))
K = [1, 2, 3]

data = pd.DataFrame({
    'I': I + [np.nan] * (max(len(I), len(T), len(K)) - len(I)),
    'T': T + [np.nan] * (max(len(I), len(T), len(K)) - len(T)),
    'K': K + [np.nan] * (max(len(I), len(T), len(K)) - len(K))
})

# scenario 1
demand_dict = generate_dict_from_excel('data/demand_data.xlsx', len(I), 'Medium', 1)
nl_spec = get_default_nl_spec(epsilon=0.06, chi=3)

print('Building Compact NL Model...')
compact_model = Problem(data, demand_dict, eps=0.06, Min_WD_i=Min_WD_i, Max_WD_i=Max_WD_i, chi=3, nl_spec=nl_spec)
compact_model.buildLinModel()
compact_model.model.setParam('TimeLimit', 10)
print('Solving...')
compact_model.solveModel()

try:
    print(f"Obj: {compact_model.model.ObjVal:.3f}")
except:
    pass
