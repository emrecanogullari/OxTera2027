# Proposed `engine_features` columns

One row is one ply: the moment a player is about to move. `game_id` + `ply` identify the row. `ply` 1 is White’s first move.

The model is trained on finished games, so each training row can include the feature list and the targets. The targets are the answers for that past move. They are not inputs. A live guess uses the feature list only.

Every name below is a column on `engine_features`. The fill is in `Peter/sql/010_fill_engine_features.sql`. `n_captures` is counted from `fen_before`.

A feature may use the position, the clocks at the start of the turn, the ratings, the time control, and what already happened earlier in the game. It must not use the move about to be played, how long that think took, the eval after that move, or the game result.

The win-percent curve, when a stored centipawn value is turned into a percent, is

`wp(cp) = 50 + 50 * (2 / (1 + exp(-0.00368208 * cp)) - 1)`.

Mates in this database are stored as ±10000 centipawns before that curve. A percent under 50 on Black’s turn is normal: the percent is from the side to move.

## Features

Known before the move. This is the input list.

### Clocks and time control

| Column | What it is | How to get it |
|---|---|---|
| `clock_self` | Seconds I have as I start thinking. | My clock after my previous move. On my first move, the start time `base`. Already stored as `move_replay.clk_before_s`. |
| `clock_opp` | Seconds my opponent has as I start thinking. | Their clock after their last move. On ply 1, `base`. Already stored as `move_replay.opp_clk_s`. |
| `clock_ratio` | Who is ahead on the clock. Above 1 means I have more time. | `clock_self / max(clock_opp, 1)`. Not stored; both clocks are. |
| `frac_self` | Share of my starting time still left. 1 means a full clock, 0.1 means I have used almost all of it. | `clock_self / base`. Empty if `base` is 0. Already stored as `move_metrics.clk_frac`. |
| `time_trouble` | I am already short of time before this think. | True when `frac_self` is under 0.10. Already stored as `move_metrics.time_trouble`. |
| `base` | Starting seconds for the game. | `180` or `300` in this probe. From `games.base`. |
| `inc` | Seconds added after each move. | `0` for both time controls in this probe. From `games.inc`. |
| `ply_phase` | A coarse stage label an LLM can read beside the raw ply number. | `opening` for ply 1–20, `middlegame` for ply 21–60, `endgame` after that. Already stored as `move_metrics.ply_phase`. |

### Pace so far

| Column | What it is | How to get it |
|---|---|---|
| `prev_self_spent` | Seconds I spent on my previous move. | Clock before that move, minus clock after it, plus `inc`. Empty on my first move. Stored per side as `move_replay.prev_think_white_s` and `prev_think_black_s`; pick the side to move. |
| `avg_self_spent` | My usual pace in this game, in seconds. | Mean of my earlier think times only. Empty on my first move. Not stored as its own column; earlier `move_metrics.think_s` rows for my colour are enough. |
| `prev_opp_spent` | Seconds my opponent spent on their previous move. | Same think-time formula on their last move. Empty on ply 1. The other of the two `prev_think_*` columns. |

### Who is playing

| Column | What it is | How to get it |
|---|---|---|
| `color` | Side to move. | `w` or `b`. From `moves.color`. Needed to read clocks, material, and win percent from that side’s point of view. |
| `elo_self` | My rating. | White’s rating if I am White, Black’s rating if I am Black. Already stored as `move_metrics.elo`. |

### The position

| Column | What it is | How to get it |
|---|---|---|
| `ply` | Half-move number. 1 is White’s first move. | The row key. Also a feature: think time and blunders change from opening to endgame. |
| `fen_before` | The board I am looking at, before I move. | Forsyth–Edwards Notation for this ply. Already on `engine_features`, `move_replay`, and `best_next_move`. This is the position itself, so separate flags such as “in check” are not extra columns. |
| `mat_total` | Material still on the board. 78 is the start. | Pawn 1, knight 3, bishop 3, rook 5, queen 9, both sides added. Already stored as `move_replay.material_total`. |
| `mat_diff` | My material minus my opponent’s. Positive means I am ahead. | Already stored as `move_replay.material_advantage_mover`. |
| `n_legal` | How many legal moves I have. | Counted from `fen_before`. Already stored as `best_next_move.n_legal_moves`. The same column exists on `engine_features` and is still empty there. |
| `n_captures` | How many of those legal moves are captures. | A count of how tactical the position is. Not stored yet. It has to be counted from `fen_before`. |

### Eval of the position I am facing

These use the Lichess eval already stored on the moves, from the side to move. They are not the Stockfish search below. Ply 1 has no earlier eval, so these are empty there.

| Column | What it is | How to get it |
|---|---|---|
| `wp_self` | My win percent before I move, from 0 to 100. | Win percent of the eval after my opponent’s last move. Already stored as `move_metrics.wp_before`. |
| `abs_cp` | How far the position is from equal, in centipawns. A large number means the game is already decided. | Absolute value of `move_metrics.eval_before_mover`. Mates count as 10000. Not stored as its own column. |
| `last_swing` | How much my opponent just hurt their own win percent. A large positive number means they just made a serious error, and I may fail to punish it. | Their win percent before their last move, minus their win percent after it. That is `move_metrics.wp_loss` on their previous ply. Empty on ply 1. |
| `prev_self_wp_loss` | How much my own previous move hurt my win percent. | My `wp_loss` on my previous ply. Empty on my first move. Not stored on this row; it is the earlier row’s `move_metrics.wp_loss`. |
| `prior_blunders_self` | How many times I have already dropped 20 or more win-percent points in this game. | Count of my earlier plies with `wp_loss` ≥ 20. Uses the same 20-point rule as the `blunder` target. Not stored as its own column. |

### Engine view of the position I am facing

Stockfish 19, MultiPV 4, depth 12, run on `fen_before` only. The numbers were copied from `best_next_move`. The search does not see the move the human played.

| Column | What it is | How to get it |
|---|---|---|
| `best_possible_move` | The move Stockfish likes most, in UCI, such as `e2e4`. | `best_next_move.best_possible_move`. |
| `second_best_move` | The second line, in UCI. | `best_next_move.second_best_move`. Empty when only one move is legal. |
| `best_possible_move_wp` | Win percent of that best line, from the side to move. | `best_next_move.best_possible_move_wp`. |
| `second_best_move_wp` | Win percent of the second line. | `best_next_move.second_best_move_wp`. Empty when there is no second line. |
| `gap` | How much better the best line is than the second, in win-percent points. | `best_possible_move_wp - second_best_move_wp`. A large gap means one move matters and missing it is a blunder. A small gap means several moves are fine. Already stored as `best_next_move.gap`. `engine_features.gap` is the same idea and is still empty. |
| `n_near_best` | How many of the searched lines sit within 5 win-percent points of the best, including the best. | At most 4, because only 4 lines were searched. 1 means the best line stands apart from the others that were searched. 4 means those lines are bunched. Already stored as `best_next_move.n_near_best`. `engine_features.n_near_best` is still empty. |

## Targets

Computed after the move. Stored on the training row so the model can learn the link. Never passed in as inputs. Not known for a live position until the player has moved.

| Column | What it is | How to get it |
|---|---|---|
| `time_spent` | Seconds this move took. | `clock_self - clock after this move + inc`. Already stored as `move_metrics.think_s`. Clocks are whole seconds. |
| `blunder` | 1 if this move drops my win percent by 20 points or more, otherwise 0. | `wp_self - wp_after ≥ 20`. `wp_after` is my win percent from the eval after my move (`move_metrics.wp_after`). Empty when `wp_self` is empty, which is ply 1. |
| `blunder_next5` | 1 if this move is a blunder or any of my next 4 moves is a blunder, using the same 20-point rule. | This ply, plus my plies two, four, six, and eight ahead, when those plies exist. A game that ends is not a blunder. Not stored yet. |

The database column `move_outcomes.blunder` is a different cutoff: Lichess calls a drop of 30 or more a blunder, and a drop of 20 or more a mistake. For this model, `blunder` means the 20-point rule, which matches `move_outcomes.mistake` and `wp_loss ≥ 20`. Do not train on `move_outcomes.blunder` if the target is the one in this file.

## Left out on purpose

These exist in the database and were considered. They are not columns in the list above.

| Name | Why it is not an input |
|---|---|
| `san`, the played move | That move is what we are judging. Knowing it tells the model the answer. |
| `clk_after_s`, `think_s`, `premove` | These are the think that just happened. `time_spent` is the target. `premove` is true when that think was under 0.3 seconds. |
| `eval_after_mover`, `wp_after`, `wp_loss`, `success` | These describe the move after it was played. `wp_loss` is how `blunder` is decided. |
| `mover_result`, `games.result` | The game result comes later. |
| `opp_elo`, `elo_diff` | Opponent rating mostly tracks `elo_self` in this pool. A separate column adds little once my rating is present. |
| `tc` | The text `180+0` or `300+0`. `base` and `inc` already say that. |
| `rating_band`, `clk_frac_band` | Coarse buckets of `elo_self` and `frac_self`. The raw numbers are in the list. |
| `log_clk_before`, `log_opp_clk` | Logs of the two clocks. The raw clocks are in the list. |
| `material_white`, `material_black` | Recoverable from `mat_total`, `mat_diff`, and `color`. |
| `best_possible_move_wp`, `second_best_move_wp` | Stored on this table as the existing columns `best_wp` and `second_wp`, so the same two percents are not kept twice. |

## Where the two win percents are stored

`best_possible_move_wp` is stored as `best_wp`. `second_best_move_wp` is stored as `second_wp`. `n_legal` is stored as `n_legal_moves`. The other names in this file are the column names.
