"""Engine, scoring and reward-integrity tests. Run: python3 -m unittest discover tests"""
import itertools
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "engine"))
sys.path.insert(0, os.path.join(ROOT, "reference"))

from crucible.episode import LAB_RUNS, ActionError, Episode, replay  # noqa: E402
from crucible.oracle import Oracle, apply_open  # noqa: E402

SEEDS = [1, 2, 3]


def winning_journal(seed):
    ep = Episode(seed)
    j = []
    for i, ch in enumerate(ep.chambers):
        for g in Oracle(ep.phys).solve(ch):
            j.append({"t": "open", "chamber": i + 1, "gate": g})
    return j


def reward(seed, journal):
    """Mirror of tests/grade.py: a rejected journal scores 0."""
    try:
        return replay(seed, journal).score()["reward"]
    except ActionError:
        return 0.0


class Engine(unittest.TestCase):
    def test_deterministic(self):
        for seed in SEEDS:
            j = winning_journal(seed)
            a, b = replay(seed, j), replay(seed, j)
            for x, y in zip(a.chambers, b.chambers):
                self.assertEqual(bytes(x.world.cell), bytes(y.world.cell))

    def test_reference_scores_one(self):
        for seed in SEEDS:
            self.assertEqual(reward(seed, winning_journal(seed)), 1.0)

    def test_skins_differ_between_seeds(self):
        skins = {tuple(sorted(Episode(s).skin.symbol.items())) for s in range(1, 9)}
        self.assertGreater(len(skins), 4)

    def test_lab_matches_chamber_rules(self):
        ep = Episode(1)
        syms = [s["symbol"] for s in ep.brief()["substances"]]
        r = ep.lab([syms[0] * 3])
        self.assertTrue(r["came_to_rest"])
        self.assertEqual(len(r["end"]), 8)


class Discoverability(unittest.TestCase):
    """Every rule a chamber depends on must be observable inside the lab box."""

    def setUp(self):
        from crucible.chambers import ROLE_ID
        self.ep = Episode(5)
        self.s = {r: self.ep.skin.symbol[i] for r, i in ROLE_ID.items()}

    def seen(self, rows):
        return {frozenset(r["between"]) for r in self.ep.lab(rows)["reactions"]}

    def test_bulk_reaction_shows_with_three_cells_but_not_one(self):
        w, g = self.s["w"], self.s["g"]
        self.assertFalse(self.seen([w, "", g]))
        self.assertIn(frozenset([w, g]), self.seen([w * 3, "", g * 3]))

    def test_chain_to_wall_eater_can_be_staged(self):
        s = self.s
        got = self.seen([s["a"] + s["w"], "", "." + s["e"]])
        self.assertIn(frozenset([s["w"], s["e"]]), got)
        self.assertIn(frozenset([s["a"], s["q"]]), got)
        self.assertIn(frozenset([s["c"], "wall (#)"]), got)

    def test_simple_pairs(self):
        s = self.s
        self.assertIn(frozenset([s["a"], s["k"]]), self.seen([s["a"], s["k"]]))
        self.assertIn(frozenset([s["a"], s["s"]]), self.seen([s["a"], s["s"]]))


class RewardIntegrity(unittest.TestCase):
    def test_do_nothing_is_zero(self):
        for seed in SEEDS:
            self.assertEqual(reward(seed, []), 0.0)

    def test_lab_only_is_zero(self):
        ep = Episode(1)
        s = ep.brief()["substances"][0]["symbol"]
        self.assertEqual(reward(1, [{"t": "lab", "rows": [s]}] * LAB_RUNS), 0.0)

    def test_close_everything_is_zero(self):
        self.assertEqual(reward(1, [{"t": "close", "chamber": c} for c in (1, 2, 3, 4, 5)]), 0.0)

    def test_strict_prefixes_never_beat_completion(self):
        for seed in SEEDS:
            j = winning_journal(seed)
            for k in range(len(j)):
                self.assertLess(reward(seed, j[:k]), 1.0)
            first = [e for e in j if e["chamber"] == 1]
            self.assertEqual(reward(seed, first[:-1]), 0.0)

    def test_every_single_action_scores_low(self):
        for seed in SEEDS:
            ep = Episode(seed)
            for i, ch in enumerate(ep.chambers):
                for g in ch.gates:
                    self.assertLess(reward(seed, [{"t": "open", "chamber": i + 1, "gate": g}]), 0.21)

    def test_random_play_is_far_below_reference(self):
        import random
        rng = random.Random(0)
        total = 0.0
        n = 300
        for _ in range(n):
            ep = Episode(1)
            for i, ch in enumerate(ep.chambers):
                gates = list(ch.gates)
                rng.shuffle(gates)
                for g in gates:
                    if not ch.active():
                        break
                    ep.open(i, g)
            total += ep.score()["reward"]
        self.assertLess(total / n, 0.35)

    def test_other_seed_solution_does_not_transfer_by_construction(self):
        # The same gate numbers are legal on another seed, so the journal is
        # accepted, but it is scored against that seed's own world.
        j = winning_journal(1)
        got = [reward(s, j) for s in range(2, 12)]
        self.assertLess(sum(got) / len(got), 0.6)

    def test_repeat_and_illegal_actions_rejected(self):
        j = winning_journal(1)
        bad = [
            j + [j[0]],                                              # reopen a gate / act on a complete chamber
            [{"t": "open", "chamber": 1, "gate": 99}],
            [{"t": "open", "chamber": 0, "gate": 1}],
            [{"t": "open", "chamber": 6, "gate": 1}],
            [{"t": "open", "chamber": True, "gate": 1}],
            [{"t": "open", "chamber": 1, "gate": "1"}],
            [{"t": "open", "chamber": 1, "gate": 1.0}],
            [{"t": "win"}],
            [{"t": "open", "chamber": 1, "gate": 1, "complete": True}] * 2,
            ["open"],
            [{"t": "lab", "rows": ["Z"]}],
            [{"t": "lab", "rows": ["." * 9]}],
            [{"t": "lab", "rows": ["."] * 7}],
            [{"t": "lab", "rows": "...."}],
            [{"t": "lab", "rows": [1, 2]}],
            [{"t": "close", "chamber": 1}, {"t": "open", "chamber": 1, "gate": 1}],
        ]
        for b in bad:
            self.assertEqual(reward(1, b), 0.0, b)
        with self.assertRaises(ActionError):
            replay(1, {"t": "open"})

    def test_extra_fields_cannot_forge_completion(self):
        self.assertEqual(reward(1, [{"t": "close", "chamber": 1, "reward": 1, "complete": True}]), 0.0)

    def test_lab_budget_enforced(self):
        ep = Episode(1)
        for _ in range(LAB_RUNS):
            ep.lab(["."])
        with self.assertRaises(ActionError):
            ep.lab(["."])

    def test_lab_cannot_touch_chambers(self):
        ep = Episode(1)
        before = [bytes(c.world.cell) for c in ep.chambers]
        syms = "".join(s["symbol"] for s in ep.brief()["substances"])
        for _ in range(LAB_RUNS):
            ep.lab([syms[:8]] * 6)
        self.assertEqual(before, [bytes(c.world.cell) for c in ep.chambers])
        self.assertEqual(ep.score()["reward"], 0.0)

    def test_reward_bounded_over_all_lines(self):
        ep = Episode(2)
        for i, ch in enumerate(ep.chambers[:2]):
            for seq in itertools.permutations(ch.gates):
                e = Episode(2)
                for g in seq:
                    if e.chambers[i].active():
                        e.open(i, g)
                r = e.score()["reward"]
                self.assertTrue(0.0 <= r <= 1.0)

    def test_completion_locks_chamber(self):
        ep = replay(1, winning_journal(1))
        for i in range(5):
            with self.assertRaises(ActionError):
                ep.open(i, ep.initial[i].gates[0])


class OracleDiagnostics(unittest.TestCase):
    def test_first_fatal_move_is_flagged(self):
        ep = Episode(1)
        ch = ep.chambers[4]
        o = Oracle(ep.phys)
        fatal = [g for g, n in o.options(ch).items() if n == 0]
        self.assertTrue(fatal)
        rows = o.trace(ch, [fatal[0]])
        self.assertTrue(rows[0]["fatal"])
        self.assertEqual(rows[0]["wins_after"], 0)
        self.assertGreater(rows[0]["wins_before"], 0)
        self.assertTrue(rows[0]["safe_alternatives"])

    def test_win_counts_are_consistent(self):
        ep = Episode(1)
        ch = ep.chambers[1]
        o = Oracle(ep.phys)
        self.assertEqual(o.wins(ch), sum(o.options(ch).values()))


if __name__ == "__main__":
    unittest.main()
