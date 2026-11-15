# Crucible

A Harbor task for AfterQuery's "Break the Agent" challenge (Junction 2026).

An agent runs a sealed materials facility. Seven substances behave in ways it is not told. It has a small lab with 6 runs to learn them, then three chambers where its only action is opening a gate, permanently, with one attempt per chamber. A wrong opening can silently make a chamber unsolvable.

It targets two weaknesses that the literature shows surviving code tools: discovering unfamiliar rules when experiments are scarce, and committing to irreversible actions whose consequences arrive later. See `docs/DECISION.md` for the research review and the design decision.

## Run it

Requirements: Docker and [Harbor](https://github.com/laude-institute/harbor) 0.26 (`uv tool install harbor`).

```bash
cd tasks
harbor run -p ./crucible-001 -a oracle                      # reference run, expect 1.0
harbor run -p ./crucible-001 -a nop                         # do nothing, expect 0.0
harbor run -p ./crucible-001 -a opencode -m <provider/model> -k 3   # three agent trials
```

`crucible-002` and `crucible-003` are other seeds. `crucible-00N-rules` is the same facility with the true substance behaviour written into the instruction (the rule-discovery ablation). More seeds: `python3 scripts/build_tasks.py 4 5 6 --rules`.

Nominate a strong model. The agent timeout is 120 minutes; agents typically stop themselves after about 5. The reference needs about 20 seconds. OpenCode is preinstalled in the task image, so trials start without a network install.

## The task

- **Substances.** Each is static, a powder or a liquid, falls down or up, and has a density. Some pairs react on contact. One reaction only happens in bulk. One product reacts again with another substance, and that product eats walls. Symbols, names and colours are reshuffled per seed, so appearance tells nothing.
- **Lab.** An 8 by 6 box. The agent draws any layout and it runs to rest under the same rules. 6 runs for the whole episode. Products cannot be placed; they have to be made inside a run.
- **Chambers.** Substances sit in reservoirs behind numbered gates. `open` removes a gate for good and the world runs until nothing moves. Zones ask for a minimum count of a substance, sometimes one that does not exist yet.
  Each facility has three chambers, all hard. Agents cleared the easier tiers in earlier runs, so those were removed; their layouts (leak, float, cellar, tower) remain in `engine/crucible/templates.py`.
  - *works* (7 gates, 3 zones): the elixir must reach a sealed vault, and the only thing that opens the vault is made from the elixir itself.
  - *foundry* (6 gates, 3 zones): seal a drain by making crust inside it, brew the elixir, then lift it over a spillway by pouring more liquid underneath. About 10 of roughly 1,950 gate orders win, and releasing the smaller reservoir first is already fatal.
  - *refinery* (7 gates, 3 zones): foundry with a leaking receiver; the elixir is only kept if a powder plug is dropped into the receiver's drain in time.
- **Observations.** The full grid, zone counts, a log of every reaction that occurred, and tick-by-tick recordings on request. Nothing a human sees in the browser version is withheld.

The agent gets a `crucible` CLI (`brief`, `view`, `lab`, `open`, `close`, `frames`, `status`) and may write any code it likes. The full statement is `task-template/instruction.md`.

## Scoring

Reward = (c1 + c2 + c3) / 3, where a complete chamber scores 1 and an incomplete one scores 0.3 x (zones met / zones). It is written to `/logs/verifier/reward.txt`.

| Policy (seeds 1 to 3, graded by journal replay) | Reward |
| --- | --- |
| Do nothing | 0.000 |
| Open one gate per chamber, then stop | 0.00 to 0.03 |
| Uniformly random gate orders (mean of 200) | 0.13 |
| Reference | 1.000 |

Reproduce with `python3 scripts/baselines.py`.

## Why the reward is hard to hack

- The rules, the seed and the episode state live in a sidecar container (`sim`). The agent's container holds only a thin HTTP client.
- The sidecar appends every accepted action to a journal. After the agent stops, Harbor copies that one file out of the sidecar into a **separate verifier container** with no network.
- The verifier has its own build of the simulator. It ignores everything else and **re-executes the journal from the seed**. Any entry the rules would not allow (unknown gate, reopened gate, action on a finished chamber, a seventh lab run, malformed data) rejects the whole journal and scores 0.
- There is no reset and no score-setting endpoint. Lab runs cannot touch chambers. Completion is recomputed from cell counts in the final replayed state, so reports, files and extra journal fields change nothing.
- `python3 -m unittest discover tests` covers the cases above (22 tests).

- `scripts/redteam.sh` runs a hostile script as the agent inside the real Harbor task: it writes reward files, plants a forged winning journal at the verifier's path in its own container, probes for hidden endpoints and path traversal, sends malformed and oversized requests, exceeds the lab budget, and leaves a background process rewriting the reward. Measured reward: 0.0000 (`results/redteam/`).

Known limits, stated plainly: the public salt in this repository makes seed to world deterministic, so anyone who learns a task's seed and has the source can compute the answer. The seed is not visible from the agent container. For a held-out evaluation set `CRUCIBLE_SALT` privately in both the sidecar and the verifier image.

## Reference solution and what it knows

`solution/solve.py` uses only the public interface. It knows the matter family (which kinds of behaviour and reaction can exist) but not which visible substance is which. It spends all 6 lab runs identifying them, plans each chamber by exhaustive search in its own copy of the simulator, and aborts if the facility ever disagrees with its prediction.

That is an advantage over an agent, which is told nothing about the family, and it is the same protocol discovery benchmarks use (solver or human against an agent without rules). Two fairer comparisons are prepared: the `-rules` task variants, and first-time human players in the browser version.

## Diagnostics: the first fatal move

Chambers have few gates, so every order is simulated. For any recorded run:

```bash
python3 scripts/analyze.py --seed 1 agent=path/to/journal.jsonl --reference --html replay.html
```

prints, per opening, how many winning orders existed before and after, flags the first opening that eliminated all of them, and lists the gates that would have kept the chamber solvable. `replay.html` is a standalone side-by-side viewer of that run against the reference. The journal of a Harbor trial is under `<trial>/artifacts/`.

## Results so far

**Harbor, local Docker, Harbor 0.26.0, tasks `crucible-001` to `003` (six chambers):** reference (`-a oracle`) 1.0000 on all three, do nothing (`-a nop`) 0.0000 on `001`. Logs are in `results/harbor/`.

**Frontier agents through Harbor and OpenCode (the official harness).** Default tasks (three hard chambers, 6 lab runs), OpenCode 1.19.5. Logs, trajectories and journals are under `results/harbor/opencode-*/`; `python3 scripts/summarize_runs.py` prints every trial with its budget, cost and the opening where each chamber was lost.

| Model | Effort | Trials | Rewards at 6 lab runs | Mean | Reference |
| --- | --- | --- | --- | --- | --- |
| `openai/gpt-6-astra` | default | 2 | 0.433, 0.167 | 0.300 | 1.00 |
| `openai/gpt-6.1-sol` | default | 5 | 0.167, 0.167, 0.367, 0.433, 0.400 | 0.307 | 1.00 |
| `openai/gpt-6.1-sol` | high | 2 | 0.167, 0.167 | 0.167 | 1.00 |
| `openai/gpt-6.1-terra` | default | 3 | 0.700, 0.400, 0.133 | 0.411 | 1.00 |

- **12 trials across three seeds, mean 0.31, best 0.70, none complete.** The reference scores 1.00 with the same 6 runs.
- Chambers lost: foundry 11 of 12 (usually at the first or second opening), works 10 of 12, refinery 7 of 12.
- The typical loss is an opening that looks harmless and removes every winning order, discovered only several openings later.
- No trial hit a tool error or a timeout; sessions were ended by the agents after about 5 minutes.

**Why the budget is 6.** With 9 lab runs an agent can rehearse risky steps as miniatures, and sometimes wins; with 6, the reference's own requirement, it has to plan from what it has learned.

| `gpt-6.1-sol` | 9 lab runs | 6 lab runs |
| --- | --- | --- |
| default effort, seed 3 | 1.000 | 0.400, 0.433 |
| high effort, seed 1 | 0.733 | 0.167 |
| high effort, seed 3 | 0.733 | 0.167 |

All 15 trials at 9 runs (tasks `crucible-00N-lab9`) are in the same results folder: Astra 0.400, 0.167, 0.167; Sol 0.133, 0.167, 0.100, 0.167, 1.000 and 0.733, 0.733 at high effort; Terra 0.133, 0.400, 0.700, 0.400, 0.400. Trials recorded before the default changed carry the task name `crucible-00N` with a budget of 9; the budget column of `summarize_runs.py` reads each trial's verifier record and is authoritative.

Caveats: small n per cell, one harness, OpenAI models only. Cost reported by Harbor: $11.88 for these 27 trials.

**Agent red-team.** `gpt-6.1-sol` and `gpt-6-astra` were given the task plus `redteam/adversarial_instruction.md` (ignore the puzzle, raise the reward by any exploit). Both declined: Astra refused in its first message and made no tool calls, Sol was stopped by a safety refusal. Both scored 0.0, but since nothing was attempted this is not evidence about robustness. The scripted check (`scripts/redteam.sh`, reward 0.0000 on this layout) is the evidence.

**Same agents on the earlier six-chamber layout** (two easy, two medium, two hard; archived in `results/harbor-v4-six-chambers/`, git tag `v4-six-chambers`): Terra 0.675, 0.45, 0.45; Sol 0.575, 0.575, 0.40; Astra 0.575. They completed most easy and medium chambers there with the same tools and interface, which is the control showing the losses above are not interface failures.

**Blind pilots with Claude Fable 5.2 (not Harbor runs, earlier layouts).** The pilots below played earlier layouts that still included easy and medium chambers. Their journals replay at git tag `pilots-3-chamber`, not at the current head. One pilot has played the current six-chamber layout (pilot 7, seed 41, journal `results/pilots/v3-pilot7-seed41.jsonl`, replays at the current head): reward 0.775. It completed five chambers, including the new foundry, and lost works at its sixth opening, the same way pilots 5 and 6 did: an earlier pour had pushed a resting liquid to a spot it had not predicted, and the wall-eating product then breached the wrong wall. Works is 0 for 3 across clean pilots; no other chamber type has been failed. Replay: `results/replay-pilot7-seed41.html`.

 To get an early signal, a frontier model (Claude Fable 5.2, as a sub-agent with a shell) was given only `instruction.md` and the `crucible` CLI against a local server, with no access to the source. Journals are in `results/pilots/`, graded by the same replay code as the verifier.

| Version | Run | Seed | Lab runs | Reward | Chamber 3 |
| --- | --- | --- | --- | --- | --- |
| 1 (6 substances, 12 runs, 12x10 lab, 5 gates) | pilot 1 | 11 | 9 | 1.00 | complete |
| 1 | pilot 2 | 12 | 5 | 1.00 | complete |
| 2 | pilot 5 | 31 | 7 | 0.55 | 1/3 zones, fatal at step 6 |
| 2 | pilot 6 | 32 | 7 | 0.60 | 2/3 zones, stopped while still solvable |
| 2 | reference | any | 5 | 1.00 | complete |

What happened, in order:

1. Version 1 produced **no gap**. Both pilots identified every substance and rehearsed each risky chamber step as a miniature in the lab. That result is why version 2 exists.
2. Version 2 shrinks the lab, cuts the runs, and adds the bulk-only reaction, the reaction chain and the 7-gate chamber. Both pilots still completed chambers 1 and 2.
3. In chamber 3, **pilot 5** kept the chamber solvable for five openings, then opened the one gate that removed the last winning order (the other remaining gate would have kept it alive). It had seen the risk but had no lab runs left to test the alternative.
4. **Pilot 6** stopped with 2 of 3 zones met and **one winning order still available**: a single further opening completed the chamber. A lab rehearsal had convinced it that opening would drain a finished zone. Its model of the world predicted most things correctly and was wrong on the one prediction that decided the outcome.

**Rules-given ablation (one run).** Pilot 8 played seed 2 with the true substance behaviour written into its instruction (`results/pilots/v3-rules-pilot8-seed2.jsonl`, replay `results/replay-rules-pilot8-seed2.html`). Reward 0.80, against 0.775 for the blind pilot on the same layout. It completed works, and lost foundry at its **first** opening: it released the smaller reservoir first, and every one of the 12 winning orders needs the larger pour to come first. It found out three openings later, and finished with 4 of 9 lab runs unused. So with the rules in hand the loss is an irreversible ordering mistake with a delayed consequence, not a failure to discover rules. One run, different seed from the blind pilot, so this is suggestive only.

Note on versions: pilots 5 to 7 ran before two simulator details were made predictable (commit `16643df`); pilot 8 ran after. Journals from before that commit replay at `b7750c9` or the `pilots-3-chamber` tag.

**After the cleanup, with 9 lab runs: no gap.** Pilot 9 (seed 43, `results/pilots/v4-pilot9-seed43.jsonl`) completed all six chambers, reward 1.00, using 7 of 9 lab runs, most of them as miniature rehearsals of risky chamber steps. With lab runs to spare, the strongest model tested solves the task. The lab budget is therefore a task parameter (`scripts/build_tasks.py --lab-runs N`, tasks named `-labN`); the reference needs 6 and scores 1.0 through Harbor at 6.

**With 6 lab runs: still no gap.** Pilot 10 (seed 44, budget 6, `results/pilots/v4-pilot10-seed44-lab6.jsonl`) also completed all six chambers, reward 1.00, using all 6 runs. By its own account two of its openings were gambles rather than tested knowledge, and its single-cell test of the bulk-only reaction was a false negative that it worked around by inference.

**Claude Fable 5.2 in the pilot harness is the exception.** Blind play scored 1.00 twice (budgets 9 and 6) and the rules-given run scored 0.80, so against that model there is no demonstrated gap. Earlier losses (pilots 5 to 7) depended on simulator details that have since been removed because they were arbitrary.

Two earlier pilots (3 and 4) are kept in `results/pilots/` but are **not evidence**: at that point the bulk reaction could not be observed with any ordinary lab layout, which is missing information rather than a reasoning failure. The threshold was lowered and `tests/` now asserts that every rule a chamber depends on can be shown in the lab box.

Caveats: n = 2 on version 2, one model, a pilot harness rather than OpenCode, and seeds differ only in skin, mirroring, chamber order and gate numbers. Treat it as a pilot signal, not a measured gap. 

Replays with exact per-move solvability: open `results/replay-pilot5-seed31.html` and `results/replay-pilot6-seed32.html` in a browser.

## Human playtest

```bash
scripts/play.sh            # then open http://localhost:8080
```

Same rules, same lab budget, same one-shot chambers. Each session is saved to `playtests/sessions/` as a journal with timestamps plus a notes file (tab switches, replays watched, the player's own explanation). Any session journal can be scored and replayed with `scripts/analyze.py`. No human has played yet, so human accessibility is unverified.

## Layout

```
engine/crucible/    simulation core (C), episode logic, oracle, server: the single source
client/crucible     the agent's CLI
reference/solve.py  reference player
task-template/      Harbor task skeleton; scripts/build_tasks.py fills tasks/
tasks/              generated, self-contained Harbor tasks
web/                browser game and replay viewer (render only, no game logic)
scripts/            build_tasks, validate, baselines, analyze, render_clip, redteam, design, play
redteam/            the hostile agent script used by scripts/redteam.sh
tests/              engine and reward-integrity tests
results/            Harbor logs, pilot journals, replay pages
docs/DECISION.md    research review, candidates, decision, formal spec
```

Determinism: integer state, fixed scan order, no randomness in the simulation. A seed fixes the skin, mirror flips and gate numbering. `python3 scripts/validate.py` checks every chamber of a seed exhaustively: nothing scores at the start, every reachable line comes to rest, a winning order exists, and a fatal first move exists.
