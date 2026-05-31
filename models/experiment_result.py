from __future__ import annotations
from dataclasses import dataclass, field

from models.solver_result import SolverResult
from models.coverage_report import CoverageReport


@dataclass
class ExperimentResult:
    """
    Fasst ein komplettes Original-vs-Mutant-Experiment zusammen.

    Ein Experiment läuft nach diesem Schema ab:
        1. Original-Formel wird mit DepQBF und CAQE gelöst      → depqbf_original, caqe_original
        2. Operator transformiert die Formel → Mutant
        3. Mutant wird mit DepQBF und CAQE gelöst               → depqbf_mutant, caqe_mutant
        4. Coverage wird für Original und Mutant gemessen        → coverage_original, coverage_mutant
        5. Verifikation: Original und Mutant müssen dasselbe
           SAT/UNSAT-Ergebnis liefern                           → equivalent
    """

    operator_name: str
    """Name of the applied operator, e.g. 'tautology_insertion'."""

    original_path: str
    """Path to the original .qdimacs file."""

    mutant_path: str
    """Path to the transformed .qdimacs file (mutant)."""

    depqbf_original: SolverResult
    """DepQBF run on the original formula (median computed)."""

    depqbf_mutant: SolverResult
    """DepQBF run on the mutant (10 runs, median computed)."""

    caqe_original: SolverResult
    """CAQE run on the original formula (median computed)."""

    caqe_mutant: SolverResult
    """CAQE run on the mutant (median computed)."""

    coverage_original: CoverageReport
    """gcov report of the DepQBF run on the original."""

    coverage_mutant: CoverageReport
    """gcov report of the DepQBF run on the mutant."""

    equivalent: bool
    """
    True if original and mutant yield the same SAT/UNSAT status.
    Must always be True — otherwise the transformation is incorrect.
    """

    depqbf_time_ratio: float = field(init=False)
    caqe_time_ratio: float = field(init=False)
    line_coverage_delta: float = field(init=False)
    branch_coverage_delta: float = field(init=False)

    def __post_init__(self) -> None:
        self.depqbf_time_ratio = _safe_ratio(
            self.depqbf_mutant.median_time,
            self.depqbf_original.median_time,
        )
        self.caqe_time_ratio = _safe_ratio(
            self.caqe_mutant.median_time,
            self.caqe_original.median_time,
        )
        self.line_coverage_delta = (
            self.coverage_mutant.line_coverage_pct
            - self.coverage_original.line_coverage_pct
        )
        self.branch_coverage_delta = (
            self.coverage_mutant.branch_coverage_pct
            - self.coverage_original.branch_coverage_pct
        )

    def is_valid(self) -> bool:
        """ Gibt True zurück, wenn das Experiment vollständig und korrekt ist """
        return (
            self.equivalent
            and self.depqbf_original.is_valid()
            and self.depqbf_mutant.is_valid()
            and self.caqe_original.is_valid()
            and self.caqe_mutant.is_valid()
        )

    def has_coverage_data(self) -> bool:
        """
        Gibt True zurück, wenn Coverage-Daten für beide Läufe vorhanden sind.
        False, wenn DepQBF ohne gcov-Flags kompiliert wurde.
        """
        return (
            not self.coverage_original.is_empty()
            and not self.coverage_mutant.is_empty()
        )

    def to_csv_row(self) -> dict:
        """ Gibt alle Felder als flaches Dictionary zurück bereit zum Speichern als CSV-Zeile mit pandas """
        return {
            # Metadaten
            "operator":                   self.operator_name,
            "original_path":              self.original_path,
            "mutant_path":                self.mutant_path,
            "equivalent":                 self.equivalent,
            "valid":                      self.is_valid(),

            # DepQBF
            "depqbf_status_original":     self.depqbf_original.status,
            "depqbf_status_mutant":       self.depqbf_mutant.status,
            "depqbf_median_original":     self.depqbf_original.median_time,
            "depqbf_median_mutant":       self.depqbf_mutant.median_time,
            "depqbf_time_ratio":          self.depqbf_time_ratio,

            # CAQE
            "caqe_status_original":       self.caqe_original.status,
            "caqe_status_mutant":         self.caqe_mutant.status,
            "caqe_median_original":       self.caqe_original.median_time,
            "caqe_median_mutant":         self.caqe_mutant.median_time,
            "caqe_time_ratio":            self.caqe_time_ratio,

            # Coverage (nur DepQBF)
            "line_coverage_original":     self.coverage_original.line_coverage_pct,
            "line_coverage_mutant":       self.coverage_mutant.line_coverage_pct,
            "line_coverage_delta":        self.line_coverage_delta,
            "branch_coverage_original":   self.coverage_original.branch_coverage_pct,
            "branch_coverage_mutant":     self.coverage_mutant.branch_coverage_pct,
            "branch_coverage_delta":      self.branch_coverage_delta,
        }

    def summary(self) -> str:
        """
        Gibt eine lesbare Zusammenfassung des Experiments zurück.
        Nützlich für Logging und schnelle Überprüfung im Terminal.
        """
        orig_name = self.original_path.split("/")[-1]
        lines = [
            f"[{self.operator_name}] {orig_name}",
            f"  Equivalent : {self.equivalent}",
            f"  DepQBF     : {self.depqbf_original.status} → {self.depqbf_mutant.status}"
            f"  | ratio={self.depqbf_time_ratio:.3f}"
            f"  | median={self.depqbf_original.median_time:.6f}s"
            f" → {self.depqbf_mutant.median_time:.6f}s",
            f"  CAQE       : {self.caqe_original.status} → {self.caqe_mutant.status}"
            f"  | ratio={self.caqe_time_ratio:.3f}"
            f"  | median={self.caqe_original.median_time:.6f}s"
            f" → {self.caqe_mutant.median_time:.6f}s",
        ]
        if self.has_coverage_data():
            lines.append(
                f"  Coverage   : lines Δ={self.line_coverage_delta:+.2f}%"
                f"  branches Δ={self.branch_coverage_delta:+.2f}%"
            )
        else:
            lines.append("  Coverage   : no data (gcov not available)")
        return "\n".join(lines)

    def __repr__(self) -> str:
        return (
            f"ExperimentResult("
            f"operator='{self.operator_name}', "
            f"equivalent={self.equivalent}, "
            f"depqbf_ratio={self.depqbf_time_ratio:.3f}, "
            f"caqe_ratio={self.caqe_time_ratio:.3f}, "
            f"Δline={self.line_coverage_delta:+.2f}%, "
            f"Δbranch={self.branch_coverage_delta:+.2f}%)"
        )


def _safe_ratio(numerator: float, denominator: float) -> float:
    """
    Berechnet numerator / denominator ohne ZeroDivisionError.
    Gibt 1.0 zurück, wenn der Nenner 0 ist.
    """
    if denominator == 0.0:
        return 1.0
    return numerator / denominator