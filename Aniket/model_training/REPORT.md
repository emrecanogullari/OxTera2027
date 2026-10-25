# Blunder Oracle models: how well did it go?

**Short answer: well.** All 9 models predict new, unseen games clearly better than any simple rule. Their
test scores match what cross-validation promised, so they learned real patterns, not the training games.

- **Blunders are very predictable.** The blunder-now models rank risky moves above safe ones 85–87% of the time
  (AUC 0.85–0.87). Flagging the riskiest 10% of moves catches about half of all blunders.
- **Blunder in the next 5 moves** is harder, as expected: AUC 0.78–0.79.
- **The probabilities are honest.** When a model says 20%, about 20% of those moves are blunders.
- **Think time** is predictable but noisy: the typical miss is 1 s in bullet, 2 s in blitz and 7 s in classical,
  and the predicted 80% range covers 80% of moves in every speed.

---

## What was built

| | |
|---|---|
| Models | 9 = 3 speeds × 3 targets, each using its feature vector from `eda/FEATURE_SET.md` |
| Training data | all EDA games: 2,000 analysed games per speed (≈120–135k moves each), 1 Sept 2026, 00:00–11:40 UTC |
| Test data | 100 **new** analysed games per speed (≈6–7k moves each), 1 Sept 14:00–14:17 UTC, pulled after skipping the first 1.5M games of the month. Zero overlap with training; labelled by the same code |
| Outputs | `think_time` → seconds (median) + 80% range; `blunder`, `blunder_next5` → probability 0–1 |

## Which model, and why

**Gradient-boosted decision trees** (scikit-learn `HistGradientBoosting`). The EDA showed the targets depend on the
features in curved ways (win% has an M shape, blunders peak 2–4 pawns from equal) and through combinations (the
clock matters only once you know the position). Trees capture both on their own, and they handle the missing
values early in a game (no previous think time yet) without any patching.

This wasn't assumed; it was tested. On every one of the 9 tasks, 5-fold cross-validation on the training games
(whole games held out) compared trees against a linear model and a smooth additive model (one curve per feature,
no combinations):

| AUC (higher is better) | linear | smooth curves | **trees** |
|---|---|---|---|
| blunder: bullet / blitz / classical | 0.81 / 0.80 / 0.80 | 0.85 / 0.84 / 0.85 | **0.85 / 0.85 / 0.86** |
| blunder in 5: bullet / blitz / classical | 0.74 / 0.74 / 0.74 | 0.76 / 0.77 / 0.77 | **0.77 / 0.77 / 0.78** |
| think time, % within 2x: bullet / blitz / classical | 91 / 74 / 53 | 91 / 76 / 59 | **91 / 77 / 60** |

The jump from linear to smooth curves is the value of curved shapes; the further gain for trees is the value of
combinations. Trees won all 9 tasks (full table: [`reports/cv.md`](reports/cv.md)).

**How they were trained:**

1. **Cross-validation grouped by game.** A game's moves are never split between training and checking, otherwise
   the model could "recognise" the game and the scores would be inflated.
2. **Tuning.** Tree size (7–63 leaves, min 100–500 moves per leaf) was tuned per model. The number of boosting
   rounds was picked where the held-out loss bottoms out.
3. **Blunder models** are trained on log loss with no re-weighting of the rare blunders, so the probabilities stay
   calibrated (calibration error 0.1–0.7 points in cross-validation).
4. **Monotone rules** ("higher rating can only lower blunder risk", "more time left can only lower it") were tested
   and kept for the 6 blunder models, where they cost nothing and make the model behave sensibly if you ask it
   "what if I had more time?". They were dropped for think time, where they hurt.
5. **Think time** is three quantile models (10% / 50% / 90%) on log seconds. Clocks only record whole seconds, so
   each second is spread over [s, s+1) first; without that the ranges come out badly miscalibrated. A conformal
   correction, learned on held-out games, then sets the range so it covers 80% of moves.
6. **Final fit.** Each model was refit on all 2,000 games with the chosen settings (38 minutes for all 9).

## Results on the 300 new games

Brackets are 95% intervals from resampling the test games.

| speed | blunder now: AUC | blunder in 5: AUC | think time: typical miss | think time: within 2x | 80% range covers |
|---|---|---|---|---|---|
| bullet | **0.867** (0.85–0.88) | **0.793** (0.76–0.82) | 1 s (avg 1.08 s) | 91% | 80% |
| blitz | **0.846** (0.83–0.87) | **0.784** (0.76–0.81) | 2 s (avg 3.32 s) | 77% | 80% |
| classical | **0.870** (0.85–0.89) | **0.779** (0.75–0.81) | 7 s (avg 16.3 s) | 59% | 80% |

What that means in practice:

- **Flag the riskiest 10% of moves** and you catch **46–51% of all blunders**. 19–28% of those flagged moves really
  are blunders, about 5× the normal rate (3.7–5.5% depending on speed).
- **Per player per game**, the model's predicted number of blunders and the real number correlate **0.71–0.72**.
- **Counts add up.** Predicted vs real blunders over all test moves: bullet 307 vs 329, blitz 332 vs 329,
  classical 280 vs 250.
- **Think time beats every simple rule.** The best rule was "the typical time at this move number". Compared on the
  same resampled games, the model has lower error than it in all three speeds (bullet −0.12 s, blitz −0.31 s,
  classical −2.2 s; every interval excludes zero) and is within 2x more often (+4, +6 and +10 points).
- **Why there's no "accuracy %"** for blunders: they're rare, so "never a blunder" is already 95% accurate. The model
  gives a risk, not a yes/no. Per-speed figures (ROC curve, calibration, risk deciles, an example game) are in
  [`reports/RESULTS.md`](reports/RESULTS.md).

### If you need a yes/no flag

Labels are 1/0; the models output the chance of a 1. To get a 1/0 flag, use **flag = 1 if chance ≥ cutoff**. The
saved cutoffs give the **best F1**, the balance between "flags that are real" and "1s caught". They were picked on the
training games and applied unchanged to the test games. Codes: first digit = flag, second = actual.

| speed | blunder now: cutoff | flagged | 11 caught / 10 false alarm / 01 missed | flags real | 1s caught | blunder in 5: cutoff | flagged | flags real | 1s caught |
|---|---|---|---|---|---|---|---|---|---|
| bullet | **17.9%** | 7.6% | 143 / 306 / 186 | 32% | 43% | **22.6%** | 36% | 40% | 71% |
| blitz | **14.6%** | 8.5% | 136 / 428 / 193 | 24% | 41% | **23.4%** | 34% | 39% | 67% |
| classical | **16.2%** | 5.5% | 89 / 279 / 161 | 24% | 36% | **22.3%** | 31% | 32% | 63% |

- **Blunder-now flags are right 1 time in 3 or 4,** about 5–6× better than flagging at random, and they catch about
  4 in 10 blunders. Test results match training, so the cutoffs carry over to new games.
- **Accuracy is 91–93%, below "always 0" (94–96%).** No flag that catches blunders can beat "always 0" on accuracy,
  because blunders are rare: the accuracy-maximising cutoff flags almost nothing (0–8 test moves) and misses every
  blunder.
- **The next-5 flag is on for about a third of moves,** because those events are common. A stricter 40% cutoff flags
  about 10% of moves and is right about half the time, but catches only ~30% of events.

**Other cutoff rules** (chosen the same way on training games; full comparison in [`reports/RESULTS.md`](reports/RESULTS.md)):

| rule | blunder now: cutoff | flagged | 1s caught | blunder in 5: cutoff | 1s caught |
|---|---|---|---|---|---|
| max accuracy (most 00 + 11 overall) | 52–78% | 0–0.1% | 0–1% | 48–51% | 11–20% |
| **best F1 (saved)** | 15–18% | 5.5–8.5% | 36–43% | 22–23% | 63–71% |
| max balanced (most 0s *and* most 1s right as rates) | 4–5% | 27–35% | 83–88% | 16–19% | 74–79% |

- **Switching needs no retraining:** `predict_moves(bundles, moves, rule="accuracy")` or `rule="balanced"`.
- **The graphs:** `reports/<speed>/<target>_flags.png` shows how precision, recall, F1 and accuracy change with the
  cutoff, the 00/10/01/11 confusion matrix, and every test game move by move.

## Why I trust these numbers

| check | result |
|---|---|
| Test vs cross-validation | test AUC within ±0.025 of cross-validation for all 6 blunder models; think-time error inside the test interval. No overfitting |
| New games only | test games from 2–3 hours after the training window; 0 shared game IDs |
| Same feature code | training and test moves both go through `eda/oracle/features.py`; the EDA's `test_no_peeking` guarantees features use only information from before the move |
| Calibration | 20% means about 20% on the test games (plots in `reports/<speed>/`) |
| Every rating band | blunder AUC 0.84–0.87 in every Elo band and speed, with predicted rate = actual rate to within 0.6 points (one exception: classical 2100+ blunder in 5, 7.4% predicted vs 8.3% actual, the smallest band). No per-Elo models needed |
| Beats simple rules | paired comparison on the same games, intervals exclude zero for all 3 think-time models |

## Honest limits

1. **Small test set.** 100 games per speed gives AUC intervals of about ±0.02–0.03. The direction is certain, the
   third decimal isn't.
2. **One day of data.** Train and test both come from 1 Sept 2026. A different month would be a stronger test.
3. **2,000 training games per speed**, as agreed. An earlier experiment suggested going to 16,000 games adds only
   about +0.01 AUC for blunders; classical think time would probably gain most.
4. **The chosen 10–11 features cost a little.** Trees on all 23 features did slightly better in cross-validation
   (+0.000–0.006 AUC, about 2–3% lower think-time error). I kept your feature vectors as agreed; switching is a
   one-line change in `config.py` if you want the extra.
5. **Four features need a chess engine live.** `wp_self`, `abs_cp`, `last_swing` and `prior_blunders_self` come
   from Lichess's own analysis in training. A live demo must run Stockfish on every position, ideally at a similar
   depth.
6. **A risk meter, not a crystal ball.** The riskiest 10% of moves blunder about 19–22% of the time (blunder now)
   and 47–57% (blunder in 5), and half of all blunders happen outside that top 10%. Classical was slightly over-predicted in the test window (3.7% actual vs 4.3%
   in training); recalibrate if you deploy at a different time.
7. **Classical think time is the weakest model** (59% within 2x). Long thinks in slow games depend on things the
   features can't see.

## What would improve it next

1. **A position-difficulty feature.** E.g. how many legal moves are blunders, from a quick multi-line engine run, or
   human-move predictions from Maia. Research says this is the strongest blunder predictor, and we don't have it yet.
2. **All 23 features and more games** (`eda/scripts/1_fetch.py` pulls 20k per speed): small, safe gains.
3. **Test on another month** to confirm it holds up over time.

## Files

```
README.md          how to run and how to use the models
REPORT.md          this file
predict.py         PGN in, the 3 predictions per move out     requirements.txt  exact versions used
cpp/               C++ predictor: superset feature vector in, 7-number prediction vector out (~50 µs per move)
reports/RESULTS.md all test numbers + figures   reports/cv.md  cross-validation per model
reports/<speed>/   blunder.png  blunder_next5.png  think_time.png  example_game.png
                   blunder_flags.png  blunder_next5_flags.png   (1/0 flag vs actual)
models/<speed>/    think_time.joblib  blunder.joblib  blunder_next5.joblib
test_data/<speed>/ games.pgn  moves.parquet  predictions.parquet
```
