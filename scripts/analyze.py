#!/usr/bin/env python3
"""Replay journals, annotate every gate opening with exact solvability counts,
and optionally write a replay bundle for the viewer.

Usage:
  analyze.py --seed N label=journal.jsonl [label=journal.jsonl ...] [--reference] [--bundle out.json] [--html out.html]
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "engine"))
from crucible.episode import DEFAULT_SALT, Episode, load_journal  # noqa: E402
from crucible.oracle import Oracle  # noqa: E402


def reference_journal(seed: int, salt: str) -> list:
    ep = Episode(seed, salt)
    j = []
    for i, ch in enumerate(ep.chambers):
        for g in Oracle(ep.phys).solve(ch):
            j.append({"t": "open", "chamber": i + 1, "gate": g})
    return j


def analyze(seed: int, journal: list, label: str, salt: str = DEFAULT_SALT, frame_stride: int = 1) -> dict:
    # Replays journals recorded under any lab budget; the verifier enforces the budget, not this tool.
    ep = Episode(seed, salt, lab_budget=max(1, sum(1 for e in journal if e.get("t") == "lab")))
    oracles = [Oracle(ep.phys) for _ in ep.chambers]
    run = {"label": label, "lab": [], "chambers": [], "events": []}
    for i, ch in enumerate(ep.chambers):
        v = ep.view(i)
        run["chambers"].append({
            "name": ch.name, "tier": ch.tier, "initial": v["grid"], "objectives": v["objectives"],
            "gates": ch.gates, "winning_orders_at_start": oracles[i].wins(ch), "steps": [],
            "first_fatal_step": None,
        })
    for e in journal:
        if e["t"] == "lab":
            r = ep.lab(e["rows"], record=False)
            fr = ep.frames(("lab", r["run"]), frame_stride)
            run["lab"].append({"run": r["run"], "frames": fr, "reactions": r["reactions"], "ticks": r["ticks"]})
            run["events"].append({"t": "lab", "run": r["run"]})
        elif e["t"] == "open":
            i = e["chamber"] - 1
            ch = ep.chambers[i]
            o = oracles[i]
            before = o.wins(ch)
            opts = o.options(ch)
            r = ep.open(i, e["gate"], record=False)
            after = o.wins(ch)
            info = run["chambers"][i]
            step = {
                "gate": e["gate"], "ticks": r["ticks"], "reactions": r["reactions"],
                "frames": ep.frames(("chamber", i + 1, len(ch.opened)), frame_stride),
                "objectives": r["objectives"],
                "wins_before": before, "wins_after": after, "fatal": before > 0 and after == 0,
                "safe_alternatives": sorted(g for g, n in opts.items() if n > 0),
                "complete": ch.complete(),
            }
            if step["fatal"] and info["first_fatal_step"] is None:
                info["first_fatal_step"] = len(info["steps"]) + 1
            info["steps"].append(step)
            run["events"].append({"t": "open", "chamber": i + 1, "step": len(info["steps"])})
        elif e["t"] == "close":
            ep.close(e["chamber"] - 1, record=False)
            run["events"].append({"t": "close", "chamber": e["chamber"]})
    run["score"] = ep.score()
    run["legend"] = {m["symbol"]: m for m in (ep.substance(k) for k in ep.skin.symbol)}
    return run


def describe(run: dict) -> str:
    out = [f"== {run['label']}: reward {run['score']['reward']}  (lab runs used: {run['score']['lab_runs_used']})"]
    for n, ch in enumerate(run["chambers"], 1):
        sc = run["score"]["chambers"][n - 1]
        out.append(f" chamber {n} ({ch['name']}): {sc['objectives_met']}/{sc['objectives']} objectives, "
                   f"{'COMPLETE' if sc['complete'] else 'not complete'}; {ch['winning_orders_at_start']} winning orders existed at the start")
        for k, s in enumerate(ch["steps"], 1):
            tag = ""
            if s["fatal"]:
                tag = (f"  <-- FATAL: eliminated all {s['wins_before']} remaining winning orders; "
                       f"gates that kept the chamber solvable: {s['safe_alternatives']}")
            elif s["wins_before"] == 0:
                tag = "  (already unsolvable)"
            out.append(f"   {k}. open gate {s['gate']}: winning orders {s['wins_before']} -> {s['wins_after']}{tag}")
        if not ch["steps"]:
            out.append("   (never touched)")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--salt", default=DEFAULT_SALT)
    ap.add_argument("--reference", action="store_true", help="add the reference line of play")
    ap.add_argument("--stride", type=int, default=1)
    ap.add_argument("--bundle")
    ap.add_argument("--html")
    ap.add_argument("runs", nargs="*", help="label=path/to/journal.jsonl")
    a = ap.parse_args()
    runs = []
    for spec in a.runs:
        label, _, path = spec.partition("=")
        runs.append(analyze(a.seed, load_journal(path), label, a.salt, a.stride))
    if a.reference:
        runs.append(analyze(a.seed, reference_journal(a.seed, a.salt), "reference", a.salt, a.stride))
    for r in runs:
        print(describe(r))
    bundle = {"seed": a.seed, "runs": runs}
    if a.bundle:
        with open(a.bundle, "w") as f:
            json.dump(bundle, f, separators=(",", ":"))
        print("bundle:", a.bundle)
    if a.html:
        page = open(os.path.join(ROOT, "web", "replay.html"), encoding="utf-8").read()
        js = open(os.path.join(ROOT, "web", "render.js"), encoding="utf-8").read()
        page = page.replace('<script src="render.js"></script>', "<script>\n" + js + "\n</script>")
        css = open(os.path.join(ROOT, "web", "style.css"), encoding="utf-8").read()
        page = page.replace("/*__STYLE__*/", css).replace('<link rel="stylesheet" href="style.css">', "")
        page = page.replace("/*__BUNDLE__*/null", json.dumps(bundle, separators=(",", ":")).replace("</", "<\\/"))
        with open(a.html, "w", encoding="utf-8") as f:
            f.write(page)
        print("html:", a.html)


if __name__ == "__main__":
    main()
