"""Predict think time, blunder chance and blunder-within-5 chance for every move of every game in a PGN file.

  python predict.py game.pgn                          # prints a table per game
  python predict.py games.pgn --out predictions.csv   # also writes every move to a CSV
  python predict.py games.pgn --out predictions.csv --quiet

Each prediction uses only what was known before that move. The PGN should have clock comments
([%clk 0:02:58]) and engine evals ([%eval 0.35]), like a Lichess export of an analysed game. Without them
the clock or engine features are missing and the predictions are unreliable (a warning is printed).
The speed (bullet / blitz / classical) comes from each game's TimeControl; other speeds have no model.
"""
import argparse
import sys
from pathlib import Path

import joblib
import pandas as pd

from config import MODELS, SPEEDS, TARGETS
from modelling import predict_moves
from oracle.features import build_tables

CSV_COLS = {  # output column -> source column
    "game_id": "game_id", "ply": "ply", "color": "color", "move": "san", "speed": "speed", "clock_self": "clock_self",
    "think_low": "think_low", "think_median": "think_median", "think_high": "think_high",
    "p_blunder": "p_blunder", "flag_blunder": "flag_blunder",
    "p_blunder_next5": "p_blunder_next5", "flag_blunder_next5": "flag_blunder_next5",
    "actual_think_time": "time_spent", "actual_blunder": "blunder", "actual_blunder_next5": "blunder_next5",
}
_BUNDLES: dict = {}


def bundles_for(speed: str) -> dict:
    if speed not in _BUNDLES:
        _BUNDLES[speed] = {t: joblib.load(MODELS / speed / f"{t}.joblib") for t in TARGETS}
    return _BUNDLES[speed]


def num(v, fmt: str = "{:.0f}") -> str:
    return "–" if pd.isna(v) else fmt.format(v)


def show(g: pd.Series, m: pd.DataFrame) -> None:
    print(f"\n== {g['game_id']}: {g['white']} ({num(g['white_elo'])}) vs {g['black']} ({num(g['black_elo'])}), "
          f"{g['speed']} {g['time_control']}, {(len(m) + 1) // 2} moves")
    t = pd.DataFrame({
        "move": [f"{(p + 1) // 2}{'.' if c == 'white' else '...'}" for p, c in zip(m["ply"], m["color"])],
        "played": m["san"],
        "clock": m["clock_self"].map(lambda v: num(v, "{:.0f}s")),
        "think (80% range)": [f"{md:.0f}s ({lo:.0f}-{hi:.0f})" for lo, md, hi in
                              zip(m["think_low"], m["think_median"], m["think_high"])],
        "real think": m["time_spent"].map(lambda v: num(v, "{:.0f}s")),
        "P(blunder)": m["p_blunder"].map(lambda v: f"{100 * v:.0f}%"),
        "flag": m["flag_blunder"],
        "was blunder": m["blunder"].map(num),
        "P(blunder in 5)": m["p_blunder_next5"].map(lambda v: f"{100 * v:.0f}%"),
        "flag ": m["flag_blunder_next5"],
        "was in 5": m["blunder_next5"].map(num),
    })
    print(t.to_string(index=False))
    real = m["blunder"].sum() if m["blunder"].notna().any() else None
    print(f"   blunders: model expected {m['p_blunder'].sum():.1f}, flagged {int(m['flag_blunder'].sum())} moves"
          + (f", real {int(real)}" if real is not None else ""))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pgn", type=Path, help="PGN file with one or more games")
    ap.add_argument("--out", type=Path, help="also write every move to this CSV")
    ap.add_argument("--quiet", action="store_true", help="do not print the per-move tables")
    a = ap.parse_args()
    if not a.pgn.exists():
        raise SystemExit(f"{a.pgn} not found")

    games, moves = build_tables(a.pgn, progress=False)
    if games.empty:
        raise SystemExit(f"no games found in {a.pgn}")
    done = []
    for _, g in games.iterrows():
        m = moves[moves["game_id"] == g["game_id"]]
        if g["speed"] not in SPEEDS:
            print(f"skipping {g['game_id']}: no model for {g['speed']} games", file=sys.stderr)
            continue
        if not g["has_clock"]:
            print(f"warning {g['game_id']}: no [%clk] clocks, so clock features are missing", file=sys.stderr)
        if not g["has_eval"]:
            print(f"warning {g['game_id']}: no [%eval] engine evals, so wp_self, abs_cp, last_swing and "
                  "prior_blunders_self are missing and the blunder chances are unreliable. Analyse the game "
                  "(Lichess computer analysis or Stockfish) and export it with evals", file=sys.stderr)
        m = m.join(predict_moves(bundles_for(g["speed"]), m))
        done.append(m)
        if not a.quiet:
            show(g, m)
    if a.out and done:
        out = pd.concat(done)[list(CSV_COLS.values())]
        out.columns = list(CSV_COLS)
        out.to_csv(a.out, index=False)
        print(f"\nwrote {len(out):,} moves from {len(done)} game{'s' if len(done) != 1 else ''} to {a.out}")


if __name__ == "__main__":
    main()
