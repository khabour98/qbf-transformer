# Filtert QBFLIB-Formeln und wählt geeignete für das QBF-Transformer-Projekt aus.

from __future__ import annotations

import argparse
import random
import shutil
import subprocess
import sys
from pathlib import Path


def quick_parse(filepath: str) -> dict | None:
    """
    Schneller Parse-Check einer QDIMACS-Datei.
    Gibt None zurück wenn die Datei ungültig ist.
    Gibt ein Dict mit Metadaten zurück wenn gültig.
    """
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except OSError:
        return None

    num_vars    = None
    num_clauses = None
    prefix      = []
    clause_count = 0
    has_matrix  = False

    for line in lines:
        line = line.strip()
        if not line or line.startswith("c"):
            continue

        parts = line.split()
        if not parts:
            continue

        if parts[0] == "p":
            if len(parts) < 4 or parts[1] != "cnf":
                return None
            try:
                num_vars    = int(parts[2])
                num_clauses = int(parts[3])
            except ValueError:
                return None

        elif parts[0] in ("a", "e"):
            if num_vars is None:
                return None
            quantifier = "forall" if parts[0] == "a" else "exists"
            if parts[-1] != "0":
                return None
            try:
                variables = [int(v) for v in parts[1:-1]]
            except ValueError:
                return None
            if variables:
                prefix.append((quantifier, variables))

        else:
            # Klausel
            if num_vars is None:
                return None
            has_matrix = True
            if parts[-1] != "0":
                return None
            clause_count += 1

    if num_vars is None or num_clauses is None:
        return None

    if clause_count != num_clauses:
        return None

    if not prefix:
        return None

    if not has_matrix and num_clauses > 0:
        return None

    # Quantifier-Alternatierung prüfen
    quantifier_types = [q for q, _ in prefix]
    alternating = all(
        quantifier_types[i] != quantifier_types[i + 1]
        for i in range(len(quantifier_types) - 1)
    )

    return {
        "num_vars":    num_vars,
        "num_clauses": num_clauses,
        "prefix_blocks": len(prefix),
        "prefix": prefix,
        "quantifier_types": quantifier_types,
        "alternating": alternating,
        "has_universal": any(q == "forall" for q, _ in prefix),
        "has_existential": any(q == "exists" for q, _ in prefix),
    }


def run_solver(filepath: str, solver: str = "depqbf", timeout: float = 10) -> str | None:
    """
    Führt DepQBF auf einer Formel aus.
    Gibt "SAT", "UNSAT" oder None (Timeout/Fehler) zurück.
    """
    try:
        cmd = [solver, "--qdo", filepath]
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=timeout,
        )
        if result.returncode == 10:
            return "SAT"
        elif result.returncode == 20:
            return "UNSAT"
        else:
            return None
    except subprocess.TimeoutExpired:
        return None
    except FileNotFoundError:
        return None

def filter_and_copy(
    source_dir: str,
    output_dir: str,
    max_vars: int = 200,
    max_clauses: int = 1000,
    min_prefix_blocks: int = 2,
    count: int = 50,
    verify: bool = False,
    timeout: float = 10.0,
    solver: str = "depqbf",
    seed: int = 42,
    require_sat: bool = False,
    require_unsat: bool = False,
    shuffle: bool = True,
) -> list[str]:
    """
    Durchsucht source_dir rekursiv nach .qdimacs-Dateien,
    filtert nach Kriterien und kopiert geeignete nach output_dir.

    Gibt die Liste der kopierten Dateipfade zurück.
    """
    src  = Path(source_dir)
    out  = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # Alle .qdimacs Dateien finden
    all_files = list(src.rglob("*.qdimacs"))
    if not all_files:
        # Auch .gz Dateien? Hinweis geben
        gz_files = list(src.rglob("*.qdimacs.gz"))
        if gz_files:
            print(f"HINWEIS: {len(gz_files)} komprimierte .qdimacs.gz gefunden.")
            print("Bitte zuerst entpacken: find . -name '*.gz' -exec gunzip {} \\;")
        print(f"Keine .qdimacs Dateien in '{src}' gefunden.")
        return []

    print(f"Gefunden: {len(all_files)} .qdimacs Dateien in '{src}'")
    print(f"Filter:   vars<={max_vars}, clauses<={max_clauses}, "
          f"prefix_blocks>={min_prefix_blocks}")
    if verify:
        print(f"Solver:   {solver}, timeout={timeout}s")
    print()

    if shuffle:
        rng = random.Random(seed)
        rng.shuffle(all_files)

    copied   = []
    rejected = {"too_large": 0, "parse_error": 0, "trivial": 0,
                "solver_timeout": 0, "wrong_status": 0}
    checked  = 0

    for filepath in all_files:
        if len(copied) >= count:
            break

        checked += 1
        if checked % 100 == 0:
            print(f"  Geprüft: {checked}/{len(all_files)}  "
                  f"Ausgewählt: {len(copied)}/{count}  ...")

        # 1. Schneller Parse-Check
        meta = quick_parse(str(filepath))
        if meta is None:
            rejected["parse_error"] += 1
            continue

        # 2. Grössenprüfung
        if meta["num_vars"] > max_vars:
            rejected["too_large"] += 1
            continue
        if meta["num_clauses"] > max_clauses:
            rejected["too_large"] += 1
            continue

        # 3. Prafix-Prüfung (mindestens 2 Blöcke für interessante Formeln)
        if meta["prefix_blocks"] < min_prefix_blocks:
            rejected["trivial"] += 1
            continue

        # 4. Muss universelle UND existenzielle Variablen haben
        if not meta["has_universal"] or not meta["has_existential"]:
            rejected["trivial"] += 1
            continue

        # 5. Optional: Solver-Verifikation
        solver_status = None
        if verify:
            solver_status = run_solver(str(filepath), solver=solver, timeout=timeout)
            if solver_status is None:
                rejected["solver_timeout"] += 1
                continue
            if require_sat and solver_status != "SAT":
                rejected["wrong_status"] += 1
                continue
            if require_unsat and solver_status != "UNSAT":
                rejected["wrong_status"] += 1
                continue

        # Datei kopieren — eindeutigen Namen vergeben
        # (Verzeichnisstruktur in Dateiname kodieren)
        rel_path = filepath.relative_to(src)
        parts    = list(rel_path.parts)
        # Verzeichnis-Hierachie als Prefix
        if len(parts) > 1:
            family_prefix = "__".join(parts[:-1])
            new_name = f"{family_prefix}__{parts[-1]}"
        else:
            new_name = parts[-1]

        dest = out / new_name

        # Duplikat vermeiden
        if dest.exists():
            stem   = dest.stem
            suffix = dest.suffix
            dest   = out / f"{stem}_{len(copied):03d}{suffix}"

        shutil.copy2(str(filepath), str(dest))
        copied.append(str(dest))

        # Status-Ausgabe
        status_str = f"  [{solver_status or '?':4s}]" if verify else "  [OK  ]"
        print(
            f"{status_str} {new_name[:60]:<60}  "
            f"vars={meta['num_vars']:4d}  "
            f"clauses={meta['num_clauses']:5d}  "
            f"prefix={meta['prefix_blocks']}"
        )

    # Zusammenfassung
    print()
    print("=" * 70)
    print(f"Ergebnis: {len(copied)} Formeln kopiert nach '{out}'")
    print(f"  Geprüft:       {checked}")
    print(f"  Zu gross:       {rejected['too_large']}")
    print(f"  Parse-Fehler:   {rejected['parse_error']}")
    print(f"  Trivial:        {rejected['trivial']}")
    if verify:
        print(f"  Solver-Timeout: {rejected['solver_timeout']}")
        print(f"  Falscher Status:{rejected['wrong_status']}")
    print()

    if len(copied) < count:
        print(f"HINWEIS: Nur {len(copied)} von {count} gewünschten Formeln gefunden.")
        print("  Lösungen:")
        print("  - Grössenlimits erhöhen: --max-vars 500 --max-clauses 5000")
        print("  - Mehr Quell-Formeln herunterladen")
        print("  - Solver-Timeout erhöhen: --timeout 30")
    else:
        print(f"Nächster Schritt:")
        print(f"  python main.py --benchmark-dir {out}")
    print("=" * 70)

    return copied


def main() -> None:
    parser = argparse.ArgumentParser(
        description="QBFLIB Benchmark Filter — wählt geeignete Formeln aus",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--source", required=True,
        help="Verzeichnis mit entpackten QBFLIB .qdimacs Dateien"
    )
    parser.add_argument(
        "--output", default="benchmarks",
        help="Ausgabe-Verzeichnis für ausgewählte Formeln"
    )
    parser.add_argument(
        "--max-vars", type=int, default=200,
        help="Maximale Variablenanzahl (grössere werden übersprungen)"
    )
    parser.add_argument(
        "--max-clauses", type=int, default=1000,
        help="Maximale Klauselanzahl"
    )
    parser.add_argument(
        "--min-prefix-blocks", type=int, default=2,
        help="Mindestanzahl Quantoren-Blöcke (z.B. 2 = mindestens forall+exists)"
    )
    parser.add_argument(
        "--count", type=int, default=50,
        help="Anzahl zu kopierender Formeln"
    )
    parser.add_argument(
        "--verify", action="store_true",
        help="Jede Formel mit DepQBF lösen (langsamer, aber sicherer)"
    )
    parser.add_argument(
        "--timeout", type=float, default=10.0,
        help="Solver-Timeout in Sekunden (nur mit --verify)"
    )
    parser.add_argument(
        "--solver", default="depqbf",
        help="Solver-Binary für --verify"
    )
    parser.add_argument(
        "--only-sat", action="store_true",
        help="Nur SAT-Formeln (nur mit --verify)"
    )
    parser.add_argument(
        "--only-unsat", action="store_true",
        help="Nur UNSAT-Formeln (nur mit --verify)"
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Zufalls-Seed für die Reihenfolge"
    )
    parser.add_argument(
        "--no-shuffle", action="store_true",
        help="Dateien in Verzeichnis-Reihenfolge (nicht zufällig)"
    )

    args = parser.parse_args()

    if args.only_sat and args.only_unsat:
        print("Fehler: --only-sat und --only-unsat können nicht zusammen verwendet werden.")
        sys.exit(1)

    filter_and_copy(
        source_dir=args.source,
        output_dir=args.output,
        max_vars=args.max_vars,
        max_clauses=args.max_clauses,
        min_prefix_blocks=args.min_prefix_blocks,
        count=args.count,
        verify=args.verify,
        timeout=args.timeout,
        solver=args.solver,
        seed=args.seed,
        require_sat=args.only_sat,
        require_unsat=args.only_unsat,
        shuffle=not args.no_shuffle,
    )


if __name__ == "__main__":
    main()