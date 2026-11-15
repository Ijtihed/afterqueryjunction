"""Exhaustive search over gate orders. Chambers have few gates, so every line
of play is enumerated and solvability claims are exact, not heuristic."""
from __future__ import annotations

from .chambers import Chamber
from .engine import Physics, settle


def apply_open(ch: Chamber, phys: Physics, gate: int, want_frames: bool = False):
    ch.world.open_gate(gate)
    ch.opened.append(gate)
    return settle(ch.world, phys, want_frames)


class Oracle:
    def __init__(self, phys: Physics):
        self.phys = phys
        self.memo: dict = {}

    def wins(self, ch: Chamber) -> int:
        """Number of distinct winning gate orders from this state."""
        if ch.complete():
            return 1
        k = ch.world.key()
        if k in self.memo:
            return self.memo[k]
        total = 0
        for g in ch.remaining_gates():
            c = ch.copy()
            apply_open(c, self.phys, g)
            total += self.wins(c)
        self.memo[k] = total
        return total

    def options(self, ch: Chamber) -> dict:
        """gate -> winning orders that remain after opening it."""
        out = {}
        for g in ch.remaining_gates():
            c = ch.copy()
            apply_open(c, self.phys, g)
            out[g] = self.wins(c)
        return out

    def solve(self, ch: Chamber):
        """One shortest winning order, or None."""
        best = None
        frontier = [(ch.copy(), [])]
        while frontier and best is None:
            nxt = []
            for c, path in frontier:
                if c.complete():
                    best = path
                    break
                for g in c.remaining_gates():
                    if self.options(c)[g] > 0:
                        d = c.copy()
                        apply_open(d, self.phys, g)
                        nxt.append((d, path + [g]))
            frontier = nxt
        return best

    def trace(self, ch: Chamber, gates: list) -> list:
        """Per-action solvability record for a line of play from ch."""
        c = ch.copy()
        rows = []
        for g in gates:
            before = self.wins(c)
            opts = self.options(c)
            met_before = sum(c.met())
            apply_open(c, self.phys, g)
            after = self.wins(c)
            rows.append({
                "gate": g,
                "wins_before": before,
                "wins_after": after,
                "fatal": before > 0 and after == 0,
                "safe_alternatives": sorted(a for a, n in opts.items() if n > 0),
                "objectives_met_before": met_before,
                "objectives_met_after": sum(c.met()),
            })
        return rows
