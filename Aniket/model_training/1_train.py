"""Step 1: train the 9 models (3 speeds x 3 targets) on ALL the EDA games -> models/<speed>/<target>.joblib

  python 1_train.py                    # all 9 (~40 min: the three speeds train in parallel)
  python 1_train.py --speed blitz      # one speed

For each model: tune tree size with 5-fold cross-validation grouped by game, pick the number of
boosting rounds on held-out games, test monotone constraints, compare against simpler models,
then refit on all games. Cross-validation results go into the saved bundle and reports/cv.md.
"""
import argparse
import os
import time
from concurrent.futures import ProcessPoolExecutor

from config import MODELS, REPORTS, SPEEDS, TARGETS, TRAIN_DATA


def train_speed(speed: str, threads: int) -> str:
    import joblib
    import pandas as pd
    from threadpoolctl import threadpool_limits

    from modelling import train_one

    moves = pd.read_parquet(TRAIN_DATA / speed / "moves.parquet")
    (MODELS / speed).mkdir(parents=True, exist_ok=True)
    with threadpool_limits(threads):
        for target in TARGETS:
            bundle = train_one(speed, target, moves, log=lambda m: print(m, flush=True))
            joblib.dump(bundle, MODELS / speed / f"{target}.joblib", compress=3)
    return speed


def cv_report() -> str:
    """reports/cv.md: how every candidate did in cross-validation on the training games."""
    import joblib
    import pandas as pd

    lines = ["# Cross-validation on the training games (5 folds, grouped by game)", "",
             "Every candidate saw the same held-out games. 'trees (chosen)' is what was saved.", ""]
    for speed in SPEEDS:
        for target in TARGETS:
            b = joblib.load(MODELS / speed / f"{target}.joblib")
            t = pd.DataFrame(b["cv"]["table"]).T
            cols = (["mae_s", "median_ae_s", "within_2x", "coverage_80", "spearman", "loss"] if target == "think_time"
                    else ["auc", "pr_auc", "log_loss", "log_loss_skill", "brier_skill", "top10_lift", "ece"])
            t = t[[c for c in cols if c in t]]
            lines += [f"## {speed} / {target}", "",
                      f"{b['train_games']:,} games, {b['train_rows']:,} moves. Chosen: max_leaf_nodes="
                      f"{b['params']['max_leaf_nodes']}, min_samples_leaf={b['params']['min_samples_leaf']}, "
                      f"{b['n_iter']} rounds, monotone constraints {'on ' + str(b['monotone_features']) if b['monotone'] else 'off'}"
                      + (f", flag cutoff {100 * b['cutoff']:.1f}% ({b['cutoff_rule']} rule: precision "
                         f"{100 * b['cv_flags']['precision']:.0f}%, recall {100 * b['cv_flags']['recall']:.0f}%, "
                         f"F1 {b['cv_flags']['f1']:.2f}, accuracy {100 * b['cv_flags']['accuracy']:.1f}%)"
                         if "cutoff" in b else "") + ".", "",
                      "| model | " + " | ".join(t.columns) + " |", "|---|" + "---:|" * len(t.columns)]
            for name, r in t.iterrows():
                lines.append(f"| {name} | " + " | ".join("" if pd.isna(v) else f"{v:.4f}" for v in r) + " |")
            lines.append("")
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--speed", choices=SPEEDS, action="append", help="default: all")
    a = ap.parse_args()
    speeds = a.speed or list(SPEEDS)
    threads = max(1, (os.cpu_count() or 3) // len(speeds))
    t0 = time.time()
    with ProcessPoolExecutor(len(speeds)) as ex:
        for s in ex.map(train_speed, speeds, [threads] * len(speeds)):
            print(f"== {s} done ({(time.time() - t0) / 60:.1f} min)", flush=True)
    if all((MODELS / s / f"{t}.joblib").exists() for s in SPEEDS for t in TARGETS):
        REPORTS.mkdir(parents=True, exist_ok=True)
        (REPORTS / "cv.md").write_text(cv_report(), encoding="utf-8")
        print(f"wrote {REPORTS / 'cv.md'}")


if __name__ == "__main__":
    main()
