import numpy as np
import math
import os
if os.environ.get("DISABLE_NUMBA") == "1":
    njit = lambda x: x
else:
    try:
        from numba import njit
    except ImportError:
        njit = lambda x: x

@njit
def h_func(nu, gamma_C):
    """Degradation multiplier C(nu;gamma_C) = nu^g - (nu-1)^g, matching Model.tex model:phi."""
    if nu < 1:
        return 0.0
    return nu**gamma_C - (nu - 1)**gamma_C

@njit
def r_func(rho, chi, gamma_R, alpha_R):
    """Recovery increment R(rho;gamma_R) = alpha_R[(rho-chi+1)^g - (rho-chi)^g],
    matching Model.tex model:phi. First eligible recovery day is rho = chi."""
    if rho < chi:
        return 0.0
    return alpha_R * ((rho - chi + 1)**gamma_R - (rho - chi)**gamma_R)

def evaluate_schedule_nl(x_dict, days, shifts, nl_spec):
    """
    Ex-post evaluation of a schedule using non-linear dynamics.
    x_dict: {(day, shift): binary}
    """
    epsilon = nl_spec['epsilon']
    chi = nl_spec['chi']
    gamma_R = nl_spec['gamma_R']
    gamma_C = nl_spec['gamma_C']
    alpha_R = nl_spec['alpha_R']
    delta = nl_spec['delta']
    e_max = nl_spec.get('e_max', 1.0)
    
    n_days = len(days)
    e = 0.0
    rho = 0
    nu = 0
    last_worked_shift = None
    
    perf_history = {}
    sc_history = {}
    r_history = {}
    e_history = {}
    rho_history = {}
    nu_history = {}
    
    for d_idx, day in enumerate(days):
        # Identify current shift
        curr_shift = 0
        for s in shifts:
            if x_dict.get((day, s), 0) > 0.5:
                curr_shift = s
                break
        
        if curr_shift > 0:
            # Shift change?
            if last_worked_shift is not None and curr_shift != last_worked_shift:
                c_new = 1
                nu += 1
                rho = 0
                # Degradation
                degrad = delta[last_worked_shift, curr_shift] * h_func(nu, gamma_C)
                e = min(e_max, e + degrad)
            else:
                c_new = 0
                nu = 0
                rho += 1
                # Recovery?
                recov = r_func(rho, chi, gamma_R, alpha_R)
                e = max(0.0, e - recov)
            
            last_worked_shift = curr_shift
            sc_history[day] = float(c_new)
        else:
            # Day off
            c_new = 0
            nu = 0
            rho += 1
            # Recovery?
            recov = r_func(rho, chi, gamma_R, alpha_R)
            e = max(0.0, e - recov)
            sc_history[day] = 0.0
            
        p = 1.0 - e
        perf_history[day] = p
        e_history[day] = e
        r_history[day] = 1.0 if (rho >= chi and c_new == 0) else 0.0
        rho_history[day] = rho
        nu_history[day] = nu

    return perf_history, sc_history, r_history, e_history, rho_history, nu_history

def generate_transitions_nl(epsilon, chi, omega_max, nl_spec):
    """
    Generate transition tables for Numba DP.
    """
    if nl_spec is None:
        return None
    
    delta_flat = nl_spec['delta'].flatten().astype(np.float64)
    
    return {
        'gamma_R': nl_spec['gamma_R'],
        'gamma_C': nl_spec['gamma_C'],
        'alpha_R': nl_spec['alpha_R'],
        'delta_flat': delta_flat,
        'e_max': nl_spec.get('e_max', 1.0)
    }
