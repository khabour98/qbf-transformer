from __future__ import annotations

from models.qbf_formula import QBFFormula
from operators.base_operator import BaseOperator, OperatorError


class PureLiteralGenerator(BaseOperator):
    """
    Wendet Pure Literal Elimination auf eine existenzielle Variable an
    die BEREITS ein echtes Pure Literal in der Formel ist.
    """

    def __init__(
        self,
        polarity: str = "auto",
        var_index: int = 0,
    ) -> None:
        if polarity not in ("positive", "negative", "auto"):
            raise ValueError(
                f"polarity must be 'positive', 'negative', or 'auto', "
                f"got: '{polarity}'"
            )
        self.polarity = polarity
        self.var_index = var_index

    def name(self) -> str:
        # Eindeutiger Name pro Variante — wichtig für CSV und Duplikat-Check
        if self.polarity == "positive":
            return "pure_literal_gen_pos"
        elif self.polarity == "negative":
            return "pure_literal_gen_neg"
        else:
            return "pure_literal_gen_auto"

    def description(self) -> str:
        return (
            f"Applies pure literal elimination to an existential variable "
            f"that is already a true pure literal (polarity='{self.polarity}'). "
            f"Removes all satisfied clauses and cleans up complements. "
            f"Truth value is guaranteed to be preserved."
        )

    def apply(self, formula: QBFFormula) -> QBFFormula:
        pure_literal, variable = self._find_pure_literal(formula)

        if pure_literal is None:
            raise OperatorError(
                operator=self.name(),
                reason=(
                    f"No true pure literal with polarity='{self.polarity}' found. "
                    f"All existential variables occur with both polarities. "
                    f"PLE would not be truth-preserving."
                ),
                formula_path=formula.source_file,
            )

        complement = -pure_literal

        mutant = formula.copy()

        # Korrekte PLE:
        # pure_literal ist z.B. +x2 (nur positiv vorkommend) → x2 = TRUE
        # -> Klauseln mit +x2: komplett entfernen (erfüllt)
        # -> Klauseln mit -x2: -x2 streichen (existiert in echtem Pure Literal nicht)
        # -> Alle anderen: unverändert
        new_matrix: list[list[int]] = []
        for clause in mutant.matrix:
            if pure_literal in clause:
                # Klausel wird durch x=TRUE/FALSE erfüllt -> entfernen
                continue
            elif complement in clause:
                # Komplement aus Klausel entfernen
                # (Sicherheitsfall — bei echtem Pure Literal nicht erreichbar)
                new_clause = [lit for lit in clause if lit != complement]
                if new_clause:
                    new_matrix.append(new_clause)
            else:
                new_matrix.append(clause)

        mutant.matrix = new_matrix
        mutant.num_clauses = len(new_matrix)

        # Variable aus dem Prafix entfernen (sie wurde durch PLE eliminiert)
        new_prefix = []
        for quantifier, variables in mutant.prefix:
            new_vars = [v for v in variables if v != variable]
            if new_vars:
                new_prefix.append((quantifier, new_vars))
        mutant.prefix = new_prefix
        mutant.num_vars = max(v for _, vs in mutant.prefix for v in vs) if mutant.prefix else 0

        return mutant

    def _find_pure_literal(
        self, formula: QBFFormula
    ) -> tuple[int | None, int | None]:
        # Sucht eine existenzielle Variable die ein echtes Pure Literal ist.

        exist_vars = formula.get_existential_vars()
        candidates: list[tuple[int, int]] = []

        for var in exist_vars:
            lits = formula.get_literals_of_var(var)
            if not lits:
                continue

            pos = sum(1 for l in lits if l > 0)
            neg = sum(1 for l in lits if l < 0)

            # Nur echte Pure Literals: EINES der beiden Vorzeichen muss 0 sein
            if self.polarity in ("positive", "auto") and pos > 0 and neg == 0:
                candidates.append((var, var))   # positives Pure Literal: +x

            if self.polarity in ("negative", "auto") and neg > 0 and pos == 0:
                candidates.append((-var, var))  # negatives Pure Literal: -x

        if not candidates:
            return None, None

        try:
            return candidates[self.var_index]
        except IndexError:
            return None, None

    def is_applicable(self, formula: QBFFormula) -> bool:
        """
        Prüft ob mindestens ein echtes Pure Literal existiert.

        Gibt False zurück wenn alle existenziellen Variablen BEIDE Vorzeichen
        haben — dann wäre der Operator nicht wahrheitswerterhaltend.
        """
        literal, _ = self._find_pure_literal(formula)
        return literal is not None

    def verify(self, original: QBFFormula, mutant: QBFFormula) -> bool:
        """
        Prüft ob PLE korrekt durchgeführt wurde.

        Zusätzliche Checks:
            1. Mutant hat weniger oder gleich viele Klauseln (PLE entfernt Klauseln)
            2. Mutant hat weniger oder gleich viele Variablen (Variable wurde eliminiert)
            3. Mutant ist wohlgeformt (validate())
        """
        if original is mutant:
            return False

        # Wohlgeformtheit prüfen
        errors = mutant.validate()
        if errors:
            return False

        # PLE kann nur Klauseln entfernen, nie hinzufügen
        if mutant.num_clauses > original.num_clauses:
            return False

        # Variable wurde aus Prafix entfernt
        orig_var_count = sum(len(v) for _, v in original.prefix)
        mut_var_count  = sum(len(v) for _, v in mutant.prefix)
        if mut_var_count > orig_var_count:
            return False

        return True

    def __repr__(self) -> str:
        return (
            f"PureLiteralGenerator("
            f"polarity='{self.polarity}', "
            f"var_index={self.var_index})"
        )