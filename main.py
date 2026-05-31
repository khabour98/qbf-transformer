"""
Orchestriert den gesamten 5-Schritt-Ablauf für alle Benchmark-Formeln
und Transformationsoperatoren.

5-Schritt-Ablauf (aus der Bachelorarbeit):
    Schritt 1 - QBF-Formel nehmen       (Parser)
    Schritt 2 - Operator anwenden       (Operator -> Mutant)
    Schritt 3 - Solver löst Original + Mutant (SolverRunner)
    Schritt 4 - Laufzeit + Coverage messen    (SolverTimer, CoverageAnalyzer)
    Schritt 5 - Ergebnis analysieren          (ResultsManager, Plotter)
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from analysis.results_manager import ResultsManager
from models.coverage_report import CoverageReport
from models.experiment_result import ExperimentResult
from operators.base_operator import BaseOperator, OperatorError
from operators.blocked_clause_insertion import BlockedClauseInsertion
from operators.pure_literal_generator import PureLiteralGenerator
from operators.tautology_insertion import TautologyInsertion
from operators.universal_reduction_trigger import UniversalReductionTrigger
from parser.qdimacs_parser import QDIMACSParser
from parser.parse_error import ParseError
from solver.coverage_analyzer import CoverageAnalyzer, CoverageError
from solver.solver_runner import SolverRunner, SolverNotFoundError


_ROOT = Path(__file__).parent
DEFAULT_BENCHMARK_DIR = str(_ROOT / "benchmarks")
DEFAULT_MUTANT_DIR    = str(_ROOT / "mutants")
DEFAULT_DEPQBF_SRC    = str(_ROOT / "depqbf")
DEFAULT_DEPQBF_BINARY = str(_ROOT / "depqbf" / "depqbf")
DEFAULT_RESULTS_CSV    = "results/experiments.csv"
DEFAULT_PLOTS_DIR      = "results/plots"
DEFAULT_RUNS           = 1
DEFAULT_TIMEOUT        = 60

# Alle verfügbaren Operatoren
ALL_OPERATORS: list[BaseOperator] = [
    TautologyInsertion(),
    PureLiteralGenerator(polarity="auto"),
    PureLiteralGenerator(polarity="positive"),
    PureLiteralGenerator(polarity="negative"),
    UniversalReductionTrigger(),
    BlockedClauseInsertion(),
    BlockedClauseInsertion(negate_literal=True),
    BlockedClauseInsertion(literal_var_index=1),
]


class Pipeline:
    """
    Orchestriert den vollständigen QBF-Transformations-Experiment-Ablauf.
    """

    def __init__(
        self,
        runs: int = DEFAULT_RUNS,
        timeout: float = DEFAULT_TIMEOUT,
        depqbf_src_dir: str = DEFAULT_DEPQBF_SRC,
        depqbf_binary: str = DEFAULT_DEPQBF_BINARY,
        results_csv: str = DEFAULT_RESULTS_CSV,
        mutant_dir: str = DEFAULT_MUTANT_DIR,
        enable_coverage: bool = True,
        skip_duplicates: bool = True,
    ) -> None:
        self.runs            = runs
        self.timeout         = timeout
        self.enable_coverage = enable_coverage
        self.skip_duplicates = skip_duplicates

        self.parser   = QDIMACSParser()
        self.runner   = SolverRunner(runs=runs, timeout=timeout)
        self.analyzer = CoverageAnalyzer(
            depqbf_src_dir=depqbf_src_dir,
            depqbf_binary=depqbf_binary,
            timeout=timeout,
        )
        self.manager  = ResultsManager(csv_path=results_csv)
        self.mutant_dir = Path(mutant_dir)
        self.mutant_dir.mkdir(parents=True, exist_ok=True)

        # FIX: Duplikat-Set einmal beim Start laden statt bei jedem Experiment
        # -> verhindert O(n^2) Performance bei grossen Experimenten
        self._duplicate_keys: set[tuple[str, str, str]] = set()

    # Setup

    def setup(self) -> bool:
        """
        Prüft ob alle Voraussetzungen für die Pipeline erfüllt sind.
        """
        print("=" * 60)
        print("Pipeline Setup — Environment Check")
        print("=" * 60)

        all_ok = True

        # Solver prüfen
        for solver in ["depqbf", "caqe"]:
            try:
                self.runner._check_solver_available(solver)
                print(f"  [OK] {solver} found")
            except SolverNotFoundError as e:
                print(f"  [ERROR] {e}")
                all_ok = False

        # Coverage prüfen
        if self.enable_coverage:
            problems = self.analyzer.check_setup()
            if problems:
                for p in problems:
                    print(f"  [WARNUNG] {p}")
                print("  Coverage-Messung wird deaktiviert.")
                self.enable_coverage = False
            else:
                print("  [OK] gcov available and DepQBF instrumented")
                self._verify_coverage_works()

        # Benchmark-Verzeichnis
        benchmark_dir = Path(DEFAULT_BENCHMARK_DIR)
        if not benchmark_dir.exists():
            print(f"  [WARNING] Benchmark directory '{benchmark_dir}' not found.")
        else:
            formulas = list(benchmark_dir.glob("**/*.qdimacs"))
            print(f"  [OK] {len(formulas)} benchmark formula(s) found")

        # Duplikat-Index aufbauen
        if self.skip_duplicates:
            self._build_duplicate_index()
            print(f"  [OK] Duplicate index: {len(self._duplicate_keys)} existing experiments")

        print("=" * 60)
        return all_ok

    def _verify_coverage_works(self) -> None:
        """
        Prüft ob DepQBF wirklich .gcda Dateien schreibt.
        Gibt Warnung aus wenn nicht — deutet auf fehlende Coverage-Flags hin.
        """
        import glob
        import subprocess

        gcda_pattern = str(self.analyzer.depqbf_src_dir / "**" / "*.gcda")

        try:
            # Snapshot VOR dem Aufruf
            gcda_before = set(glob.glob(gcda_pattern, recursive=True))

            # DepQBF mit leerem Input aufrufen — erzeugt trotzdem .gcda Dateien
            # wenn die Coverage-Flags gesetzt sind
            subprocess.run(
                [str(self.analyzer.depqbf_binary), "/dev/null"],
                capture_output=True,
                timeout=5,
            )

            # Snapshot NACH dem Aufruf
            gcda_after = set(glob.glob(gcda_pattern, recursive=True))

            # Vergleich: neue oder veränderte .gcda-Dateien?
            new_gcda = gcda_after - gcda_before
            if not gcda_after:
                print(
                    "  [WARNING] No .gcda files found after DepQBF run!\n"
                    "  DepQBF must be built with coverage flags:\n"
                    "    cd depqbf && make clean && "
                    "make CFLAGS='-fprofile-arcs -ftest-coverage -O0'"
                )
            elif not new_gcda and not gcda_before:
                # gcda_after hat Dateien, aber die gab es schon vorher — kein Beweis
                print(
                    "  [INFO] .gcda files exist but were not newly created. "
                    "Coverage instrumentation likely OK."
                )
            else:
                print(f"  [OK] Coverage instrumentation confirmed ({len(gcda_after)} .gcda files)")

        except FileNotFoundError:
            print(
                "  [WARNING] DepQBF binary not found during coverage check. "
                "Skipping instrumentation test."
            )
        except subprocess.TimeoutExpired:
            print("  [WARNING] DepQBF did not respond within 5s during coverage check.")
        except Exception as e:
            print(f"  [WARNING] Coverage verification failed unexpectedly: {e}")

    def _build_duplicate_index(self) -> None:
        """
        Lädt alle vorhandenen Experimente in ein Set für O(1)-Lookup.
        Muss nur einmal beim Start aufgerufen werden — nicht bei jedem Experiment.
        """
        df = self.manager.load_all()
        if df.empty:
            return
        for _, row in df.iterrows():
            key = (
                str(row.get("original_path", "")),
                str(row.get("operator", "")),
                str(row.get("mutant_path", "")),
            )
            self._duplicate_keys.add(key)

    def _is_duplicate(self, formula_path: str, operator: BaseOperator) -> bool:
        """
        O(1) Duplikat-Check gegen den vorgeladenen Index.
        """
        mutant_path = self._mutant_path(formula_path, operator.name())
        key = (formula_path, operator.name(), mutant_path)
        return key in self._duplicate_keys

    def _register_result(self, formula_path: str, operator: BaseOperator) -> None:
        """
        Trägt ein neues Experiment in den Duplikat-Index ein.
        """
        mutant_path = self._mutant_path(formula_path, operator.name())
        key = (formula_path, operator.name(), mutant_path)
        self._duplicate_keys.add(key)

    def run_single(
        self,
        formula_path: str,
        operator: BaseOperator,
    ) -> ExperimentResult | None:
        """
        Führt ein komplettes Experiment durch: eine Formel x ein Operator.

        Schritt 1: Formel parsen
        Schritt 2: Operator anwenden -> Mutant
        Schritt 3: Solver lösen (Original + Mutant, DepQBF + CAQE)
        Schritt 4: Coverage messen (Original + Mutant)
        Schritt 5: ExperimentResult erstellen und speichern
        """
        # Schritt 1: Formel parsen
        try:
            formula = self.parser.parse(formula_path)
        except (ParseError, FileNotFoundError) as e:
            print(f"  [PARSE ERROR] {e}")
            return None

        # Operator anwendbar?
        if not operator.is_applicable(formula):
            print(
                f"  [SKIP] {operator.name()} not applicable to "
                f"{Path(formula_path).name} "
                f"(no suitable pure literal / no matching variables)"
            )
            return None

        # Schritt 2: Operator anwenden -> Mutant
        try:
            mutant = operator.apply(formula)
        except OperatorError as e:
            print(f"  [OPERATOR ERROR] {e}")
            return None

        # FIX: Strukturelle Verifikation aufrufen (war vorher vorhanden aber korrekt)
        if not operator.verify(formula, mutant):
            print(
                f"  [VERIFY ERROR] {operator.name()} verify() failed "
                f"for {Path(formula_path).name}"
            )
            return None

        # Mutant speichern
        mutant_filename = self._mutant_path(formula_path, operator.name())
        mutant.save(mutant_filename)

        # Schritt 3: Solver
        try:
            depqbf_orig, depqbf_mut, caqe_orig, caqe_mut = (
                self.runner.run_both_solvers(formula_path, mutant_filename)
            )
        except (SolverNotFoundError, FileNotFoundError) as e:
            print(f"  [SOLVER ERROR] {e}")
            return None

        # Äquivalenz prüfen
        equivalent = self.runner.verify_equivalence(depqbf_orig, depqbf_mut)
        if not equivalent:
            print(
                f"  [EQUIVALENCE ERROR] {operator.name()} changed the truth value "
                f"for {Path(formula_path).name}! "
                f"Original={depqbf_orig.status}, Mutant={depqbf_mut.status}"
            )

        # Schritt 4: Coverage messen
        cov_original, cov_mutant = self._measure_coverage(
            formula_path, mutant_filename
        )

        # Schritt 5: Ergebnis speichern
        result = ExperimentResult(
            operator_name=operator.name(),
            original_path=formula_path,
            mutant_path=mutant_filename,
            depqbf_original=depqbf_orig,
            depqbf_mutant=depqbf_mut,
            caqe_original=caqe_orig,
            caqe_mutant=caqe_mut,
            coverage_original=cov_original,
            coverage_mutant=cov_mutant,
            equivalent=equivalent,
        )

        self.manager.save(result)
        self._register_result(formula_path, operator)
        return result

    # Schritt 4 intern
    def _measure_coverage(
        self,
        original_path: str,
        mutant_path: str,
    ) -> tuple[CoverageReport, CoverageReport]:
        """
        Misst gcov-Coverage für Original und Mutant.
        """
        empty = CoverageReport(0, 0, 0, 0)

        if not self.enable_coverage:
            return empty, empty

        try:
            # Original
            self.analyzer.reset_counters()
            self.analyzer.run_with_coverage(original_path)
            cov_original = self.analyzer.collect_coverage()

            # Warnung wenn Coverage leer
            if cov_original.is_empty():
                print(
                    "  [COVERAGE WARNING] Original produces empty coverage. "
                    "DepQBF must be built with '-fprofile-arcs -ftest-coverage'."
                )

            # Mutant
            self.analyzer.reset_counters()
            self.analyzer.run_with_coverage(mutant_path)
            cov_mutant = self.analyzer.collect_coverage()

            return cov_original, cov_mutant

        except CoverageError as e:
            print(f"  [COVERAGE ERROR] {e}")
            return empty, empty

    def run_all(
        self,
        benchmark_dir: str = DEFAULT_BENCHMARK_DIR,
        operators: list[BaseOperator] | None = None,
    ) -> None:
        """
        Führt alle Experimente durch: alle Benchmark-Formeln x alle Operatoren.
        """
        operators = operators or ALL_OPERATORS
        formulas  = sorted(Path(benchmark_dir).glob("**/*.qdimacs"))

        if not formulas:
            print(f"No .qdimacs files found in '{benchmark_dir}'.")
            return

        total    = len(formulas) * len(operators)
        done     = 0
        skipped  = 0
        errors   = 0
        start_ts = time.time()

        print(f"\nStarting {total} experiments "
              f"({len(formulas)} formulas x {len(operators)} operators)")
        print("=" * 70)

        for formula_path in formulas:
            for operator in operators:
                done += 1
                label = (
                    f"[{done:3d}/{total}] "
                    f"{operator.name():<40} "
                    f"{formula_path.name}"
                )

                # FIX: O(1) Duplikat-Check statt O(n) CSV-Reload
                if self.skip_duplicates and self._is_duplicate(
                    str(formula_path), operator
                ):
                    print(f"{label}  ->  [SKIP already exists]")
                    skipped += 1
                    continue

                result = self.run_single(str(formula_path), operator)

                if result is None:
                    # Unterscheide: nicht anwendbar vs echter Fehler
                    errors += 1
                    print(f"{label}  ->  [ERROR/SKIP]")
                else:
                    ratio = result.depqbf_time_ratio
                    delta = result.line_coverage_delta
                    equiv = "OK" if result.equivalent else "NOT EQUIVALENT"
                    print(
                        f"{label}  ->  "
                        f"ratio={ratio:.3f}  "
                        f"delta_line={delta:+.2f}%  "
                        f"[{equiv}]"
                    )

        elapsed = time.time() - start_ts
        print("=" * 70)
        print(f"Completed in {elapsed:.1f}s")
        print(f"  Total:        {total}")
        print(f"  Successful:   {total - errors - skipped}")
        print(f"  Skipped (duplicate):    {skipped}")
        print(f"  Skipped/Error (not applicable or failed): {errors}")
        print(f"  CSV:          {self.manager.csv_path}")

    # NEU (einsetzen):
    def create_plots(self) -> None:
        """Plots werden jetzt im Jupyter Notebook erstellt."""
        df = self.manager.load_all()
        if df.empty:
            print("No data in the CSV — run run_all() first.")
            return
        print(f"\nCSV ready: {len(df)} experiments in '{self.manager.csv_path}'")
        print("Create plots: jupyter notebook analysis/qbf_solver_analysis_notebook.ipynb")
        summary = self.manager.summary_by_operator()
        if not summary.empty:
            print("\nSummary per operator:")
            print(summary.to_string(index=False))

    def _mutant_path(self, formula_path: str, operator_name: str) -> str:
        stem = Path(formula_path).stem
        return str(self.mutant_dir / f"{stem}_{operator_name}.qdimacs")

    def __repr__(self) -> str:
        return (
            f"Pipeline("
            f"runs={self.runs}, "
            f"timeout={self.timeout}s, "
            f"coverage={self.enable_coverage})"
        )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="QBF Transformer — truth-preserving transformations",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--benchmark-dir", default=DEFAULT_BENCHMARK_DIR)
    parser.add_argument("--formula", default=None)
    parser.add_argument(
        "--operator", default=None,
        choices=[op.name() for op in ALL_OPERATORS],
    )
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument("--depqbf-src", default=DEFAULT_DEPQBF_SRC)
    parser.add_argument("--depqbf-binary", default=DEFAULT_DEPQBF_BINARY)
    parser.add_argument("--results-csv", default=DEFAULT_RESULTS_CSV)
    parser.add_argument("--no-coverage", action="store_true")
    parser.add_argument("--plots-only", action="store_true")
    parser.add_argument("--no-skip-duplicates", action="store_true")
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()

    pipeline = Pipeline(
        runs=args.runs,
        timeout=args.timeout,
        depqbf_src_dir=args.depqbf_src,
        depqbf_binary=args.depqbf_binary,
        results_csv=args.results_csv,
        enable_coverage=not args.no_coverage,
        skip_duplicates=not args.no_skip_duplicates,
    )

    if args.plots_only:
        pipeline.create_plots()
        return

    ok = pipeline.setup()
    if not ok:
        print("\nCritical errors found — pipeline will be aborted.")
        sys.exit(1)

    operators: list[BaseOperator] = ALL_OPERATORS
    if args.operator:
        operators = [op for op in ALL_OPERATORS if op.name() == args.operator]

    if args.formula:
        for operator in operators:
            result = pipeline.run_single(args.formula, operator)
            if result:
                print(result.summary())
    else:
        pipeline.run_all(
            benchmark_dir=args.benchmark_dir,
            operators=operators,
        )

    pipeline.create_plots()


if __name__ == "__main__":
    main()