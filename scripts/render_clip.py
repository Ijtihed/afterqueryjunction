#!/usr/bin/env python3
"""Render a recorded run against the reference as an animation, straight from
simulator frames and oracle counts (no browser, nothing hand-edited).

Usage:
  render_clip.py --seed N --journal run.jsonl --chamber K --label "agent" --out clip.gif [--frames-dir DIR]

Needs Pillow on the host. With --frames-dir it also writes numbered PNGs, e.g. for
  ffmpeg -framerate 20 -i DIR/%05d.png -pix_fmt yuv420p clip.mp4
"""
import argparse
import os
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "engine"))
from analyze import analyze, reference_journal  # noqa: E402
from crucible.episode import DEFAULT_SALT, load_journal  # noqa: E402

W, H, FPS = 1280, 720, 20
BG, PANEL, TEXT, DIM, BLUE, RED, GREEN = "#000000", "#1c1c1e", "#f5f5f7", "#98989f", "#0a84ff", "#ff453a", "#30d158"


def font(size, bold=False):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
              "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


F_T, F_B, F_S, F_N, F_G = font(24, True), font(19), font(15), font(40, True), font(13, True)


def draw_grid(d, rows, legend, x0, y0, s, zones, sel=None):
    for y, row in enumerate(rows):
        for x, c in enumerate(row):
            box = [x0 + x * s, y0 + y * s, x0 + (x + 1) * s - 1, y0 + (y + 1) * s - 1]
            if c == ".":
                continue
            if c == "#":
                d.rectangle(box, fill="#2c2c2e")
            elif c.isdigit():
                d.rectangle(box, fill=BLUE if sel == int(c) else "#0b3a6e", outline="#64b4ff")
                d.text((box[0] + s // 2, box[1] + s // 2), c, font=F_G, fill="#ffffff", anchor="mm")
            else:
                d.rounded_rectangle(box, radius=max(1, s // 5), fill=legend.get(c, {}).get("color", "#999999"))
    for z in zones:
        col = GREEN if z["met"] else legend.get(z["substance"], {}).get("color", "#8fd3ff")
        d.rectangle([x0 + z["x"][0] * s, y0 + z["y"][0] * s, x0 + (z["x"][1] + 1) * s - 1, y0 + (z["y"][1] + 1) * s - 1], outline=col, width=2)
        d.text((x0 + z["x"][0] * s + 4, y0 + z["y"][0] * s + 2), f"{z['zone']} {z['current_cells']}/{z['min_cells']}", font=F_S, fill=col)


def panel(img, run, ci, pos, frame, sel, x0, title):
    d = ImageDraw.Draw(img)
    ch = run["chambers"][ci]
    pw = W // 2 - 30
    d.rounded_rectangle([x0, 70, x0 + pw, H - 20], radius=22, fill=PANEL)
    d.text((x0 + 22, 84), title, font=F_T, fill=TEXT)
    d.text((x0 + pw - 22, 88), f"reward {run['score']['reward']:.2f}", font=F_B, fill=DIM, anchor="ra")
    rows = frame if frame is not None else (ch["initial"] if pos == 0 else ch["steps"][pos - 1]["frames"][-1])
    zones = ch["steps"][pos - 1]["objectives"] if pos > 0 else [dict(o, current_cells=0, met=False) for o in ch["objectives"]]
    s = min((pw - 44) // len(rows[0]), 400 // len(rows))
    gx = x0 + (pw - s * len(rows[0])) // 2
    draw_grid(d, rows, run["legend"], gx, 130, s, zones, sel)
    wins = ch["winning_orders_at_start"] if pos == 0 else ch["steps"][pos - 1]["wins_after"]
    d.text((x0 + 22, 548), "winning gate orders still possible", font=F_S, fill=DIM)
    d.text((x0 + 22, 566), str(wins), font=F_N, fill=RED if wins == 0 else TEXT)
    opened = "  ".join(f"{k + 1}:gate {st['gate']}" for k, st in enumerate(ch["steps"][:pos])) or "no gate opened yet"
    d.text((x0 + 130, 578), opened, font=F_S, fill=DIM)
    if pos > 0:
        st = ch["steps"][pos - 1]
        if st["fatal"]:
            msg, col = f"Gate {st['gate']} eliminated all {st['wins_before']} remaining winning orders. Safe: gate {', '.join(map(str, st['safe_alternatives']))}.", RED
        elif st["complete"]:
            msg, col = "Chamber complete.", GREEN
        elif st["wins_after"] == 0:
            msg, col = "Already unsolvable.", RED
        else:
            msg, col = f"Gate {st['gate']}: {st['wins_before']} to {st['wins_after']} winning orders.", TEXT
        d.rounded_rectangle([x0 + 16, 628, x0 + pw - 16, 680], radius=14, outline=col, width=2)
        d.text((x0 + 30, 643), msg, font=F_S, fill=col)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--journal", required=True)
    ap.add_argument("--chamber", type=int, required=True)
    ap.add_argument("--label", default="agent")
    ap.add_argument("--out", required=True)
    ap.add_argument("--frames-dir")
    ap.add_argument("--max-step-frames", type=int, default=45)
    a = ap.parse_args()
    runs = [analyze(a.seed, load_journal(a.journal), a.label), analyze(a.seed, reference_journal(a.seed, DEFAULT_SALT), "reference")]
    ci = a.chamber - 1
    name = runs[0]["chambers"][ci]["name"]
    frames = []

    def shot(pos, fr=(None, None), sel=(None, None), hold=1):
        img = Image.new("RGB", (W, H), BG)
        ImageDraw.Draw(img).text((30, 22), f"Crucible   chamber {a.chamber} ({name}), facility {a.seed}", font=F_T, fill=TEXT)
        for k, run in enumerate(runs):
            panel(img, run, ci, pos[k], fr[k], sel[k], 20 + k * (W // 2 - 10), run["label"])
        frames.extend([img] * hold)

    pos = [0, 0]
    shot(pos, hold=FPS * 2)
    while True:
        steps = [r["chambers"][ci]["steps"] for r in runs]
        act = [pos[k] < len(steps[k]) for k in range(2)]
        if not any(act):
            break
        sel = tuple(steps[k][pos[k]]["gate"] if act[k] else None for k in range(2))
        shot(pos, sel=sel, hold=FPS)
        seqs = []
        for k in range(2):
            fr = steps[k][pos[k]]["frames"] if act[k] else []
            stride = max(1, len(fr) // a.max_step_frames)
            seqs.append(fr[::stride] + fr[-1:] if fr else [])
        for i in range(max(len(q) for q in seqs)):
            shot(pos, fr=tuple(q[min(i, len(q) - 1)] if q else None for q in seqs))
        pos = [pos[k] + act[k] for k in range(2)]
        fatal = any(act[k] and steps[k][pos[k] - 1]["fatal"] for k in range(2))
        shot(pos, hold=FPS * (4 if fatal else 2))
    shot(pos, hold=FPS * 3)

    if a.frames_dir:
        os.makedirs(a.frames_dir, exist_ok=True)
        for i, f in enumerate(frames):
            f.save(os.path.join(a.frames_dir, f"{i:05d}.png"))
    small = [f.resize((960, 540), Image.LANCZOS).quantize(colors=96, method=Image.Quantize.MEDIANCUT) for f in frames[::2]]
    small[0].save(a.out, save_all=True, append_images=small[1:], duration=2000 // FPS, loop=0, optimize=False)
    print(f"{a.out}: {len(small)} frames, {os.path.getsize(a.out) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
