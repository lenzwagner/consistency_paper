"""
Worker Groups Module for Heterogeneous Column Generation.

Enables worker heterogeneity by allowing distinct (ε_g, χ_g) parameter tuples
for different worker groups via fraction-based input.
"""

from dataclasses import dataclass
from typing import List, Dict, Tuple
from fractions import Fraction


@dataclass
class WorkerGroup:
    """A group of workers with shared (epsilon, chi) parameters."""
    name: str
    epsilon: float
    chi: int
    worker_ids: List[int]


def parse_fractions(fraction_str: str) -> List[float]:
    """
    Parse a comma-separated fraction string into a list of floats.
    
    Args:
        fraction_str: String like "1/3,1/3,1/3" or "1/2,1/2"
        
    Returns:
        List of float values, e.g. [0.333, 0.333, 0.333]
        
    Example:
        >>> parse_fractions("1/3,1/3,1/3")
        [0.3333..., 0.3333..., 0.3333...]
    """
    parts = fraction_str.split(',')
    return [float(Fraction(p.strip())) for p in parts]


def create_groups_from_fractions(
    I: List[int],
    fraction_str: str,
    group_params: List[Tuple[float, int]]
) -> Dict[str, WorkerGroup]:
    """
    Split workers into groups by fractions. Remainder goes to first group.
    
    Args:
        I: List of worker IDs, e.g. [1, 2, 3, ..., 50]
        fraction_str: Proportional split, e.g. "1/3,1/3,1/3"
        group_params: List of (epsilon, chi) tuples for each group
        
    Returns:
        Dictionary mapping group name to WorkerGroup
        
    Example:
        I = [1..50], fraction_str = "1/3,1/3,1/3"
        -> Group 1: 18 workers (gets remainder), Group 2: 16, Group 3: 16
    """
    fractions = parse_fractions(fraction_str)
    
    if len(fractions) != len(group_params):
        raise ValueError(f"Number of fractions ({len(fractions)}) must match "
                        f"number of group_params ({len(group_params)})")
    
    n = len(I)
    sizes = [int(f * n) for f in fractions]
    remainder = n - sum(sizes)
    sizes[0] += remainder  # Remainder to first group
    
    groups = {}
    start = 0
    for i, (size, (eps, chi)) in enumerate(zip(sizes, group_params)):
        name = f"group_{i+1}"
        groups[name] = WorkerGroup(
            name=name,
            epsilon=eps,
            chi=chi,
            worker_ids=I[start:start+size]
        )
        start += size
    
    return groups


def create_homogeneous_group(I: List[int], eps: float, chi: int) -> Dict[str, WorkerGroup]:
    """
    Create a single group containing all workers (for backward compatibility).
    
    Args:
        I: List of worker IDs
        eps: Epsilon parameter for all workers
        chi: Chi parameter for all workers
        
    Returns:
        Dictionary with single 'all' group
    """
    return {'all': WorkerGroup('all', eps, chi, I)}


def get_worker_params(worker_groups: Dict[str, WorkerGroup]) -> Dict[int, Tuple[float, int]]:
    """
    Get (epsilon, chi) parameters for each worker.
    
    Args:
        worker_groups: Dictionary of worker groups
        
    Returns:
        Dictionary mapping worker_id -> (epsilon, chi)
    """
    params = {}
    for group in worker_groups.values():
        for worker_id in group.worker_ids:
            params[worker_id] = (group.epsilon, group.chi)
    return params


def evaluate_by_group(
    ls_sc: list, 
    ls_x: list, 
    ls_r: list, 
    ls_perf: list,
    worker_groups: Dict[str, WorkerGroup], 
    n_days: int,
    n_shifts: int = 3
) -> Dict[str, dict]:
    """
    Evaluate metrics separately per worker group.
    
    Args:
        ls_sc: List of shift change indicators (flattened: n_workers * n_days)
        ls_x: List of work assignments (flattened: n_workers * n_days * n_shifts)
        ls_r: List of recovery indicators (flattened: n_workers * n_days)
        ls_perf: List of performance values (flattened: n_workers * n_days * n_shifts)
        worker_groups: Dictionary of worker groups
        n_days: Number of days in planning horizon
        n_shifts: Number of shifts per day (default 3)
        
    Returns:
        Dictionary with per-group metrics
    """
    results = {}
    
    for group_name, group in worker_groups.items():
        # Calculate indices for this group
        # sc and r are indexed by (worker, day): size n_workers * n_days
        # x and perf are indexed by (worker, day, shift): size n_workers * n_days * n_shifts
        
        sc_indices = []
        r_indices = []
        x_indices = []
        perf_indices = []
        
        for worker_id in group.worker_ids:
            # Worker IDs are 1-indexed, array is 0-indexed
            w_idx = worker_id - 1
            
            # sc and r: one value per day per worker
            sc_start = w_idx * n_days
            sc_end = sc_start + n_days
            sc_indices.extend(range(sc_start, sc_end))
            r_indices.extend(range(sc_start, sc_end))
            
            # x and perf: n_shifts values per day per worker
            x_start = w_idx * n_days * n_shifts
            x_end = x_start + n_days * n_shifts
            x_indices.extend(range(x_start, x_end))
            perf_indices.extend(range(x_start, x_end))
        
        # Safely extract values (handle out of bounds)
        group_sc = [ls_sc[i] for i in sc_indices if i < len(ls_sc)]
        group_r = [ls_r[i] for i in r_indices if i < len(ls_r)]
        group_x = [ls_x[i] for i in x_indices if i < len(ls_x)]
        group_perf = [ls_perf[i] for i in perf_indices if i < len(ls_perf)]
        
        # Calculate metrics
        consistency = sum(group_sc)
        assignments = sum(1 for x in group_x if x > 0)
        recovery_days = sum(group_r)
        avg_perf = sum(group_perf) / len(group_perf) if group_perf else 0
        perf_loss = sum(1 - p for p in group_perf if p < 1)
        
        results[group_name] = {
            'consistency': consistency,
            'consistency_per_worker': round(consistency / len(group.worker_ids), 2),
            'assignments': assignments,
            'recovery_days': recovery_days,
            'avg_performance': round(avg_perf, 4),
            'perf_loss': round(perf_loss, 4),
            'n_workers': len(group.worker_ids),
            'epsilon': group.epsilon,
            'chi': group.chi
        }
    
    return results


def print_group_metrics(group_metrics: Dict[str, dict]):
    """Pretty print group metrics."""
    print("\n" + "="*80)
    print("PER-GROUP METRICS")
    print("="*80)
    for group_name, m in group_metrics.items():
        print(f"\n{group_name} (ε={m['epsilon']}, χ={m['chi']}, n={m['n_workers']}):")
        print(f"  Consistency:    {m['consistency']:5.0f}  ({m['consistency_per_worker']:.2f} per worker)")
        print(f"  Assignments:    {m['assignments']:5.0f}")
        print(f"  Recovery Days:  {m['recovery_days']:5.0f}")
        print(f"  Avg Perf:       {m['avg_performance']:.4f}")
        print(f"  Perf Loss:      {m['perf_loss']:.4f}")
    print("="*80 + "\n")
