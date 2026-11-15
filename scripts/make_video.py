#!/usr/bin/env python3
"""Render the pitch video: an intro clip that fades out, then twelve slides.

Every frame is drawn here (animations, fades, subtitles) and piped to ffmpeg,
which is used only to decode the intro and encode the result. Chamber footage
is simulator frames from recorded Harbor trials plus exhaustive win counts.

Usage:
  make_video.py --ffmpeg /path/to/ffmpeg --intro intro.mov --out pitch.mp4
                [--voice voice.wav] [--subs subs.json] [--preview N]

--subs  JSON list of {"start": s, "end": s, "text": "..."} replacing the built-in
        subtitle draft (times are absolute, from the start of the video).
--voice audio laid under the slides, starting when the intro ends.
--preview N  write frame N seconds in as preview.png and exit.
"""
import argparse
import glob
import json
import os
import subprocess
import sys
import wave
from array import array

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "engine"))
from analyze import analyze, reference_journal  # noqa: E402
from crucible.episode import DEFAULT_SALT, load_journal  # noqa: E402

W, H, FPS = 1920, 1080, 30
BG, WHITE, GREY, DIM, RED, LINE = (10, 10, 10), (255, 255, 255), (136, 136, 136), (51, 51, 51), (255, 69, 58), (26, 26, 26)
FONTS = os.path.join(ROOT, "video", "fonts")
_fc = {}


def font(size, weight=800, mono=False):
    k = (size, weight, mono)
    if k not in _fc:
        f = ImageFont.truetype(os.path.join(FONTS, "JetBrainsMono.ttf" if mono else "Manrope.ttf"), size)
        f.set_variation_by_axes([weight])
        _fc[k] = f
    return _fc[k]


def ease(x):
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def mix(a, b, k):
    return tuple(int(a[i] + (b[i] - a[i]) * k) for i in range(3))


def rise(t, delay=0.0, dur=0.7):
    """(alpha, y offset) for an element that fades up into place."""
    k = ease((t - delay) / dur)
    return k, int((1 - k) * 26)


def text(d, xy, s, f, col, k=1.0, anchor="la", spacing=0):
    if k <= 0:
        return
    d.text(xy, s, font=f, fill=mix(BG, col, k), anchor=anchor, spacing=spacing)


def headline(d, t, lines, y=None, size=132, delay=0.0, x=154):
    f = font(size, 800)
    k, dy = rise(t, delay)
    lh = int(size * 0.92)
    y = (H - lh * len(lines)) // 2 - 60 if y is None else y
    for i, ln in enumerate(lines):
        text(d, (x, y + i * lh + dy), ln, f, WHITE, k)
    return y + lh * len(lines)


def para(d, t, s, y, delay=0.35, size=36, x=154, col=GREY):
    k, dy = rise(t, delay)
    text(d, (x, y + dy), s, font(size, 400), col, k, spacing=14)


# ---- chamber footage ------------------------------------------------------
def draw_grid(d, rows, legend, x0, y0, s, zones, sel=None, k=1.0):
    for y, row in enumerate(rows):
        for x, c in enumerate(row):
            box = [x0 + x * s, y0 + y * s, x0 + (x + 1) * s - 2, y0 + (y + 1) * s - 2]
            if c == ".":
                continue
            if c == "#":
                d.rectangle(box, fill=mix(BG, (38, 38, 40), k))
            elif c.isdigit():
                on = sel == int(c)
                d.rectangle(box, fill=mix(BG, (10, 132, 255) if on else (12, 52, 100), k), outline=mix(BG, (100, 180, 255), k))
                d.text((box[0] + s // 2, box[1] + s // 2), c, font=font(max(10, s // 2), 700, True), fill=mix(BG, WHITE, k), anchor="mm")
            else:
                col = legend.get(c, {}).get("color", "#999999")
                rgb = tuple(int(col[i:i + 2], 16) for i in (1, 3, 5))
                d.rounded_rectangle(box, radius=max(2, s // 5), fill=mix(BG, rgb, k))
    for z in zones:
        col = (48, 209, 88) if z["met"] else tuple(int(legend.get(z["substance"], {}).get("color", "#8fd3ff")[i:i + 2], 16) for i in (1, 3, 5))
        d.rectangle([x0 + z["x"][0] * s, y0 + z["y"][0] * s, x0 + (z["x"][1] + 1) * s - 2, y0 + (z["y"][1] + 1) * s - 2], outline=mix(BG, col, k), width=3)


class Footage:
    """One chamber of one recorded trial, next to the reference line."""

    def __init__(self, seed, journal, chamber, label):
        self.runs = [analyze(seed, load_journal(journal), label), analyze(seed, reference_journal(seed, DEFAULT_SALT), "Reference")]
        self.ci = chamber - 1
        self.ch = [r["chambers"][self.ci] for r in self.runs]

    def state(self, k, t, t_gate, t_play, t_end):
        """Rows, zones, selected gate and winning-order count at time t for run k (first opening only)."""
        ch = self.ch[k]
        st = ch["steps"][0]
        zero = [dict(o, current_cells=0, met=False) for o in ch["objectives"]]
        if t < t_play:
            return ch["initial"], zero, (st["gate"] if t >= t_gate else None), ch["winning_orders_at_start"], False
        fr = st["frames"]
        i = min(len(fr) - 1, int((t - t_play) / max(0.01, t_end - t_play) * len(fr)))
        done = t >= t_end
        return fr[i], (st["objectives"] if done else zero), None, (st["wins_after"] if done else ch["winning_orders_at_start"]), done

    def draw(self, d, t, x0, y0, w, h, t_gate=1.4, t_play=2.4, t_end=6.0, only=None, bare=False):
        ks = [only] if only is not None else [0, 1]
        pw = w // len(ks) - (20 if len(ks) > 1 else 0)
        for n, k in enumerate(ks):
            rows, zones, sel, wins, done = self.state(k, t, t_gate, t_play, t_end)
            px = x0 + n * (pw + 40)
            a, dy = rise(t, 0.1 + 0.15 * n)
            s = min(pw // len(rows[0]), (h - (0 if bare else 150)) // len(rows))
            gx = px + (pw - s * len(rows[0])) // 2
            if bare:  # scenery only: no label, no counter
                draw_grid(d, rows, self.runs[k]["legend"], gx, y0 + dy, s, zones, sel, a)
                continue
            text(d, (px, y0 + dy), self.runs[k]["label"], font(30, 700), WHITE, a)
            draw_grid(d, rows, self.runs[k]["legend"], gx, y0 + 56 + dy, s, zones, sel, a)
            by = y0 + 56 + s * len(rows) + 22
            text(d, (px, by), "winning gate orders still possible", font(20, 400), GREY, a)
            st = self.ch[k]["steps"][0]
            dead = done and st["fatal"]
            text(d, (px, by + 26), str(wins), font(76, 500, True), RED if dead else WHITE, a)
            if dead:
                fk = ease((t - t_end) / 0.5)
                text(d, (px + 150, by + 44), f"gate {st['gate']} eliminated all {st['wins_before']}", font(26, 600), RED, fk)


class LabFootage:
    def __init__(self, seed, journal):
        run = analyze(seed, load_journal(journal), "agent")
        self.labs, self.legend = run["lab"], run["legend"]

    def draw(self, d, t, dur, x0, y0, w, h):
        n = len(self.labs)
        per = dur / n
        i = min(n - 1, int(t / per))
        fr = self.labs[i]["frames"]
        lt = t - i * per
        f = fr[min(len(fr) - 1, int(max(0.0, lt - 0.25) / max(0.01, per - 0.6) * len(fr)))]
        s = min(w // len(f[0]), h // len(f))
        a = ease(lt / 0.25)
        draw_grid(d, f, self.legend, x0 + (w - s * len(f[0])) // 2, y0, s, [], None, a)
        text(d, (x0 + w // 2, y0 + s * len(f) + 26), f"experiment {i + 1} of {n}", font(24, 500, True), GREY, 1.0, anchor="ma")


# ---- slides ---------------------------------------------------------------
CHART = [
    ("Reference", "ours, 3 seeds", 1.000, [1, 1, 1], WHITE),
    ("GPT-6.1 Terra", "OpenAI, 3 trials", 0.411, [0.700, 0.400, 0.133], RED),
    ("GPT-6.1 Sol", "OpenAI, 5 trials", 0.307, [0.167, 0.167, 0.367, 0.433, 0.400], RED),
    ("GPT-6 Astra", "OpenAI flagship, 2 trials", 0.300, [0.433, 0.167], RED),
    ("GPT-6.1 Sol, high effort", "more reasoning, 2 trials", 0.167, [0.167, 0.167], RED),
    ("Do nothing", "baseline", 0.000, [], DIM),
    ("Cheating agent", "hostile script", 0.000, [], DIM),
]


NAMES, ANIM = {}, {}


def build_slides(F):
    def s_title(d, t, dur):
        k, dy = rise(t, 0.0, 0.9)
        text(d, (150, 360 + dy), "Crucible.", font(250, 800), WHITE, k)
        para(d, t, "Agents learn the rules. Then they destroy their own way out.", 640, 0.6, 40)

    def s_problem(d, t, dur):
        headline(d, t, ["Where frontier agents", "still break."], y=150, size=112)
        stats = [("26.7%", "best model on Visual Cipher Bench,", "with a full code sandbox"),
                 ("4 of 8", "hard levels cleared on LongPuzzleBench,", "best of ten agents"),
                 ("17%", "error-free plans on SIMMER,", "failures arrive late")]
        for i, (n, a, b) in enumerate(stats):
            k, dy = rise(t, 0.6 + 0.35 * i)
            x = 154 + i * 560
            text(d, (x, 520 + dy), n, font(132, 800), WHITE, k)
            text(d, (x, 690 + dy), a, font(26, 400), GREY, k)
            text(d, (x, 726 + dy), b, font(26, 400), GREY, k)
        para(d, t, "Irreversible moves. Delayed consequences. That is what we built for.", 850, 1.8, 32, col=(200, 200, 200))

    def s_world(d, t, dur):
        end = headline(d, t, ["Seven unknown", "substances."], size=120, y=300)
        para(d, t, "Some pour. Some pile. Some float.\nSome fall upward. Some react.\nNobody tells you which.", end + 30, 0.4, 36)
        F["works"].draw(d, min(t, 1.0), 1040, 200, 760, 620, only=1, bare=True)

    def s_lab(d, t, dur):
        end = headline(d, t, ["Six", "experiments."], size=120, y=330)
        para(d, t, "A small lab. Paint anything, press run, watch.\nThat is all you get to learn the world.", end + 30, 0.4, 36)
        F["lab"].draw(d, t, dur, 1040, 280, 760, 480)

    def s_gate(d, t, dur):
        end = headline(d, t, ["Open a gate.", "Forever."], size=120, y=330)
        para(d, t, "Three chambers. One attempt each.\nNo undo. No reset.", end + 30, 0.4, 36)
        F["works"].draw(d, t, 1040, 200, 760, 620, t_gate=0.8, t_play=1.6, t_end=dur - 0.6, only=1, bare=True)

    def s_clip1(d, t, dur):
        F["works"].draw(d, t, 154, 110, 1612, 760, **ANIM.get("clip1", dict(t_gate=1.2, t_play=2.2, t_end=5.2)))
        k, dy = rise(t, ANIM.get("clip1", {}).get("t_end", 5.2) + 0.3)
        text(d, (154, 60), "A real trial. OpenAI GPT-6.1 Sol through OpenCode.", font(26, 500), GREY, ease(t / 0.6))
        text(d, (W - 154, 40 + dy), "It keeps playing.", font(58, 800), WHITE, k, anchor="ra")

    def s_clip2(d, t, dur):
        F["foundry"].draw(d, t, 154, 110, 1612, 760, **ANIM.get("clip2", dict(t_gate=1.0, t_play=1.9, t_end=4.6)))
        k, dy = rise(t, ANIM.get("clip2", {}).get("t_end", 4.6) + 0.2)
        text(d, (154, 60), "The flagship. OpenAI GPT-6 Astra, hardest chamber, first move.", font(26, 500), GREY, ease(t / 0.6))
        text(d, (W - 154, 40 + dy), "We simulate every order.", font(58, 800), WHITE, k, anchor="ra")

    def s_chart(d, t, dur):
        headline(d, t, ["Who did well."], y=90, size=112)
        para(d, t, "Twelve agent trials through Harbor and OpenCode. Zero facilities completed.", 220, 0.3, 32)
        x0, x1, y0, rh = 560, 1560, 330, 82
        for i, (name, sub, mean, runs, col) in enumerate(CHART):
            k, dy = rise(t, 0.5 + 0.12 * i)
            y = y0 + i * rh
            text(d, (154, y - 4 + dy), name, font(30, 700), WHITE if col == WHITE else (190, 190, 190), k)
            text(d, (154, y + 34 + dy), sub, font(19, 400), (90, 90, 90), k)
            d.rectangle([x0, y, x1, y + 44], fill=mix(BG, (17, 17, 17), k), outline=mix(BG, (24, 24, 24), k))
            g = ease((t - 0.9 - 0.12 * i) / 1.3)
            if mean * g > 0:
                d.rectangle([x0, y, x0 + int((x1 - x0) * mean * g), y + 44], fill=col)
            dk = ease((t - 2.4 - 0.1 * i) / 0.4)
            for v in runs:
                cx = x0 + int((x1 - x0) * v)
                if dk > 0:
                    d.ellipse([cx - 8, y + 14, cx + 8, y + 30], fill=mix(BG, BG, 1), outline=mix(BG, WHITE, dk), width=3)
            text(d, (x1 + 150, y + 4 + dy), f"{mean * g:.2f}", font(34, 500, True), WHITE, k, anchor="ra")
        for j, lab in enumerate(["0", "0.25", "0.5", "0.75", "1.0"]):
            text(d, (x0 + (x1 - x0) * j // 4, y0 + 7 * rh - 16), lab, font(18, 400, True), (85, 85, 85), ease((t - 1.5) / 0.5), anchor="ma")

    def s_budget(d, t, dur):
        headline(d, t, ["Take away the rehearsal."], y=210, size=112)
        for i, (lab, val, note, col) in enumerate([("9 EXPERIMENTS", 1.00, "Same model. It rehearses, and wins.", WHITE),
                                                   ("6 EXPERIMENTS", 0.42, "All our reference needs. It has to plan.", RED)]):
            t_in = ANIM.get("budget", [0.5, 1.0])[i]
            k, dy = rise(t, t_in)
            x = 154 + i * 780
            text(d, (x, 430 + dy), lab, font(20, 700), (80, 80, 80), k)
            text(d, (x, 460 + dy), f"{val * ease((t - t_in - 0.2) / 1.3):.2f}", font(240, 800), col, k)
            text(d, (x, 760 + dy), note, font(28, 400), GREY, k)

    def s_fair(d, t, dur):
        headline(d, t, ["We tried to", "explain it away."], y=130, size=112)
        rows = [("The interface?", "Same tools cleared the easier chambers."),
                ("Missing information?", "Tests prove every rule is observable in the lab."),
                ("Quirky physics?", "We found two arbitrary details and removed them."),
                ("Not enough thinking?", "High reasoning effort scored 0.17.")]
        for i, (q, a) in enumerate(rows):
            k, dy = rise(t, 0.7 + 0.45 * i)
            y = 470 + i * 100
            text(d, (154, y + dy), q, font(40, 800), WHITE, k)
            text(d, (700, y + 6 + dy), a, font(32, 400), GREY, k)

    def s_cheat(d, t, dur):
        headline(d, t, ["Try to break it."], y=170, size=112)
        boxes = [("AGENT", "a thin client,\nnothing to read"), ("SIMULATOR", "rules, seed, state,\nthe only journal"), ("VERIFIER", "no network,\nreplays the journal")]
        for i, (a, b) in enumerate(boxes):
            k, dy = rise(t, 0.5 + 0.3 * i)
            x = 154 + i * 420
            d.rounded_rectangle([x, 400 + dy, x + 360, 600 + dy], radius=10, outline=mix(BG, (60, 60, 60), k), width=2)
            text(d, (x + 28, 424 + dy), a, font(20, 700), (120, 120, 120), k)
            text(d, (x + 28, 470 + dy), b, font(28, 400), (210, 210, 210), k, spacing=10)
            if i < 2:
                text(d, (x + 390, 480 + dy), "→", font(40, 700), (90, 90, 90), k, anchor="ma")
        k, dy = rise(t, 1.7)
        text(d, (1420, 390 + dy), f"{0:.2f}", font(170, 800), WHITE, k)
        text(d, (1420, 590 + dy), "hostile agent,", font(24, 400), GREY, k)
        text(d, (1420, 624 + dy), "inside the real task", font(24, 400), GREY, k)
        para(d, t, "Forged reward files. A forged journal. Hidden endpoints. A process rewriting the score.", 720, 2.0, 30)

    def s_end(d, t, dur):
        k, dy = rise(t, 0.0, 0.9)
        text(d, (150, 250 + dy), "Crucible.", font(210, 800), WHITE, k)
        for i, (n, lab) in enumerate([("34", "agent trials, every log in the repo"), ("1.00", "reference, every seed"), ("1", "command to rerun it all")]):
            a, dy2 = rise(t, 0.6 + 0.3 * i)
            x = 154 + i * 560
            text(d, (x, 560 + dy2), n, font(120, 800), WHITE, a)
            text(d, (x, 710 + dy2), lab, font(26, 400), GREY, a)
        text(d, (154, 830), "$ scripts/verify.sh", font(30, 500, True), (200, 200, 200), ease((t - 1.8) / 0.6))

    def s_chambers(d, t, dur):
        headline(d, t, ["Where they break."], y=170, size=112)
        para(d, t, "Chambers lost, out of twelve trials.", 310, 0.3, 32)
        for i, (n, name, note) in enumerate([("11", "Foundry", "most steps that must happen in order"), ("10", "Works", "a product that opens its own vault"), ("7", "Refinery", "a plug that has to land in time")]):
            k, dy = rise(t, 0.7 + 0.5 * i)
            x = 154 + i * 560
            text(d, (x, 430 + dy), n, font(220, 800), RED, k)
            text(d, (x + (250 if len(n) == 2 else 140), 560 + dy), "/ 12", font(60, 800), (90, 90, 90), k)
            text(d, (x, 700 + dy), name, font(40, 800), WHITE, k)
            text(d, (x, 756 + dy), note, font(24, 400), GREY, k)

    def s_orders(d, t, dur):
        headline(d, t, ["Every order,", "simulated."], y=150, size=112)
        for i, (n, of, name) in enumerate([("376", "of 13,700", "Works"), ("10", "of 1,950", "Foundry"), ("55", "of 13,700", "Refinery")]):
            k, dy = rise(t, 0.4 + 0.3 * i)
            x = 154 + i * 560
            text(d, (x, 480 + dy), n, font(150, 800), WHITE, k)
            text(d, (x, 660 + dy), of + " gate orders win", font(26, 400), GREY, k)
            text(d, (x, 700 + dy), name, font(26, 700), (200, 200, 200), k)

    NAMES.update(title=s_title, problem=s_problem, world=s_world, lab=s_lab, gate=s_gate, clip1=s_clip1, clip2=s_clip2, chart=s_chart,
                 budget=s_budget, fair=s_fair, cheat=s_cheat, chambers=s_chambers, orders=s_orders, end=s_end)
    # (draw function, seconds, subtitle draft)
    return [
        (s_title, 4.5, "This is the box. We call it Crucible."),
        (s_problem, 8.0, "Frontier agents write code and pass exams. But give them a move they cannot undo, and they break."),
        (s_world, 6.0, "So we built a sealed facility. Seven substances. Nobody tells you how they behave."),
        (s_lab, 6.5, "You get six experiments in a small lab to figure them out."),
        (s_gate, 6.5, "Then three chambers. Your only move is to open a gate. Forever."),
        (s_clip1, 9.0, "Here is OpenAI's GPT-6.1 Sol. One gate, and three hundred seventy six ways to win become zero. It keeps playing."),
        (s_clip2, 8.5, "The flagship, GPT-6 Astra, does the same in our hardest chamber. First move. We know, because we simulate every possible order."),
        (s_chart, 9.0, "Who did well. Our reference: perfect. Twelve agent trials through Harbor and OpenCode: zero facilities completed."),
        (s_budget, 7.5, "Give the same model three more experiments and it wins. At six, all our reference needs, it has to plan. It can't."),
        (s_fair, 8.0, "We tried to explain it away. Same tools, easier chambers: solved. Every rule is observable. More reasoning made it worse."),
        (s_cheat, 7.5, "And you cannot cheat it. A hostile agent inside the real task scored zero."),
        (s_end, 6.0, "Thirty four trials, every log in the repo, one command to rerun. Crucible."),
    ]


# ---- subtitles ------------------------------------------------------------
def chunk(text_, start, end, max_words=8):
    words = text_.split()
    parts = [" ".join(words[i:i + max_words]) for i in range(0, len(words), max_words)]
    total = sum(len(p.split()) for p in parts)
    out, t = [], start
    for p in parts:
        dur = (end - start) * len(p.split()) / total
        out.append({"start": t, "end": t + dur, "text": p})
        t += dur
    return out


def draw_sub(img, subs, t):
    for s in subs:
        if s["start"] <= t < s["end"]:
            d = ImageDraw.Draw(img, "RGBA")
            f = font(42, 600)
            lines = [s["text"]]
            if d.textlength(s["text"], font=f) > 1250:  # balance long lines over two rows
                words = s["text"].split()
                cut = min(range(1, len(words)), key=lambda i: abs(len(" ".join(words[:i])) - len(" ".join(words[i:]))))
                lines = [" ".join(words[:cut]), " ".join(words[cut:])]
            k = min(1.0, (t - s["start"]) / 0.12, (s["end"] - t) / 0.12)  # quick fade in and out
            ws = [d.textlength(ln, font=f) for ln in lines]
            bw, bh = max(ws) + 60, 62 * len(lines) + 20
            x0, y0 = (W - bw) / 2, H - 70 - bh
            d.rounded_rectangle([x0, y0, x0 + bw, y0 + bh], radius=14, fill=(0, 0, 0, int(200 * k)))
            for n, (ln, w) in enumerate(zip(lines, ws)):
                d.text(((W - w) / 2, y0 + 12 + 62 * n), ln, font=f, fill=(255, 255, 255, int(255 * k)))
            return


# ---- assembly -------------------------------------------------------------
def journal_of(trial):
    return glob.glob(os.path.join(ROOT, "results", "harbor", "opencode-*", "*", trial, "artifacts", "var", "crucible", "journal.jsonl"))[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ffmpeg", required=True)
    ap.add_argument("--intro")
    ap.add_argument("--out", default=os.path.join(ROOT, "video", "pitch.mp4"))
    ap.add_argument("--voice")
    ap.add_argument("--subs")
    ap.add_argument("--intro-subs", help="JSON list of {start, end, text} subtitles for the intro clip")
    ap.add_argument("--intro-cut", type=float, help="keep only this many seconds of the intro")
    ap.add_argument("--plan", help="JSON {slides: [[name, seconds], ...], anim: {...}} replacing the default order and timing")
    ap.add_argument("--preview", type=float)
    a = ap.parse_args()
    env = dict(os.environ, LD_LIBRARY_PATH=os.path.dirname(a.ffmpeg))

    F = {"works": Footage(1, journal_of("crucible-001__pmjymvJ"), 1, "GPT-6.1 Sol"),
         "foundry": Footage(1, journal_of("crucible-001__AfmnYHV"), 3, "GPT-6 Astra"),
         "lab": LabFootage(1, journal_of("crucible-001__AfmnYHV"))}
    slides = build_slides(F)
    if a.plan:
        plan = json.load(open(a.plan))
        ANIM.update(plan.get("anim", {}))
        slides = [(NAMES[name], dur, "") for name, dur in plan["slides"]]

    # This ffmpeg build has no raw pipes, so frames travel as PNG and audio as WAV.
    import tempfile
    tmp = tempfile.mkdtemp(prefix="crucible-video-")

    def decode_audio(path):
        out = os.path.join(tmp, "a.wav")
        subprocess.run([a.ffmpeg, "-y", "-loglevel", "error", "-i", path, "-vn", "-ac", "1", "-ar", str(RATE), "-c:a", "pcm_s16le", out], env=env, check=True)
        with wave.open(out, "rb") as wf:
            return array("h", wf.readframes(wf.getnframes()))

    intro_frames, intro_pcm, RATE = [], array("h"), 44100
    iw = ih = 0
    if a.intro:
        subprocess.run([a.ffmpeg, "-loglevel", "error", "-i", a.intro, "-r", str(FPS), os.path.join(tmp, "i%05d.png")], env=env, check=True)
        intro_frames = sorted(glob.glob(os.path.join(tmp, "i*.png")))
        if a.intro_cut:
            intro_frames = intro_frames[:int(a.intro_cut * FPS)]
        iw, ih = Image.open(intro_frames[0]).size
        intro_pcm = decode_audio(a.intro)
    intro_dur = len(intro_frames) / FPS
    FADE = 0.7

    starts, t = [], intro_dur
    for _, dur, _ in slides:
        starts.append(t)
        t += dur
    total = t
    if a.subs:
        subs = json.load(open(a.subs))
    else:
        subs = json.load(open(a.intro_subs)) if a.intro_subs else []
        for (fn, dur, say), st in zip(slides, starts):
            subs += chunk(say, st + 0.3, st + dur - 0.2)

    def frame(tt):
        img = Image.new("RGB", (W, H), BG)
        if tt < intro_dur:
            src = Image.open(intro_frames[min(len(intro_frames) - 1, int(tt * FPS))]).convert("RGB")
            sc = min(W / iw, H / ih)
            src = src.resize((int(iw * sc), int(ih * sc)), Image.BILINEAR)
            img = Image.new("RGB", (W, H), (0, 0, 0))
            img.paste(src, ((W - src.width) // 2, (H - src.height) // 2))
            k = min(1.0, (intro_dur - tt) / FADE)
            if k < 1:
                img = Image.blend(Image.new("RGB", (W, H), BG), img, max(0.0, k))
        else:
            i = max(j for j, s in enumerate(starts) if s <= tt)
            fn, dur, _ = slides[i]
            lt = tt - starts[i]
            d = ImageDraw.Draw(img)
            fn(d, lt, dur)
            d.text((W - 40, 34), f"{i + 1:02d}/{len(slides):02d}", font=font(16, 800), fill=DIM, anchor="ra")
            d.rectangle([0, H - 3, int(W * (tt - intro_dur) / (total - intro_dur)), H], fill=(120, 120, 120))
            k = min(1.0, lt / 0.3, (dur - lt) / (1.0 if i == len(slides) - 1 else 0.25))
            if k < 1:
                img = Image.blend(Image.new("RGB", (W, H), BG), img, max(0.0, k))
        draw_sub(img, subs, tt)
        return img

    if a.preview is not None:
        frame(a.preview).save(os.path.join(ROOT, "video", "preview.png"))
        print(f"preview at {a.preview}s of {total:.1f}s; slide starts: {[round(s, 1) for s in starts]}")
        return

    # audio: intro sound with a fade, then the voice track (or silence)
    pcm = array("h", intro_pcm[:int(intro_dur * RATE)])
    fade_n = int(FADE * RATE)
    for i in range(min(fade_n, len(pcm))):
        pcm[len(pcm) - 1 - i] = int(pcm[len(pcm) - 1 - i] * i / fade_n)
    pcm.extend([0] * (int(intro_dur * RATE) - len(pcm)))
    if a.voice:
        v = decode_audio(a.voice)
        pcm.extend(v)
    # the last second of the picture fades to black
    pcm.extend([0] * max(0, int(total * RATE) - len(pcm)))
    pcm = pcm[:int(total * RATE)]
    wav = a.out + ".wav"
    with wave.open(wav, "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(RATE); wf.writeframes(pcm.tobytes())

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    enc = subprocess.Popen([a.ffmpeg, "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS), "-c:v", "png", "-i", "-",
                            "-i", wav, "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                            "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", "-shortest", a.out], stdin=subprocess.PIPE, env=env)
    n = int(total * FPS)
    for i in range(n):
        frame(i / FPS).save(enc.stdin, format="PNG", compress_level=1)
        if i % 300 == 0:
            print(f"  {i / FPS:5.1f}s / {total:.1f}s", flush=True)
    enc.stdin.close()
    enc.wait()
    os.remove(wav)
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)
    with open(a.out.rsplit(".", 1)[0] + ".subs.json", "w") as f:
        json.dump([{"start": round(s["start"], 2), "end": round(s["end"], 2), "text": s["text"]} for s in subs], f, indent=1)
    print(f"{a.out}: {total:.1f}s, {os.path.getsize(a.out) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
