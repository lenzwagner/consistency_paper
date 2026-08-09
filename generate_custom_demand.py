import os
import math
import random
import pandas as pd
from Utils.demand import generate_demand

def main():
    print("=============================================================")
    print("          CUSTOM DEMAND PATTERN GENERATOR                    ")
    print("=============================================================")
    
    # 1. Input parameters
    try:
        # Input for I (workforce sizes)
        i_input = input("Enter workforce sizes (I) separated by commas [default: 100]: ").strip()
        if not i_input:
            i_values = [100]
        else:
            i_values = [int(x.strip()) for x in i_input.split(',')]
            
        # Input for Days
        days_input = input("Enter number of Days [default: 28]: ").strip()
        days = int(days_input) if days_input else 28
        
        # Input for Scenarios / Seeds
        seeds_input = input("Enter seed/scenario range (e.g. '1..25' or '1,2,3' or single integer) [default: 1..25]: ").strip()
        if not seeds_input:
            scenarios = list(range(1, 26))
        elif '..' in seeds_input:
            start, end = map(int, seeds_input.split('..'))
            scenarios = list(range(start, end + 1))
        else:
            scenarios = [int(x.strip()) for x in seeds_input.split(',')]
            
        # Input for Shift Proportions
        shift_input = input("Enter shift proportions (Early, Late, Night) [default: 50,30,20]: ").strip()
        if not shift_input:
            shift_probs = (50, 30, 20)
        else:
            shift_probs = tuple(int(x.strip()) for x in shift_input.split(','))
            
        # Input for Delta (Daily Total Volatility)
        delta_input = input("Enter daily total volatility delta [default: 0.25]: ").strip()
        delta = float(delta_input) if delta_input else 0.25
        
        # Input for Prop Volatility (Shift-Mix Volatility)
        prop_input = input("Enter shift-mix volatility prop_volatility [default: 0.30]: ").strip()
        prop_volatility = float(prop_input) if prop_input else 0.30
        
        # Output excel path
        out_file = input("Enter output excel path [default: data/demand_data_custom.xlsx]: ").strip()
        if not out_file:
            out_file = 'data/demand_data_custom.xlsx'
            
    except Exception as e:
        print(f"\nError parsing inputs: {e}. Exiting.")
        return

    # 2. Setup patterns (low, medium, high)
    patterns = {'Low': 0.9, 'Medium': 1.0, 'High': 1.1}
    
    # 3. Generate demand rows
    shift_cols = [f'{d},{s}' for d in range(1, days + 1) for s in (1, 2, 3)]
    cols = ['Scenario', 'I', 'Pattern'] + shift_cols
    rows = []
    
    print("\nGenerating demand data...")
    for scen in scenarios:
        for I in i_values:
            for pat, prob in patterns.items():
                # generate_demand(num_days, prob, demand, shift_probs, delta, seed, prop_volatility)
                dd = generate_demand(
                    num_days=days,
                    prob=prob,
                    demand=I,
                    shift_probs=shift_probs,
                    delta=delta,
                    seed=scen,
                    prop_volatility=prop_volatility
                )
                
                row = {'Scenario': scen, 'I': I, 'Pattern': pat}
                for d in range(1, days + 1):
                    for s in (1, 2, 3):
                        row[f'{d},{s}'] = dd[(d, s)]
                rows.append(row)
                
    df = pd.DataFrame(rows)[cols]
    
    # Ensure directory exists
    dir_name = os.path.dirname(out_file)
    if dir_name and not os.path.exists(dir_name):
        os.makedirs(dir_name)
        
    df.to_excel(out_file, index=False)
    print(f"\nSUCCESS: Generated {df.shape[0]} rows x {df.shape[1]} columns.")
    print(f"Saved to: {os.path.abspath(out_file)}")
    
    # Print summary statistics
    print("\nSummary of aggregate shift proportions:")
    for I in i_values:
        for pat in patterns:
            sub = df[(df['I'] == I) & (df['Pattern'] == pat)]
            if sub.empty:
                continue
            E = sub[[f'{d},1' for d in range(1, days + 1)]].values.sum()
            L = sub[[f'{d},2' for d in range(1, days + 1)]].values.sum()
            N = sub[[f'{d},3' for d in range(1, days + 1)]].values.sum()
            tot = E + L + N
            if tot > 0:
                print(f"  I={I:3d} {pat:6s}: Early={100*E/tot:.1f}% | Late={100*L/tot:.1f}% | Night={100*N/tot:.1f}% (total={tot})")

if __name__ == '__main__':
    main()
