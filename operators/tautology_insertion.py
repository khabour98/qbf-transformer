from __future__ import annotations

from models.qbf_formula import QBFFormula
from operators.base_operator import BaseOperator, OperatorError


class TautologyInsertion(BaseOperator):
    """
    Fügt eine Tautologie-Klausel (x OR NOT x) in die Formel ein.

    Die Variable x wird aus den existenziellen Variablen gewählt.
    Standardmäßig wird die erste existenzielle Variable verwendet —
    optional kann ein Index angegeben werden um eine andere zu wählen.
    """

    def __init__(self, var_index: int = 0) -> None:
        self.var_index = var_index

    def name(self) -> str:
        return "tautology_insertion"

    def description(self) -> str:
        return (
            "Inserts a tautology clause (x OR NOT x) for an existential "
            "variable x. The truth value of the formula remains unchanged "
            "because (x ∨ ¬x) is always true."
        )

    def apply(self, formula: QBFFormula) -> QBFFormula:
        """
        Fügt eine Tautologie-Klausel in die Formel ein.

        Schritte:
            1. Existenzielle Variablen holen
            2. Variable per var_index auswählen
            3. Formel kopieren (Original unverändert lassen)
            4. Klausel [x, -x] an die Matrix anhängen
            5. num_clauses um 1 erhöhen
        """
        exist_vars = formula.get_existential_vars()

        if not exist_vars:
            raise OperatorError(
                operator=self.name(),
                reason="No existential variables present. "
                       "Tautology insertion needs at least one exists variable.",
                formula_path=formula.source_file,
            )

        # Variable per Index auswählen
        try:
            variable = exist_vars[self.var_index]
        except IndexError:
            raise OperatorError(
                operator=self.name(),
                reason=(
                    f"var_index={self.var_index} is invalid for "
                    f"{len(exist_vars)} existential variable(s)."
                ),
                formula_path=formula.source_file,
            )

        # Formel kopieren — Original darf nicht verändert werden
        mutant = formula.copy()

        # Tautologie-Klausel einfügen: [x, -x]
        tautology_clause = [variable, -variable]
        mutant.matrix.append(tautology_clause)
        mutant.num_clauses += 1

        return mutant

    def is_applicable(self, formula: QBFFormula) -> bool:
        """
        Prüft ob die Formel mindestens eine existenzielle Variable hat.
        """
        return len(formula.get_existential_vars()) > 0

    def verify(self, original: QBFFormula, mutant: QBFFormula) -> bool:
        if not super().verify(original, mutant):
            return False

        # Genau eine Klausel mehr
        if mutant.num_clauses != original.num_clauses + 1:
            return False

        if len(mutant.matrix) != len(original.matrix) + 1:
            return False

        # Letzte Klausel muss Tautologie sein: [x, -x] oder [-x, x]
        last_clause = mutant.matrix[-1]

        if len(last_clause) != 2:
            return False

        a, b = last_clause
        if a != -b:
            return False

        # Variable muss existenziell sein
        variable = abs(a)
        if mutant.get_quantifier_of(variable) != "exists":
            return False

        return True

    def __repr__(self) -> str:
        return f"TautologyInsertion(var_index={self.var_index})"