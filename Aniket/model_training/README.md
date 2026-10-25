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

## Run it

```bash
python 1_train.py        # train all 9 on the 2,000 EDA games per speed (~40 min, speeds in parallel)
python 2_fetch_test.py   # pull 100 NEW games per speed from later the same day, label them (~2 min)
python 3_evaluate.py     # predict the test games, score vs labels, write reports/ (~2 min)
```

## Layout

```
config.py          paths, the 9 feature vectors, monotone rules, test-pull settings
modelling.py       the models, grouped cross-validation, scoring, predict_moves()
1_train.py  2_fetch_test.py  3_evaluate.py
models/<speed>/<target>.joblib        trained models (+ their cross-validation results)
test_data/<speed>/                    games.pgn, moves.parquet (labelled), predictions.parquet
reports/                              RESULTS.md, cv.md, <speed>/*.png
```

Features and labels are computed by the EDA code (`../eda/oracle/features.py`), imported, not copied,
so training and test moves go through exactly the same code.

## Use a model

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

Each bundle also holds `features` (the exact input columns), `params`, `cutoff` (blunder models: flag = chance ≥ cutoff,
chosen on training games for the best F1) and its cross-validation results under `cv`.
`.joblib`, `.parquet` and `.pgn` files are git-ignored by the repo's root `.gitignore`. To get the models elsewhere,
re-run the three scripts (the EDA data is needed for step 1).
