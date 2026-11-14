# Crucible

You operate a sealed materials facility through the `crucible` command. The facility holds seven substances whose behaviour you are not told, a small lab where you can test them, and three chambers.

## Goal

Complete as many chambers as you can. A chamber is complete when every objective zone holds at least the required number of cells of the required substance once everything has come to rest.

## Chambers

- Substances start in reservoirs sealed by numbered gates.
- Your only action in a chamber is opening one gate. An opened gate stays open forever.
- After each opening the world runs by itself until nothing moves, then you see the result.
- There is no undo and no reset. You get one attempt per chamber.
- A wrong opening can make a chamber impossible to complete.
- An objective may ask for a substance that does not exist anywhere yet. It has to be produced.
- A chamber stops accepting actions once it is complete.

## Lab

- You have 7 lab runs in total, shared across all chambers.
- For each run you draw a layout in a box 8 cells wide and 6 high, using `.` (empty), `#` (wall) and the seven substance symbols. The box is enclosed by walls. The layout then runs until nothing moves.
- The lab follows exactly the same rules as the chambers. The rules are deterministic.
- Lab runs never change a chamber.
- Substances produced by reactions cannot be placed directly. To study one, make it inside the run.
- Lab output shows the enclosing wall, so its coordinates are shifted by one from your layout.

## What you are not told

How each substance moves, and what happens when substances touch. Behaviour can depend on how much of a substance is present, and substances produced by a reaction can react further. Symbols and names are arbitrary and differ between facilities. Everything you need can be learned in the lab.

## Scoring

Chambers 1, 2 and 3 have weights 0.2, 0.3 and 0.5. A complete chamber earns its full weight. An incomplete chamber earns 0.3 x (objectives met / objectives) x weight. Only the final state of the chambers counts. Nothing you write or report affects the score.

## Commands

```
crucible brief                     substances, lab budget, all chambers and objectives
crucible view N                    grid, gates and objectives of chamber N
crucible lab FILE                  run a lab experiment from a layout text file (- for stdin)
crucible open N GATE               open gate GATE in chamber N (permanent)
crucible close N                   give up on chamber N
crucible frames lab RUN            tick-by-tick recording of lab run RUN
crucible frames chamber N K        recording of the K-th gate opening in chamber N
crucible status                    progress summary
```

Add `--json` before the subcommand for machine-readable output, and `--every K` to `frames` to keep every K-th frame. Coordinates are zero-based: x grows to the right, y grows downward.

You may write and run any code you like in this container. When you are done, simply stop.

## Ground truth for this facility

This section is the complete and correct description of the substances.

- `F`: liquid: moves along its gravity, creeps sideways toward the nearest place it can keep going, and levels out; gravity pulls it down; density 20
- `A`: powder: moves straight or diagonally along its gravity, never sideways, so it piles; gravity pulls it down; density 40
- `B`: liquid: moves along its gravity, creeps sideways toward the nearest place it can keep going, and levels out; gravity pulls it up; density 10
- `D`: powder: moves straight or diagonally along its gravity, never sideways, so it piles; gravity pulls it up; density 30
- `J`: liquid: moves along its gravity, creeps sideways toward the nearest place it can keep going, and levels out; gravity pulls it down; density 30
- `E`: static solid, never moves
- `G`: static solid, never moves (does not exist at the start; made by a reaction)
- `K`: liquid: moves along its gravity, creeps sideways toward the nearest place it can keep going, and levels out; gravity pulls it down; density 15 (does not exist at the start; made by a reaction)
- `C`: liquid: moves along its gravity, creeps sideways toward the nearest place it can keep going, and levels out; gravity pulls it down; density 35 (does not exist at the start; made by a reaction)
- `H`: liquid: moves along its gravity, creeps sideways toward the nearest place it can keep going, and levels out; gravity pulls it down; density 12

A moving cell passes through a liquid cell when that liquid has the opposite gravity, or the same gravity and lower density. Powders never pass through powders.

Reactions happen when cells touch side to side or top to bottom:

- `J` touching `E`: `J` becomes nothing, `E` becomes nothing.
- `J` touching `A`: `J` becomes nothing, `A` becomes nothing.
- `F` touching `B`: `F` becomes `G`, `B` becomes `G`. Only happens when the `B` cell has at least 1 neighbours of its own kind.
- `F` touching `D`: `F` becomes `K`, `D` becomes nothing.
- `K` touching `D`: `K` becomes `K`, `D` becomes `K`.
- `K` touching `J`: `K` becomes `C`, `J` becomes `C`.
- `C` touching a wall cell: `C` becomes nothing, a wall cell becomes nothing.
- `H` touching `K`: `H` becomes `H`, `K` becomes `H`.
