#!/usr/bin/env python3
"""Scores of trivial policies, graded exactly as the verifier grades (journal replay).

Usage: baselines.py [seed ...]
"""
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "engine"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from analyze import reference_journal  # noqa: E402
from crucible.episode import Episode, replay  # noqa: E402


def random_journal(seed: int, rng: random.Random) -> list:
    ep = Episode(seed)
    for i, ch in enumerate(ep.chambers):
        gates = list(ch.gates)
        rng.shuffle(gates)
        for g in gates:
            if ch.active():
                ep.open(i, g)
    return ep.journal


def main():
    seeds = [int(a) for a in sys.argv[1:]] or [1, 2, 3, 4, 5]
    print(f"{'seed':>4}  {'do nothing':>10}  {'stop early':>10}  {'ref minus last':>14}  {'random (n=200)':>14}  {'reference':>9}")
    for seed in seeds:
        ref = reference_journal(seed, "crucible-public-v1")
        score = lambda j: replay(seed, j).score()["reward"]
        first = [{"t": "open", "chamber": i + 1, "gate": ch.gates[0]} for i, ch in enumerate(Episode(seed).chambers)]
        rng = random.Random(seed)
        rnd = sum(score(random_journal(seed, rng)) for _ in range(200)) / 200
        print(f"{seed:>4}  {score([]):>10.3f}  {score(first):>10.3f}  {score(ref[:-1]):>14.3f}  {rnd:>14.3f}  {score(ref):>9.3f}")


if __name__ == "__main__":
    main()
