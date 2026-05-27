import pandas as pd
from Utils.gcutil import create_individual_working_list

# Sets (formerly loaded from Physicians.xlsx and Shifts.xlsx)
# Physicians setup (formerlyPhysician.xlsx – sheet 'Physician')
work = pd.DataFrame({
    'Id':      list(range(1, 21)),
    'WT':      [40.0, 40.0, 40.0, 40.0] + [None] * 16,
    'Weekend': [1.0,  1.0,  1.0,  1.0]  + [None] * 16,
})

# Scaling/Horizon setup (formerly NF.xlsx – sheet 'NF')
df = pd.DataFrame({
    'Day': list(range(1, 15)),
})

# Shift setup (formerly NF.xlsx – sheet 'Shift')
df1 = pd.DataFrame({
    'Shift': [1, 2, 3],
    'Hours': [8, 8, 8],
})

I = work['Id'].tolist()
W_I = work['Weekend'].tolist()
T = df['Day'].tolist()
K = df1['Shift'].tolist()
S_T = df1['Hours'].tolist()
I_T = work['WT'].tolist()

# Zip sets
S_T = {a: c for a, c in zip(K, S_T)}
I_T = {a: d for a, d in zip(I, I_T)}
W_I = {a: e for a, e in zip(I, W_I)}

# Individual working days
Max_WD_i = create_individual_working_list(len(I), 5, 6, 5)
Min_WD_i = create_individual_working_list(len(I), 3, 4, 3)
Min_WD_i = {a: f for a, f in zip(I, Min_WD_i)}
Max_WD_i = {a: g for a, g in zip(I, Max_WD_i)}