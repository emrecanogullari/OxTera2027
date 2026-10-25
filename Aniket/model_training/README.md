# Blunder Oracle: model training

9 models: 3 speeds (bullet, blitz, classical) × 3 targets, each using its feature vector from
[`../eda/FEATURE_SET.md`](../eda/FEATURE_SET.md):

| target | the model outputs |
|---|---|
| `think_time` | predicted seconds for this move + an 80% range (low–high) |
| `blunder` | chance (0–1) that this move loses ≥ 20 win% points, + a 1/0 flag (chance ≥ the model's cutoff) |
| `blunder_next5` | chance (0–1) of a blunder on this move or my next 4, + a 1/0 flag |

**Read [`REPORT.md`](REPORT.md) first** (how well it went). Full numbers: [`reports/RESULTS.md`](reports/RESULTS.md) (test games)
and [`reports/cv.md`](reports/cv.md) (cross-validation on the training games).

## Predict a game

```bash
pip install -r requirements.txt
python predict.py game.pgn                          # table per move: think time, P(blunder), P(blunder in 5), flags
python predict.py games.pgn --out predictions.csv   # every move to a CSV
```

The PGN needs clocks (`[%clk 0:02:58]`) and engine evals (`[%eval 0.35]`), e.g. a Lichess export of an analysed
game. Without evals the blunder chances are unreliable, and `predict.py` warns. The speed comes from each game's
TimeControl; rapid and other speeds have no model and are skipped.

## Run the pipeline

```bash
python 1_train.py        # train all 9 on the 2,000 EDA games per speed (~40 min, speeds in parallel)
python 2_fetch_test.py   # pull 100 NEW games per speed from later the same day, label them (~2 min)
python 3_evaluate.py     # predict the test games, score vs labels, write reports/ (~2 min)
python 4_export_cpp.py   # export the models for the C++ predictor -> cpp/models/ (then: cd cpp && make test)
```

## C++ predictor (fast)

[`cpp/`](cpp/README.md): feed it a move's superset feature vector (`config.SUPERSETS`, the arrays in
`../eda/FEATURE_SET.md`) and get back the 7-number prediction vector, with the flags applied. It's a single header
with no dependencies, takes about 50 µs per move for all 3 models, and matches the Python predictions exactly on
every test move.

## Layout

```
config.py          paths, the 9 feature vectors, monotone rules, test-pull settings
modelling.py       the models, grouped cross-validation, scoring, predict_moves()
1_train.py  2_fetch_test.py  3_evaluate.py  4_export_cpp.py
predict.py         PGN in, the 3 predictions per move out
requirements.txt   the exact versions the models were trained with
cpp/               C++ predictor: oracle_model.hpp, oracle_predict.cpp, Makefile, models/<speed>.txt
models/<speed>/<target>.joblib        trained models (+ their cross-validation results)
test_data/<speed>/                    games.pgn, moves.parquet (labelled), predictions.parquet
reports/                              RESULTS.md, cv.md, <speed>/*.png
```

Features and labels are computed by the EDA code (`../eda/oracle/features.py`), imported, not copied,
so training, test and `predict.py` moves all go through exactly the same code.

## Use the models in your own code

You need the `.joblib` files, Python 3.11 with **scikit-learn 1.3.0** (see `requirements.txt`; the saved models are
tied to that version), and a feature table with:
- **the columns in each bundle's `features`:** same names, same order (the wrong order raises an error)
- **the same units** as training
- **missing values left as NaN**

The safest way to make that table is `build_tables()` from `../eda/oracle/features.py`; otherwise follow
`../eda/FEATURE_SET.md` exactly.

**With this folder's code:**

```python
import joblib, pandas as pd
from modelling import predict_moves      # run from this folder

speed = "blitz"
bundles = {t: joblib.load(f"models/{speed}/{t}.joblib") for t in ("think_time", "blunder", "blunder_next5")}
moves = pd.read_parquet(f"test_data/{speed}/moves.parquet")   # any table made by eda's build_tables()
print(predict_moves(bundles, moves).head())
#    think_low  think_median  think_high  p_blunder  flag_blunder  p_blunder_next5  flag_blunder_next5
predict_moves(bundles, moves, rule="balanced")   # other flag cutoff: "f1" (saved), "accuracy", "balanced"
```

**Without any of our code.** The `.joblib` files hold plain scikit-learn models, so numpy, pandas, scikit-learn and
joblib are enough:

```python
import joblib, numpy as np

b = joblib.load("models/blitz/blunder.joblib")             # same for blunder_next5.joblib
p = b["model"].predict_proba(moves[b["features"]])[:, 1]   # chance of a blunder on this move
flag = p >= b["cutoff"]                                    # 1/0 flag (best-F1 cutoff)

t = joblib.load("models/blitz/think_time.joblib")
P = np.column_stack([t["model"][k].predict(moves[t["features"]]) for k in ("low", "median", "high")])
P.sort(axis=1)                                             # the three never cross
P[:, 0] -= t["widen"]; P[:, 2] += t["widen"]               # calibrated 80% range
low, median, high = np.floor(np.expm1(P)).clip(0).T        # whole seconds
```

Each bundle also holds `params`, its cross-validation results under `cv`, and (blunder models) `cutoff_rule`.
`.joblib`, `.parquet`, `.pgn` and `.csv` files are git-ignored by the repo's root `.gitignore`: share the `models/`
folder directly, or re-run the scripts (step 1 needs the EDA data).
