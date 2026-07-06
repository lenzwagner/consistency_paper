"""
run_loopcg_scalars.py
=====================
Runs ONE loop_cg pass (1 seed / scenario) for a configurable
workforce size and horizon length and prints ONLY the scalar values
(objective function, undercoverage, consistency, performance loss, Gini,
spread, load-share) across all three paradigms: BAP (behavior), NPP
(naive), and ECP.
"""
import os
import sys
import time

import numpy as np
import pandas as pd

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)
os.chdir(_THIS_DIR)

from core.cg_behavior import column_generation_behavior
from core.cg_naive import column_generation_naive
from core.cg_ecp import column_generation_ecp
from core.base_case import get_base_case_groups, get_wd_constraints, PATTERN, CHI
from core.solver_base import MAX_ITR, THRESHOLD, TIME_CG_INIT, TIME_CG
from Utils.gcutil import read_demand

# ============================ CONFIG ============================
NUM_WORKERS = 50      # Workforce size (must exist in demand_data.xlsx: 50/100/150)
NUM_DAYS    = 28      # Horizon (demand data is available for 28 days)
SEED        = 1       # Demand scenario (= "seed") 1..25
# ===============================================================

PROB = {'Medium': 1.0, 'High': 1.1, 'Low': 0.9}.get(PATTERN)

I = list(range(1, NUM_WORKERS + 1))
T = list(range(1, NUM_DAYS + 1))
K = [1, 2, 3]
ml = max(len(I), len(T), len(K))
data = pd.DataFrame({
    'I': I + [np.nan] * (ml - len(I)),
    'T': T + [np.nan] * (ml - len(T)),
    'K': K + [np.nan] * (ml - len(K)),
})

demand_dict = read_demand('data/demand_data.xlsx', NUM_WORKERS, PATTERN, scenario=SEED)
demand_dict = {k: v for k, v in demand_dict.items() if k[0] <= NUM_DAYS}

Min_WD_i, Max_WD_i = get_wd_constraints(I)
worker_groups = get_base_case_groups(I)

print("=" * 78)
print(f"loop_cg (scalars)  |  I={NUM_WORKERS}  T={NUM_DAYS}  Seed/Scenario={SEED}  Pattern={PATTERN}")
print("=" * 78)

# ----------------------------- BAP (behavior) -----------------------------
print("\n[1/3] BAP (behavior, CG+labeling_bidir) ...")
t0 = time.time()
b = column_generation_behavior(
    data, demand_dict, 0.0, Min_WD_i, Max_WD_i, TIME_CG_INIT, MAX_ITR, 100, CHI,
    THRESHOLD, TIME_CG, I, T, K, PROB, sp_solver='labeling_bidir',
    worker_groups=worker_groups, use_heuristic_start=False, use_null_column=True,
)
t_bap = time.time() - t0

# ----------------------------- NPP (naive) --------------------------------
print("[2/3] NPP (naive) ...")
t0 = time.time()
n = column_generation_naive(
    data, demand_dict, 0, Min_WD_i, Max_WD_i, TIME_CG_INIT, MAX_ITR, 100, CHI,
    THRESHOLD, TIME_CG, I, T, K, PROB, sp_solver='labeling_bidir',
    worker_groups=worker_groups, use_null_column=True,
)
t_npp = time.time() - t0

# ----------------------------- ECP ----------------------------------------
print("[3/3] ECP (k<=2) ...")
t0 = time.time()
e = column_generation_ecp(
    data, demand_dict, 0, Min_WD_i, Max_WD_i, TIME_CG_INIT, MAX_ITR, 100, CHI,
    THRESHOLD, TIME_CG, I, T, K, PROB, k=2, sp_solver='labeling_bidir',
    worker_groups=worker_groups, use_null_column=True,
)
t_ecp = time.time() - t0

# --------- Scalar extraction (indices match loop_cg-unpacking) -----------
# behavior: [0]undercover [1]understaff [2]perfloss [3]cons [4]cons_norm
#           [5]undercover_norm [6]understaff_norm [7]perfloss_norm [8]final_obj
#           [9]lb [11]lagrange [12]gap ... [23]spread_sc [24]load_share_sc
#           [25]gini_sc [27]spread_perf [28]load_share_perf [29]gini_perf
def scal_behavior(r):
    return dict(obj=r[8], lb=r[9], gap=r[12], lagrange=r[11],
                undercover=r[0], undercover_norm=r[5],
                understaff=r[1], understaff_norm=r[6],
                perfloss=r[2], perfloss_norm=r[7],
                cons=r[3], cons_norm=r[4],
                spread_sc=r[23], load_share_sc=r[24], gini_sc=r[25],
                spread_perf=r[27], load_share_perf=r[28], gini_perf=r[29])

# naive/ecp: [0]undercover [1]understaff [2]perfloss [3]cons [4]cons_norm
#            [5]undercover_norm [6]understaff_norm [7]perfloss_norm [8]final_obj
#            ... [16]spread_sc [17]load_share_sc [18]gini_sc
#            [20]spread_perf [21]load_share_perf [22]gini_perf
def scal_simple(r):
    return dict(obj=r[8], lb=np.nan, gap=np.nan, lagrange=np.nan,
                undercover=r[0], undercover_norm=r[5],
                understaff=r[1], understaff_norm=r[6],
                perfloss=r[2], perfloss_norm=r[7],
                cons=r[3], cons_norm=r[4],
                spread_sc=r[16], load_share_sc=r[17], gini_sc=r[18],
                spread_perf=r[20], load_share_perf=r[21], gini_perf=r[22])

rows = {
    'BAP':  {**scal_behavior(b), 'time': t_bap},
    'NPP':  {**scal_simple(n),   'time': t_npp},
    'ECP':  {**scal_simple(e),   'time': t_ecp},
}
df = pd.DataFrame(rows).T

metric_order = ['obj', 'lb', 'gap', 'lagrange',
                'undercover', 'undercover_norm', 'understaff', 'understaff_norm',
                'perfloss', 'perfloss_norm', 'cons', 'cons_norm',
                'spread_sc', 'load_share_sc', 'gini_sc',
                'spread_perf', 'load_share_perf', 'gini_perf', 'time']
df = df[metric_order]

pd.set_option('display.float_format', lambda x: f'{x:.4f}')
pd.set_option('display.width', 200)
pd.set_option('display.max_columns', 50)

print("\n" + "=" * 78)
print("SCALAR VALUES across all three paradigms")
print("=" * 78)
# Transposed: metrics as rows, paradigms as columns (highly readable)
print(df.T.to_string())

out = os.path.join(_THIS_DIR, 'results', 'csv', f'loopcg_scalars_I{NUM_WORKERS}_T{NUM_DAYS}_seed{SEED}.csv')
os.makedirs(os.path.dirname(out), exist_ok=True)
df.T.to_csv(out)
print(f"\nSaved: {out}")
