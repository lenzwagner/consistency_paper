import numpy as np
from typing import List, Dict, Tuple, Any

def calculate_gini(values: List[float]) -> float:
    """
    Calculate the Gini coefficient of a list of values.
    0 = absolute equality, 1 = absolute inequality.
    """
    values = np.array(values, dtype=np.float64)
    if len(values) == 0 or np.sum(values) == 0:
        return 0.0
    
    # Sort values
    sorted_values = np.sort(values)
    n = len(values)
    
    # Gini formula: (2 * sum(i * x_i) / (n * sum(x_i))) - (n + 1) / n
    # where i is 1-indexed
    index = np.arange(1, n + 1)
    return (2.0 * np.sum(index * sorted_values) / (n * np.sum(sorted_values))) - (n + 1.0) / n

def calculate_cv(values: List[float]) -> float:
    """Calculate coefficient of variation (std/mean)."""
    values = np.array(values, dtype=np.float64)
    mean = np.mean(values)
    if len(values) == 0 or mean == 0:
        return 0.0
    return np.std(values) / mean

def calculate_90_10_ratio(values: List[float]) -> float:
    """Calculate ratio of 90th to 10th percentile."""
    values = np.array(values, dtype=np.float64)
    if len(values) == 0:
        return 0.0
    p90 = np.percentile(values, 90)
    p10 = np.percentile(values, 10)
    return p90 / p10 if p10 > 0 else float('inf')

def calculate_disutility_index(values: List[float]) -> float:
    """
    Level-and-inequality-adjusted score for "less is better" quantities
    (e.g. shift changes, performance loss): mean * (1 + Gini).
    Lower is better on both the level (mean) and the equality (Gini) dimension.
    """
    values = np.array(values, dtype=np.float64)
    if len(values) == 0:
        return 0.0
    return float(np.mean(values) * (1.0 + calculate_gini(values)))

def calculate_top_share(values: List[float], frac: float = 0.1) -> float:
    """
    Share of the total borne by the top `frac` (e.g. 10%) most-burdened workers.
    At least one worker is always included, even if frac * n < 1.
    """
    values = np.array(values, dtype=np.float64)
    n = len(values)
    if n == 0:
        return 0.0
    total = np.sum(values)
    if total <= 0:
        return 0.0
    n_top = max(1, int(np.ceil(frac * n)))
    top_sum = np.sum(np.sort(values)[-n_top:])
    return float(top_sum / total)

def evaluate_inequality(lst: List[float], T: int, n_workers_given: int = None) -> Tuple[Dict[int, float], float, float, float, float, float]:
    """
    Evaluate inequality metrics (spread, load share, gini, disutility, top-10% share)
    for a flattened list of assignments.

    Args:
        lst: Flattened list of values (e.g., shift changes per day per worker)
        T: Horizon length (days)
        n_workers_given: Number of workers. If None, calculated from list length.

    Returns:
        tuple: (worker_totals_dict, spread, load_share, gini, disutility, top10_share)
    """
    if n_workers_given is None:
        n_workers = int(np.ceil(len(lst) / T))
    else:
        n_workers = n_workers_given

    # Calculate totals per worker
    worker_totals = {}
    for i in range(n_workers):
        start = i * T
        end = min((i + 1) * T, len(lst))
        worker_totals[i + 1] = sum(lst[start:end])

    values = list(worker_totals.values())
    total_sum = sum(values)

    spread = max(values) - min(values) if values else 0.0
    load_share = round(max(values) / total_sum, 3) if total_sum > 0 else 0.0
    gini = calculate_gini(values)
    disutility = calculate_disutility_index(values)
    top10_share = calculate_top_share(values, frac=0.1)

    return worker_totals, round(spread, 3), load_share, round(gini, 3), round(disutility, 3), round(top10_share, 3)

def calculate_group_metrics(
    ls_sc: List[float], 
    ls_perf: List[float], 
    worker_groups: Any, 
    n_days: int, 
    n_shifts: int = 3
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, float]]:
    """
    Calculate detailed metrics per worker group.
    
    Args:
        ls_sc: List of shift changes (flattened: worker * days)
        ls_perf: List of performance values (flattened: worker * days * shifts)
        worker_groups: Dictionary of WorkerGroup objects
        n_days: Horizon length
        n_shifts: Number of shifts
        
    Returns:
        tuple: (group_metrics_dict, global_fairness_dict)
    """
    group_metrics = {}
    all_perf_losses = []
    all_shift_changes = []
    
    for group_name, group in worker_groups.items():
        group_sc = []
        group_perf_loss = []
        
        for worker_id in group.worker_ids:
            w_idx = worker_id - 1
            
            # Shift changes
            sc_start = w_idx * n_days
            sc_end = sc_start + n_days
            if sc_end <= len(ls_sc):
                worker_sc = sum(ls_sc[sc_start:sc_end])
                group_sc.append(worker_sc)
                all_shift_changes.append(worker_sc)
            
            # Performance loss
            perf_start = w_idx * n_days * n_shifts
            perf_end = perf_start + n_days * n_shifts
            if perf_end <= len(ls_perf):
                worker_perf = ls_perf[perf_start:perf_end]
                # Loss = Σ(1-p) for shifts worked (p>0)
                loss = sum(1.0 - p for p in worker_perf if p > 0)
                group_perf_loss.append(loss)
                all_perf_losses.append(loss)
        
        group_metrics[group_name] = {
            'epsilon': group.epsilon,
            'chi': group.chi,
            'n_workers': len(group.worker_ids),
            'total_shift_changes': sum(group_sc),
            'avg_shift_changes': np.mean(group_sc) if group_sc else 0,
            'std_shift_changes': np.std(group_sc) if group_sc else 0,
            'min_shift_changes': min(group_sc) if group_sc else 0,
            'max_shift_changes': max(group_sc) if group_sc else 0,
            'total_perf_loss': sum(group_perf_loss),
            'avg_perf_loss': np.mean(group_perf_loss) if group_perf_loss else 0,
            'std_perf_loss': np.std(group_perf_loss) if group_perf_loss else 0,
            'min_perf_loss': min(group_perf_loss) if group_perf_loss else 0,
            'max_perf_loss': max(group_perf_loss) if group_perf_loss else 0,
        }
    
    fairness = {
        'gini_perf_loss': calculate_gini(all_perf_losses),
        'gini_shift_changes': calculate_gini(all_shift_changes),
        'cv_perf_loss': calculate_cv(all_perf_losses),
        'cv_shift_changes': calculate_cv(all_shift_changes),
        'ratio_90_10_perf': calculate_90_10_ratio(all_perf_losses),
        'ratio_90_10_sc': calculate_90_10_ratio(all_shift_changes),
    }
    
    return group_metrics, fairness

def compute_horizon_stability_metrics(
    p_list: List[float],
    n_workers: int,
    n_days: int,
    tau: float = 0.9,
    k: int = 7,
) -> Dict[str, Any]:
    """
    End-of-horizon performance stability proxies (used in the demand-regime /
    exhaustion analysis): mean daily performance, end-of-horizon performance,
    the share of workers below a performance floor at the end, and the number
    of low-performance days in the final k-day window.

    Args:
        p_list: Flattened per-worker, per-day continuous performance state
            (worker-major layout, length n_workers * n_days) -- this is the
            "p_list_*"/"ls_p" list already exported by the CG functions
            (subproblem.getOptP(), i.e. p_{id} regardless of whether the
            worker is actually scheduled that day).
        n_workers: Number of workers.
        n_days: Horizon length.
        tau: Performance floor for B^end_tau / L^tail_tau.
        k: Window size (days) for L^tail_tau.

    Returns:
        dict with keys: p_bar_d (list, length n_days), p_end, b_end_tau, l_tail_tau
    """
    p = np.array(p_list, dtype=np.float64).reshape(n_workers, n_days)

    p_bar_d = p.mean(axis=0)  # average across workers, per day
    p_end = float(p_bar_d[-1])
    b_end_tau = float(np.mean(p[:, -1] < tau))

    window = p_bar_d[-k:] if n_days >= k else p_bar_d
    l_tail_tau = int(np.sum(window < tau))

    return {
        'p_bar_d': p_bar_d.tolist(),
        'p_end': round(p_end, 5),
        'b_end_tau': round(b_end_tau, 5),
        'l_tail_tau': l_tail_tau,
    }

def compute_autocorrelation(series: List[float], lag: int) -> float:
    """Compute autocorrelation for a series at a specific lag."""
    series = np.array(series)
    n = len(series)
    if lag >= n or n <= 1:
        return 0.0
    
    mean = np.mean(series)
    var = np.var(series)
    if var == 0:
        return 0.0
        
    cov = np.sum((series[:n - lag] - mean) * (series[lag:] - mean)) / n
    return float(cov / var)
