#!/usr/bin/env python3
"""Download a Lichess monthly dump and pipe PGN into the C++ ingest binary."""

from __future__ import annotations

import argparse
import subprocess
import sys
import urllib.request
from pathlib import Path

import zstandard as zstd

DEFAULT_URL = (
    "https://database.lichess.org/standard/lichess_db_standard_rated_2026-09.pgn.zst"
)


def ingest_binary() -> Path:
    build = Path(__file__).resolve().parent / "cpp" / "build"
    for name in ("ingest.exe", "ingest"):
        path = build / name
        if path.is_file():
            return path
    raise SystemExit(
        "C++ ingest not built. From Peter/ingest/cpp run: powershell -File compile.ps1"
    )


def run_ingest(pgn_bytes_src, out_dir: Path, max_games: int) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [str(ingest_binary()), "--out-dir", str(out_dir)]
    if max_games:
        cmd.extend(["--max-games", str(max_games)])
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    assert proc.stdin is not None
    try:
        while True:
            chunk = pgn_bytes_src.read(1024 * 1024)
            if not chunk:
                break
            proc.stdin.write(chunk)
    finally:
        proc.stdin.close()
    code = proc.wait()
    if code != 0:
        raise SystemExit(code)


def stream_url(url: str, out_dir: Path, max_games: int) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "OxTera2027-ingest"})
    print(f"streaming {url}", file=sys.stderr, flush=True)
    with urllib.request.urlopen(request, timeout=60) as response:
        reader = zstd.ZstdDecompressor().stream_reader(response)
        run_ingest(reader, out_dir, max_games)


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
