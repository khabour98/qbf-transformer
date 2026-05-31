from __future__ import annotations

import time
from statistics import median, mean, stdev
from typing import Callable, TypeVar, Any

T = TypeVar("T")


class SolverTimer:
    """
    Kapselt hochauflösende Laufzeitmessung für wiederholte Solver-Aufrufe.

    Kernaufgaben:
        - Einzelnen Funktionsaufruf messen (measure)
        - Funktion n-mal wiederholen und alle Zeiten sammeln (measure_repeated)
        - Statistische Auswertung: Median, Mittelwert, Stddev, Min, Max
        - Laufzeit-Ratio zwischen Mutant und Original berechnen
    """

    def __init__(self, warmup_runs: int = 0) -> None:
        self.warmup_runs = warmup_runs


    def measure(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> tuple[T, float]:
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        return result, elapsed

    def measure_repeated(
        self,
        func: Callable[..., T],
        *args: Any,
        runs: int = 10,
        **kwargs: Any,
    ) -> tuple[list[T], list[float]]:
        # Aufwärm-Läufe (Ergebnisse verwerfen)
        for _ in range(self.warmup_runs):
            func(*args, **kwargs)

        results: list[T] = []
        times: list[float] = []

        for _ in range(runs):
            result, elapsed = self.measure(func, *args, **kwargs)
            results.append(result)
            times.append(elapsed)

        return results, times

    def compute_median(self, times: list[float]) -> float:
        """ Berechnet den Median der Laufzeiten """
        if not times:
            return 0.0
        return median(times)

    def compute_mean(self, times: list[float]) -> float:
        """ Berechnet den Mittelwert der Laufzeiten """
        if not times:
            return 0.0
        return mean(times)

    def compute_stdev(self, times: list[float]) -> float:
        """Berechnet die Standardabweichung der Laufzeiten """
        if len(times) < 2:
            return 0.0
        return stdev(times)

    def compute_min(self, times: list[float]) -> float:
        """ Gibt die schnellste Messung zurück """
        if not times:
            return 0.0
        return min(times)

    def compute_max(self, times: list[float]) -> float:
        """Gibt die langsamste Messung zurück """
        if not times:
            return 0.0
        return max(times)

    def compute_ratio(
        self,
        time_mutant: float,
        time_original: float,
    ) -> float:
        """Berechnet die Laufzeit-Ratio: Mutant / Original """
        if time_original == 0.0:
            return 1.0
        return time_mutant / time_original

    def summarize(self, times: list[float]) -> dict[str, float]:
        """ Gibt alle statistischen Kennzahlen als Dictionary zurück """
        return {
            "median": self.compute_median(times),
            "mean":   self.compute_mean(times),
            "stdev":  self.compute_stdev(times),
            "min":    self.compute_min(times),
            "max":    self.compute_max(times),
            "runs":   float(len(times)),
        }

    def is_stable(
        self,
        times: list[float],
        max_relative_stdev: float = 0.10,
    ) -> bool:
        """ Prüft ob die Messungen stabil genug sind """
        med = self.compute_median(times)
        if med == 0.0:
            return True
        relative_stdev = self.compute_stdev(times) / med
        return relative_stdev <= max_relative_stdev

    def __repr__(self) -> str:
        return f"SolverTimer(warmup_runs={self.warmup_runs})"