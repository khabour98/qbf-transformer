from __future__ import annotations

import re
import subprocess
from pathlib import Path

from models.coverage_report import CoverageReport


class CoverageAnalyzer:
    """
    Steuert gcov-Messungen für DepQBF-Läufe.

    Kernaufgaben:
        - .gcda-Dateien löschen (reset_counters)
        - DepQBF mit Coverage ausführen (run_with_coverage)
        - gcov aufrufen und Bericht parsen (collect_coverage)
        - Delta zwischen zwei Berichten berechnen (compute_delta)
    """

    def __init__(
        self,
        depqbf_src_dir: str = ".",
        depqbf_binary: str = "depqbf",
        timeout: float = 60.0,
    ) -> None:
        self.depqbf_src_dir = Path(depqbf_src_dir)
        self.depqbf_binary = depqbf_binary
        self.timeout = timeout

    def reset_counters(self) -> None:
        """
        Löscht alle .gcda-Dateien im DepQBF-Quellverzeichnis.

        .gcda-Dateien enthalten die Zählerstände der vorherigen Läufe.
        Ohne Reset würden sich die Zähler über mehrere Läufe summieren
        und die Messung wäre nicht mehr aussagekräftig.
        """
        if not self.depqbf_src_dir.exists():
            raise CoverageError(
                reason=(
                    f"DepQBF source directory not found: "
                    f"'{self.depqbf_src_dir}'"
                )
            )

        gcda_files = list(self.depqbf_src_dir.glob("**/*.gcda"))

        for gcda_file in gcda_files:
            gcda_file.unlink()

    def run_with_coverage(self, formula_path: str) -> int:
        """
        Führt DepQBF auf einer Formel aus — gcov zeichnet Coverage automatisch auf.

        Beim Ausführen schreibt DepQBF (wenn mit -fprofile-arcs gebaut)
        automatisch .gcda-Dateien in das Quellverzeichnis.
        Ein expliziter gcov-Aufruf ist hier noch nicht nötig.
        """
        if not Path(formula_path).exists():
            raise FileNotFoundError(
                f"Formula file not found: '{formula_path}'"
            )

        command = [self.depqbf_binary, "--qdo", formula_path]

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                timeout=self.timeout,
                cwd=str(self.depqbf_src_dir),
            )
            return result.returncode

        except subprocess.TimeoutExpired:
            return 124

        except FileNotFoundError:
            raise CoverageError(
                reason=(
                    f"DepQBF binary not found: '{self.depqbf_binary}'. "
                    f"Please provide the path via depqbf_binary."
                )
            )

    def collect_coverage(self) -> CoverageReport:
        """
        Ruft gcov auf und parst den Coverage-Bericht.

        Führt gcov auf allen .c-Dateien im DepQBF-Quellverzeichnis aus
        und aggregiert die Ergebnisse über alle Dateien.

        Hinweis: gcov muss im PATH sein. Prüfe mit: gcov --version
        """
        c_files = list(self.depqbf_src_dir.glob("*.c"))

        if not c_files:
            return self._empty_report()

        # gcov für alle .c-Dateien aufrufen
        gcov_output = self._run_gcov(c_files)

        if not gcov_output:
            return self._empty_report()

        # Output parsen und aggregieren
        return self._parse_gcov_output(gcov_output)

    def compute_delta(
        self,
        report_original: CoverageReport,
        report_mutant: CoverageReport,
    ) -> tuple[float, float]:
        """
        Berechnet delta-Coverage zwischen Original und Mutant.
        """
        delta_lines    = report_mutant.line_delta(report_original)
        delta_branches = report_mutant.branch_delta(report_original)
        return delta_lines, delta_branches

    def _run_gcov(self, c_files: list[Path]) -> str:
        """
        Ruft gcov auf allen angegebenen .c-Dateien auf.
        """
        all_output: list[str] = []

        for c_file in c_files:
            try:
                result = subprocess.run(
                    ["gcov", "-b", "-c", str(c_file)],
                    capture_output=True,
                    text=True,
                    cwd=str(self.depqbf_src_dir),
                    timeout=30,
                )
                if result.stdout:
                    all_output.append(result.stdout)

            except FileNotFoundError:
                # gcov nicht installiert → leeren Report zurückgeben
                return ""

            except subprocess.TimeoutExpired:
                continue

        return "\n".join(all_output)

    def _parse_gcov_output(self, gcov_output: str) -> CoverageReport:
        """
        Parst den gcov-Output und aggregiert Zeilen- und Branch-Coverage.

        Aggregierung: gewichteter Durchschnitt über alle Dateien
        (gewichtet nach Gesamtzahl der Zeilen/Branches pro Datei).
        """
        # Zeilen-Coverage extrahieren
        line_pattern    = re.compile(
            r"Lines executed:(\d+\.?\d*)% of (\d+)"
        )
        # Branch-Coverage extrahieren
        branch_pattern  = re.compile(
            r"Branches executed:(\d+\.?\d*)% of (\d+)"
        )

        total_lines_executed    = 0
        total_lines_total       = 0
        total_branches_executed = 0
        total_branches_total    = 0

        for line_match in line_pattern.finditer(gcov_output):
            pct   = float(line_match.group(1))
            total = int(line_match.group(2))
            executed = int(round(pct / 100.0 * total))
            total_lines_executed += executed
            total_lines_total    += total

        for branch_match in branch_pattern.finditer(gcov_output):
            pct   = float(branch_match.group(1))
            total = int(branch_match.group(2))
            executed = int(round(pct / 100.0 * total))
            total_branches_executed += executed
            total_branches_total    += total

        if total_lines_total == 0 and total_branches_total == 0:
            return self._empty_report()

        return CoverageReport(
            lines_executed=total_lines_executed,
            lines_total=total_lines_total,
            branches_executed=total_branches_executed,
            branches_total=total_branches_total,
        )

    def _empty_report(self) -> CoverageReport:
        """
        Gibt einen leeren CoverageReport zurück (is_empty() == True).
        Wird verwendet wenn gcov nicht verfügbar oder keine .gcda-Dateien vorhanden.
        """
        return CoverageReport(
            lines_executed=0,
            lines_total=0,
            branches_executed=0,
            branches_total=0,
        )

    def is_gcov_available(self) -> bool:
        """
        Prüft ob gcov im System-PATH verfügbar ist.
        """
        try:
            subprocess.run(
                ["gcov", "--version"],
                capture_output=True,
                timeout=5,
            )
            return True
        except FileNotFoundError:
            return False

    def is_depqbf_instrumented(self) -> bool:
        """
        Prüft ob DepQBF mit Coverage-Flags gebaut wurde.

        Prüft ob .gcno-Dateien im Quellverzeichnis vorhanden sind.
        .gcno-Dateien werden beim Compilieren mit -fprofile-arcs erzeugt.

        True wenn DepQBF Coverage-fähig ist.
        """
        gcno_files = list(self.depqbf_src_dir.glob("**/*.gcno"))
        return len(gcno_files) > 0

    def check_setup(self) -> list[str]:
        """
        Prüft die gesamte gcov-Umgebung und gibt eine Liste von Problemen zurück.

        Rückgabe: Leere Liste wenn alles korrekt konfiguriert ist.
                  Liste mit Fehlermeldungen wenn Probleme gefunden wurden.
        """
        problems: list[str] = []

        if not self.depqbf_src_dir.exists():
            problems.append(
                f"DepQBF source directory not found: '{self.depqbf_src_dir}'"
            )

        if not self.is_gcov_available():
            problems.append(
                "gcov not installed. Install with: apt install gcc"
            )

        if not self.is_depqbf_instrumented():
            problems.append(
                "DepQBF was not built with coverage flags. "
                "Rebuild: make CFLAGS='-fprofile-arcs -ftest-coverage'"
            )

        return problems

    def __repr__(self) -> str:
        return (
            f"CoverageAnalyzer("
            f"src_dir='{self.depqbf_src_dir}', "
            f"binary='{self.depqbf_binary}')"
        )


# CoverageError
class CoverageError(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(str(self))

    def __str__(self) -> str:
        return f"[CoverageError] {self.reason}"

    def __repr__(self) -> str:
        return f"CoverageError(reason='{self.reason}')"