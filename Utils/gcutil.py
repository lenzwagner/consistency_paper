from itertools import chain
import random
import math
import numpy as np
import pandas as pd

def generate_dict_from_excel(file_path, value_I, pattern, scenario):

    data = pd.read_excel(file_path)

    filtered_row = data[(data['I'] == value_I) & (data['Pattern'] == pattern) & (data['Scenario'] == scenario) ]

    if not filtered_row.empty:
        result_dict = {
            tuple(map(int, col.split(','))): filtered_row[col].values[0]
            for col in data.columns if ',' in col
        }
        return result_dict
    else:
        print("No data.")
        return {}

# evaluate_inequality has been moved to Utils.metrics


# **** Print Results Table ****
def printResults(itr, total_time, time_problem, nr, optimal_ip, optimal_lp, lagranigan_bound, compact_obj, step):
    lb = analytical_lb(optimal_lp, step, optimal_ip)
    gap_percentage = round((optimal_ip - compact_obj) / compact_obj, 2) * 100
    gap_percentage_str = str(gap_percentage) if gap_percentage != -0.0 else "0.0"

    print("*" * (nr + 2))
    print("*{:^{nr}}*".format("******* Results *******", nr=nr))
    print("*{:^{nr}}*".format("", nr=nr))
    print("*{:^{nr}}*".format("Total Column Generation iterations: " + str(itr), nr=nr))
    print("*{:^{nr}}*".format("Total elapsed time: " + str(round((total_time), 4)) + " seconds", nr=nr))
    print("*{:^{nr}}*".format("Final Integer Column Generation solution: " + str(round(optimal_ip, 4)), nr=nr))
    print("*{:^{nr}}*".format("Final Compact solution: " + str(round(compact_obj, 4)), nr=nr))
    print("*{:^{nr}}*".format("IP-Optimality Gap: " + gap_percentage_str+ "%", nr=nr))

    print("*{:^{nr}}*".format("", nr=nr))
    print("*{:^{nr}}*".format("The LP Relaxation (Lower Bound) is: " + str(round(optimal_lp, 4)), nr=nr))
    print("*{:^{nr}}*".format("The Analytical Lower Bound is: " + str(round(lb, 4)), nr=nr))
    print("*{:^{nr}}*".format("The Lagrangian Bound is: " + str(round(lagranigan_bound, 4)), nr=nr))


    gap = round((((optimal_ip - optimal_lp) / optimal_lp) * 100), 3)
    gap = 0.0 if abs(gap) < 1e-9 else gap
    gap_str = f"{gap}%"

    print("*{:^{nr}}*".format("LP-Optimality GAP: " + str(gap_str), nr=nr))
    if gap != 0:
        print("*{:^{nr}}*".format("Column Generation does not prove the global optimal solution!", nr=nr))
    print("*{:^{nr}}*".format("", nr=nr))
    print("*{:^{nr}}*".format("Solving Times:", nr=nr))
    print("*{:^{nr}}*".format(f"Time Column Generation: {round(total_time, 4)} seconds", nr=nr))
    print("*{:^{nr}}*".format(f"Time Compact Solver: {round(time_problem, 4)} seconds", nr=nr))
    print("*{:^{nr}}*".format("", nr=nr))
    if round((total_time), 4) < time_problem:
        print("*{:^{nr}}*".format(
            "Column Generation is faster by " + str(round((time_problem - round((total_time), 4)), 4)) + " seconds,", nr=nr))
        print("*{:^{nr}}*".format(
            "which is " + str(round(((time_problem/ round(total_time, 4))-1)*100, 3)) + "% faster.", nr=nr))
    elif round((total_time), 4) > time_problem:
        print("*{:^{nr}}*".format(
            "Compact solver is faster by " + str(round((round((total_time), 4) - time_problem), 4)) + " seconds,", nr=nr))
        print("*{:^{nr}}*".format(
            "which is " + str(round((((round(total_time, 4)/ time_problem))-1)*100, 4)) + "% faster.", nr=nr))
    else:
        print("*{:^{nr}}*".format("Column Generation and compact solver are equally fast: " + str(time_problem) + " seconds", nr=nr))
    print("*" * (nr + 2))
    return gap


# **** Compare Roster ****
def ListComp(list1, list2, num):
    if list1 == list2:
        print("*" * (num + 2))
        print("*{:^{num}}*".format(f"***** Roster Check *****", num = num))
        print("*{:^{num}}*".format(f"Roster are the same!", num = num))
        print("*" * (num + 2))
    else:
        print("*" * (num + 2))
        print("*{:^{num}}*".format(f"***** Roster Check *****", num = num))
        print("*{:^{num}}*".format(f"Roster are not the same!", num = num))
        print("*" * (num + 2))

# **** Get x-values ****
def get_physician_schedules(Iter_schedules, lambdas, I):
    physician_schedules = []
    flat_physician_schedules = []

    for i in I:
        physician_schedule = []
        for r, schedule in enumerate(Iter_schedules[f"Physician_{i}"]):
            if (i, r + 2) in lambdas and lambdas[(i, r + 2)] == 1:
                physician_schedule.append(schedule)
        physician_schedules.append(physician_schedule)
        flat_physician_schedules.extend(physician_schedule)

    flat_x = list(chain(*flat_physician_schedules))
    return flat_x

# **** Get perf-values ****
def get_physician_perf_schedules(Iter_perf_schedules, lambdas, I):
    physician_schedules = []
    flat_physician_schedules = []

    for i in I:
        physician_schedule = []
        for r, schedule in enumerate(Iter_perf_schedules[f"Physician_{i}"]):
            if (i, r + 1) in lambdas and lambdas[(i, r + 1)] == 1:
                physician_schedule.append(schedule)
        physician_schedules.append(physician_schedule)
        flat_physician_schedules.extend(physician_schedule)

    flat_perf = list(chain(*flat_physician_schedules))
    return flat_perf


def get_nurse_schedules(Iter_schedules, lambdas, I_list):
    nurse_schedules = []
    flat_nurse_schedules = []

    for i in I_list:
        nurse_schedule = []
        for r, schedule in enumerate(Iter_schedules[f"Physician_{i}"]):
            if (i, r + 1) in lambdas and lambdas[(i, r + 1)] == 1:
                nurse_schedule.append(schedule)
        nurse_schedules.append(nurse_schedule)
        flat_nurse_schedules.extend(nurse_schedule)

    flat = list(chain(*flat_nurse_schedules))
    return flat

def get_consistency(Schedules, lambdas, I):
    physician_schedules = []
    flat_physician_schedules = []

    for i in I:
        physician_schedule = []
        for r, schedule in enumerate(Schedules[f"Physician_{i}"]):
            if (i, r + 1) in lambdas and lambdas[(i, r + 1)] == 1:
                physician_schedule.append(schedule)
        physician_schedules.append(physician_schedule)
        flat_physician_schedules.extend(physician_schedule)

    flat_cons = list(chain(*flat_physician_schedules))
    return flat_cons

# **** List comparison ****
def list_diff_sum(list1, list2):
    result = []

    for i in range(len(list1)):
        diff = list1[i] - list2[i]
        if diff == 0:
            result.append(0)
        else:
            result.append(1)

    return result

# **** Optimality Check ****
def is_Opt(seed, final_obj_cg, obj_val_problem, nr):
    is_optimal = {}
    diff = round(final_obj_cg, 3) - round(obj_val_problem, 3)

    if diff == 0:
        is_optimal[(seed)] = 1
    else:
        is_optimal[(seed)] = 0

    print("*" * (nr + 2))
    print("*{:^{nr}}*".format("Is optimal?", nr=nr))
    print("*{:^{nr}}*".format("1: Yes ", nr=nr))
    print("*{:^{nr}}*".format("0: No", nr=nr))
    print("*{:^{nr}}*".format("", nr=nr))
    print("*{:^{nr}}*".format(f" {is_optimal}", nr=nr))
    print("*" * (nr + 2))

    return is_optimal

# **** Remove unnecessary variables ****
def remove_vars(master, I_list, T_list, K_list, last_itr, max_itr):
    for i in I_list:
        for t in T_list:
            for s in K_list:
                for r in range(last_itr + 1, max_itr + 2):
                    var_name = f"motivation_i[{i},{t},{s},{r}]"
                    var = master.model.getVarByName(var_name)
                    master.model.remove(var)
                    master.model.update()

def create_demand_dict(num_days, total_demand):
    demand_dict = {}

    for day in range(1, num_days + 1):
        remaining_demand = total_demand
        shifts = [0, 0, 0]

        while remaining_demand > 0:
            shift_idx = random.randint(0, 2)
            shift_demand = min(remaining_demand, random.randint(0, remaining_demand))
            shifts[shift_idx] += shift_demand
            remaining_demand -= shift_demand

        for i in range(3):
            shifts[i] = round(shifts[i])
            demand_dict[(day, i + 1)] = shifts[i]

    return demand_dict

def demand_dict_fifty(num_days, prob, demand):
    total_demand = int(prob * demand)
    demand_dict = {}

    for day in range(1, num_days + 1):
        middle_shift_ratio = random.random()
        middle_shift_demand = round(total_demand * middle_shift_ratio)
        remaining_demand = total_demand - middle_shift_demand
        early_shift_ratio = random.random()
        early_shift_demand = round(remaining_demand * early_shift_ratio)
        late_shift_demand = remaining_demand - early_shift_demand

        demand_dict[(day, 1)] = early_shift_demand
        demand_dict[(day, 2)] = middle_shift_demand
        demand_dict[(day, 3)] = late_shift_demand

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

# **** Generate random pattern ****
def generate_cost(num_days, phys, K):
    cost = {}
    shifts = range(1, K + 1)
    for day in range(1, num_days + 1):
        num_costs = phys
        for shift in shifts[:-1]:
            shift_cost = random.randrange(0, num_costs)
            cost[(day, shift)] = shift_cost
            num_costs -= shift_cost
        cost[(day, shifts[-1])] = num_costs
    return cost


def plotPerformanceList2(dicts, dict_phys, I, max_itr):
    final_list = []

    for i in I:
        r_selected = None
        for r in range(1, max_itr + 2):

            if dicts.get((i, r)) == 1.0:
                r_selected = r - 1
                break

        if r_selected is not None:
            person_key = f'Physician_{i}'
            dict_selected = dict_phys[person_key][r_selected]
            final_list.extend(list(dict_selected.values()))

    return final_list

def create_perf_dict(lst, index, days, shift):
    sublist_length = len(lst) // index
    sublists = [lst[i * sublist_length:(i + 1) * sublist_length] for i in range(index)]
    result_dict = {}

    for i, sublist in enumerate(sublists):
        for d in range(1, days + 1):
            for s in range(1, shift + 1):
                index_key = (i + 1, d, s)

                value = sublist[(d - 1) * shift + (s - 1)]

                result_dict[index_key] = value

    return result_dict

def create_individual_working_list(phys, min_val, max_val, mean_val):
    random_list = []

    for _ in range(phys):
        values = list(range(min_val, max_val + 1))
        probs = [1 / (abs(val - mean_val) + 1) for val in values]
        norm_probs = [prob / sum(probs) for prob in probs]

        random_value = random.choices(values, weights=norm_probs)[0]

        random_list.append(random_value)

    return random_list

def analytical_lb(optimal_lp, step, optimal_ip):
    current_value = optimal_ip
    while current_value > optimal_lp:
        current_value -= step
        if current_value <= optimal_lp:
            return current_value + step
    return optimal_ip

def total_consistency(lm1, lm2):
    print(f"lm1: {lm1}")
    print(f"lm2: {lm2}")

    selected_lists = []
    for physician, lists in lm2.items():
        for i, l in enumerate(lists):
            iteration = i + 1
            for key, value in lm1.items():
                if key[0] == int(physician[-1]) and key[1] == iteration and value == 1:
                    selected_lists.append(l)
                    break
    total_value = 0
    for l in selected_lists:
        for key, value in l.items():
            total_value += value
    return total_value, selected_lists

def create_schedule_dict(start_values, physician_indices, time_indices, shift_indices=None):
    schedule_dict = {}
    index = 1
    if shift_indices is None:
        schedule_dict[f"Physician_{index}"] = [{(t): start_values[(t)] for t in time_indices}]
    else:
        schedule_dict[f"Physician_{index}"] = [{(t, s): start_values[(t, s)] for t in time_indices for s in shift_indices}]
    return schedule_dict

def plotPerformanceList(dict_a, dict_b):
    result_list = []

    for key, value in dict_b.items():
        if value == 1.0:
            if f"Physician_1" in dict_a:
                result_list.extend(list(dict_a[f"Physician_1"][key - 1].values()))
        elif value > 1.0:
            if f"Physician_1" in dict_a:
                for _ in range(int(value)):
                    result_list.extend(list(dict_a[f"Physician_1"][key - 1].values()))

    return result_list

def calculate_stats(values):
    if not values:  # Check for empty list
        return None, None, None, None
    min_value = min(values)
    max_value = max(values)
    mean_value = sum(values) / len(values)
    std_dev = math.sqrt(sum((x - mean_value) ** 2 for x in values) / len(values))
    return min_value, max_value, mean_value, std_dev

def process_LSR(LSR, num_sublists):
    sublist_length = len(LSR) // num_sublists
    sublists = [LSR[i:i + sublist_length] for i in range(0, len(LSR), sublist_length)]

    first_ones = []
    last_ones = []
    avg_ones = []

    for sublist in sublists:
        subdict = {i + 1: value for i, value in enumerate(sublist)}

        first_one = next((k for k, v in subdict.items() if v == 1), None)
        if first_one:
            first_ones.append(first_one)

        last_one = max((k for k, v in subdict.items() if v == 1), default=None)
        if last_one:
            last_ones.append(last_one)

        ones_keys = [k for k, v in subdict.items() if v == 1]
        if ones_keys:
            avg_ones.append(sum(ones_keys) / len(ones_keys))

    first_stats = calculate_stats(first_ones)
    last_stats = calculate_stats(last_ones)
    avg_stats = calculate_stats(avg_ones)

    stats = [
        first_stats,
        last_stats,
        avg_stats
    ]

    return stats

def format_LSR_stats(LSR, n=100):
    stats = process_LSR(LSR, n)
    formatted_stats = [
        tuple(round(val, 2) if isinstance(val, float) else val for val in stat)
        for stat in stats
    ]
    return formatted_stats

def process_recovery(input_list, chi, length):
    sublists = [input_list[i:i + length] for i in range(0, len(input_list), length)]

    result = []
    for sublist in sublists:
        new_sublist = [0.0] * chi

        for i in range(chi, len(sublist)):
            if any(sublist[max(0, i - chi):i+1]):
                new_sublist.append(0.0)
            else:
                new_sublist.append(1.0)

        result.extend(new_sublist)

    return result


def combine_lists(ls1, ls2, days, worker):
    new_list = []
    limit = days * worker

    for a, b in zip(ls1, ls2):
        if len(new_list) >= limit:
            break

        a_val = bool(a)
        b_val = bool(b)

        if not a_val and not b_val:
            new_list.append(0)
        elif a_val and not b_val:
            new_list.append(1)
        elif not a_val and b_val:
            new_list.append(2)
        elif a_val and b_val:
            new_list.append(3)

    return new_list

def process_list_shuffle(input_list, T):
    sublists = [input_list[i:i + T] for i in range(0, len(input_list), T)]
    random.shuffle(sublists)  # Shuffle the sublists randomly
    flat_list = [item for sublist in sublists for item in sublist]
    return flat_list

import matplotlib.pyplot as plt
def analyze_and_plot_blocks(raw_data, num_workers, num_days, num_shifts, plt_show = False):
    """
    Analyzes a flat list of shift assignments to calculate lengths of consistent shift blocks
    and plots a histogram.

    Args:
    raw_data (list): Flattened list of binary shift assignments.
    num_workers (int): Number of workers.
    num_days (int): Number of days.
    num_shifts (int): Number of shift types per day.

    Returns:
    list: A list containing the lengths of all identified consistent shift blocks.
    """

    # 1. Reshape and Decode Data
    worker_schedules = []
    current_index = 0

    for w in range(num_workers):
        daily_shifts = []
        for d in range(num_days):
            # Extract the triplet (or tuple of size num_shifts) for this day
            # Data is expected to be: [w1_d1_s1, w1_d1_s2, ..., w1_d2_s1, ...]
            if current_index + num_shifts > len(raw_data):
                break  # Safety break

            day_data = raw_data[current_index: current_index + num_shifts]
            current_index += num_shifts

            # Determine shift ID (0 = Free, 1..N = Shift Type)
            shift_id = 0
            for i, val in enumerate(day_data):
                if val == 1.0:
                    shift_id = i + 1
                    break
            daily_shifts.append(shift_id)
        worker_schedules.append(daily_shifts)

    # 2. Calculate Block Lengths
    all_block_lengths = []

    for schedule in worker_schedules:
        current_len = 0
        last_shift = -1

        for shift in schedule:
            if shift == 0:  # Free/Off day breaks the consistency block
                if current_len > 0:
                    all_block_lengths.append(current_len)
                current_len = 0
                last_shift = -1
                continue

            if shift == last_shift:
                # Continue existing block
                current_len += 1
            else:
                # Shift type changed (but not to free): New block starts
                if current_len > 0:
                    all_block_lengths.append(current_len)
                current_len = 1
                last_shift = shift

        # Capture block if it ends at the very end of the schedule
        if current_len > 0:
            all_block_lengths.append(current_len)

    # 3. Plot Histogram
    if all_block_lengths:
        plt.figure(figsize=(8, 5))
        # Create bins centered on integers: 0.5, 1.5, 2.5, ...
        max_val = max(all_block_lengths)
        bins = np.arange(0.5, max_val + 1.5, 1)

        plt.hist(all_block_lengths, bins=bins, color='#4c72b0', edgecolor='white', rwidth=0.8)
        plt.title("Distribution of Block Lengths (Consistency Analysis)")
        plt.xlabel("Length of Consistent Block (Days)")
        plt.ylabel("Frequency")
        plt.xticks(range(1, max_val + 1))
        plt.grid(axis='y', alpha=0.5, linestyle='--')
        if plt_show == True:
            plt.show()
    else:
        print("No consistent work blocks found.")

    return all_block_lengths
