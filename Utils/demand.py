import random
import matplotlib.pyplot as plt
import numpy as np
import math

plt.rcParams.update({
    "text.usetex": True,
    "font.family": "lmodern",
    "font.serif": "Computer Modern Roman",
    "font.sans-serif": "Computer Modern Sans",
    "font.monospace": "Computer Modern Typewriter",
    "axes.labelsize": 11,  # adjust as necessary
    "font.size": 11,        # adjust as necessary
    "legend.fontsize": 9,   # adjust as necessary
    "xtick.labelsize": 9,   # adjust as necessary
    "ytick.labelsize": 9,   # adjust as necessary
})

pt = 1./72.27 # Hundreds of years of history... 72.27 points to an inch.

jour_sizes = {"PRD": {"onecol": 468.*pt, "twocol": 510.*pt},
              "CQG": {"onecol": 374.*pt}, # CQG is only one column
              # Add more journals below. Can add more properties to each journal
             }

my_width = jour_sizes["PRD"]["onecol"]
# Our figure's aspect ratio
golden = (1 + 5 ** 0.5) / 2

fig = plt.figure(figsize = (my_width, my_width/golden))




def demand_dict_fifty(num_days, prob, demand, middle_shift, fluctuation=0.25):
    base_total_demand = int(prob * demand)
    demand_dict = {}

    for day in range(1, num_days + 1):
        fluctuation_factor = 1 + (random.uniform(-fluctuation, fluctuation))
        total_demand = int(base_total_demand * fluctuation_factor)

        middle_shift_ratio = random.random()
        middle_shift_demand = round(total_demand * middle_shift_ratio)
        remaining_demand = total_demand - middle_shift_demand

        early_late_ratio = random.random()
        early_demand = round(remaining_demand * early_late_ratio)
        late_demand = remaining_demand - early_demand

        if middle_shift == 1:
            demand_dict[(day, 1)] = middle_shift_demand
            demand_dict[(day, 2)] = early_demand
            demand_dict[(day, 3)] = late_demand
        elif middle_shift == 2:
            demand_dict[(day, 1)] = early_demand
            demand_dict[(day, 2)] = middle_shift_demand
            demand_dict[(day, 3)] = late_demand
        elif middle_shift == 3:
            demand_dict[(day, 1)] = early_demand
            demand_dict[(day, 2)] = late_demand
            demand_dict[(day, 3)] = middle_shift_demand
        else:
            raise ValueError("Invalid middle_shift value")

    return demand_dict


def demand_dict_third(num_days, prob, demand):
    total_demand = int(prob * demand)
    demand_dict = {}

    for day in range(1, num_days + 1):
        z1 = random.random()
        z2 = random.random()
        z3 = random.random()

        summe = z1 + z2 + z3

        demand1 = (z1 / summe) * total_demand
        demand2 = (z2 / summe) * total_demand
        demand3 = (z3 / summe) * total_demand

        demand1_rounded = round(demand1)
        demand2_rounded = round(demand2)
        demand3_rounded = round(demand3)

        rounded_total = demand1_rounded + demand2_rounded + demand3_rounded
        rounding_difference = total_demand - rounded_total

        if rounding_difference != 0:
            shift_indices = [1, 2, 3]
            random.shuffle(shift_indices)
            for i in range(abs(rounding_difference)):
                if rounding_difference > 0:
                    if shift_indices[i] == 1:
                        demand1_rounded += 1
                    elif shift_indices[i] == 2:
                        demand2_rounded += 1
                    else:
                        demand3_rounded += 1
                else:
                    if shift_indices[i] == 1:
                        demand1_rounded -= 1
                    elif shift_indices[i] == 2:
                        demand2_rounded -= 1
                    else:
                        demand3_rounded -= 1

        demand_dict[(day, 1)] = demand1_rounded
        demand_dict[(day, 2)] = demand2_rounded
        demand_dict[(day, 3)] = demand3_rounded

    return demand_dict

def plot_demand_pattern(demands, days, shifts):
    shift_labels = ["Morning", "Noon", "Evening"]
    """
    Plots the demand pattern over shifts for a given number of days and shifts.

    Parameters:
    - demands: dict, demand values with keys as (day, shift) tuples.
    - days: int, number of days.
    - shifts: int, number of shifts per day.
    - shift_labels: list of str, labels for each shift.
    """
    plt.figure(figsize=(10, 6))

    colors = plt.cm.viridis(np.linspace(0, 1, days))

    for day in range(1, days + 1):
        shift_demand = [demands[(day, shift)] for shift in range(1, shifts + 1)]
        plt.plot(range(1, shifts + 1), shift_demand, marker='o', label=f'Day {day}', color=colors[day - 1])

    plt.xlabel('Shift')
    plt.ylabel('Demand')
    plt.title('Demand Pattern Over Shifts')
    plt.xticks(range(1, shifts + 1), shift_labels)
    plt.legend()
    plt.grid(True)
    plt.savefig('demand.svg', bbox_inches='tight')

    #plt.show()

def plot_demand_bar(demands, days, shifts):
    """
    Plots the demand pattern over shifts using a bar plot for a given number of days and shifts.

    Parameters:
    - demands: dict, demand values with keys as (day, shift) tuples.
    - days: int, number of days.
    - shifts: int, number of shifts per day.
    """
    demands_list = []
    grays = plt.cm.Greys(np.linspace(0.3, 0.7, shifts))

    for day in range(1, days + 1):
        for shift in range(1, shifts + 1):
            demands_list.append(demands[(day, shift)])

    plt.figure(figsize=(14, 8))
    bars = plt.bar(range(len(demands_list)), demands_list)

    for i, bar in enumerate(bars):
        shift_index = i % shifts
        bar.set_color(grays[shift_index])

    plt.xticks(ticks=[(i * shifts + (shifts - 1) / 2) for i in range(days)],
               labels=[f"Day {i + 1}" for i in range(days)], rotation=0)

    for bar in bars:
        yval = bar.get_height()
        plt.text(bar.get_x() + bar.get_width() / 2, yval, int(yval), ha='center', va='bottom', fontsize=10)

    plt.xlabel('Day')
    plt.ylabel('Demand')
    plt.title('Demand Pattern Over Shifts')
    plt.grid(axis='y')
    plt.tight_layout()
    plt.show()


import matplotlib.pyplot as plt
import numpy as np


import matplotlib.pyplot as plt
import numpy as np

def plot_demand_bar_by_day(demands, days, shifts, pt):
    """
    Plots the demand pattern over shifts using a bar plot for a given number of days and shifts.
    Parameters:
    - demands: dict, demand values with keys as (day, shift) tuples.
    - days: int, number of days.
    - shifts: int, number of shifts per day.
    - pt: int, width of the plot in points.
    """
    demands_list = []
    colors = plt.cm.magma(np.linspace(0, 0.8, shifts))
    for day in range(1, days + 1):
        for shift in range(1, shifts + 1):
            demands_list.append(demands[(day, shift)])
    pt_in = pt / 72
    width_plt = round(pt_in)
    height_plt = round((width_plt / 16) * 9)
    plt.figure(figsize=(width_plt, height_plt))

    bars = plt.bar(range(len(demands_list)), demands_list)
    for i, bar in enumerate(bars):
        shift_index = i % shifts
        bar.set_color(colors[shift_index])
        yval = bar.get_height()
        xval = bar.get_x() + bar.get_width() / 2

        if yval < 10:
            plt.text(xval, yval + 1.7, int(yval), rotation=90, ha='center', va='bottom',
                     fontsize=4.5, color='black')
        else:
            plt.text(xval, yval / 2, int(yval), rotation=90, ha='center', va='center',
                     fontsize=4.5, color='white')

    plt.xticks(ticks=[(i * shifts + (shifts - 1) / 2) for i in range(days)],
               labels=[f"{i + 1}" for i in range(days)], rotation=0)
    plt.xlabel('Day', fontsize=11)
    plt.ylabel('Demand', fontsize=11)
    plt.grid(axis='y')
    plt.tight_layout()
    plt.savefig('images/demand.eps', bbox_inches='tight')
    plt.show()

def demand_dict_fifty_min(num_days, prob, demand, middle_shift, fluctuation=0.25, seed=None):
    if seed is not None:
        random.seed(seed)

    base_total_demand = int(prob * demand)
    demand_dict = {}

    for day in range(1, num_days + 1):
        fluctuation_factor = 1 + (random.uniform(-fluctuation, fluctuation))
        total_demand = int(base_total_demand * fluctuation_factor)

        # Ensure each shift has at least 5% of total demand
        min_demand_per_shift = math.ceil(0.05 * total_demand)
        remaining_demand = total_demand - 3 * min_demand_per_shift

        # Distribute the remaining demand
        middle_shift_ratio = random.random()
        middle_shift_demand = round(remaining_demand * middle_shift_ratio) + min_demand_per_shift
        remaining_demand -= (middle_shift_demand - min_demand_per_shift)

        early_late_ratio = random.random()
        early_demand = round(remaining_demand * early_late_ratio) + min_demand_per_shift
        late_demand = remaining_demand - (early_demand - min_demand_per_shift) + min_demand_per_shift

        if middle_shift == 1:
            demand_dict[(day, 1)] = middle_shift_demand
            demand_dict[(day, 2)] = early_demand
            demand_dict[(day, 3)] = late_demand
        elif middle_shift == 2:
            demand_dict[(day, 1)] = early_demand
            demand_dict[(day, 2)] = middle_shift_demand
            demand_dict[(day, 3)] = late_demand
        elif middle_shift == 3:
            demand_dict[(day, 1)] = early_demand
            demand_dict[(day, 2)] = late_demand
            demand_dict[(day, 3)] = middle_shift_demand
        else:
            raise ValueError("Invalid middle_shift value")

    return demand_dict


import numpy as np
import matplotlib.pyplot as plt


def plot_demand_bar_by_day2(demands, days, shifts, pt):
    """
    Plots the demand pattern over shifts using a stacked bar plot for a given number of days and shifts.

    Parameters:
    - demands: dict, demand values with keys as (day, shift) tuples.
    - days: int, number of days.
    - shifts: int, number of shifts per day.
    - pt: int, width of the plot in points.
    """
    demands_by_day = np.zeros((days, shifts))
    for (day, shift), demand in demands.items():
        demands_by_day[day - 1, shift - 1] = demand

    colors = plt.cm.magma(np.linspace(0.15, 0.85, shifts))

    pt_in = pt / 72
    ratio_gl = 1. / 1.918
    width_plt = round(pt_in)
    height_plt = round((width_plt) * ratio_gl)
    plt.figure(figsize=(width_plt, height_plt))

    bar_bottom = np.zeros(days)
    bars = []

    for shift in range(shifts):
        bars.append(plt.bar(range(1, days + 1), demands_by_day[:, shift], bottom=bar_bottom, color=colors[shift],
                            label=f'Shift {shift + 1}'))
        bar_bottom += demands_by_day[:, shift]

    plt.xticks(ticks=range(1, days + 1), labels=[f"{i + 1}" for i in range(days)], rotation=0)
    plt.xlabel('Day', fontsize=11)
    plt.ylabel('Demand', fontsize=11)

    # Add legend horizontally below the x-axis
    plt.legend(title='Shifts', loc='upper center', bbox_to_anchor=(0.5, -0.22), ncol=shifts)

    plt.grid(axis='y')

    # Add demand values to each bar
    for shift_idx, bars_shift in enumerate(bars):
        for bar in bars_shift:
            yval = bar.get_height()
            xval = bar.get_x() + bar.get_width() / 2
            bar_label = f'{int(yval)}'
            if yval < 5:  # Adjust the threshold as needed
                plt.text(xval, bar.get_y() + yval + 0.5, bar_label, ha='center', va='bottom', fontsize=6, color='black')
            else:
                plt.text(xval, bar.get_y() + yval / 2, bar_label, ha='center', va='center', fontsize=6, color='white')

    plt.tight_layout()
    #plt.savefig('images/demand.eps', bbox_inches='tight')
    plt.show()

