"""Episode state machine: one hidden matter skin, a budgeted lab, and three
one-shot chambers. Every accepted action is appended to a journal, and an
episode can be rebuilt from (seed, journal) alone."""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from . import templates  # noqa: F401  (registers templates)
from .chambers import (BASE_ROLES, ROLE_ID, TEMPLATES, Chamber, Skin, build, family_physics,
                       make_skin, relabel_gates, rng_for)
from .engine import EMPTY, GATE, MAT0, WALL, World, settle
from .oracle import apply_open

LAB_W, LAB_H, LAB_RUNS = 8, 6, 9
TIER_PLAN = [(3, 3)]  # (tier, chambers drawn without repeats)
WEIGHTS = {3: 1 / 3}
PARTIAL = 0.3
DEFAULT_SALT = "crucible-public-v1"
MAX_FRAMES_KEPT = 600


class ActionError(Exception):
    pass


@dataclass
class Episode:
    seed: int
    salt: str = DEFAULT_SALT
    journal: list = field(default_factory=list)
    lab_budget: int = 0  # 0 means the default LAB_RUNS

    def __post_init__(self):
        self.lab_budget = self.lab_budget or LAB_RUNS
        self.phys = family_physics()
        self.skin: Skin = make_skin(rng_for(self.seed, self.salt, "skin"))
        r = rng_for(self.seed, self.salt, "chambers")
        self.chambers: list = []
        for tier, count in TIER_PLAN:
            pool = [t for t in TEMPLATES if t.tier == tier]
            for t in r.sample(pool, count):
                ch = build(t, r.random() < 0.5)
                relabel_gates(ch, r)
                self.chambers.append(ch)
        self.initial = [c.copy() for c in self.chambers]
        self.lab_runs: list = []
        self.last_frames: dict = {}
        self.base_ids = [ROLE_ID[x] for x in BASE_ROLES]

    # ---- rendering -------------------------------------------------------
    def sym(self, c: int, gate: int = 0) -> str:
        if c == EMPTY:
            return "."
        if c == WALL:
            return "#"
        if c == GATE:
            return str(gate)
        return self.skin.symbol[c]

    def rows(self, world: World, cells=None) -> list:
        cells = world.cell if cells is None else cells
        return ["".join(self.sym(cells[y * world.w + x], world.gate[y * world.w + x]) for x in range(world.w))
                for y in range(world.h)]

    def substance(self, i: int) -> dict:
        return {"symbol": self.skin.symbol[i], "name": self.skin.name[i], "color": self.skin.color[i]}

    def _reactions(self, rx: dict, before: dict, after: dict) -> list:
        out = []
        merged = {}
        for (a, b), n in rx.items():
            k = (a, b) if (b, a) not in merged else (b, a)
            merged[k] = merged.get(k, 0) + n
        for (a, b), n in sorted(merged.items()):
            a2, b2 = self.phys.rx[(a * 32 + b) * 2], self.phys.rx[(a * 32 + b) * 2 + 1]

            def nm(v):
                return "wall (#)" if v == WALL else "nothing" if v == EMPTY else self.skin.symbol[v]
            out.append({"between": [nm(a), nm(b)], "contacts": n,
                        "result": f"{nm(a)} became {nm(a2)}, {nm(b)} became {nm(b2)}"})
        return out

    # ---- public views ----------------------------------------------------
    def brief(self) -> dict:
        return {
            "substances": sorted((self.substance(i) for i in self.base_ids), key=lambda s: s["symbol"]),
            "note": "Other substances may appear when substances touch. Their symbols are shown when they exist.",
            "lab": {"width": LAB_W, "height": LAB_H, "runs_total": self.lab_budget, "runs_left": self.lab_budget - len(self.lab_runs)},
            "chambers": [self.view(i, grid=False) for i in range(len(self.chambers))],
            "scoring": {"weights": [round(WEIGHTS[c.tier], 3) for c in self.chambers], "partial_factor": PARTIAL},
        }

    def view(self, idx: int, grid: bool = True) -> dict:
        ch = self._ch(idx)
        met = ch.met()
        v = {
            "chamber": idx + 1, "width": ch.world.w, "height": ch.world.h,
            "status": "complete" if ch.complete() else "closed" if not ch.active() else "active",
            "gates_closed": ch.remaining_gates(), "gates_opened_in_order": list(ch.opened),
            "objectives": [
                {"zone": z, "x": [ch.zones[z][0], ch.zones[z][2]], "y": [ch.zones[z][1], ch.zones[z][3]],
                 "needs": f"at least {n} cells of {self.skin.symbol[m]} ({self.skin.name[m]}) resting inside the zone",
                 "substance": self.skin.symbol[m], "min_cells": n,
                 "current_cells": ch.world.count(m, ch.zones[z]), "met": met[k]}
                for k, (z, m, n) in enumerate(ch.objectives)],
        }
        if grid:
            v["grid"] = self.rows(ch.world)
            present = sorted({c for c in ch.world.cell if c >= MAT0})
            v["substances_present"] = [self.substance(i) for i in present]
        return v

    # ---- actions ---------------------------------------------------------
    def _ch(self, idx: int) -> Chamber:
        if not isinstance(idx, int) or isinstance(idx, bool) or not 0 <= idx < len(self.chambers):
            raise ActionError(f"chamber must be 1..{len(self.chambers)}")
        return self.chambers[idx]

    def lab(self, rows, record: bool = True) -> dict:
        if len(self.lab_runs) >= self.lab_budget:
            raise ActionError("no lab runs left")
        if not isinstance(rows, list) or not rows or len(rows) > LAB_H or not all(isinstance(r, str) for r in rows):
            raise ActionError(f"layout must be 1..{LAB_H} text rows")
        if any(len(r) > LAB_W for r in rows):
            raise ActionError(f"rows must be at most {LAB_W} characters")
        by_sym = {self.skin.symbol[i]: i for i in self.base_ids}
        rows = [r.ljust(LAB_W, ".") for r in rows]
        rows = ["." * LAB_W] * (LAB_H - len(rows)) + rows
        w, h = LAB_W + 2, LAB_H + 2
        world = World.blank(w, h)
        for i in range(w * h):
            x, y = i % w, i // w
            if x in (0, w - 1) or y in (0, h - 1):
                world.cell[i] = WALL
        for y, r in enumerate(rows):
            for x, c in enumerate(r):
                if c == "#":
                    v = WALL
                elif c in (".", " "):
                    v = EMPTY
                elif c in by_sym:
                    v = by_sym[c]
                else:
                    raise ActionError(f"unknown symbol {c!r}; use . # or one of {''.join(sorted(by_sym))}")
                world.cell[(y + 1) * w + x + 1] = v
        start = self.rows(world)
        res = settle(world, self.phys, want_frames=True)
        n = len(self.lab_runs) + 1
        self.lab_runs.append(rows)
        if record:
            self.journal.append({"t": "lab", "rows": rows})
        self.last_frames[("lab", n)] = (world.w, world.h, world.gate, None, res.frames[:MAX_FRAMES_KEPT], start)
        return {"run": n, "runs_left": self.lab_budget - n, "ticks": res.ticks, "came_to_rest": res.settled,
                "start": start, "end": self.rows(world), "reactions": self._reactions(res.reactions, {}, {}),
                "note": "The lab box is enclosed by walls on all four sides (shown)."}

    def open(self, idx: int, gate, record: bool = True) -> dict:
        ch = self._ch(idx)
        if not ch.active():
            raise ActionError("chamber is not active")
        if not isinstance(gate, int) or isinstance(gate, bool) or gate not in ch.remaining_gates():
            raise ActionError(f"gate must be one of {ch.remaining_gates()}")
        start = self.rows(ch.world)
        ch.world.open_gate(gate)
        ch.opened.append(gate)
        res = settle(ch.world, self.phys, want_frames=True)
        if record:
            self.journal.append({"t": "open", "chamber": idx + 1, "gate": gate})
        self.last_frames[("chamber", idx + 1, len(ch.opened))] = (ch.world.w, ch.world.h, ch.world.gate, None, res.frames[:MAX_FRAMES_KEPT], start)
        v = self.view(idx)
        v.update({"opened": gate, "ticks": res.ticks, "came_to_rest": res.settled,
                  "reactions": self._reactions(res.reactions, {}, {})})
        return v

    def close(self, idx: int, record: bool = True) -> dict:
        ch = self._ch(idx)
        if not ch.active():
            raise ActionError("chamber is not active")
        ch.closed = True
        if record:
            self.journal.append({"t": "close", "chamber": idx + 1})
        return self.view(idx, grid=False)

    def frames(self, key: tuple, every: int = 1) -> list:
        if key not in self.last_frames:
            raise ActionError("no such recording")
        w, h, gate, _, frames, start = self.last_frames[key]
        tmp = World(w, h, bytearray(w * h), gate, bytearray(w * h))
        every = max(1, int(every))
        out = [start] + [self.rows(tmp, f) for f in frames[every - 1::every]]
        if frames and (len(frames) % every):
            out.append(self.rows(tmp, frames[-1]))
        return out

    # ---- scoring ---------------------------------------------------------
    def score(self) -> dict:
        per = []
        total = 0.0
        for ch in self.chambers:
            met = ch.met()
            s = 1.0 if all(met) else PARTIAL * sum(met) / len(met)
            per.append({"chamber": ch.name, "tier": ch.tier, "objectives_met": sum(met), "objectives": len(met),
                        "complete": all(met), "score": round(s, 4), "weight": round(WEIGHTS[ch.tier], 4),
                        "gates_opened": list(ch.opened)})
            total += WEIGHTS[ch.tier] * s
        return {"reward": round(min(1.0, max(0.0, total)), 4), "chambers": per,
                "lab_runs_used": len(self.lab_runs)}


def replay(seed: int, journal: list, salt: str = DEFAULT_SALT, lab_budget: int = 0) -> Episode:
    """Rebuild an episode by re-executing a journal. Raises ActionError on any
    entry the rules would not have allowed."""
    ep = Episode(seed, salt, lab_budget=lab_budget)
    if not isinstance(journal, list):
        raise ActionError("journal must be a list")
    for e in journal:
        if not isinstance(e, dict):
            raise ActionError("journal entry must be an object")
        t = e.get("t")
        if t == "lab":
            ep.lab(e.get("rows"), record=False)
        elif t == "open":
            ep.open(e.get("chamber", 0) - 1 if isinstance(e.get("chamber"), int) else -1, e.get("gate"), record=False)
        elif t == "close":
            ep.close(e.get("chamber", 0) - 1 if isinstance(e.get("chamber"), int) else -1, record=False)
        else:
            raise ActionError(f"unknown journal entry type {t!r}")
        ep.journal.append(e)
    return ep


def load_journal(path: str) -> list:
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                out.append(json.loads(line))
    return out
