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

def generate_demand(num_days, prob, demand, shift_probs=(0.50, 0.30, 0.20), delta=0.25,
                    seed=None, prop_volatility=0.0):
    """Generate a demand dictionary keyed by (day, shift).

    Parameters
    ----------
    num_days    : length of the planning horizon.
    prob        : demand scarcity factor (e.g. 0.9 / 1.0 / 1.1) applied to `demand`.
    demand      : base total demand per day (e.g. the workforce size |I|).
    shift_probs : target proportions for the three shifts, positionally
                  (shift 1, shift 2, shift 3) = (early E, late L, night N).
                  The base case is E-heavy (0.50, 0.30, 0.20). Values need not
                  sum to 1; they are normalized internally, so (50, 30, 20)
                  and (0.5, 0.3, 0.2) are equivalent.
    delta       : daily volatility of the TOTAL. The daily total fluctuates uniformly
                  in [(1-delta)*base, (1+delta)*base].
    prop_volatility : day-to-day volatility of the SHIFT SPLIT (default 0.0 = the
                  legacy behaviour where every day has the identical fixed split).
                  With prop_volatility=0 the per-shift demand is proportionally
                  constant across days, so a fixed shift-type assignment covers it
                  perfectly and BAP has NO incentive to change shifts (cons=0).
                  Set it > 0 (e.g. 0.25-0.35) to perturb each day's proportions so
                  that some days are E-heavy, others L- or N-heavy; this is what
                  forces shift changes. Implemented as a symmetric Dirichlet-style
                  perturbation: p_day[j] = normalize(max(eps, p[j] + U(-v, v))).
    seed        : optional RNG seed for reproducibility.
    """
    if seed is not None:
        random.seed(seed)

    p = list(shift_probs)
    if len(p) != 3:
        raise ValueError("shift_probs must have exactly 3 entries (E, L, N).")
    s = sum(p)
    if s <= 0:
        raise ValueError("shift_probs must sum to a positive value.")
    p = [x / s for x in p]  # normalize -> proportions

    base_total_demand = prob * demand
    lo = int(math.floor((1 - delta) * base_total_demand))
    hi = int(math.floor((1 + delta) * base_total_demand))
    demand_dict = {}

    for day in range(1, num_days + 1):
        # Daily total: uniform integer in [floor((1-delta)*base), floor((1+delta)*base)].
        total_demand = random.randint(lo, hi)

        # Per-day shift split. With prop_volatility>0 each day's proportions are
        # perturbed so the shift MIX (not just the total) varies day-to-day, which
        # is what creates a shift-change incentive for BAP.
        if prop_volatility > 0.0:
            eps = 0.01
            p_day = [max(eps, p[j] + random.uniform(-prop_volatility, prop_volatility))
                     for j in range(3)]
            ssum = sum(p_day)
            p_day = [x / ssum for x in p_day]
        else:
            p_day = p

        # Shift split (Appendix formula): round the first two shifts to their target
        # proportion, the last shift takes the remainder so the total is preserved.
        q1 = int(round(p_day[0] * total_demand))
        q2 = int(round(p_day[1] * total_demand))
        q3 = total_demand - q1 - q2
        if q3 < 0:  # safety for extreme proportions/rounding
            q3 = 0
            q2 = total_demand - q1

        demand_dict[(day, 1)] = q1
        demand_dict[(day, 2)] = q2
        demand_dict[(day, 3)] = q3

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

