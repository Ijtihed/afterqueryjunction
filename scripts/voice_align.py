#!/usr/bin/env python3
"""Fit the pitch video to a voice recording.

Removes the listed dead air and retakes from the recording and writes the
trimmed audio, the slide plan and subtitles that follow the speaker's own
words. Cut points, slide cues and subtitle lines were set by hand from a
word-timed transcript. The recording itself is not kept in the repository. Usage:
  voice_align.py --ffmpeg FF --voice in.mp3 --intro-subs intro.subs.json --intro 7.4 --outdir video
"""
import argparse
import json
import os
import subprocess
import wave
from array import array

RATE = 44100
# seconds of the original recording that are kept
KEEP = [(2.55, 12.40), (13.06, 38.60), (40.70, 63.90), (65.00, 84.10)]
# slide name and the original-recording time at which it starts
CUES = [("title", 2.55), ("problem", 5.30), ("world", 13.75), ("gate", 21.30), ("lab", 25.70), ("clip1", 34.10), ("clip2", 44.30),
        ("chart", 47.60), ("budget", 62.20), ("chambers", 73.30), ("orders", 80.80)]
END_HOLD = 5.0
# Subtitle lines written by hand from the word-timed transcript: (time in the
# original recording of the first word, text).
LINES = [
    (2.72, "So this is the box that we call Crucible."),
    (5.52, "We know that frontier agents"),
    (6.90, "are really good at writing code,"),
    (8.56, "they can pass bar exams, they can pass SATs,"),
    (10.38, "but if you give them something they cannot undo,"),
    (13.08, "they break."),
    (14.08, "And how does that work?"),
    (15.20, "We gave them an example of an environment:"),
    (17.70, "seven unknown substances."),
    (19.58, "Some pour, some pile, some do whatever."),
    (21.44, "Then three chambers,"),
    (22.40, "and your only move is to open a gate, forever."),
    (24.46, "That's it. You only get one choice."),
    (25.80, "You get six experiments to try with beforehand,"),
    (28.56, "so you can play around with the tries and errors."),
    (32.42, "That's all we gave the agents."),
    (34.38, "As you can see, here's GPT-6.1 Sol."),
    (37.02, "We gave it one gate, and it just..."),
    (40.86, "370 ways to win become zero."),
    (42.64, "It's just kind of instantly lost."),
    (44.48, "The flagship, GPT-6 Astra,"),
    (46.10, "does the same thing in our hardest chamber."),
    (47.90, "So what we noticed is that the AI agent"),
    (50.58, "is very confident in its answers."),
    (52.06, "And as you can see here, we have GPT-6.1 Terra,"),
    (54.38, "which is actually worse than Sol."),
    (56.10, "It's doing better because it's a bit more apprehensive."),
    (59.48, "It takes its time to think about it a bit more."),
    (62.56, "Once you give the agents more rehearsal,"),
    (66.42, "so nine experiments, it does way better."),
    (68.54, "But if you give it six, it struggles tremendously,"),
    (71.22, "and that's pretty interesting."),
    (73.76, "Even though the chambers are very similar difficulty,"),
    (77.50, "they struggle more with the ones that have more complexity."),
    (81.04, "And now we know, because we simulated every possible order."),
]


def remap(t):
    """Original recording time -> time in the trimmed audio (None if cut)."""
    acc = 0.0
    for a, b in KEEP:
        if a <= t <= b:
            return acc + (t - a)
        acc += b - a
    return None


def main():
    ap = argparse.ArgumentParser()
    for k in ("ffmpeg", "voice", "intro-subs", "outdir"):
        ap.add_argument("--" + k, required=True)
    ap.add_argument("--intro", type=float, required=True)
    a = ap.parse_args()
    env = dict(os.environ, LD_LIBRARY_PATH=os.path.dirname(a.ffmpeg))
    tmp = os.path.join(a.outdir, "_voice.wav")
    subprocess.run([a.ffmpeg, "-y", "-loglevel", "error", "-i", a.voice, "-vn", "-ac", "1", "-ar", str(RATE), "-af", "loudnorm=I=-16:TP=-1.5",
                    "-c:a", "pcm_s16le", tmp], env=env, check=True)
    with wave.open(tmp, "rb") as wf:
        src = array("h", wf.readframes(wf.getnframes()))
    os.remove(tmp)
    out, edge = array("h"), int(0.012 * RATE)
    for s0, s1 in KEEP:
        seg = src[int(s0 * RATE):int(s1 * RATE)]
        for i in range(min(edge, len(seg) // 2)):  # short fades so cuts do not click
            seg[i] = int(seg[i] * i / edge)
            seg[-1 - i] = int(seg[-1 - i] * i / edge)
        out.extend(seg)
    with wave.open(os.path.join(a.outdir, "voice_cut.wav"), "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(RATE); wf.writeframes(out.tobytes())
    voice_len = len(out) / RATE

    starts = [remap(t) for _, t in CUES]
    slides = [[name, round((starts[i + 1] if i + 1 < len(CUES) else voice_len) - starts[i], 2)] for i, (name, _) in enumerate(CUES)]
    slides.append(["end", END_HOLD])
    c1, c2, bud = starts[5], starts[6], starts[8]
    anim = {"clip1": {"t_gate": round(remap(37.0) - c1, 2), "t_play": round(remap(37.9) - c1, 2), "t_end": round(remap(42.3) - c1, 2)},
            "clip2": {"t_gate": 0.3, "t_play": 0.8, "t_end": 2.4},
            "budget": [round(remap(66.4) - bud, 2), round(remap(68.6) - bud, 2)]}
    json.dump({"slides": slides, "anim": anim}, open(os.path.join(a.outdir, "plan.json"), "w"), indent=1)

    subs = json.load(open(a.intro_subs))
    for n, (t, txt) in enumerate(LINES):
        st = remap(t)
        en = remap(LINES[n + 1][0]) if n + 1 < len(LINES) else voice_len
        subs.append({"start": round(a.intro + st, 2), "end": round(a.intro + min(en, st + 6.0) - 0.04, 2), "text": txt})
    json.dump(subs, open(os.path.join(a.outdir, "final.subs.json"), "w"), indent=1)
    print(f"voice {voice_len:.1f}s after cuts; total video {a.intro + voice_len + END_HOLD:.1f}s")
    for name, dur in slides:
        print(f"  {name:9s} {dur:5.2f}s")
    for s_ in subs:
        print(f"  {s_['start']:6.2f}-{s_['end']:6.2f}  {s_['text']}")


if __name__ == "__main__":
    main()
