# Which features matter for each label

Data: 2,000 analysed Lichess games each of **bullet, blitz, classical** (Sept 2026), about 130k
moves per speed. Strength = **eta** (correlation ratio, 0–1). It works like a correlation but also
catches U/V shapes. Full tables are in `<label>/ranking.md`, heatmaps in `<label>/ranking.png`.

## The answer: recommended features

| | think time (C) | blunder (A) | blunder in next 5 (B) |
|---|---|---|---|
| 1 | `avg_self_spent` 0.40 | `last_swing` 0.24 | `wp_self` 0.23 |
| 2 | `prev_self_spent` 0.36 | `wp_self` 0.16 | `last_swing` 0.23 |
| 3 | `prev_opp_spent` 0.36 | `abs_cp` 0.11 | `abs_cp` 0.22 |
| 4 | `ply` 0.33 | `mat_diff` 0.09 | `mat_diff` 0.16 |
| 5 | `clock_self` 0.25 | `mat_total` 0.09 | `mat_total` 0.16 |
| 6 | `n_legal` 0.25 | `n_captures` 0.09 | `n_captures` 0.13 |
| 7 | `inc` 0.22 | `n_legal` 0.07 | `n_legal` 0.12 |
| 8 | `n_captures` 0.22 | `prior_blunders_self` 0.07 | `clock_self` 0.10 |
| 9 | `abs_cp` 0.19 | `clock_self` 0.07 * | `prior_blunders_self` 0.05 |
| 10 | `elo_self` 0.14 * | `elo_self` 0.06 * | `elo_self` 0.10 * |

`*` = kept on purpose despite a modest score: the clock's real effect only shows once the position is
held fixed (see below), and rating shifts every curve up or down. Numbers are mean eta over the three
speeds. Eta values for rare yes/no labels (blunders ≈ 5%) are naturally smaller than for think time,
so compare within a column, not across columns.

**Drop for all three labels:**
- Near-duplicates of a kept feature: `clock_opp` (0.85 with `clock_self`), `frac_self` (0.82 with
  `clock_self` and `ply`), `elo_opp` (0.92 with `elo_self`). Keep only one of `ply` and `mat_total`
  (−0.92): `ply` for think time, `mat_total` for blunders.
- Little signal anywhere: `in_check`, `n_checks`, `elo_diff`, `base`, `clock_ratio`.
- `inc` matters for think time only.

That leaves **14 distinct features** across all three labels, down from 23.

## What the plots show

### Think time (`think_time/`)
- **Habit is the strongest signal.** How long I've been thinking this game (`avg_self_spent`),
  my last move's time, and *my opponent's* last move time (people match the pace) are the top three in
  every speed and every Elo band.
- **Game stage:** think time rises through the opening, peaks around ply 30–40, then falls (`ply`).
  In classical the peak is about 30 s per move vs about 7 s in blitz and 2–3 s in bullet.
- **Complexity:** more legal moves and more captures available → longer thinks (`n_legal`, `n_captures`).
- **Decided positions are played faster** (`abs_cp`: high → shorter).
- **Rating cuts both ways:** in bullet and blitz stronger players move *faster*. In **classical they think
  longer** (about 17 s per move at < 1200 → about 29 s at 2100+). This is the clearest difference
  between the game types.

### Blunder now (`blunder/`) and blunder in next 5 (`blunder_next5/`)
- **The ranking is nearly identical in bullet, blitz and classical.** The curves in `speeds.png`
  lie on top of each other; only the level shifts a little. One feature set works for all three speeds.
- **`last_swing`:** if my opponent just blundered, I "blunder" 20–25% of the time. Mostly I fail
  to punish, and the eval swings back.
- **`wp_self` has an M shape, not a line.** 0% below 20% win chance (you can't lose 20 points from
  a lost position), a peak around 40%, a dip at 50% (the opening), the highest peak around 75–80%
  ("winning but not won" is where people throw it away), and low again above 90%. A straight-line
  model would miss this. Use trees or binned features.
- **`abs_cp`:** blunders peak in positions about 2–4 pawns from equal. Dead-equal and totally decided
  positions are both safe.
- **`mat_diff`:** most blunders happen when material is roughly level or I'm a pawn or two up.
- **Busy positions are dangerous:** more captures and legal moves available → more blunders (rising almost linearly).
- **Rating** shifts every curve down (2100+ blunder at about half the rate of < 1200 at the same
  position), but the *shapes* stay the same within every Elo band.
- **Label B** (next 5 moves) is driven by the same features. Win chance and how decided the game is
  matter even more for B than for A.

### Time pressure is real but hidden (`clock_in_position.png`)
On its own, `clock_self` looks weak and jagged (eta 0.07). This has two causes:
1. A full clock means you're still in the opening, where nobody blunders.
2. Low-clock positions are often already decided, and you can't lose 20 points from a lost
   position.

So the plot holds win chance fixed (20–80%) and skips the opening. Then the clock effect is clear:

| contested positions, after move 10 | most time | < 5 s left |
|---|---|---|
| bullet | 2.5% (2–5 min) | **16%** |
| blitz | 4.6% (5–10 min) | **13.5%** |
| classical | 7% (10 min+) | 9% at 1–2 min; classical players rarely get lower |

So **`clock_self` stays in the blunder sets** even though its raw score is low. A model will only
use it properly alongside `wp_self`/`abs_cp` and `ply`/`mat_total`.

## How sure are we?

- **Stable:** eta computed on two random halves of the games differs by ≤ 0.035 for every feature
  (most < 0.02), and the top-5 order is the same in all three speeds.
- **Not just rating:** eta inside each Elo band (column "eta inside Elo bands" in `ranking.md`) is
  about the same as overall for every non-rating feature.
- **Only 2,000 games per speed.** Rare corners (classical with < 30 s, 2100+ in time trouble) are
  thin, and points with < 150 moves are hidden. `python scripts/1_fetch.py` (20k per speed,
  ~1.5–2 h) would firm these up.
- **Eta is one feature at a time.** It says what is *related*, not what adds information on top of
  the others. The redundancy plot (`feature_redundancy.png`) is the guard against picking the same
  information twice.

## Per speed: the 10 strongest non-duplicate features (eta within that speed)

| label | bullet | blitz | classical |
|---|---|---|---|
| **think time** | avg_self_spent .42, base .34, prev_opp_spent .33, prev_self_spent .33, ply .32, clock_self .30, inc .30, n_captures .22, n_legal .22, elo_self .20 | ply .37, prev_opp_spent .36, avg_self_spent .35, prev_self_spent .35, clock_self .30, n_legal .26, clock_ratio .24, n_captures .23, inc .23, abs_cp .21 | prev_self_spent .42, avg_self_spent .41, prev_opp_spent .37, ply .29, n_legal .26, frac_self .24, clock_ratio .22, n_captures .20, abs_cp .18, wp_self .18 |
| **blunder** | last_swing .27, wp_self .17, abs_cp .11, mat_diff .10, n_captures .10, mat_total .09, n_legal .08, prior_blunders_self .07, clock_opp .07, clock_ratio .07 | last_swing .23, wp_self .15, abs_cp .10, mat_total .10, mat_diff .08, n_captures .08, clock_opp .08, prior_blunders_self .07, avg_self_spent .07, prev_self_spent .07 | last_swing .23, wp_self .15, abs_cp .10, mat_diff .09, n_captures .08, ply .08, elo_self .07, n_legal .07, prior_blunders_self .06, frac_self .06 |
| **blunder in 5** | wp_self .24, last_swing .24, abs_cp .22, mat_diff .18, mat_total .16, n_captures .13, n_legal .12, clock_self .11, clock_ratio .09, prev_opp_spent .07 | wp_self .22, last_swing .22, abs_cp .21, mat_total .17, mat_diff .14, n_captures .13, clock_opp .12, n_legal .12, prev_opp_spent .11, clock_ratio .11 | wp_self .24, last_swing .22, abs_cp .22, mat_diff .15, mat_total .13, elo_self .13, n_captures .11, n_legal .10, frac_self .10, clock_self .08 |

## How each feature is calculated from the Lichess PGN

Raw ingredients per move: `%clk` = mover's clock **after** the move; `%eval` = engine eval **after** the move
(White's view, pawns; `#-3` = mate); headers = ratings and TimeControl `base+inc`. A feature for move t uses only
moves before t (the eval/clock after the opponent's last move describe the position I face).

| feature | calculation |
|---|---|
| `clock_self` | my own `%clk` after my previous move (my clock doesn't run on the opponent's turn); first move = base |
| `clock_opp` | opponent's `%clk` after their last move (ply 1: base) |
| `clock_ratio` | clock_self / max(clock_opp, 1) |
| `frac_self` | clock_self / base (NaN for 0+k games) |
| `prev_self_spent` | my think time on my previous move = (my clock before it − my clock after it + inc) |
| `prev_opp_spent` | the same for the opponent's last move |
| `avg_self_spent` | mean of all my earlier think times this game |
| `base`, `inc` | TimeControl header, e.g. `180+2` → 180, 2 (berserk players: inc treated as 0) |
| `elo_self` | WhiteElo or BlackElo header, by my colour |
| `ply` | half-move number (count of moves so far + 1) |
| `n_legal`, `n_captures` | replay the moves with python-chess; on the board BEFORE my move, count legal moves / legal captures |
| `mat_total`, `mat_diff` | same board: sum of pieces (P1 N3 B3 R5 Q9) for both sides / mine − theirs |
| `wp_self` | eval after the opponent's last move → win% = 50 + 50·(2/(1+e^(−0.00368208·cp)) − 1), cp capped ±1000, mate → 0/100; flipped if I'm Black |
| `abs_cp` | absolute value of that eval in centipawns (mate → 1000) |
| `last_swing` | opponent's win% before their last move − after it (big = they just blundered) |
| `prior_blunders_self` | count of my earlier moves this game with a ≥ 20-point win% drop |

## One model per Elo band? No. One per speed? For think time, yes.

**Elo changes the level, not which features matter.** Inside each speed, the feature ranking computed separately in
each Elo band matches the overall ranking (Spearman 0.86–0.99 for all labels and speeds), with one exception:
classical 2100+ (0.43–0.49). That band has only 6,343 moves (~100 games), too few to trust. What does change with Elo
is the level:

| blunder rate | <1200 | 1200-1500 | 1500-1800 | 1800-2100 | 2100+ |
|---|---|---|---|---|---|
| bullet | 6.5% | 5.6% | 5.3% | 4.9% | 4.0% |
| blitz | 6.4% | 5.0% | 4.5% | 4.1% | 2.7% |
| classical | 7.3% | 6.0% | 3.9% | 3.0% | 1.8% |

| mean think time | <1200 | 1200-1500 | 1500-1800 | 1800-2100 | 2100+ |
|---|---|---|---|---|---|
| bullet | 2.6 s | 2.2 s | 2.0 s | 1.8 s | 1.5 s |
| blitz | 6.0 s | 5.6 s | 5.1 s | 4.9 s | 4.1 s |
| classical | 16.8 s | 19.1 s | 21.0 s | 25.5 s | 30.6 s |

A tree model handles a level shift by itself if `elo_self` is a feature. Separate Elo models would split the data
5 ways (the top classical band would have ~100 games) for no gain. **Recommendation: keep `elo_self` as a feature,
no Elo models; check the predictions are calibrated in each Elo band.**

**Speed:** think time differs about 10× between bullet and classical, and its top features differ (`base` matters
in bullet, `clock_ratio` in blitz, `frac_self` in classical): **one think-time model per speed**. Blunder features
rank almost identically in all three speeds, so the blunder models (A, B) can be per speed *or* one pooled model
with `base`/`inc` as features. Per speed is the simpler starting point: 3 speeds × 3 labels = 9 models.

## Files

```
reports/
  FEATURES.md                 this file
  feature_ranking.csv         every eta / rho, per label x speed x Elo band
  feature_redundancy.png      which features duplicate each other
  think_time/  blunder/  blunder_next5/
    ranking.png  ranking.md   feature strength by speed and Elo band
    bullet.png blitz.png classical.png   label vs top features, one line per Elo band
    speeds.png                label vs top features, bullet vs blitz vs classical
    clock_in_position.png     (blunder labels only) time pressure at fixed win chance
```
