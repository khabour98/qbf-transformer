"""
parser/parse_error.py

Exception-Klasse für Fehler beim Einlesen von QDIMACS-Dateien.
Wird vom QDIMACSParser geworfen wenn die Datei ungültig ist.
"""

from __future__ import annotations


class ParseError(Exception):
    """
    Wird geworfen wenn eine .qdimacs-Datei nicht korrekt eingelesen werden kann.

    Enthält neben der Fehlermeldung auch die Zeilennummer und den
    Dateinamen — damit man sofort weiß wo in der Datei der Fehler liegt.

    Mögliche Ursachen:
        - Fehlende oder falsche Header-Zeile ("p cnf ...")
        - Unbekannter Quantor (weder "a" noch "e")
        - Klausel endet nicht mit 0
        - Literal ist kein gültiger Integer
        - Variable im Literal ist nicht im Präfix definiert
        - Datei ist leer oder nicht lesbar

    Beispiel:
        raise ParseError(
            message="Fehlende Header-Zeile 'p cnf'",
            filepath="benchmarks/formula_001.qdimacs",
            line_number=1,
        )

    Ausgabe von str(error):
        [benchmarks/formula_001.qdimacs, Zeile 1] Fehlende Header-Zeile 'p cnf'
    """

    def __init__(
        self,
        message: str,
        filepath: str = "",
        line_number: int | None = None,
        line_content: str = "",
    ) -> None:
        """
        Args:
            message:      Beschreibung des Fehlers.
            filepath:     Pfad zur fehlerhaften Datei (optional).
            line_number:  Zeilennummer wo der Fehler aufgetreten ist (optional, 1-basiert).
            line_content: Inhalt der fehlerhaften Zeile (optional, für bessere Diagnose).
        """
        self.message = message
        self.filepath = filepath
        self.line_number = line_number
        self.line_content = line_content

        super().__init__(str(self))

    # ------------------------------------------------------------------ #
    # Darstellung                                                          #
    # ------------------------------------------------------------------ #

    def __str__(self) -> str:
        """
        Gibt eine lesbare Fehlermeldung zurück.

        Beispiele:
            Nur message:
                "Fehlende Header-Zeile 'p cnf'"

            Mit filepath:
                "[benchmarks/formula_001.qdimacs] Fehlende Header-Zeile 'p cnf'"

            Mit filepath und line_number:
                "[benchmarks/formula_001.qdimacs, Zeile 3] Unbekannter Quantor: 'x'"

            Mit filepath, line_number und line_content:
                "[benchmarks/formula_001.qdimacs, Zeile 3] Unbekannter Quantor: 'x'
                 Zeile: 'x 1 2 0'"
        """
        parts: list[str] = []

        if self.filepath and self.line_number is not None:
            parts.append(f"[{self.filepath}, line {self.line_number}]")
        elif self.filepath:
            parts.append(f"[{self.filepath}]")
        elif self.line_number is not None:
            parts.append(f"[line {self.line_number}]")

        parts.append(self.message)
        result = " ".join(parts)

        if self.line_content:
            result += f"\n  line: '{self.line_content.strip()}'"

        return result

    def __repr__(self) -> str:
        return (
            f"ParseError("
            f"message='{self.message}', "
            f"filepath='{self.filepath}', "
            f"line_number={self.line_number})"
        )