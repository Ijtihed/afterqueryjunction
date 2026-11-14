#!/usr/bin/env python3
"""Exhaustively check every chamber of the given seeds.

For each chamber: no objective is met before any action, every reachable line
of play comes to rest, at least one winning order exists, and a fatal first
move exists (so order genuinely matters). Usage: validate.py [seed ...]
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "engine"))
from crucible.episode import Episode  # noqa: E402
from crucible.oracle import Oracle, apply_open  # noqa: E402


def check(seed: int) -> bool:
    ep = Episode(seed)
    ok = ep.score()["reward"] == 0.0
    line = [f"seed {seed:>3}"]
    for ch in ep.chambers:
        o = Oracle(ep.phys)
        wins = o.wins(ch)
        seen, stack, unsettled, total = set(), [ch.copy()], 0, 0
        while stack:
            c = stack.pop()
            total += 1
            if not c.active():
                continue
            for g in c.remaining_gates():
                d = c.copy()
                unsettled += not apply_open(d, ep.phys, g).settled
                key = d.world.key()
                if key not in seen:
                    seen.add(key)
                    stack.append(d)
        fatal_first = sum(1 for n in o.options(ch).values() if n == 0)
        good = wins > 0 and unsettled == 0 and not any(ch.met()) and fatal_first > 0
        ok &= good
        line.append(f"{ch.name}: {wins} winning orders, {total} reachable states, {fatal_first}/{len(ch.gates)} fatal first moves"
                    + ("" if good else "  <-- BAD"))
    print(" | ".join(line))
    return ok


if __name__ == "__main__":
    seeds = [int(a) for a in sys.argv[1:]] or list(range(1, 21))
    bad = [s for s in seeds if not check(s)]
    print("all seeds valid" if not bad else f"INVALID seeds: {bad}")
    sys.exit(1 if bad else 0)
