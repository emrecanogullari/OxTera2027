#!/usr/bin/env python3
"""Download Lichess monthly dump(s) and pipe PGN into the C++ ingest binary."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

import zstandard as zstd

URL_TMPL = (
    "https://database.lichess.org/standard/lichess_db_standard_rated_{month}.pgn.zst"
)
DEFAULT_MONTHS = ("2026-08", "2026-09")


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
    with urllib.request.urlopen(request, timeout=120) as response:
        reader = zstd.ZstdDecompressor().stream_reader(response)
        run_ingest(reader, out_dir, max_games)


def append_csv(src: Path, dest: Path, *, write_header: bool) -> None:
    with src.open("r", encoding="utf-8", newline="") as hin, dest.open(
        "a" if dest.exists() and not write_header else "w",
        encoding="utf-8",
        newline="",
    ) as hout:
        header = hin.readline()
        if write_header:
            hout.write(header)
        shutil.copyfileobj(hin, hout)


def merge_month_dirs(month_dirs: list[Path], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in ("games.csv", "moves.csv"):
        dest = out_dir / name
        if dest.exists():
            dest.unlink()
        first = True
        for month_dir in month_dirs:
            src = month_dir / name
            if not src.is_file():
                raise SystemExit(f"missing {src}")
            append_csv(src, dest, write_header=first)
            first = False
        print(f"merged {dest}", file=sys.stderr, flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--months",
        default=",".join(DEFAULT_MONTHS),
        help="Comma-separated YYYY-MM months (default: 2026-08,2026-09)",
    )
    parser.add_argument("--url", default=None, help="Single dump URL (overrides --months)")
    parser.add_argument("--out-dir", type=Path, default=Path("data"))
    parser.add_argument(
        "--max-games",
        type=int,
        default=0,
        help="Stop after N kept games per month (0 = full month)",
    )
    parser.add_argument(
        "--keep-month-dirs",
        action="store_true",
        help="Keep per-month CSV folders under out-dir/months/",
    )
    args = parser.parse_args()

    if args.url:
        stream_url(args.url, args.out_dir, args.max_games)
        return 0

    months = [m.strip() for m in args.months.split(",") if m.strip()]
    if not months:
        raise SystemExit("no months given")

    month_root = args.out_dir / "months"
    month_dirs: list[Path] = []
    for month in months:
        month_dir = month_root / month
        stream_url(URL_TMPL.format(month=month), month_dir, args.max_games)
        month_dirs.append(month_dir)

    if len(month_dirs) == 1:
        for name in ("games.csv", "moves.csv"):
            src = month_dirs[0] / name
            dest = args.out_dir / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dest)
    else:
        merge_month_dirs(month_dirs, args.out_dir)

    if not args.keep_month_dirs and month_root.exists():
        shutil.rmtree(month_root)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
