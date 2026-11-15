# 60 second pitch

Open `presentation.html` in Chrome, full screen (F11). Press **Space** to start the timed run; it advances itself and ends at 1:00. Space again pauses. Arrow keys step manually. **N** shows these lines on screen for rehearsal. **R** resets.

Each slide carries little text on purpose: the screen shows, you tell.

| Time | On screen | Say |
| --- | --- | --- |
| 0:00 to 0:07 | **Crucible.** | This is Crucible. Frontier agents learn every rule of this world correctly. Then they destroy their own way out. |
| 0:07 to 0:16 | **Open a gate. Forever.** and the game | Seven unknown substances. Six experiments to figure them out. Then three chambers where your only move is to open a gate, forever. No undo. A person gets the rules in thirty seconds. |
| 0:16 to 0:30 | Real trial clip, **376 → 0** | Watch the left side. That is OpenAI's GPT-6.1 Sol. One gate. Three hundred seventy six ways to win become zero. Nothing looks wrong, so it keeps playing. We know the exact move because we simulate every possible order. |
| 0:30 to 0:43 | **Who did well.** bar chart | Who did well. Our reference scores a perfect one, every seed. OpenAI's GPT-6 family, twelve trials through Harbor and OpenCode: zero facilities completed. The flagship, Astra, averages point three. And more thinking made it worse. |
| 0:43 to 0:52 | **Take away the rehearsal.** 1.00 against 0.42 | Here is why it is fair. Give the same model three extra experiments and it wins, because it can rehearse. At six, which is all our reference needs, it has to actually plan. And it can't. |
| 0:52 to 1:00 | **Try to break it.** 0.00, 34, 1 | And you cannot cheat it. We ran a hostile agent inside the real task: zero. Thirty four trials, every log in the repo, one command to rerun all of it. That's Crucible. |

About 150 words, which is a comfortable pace for 60 seconds.

## Where the numbers come from

- **376 → 0:** trial `crucible-001__pmjymvJ`, `gpt-6.1-sol`, works chamber, first opening. Exhaustive count from `scripts/analyze.py`.
- **Chart:** the 12 trials at 6 lab runs in the README results table. Dots are individual trials, bars are means.
- **1.00 against 0.42:** `gpt-6.1-sol`, default effort, seed 3. One trial at 9 lab runs (1.000); two at 6 (0.400 and 0.433, mean 0.42).
- **0.00:** `scripts/redteam.sh` through Harbor.
- **34:** scored agent trials through Harbor and OpenCode across both layouts.

If a judge asks about Claude: it was only tested in a pilot harness on earlier layouts, where it scored 1.00, and it has not been run on the final tasks. The chart is OpenAI models only.
