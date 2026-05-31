from __future__ import annotations
from dataclasses import dataclass, field
from statistics import median


@dataclass
class SolverResult:
    """
    Ergebnis eines einzelnen Solver-Laufs (Original oder Mutant).

    Ein Lauf besteht aus mehreren Wiederholungen desselben Solver-Aufrufs, damit stabile Messwerte entstehen.
    Median und Status werden automatisch via __post_init__ berechnet.
    """

    solver: str
    """Name des Solvers: "depqbf" oder "caqe"."""

    formula_path: str
    """Pfad zur gelösten .qdimacs-Datei."""

    exit_code: int
    """Roh-Exit-Code des Solver-Prozesses (10, 20 oder anderes)."""

    times: list[float] = field(default_factory=list)
    """
    Alle Einzelmessungen in Sekunden.
    Normalerweise 10 Werte — gemessen mit time.perf_counter().
    """

    # Automatisch berechnete Felder
    median_time: float = field(init=False)
    """Median aller Einzelmessungen in Sekunden. Wird automatisch berechnet."""

    status: str = field(init=False)
    """Lesbare Statusangabe: "SAT", "UNSAT" oder "ERROR". Wird automatisch gesetzt."""

    def __post_init__(self) -> None:
        self.status = self._parse_exit_code(self.exit_code)
        self.median_time = median(self.times) if self.times else 0.0

    def _parse_exit_code(self, code: int) -> str:
        if code == 10:
            return "SAT"
        elif code == 20:
            return "UNSAT"
        else:
            return "ERROR"

    def is_valid(self) -> bool:
        """
        Gibt True zurück wenn der Solver ein gültiges Ergebnis geliefert hat.
        False bei Timeout, Absturz oder ungültiger Formel (status == "ERROR").
        """
        return self.status in ("SAT", "UNSAT")

    def is_sat(self) -> bool:
        """Gibt True zurück wenn die Formel erfüllbar ist (exit_code == 10)."""
        return self.status == "SAT"

    def is_unsat(self) -> bool:
        """Gibt True zurück wenn die Formel unerfüllbar ist (exit_code == 20)."""
        return self.status == "UNSAT"

    def min_time(self) -> float:
        """Gibt die schnellste Einzelmessung zurück. 0.0 wenn keine Messungen vorhanden."""
        return min(self.times) if self.times else 0.0

    def max_time(self) -> float:
        """Gibt die langsamste Einzelmessung zurück. 0.0 wenn keine Messungen vorhanden."""
        return max(self.times) if self.times else 0.0

    def num_runs(self) -> int:
        """Gibt die Anzahl der durchgeführten Solver-Läufe zurück."""
        return len(self.times)

    def __repr__(self) -> str:
        return (
            f"SolverResult("
            f"solver='{self.solver}', "
            f"status='{self.status}', "
            f"median={self.median_time:.6f}s, "
            f"runs={self.num_runs()})"
        )