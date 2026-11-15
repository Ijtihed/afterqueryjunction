#!/usr/bin/env python3
"""Tabulate Harbor agent trials: reward, cost, and where each chamber was lost.

Usage: summarize_runs.py [results/harbor]   (prints a Markdown table)
"""
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "engine"))
from analyze import analyze  # noqa: E402
from crucible.episode import load_journal  # noqa: E402


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "results", "harbor")
    rows, total = [], 0.0
    for res in sorted(glob.glob(os.path.join(base, "opencode-*", "*", "*__*", "result.json"))):
        trial = os.path.dirname(res)
        r = json.load(open(res))
        m = re.match(r"crucible-(\d+)(?:-lab(\d+))?(-rules)?__", os.path.basename(trial))
        seed = int(m.group(1))
        ar = r.get("agent_result") or {}
        model = next(iter(ar.get("model_usage") or {"?": 0}))
        cost = ar.get("cost_usd") or 0.0
        total += cost
        jp = os.path.join(trial, "artifacts", "var", "crucible", "journal.jsonl")
        reward_file = os.path.join(trial, "verifier", "reward.txt")
        reward = open(reward_file).read().strip() if os.path.exists(reward_file) else "none"
        lost, labs, budget = "no journal", "?", "?"
        dj = os.path.join(trial, "verifier", "details.json")
        if os.path.exists(dj):
            budget = json.load(open(dj)).get("lab_budget", 9)
        effort = "high" if "-high" in trial else "default"
        if os.path.exists(jp):
            run = analyze(seed, load_journal(jp), "t")
            labs = run["score"]["lab_runs_used"]
            parts = []
            for ch, sc in zip(run["chambers"], run["score"]["chambers"]):
                if sc["complete"]:
                    continue
                k = ch["first_fatal_step"]
                parts.append(f"{ch['name']} ({'fatal at opening ' + str(k) if k else 'never made unsolvable' if ch['steps'] else 'untouched'})")
            lost = "; ".join(parts) or "none"
        rows.append((model, effort, f"seed {seed}", budget, reward, labs, f"{cost:.2f}", lost, os.path.relpath(trial, ROOT)))
    print("| Model | Effort | Facility | Lab budget | Reward | Lab runs used | Cost $ | Chambers lost | Trial |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    rows.sort(key=lambda r: (str(r[3]), r[0], r[1], r[2]))
    for row in rows:
        print("| " + " | ".join(str(x) for x in row[:8]) + f" | `{os.path.basename(row[8])}` |")
    print(f"\nTotal cost reported by Harbor: ${total:.2f} over {len(rows)} trials")


if __name__ == "__main__":
    main()
