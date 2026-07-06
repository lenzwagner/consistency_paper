"""Temporary script: regenerate the demand Excel with the E-heavy (50/30/20)
target distribution, matching the structure of the old data/demand_data_old.xlsx.

Structure replicated exactly:
  - meta columns: Scenario, I, Pattern
  - shift columns: 'day,shift' for day 1..28, shift 1..3  (day-major, shift-minor)
  - rows: I in {50,100,150} x Pattern in {Low,Medium,High} x Scenario in 1..25
  - Pattern -> scarcity prob: Low=0.9, Medium=1.0, High=1.1
  - seed = scenario index (reproducible), volatility delta=0.25
Writes to data/demand_data.xlsx (does NOT overwrite the original).
"""
import pandas as pd
from Utils.demand import generate_demand

DAYS = 28
I_VALUES = [50, 100, 150]
PATTERNS = {'Low': 0.9, 'Medium': 1.0, 'High': 1.1}
SCENARIOS = list(range(1, 26))
SHIFT_PROBS = (50, 30, 20)   # E-heavy: early / late / night (AVERAGE split)
DELTA = 0.25                 # daily TOTAL volatility
PROP_VOLATILITY = 0.30       # day-to-day SHIFT-MIX volatility. 0.0 => fixed split every
                             # day (no BAP shift-change incentive, cons=0). >0 makes the
                             # daily mix vary (some days E-heavy, others L/N-heavy), which
                             # is what forces BAP shift changes while keeping the ~50/30/20
                             # average over the horizon.
OUT = 'data/demand_data_vol.xlsx'   # NEW file, does NOT overwrite demand_data.xlsx

shift_cols = [f'{d},{s}' for d in range(1, DAYS + 1) for s in (1, 2, 3)]
cols = ['Scenario', 'I', 'Pattern'] + shift_cols

rows = []
for scen in SCENARIOS:
    for I in I_VALUES:
        for pat, prob in PATTERNS.items():
            dd = generate_demand(DAYS, prob, I, shift_probs=SHIFT_PROBS, delta=DELTA,
                                 seed=scen, prop_volatility=PROP_VOLATILITY)
            row = {'Scenario': scen, 'I': I, 'Pattern': pat}
            for d in range(1, DAYS + 1):
                for s in (1, 2, 3):
                    row[f'{d},{s}'] = dd[(d, s)]
            rows.append(row)

df = pd.DataFrame(rows)[cols]
df.to_excel(OUT, index=False)
print(f"Wrote {OUT}: {df.shape[0]} rows x {df.shape[1]} columns")

# --- quick verification of the aggregate distribution per (I, Pattern) ---
print("\nAggregate shift split (over all 25 scenarios), should be ~50/30/20:")
for I in I_VALUES:
    for pat in PATTERNS:
        sub = df[(df['I'] == I) & (df['Pattern'] == pat)]
        E = sub[[f'{d},1' for d in range(1, DAYS + 1)]].values.sum()
        L = sub[[f'{d},2' for d in range(1, DAYS + 1)]].values.sum()
        N = sub[[f'{d},3' for d in range(1, DAYS + 1)]].values.sum()
        tot = E + L + N
        print(f"  I={I:3d} {pat:6s}: E={100*E/tot:.1f}%  L={100*L/tot:.1f}%  N={100*N/tot:.1f}%  (total={tot})")

# volatility check for I=100 Medium
sub = df[(df['I'] == 100) & (df['Pattern'] == 'Medium')]
dailies = []
for _, r in sub.iterrows():
    for d in range(1, DAYS + 1):
        dailies.append(r[f'{d},1'] + r[f'{d},2'] + r[f'{d},3'])
print(f"\nI=100 Medium daily-total range: [{min(dailies)}, {max(dailies)}]  (base=100, delta=0.25 -> [75,125])")
