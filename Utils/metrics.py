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

def evaluate_inequality(lst: List[float], T: int, n_workers_given: int = None) -> Tuple[Dict[int, float], float, float, float]:
    """
    Evaluate inequality metrics (spread, load share, gini) for a flattened list of assignments.
    
    Args:
        lst: Flattened list of values (e.g., shift changes per day per worker)
        T: Horizon length (days)
        n_workers_given: Number of workers. If None, calculated from list length.
        
    Returns:
        tuple: (worker_totals_dict, spread, load_share, gini)
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
    
    return worker_totals, round(spread, 3), load_share, round(gini, 3)

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
