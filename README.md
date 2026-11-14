# Crucible

A Harbor task for AfterQuery's "Break the Agent" challenge (Junction 2026).

An agent runs a sealed materials facility. Seven substances behave in ways it is not told. It has a small lab with 7 runs to learn them, then five chambers where its only action is opening a gate, permanently, with one attempt per chamber. A wrong opening can silently make a chamber unsolvable.

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

Nominate a strong model. The agent timeout is 90 minutes; the reference needs about 20 seconds.

## The task

- **Substances.** Each is static, a powder or a liquid, falls down or up, and has a density. Some pairs react on contact. One reaction only happens in bulk. One product reacts again with another substance, and that product eats walls. Symbols, names and colours are reshuffled per seed, so appearance tells nothing.
- **Lab.** An 8 by 6 box. The agent draws any layout and it runs to rest under the same rules. 7 runs for the whole episode. Products cannot be placed; they have to be made inside a run.
- **Chambers.** Substances sit in reservoirs behind numbered gates. `open` removes a gate for good and the world runs until nothing moves. Zones ask for a minimum count of a substance, sometimes one that does not exist yet.
  Each facility has five chambers: two easy, two medium, one hard, drawn from these types.
  - *leak* (easy, 3 gates): plug a hole before pouring.
  - *float* (easy, 4 gates): a light liquid reaches its zone only if a heavier one lifts it; one gate dissolves the floor seal.
  - *cellar* (medium, 4 gates): the target is made only when a powder that falls upward meets liquid waiting above it.
  - *tower* (medium, 6 gates): the elixir floats, so it needs enough liquid beneath it; three other gates each ruin it for a different reason.
  - *works* (hard, 7 gates, 3 zones): the elixir must reach a sealed vault, and the only thing that opens the vault is made from the elixir itself. 245 of roughly 13,700 gate orders win.
- **Observations.** The full grid, zone counts, a log of every reaction that occurred, and tick-by-tick recordings on request. Nothing a human sees in the browser version is withheld.

The agent gets a `crucible` CLI (`brief`, `view`, `lab`, `open`, `close`, `frames`, `status`) and may write any code it likes. The full statement is `task-template/instruction.md`.

## Scoring

Reward = 0.1 x c1 + 0.1 x c2 + 0.2 x c3 + 0.2 x c4 + 0.4 x c5, where a complete chamber scores 1 and an incomplete one scores 0.3 x (zones met / zones). It is written to `/logs/verifier/reward.txt`.

| Policy (seeds 1 to 3, graded by journal replay) | Reward |
| --- | --- |
| Do nothing | 0.000 |
| Open one gate per chamber, then stop | 0.000 |
| Uniformly random gate orders (mean of 200) | 0.19 |
| Reference | 1.000 |

Reproduce with `python3 scripts/baselines.py`.

## Why the reward is hard to hack

- The rules, the seed and the episode state live in a sidecar container (`sim`). The agent's container holds only a thin HTTP client.
- The sidecar appends every accepted action to a journal. After the agent stops, Harbor copies that one file out of the sidecar into a **separate verifier container** with no network.
- The verifier has its own build of the simulator. It ignores everything else and **re-executes the journal from the seed**. Any entry the rules would not allow (unknown gate, reopened gate, action on a finished chamber, an eighth lab run, malformed data) rejects the whole journal and scores 0.
- There is no reset and no score-setting endpoint. Lab runs cannot touch chambers. Completion is recomputed from cell counts in the final replayed state, so reports, files and extra journal fields change nothing.
- `python3 -m unittest discover tests` covers the cases above (22 tests).

Known limits, stated plainly: the public salt in this repository makes seed to world deterministic, so anyone who learns a task's seed and has the source can compute the answer. The seed is not visible from the agent container. For a held-out evaluation set `CRUCIBLE_SALT` privately in both the sidecar and the verifier image.

## Reference solution and what it knows

`solution/solve.py` uses only the public interface. It knows the matter family (which kinds of behaviour and reaction can exist) but not which visible substance is which. It spends 5 lab runs identifying them, plans each chamber by exhaustive search in its own copy of the simulator, and aborts if the facility ever disagrees with its prediction.

That is an advantage over an agent, which is told nothing about the family, and it is the same protocol discovery benchmarks use (solver or human against an agent without rules). Two fairer comparisons are prepared: the `-rules` task variants, and first-time human players in the browser version.

## Diagnostics: the first fatal move

Chambers have few gates, so every order is simulated. For any recorded run:

```bash
python3 scripts/analyze.py --seed 1 agent=path/to/journal.jsonl --reference --html replay.html
```

prints, per opening, how many winning orders existed before and after, flags the first opening that eliminated all of them, and lists the gates that would have kept the chamber solvable. `replay.html` is a standalone side-by-side viewer of that run against the reference. The journal of a Harbor trial is under `<trial>/artifacts/`.

## Results so far

**Harbor, local Docker, Harbor 0.26.0, task `crucible-001` (five chambers):** reference (`-a oracle`) 1.0000, do nothing (`-a nop`) 0.0000. Logs are in `results/harbor/`.

**No Harbor run with OpenCode exists yet.** This machine had no model API credentials, so the required agent run log is still missing. Run the third command above with a key and keep the job directory.

**Blind pilots (not Harbor runs, and on the earlier three-chamber layout).** The pilots below played leak, cellar and works with weights 0.2, 0.3, 0.5, before float and tower were added. Their journals replay at git tag `pilots-3-chamber`, not at the current head. The five-chamber layout has not been piloted.

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

Two earlier pilots (3 and 4) are kept in `results/pilots/` but are **not evidence**: at that point the bulk reaction could not be observed with any ordinary lab layout, which is missing information rather than a reasoning failure. The threshold was lowered and `tests/` now asserts that every rule a chamber depends on can be shown in the lab box.

Caveats: n = 2 on version 2, one model, a pilot harness rather than OpenCode, and seeds differ only in skin, mirroring, chamber order and gate numbers. Treat it as a pilot signal, not a measured gap. The rules-given ablation has not been run.

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
scripts/            build_tasks, validate, baselines, analyze, design, play
tests/              engine and reward-integrity tests
results/            Harbor logs, pilot journals, replay pages
docs/DECISION.md    research review, candidates, decision, formal spec
```

Determinism: integer state, fixed scan order, no randomness in the simulation. A seed fixes the skin, mirror flips and gate numbering. `python3 scripts/validate.py` checks every chamber of a seed exhaustively: nothing scores at the start, every reachable line comes to rest, a winning order exists, and a fatal first move exists.
