# Pilot journals

Blind runs by Claude Fable 5.2 as a sub-agent with a shell, the `crucible` CLI and no source access. These are not Harbor runs. Each journal only replays against the engine version it was recorded on.

| Journal | Layout | Reward | Replays at |
| --- | --- | --- | --- |
| `v1-pilot1-seed11`, `v1-pilot2-seed12` | first version, 3 chambers, 12 lab runs | 1.00, 1.00 | not preserved as a commit |
| `pilot3-seed21`, `pilot4-seed22` | version 2 with a bulk threshold that could not be observed in the lab | 0.55, 0.55 | discarded as evidence; not preserved |
| `pilot5-seed31`, `pilot6-seed32` | version 2, 3 chambers, 7 lab runs | 0.55, 0.60 | tag `pilots-3-chamber` |
| `v3-pilot7-seed41` | 6 chambers, 9 lab runs | 0.775 | tag `pilots-v3` |
| `v3-rules-pilot8-seed2` | 6 chambers, 9 lab runs, rules given | 0.80 | tag `v4-six-chambers` |
| `v4-pilot9-seed43` | 6 chambers, 9 lab runs | 1.00 | tag `v4-six-chambers` |
| `v4-pilot10-seed44-lab6` | 6 chambers, 6 lab runs | 1.00 | tag `v4-six-chambers` |

Pilots 5 to 7 lost on two simulator details that were later removed as arbitrary, so their scores are not evidence about the current task.
