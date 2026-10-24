"""Step 1: stream one Lichess month and keep N analysed games per speed.

  python scripts/1_fetch.py                    # 20k each of bullet, blitz, classical -> data/<speed>/games.pgn
  python scripts/1_fetch.py --n 2000           # quick sample
  python scripts/1_fetch.py --source path/to/lichess_db_standard_rated_2026-09.pgn.zst

Only games with clocks AND engine evals are kept (blunder labels need evals).
Classical is the bottleneck (~1 analysed game per 600 scanned): ~12M games for 20k.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from oracle.config import DATA, DEFAULT_MONTH, EVERY, LICHESS_URL, SPEEDS  # noqa: E402
from oracle.fetch import fetch_by_speed  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--month", default=DEFAULT_MONTH, help="YYYY-MM of the monthly dump")
    ap.add_argument("--source", help="URL or local .pgn/.pgn.zst (overrides --month)")
    ap.add_argument("--n", type=int, default=20000, help="games to keep per speed")
    a = ap.parse_args()

    source = a.source or LICHESS_URL.format(month=a.month)
    print(f"source : {source}\nkeep   : {a.n:,} analysed games each of {', '.join(SPEEDS)} (every-k: {EVERY})")
    st = fetch_by_speed(source, DATA, a.n, SPEEDS, every=EVERY)
    print(f"\nscanned {st.scanned:,} games in {st.seconds / 60:.1f} min")
    for s, k in st.kept.items():
        print(f"  {s:10s} {k:,} -> {DATA / s / 'games.pgn'}" + ("   WARNING: fewer than --n" if k < a.n else ""))


if __name__ == "__main__":
    main()
