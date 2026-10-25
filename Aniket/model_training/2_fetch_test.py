"""Step 2: pull fresh TEST games and label them with the same code as the training data.

  python 2_fetch_test.py              # 100 analysed games per speed -> test_data/<speed>/

Training games came from the first 1,122,353 games of the 2026-09 dump. We skip the first
1.5M games (test games are a few hours later), keep games with the same filter and the same
every-k thinning as training, drop any game id seen in training, and build the feature/label
tables with the EDA's own build_tables().
"""
import argparse
import itertools
import time

from config import SPEEDS, TEST_DATA, TEST_GAMES, TEST_SKIP, TRAIN_DATA

import pandas as pd
from oracle.config import DEFAULT_MONTH, EVERY, LICHESS_URL
from oracle.features import build_tables
from oracle.fetch import GameFilter, open_text_stream
from oracle.pgn import iter_raw_games, parse_time_control, speed_of


def skip_games(lines, n: int):
    """Advance a PGN line stream past its first n games (cheap: no parsing)."""
    seen = 0
    for line in lines:
        if line.startswith("[Event "):
            seen += 1
            if seen > n:
                return itertools.chain([line], lines)
    return iter(())


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=TEST_GAMES, help="test games per speed")
    ap.add_argument("--skip", type=int, default=TEST_SKIP, help="games to skip at the start of the month")
    a = ap.parse_args()

    train_ids = set().union(*(set(pd.read_parquet(TRAIN_DATA / s / "games.parquet", columns=["game_id"])["game_id"])
                              for s in SPEEDS))
    flt = GameFilter()
    kept = {s: [] for s in SPEEDS}
    matched = {s: 0 for s in SPEEDS}
    t0 = time.time()
    source = LICHESS_URL.format(month=DEFAULT_MONTH)
    print(f"source: {source}\nskipping the first {a.skip:,} games ...")
    raw = open_text_stream(source)
    lines = skip_games(raw, a.skip)
    print(f"skipped in {time.time() - t0:.0f}s; collecting {a.n} games per speed")
    scanned = 0
    for headers, header_text, movetext in iter_raw_games(lines):
        scanned += 1
        s = speed_of(*parse_time_control(headers.get("TimeControl", "-")))
        if s not in kept or len(kept[s]) >= a.n or not flt.keep(headers, movetext):
            continue
        if headers.get("Site", "").rsplit("/", 1)[-1] in train_ids:
            continue
        matched[s] += 1
        if (matched[s] - 1) % EVERY[s]:
            continue
        kept[s].append(header_text + "\n\n" + movetext + "\n\n")
        if all(len(v) >= a.n for v in kept.values()):
            break
    raw.close()
    print(f"scanned {scanned:,} more games in {time.time() - t0:.0f}s total")

    for s in SPEEDS:
        out = TEST_DATA / s
        out.mkdir(parents=True, exist_ok=True)
        (out / "games.pgn").write_text("".join(kept[s]), encoding="utf-8")
        games, moves = build_tables(out / "games.pgn", progress=False)
        games.to_parquet(out / "games.parquet", index=False)
        moves.to_parquet(out / "moves.parquet", index=False)
        overlap = len(set(games["game_id"]) & train_ids)
        print(f"  {s:10s} {len(games)} games, {len(moves):,} moves, {moves['blunder'].notna().sum():,} labelled, "
              f"{games['utc'].min()} -> {games['utc'].max()}, overlap with training: {overlap}")


if __name__ == "__main__":
    main()
