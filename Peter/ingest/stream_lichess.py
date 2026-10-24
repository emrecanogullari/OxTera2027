#!/usr/bin/env python3
"""Download a Lichess monthly dump as a zstd stream and keep N matching games."""

from __future__ import annotations

import argparse
import io
import sys
import urllib.request
from pathlib import Path

import zstandard as zstd

from ingest.ingest import ingest, write_csv

DEFAULT_URL = (
    "https://database.lichess.org/standard/lichess_db_standard_rated_2026-09.pgn.zst"
)


def stream_url(url: str, out_dir: Path, max_games: int) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "OxTera2027-ingest"})
    print(f"streaming {url}", file=sys.stderr, flush=True)
    with urllib.request.urlopen(request, timeout=60) as response:
        reader = zstd.ZstdDecompressor().stream_reader(response)
        text = io.TextIOWrapper(reader, encoding="utf-8", errors="replace")
        games, moves, stats = ingest(text, max_games=max_games)
    write_csv(out_dir, games, moves)
    print(
        f"seen={stats['seen']} kept={stats['kept']} moves={len(moves)} "
        f"filtered={stats['filtered']} dupes={stats['dupes']} no_moves={stats['no_moves']}",
        file=sys.stderr,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--out-dir", type=Path, default=Path("data"))
    parser.add_argument("--max-games", type=int, default=1000)
    args = parser.parse_args()
    stream_url(args.url, args.out_dir, args.max_games)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
