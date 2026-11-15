#!/usr/bin/env python3
"""Reference player.

It knows the matter family (which kinds of behaviour and reaction can exist)
but not which visible substance has which behaviour: that is identified with
three lab runs through the same public interface an agent uses. It then plans
each chamber by exhaustive search in its own copy of the simulator and checks
every prediction against what the facility reports.
"""
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from crucible.chambers import ROLE_ID, Chamber, family_physics  # noqa: E402
from crucible.engine import EMPTY, GATE, WALL, World  # noqa: E402
from crucible.oracle import Oracle, apply_open  # noqa: E402

URL = os.environ.get("CRUCIBLE_URL", "http://sim:8000")
W, H = 8, 6


def call(cmd, **body):
    req = urllib.request.Request(f"{URL}/api/{cmd}", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def columns(spec):
    """spec: list of {row: symbol} per compartment; compartments are 1-wide
    columns at even x, separated by full-height walls."""
    rows = []
    for y in range(H):
        rows.append("".join((spec[x // 2].get(y, ".") if x // 2 < len(spec) else ".") if x % 2 == 0 else "#"
                            for x in range(W)))
    end = call("lab", rows=rows)["end"]
    # end includes the enclosing wall; compartment k is at end x = 1 + 2k
    return [[end[y + 1][1 + 2 * k] for y in range(H)] for k in range(len(spec))]


def identify(symbols):
    """Six lab runs: two for how each substance moves alone, three for the
    contacts that tell apart substances that move alike, one for the crust."""
    cols = columns([{2: s} for s in symbols[:4]]) + columns([{2: s} for s in symbols[4:]])
    down, up, static = [], [], []
    for s, col in zip(symbols, cols):
        (down if col[H - 1] == s else up if col[0] == s else static).append(s)
    assert len(down) == 4 and len(up) == 2 and len(static) == 1, (down, up, static)
    k = static[0]
    cols = columns([{H - 1: k, 1: d} for d in down])
    a = down[[all(c == "." for c in col) for col in cols].index(True)]
    rest = [d for d in down if d != a]
    cols = columns([{H - 1: d, 1: a} for d in rest])
    s = rest[[all(c == "." for c in col) for col in cols].index(True)]
    liquids = [d for d in rest if d != s]
    pairs = [(d, u) for d in liquids for u in up]
    cols = columns([{1: d, 4: u} for d, u in pairs])
    role = {s: "s", a: "a", k: "k"}
    for (d, u), col in zip(pairs, cols):
        left = [c for c in col if c != "."]
        if len(left) == 1:
            role[d], role[u], role[left[0]] = "w", "e", "q"
    role[next(d for d in liquids if d not in role)] = "o"
    g = next(u for u in up if u not in role)
    role[g] = "g"
    # The crust only forms in bulk, so it needs its own three-against-three run.
    w = next(sym for sym, r in role.items() if r == "w")
    end = call("lab", rows=[w * 3, "", g * 3])["end"]
    new = {c for row in end for c in row} - set(role) - set("#.")
    assert len(new) == 1, new
    role[new.pop()] = "x"
    return role


def to_chamber(view, role):
    rows = view["grid"]
    h, w = len(rows), len(rows[0])
    world = World.blank(w, h)
    gate = bytearray(w * h)
    for y, r in enumerate(rows):
        for x, c in enumerate(r):
            i = y * w + x
            if c == "#":
                world.cell[i] = WALL
            elif c.isdigit():
                world.cell[i] = GATE
                gate[i] = int(c)
            elif c != ".":
                world.cell[i] = ROLE_ID[role[c]]
    world.gate = bytes(gate)
    zones = {o["zone"]: (o["x"][0], o["y"][0], o["x"][1], o["y"][1]) for o in view["objectives"]}
    objs = [(o["zone"], ROLE_ID[role[o["substance"]]], o["min_cells"]) for o in view["objectives"]]
    return Chamber("ref", 0, world, zones, objs, sorted(view["gates_closed"]))


def matches(ch, role, grid):
    """Compare the model with the facility's grid. Product substances are met
    for the first time here, so their symbols are bound on first sight."""
    inv = {ROLE_ID[r]: sym for sym, r in role.items()}
    by_id = {v: r for r, v in ROLE_ID.items()}
    w = ch.world
    for y in range(w.h):
        for x in range(w.w):
            c, got = w.cell[y * w.w + x], grid[y][x]
            want = "#" if c == WALL else "." if c == EMPTY else str(w.gate[y * w.w + x]) if c == GATE else inv.get(c)
            if want is None and got not in role and got not in "#." and not got.isdigit():
                role[got] = by_id[c]
                inv[c] = want = got
            if want != got:
                return False
    return True


def main():
    brief = call("brief")
    role = identify([s["symbol"] for s in brief["substances"]])
    print("identified roles:", role)
    phys = family_physics()
    for n in range(1, len(brief["chambers"]) + 1):
        ch = to_chamber(call("view", chamber=n), role)
        plan = Oracle(phys).solve(ch)
        print(f"chamber {n}: plan {plan}")
        if plan is None:
            sys.exit(f"chamber {n}: no winning order exists in the reference model")
        for g in plan:
            apply_open(ch, phys, g)
            got = call("open", chamber=n, gate=g)
            if not matches(ch, role, got["grid"]):
                sys.exit(f"chamber {n}: facility diverged from the reference model after gate {g}")
        print(f"chamber {n}: {call('view', chamber=n)['status']}")


if __name__ == "__main__":
    main()
