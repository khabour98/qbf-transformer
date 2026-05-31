from __future__ import annotations

from models.qbf_formula import QBFFormula
from operators.base_operator import BaseOperator, OperatorError


class BlockedClauseInsertion(BaseOperator):

    def __init__(
        self,
        literal_var_index: int = 0,
        negate_literal: bool = False,
    ) -> None:
        self.literal_var_index = literal_var_index
        self.negate_literal = negate_literal

    # Pflicht-Methoden

    def name(self) -> str:
        # Eindeutiger Name pro Variante — wichtig für CSV und Duplikat-Check
        parts = ["blocked_clause_insertion"]
        if self.negate_literal:
            parts.append("neg")
        if self.literal_var_index != 0:
            parts.append(f"v{self.literal_var_index}")
        return "_".join(parts)

    def description(self) -> str:
        return (
            f"Inserts a blocked clause into the formula (Blocked Clause Addition). "
            f"A clause C is blocked with respect to a literal L if every possible "
            f"resolution step involving C produces a tautology. "
            f"The truth value of the formula is preserved "
            f"(Biere, Lonsing & Seidl 2011). "
            f"[var_index={self.literal_var_index}, negate={self.negate_literal}]"
        )

    def apply(self, formula: QBFFormula) -> QBFFormula:

        # Inserts a blocked clause into the formula.

        exist_vars = formula.get_existential_vars()

        if not exist_vars:
            raise OperatorError(
                operator=self.name(),
                reason="No existential variables available.",
                formula_path=formula.source_file,
            )

        try:
            variable = exist_vars[self.literal_var_index]
        except IndexError:
            raise OperatorError(
                operator=self.name(),
                reason=(
                    f"literal_var_index={self.literal_var_index} is invalid for "
                    f"{len(exist_vars)} existential variable(s)."
                ),
                formula_path=formula.source_file,
            )

        blocking_literal = -variable if self.negate_literal else variable

        blocked_clause = self._build_blocked_clause(blocking_literal, formula)

        mutant = formula.copy()
        mutant.matrix.append(blocked_clause)
        mutant.num_clauses += 1

        return mutant

    def _build_blocked_clause(
        self,
        blocking_literal: int,
        formula: QBFFormula,
    ) -> list[int]:

        # Konstruiert eine blocked Clause bezüglich des blocking Literals L.

        complement = -blocking_literal

        resolution_partners = [
            clause for clause in formula.matrix
            if complement in clause
        ]

        if not resolution_partners:
            return [blocking_literal]

        candidate_clause = [blocking_literal]
        defined_vars = formula.get_all_variables()

        for partner in resolution_partners:
            added = False
            for literal in partner:
                if literal == complement:
                    continue

                complement_of_literal = -literal

                if complement_of_literal not in candidate_clause:
                    if abs(complement_of_literal) in defined_vars:
                        candidate_clause.append(complement_of_literal)
                        added = True
                        break

            if not added:
                if -blocking_literal not in candidate_clause:
                    candidate_clause.append(-blocking_literal)
                break

        if self._is_blocked(candidate_clause, blocking_literal, formula):
            return candidate_clause

        # Fallback: Tautologie-Klausel ist immer blocked
        return [blocking_literal, -blocking_literal]

    def _is_blocked(
        self,
        clause: list[int],
        blocking_literal: int,
        formula: QBFFormula,
    ) -> bool:
        # Prüft ob eine Klausel C blocked ist bezüglich des Literals L.
        complement_of_L = -blocking_literal
        clause_set = set(clause)

        for partner in formula.matrix:
            if complement_of_L not in partner:
                continue

            partner_set = set(partner)
            is_tautology = any(-lit in partner_set for lit in clause_set)

            if not is_tautology:
                return False

        return True

    def is_applicable(self, formula: QBFFormula) -> bool:
        exist_vars = formula.get_existential_vars()
        if not exist_vars:
            return False
        try:
            _ = exist_vars[self.literal_var_index]
            return True
        except IndexError:
            return False

    def verify(self, original: QBFFormula, mutant: QBFFormula) -> bool:
        # Prüft ob die Blocked Clause korrekt eingefügt wurde.
        if not super().verify(original, mutant):
            return False

        if mutant.num_clauses != original.num_clauses + 1:
            return False

        if len(mutant.matrix) != len(original.matrix) + 1:
            return False

        inserted_clause = mutant.matrix[-1]

        if not inserted_clause:
            return False

        for literal in inserted_clause:
            if self._is_blocked(inserted_clause, literal, original):
                return True

        return False

    def __repr__(self) -> str:
        return (
            f"BlockedClauseInsertion("
            f"literal_var_index={self.literal_var_index}, "
            f"negate_literal={self.negate_literal})"
        )