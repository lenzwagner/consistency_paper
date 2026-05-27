import math
import seaborn as sns
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

def plot_comparison_boxplots_seaborn(stats1, stats2, var1_name, var2_name, length):
    data = []
    categories = ['Min. Depth', 'Max. Depth', 'Mean Depth']
    for i, (s1, s2) in enumerate(zip(stats1, stats2)):
        category = categories[i]
        for var, name in [(s1, var1_name), (s2, var2_name)]:
            min_val, max_val, mean, std = var
            data.extend([
                {'Category': category, 'Variable': name, 'Value': mean, 'Type': 'Mean'},
                {'Category': category, 'Variable': name, 'Value': min_val, 'Type': 'Min'},
                {'Category': category, 'Variable': name, 'Value': max_val, 'Type': 'Max'}
            ])
            for _ in range(length):
                value = np.random.normal(mean, std)
                data.append({'Category': category, 'Variable': name, 'Value': value, 'Type': 'Distribution'})

    df = pd.DataFrame(data)

    # Plot
    plt.figure(figsize=(15, 8))
    sns.set_style("whitegrid")
    sns.set_palette("husl")

    # Boxplot
    ax = sns.boxplot(x='Category', y='Value', hue='Variable', data=df[df['Type'] != 'Distribution'],
                     width=0.6, palette=['orange', 'green'])
    sns.stripplot(x='Category', y='Value', hue='Variable', data=df[df['Type'] == 'Distribution'],
                  dodge=True, alpha=0.3, jitter=True, ax=ax)

    sns.pointplot(x='Category', y='Value', hue='Variable', data=df[df['Type'] == 'Mean'],
                  dodge=0.3, join=False, ci=None, markers='D', scale=0.7, ax=ax)

    plt.title('')
    plt.xlabel('')
    plt.ylabel('Day in Planning Period', fontsize=12)

    handles, labels = ax.get_legend_handles_labels()
    plt.legend(handles[:2], labels[:2], title='Variable', loc='upper left')

    plt.ylim(0, df['Value'].max() * 1.1)  # Changed this line to start y-axis at 0

    plt.tight_layout()
    plt.show()

#plot_comparison_boxplots_seaborn(formatted_stats, formatted_stats, "Variable 1", "Variable 2", 28)