from __future__ import annotations
from abc import ABC, abstractmethod

from models.qbf_formula import QBFFormula


class BaseOperator(ABC):
    """
    Abstrakte Basisklasse für alle wahrheitswert-erhaltenden Transformationsoperatoren.

    Jeder konkrete Operator (TautologyInsertion, PureLiteralGenerator, ...)
    erbt von dieser Klasse und überschreibt mindestens:
        - apply()
        - name()
        - description()

    apply() darf das Original-QBFFormula NIEMALS direkt verändern.
    """

    @abstractmethod
    def apply(self, formula: QBFFormula) -> QBFFormula:
        """
        Wendet den Transformationsoperator auf die Formel an.

        WICHTIG: Das Original-Objekt darf nicht verändert werden.
        Immer zuerst formula.copy() aufrufen!
        """

    @abstractmethod
    def name(self) -> str:
        """
        Gibt den eindeutigen, maschinenlesbaren Namen des Operators zurück.
        Konvention: lowercase, Unterstriche, kein Leerzeichen.
        """

    @abstractmethod
    def description(self) -> str:
        """
        Gibt eine kurze, menschenlesbare Beschreibung des Operators zurück.
        """

    def is_applicable(self, formula: QBFFormula) -> bool:
        """
        Prüft ob der Operator auf diese Formel angewendet werden kann.
        """
        return True

    def verify(self, original: QBFFormula, mutant: QBFFormula) -> bool:
        """
        Prüft strukturell ob die Transformation plausibel durchgeführt wurde.

        Dies ist KEIN vollständiger Äquivalenz-Beweis — dafür sind die Solver
        zuständig. verify() ist ein schneller Sanity-Check der sicherstellt,
        dass die Transformation nicht offensichtlich falsch ist.

        Standardimplementierung prüft:
            1. Mutant ist ein anderes Objekt als das Original (copy() wurde aufgerufen)
            2. Präfix-Struktur ist unverändert (Quantoren-Reihenfolge bleibt gleich)
            3. Mutant besteht den validate()-Check (wohlgeformt)
        """
        # Original und Mutant müssen verschiedene Objekte sein
        if original is mutant:
            return False

        # Präfix-Länge muss gleich bleiben (Quantoren-Struktur unverändert)
        if len(original.prefix) != len(mutant.prefix):
            return False

        # Quantoren-Reihenfolge muss gleich bleiben
        for (orig_q, _), (mut_q, _) in zip(original.prefix, mutant.prefix):
            if orig_q != mut_q:
                return False

        # Mutant muss wohlgeformt sein
        errors = mutant.validate()
        if errors:
            return False

        return True

    def safe_apply(self, formula: QBFFormula) -> QBFFormula | None:
        """
        Wendet den Operator an — gibt None zurück statt eine Exception zu werfen.

        Prüft zuerst is_applicable(). Falls der Operator nicht anwendbar ist
        oder apply() eine OperatorError wirft, wird None zurückgegeben.
        """
        if not self.is_applicable(formula):
            return None
        try:
            return self.apply(formula)
        except OperatorError:
            return None

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name()}')"

    def __str__(self) -> str:
        return f"{self.name()}: {self.description()}"


# ------------------------------------------------------------------ #
# OperatorError                                                      #
# ------------------------------------------------------------------ #

class OperatorError(Exception):

    def __init__(
        self,
        operator: str,
        reason: str,
        formula_path: str = "",
    ) -> None:
        self.operator = operator
        self.reason = reason
        self.formula_path = formula_path
        super().__init__(str(self))

    def __str__(self) -> str:
        if self.formula_path:
            return (
                f"[{self.operator}] Operator not applicable to "
                f"'{self.formula_path}': {self.reason}"
            )
        return f"[{self.operator}] Operator not applicable: {self.reason}"

    def __repr__(self) -> str:
        return (
            f"OperatorError("
            f"operator='{self.operator}', "
            f"reason='{self.reason}')"
        )