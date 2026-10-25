"""Step 3: features vs labels for each speed and Elo band -> reports/<label>/

  python scripts/3_eda.py

Writes, for each label (think_time, blunder, blunder_next5):
  reports/<label>/ranking.png + ranking.md   feature strength by speed and Elo band
  reports/<label>/<speed>.png                label vs the relevant features, one line per Elo band
  reports/<label>/speeds.png                 the same, bullet vs blitz vs classical
  reports/<label>/clock_in_position.png      (blunder labels) time pressure at fixed win%
and reports/feature_ranking.csv, reports/feature_redundancy.png.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from oracle.config import REPORTS, SPEEDS  # noqa: E402
from oracle.eda import run_all  # noqa: E402
from oracle.features import load_moves  # noqa: E402


def main() -> None:
    t0 = time.time()
    data = {s: load_moves(s) for s in SPEEDS}
    for s, m in data.items():
        print(f"{s:10s} {m['game_id'].nunique():,} games, {m['blunder'].notna().sum():,} labelled moves")
    picks = run_all(data, REPORTS, log=lambda msg: print(f"{msg}  ({time.time() - t0:.0f}s)"))
    print("\nrecommended features:")
    for label, feats in picks.items():
        print(f"  {label:13s} {', '.join(feats)}")


if __name__ == "__main__":
    main()
