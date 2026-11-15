# Research and decision report

Written 2026-11-14 for AfterQuery "Break the Agent" (Junction 2026). Literature claims were checked against the primary pages by a research pass; items read only as abstracts are marked.

## A. Most important research findings

1. **Rule discovery fails mainly when the agent cannot cheaply query the world.** Visual Cipher Bench (2611.16861) gave agents a full code sandbox and 60 minutes; best configuration 26.7%, rule-induction category 0.6% pooled, and one hint moved a 10-task subset from 7.8% to 55.6%. No human baseline. WitnessBench (2609.32208) shows the converse: with a Python REPL plus referee access Opus 5 went from about 30 to 68 by programmatic search, and fell to 4.4 when rescored on typed moves only. Design consequence: experiments must be budgeted and no resettable simulator may be exposed.
2. **The DiG-bench headline overstates the frontier gap.** Gemini 3.1 Pro 18/70 without rules and 69/70 with them is real, but Opus 5 scored 50/70 without rules in the same no-code harness. Code-capable harnesses were only run on tiers 6 and 7 and did not beat the basic loop.
3. **Irreversible, option-destroying moves stay hard even with rules and code.** LongPuzzleBench (2609.34769): no episode cleared more than 4 of 8 Bolt Unscrew Hard levels across ten backbones, with or without code execution; a rule card raised correct rule statements from 43% to 88% but completion only from 50% to 60%. One human solved everything (n = 1). SIMMER (2606.14574, abstract): at most 17% error-free plans, many failures latent.
4. **Agents design uninformative experiments, but the evidence is on small models.** ZendoWorld (2607.08233): humans 73.3% (n = 19) against 44.5% for a gpt-5-mini agent; a symbolic oracle reaches 95.5%.
5. **Latent structure is what breaks physical discovery.** DiscoverPhysics (2605.26087): 22 worlds, best pass@5 50.0% and pass@1 26.4%; law fitting is manageable, latent structure is not. No humans.
6. **Harness matters more than most claimed gaps.** ARC-AGI-3: GPT-6 Astra 62.7% (standard, max effort) against 98.6% with the provider adapter at the same effort. Neither harness has code. Any gap we claim must survive a competent harness.

Evidence gap: no benchmark was found on LLM agents predicting liquid or powder flow on a grid. Contrary signal: "spatial manipulation and simulation" is the easiest Visual Cipher category (80%). So a known deterministic grid rule is not a source of difficulty; discovering it under a budget is.

## B. Five candidate projects

1. **Crucible (chosen).** Unknown substances in a cellular matter simulation; a small budgeted lab to learn them; one-shot chambers where the only action is opening a gate forever.
2. **Echo Vault.** Record a move sequence, a ghost replays it, coordinate with your past self around irreversible switches.
3. **Prism Lab.** Black-box crystals bend, split and recolour light beams; place them to power receivers.
4. **WorldFuzz Arena.** Given a flawed world model, find scenarios where it flips a planner's choice.
5. **Menagerie.** Creatures with hidden behaviour policies must be herded into pens; some eat each other.

## C. Human and agent gap assessment (all predictions untested unless stated)

| Concept | Why a person might solve it | Why an agent might fail |
| --- | --- | --- |
| Crucible | Pouring, piling and floating are read at a glance from the animation; the lab is play | Tests minimal amounts and generalises; skips products of products; commits before testing the case that matters |
| Echo Vault | Familiar from games | Rules are known, so a coding agent writes a search. Expected gap: none |
| Prism Lab | Optics intuition | Static constraint problem; systematic probing identifies each crystal. Expected gap: small |
| WorldFuzz Arena | Needs programming, not accessible | Writing fuzzers is a strength of coding agents |
| Menagerie | People read animal behaviour instantly | Must infer policies from coordinates; plausible gap, weaker spectacle, costly to tune |

## D. Decision matrix (internal weights)

| Concept | Gap 25 | Human 20 | Reference 15 | Visual 15 | Reward 10 | Feasible 10 | Novel 5 | Total |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Crucible | 14 | 15 | 14 | 13 | 9 | 8 | 4 | 77 |
| Menagerie | 13 | 16 | 10 | 10 | 8 | 6 | 4 | 67 |
| Prism Lab | 9 | 15 | 13 | 14 | 9 | 8 | 2 | 70 |
| Echo Vault | 5 | 15 | 14 | 12 | 9 | 8 | 2 | 65 |
| WorldFuzz Arena | 8 | 4 | 12 | 5 | 7 | 8 | 4 | 48 |

The gap column is deliberately low everywhere. Pilot results (README) later showed that even Crucible's first version produced no gap against a top model.

## E. Final project decision

Crucible. It is the only candidate that combines the two findings that survive code tools: budgeted discovery (finding 1) and irreversible commitment with delayed consequences (finding 3). The sidecar holds the rules, so the agent cannot read or re-run the simulator; exhaustive search over gate orders gives exact "last solvable state" and "first fatal move" diagnostics; and a falling-matter simulation is cheap to render well.

## F. Formal environment specification

- **State.** Per chamber: a grid of cells (empty, wall, gate with id, or a substance id), a one-bit preference per cell, and a tick counter. Episode: a seeded skin (which visible symbol plays which role), three hard chambers, lab runs used, and the journal.
- **Substances.** Each has a phase (static, powder, liquid), a gravity direction (down or up) and a density. A moving cell passes through a liquid of opposite gravity or of the same gravity and lower density.
- **Reactions.** Fire on 4-neighbour contact; each maps a pair to a pair (possibly empty). A reaction may require a reactant to have enough same-kind neighbours (bulk only). One product reacts with wall cells.
- **Actions.** `lab(layout)` up to the run budget; `open(chamber, gate)`; `close(chamber)`.
- **Transition.** Opening a gate removes its cells, then the simulation runs to a fixed point (bounded by a tick limit). Fixed scan order, no randomness.
- **Observation.** Full grid, zones, objective counts, a reaction log, and tick-by-tick recordings on request. Hidden: substance behaviour and reactions.
- **Goal and reward.** A chamber is complete when every zone holds its required count. Reward is the mean of the three chamber scores, where an incomplete chamber earns 0.3 times its fraction of zones met.
- **Generator.** Seed chooses skin, mirror flip and gate numbering per chamber template. `scripts/validate.py` checks each seed exhaustively.
- **Solver.** `Oracle` enumerates gate orders with memoisation. The reference player identifies roles with six lab runs through the public interface, then plans with the oracle.
- **Diagnostics.** For every opening in a journal: winning orders before and after, whether it was the first fatal move, and which gates would have kept the chamber solvable.

## G. Concrete first playable puzzle

This was the first chamber built. It is no longer part of the shipped tasks (see section K) but remains in `templates.py`.

Chamber "leak" (unflipped): a basin whose floor has a one-cell hole above a sump. Gate 1 holds the carrier liquid, gate 2 a heavy powder directly above the hole, gate 3 a solvent that destroys the powder. Zone Z1 is the basin and needs 12 cells of the liquid. Winning orders, found by enumeration: (2, 1), (2, 3, 1), (3, 2, 1). Opening gate 1 first drains every liquid cell into the sump and no order recovers. Check it with `python3 scripts/design.py leak`.

## H. Engineering architecture

`engine/crucible/` is the single source: `core.c` (simulation), `engine.py` (ctypes binding), `chambers.py` and `templates.py` (matter family, chambers), `episode.py` (state machine, journal, scoring, replay), `oracle.py`, `server.py`. `scripts/build_tasks.py` copies it into self-contained Harbor task directories: `environment/` (agent container with only the CLI, plus the `sim` sidecar), `tests/` (separate verifier image that replays the sidecar journal with its own build), `solution/` (reference player). `web/` renders symbol grids produced by the engine and holds no game logic.

## I. Milestones

Done: simulation core, oracle, chamber set, server and CLI, reference player, Harbor reference and do-nothing runs, reward-integrity tests, hostile-agent check, blind pilots, 27 agent trials through Harbor and OpenCode, playtest page, replay viewer, clip renderer, rules-given and 9-run task variants. Not done: human playtests, demo video, small-model training.

## J. Risks and kill criteria

- **A top model solves it.** Triggered twice during development (see K). On the shipped tasks no OpenAI trial completed a facility in 12 attempts; Claude Fable 5.2 has not been run on them.
- **Humans cannot do it.** Untested. The shipped tasks are three hard chambers, so this risk is real.
- **Reference advantage.** The reference knows the matter family. This is disclosed, and the `-rules` variants exist to measure planning without discovery.

## K. What changed after the decision, and why

1. **Version 1 had no gap.** Two blind Claude pilots scored 1.00 by rehearsing every risky step in a generous lab. Response: smaller lab, fewer runs, a bulk-only reaction, a three-step reaction chain that eats walls.
2. **A fairness bug.** The bulk reaction could not be observed with any ordinary lab layout. The threshold was lowered and tests now assert that every rule is observable in the lab.
3. **Two arbitrary details removed.** Pilot losses traced to which wall the corrosive attacked first and to liquids being shoved by a different liquid. Both were made predictable, after which the strongest Claude pilot solved the six-chamber layout.
4. **Real agents measured.** Through Harbor and OpenCode, OpenAI models cleared the easy and medium chambers and lost the hard ones, so the easy and medium tiers were dropped and a third hard chamber (refinery) was added.
5. **Lab budget set to 6.** At 9 runs `gpt-6.1-sol` scored 1.00 once and 0.73 twice; at 6, the reference's own requirement, the same configurations scored 0.40, 0.43, 0.17, 0.17.
6. **A simulator convergence bug** (a cell shuttled forever between two trapped stacks) was found by exhaustive validation and fixed.

Current results are in the README.
