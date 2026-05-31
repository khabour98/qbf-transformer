"""
parser/qdimacs_parser.py

Liest .qdimacs-Dateien ein und gibt QBFFormula-Objekte zurück.
Wirft ParseError bei ungültigem Format.

QDIMACS-Format (Kurzreferenz):
    Kommentarzeilen:   c Dies ist ein Kommentar
    Header:            p cnf <num_vars> <num_clauses>
    Quantoren-Präfix:  a 1 2 0        (forall: alle Variablen mit 'a')
                       e 3 4 0        (exists: existenzielle Variablen mit 'e')
    Matrix (Klauseln): 1 -2 3 0       (Literale, terminiert mit 0)
                       -1 4 0

Offizielle Spezifikation: https://www.qbflib.org/qdimacs.html
"""

from __future__ import annotations

from models.qbf_formula import QBFFormula
from parser.parse_error import ParseError


class QDIMACSParser:
    """
    Liest eine .qdimacs-Datei ein und gibt ein QBFFormula-Objekt zurück.

    Verwendung:
        parser  = QDIMACSParser()
        formula = parser.parse("benchmarks/formula_001.qdimacs")

    Fehlerbehandlung:
        Alle Fehler werden als ParseError geworfen mit Dateiname,
        Zeilennummer und Zeileninhalt für einfache Diagnose.

    Unterstützte Features:
        - Kommentarzeilen (beginnen mit 'c')
        - Header-Zeile ('p cnf <vars> <clauses>')
        - Beliebig viele Quantoren-Blöcke ('a' und 'e')
        - Klauseln mit beliebig vielen Literalen
        - Leerzeilen werden ignoriert

    Nicht unterstützt (außerhalb QDIMACS-Standard):
        - Mehrere Header-Zeilen
        - Quantoren-Blöcke nach den Klauseln
        - Variablen außerhalb des deklarierten Bereichs
    """

    def parse(self, filepath: str) -> QBFFormula:
        """
        Hauptmethode: Liest eine .qdimacs-Datei ein und gibt eine QBFFormula zurück.

        Args:
            filepath: Pfad zur .qdimacs-Datei

        Rückgabe: Vollständiges QBFFormula-Objekt

        Raises:
            ParseError:  Wenn die Datei ungültig ist
            OSError:     Wenn die Datei nicht gelesen werden kann

        Beispiel:
            parser  = QDIMACSParser()
            formula = parser.parse("benchmarks/formula_001.qdimacs")
            print(formula.num_vars)    # 4
            print(formula.prefix)     # [("forall", [1,2]), ("exists", [3,4])]
            print(formula.matrix)     # [[1, -2], [-3, 4]]
        """
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except OSError as e:
            raise ParseError(
                message=f"Could not read file: {e}",
                filepath=filepath,
            ) from e

        if not lines:
            raise ParseError(
                message="File is empty.",
                filepath=filepath,
            )

        # Zeilen mit Nummern aufbereiten (1-basiert, Leerzeilen behalten)
        numbered = [(i + 1, line) for i, line in enumerate(lines)]

        # Kommentare und Leerzeilen herausfiltern
        content_lines = [
            (num, line)
            for num, line in numbered
            if line.strip() and not line.strip().startswith("c")
        ]

        if not content_lines:
            raise ParseError(
                message="File contains no usable lines (only comments or empty).",
                filepath=filepath,
            )

        # Header parsen
        header_num, header_line = content_lines[0]
        num_vars, num_clauses = self._parse_header(
            header_line, filepath, header_num
        )

        # Präfix und Matrix trennen
        remaining = content_lines[1:]
        prefix, matrix_lines = self._split_prefix_and_matrix(
            remaining, filepath
        )

        # Präfix parsen
        parsed_prefix = self._parse_prefix(prefix, filepath)

        # Matrix parsen
        parsed_matrix = self._parse_matrix(matrix_lines, filepath)

        # Konsistenz-Checks
        self._validate_counts(
            num_vars, num_clauses,
            parsed_prefix, parsed_matrix,
            filepath,
        )

        formula = QBFFormula(
            num_vars=num_vars,
            num_clauses=num_clauses,
            prefix=parsed_prefix,
            matrix=parsed_matrix,
            source_file=filepath,
        )

        return formula

    # ------------------------------------------------------------------ #
    # Header                                                               #
    # ------------------------------------------------------------------ #

    def _parse_header(
        self,
        line: str,
        filepath: str,
        line_number: int,
    ) -> tuple[int, int]:
        """
        Parst die Header-Zeile: 'p cnf <num_vars> <num_clauses>'

        Args:
            line:        Rohe Zeile aus der Datei
            filepath:    Für Fehlermeldungen
            line_number: Für Fehlermeldungen

        Rückgabe: (num_vars, num_clauses) als Integer-Tupel

        Raises:
            ParseError: Wenn Format nicht 'p cnf <int> <int>' entspricht
        """
        parts = line.strip().split()

        if len(parts) != 4:
            raise ParseError(
                message=(
                    f"Invalid header line: expected 'p cnf <vars> <clauses>', "
                    f"found '{line.strip()}'"
                ),
                filepath=filepath,
                line_number=line_number,
                line_content=line,
            )

        if parts[0] != "p" or parts[1] != "cnf":
            raise ParseError(
                message=(
                    f"Header must start with 'p cnf', "
                    f"found '{parts[0]} {parts[1]}'"
                ),
                filepath=filepath,
                line_number=line_number,
                line_content=line,
            )

        try:
            num_vars = int(parts[2])
            num_clauses = int(parts[3])
        except ValueError:
            raise ParseError(
                message=(
                    f"num_vars and num_clauses must be integers, "
                    f"found '{parts[2]}' and '{parts[3]}'"
                ),
                filepath=filepath,
                line_number=line_number,
                line_content=line,
            )

        if num_vars <= 0:
            raise ParseError(
                message=f"num_vars must be > 0, found {num_vars}",
                filepath=filepath,
                line_number=line_number,
                line_content=line,
            )

        if num_clauses < 0:
            raise ParseError(
                message=f"num_clauses must not be negative, found {num_clauses}",
                filepath=filepath,
                line_number=line_number,
                line_content=line,
            )

        return num_vars, num_clauses

    # ------------------------------------------------------------------ #
    # Präfix / Matrix trennen                                              #
    # ------------------------------------------------------------------ #

    def _split_prefix_and_matrix(
        self,
        lines: list[tuple[int, str]],
        filepath: str,
    ) -> tuple[list[tuple[int, str]], list[tuple[int, str]]]:
        """
        Trennt Quantoren-Zeilen ('a'/'e') von Klausel-Zeilen.

        Quantoren-Zeilen kommen immer vor den Klauseln.
        Sobald eine Zeile weder mit 'a' noch 'e' beginnt, beginnt die Matrix.

        Args:
            lines:    Nummerierte Zeilen nach dem Header
            filepath: Für Fehlermeldungen

        Rückgabe: (prefix_lines, matrix_lines) als zwei separate Listen
        """
        prefix_lines: list[tuple[int, str]] = []
        matrix_lines: list[tuple[int, str]] = []

        in_matrix = False

        for line_num, line in lines:
            token = line.strip().split()[0] if line.strip() else ""

            if not in_matrix and token in ("a", "e"):
                prefix_lines.append((line_num, line))
            else:
                in_matrix = True
                matrix_lines.append((line_num, line))

        return prefix_lines, matrix_lines

    # ------------------------------------------------------------------ #
    # Präfix                                                               #
    # ------------------------------------------------------------------ #

    def _parse_prefix(
        self,
        lines: list[tuple[int, str]],
        filepath: str,
    ) -> list[tuple[str, list[int]]]:
        """
        Parst alle Quantoren-Zeilen des Präfix.

        Format je Zeile:
            a 1 2 3 0    →  ("forall", [1, 2, 3])
            e 4 5 0      →  ("exists", [4, 5])

        Args:
            lines:    Nummerierte Quantoren-Zeilen
            filepath: Für Fehlermeldungen

        Rückgabe: Liste von (quantifier, variables)-Tupeln

        Raises:
            ParseError: Bei unbekanntem Quantor, fehlender 0, oder ungültigen Variablen
        """
        if not lines:
            raise ParseError(
                message="No quantifier prefix found. QBF formulas need at least one quantifier block.",
                filepath=filepath,
            )

        result: list[tuple[str, list[int]]] = []

        for line_num, line in lines:
            parts = line.strip().split()

            if not parts:
                continue

            quantifier_char = parts[0]

            if quantifier_char == "a":
                quantifier = "forall"
            elif quantifier_char == "e":
                quantifier = "exists"
            else:
                raise ParseError(
                    message=(
                        f"Unknown quantifier: '{quantifier_char}'. "
                        f"Expected 'a' (forall) or 'e' (exists)."
                    ),
                    filepath=filepath,
                    line_number=line_num,
                    line_content=line,
                )

            # Letzte Zahl muss 0 sein (Terminator)
            if parts[-1] != "0":
                raise ParseError(
                    message=(
                        f"Quantifier line does not end with 0. "
                        f"Found: '{parts[-1]}'"
                    ),
                    filepath=filepath,
                    line_number=line_num,
                    line_content=line,
                )

            # Variablen parsen (zwischen Quantor und abschließender 0)
            raw_vars = parts[1:-1]

            if not raw_vars:
                raise ParseError(
                    message=f"Quantifier block '{quantifier_char}' contains no variables.",
                    filepath=filepath,
                    line_number=line_num,
                    line_content=line,
                )

            variables: list[int] = []
            for token in raw_vars:
                try:
                    var = int(token)
                except ValueError:
                    raise ParseError(
                        message=f"Invalid variable in prefix: '{token}' is not an integer.",
                        filepath=filepath,
                        line_number=line_num,
                        line_content=line,
                    )

                if var <= 0:
                    raise ParseError(
                        message=(
                            f"Variables in the prefix must be positive integers, "
                            f"found {var}."
                        ),
                        filepath=filepath,
                        line_number=line_num,
                        line_content=line,
                    )

                variables.append(var)

            result.append((quantifier, variables))

        return result

    # ------------------------------------------------------------------ #
    # Matrix                                                               #
    # ------------------------------------------------------------------ #

    def _parse_matrix(
        self,
        lines: list[tuple[int, str]],
        filepath: str,
    ) -> list[list[int]]:
        """
        Parst alle Klausel-Zeilen der Matrix.

        Format je Zeile:
            1 -2 3 0   →  [1, -2, 3]
            -1 4 0     →  [-1, 4]

        Args:
            lines:    Nummerierte Klausel-Zeilen
            filepath: Für Fehlermeldungen

        Rückgabe: Liste von Klauseln als Integer-Listen

        Raises:
            ParseError: Bei fehlender 0, ungültigen Literalen oder Literal 0 in der Klausel
        """
        result: list[list[int]] = []

        for line_num, line in lines:
            parts = line.strip().split()

            if not parts:
                continue

            # Letzte Zahl muss 0 sein (Klausel-Terminator)
            if parts[-1] != "0":
                raise ParseError(
                    message=(
                        f"Clause does not end with 0. "
                        f"Found: '{parts[-1]}'"
                    ),
                    filepath=filepath,
                    line_number=line_num,
                    line_content=line,
                )

            # Literale parsen (alle außer der abschließenden 0)
            raw_literals = parts[:-1]

            clause: list[int] = []
            for token in raw_literals:
                try:
                    literal = int(token)
                except ValueError:
                    raise ParseError(
                        message=f"Invalid literal: '{token}' is not an integer.",
                        filepath=filepath,
                        line_number=line_num,
                        line_content=line,
                    )

                if literal == 0:
                    raise ParseError(
                        message="Literal 0 is not allowed inside a clause (0 is the terminator).",
                        filepath=filepath,
                        line_number=line_num,
                        line_content=line,
                    )

                clause.append(literal)

            # Leere Klausel → sofort UNSAT, trotzdem parsen und speichern
            result.append(clause)

        return result

    # ------------------------------------------------------------------ #
    # Konsistenz-Validierung                                               #
    # ------------------------------------------------------------------ #

    def _validate_counts(
        self,
        num_vars: int,
        num_clauses: int,
        prefix: list[tuple[str, list[int]]],
        matrix: list[list[int]],
        filepath: str,
    ) -> None:
        """
        Prüft ob num_vars und num_clauses mit dem tatsächlichen Inhalt übereinstimmen.

        Args:
            num_vars:    Deklarierte Variablenanzahl aus dem Header
            num_clauses: Deklarierte Klauselanzahl aus dem Header
            prefix:      Geparster Präfix
            matrix:      Geparste Matrix
            filepath:    Für Fehlermeldungen

        Raises:
            ParseError: Bei Abweichungen zwischen Header und tatsächlichem Inhalt
        """
        # Klauselanzahl prüfen
        if len(matrix) != num_clauses:
            raise ParseError(
                message=(
                    f"Header declares {num_clauses} clauses, "
                    f"but {len(matrix)} clauses were found."
                ),
                filepath=filepath,
            )

        # Höchste Variable im Präfix prüfen
        all_prefix_vars: list[int] = []
        for _, variables in prefix:
            all_prefix_vars.extend(variables)

        if all_prefix_vars:
            max_prefix_var = max(all_prefix_vars)
            if max_prefix_var > num_vars:
                raise ParseError(
                    message=(
                        f"Header declares {num_vars} variables, "
                        f"but prefix contains variable {max_prefix_var}."
                    ),
                    filepath=filepath,
                )

        # Variablen in der Matrix müssen im Präfix definiert sein
        defined_vars = set(all_prefix_vars)
        for clause_idx, clause in enumerate(matrix):
            for literal in clause:
                var = abs(literal)
                if var not in defined_vars:
                    raise ParseError(
                        message=(
                            f"Clause {clause_idx + 1}: variable {var} "
                            f"is not defined in the prefix."
                        ),
                        filepath=filepath,
                    )