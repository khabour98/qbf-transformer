from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class QBFFormula:
    # Repräsentiert eine Quantified Boolean Formula (QBF) im QDIMACS-Format.

    num_vars: int
    num_clauses: int
    prefix: list[tuple[str, list[int]]]   # [("forall", [1,2]), ("exists", [3,4])]
    matrix: list[list[int]]               # [[1, -2], [-3, 4, 2], ...]
    source_file: str = ""

    def to_qdimacs(self) -> str:
        # Serialisiert die Formel zurück ins QDIMACS-Format

        lines: list[str] = []

        # Header
        lines.append(f"p cnf {self.num_vars} {self.num_clauses}")

        # Präfix
        for quantifier, variables in self.prefix:
            if quantifier == "forall":
                prefix_char = "a"
            else:
                prefix_char = "e"
            var_str = " ".join(str(v) for v in variables)
            lines.append(f"{prefix_char} {var_str} 0")

        # Matrix (Klauseln)
        for clause in self.matrix:
            literal_str = " ".join(str(lit) for lit in clause)
            lines.append(f"{literal_str} 0")

        return "\n".join(lines) + "\n"

    def save(self, filepath: str) -> None:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(self.to_qdimacs())

    def get_all_variables(self) -> set[int]:
        # Gibt alle Variablen-IDs zurück, die im Präfix definiert sind
        all_vars: set[int] = set()
        for _, variables in self.prefix:
            all_vars.update(variables)
        return all_vars

    def get_existential_vars(self) -> list[int]:
        # Gibt alle existenziell quantifizierten Variablen zurück (exists / 'e').

        existential: list[int] = []
        for quantifier, variables in self.prefix:
            if quantifier == "exists":
                existential.extend(variables)
        return existential

    def get_universal_vars(self) -> list[int]:
        # Gibt alle universell quantifizierten Variablen zurück (forall / 'a').

        universal: list[int] = []
        for quantifier, variables in self.prefix:
            if quantifier == "forall":
                universal.extend(variables)
        return universal

    def get_quantifier_of(self, variable: int) -> str | None:

        # Gibt den Quantor einer bestimmten Variable zurück.
        for quantifier, variables in self.prefix:
            if variable in variables:
                return quantifier
        return None

    def get_prefix_level_of(self, variable: int) -> int | None:
        # Gibt die Quantoren-Ebene (0-basiert) einer Variable im Präfix zurück.
        for level, (_, variables) in enumerate(self.prefix):
            if variable in variables:
                return level
        return None

    def get_literals_of_var(self, variable: int) -> list[int]:
        # Gibt alle Vorkommen einer Variable in der Matrix zurück (positiv und negativ).

        result: list[int] = []
        for clause in self.matrix:
            for literal in clause:
                if abs(literal) == variable:
                    result.append(literal)
        return result

    def get_clauses_containing(self, variable: int) -> list[list[int]]:
        # Gibt alle Klauseln zurück, die die Variable enthalten (positiv oder negativ).

        result: list[list[int]] = []
        for clause in self.matrix:
            for literal in clause:
                if abs(literal) == variable:
                    result.append(clause)
                    break
        return result

    def is_satisfiable_structure(self) -> bool:
        """
        Führt einen strukturellen Grundcheck durch — kein vollständiger SAT-Check.

        Prüft:
            1. Keine leere Klausel vorhanden (leere Klausel → sofort UNSAT)
            2. num_vars und num_clauses stimmen mit tatsächlichem Inhalt überein
            3. Präfix ist nicht leer
            4. Alle Variablen in der Matrix sind im Präfix definiert

        """
        # Leere Klausel vorhanden?
        for clause in self.matrix:
            if len(clause) == 0:
                return False

        # Präfix nicht leer?
        if not self.prefix:
            return False

        # Klauselanzahl stimmt?
        if len(self.matrix) != self.num_clauses:
            return False

        # Alle Variablen im Präfix definiert?
        defined_vars = self.get_all_variables()
        for clause in self.matrix:
            for literal in clause:
                if abs(literal) not in defined_vars:
                    return False

        return True

    def validate(self) -> list[str]:
        # Gibt eine Liste aller gefundenen Strukturprobleme zurück.
        errors: list[str] = []

        if not self.prefix:
            errors.append("Prefix is empty — formula has no quantifiers.")

        if self.num_vars <= 0:
            errors.append(f"num_vars must be > 0, but is {self.num_vars}.")

        if self.num_clauses != len(self.matrix):
            errors.append(
                f"num_clauses={self.num_clauses} does not match "
                f"actual number of clauses={len(self.matrix)} ."
            )

        defined_vars = self.get_all_variables()
        actual_max = max(defined_vars) if defined_vars else 0
        if actual_max > self.num_vars:
            errors.append(
                f"Highest variable in prefix ({actual_max}) "
                f"exceeds num_vars ({self.num_vars})."
            )

        for i, clause in enumerate(self.matrix):
            if len(clause) == 0:
                errors.append(f"Clause {i} is empty — formula is immediately UNSAT.")
            for literal in clause:
                if abs(literal) not in defined_vars:
                    errors.append(
                        f"Clause {i}: variable {abs(literal)} "
                        f"is not defined in the prefix."
                    )

        return errors

    def next_free_variable(self) -> int:
        all_vars = self.get_all_variables()
        return max(all_vars) + 1 if all_vars else 1

    def copy(self) -> QBFFormula:
        # Jeder Operator muss zuerst copy() aufrufen und dann die Kopie verändern
        # das Original darf NIE verändert werden.

        return QBFFormula(
            num_vars=self.num_vars,
            num_clauses=self.num_clauses,
            prefix=[(q, list(vars_)) for q, vars_ in self.prefix],
            matrix=[list(clause) for clause in self.matrix],
            source_file=self.source_file,
        )

    def __repr__(self) -> str:
        return (
            f"QBFFormula("
            f"vars={self.num_vars}, "
            f"clauses={self.num_clauses}, "
            f"prefix_blocks={len(self.prefix)}, "
            f"source='{self.source_file}')"
        )

    def __eq__(self, other: object) -> bool:
        """
        Zwei Formeln sind gleich wenn Präfix und Matrix identisch sind.
        num_vars und num_clauses werden implizit durch den Inhalt bestimmt.
        """
        if not isinstance(other, QBFFormula):
            return NotImplemented
        return self.prefix == other.prefix and self.matrix == other.matrix