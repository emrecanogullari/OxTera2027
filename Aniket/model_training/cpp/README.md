# C++ predictor

Feed it one move's **superset feature vector** and it returns the **prediction vector**. That's all 3 models of a
speed, with the flag cutoffs applied. It's a single header (`oracle_model.hpp`), C++17, with no dependencies.

```cpp
#include "oracle_model.hpp"

oracle::Model blitz("models/blitz.txt");                 // load once (~0.02 s)
std::vector<double> x = {/* 17 numbers in blitz.features() order, oracle::kMissing where undefined */};
oracle::Prediction p = blitz.predict(x);                 // ~50 microseconds, all 3 models
std::array<double, 7> v = blitz.predict_vector(x);       // the same as a vector
```

| | |
|---|---|
| **input** | the speed's superset vector, in exactly this order: bullet 18, blitz 17, classical 16 features (`../config.py` `SUPERSETS`, same as `../../eda/FEATURE_SET.md`). `./oracle_predict models/blitz.txt --features` prints it. Same units as training; `NaN` (`oracle::kMissing`) where a feature isn't defined yet (e.g. no previous think time on a player's first move) |
| **output** | `think_low, think_median, think_high` (whole seconds, 80% range), `p_blunder`, `flag_blunder`, `p_blunder_next5`, `flag_blunder_next5` (flag = chance ≥ the saved best-F1 cutoff) |

## Build, test, benchmark

```bash
python ../4_export_cpp.py   # models/<speed>.txt + tests/<speed>.csv from the trained .joblib models
make                        # builds oracle_predict
make test                   # C++ must match the Python predictions on every test move
make bench                  # speed
```

Results on this machine:
- **Matches Python exactly on all 19,656 test moves:** 0 think-time or flag mismatches, max chance difference 0.0.
- **47–56 µs per move for all 3 models** (about 2,000 trees), single-threaded. Python takes ~40 ms per move one at a
  time (about 800× slower).

## Command line

```bash
./oracle_predict models/blitz.txt vectors.csv > predictions.csv   # CSV with a header row; columns in any order
./oracle_predict models/blitz.txt --features                      # expected input order
```

- **One CSV row = one move's feature vector,** with as many rows as you like. You get one prediction row back per
  input row, in the same order.
- **The first row must name the columns.** Order doesn't matter and extra columns are ignored.
- **`nan` or an empty cell** = missing.
- **No file argument** = read from stdin.

## Example (real classical moves)

[`example_classical.csv`](example_classical.csv) holds Black's moves 45–50 of test game `3aRcE6wG` (1812-rated,
20+10):

```text
clock_self,clock_ratio,frac_self,prev_self_spent,avg_self_spent,prev_opp_spent,elo_self,ply,mat_total,mat_diff,n_legal,n_captures,wp_self,abs_cp,last_swing,prior_blunders_self
397.0,2.1459,0.3308,7.0,28.6744,4.0,1812,90,33.0,-5.0,24.0,1.0,11.396,557.0,2.8281,5.0
391.0,2.3136,0.3258,16.0,28.3864,26.0,1812,92,33.0,-5.0,26.0,2.0,10.9933,568.0,3.9088,5.0
391.0,2.3841,0.3258,10.0,27.9778,15.0,1812,94,33.0,-5.0,35.0,2.0,50.0,0.0,40.6518,5.0
386.0,2.2442,0.3217,15.0,27.6957,2.0,1812,96,33.0,-5.0,34.0,3.0,50.0,0.0,44.9883,6.0
391.0,2.2733,0.3258,5.0,27.2128,10.0,1812,98,33.0,-5.0,36.0,3.0,50.0,0.0,0.0,6.0
393.0,2.2717,0.3275,8.0,26.8125,9.0,1812,100,33.0,-5.0,29.0,1.0,50.0,0.0,0.0,6.0
```

`./oracle_predict models/classical.txt example_classical.csv` gives (cutoffs: blunder 16.2%, within 5: 22.3%):

```text
think_low,think_median,think_high,p_blunder,flag_blunder,p_blunder_next5,flag_blunder_next5
3,8,31,0.000058,0,0.023567,0
5,16,48,0.000059,0,0.023341,0
5,13,47,0.230939,1,0.550122,1
3,11,41,0.273985,1,0.550045,1
4,11,45,0.075480,0,0.283171,1
4,10,43,0.025974,0,0.182699,0
```

What actually happened: think times 16, 10, 15, 5, 8, 10 s. Move 47 (Qb1+) was a blunder; the model flagged it at 23%,
right after White's own 41-point blunder (`last_swing` 40.65). Move 48 was flagged too but wasn't one (false alarm).

## Notes

- **Re-run `python ../4_export_cpp.py` after retraining.** The `.txt` files are plain text: per tree, one line per
  node, either `feature threshold missing_goes_left left right` or `-1 leaf_value` (format in `../4_export_cpp.py`).
- **Don't compile with `-ffast-math`.** Missing values are NaN, and that flag lets the compiler assume NaN never
  occurs.
- **macOS:** some Command Line Tools installs lack the C++ standard headers. The Makefile detects this and uses the
  SDK's copy.
