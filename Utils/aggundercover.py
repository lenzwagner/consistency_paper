from Utils.demand import *

plt.rcParams.update({
    "text.usetex": True,
    "font.family": "lmodern",
    "font.serif": "Computer Modern Roman",
    "font.sans-serif": "Computer Modern Sans",
    "font.monospace": "Computer Modern Typewriter",
    "axes.labelsize": 18,  # adjust as necessary
    "font.size": 18,        # adjust as necessary
    "legend.fontsize": 16,   # adjust as necessary
    "xtick.labelsize": 16,   # adjust as necessary
    "ytick.labelsize": 16,   # adjust as necessary
})

def create_dict_from_list(lst, days, shifts):
    if len(lst) != days * shifts:
        raise ValueError("Error")

    result = {}
    index = 0

    for i in range(1, days + 1):
        for j in range(1, shifts + 1):
            result[(i, j)] = lst[index]
            index += 1

    return result


def plot_undercover(ls, days, shifts, pt):
    lss_list = []
    colors = plt.cm.magma(np.linspace(0, 0.8, shifts))

    for day in range(1, days + 1):
        for shift in range(1, shifts + 1):
            lss_list.append(ls[(day, shift)])

    pt_in = pt / 72
    width_plt = round(pt_in)
    height_plt = round((width_plt / 16) * 9)
    plt.figure(figsize=(12,6))
    bars = plt.bar(range(len(lss_list)), lss_list)

    for i, bar in enumerate(bars):
        shift_index = i % shifts
        bar.set_color(colors[shift_index])

    plt.xticks(ticks=[(i * shifts + (shifts - 1) / 2) for i in range(days)],
               labels=[f"{i + 1}" for i in range(days)], rotation=0)

    for bar in bars:
        yval = bar.get_height()
        # Format the value depending on whether it is an integer or not
        yval_str = f"{int(yval)}" if yval.is_integer() else f"{yval:.2f}"
        plt.text(bar.get_x() + bar.get_width() / 2, yval, yval_str, ha='center', va='bottom', fontsize=9)

    plt.xlabel('Day', fontsize=11)
    plt.ylabel('Undercoverage', fontsize=11)
    #plt.title('Demand Pattern', fontsize=20)
    plt.grid(axis='y')
    plt.tight_layout()
    plt.savefig('images/undercover.svg', bbox_inches='tight')

    plt.show()

def rel_dict(a,b):
    return {key: a[key] / b[key] if key in b and b[key] != 0 else None for key in a}

def dict_reducer(data):
    result = {}

    for (key1, key2), value in data.items():
        if key1 in result:
            result[key1] += value
        else:
            result[key1] = value

    return result

def plot_undercover_d(ls, days, shifts, pt, filename_suffix=''):
    daily_undercover = []

    for day in range(1, days + 1):
        daily_sum = sum(ls.get((day, shift), 0) for shift in range(1, shifts + 1))
        daily_undercover.append(daily_sum)

    pt_in = pt / 72
    width_plt = round(pt_in)
    height_plt = round((width_plt / 16) * 9)

    plt.figure(figsize=(12, 6))
    bars = plt.bar(range(1, days + 1), daily_undercover, color='blue', alpha=0.7)

    plt.xlabel('Day', fontsize=11)
    plt.ylabel('Daily Undercoverage', fontsize=11)
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.xticks(range(1, days + 1, 2))  # Show every other day on x-axis

    for bar in bars:
        yval = bar.get_height()
        yval_str = f"{int(yval)}" if yval.is_integer() else f"{yval:.2f}"
        plt.text(bar.get_x() + bar.get_width() / 2, yval, yval_str,
                 ha='center', va='bottom', fontsize=9)

    total_undercoverage = sum(daily_undercover)
    plt.text(0.95, 0.95, f'Total Undercoverage: {total_undercoverage:.2f}',
             transform=plt.gca().transAxes, ha='right', va='top',
             bbox=dict(facecolor='white', edgecolor='none', alpha=0.7))

    plt.tight_layout()

    # Create the filename with the optional suffix
    base_filename = 'daily_undercover'
    if filename_suffix:
        base_filename += f'_{filename_suffix}'

    plt.savefig(f'images/undercover/{base_filename}.svg', bbox_inches='tight')
    plt.savefig(f'images/undercover/{base_filename}.png', bbox_inches='tight')
    plt.show()

def plot_relative_undercover(ls1, ls2, demand_dict, days, shifts, pt, filename_suffix=''):
    daily_relative_undercover1 = []
    daily_relative_undercover2 = []

    for day in range(1, days + 1):
        # Sum of undercoverage per day for both lists
        daily_sum1 = sum(ls1.get((day, shift), 0) for shift in range(1, shifts + 1))
        daily_sum2 = sum(ls2.get((day, shift), 0) for shift in range(1, shifts + 1))

        # Sum of demand per day
        daily_demand_sum = sum(demand_dict.get((day, shift), 0) for shift in range(1, shifts + 1))

        # Calculate relative undercoverage for both lists
        if daily_demand_sum > 0:
            relative_undercover1 = daily_sum1 / daily_demand_sum
            relative_undercover2 = daily_sum2 / daily_demand_sum
        else:
            relative_undercover1 = relative_undercover2 = 0  # or another rule if demand is 0

        daily_relative_undercover1.append(relative_undercover1)
        daily_relative_undercover2.append(relative_undercover2)

    pt_in = pt / 72
    width_plt = round(pt_in)
    height_plt = round((width_plt / 16) * 9)

    plt.figure(figsize=(12, 6))

    x = np.arange(1, days + 1)
    width = 0.35

    colors = plt.cm.magma([0.2, 0.8])  # Use magma colorscheme with two distinct colors

    bars1 = plt.bar(x - width/2, daily_relative_undercover1, width, color=colors[0], alpha=0.7, label='List 1')
    bars2 = plt.bar(x + width/2, daily_relative_undercover2, width, color=colors[1], alpha=0.7, label='List 2')

    plt.xlabel('Day', fontsize=11)
    plt.ylabel('Relative Undercoverage', fontsize=11)
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.xticks(x)

    def add_value_labels(bars):
        for bar in bars:
            height = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2., height/2,
                     f'{height:.2%}',
                     ha='center', va='center', rotation=90, fontsize=9)

    add_value_labels(bars1)
    add_value_labels(bars2)

    avg_relative_undercoverage1 = sum(daily_relative_undercover1) / len(daily_relative_undercover1)
    avg_relative_undercoverage2 = sum(daily_relative_undercover2) / len(daily_relative_undercover2)
    plt.text(0.95, 0.95, f'Avg. Relative Undercoverage 1: {avg_relative_undercoverage1:.2%}\nAvg. Relative Undercoverage 2: {avg_relative_undercoverage2:.2%}',
             transform=plt.gca().transAxes, ha='right', va='top',
             bbox=dict(facecolor='white', edgecolor='none', alpha=0.7))

    plt.legend()
    plt.tight_layout()

    base_filename = 'relative_undercover'
    if filename_suffix:
        base_filename += f'_{filename_suffix}'

    plt.savefig(f'images/undercover/{base_filename}.svg', bbox_inches='tight')
    plt.savefig(f'images/undercover/{base_filename}.png', bbox_inches='tight')
    #plt.show()


def plot_relative_undercover_dual(ls1, ls2, demand_dict, days, shifts, pt, filename_suffix=''):
    daily_relative_undercover1 = []
    daily_relative_undercover2 = []

    for day in range(1, days + 1):
        daily_sum1 = sum(ls1.get((day, shift), 0) for shift in range(1, shifts + 1))
        daily_sum2 = sum(ls2.get((day, shift), 0) for shift in range(1, shifts + 1))
        daily_demand_sum = sum(demand_dict.get((day, shift), 0) for shift in range(1, shifts + 1))

        if daily_demand_sum > 0:
            relative_undercover1 = daily_sum1 / daily_demand_sum
            relative_undercover2 = daily_sum2 / daily_demand_sum
        else:
            relative_undercover1 = relative_undercover2 = 0

        daily_relative_undercover1.append(relative_undercover1)
        daily_relative_undercover2.append(relative_undercover2)

    pt_in = pt / 72
    width_plt = round(pt_in)
    height_plt = round((width_plt / 16) * 9)

    plt.figure(figsize=(12, 6))

    x = np.arange(1, days + 1)
    width = 0.35

    colors = plt.cm.magma([0.8, 0.2])

    bars1 = plt.bar(x - width / 2, daily_relative_undercover1, width, color=colors[0], alpha=0.7,
                    label='Human-Scheduling Approach')
    bars2 = plt.bar(x + width / 2, daily_relative_undercover2, width, color=colors[1], alpha=0.7,
                    label='Machine-Like Scheduling Approach')

    # Move axis labels down
    plt.xlabel('Days', fontsize=14.5, labelpad=15)  # labelpad increases distance to axis
    plt.ylabel('Relative Undercoverage', fontsize=14.5, labelpad=15)  # labelpad increases distance to axis

    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.xticks(x)

    def add_value_labels(bars):
        for bar in bars:
            height = bar.get_height()
            plt.text(bar.get_x() + bar.get_width() / 2., height + 0.01, f'{height:.2%}',
                     ha='center', va='bottom', rotation=90, fontsize=10, color='black',
                     bbox=dict(facecolor='none', edgecolor='red', alpha=0, pad=0.))

    add_value_labels(bars1)
    add_value_labels(bars2)

    # Find the maximum height of all bars
    max_height = max(max(bar.get_height() for bar in bars1),
                     max(bar.get_height() for bar in bars2))

    # Add a margin (e.g., 15% of the max height) above the highest bar for the labels and legend
    legend_margin = 0.15 * max_height
    plt.ylim(top=max_height + legend_margin)

    # Create legend with thinner frame
    legend = plt.legend(loc='upper left', bbox_to_anchor=(0.02, 0.98), ncol=1, frameon=True, edgecolor='black',
                        facecolor='white', framealpha=1, fontsize=14.5)  # Set font size to match axis labels
    legend.get_frame().set_linewidth(0.5)

    plt.tight_layout()

    base_filename = 'relative_undercover'
    if filename_suffix:
        base_filename += f'_{filename_suffix}'

    # Save as .eps file
    plt.savefig(f'images/undercover/{base_filename}.svg', format='svg', bbox_inches='tight')
    plt.show()

#comb_text = str(0.06) + '_' + str(3)
#file3 = 'comb1'
#demand_dict = {(1, 1): 1, (1, 2): 86, (1, 3): 0, (2, 1): 27, (2, 2): 71, (2, 3): 3, (3, 1): 1, (3, 2): 57, (3, 3): 53, (4, 1): 26, (4, 2): 53, (4, 3): 32, (5, 1): 0, (5, 2): 47, (5, 3): 28, (6, 1): 2, (6, 2): 73, (6, 3): 49, (7, 1): 50, (7, 2): 51, (7, 3): 1, (8, 1): 55, (8, 2): 29, (8, 3): 24, (9, 1): 25, (9, 2): 21, (9, 3): 57, (10, 1): 28, (10, 2): 2, (10, 3): 71, (11, 1): 5, (11, 2): 83, (11, 3): 1, (12, 1): 32, (12, 2): 78, (12, 3): 14, (13, 1): 2, (13, 2): 103, (13, 3): 17, (14, 1): 7, (14, 2): 65, (14, 3): 34, (15, 1): 7, (15, 2): 47, (15, 3): 46, (16, 1): 23, (16, 2): 50, (16, 3): 22, (17, 1): 5, (17, 2): 40, (17, 3): 45, (18, 1): 7, (18, 2): 97, (18, 3): 3, (19, 1): 20, (19, 2): 87, (19, 3): 2, (20, 1): 39, (20, 2): 24, (20, 3): 18, (21, 1): 3, (21, 2): 83, (21, 3): 10, (22, 1): 60, (22, 2): 13, (22, 3): 36, (23, 1): 9, (23, 2): 105, (23, 3): 4, (24, 1): 100, (24, 2): 2, (24, 3): 2, (25, 1): 24, (25, 2): 47, (25, 3): 28, (26, 1): 17, (26, 2): 37, (26, 3): 46, (27, 1): 34, (27, 2): 45, (27, 3): 14, (28, 1): 4, (28, 2): 18, (28, 3): 89}



#aa = {(1, 1): 0.0, (1, 2): 0.0, (1, 3): 0.0, (2, 1): 25.0, (2, 2): 0.0, (2, 3): 0.18, (3, 1): 0.0, (3, 2): 33.0, (3, 3): 8.820000000000002, (4, 1): 7.140000000000001, (4, 2): 29.0, (4, 3): 5.6800000000000015, (5, 1): 0.0, (5, 2): 9.340000000000002, (5, 3): 1.680000000000001, (6, 1): 2.0, (6, 2): 25.560000000000002, (6, 3): 41.54, (7, 1): 38.2, (7, 2): 4.440000000000003, (7, 3): 0.18, (8, 1): 19.880000000000003, (8, 2): 5.920000000000001, (8, 3): 4.200000000000001, (9, 1): 2.9800000000000004, (9, 2): 6.44, (9, 3): 32.5, (10, 1): 2.220000000000001, (10, 2): 0.24, (10, 3): 43.0, (11, 1): 0.6600000000000001, (11, 2): 37.28, (11, 3): 0.18, (12, 1): 29.0, (12, 2): 32.160000000000004, (12, 3): 3.34, (13, 1): 2.0, (13, 2): 47.96, (13, 3): 2.5200000000000005, (14, 1): 7.0, (14, 2): 31.540000000000003, (14, 3): 5.459999999999996, (15, 1): 4.3, (15, 2): 8.280000000000006, (15, 3): 23.82, (16, 1): 19.54, (16, 2): 8.640000000000006, (16, 3): 14.04, (17, 1): 2.36, (17, 2): 6.700000000000002, (17, 3): 24.26, (18, 1): 0.84, (18, 2): 52.14, (18, 3): 3.0, (19, 1): 7.460000000000001, (19, 2): 41.94, (19, 3): 1.3599999999999999, (20, 1): 8.999999999999996, (20, 2): 0.0, (20, 3): 4.14, (21, 1): 1.08, (21, 2): 36.82, (21, 3): 3.3, (22, 1): 46.76, (22, 2): 3.8799999999999994, (22, 3): 17.099999999999998, (23, 1): 0.0, (23, 2): 98.22, (23, 3): 2.08, (24, 1): 54.00000000000001, (24, 2): 0.24, (24, 3): 0.0, (25, 1): 10.18, (25, 2): 16.400000000000002, (25, 3): 9.440000000000001, (26, 1): 0.0, (26, 2): 0.0, (26, 3): 19.68, (27, 1): 17.3, (27, 2): 17.119999999999997, (27, 3): 0.0, (28, 1): 4.0, (28, 2): 10.260000000000002, (28, 3): 39.68000000000001}
#ab = {(1, 1): 0.0, (1, 2): 0.0, (1, 3): 0.0, (2, 1): 25.0, (2, 2): 0.0, (2, 3): 0.0, (3, 1): 0.0, (3, 2): 0.0, (3, 3): 33.96, (4, 1): 25.0, (4, 2): 0.0, (4, 3): 4.5, (5, 1): 0.0, (5, 2): 0.0, (5, 3): 0.5, (6, 1): 0.12, (6, 2): 31.0, (6, 3): 44.06, (7, 1): 39.6, (7, 2): 15.0, (7, 3): 0.0, (8, 1): 22.04, (8, 2): 1.0, (8, 3): 0.36, (9, 1): 0.0, (9, 2): 1.96, (9, 3): 33.36, (10, 1): 0.0, (10, 2): 0.0, (10, 3): 47.36, (11, 1): 0.06, (11, 2): 29.3, (11, 3): 0.0, (12, 1): 29.0, (12, 2): 12.2, (12, 3): 13.0, (13, 1): 0.0, (13, 2): 47.8, (13, 3): 0.0, (14, 1): 3.0, (14, 2): 20.9, (14, 3): 14.18, (15, 1): 2.0, (15, 2): 0.0, (15, 3): 23.42, (16, 1): 16.240000000000002, (16, 2): 12.0, (16, 3): 0.36, (17, 1): 0.24, (17, 2): 0.12, (17, 3): 24.3, (18, 1): 0.24, (18, 2): 40.12, (18, 3): 0.06, (19, 1): 0.08, (19, 2): 33.0, (19, 3): 0.0, (20, 1): 3.86, (20, 2): 1.0, (20, 3): 2.7800000000000002, (21, 1): 0.18, (21, 2): 30.48, (21, 3): 0.42, (22, 1): 41.14, (22, 2): 0.0, (22, 3): 0.78, (23, 1): 0.0, (23, 2): 96.14, (23, 3): 0.06, (24, 1): 66.04, (24, 2): 0.0, (24, 3): 0.06, (25, 1): 0.44, (25, 2): 25.38, (25, 3): 1.36, (26, 1): 0.37999999997459355, (26, 2): 0.0, (26, 3): 18.68, (27, 1): 7.38, (27, 2): 4.62, (27, 3): 0.0, (28, 1): 0.24, (28, 2): 0.0, (28, 3): 17.14}

#plot_relative_undercover_dual(aa, ab, demand_dict, 28,  3, 499, file3)