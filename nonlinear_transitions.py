import numpy as np
import math
try:
    from numba import njit
except ImportError:
    njit = lambda x: x

def get_default_nl_spec(epsilon, chi):
    """
    Returns the non-linear specification as described in the paper.
    """
    # Table 7: Degradation Matrix Delta(s, s')
    # Indices: 0=Off, 1=Early, 2=Late, 3=Night
    # We use 1-based indexing for shifts E=1, L=2, N=3 to match the codebase.
    delta = np.zeros((4, 4))
    
    # E -> ...
    delta[1, 1] = 1.0 * epsilon
    delta[1, 2] = 1.2 * epsilon
    delta[1, 3] = 1.5 * epsilon
    
    # L -> ...
    delta[2, 1] = 2.5 * epsilon
    delta[2, 2] = 1.0 * epsilon
    delta[2, 3] = 1.2 * epsilon
    
    # N -> ...
    delta[3, 1] = 1.2 * epsilon
    delta[3, 2] = 1.5 * epsilon
    delta[3, 3] = 1.0 * epsilon
    
    return {
        'epsilon': epsilon,
        'chi': chi,
        'gamma_R': 0.5,    # Concave recovery
        'gamma_C': 1.25,   # Convex change effects
        'alpha_R': 0.04,   # Scaling for first recovery step
        'delta': delta,
        'e_max': 0.5       # Maximum admissible degradation (min perf = 0.5)
    }

@njit
def h_func(nu, gamma_C):
    """Non-linear shift change multiplier."""
    if nu < 1:
        return 0.0
    return nu**gamma_C - (nu - 1)**gamma_C

@njit
def r_func(rho, chi, gamma_R, alpha_R):
    """Non-linear recovery amount."""
    if rho <= chi:
        return 0.0
    return alpha_R * ((rho - chi)**gamma_R - (rho - chi - 1)**gamma_R)

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
                # delta[last_worked_shift, curr_shift]
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
        r_history[day] = 1.0 if (rho > chi and c_new == 0) else 0.0
        
    return perf_history, sc_history, r_history, e_history

def generate_transitions_nl(epsilon, chi, omega_max, nl_spec):
    """
    Generate transition tables for Numba DP.
    
    State transition: e' = e + delta * h(nu) - r(rho)
    
    Since e is continuous in the NL extension, we might need to discretize it 
    OR handle it differently.
    
    Wait, the user's provided text says:
    "the labeling algorithm stores the same information directly in each active label."
    
    If we use lookup tables, we need to map (e, rho, nu, s_prev, s_new) -> e'.
    
    However, for Numba, we can just calculate it directly if we don't want massive tables.
    But the user's text says: "embedded through finite lookup tables and binary selection variables."
    
    Let's provide the spec parameters to Numba.
    """
    if nl_spec is None:
        return None
    
    # We'll return the parameters and Delta matrix as flat arrays for Numba
    delta_flat = nl_spec['delta'].flatten().astype(np.float64)
    
    return {
        'gamma_R': nl_spec['gamma_R'],
        'gamma_C': nl_spec['gamma_C'],
        'alpha_R': nl_spec['alpha_R'],
        'delta_flat': delta_flat,
        'e_max': nl_spec.get('e_max', 1.0)
    }
