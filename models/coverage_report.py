from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class CoverageReport:
    """
    gcov-Coverage-Bericht für einen einzelnen Solver-Lauf.
    gcov misst welche Zeilen und Zweige des DepQBF-Quellcodes
    während des Lösens tatsächlich ausgeführt wurden.
    """

    lines_executed: int
    lines_total: int
    branches_executed: int
    branches_total: int

    line_coverage_pct: float = field(init=False)
    # Line coverage in percent. Computed automatically

    branch_coverage_pct: float = field(init=False)
    # Branch coverage in percent. Computed automatically

    def __post_init__(self) -> None:
        self.line_coverage_pct = (
            (self.lines_executed / self.lines_total * 100)
            if self.lines_total > 0
            else 0.0
        )
        self.branch_coverage_pct = (
            (self.branches_executed / self.branches_total * 100)
            if self.branches_total > 0
            else 0.0
        )

    # Abfragen

    def is_empty(self) -> bool:
        # Gibt True zurück wenn keine Coverage-Daten vorhanden sind.

        return self.lines_total == 0

    def line_delta(self, other: CoverageReport) -> float:
        # Berechnet die Differenz der Zeilen-Coverage gegenüber einem anderen Bericht

        return self.line_coverage_pct - other.line_coverage_pct

    def branch_delta(self, other: CoverageReport) -> float:
        # Berechnet die Differenz der Branch-Coverage gegenüber einem anderen Bericht.

        return self.branch_coverage_pct - other.branch_coverage_pct


    def __repr__(self) -> str:
        return (
            f"CoverageReport("
            f"lines={self.lines_executed}/{self.lines_total} "
            f"({self.line_coverage_pct:.1f}%), "
            f"branches={self.branches_executed}/{self.branches_total} "
            f"({self.branch_coverage_pct:.1f}%))"
        )