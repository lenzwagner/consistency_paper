# Column Generation for Nurse Rostering with Performance Consistency

An optimization system for healthcare staff scheduling using Column Generation with performance-aware scheduling.

## Project Description

This project implements a Column Generation algorithm for solving Nurse Rostering Problems (NRP). The system optimizes schedule creation while accounting for performance degradation due to shift changes and recovery during stable shift sequences.

## Key Features

- **Performance-Aware Scheduling**: Models worker performance as a function of shift consistency
- **Column Generation**: Efficient decomposition approach for large-scale scheduling
- **Numba-Accelerated Labeling**: Fast dynamic programming solver using Numba JIT compilation
- **Flexible Demand Patterns**: Supports different demand scenarios (Low, Medium, High)

## Main Components

### Core Modules

- **masterproblem.py**: Restricted Master Problem implementation using Gurobi
- **subproblem.py**: MIP-based pricing problem for column generation
- **subproblem_dp.py**: Label-setting dynamic programming solver
- **subproblem_dp_optimized.py**: Numba-optimized DP solver with bidirectional labeling
- **subproblem_factory.py**: Factory pattern for subproblem solver selection

### Solution Approaches

- **cg_behavior.py**: Column Generation with performance consistency modeling
- **cg_naive.py**: Baseline Column Generation without performance modeling

### Heterogeneity Modules

- **worker_groups.py**: Worker grouping logic for heterogeneous performance parameters
- **loop_heterogeneity_analysis.py**: Analysis of heterogeneous worker populations
- **loop_heterogeneity_robustness.py**: Robustness analysis across sensitivity dimensions

### Utility Modules

- **Utils/setup.py**: Configuration and setup
- **Utils/demand.py**: Demand pattern generation
- **Utils/compactsolver.py**: Compact MIP formulation solver
- **Utils/aggundercover.py**: Undercoverage aggregation utilities

## Requirements

- Python 3.8+
- Gurobi Optimizer (license required)
- NumPy
- Pandas
- Numba
- openpyxl

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd columngeneration_consistency
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure Gurobi license

## Usage

### Basic Execution

```bash
python loop_cg.py
```

### Parameter Configuration

Key parameters can be adjusted in `loop_cg.py`:

- `epsilon`: Performance degradation per shift change (e.g., 0.06 = 6%)
- `chi`: Recovery threshold (consecutive days without shift change)
- `time_cg`: Time limit for column generation (seconds)
- `max_itr`: Maximum column generation iterations

## Algorithm

The system uses a Column Generation approach:

1. Solve the relaxed Master Problem (RMP)
2. Extract dual values (pi, gamma)
3. Solve pricing problems using Numba-accelerated DP
4. Add columns with negative reduced costs
5. Repeat until convergence
6. Solve final Integer Program

## Performance Model

The model captures:

- **Performance Degradation**: `P = 1 - ε × e` where e is effective shift changes
- **Shift Changes**: Detected when consecutive work days have different shifts
- **Recovery**: After χ+1 consecutive days without shift changes, performance recovers
- **Bounds**: ē and ê variables prevent infeasible performance values

## Constraints

The system enforces:

- Demand coverage per shift and day
- Min/Max consecutive workdays (2-5 days)
- Minimum rest days between work blocks (2 days)
- Forbidden shift sequences (night→early, night→late, late→early)
- Forward rotation for shift changes

## Output

Results are saved in:

- `results/`: Excel files with optimization results
- Metrics include: undercoverage, consistency, performance loss, Gini coefficients

## Project Structure

```
columngeneration_consistency/
├── masterproblem.py                   # Restricted Master Problem
├── subproblem.py                      # MIP pricing problem
├── subproblem_dp.py                   # DP label-setting solver
├── subproblem_dp_optimized.py         # Numba-optimized DP solver
├── subproblem_factory.py              # Solver factory
├── cg_behavior.py                     # CG with performance model
├── cg_naive.py                        # Baseline CG
├── loop_cg.py                         # Main execution script
├── loop_compact.py                    # Compact model execution
├── loop_heterogeneity_analysis.py     # Main execution script for worker heterogeneity
├── loop_heterogeneity_robustness.py   # Robustness analysis for heterogeneity
├── worker_groups.py                   # Worker heterogeneity modeling
├── data/                              # Input data (demand scenarios)
├── results/                           # Output results
└── Utils/                             # Utility functions
```

## License

This project is for research purposes.

## Contact

For questions or comments, please create an issue.
