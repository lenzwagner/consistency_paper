"""Extension 3: alignment scenario -- does the BAP satisfy worker preferences
'for free' (i.e. at lambda_P=0, with NO explicit preference penalty), because
its behaviorally-motivated off-day placement happens to coincide with days
workers would prefer off anyway?

Operationalization of extensions.tex's three scenarios:
  (i)   random     -- preferred days sampled uniformly (baseline, no correlation)
  (ii)  aligned     -- preferred days sampled from the BAP's OWN off-day choices
                       at lambda_P=0 (mimics workers who self-select
                       recovery-beneficial off-days, extensions.tex Ext.3 setup)
  (iii) conflicting -- preferred days sampled from the highest-demand days

For each scenario, BAP and NPP are solved once at lambda_P=0 (no preference
penalty at all), and we report the REALIZED preference-satisfaction rate --
i.e. how often the schedule the policy would produce anyway already honors
the (unseen-by-the-optimizer) preference.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import random
import numpy as np
import pandas as pd
from core.worker_groups import create_groups_from_fractions
from Utils.demand import generate_demand
from extensions.preferences.loop_preferences import make_singleton_groups
from extensions.preferences.loop_preferences_labeling import run_cg as run_pref

MAX_ITR_TEST = 60

len_I, num_days, seed = 10, 14, 1
I = list(range(1, len_I + 1)); T = list(range(1, num_days + 1)); K = [1, 2, 3]
maxlen = max(len(I), len(T), len(K))
data = pd.DataFrame({'I': I + [np.nan]*(maxlen-len(I)),
                     'T': T + [np.nan]*(maxlen-len(T)),
                     'K': K + [np.nan]*(maxlen-len(K))})
demand_dict = generate_demand(num_days, 0.7, len_I, shift_probs=(25, 50, 25),
                              delta=0.25, seed=seed, prop_volatility=0.30)
worker_groups = create_groups_from_fractions(I, "1/2,1/2", [(0.5, 0.5, 2, 7), (1.5, 1.5, 4, 21)])
singleton_groups = make_singleton_groups(I, worker_groups)


def get_offdays_from_schedule(mode, pref_by_worker, lam_pref=0.0):
    """Solve once and return, per worker, the list of days on which they are OFF."""
    # We need the actual x-schedule; run_cg only returns aggregate metrics, so
    # call it once and separately re-extract off-days via a light re-solve
    # using the same run_cg internals is not exposed -- instead, monkey-patch
    # by importing the lower-level pieces used inside run_cg is overkill here;
    # simplest robust approach: reuse run_cg's returned satisfaction rate only
    # for the metrics, and separately reconstruct off-days from a raw BAP
    # solve with lam_pref=0 using the same singleton-group CG loop, capturing
    # x_by_group via a small local copy of run_cg's core loop.
    import gurobipy as gu
    from core.base_case import get_wd_constraints, K_ECP
    from core.masterproblem import MasterProblem
    from core.subproblem_dp_extensions import SubproblemPreferencesDP
    from core.solver_base import THRESHOLD, TIME_CG_INIT, TIME_CG_SP

    Min_WD_i, Max_WD_i = get_wd_constraints(I)
    start_perf = {(t, s): 0.0 for t in T for s in K}
    master = MasterProblem(data, demand_dict, MAX_ITR_TEST, 0, 0, 100, start_perf, worker_groups=singleton_groups)
    master.buildModel()
    master.setStartSolution()

    group_names = list(singleton_groups.keys())
    x_by_group = {g: {} for g in group_names}

    itr, col_idx, improvable = 0, 0, True
    while improvable and itr < MAX_ITR_TEST:
        master.model.Params.OutputFlag = 0
        master.model.optimize()
        duals_i, duals_ts = master.getDuals_i(), master.getDuals_ts()
        improvable = False
        for g_idx, (gname, group) in enumerate(singleton_groups.items(), start=1):
            wid = group.worker_ids[0]
            eps_sp = group.epsilon if mode == 'bap' else 0.0
            sp = SubproblemPreferencesDP(duals_i.get(g_idx, 0.0), duals_ts, data, wid, itr,
                                          eps_sp, Min_WD_i, Max_WD_i, group.chi,
                                          pref_by_worker.get(wid, []), lam_pref)
            if mode == 'bap':
                sp.gamma_C, sp.gamma_R, sp.alpha_R, sp.delta, sp.e_max = (
                    group.gamma_C, group.gamma_R, group.alpha_R, group.delta, group.e_max)
            else:
                sp.gamma_C, sp.gamma_R, sp.alpha_R, sp.e_max = 1.0, 1.0, 1.0, 0.0
                sp.delta = np.zeros((4, 4))
            sp.buildModel()
            sp.solveModelOpt(TIME_CG_INIT if itr == 0 else TIME_CG_SP)
            if sp.getStatus() != gu.GRB.OPTIMAL:
                continue
            rc = sp.model.objval
            if rc >= -THRESHOLD:
                continue
            col_idx += 1
            master.addLambda(col_idx - 1, g_idx)
            x_vals = sp.getOptX()
            col = {(t, s, col_idx): v for (t, s, _), v in sp.getNewSchedule().items()}
            master.addColumn(col_idx - 1, col, g_idx)
            x_by_group[gname][col_idx] = x_vals
            improvable = True
        itr += 1

    master.model.Params.OutputFlag = 0
    for v in master.lmbda.values():
        v.VType = gu.GRB.INTEGER
    master.model.optimize()

    offdays_by_worker = {}
    for g_idx, (gname, group) in enumerate(singleton_groups.items(), start=1):
        wid = group.worker_ids[0]
        for r in master.active_roster_by_group.get(g_idx, []):
            if (g_idx, r) not in master.lmbda or round(master.lmbda[(g_idx, r)].X) <= 0:
                continue
            x_sched = x_by_group[gname].get(r, {})
            offdays_by_worker[wid] = [t for t in T if all(x_sched.get((t, s), 0) <= 0.5 for s in K)]
            break
    return offdays_by_worker


def satisfaction_rate(pref_by_worker, offdays_by_worker):
    satisfied, total = 0, 0
    for wid, prefs in pref_by_worker.items():
        total += len(prefs)
        satisfied += sum(1 for d in prefs if d in offdays_by_worker.get(wid, []))
    return satisfied / total if total else 0.0


if __name__ == "__main__":
    random.seed(11)

    # Baseline BAP off-days at lambda_P=0 (no preferences at all yet), used to
    # construct the "aligned" scenario's preference sets.
    baseline_offdays = get_offdays_from_schedule("bap", {}, lam_pref=0.0)
    print("Baseline BAP off-days (no preferences):")
    for wid, days in baseline_offdays.items():
        print(f"  worker {wid}: {days}")

    demand_by_day = {t: sum(demand_dict[(t, s)] for s in K) for t in T}
    peak_days = sorted(T, key=lambda t: -demand_by_day[t])

    scenarios = {}
    scenarios["random"] = {w: random.sample(T, random.randint(1, 2)) for w in I}
    scenarios["aligned"] = {
        w: (random.sample(baseline_offdays[w], min(2, len(baseline_offdays[w])))
            if baseline_offdays.get(w) else random.sample(T, 1))
        for w in I
    }
    scenarios["conflicting"] = {w: random.sample(peak_days[:5], min(2, 5)) for w in I}

    print("\n" + "="*70)
    print("Preference satisfaction rate at lambda_P=0 (NO explicit penalty)")
    print("="*70)
    print(f"  {'scenario':>13} {'mode':>5} {'satisfaction_rate':>18}")
    for scen_name, pref_by_worker in scenarios.items():
        for mode in ("bap", "npp"):
            offdays = get_offdays_from_schedule(mode, {}, lam_pref=0.0)  # solved WITHOUT preference info
            rate = satisfaction_rate(pref_by_worker, offdays)
            print(f"  {scen_name:>13} {mode:>5} {rate:18.2f}", flush=True)
