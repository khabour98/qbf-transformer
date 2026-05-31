from __future__ import annotations

import subprocess
from pathlib import Path

from models.solver_result import SolverResult
from solver.solver_timer import SolverTimer


# Solver-Konfiguration
SOLVER_COMMANDS: dict[str, list[str]] = {
    "depqbf": ["depqbf/depqbf", "--qdo"],
    "caqe":   ["caqe/target/release/caqe"],
}

DEFAULT_RUNS    = 1
DEFAULT_TIMEOUT = 60  # Sekunden bis Timeout


class SolverRunner:
    """
    Führt DepQBF und CAQE auf QBF-Formeln aus und misst Laufzeit.

    Kernaufgaben:
        - Solver n-mal auf einer Formel ausführen (run)
        - Original und Mutant auf Äquivalenz prüfen (verify_equivalence)
        - Beide Solver auf Original und Mutant ausführen (run_both_solvers)
    """

    def __init__(
        self,
        runs: int = DEFAULT_RUNS,
        timeout: float = DEFAULT_TIMEOUT,
        solver_commands: dict[str, list[str]] | None = None,
    ) -> None:
        self.runs = runs
        self.timeout = timeout
        self.solver_commands = solver_commands or SOLVER_COMMANDS
        self.timer = SolverTimer()

    def run(
        self,
        formula_path: str,
        solver: str = "depqbf",
        runs: int | None = None,
    ) -> SolverResult:
        """
        Führt einen Solver mehrfach auf einer Formel aus und gibt SolverResult zurück.
        """
        num_runs = runs if runs is not None else self.runs

        # Datei-Existenz prüfen
        if not Path(formula_path).exists():
            raise FileNotFoundError(
                f"Formula file not found: '{formula_path}'"
            )

        # Solver-Befehl holen
        command = self._get_command(solver, formula_path)

        # Solver-Installation prüfen
        self._check_solver_available(solver)

        # n Läufe durchführen
        times: list[float] = []
        last_exit_code = -1

        for _ in range(num_runs):
            exit_code, elapsed = self._run_once(command)
            times.append(elapsed)
            last_exit_code = exit_code

            # Bei ERROR nach erstem Lauf abbrechen
            if exit_code not in (10, 20):
                return SolverResult(
                    solver=solver,
                    formula_path=formula_path,
                    exit_code=exit_code,
                    times=times,
                )

        return SolverResult(
            solver=solver,
            formula_path=formula_path,
            exit_code=last_exit_code,
            times=times,
        )

    def verify_equivalence(self, orig, mutant):
        # Wenn Original schon ERROR ist → können wir keine Aussage machen
        if orig.status == "ERROR":
            return True  # neutral: nicht als Fehler werten
        return orig.status == mutant.status

    def run_both_solvers(
        self,
        original_path: str,
        mutant_path: str,
        runs: int | None = None,
    ) -> tuple[SolverResult, SolverResult, SolverResult, SolverResult]:
        """
        Führt DepQBF und CAQE jeweils auf Original und Mutant aus.

        Reihenfolge der Ausführung:
            1. DepQBF auf Original
            2. DepQBF auf Mutant
            3. CAQE auf Original
            4. CAQE auf Mutant
        """
        depqbf_original = self.run(original_path, solver="depqbf", runs=runs)
        depqbf_mutant   = self.run(mutant_path,   solver="depqbf", runs=runs)
        caqe_original   = self.run(original_path, solver="caqe",   runs=runs)
        caqe_mutant     = self.run(mutant_path,   solver="caqe",   runs=runs)

        return depqbf_original, depqbf_mutant, caqe_original, caqe_mutant

    def _run_once(self, command: list[str]) -> tuple[int, float]:
        """
        Führt einen einzelnen Solver-Aufruf aus und misst die Laufzeit.
        """
        try:
            result, elapsed = self.timer.measure(
                subprocess.run,
                command,
                capture_output=True,
                timeout=self.timeout,
            )
            return result.returncode, elapsed

        except subprocess.TimeoutExpired:
            return 124, float(self.timeout)

        except Exception:
            return -1, 0.0

    def _get_command(self, solver: str, formula_path: str) -> list[str]:
        """
        Baut den vollständigen Solver-Befehl zusammen.
        """
        if solver not in self.solver_commands:
            raise SolverNotFoundError(
                solver=solver,
                reason=(
                    f"Unknown solver '{solver}'. "
                    f"Available: {list(self.solver_commands.keys())}"
                ),
            )
        return self.solver_commands[solver] + [formula_path]

    def _check_solver_available(self, solver: str) -> None:
        """
        Prüft ob der Solver im System-PATH verfügbar ist.
        """
        executable = self.solver_commands[solver][0]
        try:
            subprocess.run(
                [executable, "--help"],
                capture_output=True,
                timeout=5,
            )
        except FileNotFoundError:
            raise SolverNotFoundError(
                solver=solver,
                reason=(
                    f"'{executable}' not found. "
                    f"Please install it or set the path in solver_commands."
                ),
            )
        except subprocess.TimeoutExpired:
            # --help hat 5s gebraucht → Solver ist da aber reagiert seltsam
            # Trotzdem weitermachen
            pass

    def __repr__(self) -> str:
        return (
            f"SolverRunner("
            f"runs={self.runs}, "
            f"timeout={self.timeout}s, "
            f"solvers={list(self.solver_commands.keys())})"
        )


# SolverNotFoundError

class SolverNotFoundError(Exception):
    """
    Wird geworfen wenn ein Solver nicht installiert oder nicht im PATH ist.
    """

    def __init__(self, solver: str, reason: str) -> None:
        self.solver = solver
        self.reason = reason
        super().__init__(str(self))

    def __str__(self) -> str:
        return f"[SolverNotFoundError] Solver='{self.solver}': {self.reason}"

    def __repr__(self) -> str:
        return f"SolverNotFoundError(solver='{self.solver}')"