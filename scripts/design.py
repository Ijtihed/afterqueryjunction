"""Design aid: print every gate order of each template with its outcome."""
import itertools, sys
sys.path.insert(0, "engine")
from crucible.chambers import TEMPLATES, ROLE_ID, build, family_physics
from crucible.oracle import Oracle, apply_open
from crucible import templates  # noqa: F401  (registers templates)

INV = {v: k for k, v in ROLE_ID.items()}

def show(ch):
    w = ch.world
    for y in range(w.h):
        print("   ", "".join("#" if c == 1 else str(w.gate[y*w.w+x]) if c == 2 else "." if c == 0 else INV[c]
                              for x, c in enumerate(w.cell[y*w.w:(y+1)*w.w])))

phys = family_physics()
only = sys.argv[1] if len(sys.argv) > 1 else None
for t in TEMPLATES:
    if only and t.name != only: continue
    for flip in (False, True):
        ch = build(t, flip)
        o = Oracle(phys)
        n = o.wins(ch)
        print(f"== {t.name} flip={flip} gates={ch.gates} initial_met={ch.met()} winning_orders={n}")
        if flip: continue
        show(ch)
        for k in range(1, len(ch.gates) + 1):
            for seq in itertools.permutations(ch.gates, k):
                c = ch.copy(); done = False
                for i, g in enumerate(seq):
                    r = apply_open(c, phys, g)
                    if c.complete(): done = i == len(seq) - 1; break
                    if not r.settled: print("UNSETTLED", seq)
                else:
                    done = False
                if done: print("   WIN", seq)
        if "-v" in sys.argv:
            for seq in [a.split(",") for a in sys.argv if a[0].isdigit()]:
                c = ch.copy()
                for g in seq:
                    apply_open(c, phys, int(g)); print("after", g, c.met(), [c.world.count(m, c.zones[z]) for z, m, _ in c.objectives]); show(c)
