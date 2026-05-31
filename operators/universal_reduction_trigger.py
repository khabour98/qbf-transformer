from __future__ import annotations

from models.qbf_formula import QBFFormula
from operators.base_operator import BaseOperator, OperatorError


class UniversalReductionTrigger(BaseOperator):
    """
    Inserts a tautological clause [u, e, ¬e] to trigger Universal Reduction.

    The clause structure guarantees:
    1. Truth-value preservation: [u, e, ¬e] is always TRUE (tautology)
    2. UR is triggered:  level(u) < level(e)  →  solver removes u
    3. Remaining [e, ¬e] is also a tautology  →  removed by preprocessing
    """

    def __init__(
        self,
        univ_var_index: int = 0,
        exist_var_index: int = 0,
    ) -> None:
        self.univ_var_index  = univ_var_index
        self.exist_var_index = exist_var_index

    def name(self) -> str:
        return "universal_reduction_trigger"

    def description(self) -> str:
        return (
            "Inserts a tautological clause [u, e, ¬e] where u is a universal "
            "variable at an outer quantifier level than existential variable e. "
            "The clause [u, e, ¬e] is a tautology — truth value is always preserved. "
            "The solver triggers Universal Reduction on u, then removes [e, ¬e] "
            "as a tautology. This activates the UR code path in the solver."
        )

    def apply(self, formula: QBFFormula) -> QBFFormula:

        univ_var, exist_var = self._select_pair(formula)

        # Build the tautological UR clause: [u, e, ¬e]
        ur_clause = [univ_var, exist_var, -exist_var]

        mutant = formula.copy()
        mutant.matrix.append(ur_clause)
        mutant.num_clauses += 1

        return mutant

    def _select_pair(self, formula: QBFFormula) -> tuple[int, int]:
        """
        Selects a valid (universal, existential) variable pair where
        level(universal) < level(existential).

        First tries to use the configured indices (univ_var_index,
        exist_var_index). If the level condition is not met for those
        indices, falls back to searching all combinations.
        """
        univ_vars  = formula.get_universal_vars()
        exist_vars = formula.get_existential_vars()

        if not univ_vars:
            raise OperatorError(
                operator=self.name(),
                reason="No universal variables in this formula.",
                formula_path=formula.source_file,
            )
        if not exist_vars:
            raise OperatorError(
                operator=self.name(),
                reason="No existential variables in this formula.",
                formula_path=formula.source_file,
            )

        # Try configured indices first
        if (self.univ_var_index < len(univ_vars)
                and self.exist_var_index < len(exist_vars)):
            u = univ_vars[self.univ_var_index]
            e = exist_vars[self.exist_var_index]
            lu = formula.get_prefix_level_of(u)
            le = formula.get_prefix_level_of(e)
            if lu is not None and le is not None and lu < le:
                return u, e

        # Fallback: search all combinations
        return self._find_valid_pair(formula)

    def _find_valid_pair(self, formula: QBFFormula) -> tuple[int, int]:
        """
        Exhaustively searches for a (universal, existential) pair where
        level(universal) < level(existential).
        """
        exist_vars = formula.get_existential_vars()

        for quantifier, variables in formula.prefix:
            if quantifier != "forall":
                continue
            for univ_var in variables:
                lu = formula.get_prefix_level_of(univ_var)
                if lu is None:
                    continue
                for exist_var in exist_vars:
                    le = formula.get_prefix_level_of(exist_var)
                    if le is not None and lu < le:
                        return univ_var, exist_var

        raise OperatorError(
            operator=self.name(),
            reason=(
                "No valid (universal, existential) pair found where "
                "level(forall variable) < level(exists variable). "
                "Universal Reduction requires: level(∀) < level(∃)."
            ),
            formula_path=formula.source_file,
        )

    def is_applicable(self, formula: QBFFormula) -> bool:
        if not formula.get_universal_vars() or not formula.get_existential_vars():
            return False
        try:
            self._find_valid_pair(formula)
            return True
        except OperatorError:
            return False

    def verify(self, original: QBFFormula, mutant: QBFFormula) -> bool:
        if not super().verify(original, mutant):
            return False

        # Exactly one clause added
        if mutant.num_clauses != original.num_clauses + 1:
            return False
        if len(mutant.matrix) != len(original.matrix) + 1:
            return False

        # Inserted clause must have 3 literals
        last_clause = mutant.matrix[-1]
        if len(last_clause) != 3:
            return False

        lit_u, lit_e_pos, lit_e_neg = last_clause
        var_u = abs(lit_u)
        var_e_pos = abs(lit_e_pos)
        var_e_neg = abs(lit_e_neg)

        # Second and third literal must be the same variable with opposite signs
        if var_e_pos != var_e_neg:
            return False
        if lit_e_pos != -lit_e_neg:
            return False

        var_e = var_e_pos

        # First literal must be universal
        if mutant.get_quantifier_of(var_u) != "forall":
            return False

        # Second/third literal must be existential
        if mutant.get_quantifier_of(var_e) != "exists":
            return False

        # Level check: u must be at an outer level than e
        lu = mutant.get_prefix_level_of(var_u)
        le = mutant.get_prefix_level_of(var_e)

        if lu is None or le is None:
            return False

        return lu < le

    def __repr__(self) -> str:
        return (
            f"UniversalReductionTrigger("
            f"univ_var_index={self.univ_var_index}, "
            f"exist_var_index={self.exist_var_index})"
        )