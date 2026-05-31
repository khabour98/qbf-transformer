"""
Speichert und lädt ExperimentResult-Objekte als CSV .
Einzige Persistenz-Schicht des gesamten Projekts.

CSV-Schema (eine Zeile pro Experiment):
    operator, original_path, mutant_path, equivalent, valid,
    depqbf_status_original, depqbf_status_mutant,
    depqbf_median_original, depqbf_median_mutant, depqbf_time_ratio,
    caqe_status_original, caqe_status_mutant,
    caqe_median_original, caqe_median_mutant, caqe_time_ratio,
    line_coverage_original, line_coverage_mutant, line_coverage_delta,
    branch_coverage_original, branch_coverage_mutant, branch_coverage_delta
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from models.experiment_result import ExperimentResult


class ResultsManager:
    """
    Speichert ExperimentResult-Objekte als CSV und lädt sie wieder.

    Jede Zeile in der CSV entspricht einem Experiment:
        Original-Formel × Operator × Solver-Messungen × Coverage

    Die CSV wird append-weise befüllt — jedes Experiment wird sofort
    gespeichert damit bei Absturz keine Daten verloren gehen.
    """

    def __init__(self, csv_path: str = "results/experiments.csv") -> None:
        self.csv_path = Path(csv_path)
        self._ensure_directory()

    # Speichern

    def save(self, result: ExperimentResult) -> None:
        """
        Hängt ein einzelnes ExperimentResult an die CSV an.

        Falls die CSV noch nicht existiert, wird sie mit Header angelegt.
        Falls sie bereits existiert, wird die Zeile ohne Header angehängt.
        """
        row = result.to_csv_row()
        df  = pd.DataFrame([row])

        if not self.csv_path.exists():
            df.to_csv(self.csv_path, index=False, mode="w")
        else:
            df.to_csv(self.csv_path, index=False, mode="a", header=False)

    def save_batch(self, results: list[ExperimentResult]) -> None:
        """
        Speichert eine Liste von ExperimentResult-Objekten auf einmal.

        Effizienter als save() in einer Schleife da nur ein Schreibvorgang
        stattfindet. Trotzdem append-sicher: bestehende Daten bleiben erhalten.
        """
        if not results:
            return

        rows = [r.to_csv_row() for r in results]
        df   = pd.DataFrame(rows)

        if not self.csv_path.exists():
            df.to_csv(self.csv_path, index=False, mode="w")
        else:
            df.to_csv(self.csv_path, index=False, mode="a", header=False)

    # Laden

    def load_all(self) -> pd.DataFrame:
        """Lädt die gesamte CSV als pandas DataFrame """
        if not self.csv_path.exists():
            return pd.DataFrame()

        return pd.read_csv(self.csv_path)

    def filter_by_operator(self, operator_name: str) -> pd.DataFrame:
        """ Gibt alle Experimente eines bestimmten Operators zurück """
        df = self.load_all()
        if df.empty:
            return df
        return df[df["operator"] == operator_name].reset_index(drop=True)

    def filter_valid(self) -> pd.DataFrame:
        """
        Gibt nur Experimente zurück bei denen equivalent=True und valid=True.

        Filtert fehlerhafte Experimente heraus (Solver-Crash, Timeout,
        oder Transformation hat Wahrheitswert verändert).
        """
        df = self.load_all()
        if df.empty:
            return df
        return df[(df["equivalent"] == True) & (df["valid"] == True)].reset_index(drop=True)

    def filter_by_formula(self, formula_path: str) -> pd.DataFrame:
        """Gibt alle Experimente für eine bestimmte Benchmark-Formel zurück """
        df = self.load_all()
        if df.empty:
            return df
        return df[df["original_path"] == formula_path].reset_index(drop=True)

    # Auswertung
    def summary_by_operator(self) -> pd.DataFrame:
        """Aggregiert Kennzahlen pro Operator über alle Benchmark-Formeln """
        df = self.filter_valid()
        if df.empty:
            return pd.DataFrame()

        return (
            df.groupby("operator")
            .agg(
                count=("operator", "count"),
                depqbf_ratio_median=("depqbf_time_ratio", "median"),
                caqe_ratio_median=("caqe_time_ratio", "median"),
                line_delta_median=("line_coverage_delta", "median"),
                branch_delta_median=("branch_coverage_delta", "median"),
            )
            .reset_index()
            .sort_values("depqbf_ratio_median", ascending=True)
        )

    def count_experiments(self) -> dict[str, int]:
        #Gibt die Anzahl der Experimente pro Operator zurück.
        df = self.load_all()
        if df.empty:
            return {}
        return df["operator"].value_counts().to_dict()

    def has_duplicate(self, result: ExperimentResult) -> bool:
        """
        Prüft ob ein Experiment bereits in der CSV vorhanden ist.
        Ein Duplikat liegt vor wenn Original-Pfad UND Operator UND Mutant-Pfad
        bereits in der CSV stehen.
        """
        df = self.load_all()
        if df.empty:
            return False

        mask = (
            (df["original_path"] == result.original_path)
            & (df["operator"]      == result.operator_name)
            & (df["mutant_path"]   == result.mutant_path)
        )
        return bool(mask.any())

    # Verwaltung

    def clear(self) -> None:
        """
        Löscht die gesamte CSV-Datei.
        Achtung: Nur für Tests verwenden.
        """
        if self.csv_path.exists():
            self.csv_path.unlink()

    def row_count(self) -> int:
        # Gibt die Anzahl der gespeicherten Experimente zurück
        df = self.load_all()
        return len(df)

    def get_operators(self) -> list[str]:
        # Gibt eine sortierte Liste aller Operatoren in der CSV zurück.

        df = self.load_all()
        if df.empty:
            return []
        return sorted(df["operator"].unique().tolist())

    def get_formulas(self) -> list[str]:
        # Gibt eine sortierte Liste aller Benchmark-Formeln in der CSV zurück.

        df = self.load_all()
        if df.empty:
            return []
        return sorted(df["original_path"].unique().tolist())

    def _ensure_directory(self) -> None:

        # Erstellt das übergeordnete Verzeichnis der CSV falls es nicht existiert.

        self.csv_path.parent.mkdir(parents=True, exist_ok=True)

    # Darstellung
    def __repr__(self) -> str:
        return (
            f"ResultsManager("
            f"csv_path='{self.csv_path}', "
            f"rows={self.row_count()})"
        )