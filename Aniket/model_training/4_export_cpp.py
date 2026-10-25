"""Step 4: export the 9 models for the C++ predictor -> cpp/models/<speed>.txt (+ cpp/tests/<speed>.csv)

  python 4_export_cpp.py
  cd cpp && make test       # C++ must reproduce the Python predictions on every test move

Each speed's file holds the superset feature vector it expects (config.SUPERSETS, same order as
eda/FEATURE_SET.md) and its 5 boosted-tree models (think time low/median/high, blunder, blunder_next5).
Every split already points into the superset vector, so the C++ code reads the vector directly.
cpp/tests/<speed>.csv holds every test move's superset vector plus the Python predictions.

File format (text, one item per line):
  oracle-model 1 / speed <name> / features <n> <names...>
  booster <name> <quantile|logistic> <baseline> <n_trees>, then per tree: tree <n_nodes>, then per node
      "<feature> <threshold> <missing_goes_left> <left> <right>" (split) or "-1 <value>" (leaf)
  widen <w>            think-time range correction (log scale)
  cutoff <name> <c>    flag = chance >= c
  end
"""
import joblib
import numpy as np
import pandas as pd

from config import FEATURES, MODELS, ROOT, SPEEDS, SUPERSETS, TARGETS, TEST_DATA

CPP = ROOT / "cpp"
OUTPUTS = ["think_low", "think_median", "think_high", "p_blunder", "flag_blunder", "p_blunder_next5", "flag_blunder_next5"]


def write_booster(f, name: str, kind: str, model, features: list[str], superset: list[str]) -> int:
    to_superset = [superset.index(c) for c in features]
    trees = [p[0] for p in model._predictors]  # binary / regression: one tree per boosting round
    f.write(f"booster {name} {kind} {float(np.ravel(model._baseline_prediction)[0])!r} {len(trees)}\n")
    for t in trees:
        assert not t.nodes["is_categorical"].any()
        f.write(f"tree {len(t.nodes)}\n")
        for n in t.nodes:
            if n["is_leaf"]:
                f.write(f"-1 {float(n['value'])!r}\n")
            else:
                f.write(f"{to_superset[n['feature_idx']]} {float(n['num_threshold'])!r} {int(n['missing_go_to_left'])} "
                        f"{int(n['left'])} {int(n['right'])}\n")
    return len(trees)


def main() -> None:
    (CPP / "models").mkdir(parents=True, exist_ok=True)
    (CPP / "tests").mkdir(parents=True, exist_ok=True)
    for speed in SPEEDS:
        superset = SUPERSETS[speed]
        assert len(set(superset)) == len(superset) and set(superset) == set().union(*FEATURES[speed].values())
        b = {t: joblib.load(MODELS / speed / f"{t}.joblib") for t in TARGETS}
        path = CPP / "models" / f"{speed}.txt"
        n_trees = 0
        with open(path, "w") as f:
            f.write(f"oracle-model 1\nspeed {speed}\nfeatures {len(superset)} {' '.join(superset)}\n")
            tt = b["think_time"]
            for head in ("low", "median", "high"):
                n_trees += write_booster(f, f"think_{head}", "quantile", tt["model"][head], tt["features"], superset)
            f.write(f"widen {tt['widen']!r}\n")
            for t in ("blunder", "blunder_next5"):
                n_trees += write_booster(f, t, "logistic", b[t]["model"], b[t]["features"], superset)
                f.write(f"cutoff {t} {b[t]['cutoff']!r}\n")
            f.write("end\n")
        p = pd.read_parquet(TEST_DATA / speed / "predictions.parquet")  # Python predictions from 3_evaluate.py
        p[superset + OUTPUTS].to_csv(CPP / "tests" / f"{speed}.csv", index=False, float_format="%.17g", na_rep="nan")
        print(f"{speed:10s} {len(superset)} inputs, {n_trees:,} trees -> {path} ({path.stat().st_size / 1e6:.1f} MB); "
              f"{len(p):,} test vectors")


if __name__ == "__main__":
    main()
