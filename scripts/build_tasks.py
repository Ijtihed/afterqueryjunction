#!/usr/bin/env python3
"""Generate self-contained Harbor task directories, one per seed.

Usage: python3 scripts/build_tasks.py [seed ...] [--rules]

--rules also writes a <name>-rules variant whose instruction discloses the
facility's true substance behaviour (the rule-discovery ablation).
"""
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = os.path.join(ROOT, "engine", "crucible")
ENGINE_FILES = ["__init__.py", "core.c", "engine.py", "chambers.py", "templates.py", "oracle.py", "episode.py", "server.py"]
DEFAULT_SEEDS = [1, 2, 3, 4, 5]


def copy_engine(dst, files=ENGINE_FILES):
    os.makedirs(dst, exist_ok=True)
    for f in files:
        shutil.copy(os.path.join(ENGINE, f), os.path.join(dst, f))


def rules_card(seed: int) -> str:
    """Ground truth for one facility, used only by the rules-given ablation."""
    sys.path.insert(0, os.path.join(ROOT, "engine"))
    from crucible.chambers import REACTIONS, ROLE_ID, ROLES
    from crucible.episode import Episode
    ep = Episode(seed)
    sym = {r: ep.skin.symbol[i] for r, i in ROLE_ID.items()}
    phase = {0: "static solid, never moves", 1: "powder: moves straight or diagonally along its gravity, never sideways, so it piles",
             2: "liquid: moves along its gravity, creeps sideways toward the nearest place it can keep going, and levels out"}
    out = ["", "## Ground truth for this facility", "",
           "This section is the complete and correct description of the substances.", ""]
    for r, (ph, gr, de) in ROLES.items():
        out.append(f"- `{sym[r]}`: {phase[ph]}" + ("" if ph == 0 else f"; gravity pulls it {'down' if gr > 0 else 'up'}; density {de}")
                   + ("" if r in "wsgeako" else " (does not exist at the start; made by a reaction)"))
    out += ["", "A moving cell passes through a liquid cell when that liquid has the opposite gravity, or the same gravity and lower density. Powders never pass through powders.", "",
            "Reactions happen when cells touch side to side or top to bottom:", ""]
    for a, b, a2, b2, na, nb in REACTIONS:
        nm = lambda v: "nothing" if v is None else f"`{sym[v]}`"
        bb = "a wall cell" if b == "#" else f"`{sym[b]}`"
        need = f" Only happens when the `{sym[b]}` cell has at least {nb} neighbours of its own kind." if nb else ""
        out.append(f"- `{sym[a]}` touching {bb}: `{sym[a]}` becomes {nm(a2)}, {bb} becomes {nm(b2)}.{need}")
    return "\n".join(out) + "\n"


def build(seed: int, rules: bool = False) -> str:
    name = f"crucible-{seed:03d}" + ("-rules" if rules else "")
    out = os.path.join(ROOT, "tasks", name)
    shutil.rmtree(out, ignore_errors=True)
    shutil.copytree(os.path.join(ROOT, "task-template"), out)
    for rel in ("task.toml", "environment/docker-compose.yaml"):
        p = os.path.join(out, rel)
        s = open(p).read().replace("__SEED__", str(seed)).replace("__NAME__", name)
        open(p, "w").write(s)
    if rules:
        with open(os.path.join(out, "instruction.md"), "a") as f:
            f.write(rules_card(seed))
    shutil.copy(os.path.join(ROOT, "client", "crucible"), os.path.join(out, "environment", "crucible"))
    copy_engine(os.path.join(out, "environment", "sim", "crucible"))
    copy_engine(os.path.join(out, "tests", "crucible"), [f for f in ENGINE_FILES if f != "server.py"])
    open(os.path.join(out, "tests", "seed.txt"), "w").write(f"{seed}\n")
    copy_engine(os.path.join(out, "solution", "crucible"), [f for f in ENGINE_FILES if f != "server.py"])
    shutil.copy(os.path.join(ROOT, "reference", "solve.py"), os.path.join(out, "solution", "solve.py"))
    for rel in ("tests/test.sh", "solution/solve.sh", "environment/crucible"):
        os.chmod(os.path.join(out, rel), 0o755)
    return out


if __name__ == "__main__":
    seeds = [int(a) for a in sys.argv[1:] if a.isdigit()] or DEFAULT_SEEDS
    for s in seeds:
        print(build(s))
        if "--rules" in sys.argv:
            print(build(s, rules=True))
