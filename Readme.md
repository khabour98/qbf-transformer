# QBF Transformer

Bachelor's thesis project — **Johannes Kepler University Linz**, May 2026  
Author: **Mohamad Khabour**

A Python tool that automatically transforms QBF formulas in QDIMACS format, solves them using DepQBF and CAQE, and systematically measures runtime and code coverage.

---

## Overview

The tool implements a five-step experimental pipeline:

1. **Parse** — Read a `.qdimacs` formula via `QDIMACSParser`
2. **Transform** — Apply a truth-value-preserving operator to produce a mutant
3. **Solve** — Run DepQBF and CAQE on both the original and the mutant
4. **Measure** — Record runtime (`SolverTimer`) and code coverage (`CoverageAnalyzer`)
5. **Analyse** — Aggregate and visualise results (`ResultsManager`, Jupyter notebook)

Four transformation operators are implemented, each targeting a different internal solver mechanism:

| Operator | Effect |
|---|---|
| `TautologyInsertion` | Inserts a tautological clause |
| `PureLiteralGenerator` | Creates a pure literal (positive / negative / auto) |
| `UniversalReductionTrigger` | Forces universal reduction to fire |
| `BlockedClauseInsertion` | Inserts a blocked clause |

---

## Project Structure

```
.
├── main.py                          # Pipeline entry point
├── filter_benchmarks.py             # Utility: select benchmarks from QBFLIB
├── qbf_solver_analysis_notebook.ipynb  # Interactive plots & analysis
│
├── models/
│   ├── qbf_formula.py
│   ├── solver_result.py
│   ├── coverage_report.py
│   └── experiment_result.py
│
├── parser/
│   ├── qdimacs_parser.py
│   └── parse_error.py
│
├── operators/
│   ├── base_operator.py
│   ├── tautology_insertion.py
│   ├── pure_literal_generator.py
│   ├── universal_reduction_trigger.py
│   └── blocked_clause_insertion.py
│
├── solver/
│   ├── solver_runner.py
│   ├── solver_timer.py
│   └── coverage_analyzer.py
│
└── analysis/
    └── results_manager.py
```

---

## Requirements

- Python 3.10+
- [DepQBF](https://github.com/lonsing/depqbf) (compiled binary at `depqbf/depqbf`)
- [CAQE](https://github.com/ltentrup/caqe) (compiled binary on `$PATH` or configured)
- `gcov` (for code coverage measurement)

Install Python dependencies:

```bash
pip install -r requirements.txt
```

---

## Usage

### Run the full benchmark pipeline

```bash
python main.py --benchmark-dir benchmarks/
```

### Run a single formula with a specific operator

```bash
python main.py --formula benchmarks/example.qdimacs --operator tautology_insertion
```

### Filter benchmark formulas from QBFLIB

```bash
python filter_benchmarks.py --source /path/to/qbflib --output benchmarks/
```

### Interactive analysis

Open `qbf_solver_analysis_notebook.ipynb` in Jupyter to generate plots and explore results.

---

## Results

Results are saved to `results/experiments.csv`. Plots are written to `results/plots/`.

---

## Thesis

The full thesis (`main.pdf`) is included in the repository and documents the theoretical foundations, formal operator proofs, system architecture, and experimental evaluation.