"""Matter family and chamber templates.

Templates are written against abstract roles (lowercase letters). A seed decides
which visible substance plays which role, so nothing in a chamber's appearance
reveals how its contents behave.
"""
from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field

from .engine import EMPTY, GATE, LIQUID, MAT0, POWDER, SOLID, WALL, Physics, World

# role -> (phase, gravity, density)
ROLES = {
    "w": (LIQUID, 1, 20),   # carrier liquid
    "s": (POWDER, 1, 40),   # heavy powder, piles and plugs
    "g": (LIQUID, -1, 10),  # rises and spreads under ceilings
    "e": (POWDER, -1, 30),  # powder that falls upward
    "a": (LIQUID, 1, 30),   # solvent
    "k": (SOLID, 1, 0),     # seal, static
    "x": (SOLID, 1, 0),     # crust (product)
    "q": (LIQUID, 1, 15),   # elixir (product), floats on the carrier
    "c": (LIQUID, 1, 35),   # corrosive (product), eats walls
    "o": (LIQUID, 1, 12),   # light liquid that spoils the elixir
}
ROLE_ORDER = "wsgeakoxqc"
BASE_ROLES = "wsgeako"
ROLE_ID = {r: MAT0 + i for i, r in enumerate(ROLE_ORDER)}
# (a, b, a', b', bulk_a, bulk_b). None = vanishes. bulk_* = how many
# same-kind neighbours that reactant needs, so some reactions only happen in
# quantity. "#" as b means a wall cell.
REACTIONS = [
    ("a", "k", None, None, 0, 0),
    ("a", "s", None, None, 0, 0),
    ("w", "g", "x", "x", 0, 1),
    ("w", "e", "q", None, 0, 0),
    ("q", "e", "q", "q", 0, 0),
    ("q", "a", "c", "c", 0, 0),
    ("c", "#", None, None, 0, 0),
    ("o", "q", "o", "o", 0, 0),
]

SYMBOLS = "ABCDEFGHJK"
NAMES = ["Vex", "Oru", "Kith", "Zam", "Ylo", "Bren", "Quil", "Tosk", "Ixa", "Mur", "Dael", "Fyn"]
COLORS = ["#ff375f", "#64d2ff", "#ffd60a", "#bf5af2", "#ff9f0a", "#30d158", "#0a84ff", "#e5e5ea", "#ac8e68", "#ff6961"]


def family_physics() -> Physics:
    p = Physics()
    for r, (ph, gr, de) in ROLES.items():
        i = ROLE_ID[r]
        p.phase[i], p.grav[i], p.dens[i] = ph, gr, de
    for a, b, a2, b2, na, nb in REACTIONS:
        p.add_reaction(ROLE_ID[a], WALL if b == "#" else ROLE_ID[b],
                       ROLE_ID[a2] if a2 else EMPTY, ROLE_ID[b2] if b2 else EMPTY, na, nb)
    return p


@dataclass
class Template:
    name: str
    tier: int
    rows: list
    zones: dict       # zone name -> (x0, y0, x1, y1), inclusive
    objectives: list  # (zone, role, min_count)


@dataclass
class Chamber:
    name: str
    tier: int
    world: World
    zones: dict
    objectives: list  # (zone, material id, min_count)
    gates: list
    opened: list = field(default_factory=list)
    closed: bool = False

    def met(self) -> list:
        return [self.world.count(m, self.zones[z]) >= n for z, m, n in self.objectives]

    def complete(self) -> bool:
        return all(self.met())

    def remaining_gates(self) -> list:
        return [g for g in self.gates if g not in self.opened]

    def active(self) -> bool:
        return not self.closed and not self.complete() and bool(self.remaining_gates())

    def copy(self) -> "Chamber":
        return Chamber(self.name, self.tier, self.world.copy(), self.zones, self.objectives,
                       self.gates, list(self.opened), self.closed)


def build(t: Template, flip: bool) -> Chamber:
    rows = [r[::-1] for r in t.rows] if flip else list(t.rows)
    h, w = len(rows), len(rows[0])
    assert all(len(r) == w for r in rows), t.name
    world = World.blank(w, h)
    gate = bytearray(w * h)
    gates = set()
    for y, row in enumerate(rows):
        for x, c in enumerate(row):
            i = y * w + x
            if c == "#":
                world.cell[i] = WALL
            elif c.isdigit():
                world.cell[i] = GATE
                gate[i] = int(c)
                gates.add(int(c))
            elif c in ROLE_ID:
                world.cell[i] = ROLE_ID[c]
            else:
                assert c == ".", (t.name, c)
    world.gate = bytes(gate)
    zones = {}
    for z, (x0, y0, x1, y1) in t.zones.items():
        zones[z] = (w - 1 - x1, y0, w - 1 - x0, y1) if flip else (x0, y0, x1, y1)
    objs = [(z, ROLE_ID[r], n) for z, r, n in t.objectives]
    return Chamber(t.name, t.tier, world, zones, objs, sorted(gates))


@dataclass
class Skin:
    """Seeded mapping from internal material ids to what a player sees."""
    symbol: dict
    name: dict
    color: dict

    def by_symbol(self) -> dict:
        return {s: i for i, s in self.symbol.items()}


def rng_for(seed: int, salt: str, purpose: str) -> random.Random:
    d = hashlib.sha256(f"{salt}|{seed}|{purpose}".encode()).digest()
    return random.Random(int.from_bytes(d[:8], "big"))


def make_skin(rng: random.Random) -> Skin:
    syms = list(SYMBOLS)
    names = list(NAMES)
    cols = list(COLORS)
    rng.shuffle(syms)
    rng.shuffle(names)
    rng.shuffle(cols)
    ids = [ROLE_ID[r] for r in ROLE_ORDER]
    return Skin({i: syms[k] for k, i in enumerate(ids)},
                {i: names[k] for k, i in enumerate(ids)},
                {i: cols[k] for k, i in enumerate(ids)})


def relabel_gates(ch: Chamber, rng: random.Random) -> None:
    """Shuffle gate numbers so a gate's number carries no hint about order."""
    perm = list(ch.gates)
    rng.shuffle(perm)
    m = dict(zip(ch.gates, perm))
    ch.world.gate = bytes(m.get(g, 0) for g in ch.world.gate)


TEMPLATES: list = []


def _t(name, tier, rows, zones, objectives):
    TEMPLATES.append(Template(name, tier, [r for r in rows.strip("\n").split("\n")], zones, objectives))
