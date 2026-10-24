"""Step 2: parse data/<speed>/games.pgn into games.parquet (1 row/game) + moves.parquet (1 row/move).

  python scripts/2_build.py                  # all three speeds, in parallel (~10 min: board replay is slow)
  python scripts/2_build.py --speed classical --limit 500
"""
import argparse
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from oracle.config import DATA, SPEEDS  # noqa: E402
from oracle.features import build_tables  # noqa: E402


def build(speed: str, limit: int | None, progress: bool) -> str:
    games, moves = build_tables(DATA / speed / "games.pgn", limit=limit, progress=progress)
    games.to_parquet(DATA / speed / "games.parquet", index=False)
    moves.to_parquet(DATA / speed / "moves.parquet", index=False)
    lab = moves["blunder"].notna()
    return (f"{speed:10s} {len(games):,} games, {len(moves):,} moves, {lab.sum():,} labelled, "
            f"blunder rate {moves.loc[lab, 'blunder'].mean():.2%}, median think {moves['time_spent'].median():.0f}s")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--speed", choices=SPEEDS, action="append", help="default: all")
    ap.add_argument("--limit", type=int, help="parse only the first N games per speed")
    a = ap.parse_args()
    speeds = a.speed or list(SPEEDS)
    if len(speeds) == 1:
        print(build(speeds[0], a.limit, True))
        return
    with ProcessPoolExecutor(len(speeds)) as ex:
        for line in ex.map(build, speeds, [a.limit] * len(speeds), [False] * len(speeds)):
            print(line)


if __name__ == "__main__":
    main()
