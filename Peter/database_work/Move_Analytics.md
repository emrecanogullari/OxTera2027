# Move analytics: `best_next_move`

This pass does not write to `engine_features`. That table stays as it is for the other Stockfish job. Results go in a new table, `best_next_move`.

The script is `Peter/annotate/build_best_next_move.py`. The table statement is `Peter/sql/009_best_next_move.sql`.

Nothing in this pass deletes rows. There is no `DELETE`, `TRUNCATE`, or `DROP`. The only write is `CREATE TABLE IF NOT EXISTS best_next_move`, then `INSERT` into that table. If a `(game_id, ply)` is already there, the insert updates the seven result columns on that same row and leaves the copied input columns alone.

## What is read

One row per replayed half-move. A row is skipped once it already exists in `best_next_move`. Games that never made it into `engine_features` are not invented here.

| Source | Columns copied, same names |
|---|---|
| `engine_features` | `game_id`, `ply`, `fen_before` |
| `moves` | `color`, `san` |
| `move_replay` | `material_white`, `material_black`, `material_total`, `material_advantage_white`, `material_advantage_mover`, `prev_think_white_s`, `prev_think_black_s`, `clk_before_s`, `opp_clk_s`, `log_clk_before`, `log_opp_clk` |
| `move_metrics` | `elo`, `opp_elo`, `elo_diff`, `rating_band`, `base`, `inc`, `tc`, `clk_frac`, `clk_frac_band`, `ply_phase`, `premove` |

`san` is the move that was played. `fen_before` is the position the player was looking at before that move. Clocks are the times at the start of the turn. Material and the rating fields describe that same moment.

These are not copied, because they describe the move after it was played: `eval_cp`, `clk_after_s`, `think_s`, `wp_after`, `wp_loss`. `move_outcomes` and `lookup_budgets` are not read.

The only value Stockfish is given is `fen_before`.

## What is written

All of the copied columns above, plus:

| Column | Meaning |
|---|---|
| `best_possible_move` | UCI of the best Stockfish line, from the side to move. This replaces the name `best_wp`. |
| `second_best_move` | UCI of the second line. This replaces the name `second_wp`. Empty when the position has only one legal move. |
| `best_possible_move_wp` | Win percent of that best line, side to move. Kept so `gap` can be checked. |
| `second_best_move_wp` | Win percent of the second line. Empty when there is no second line. |
| `gap` | `best_possible_move_wp - second_best_move_wp`. Empty when there is no second line. |
| `n_near_best` | How many of the searched lines sit within 5 win-percent points of the best line, including the best line. |
| `n_legal_moves` | Legal moves in `fen_before`, counted with python-chess. |

Win percent is the Lichess curve, the same one as `wp_from_cp` in the database:

```text
wp(cp) = 50 + 50 * (2 / (1 + exp(-0.00368208 * cp)) - 1)
```

A mate score is clamped to ±10000 centipawns before that formula. Stockfish’s score is already from the side to move.

## How the search is run

Stockfish 19, MultiPV 4, depth 12, one thread and 64 MB hash per worker. Workers are one less than the number of CPU cores. Each position starts a fresh search, so one row does not inherit the previous position. The main process writes 50 finished rows at a time and commits.

If a `(game_id, ply)` is already present, the same insert replaces the seven result columns and leaves the copied inputs in place. No row is removed.

From `Peter/`, after `tiger auth login` on this machine:

```bash
python -m annotate.build_best_next_move
```

The binary used is `Peter/.tools/stockfish`. That folder is gitignored.

## Two rows checked before the fill

These two reads did not write anything. They used the same search as the fill. Both checks held: the best and second moves were legal, the gap was the difference of the two win percents, the legal-move count matched the position, and the side to move matched `color`.

Ply 1 of game `00gJXq6n`, White to move, starting position, 300+0, both clocks 300, played `e4`:

| Column | Value |
|---|---|
| best_possible_move | `e2e4` |
| second_best_move | `d2d4` |
| best_possible_move_wp | 52.94 |
| second_best_move_wp | 52.12 |
| gap | 0.83 |
| n_near_best | 4 |
| n_legal_moves | 20 |

Ply 2 of the same game, Black to move after `e4`, played `e5`:

| Column | Value |
|---|---|
| best_possible_move | `e7e5` |
| second_best_move | `c7c5` |
| best_possible_move_wp | 48.44 |
| second_best_move_wp | 47.24 |
| gap | 1.19 |
| n_near_best | 4 |
| n_legal_moves | 20 |

The full fill writes every replayed ply, including these two, into `best_next_move` only.
