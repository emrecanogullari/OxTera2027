# Blunder Oracle: feature set per speed

Each row of data = one move, described **before** the player makes it. From that row we predict 3 targets:

| target | meaning |
|---|---|
| **T** `time_spent` | seconds the player will spend on this move |
| **A** `blunder` | the move loses ≥ 20 points of win chance (1/0) |
| **B** `blunder_next5` | a blunder on this move or one of the player's next 4 moves (1/0) |

## Feature arrays (everything needed for T + A + B in that speed)

```python
bullet = ["clock_self", "clock_opp", "clock_ratio", "base", "inc",
          "prev_self_spent", "avg_self_spent", "prev_opp_spent",
          "elo_self", "ply", "mat_total", "mat_diff", "n_legal", "n_captures",
          "wp_self", "abs_cp", "last_swing", "prior_blunders_self"]            # 18

blitz = ["clock_self", "clock_opp", "clock_ratio", "inc",
         "prev_self_spent", "avg_self_spent", "prev_opp_spent",
         "elo_self", "ply", "mat_total", "mat_diff", "n_legal", "n_captures",
         "wp_self", "abs_cp", "last_swing", "prior_blunders_self"]             # 17

classical = ["clock_self", "clock_ratio", "frac_self",
             "prev_self_spent", "avg_self_spent", "prev_opp_spent",
             "elo_self", "ply", "mat_total", "mat_diff", "n_legal", "n_captures",
             "wp_self", "abs_cp", "last_swing", "prior_blunders_self"]         # 16
```

## Feature vector for each target (strongest first)

### Bullet

```python
think_time    = ["avg_self_spent", "base", "prev_opp_spent", "prev_self_spent", "ply",
                 "clock_self", "inc", "n_captures", "n_legal", "elo_self"]
blunder       = ["last_swing", "wp_self", "abs_cp", "mat_diff", "n_captures", "mat_total",
                 "n_legal", "prior_blunders_self", "clock_opp", "clock_ratio", "elo_self"]
blunder_next5 = ["wp_self", "last_swing", "abs_cp", "mat_diff", "mat_total", "n_captures",
                 "n_legal", "clock_self", "clock_ratio", "prev_opp_spent", "elo_self"]
```

### Blitz

```python
think_time    = ["ply", "prev_opp_spent", "avg_self_spent", "prev_self_spent", "clock_self",
                 "n_legal", "clock_ratio", "n_captures", "inc", "abs_cp", "elo_self"]
blunder       = ["last_swing", "wp_self", "abs_cp", "mat_total", "mat_diff", "n_captures",
                 "clock_opp", "prior_blunders_self", "avg_self_spent", "prev_self_spent", "elo_self"]
blunder_next5 = ["wp_self", "last_swing", "abs_cp", "mat_total", "mat_diff", "n_captures",
                 "clock_opp", "n_legal", "prev_opp_spent", "clock_ratio", "elo_self"]
```

### Classical

```python
think_time    = ["prev_self_spent", "avg_self_spent", "prev_opp_spent", "ply", "n_legal",
                 "frac_self", "clock_ratio", "n_captures", "abs_cp", "wp_self", "elo_self"]
blunder       = ["last_swing", "wp_self", "abs_cp", "mat_diff", "n_captures", "ply",
                 "elo_self", "n_legal", "prior_blunders_self", "frac_self"]
blunder_next5 = ["wp_self", "last_swing", "abs_cp", "mat_diff", "mat_total", "elo_self",
                 "n_captures", "n_legal", "frac_self", "clock_self"]
```

Each list is the 10 strongest features for that target and speed (picked from 23 candidates, skipping
near-duplicates), measured on 2,000 analysed Lichess games per speed (Sept 2026). `elo_self` is in every
list: rating shifts every target up or down (e.g. blitz blunder rate is 6.4% under 1200 vs 2.7% at 2100+),
but which features matter is the same in every rating band, so no separate per-Elo models are needed.

## Feature reference

From a Lichess PGN:
- `[%clk h:mm:ss]` = the mover's clock **after** the move.
- `[%eval x]` = the engine eval **after** the move, from White's view, in pawns (`#-3` = mate).
- Headers give the ratings and `TimeControl "base+inc"`.

**Rule: a move's features only use moves before it.** The eval and clock after the opponent's last move
describe the position I'm facing.

| feature | what it means | how to calculate |
|---|---|---|
| `clock_self` | my time left as I start thinking (s) | my `%clk` after my previous move (my first move: `base`) |
| `clock_opp` | opponent's time left (s) | opponent's `%clk` after their last move (ply 1: `base`) |
| `clock_ratio` | who's ahead on time | `clock_self / max(clock_opp, 1)` |
| `frac_self` | share of my starting time left | `clock_self / base` (NaN if base = 0) |
| `base` | starting time (s) | TimeControl `180+2` → 180 |
| `inc` | seconds added per move | TimeControl `180+2` → 2 (berserk player: 0) |
| `prev_self_spent` | how long I took on my last move (s) | my clock before that move − my clock after it + `inc` |
| `avg_self_spent` | my usual pace this game (s) | mean of all my earlier think times this game |
| `prev_opp_spent` | how long my opponent took on their last move (s) | same formula on the opponent's last move |
| `elo_self` | my rating | `WhiteElo` or `BlackElo`, depending on my colour |
| `ply` | game stage (half-move number) | 1 for White's first move, 2 for Black's, … |
| `mat_total` | material left (game stage) | sum of all pieces, P=1 N=3 B=3 R=5 Q=9 (78 at the start) |
| `mat_diff` | material balance | my material − opponent's material |
| `n_legal` | how many options I have (complexity) | replay the game with python-chess; count legal moves before my move |
| `n_captures` | how tactical the position is | number of those legal moves that capture |
| `wp_self` | my win chance before moving (0–100) | eval after opponent's last move → `50 + 50·(2/(1+e^(−0.00368208·cp)) − 1)`, cp capped ±1000, mate → 0/100; use `100 − x` if I'm Black |
| `abs_cp` | how decided the game is | absolute value of that eval in centipawns (mate → 1000) |
| `last_swing` | did my opponent just blunder? | opponent's win% before their last move − after it |
| `prior_blunders_self` | my blunders so far this game | count of my earlier moves with win% drop ≥ 20 |

**Targets (computed after the move, training only, never inputs):**
- `time_spent = clock_self − (my %clk after this move) + inc`
- `blunder = 1 if wp_self − wp_after ≥ 20`, where `wp_after` is my win% from the eval after my move
- `blunder_next5 = 1 if blunder on this move or any of my next 4 moves`

**Notes:**
- `wp_self`, `abs_cp`, `last_swing` and `prior_blunders_self` need an engine eval of every position. In
  training this comes from Lichess's `%eval`; live, you'd run Stockfish yourself.
- Clocks are whole seconds. Each side's first move has no think time (leave it NaN).
- Use a tree model (gradient boosting handles NaN natively): one model per target per speed.
