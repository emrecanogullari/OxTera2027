#!/usr/bin/env python3
"""Download Lichess monthly dump(s) and pipe PGN into the C++ ingest binary.

Downloads the .zst to disk with curl resume, then decompresses locally.
HTTP streaming mid-decompress cannot resume after a connection drop.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
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


def download_zst(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    # curl -C - resumes; -L follows redirects; --retry for transient drops.
    cmd = [
        "curl.exe",
        "-L",
        "--fail",
        "--retry",
        "5",
        "--retry-delay",
        "5",
        "-C",
        "-",
        "-o",
        str(dest),
        url,
    ]
    print(f"downloading {url} -> {dest}", file=sys.stderr, flush=True)
    subprocess.check_call(cmd)


def ingest_zst_file(zst_path: Path, out_dir: Path, max_games: int) -> None:
    print(f"decompress+ingest {zst_path}", file=sys.stderr, flush=True)
    with zst_path.open("rb") as handle:
        reader = zstd.ZstdDecompressor().stream_reader(handle)
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


def process_month(
    month: str,
    out_dir: Path,
    dumps_dir: Path,
    max_games: int,
    *,
    keep_dump: bool,
) -> Path:
    url = URL_TMPL.format(month=month)
    zst_path = dumps_dir / f"lichess_db_standard_rated_{month}.pgn.zst"
    month_dir = out_dir / "months" / month
    if (month_dir / "games.csv").is_file() and (month_dir / "moves.csv").is_file():
        # Allow manual skip only when a .done marker exists (full successful run).
        done = month_dir / ".done"
        if done.is_file():
            print(f"skip {month} (found {done})", file=sys.stderr, flush=True)
            return month_dir

    download_zst(url, zst_path)
    if month_dir.exists():
        shutil.rmtree(month_dir)
    ingest_zst_file(zst_path, month_dir, max_games)
    (month_dir / ".done").write_text("ok\n", encoding="utf-8")
    if not keep_dump:
        zst_path.unlink(missing_ok=True)
        print(f"removed {zst_path}", file=sys.stderr, flush=True)
    return month_dir


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
        "--dumps-dir",
        type=Path,
        default=None,
        help="Where to store .zst downloads (default: out-dir/dumps)",
    )
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
    parser.add_argument(
        "--keep-dumps",
        action="store_true",
        help="Keep downloaded .zst files after ingest",
    )
    args = parser.parse_args()
    dumps_dir = args.dumps_dir or (args.out_dir / "dumps")

    if args.url:
        # One-off URL: download name from URL basename.
        name = args.url.rstrip("/").split("/")[-1]
        zst_path = dumps_dir / name
        download_zst(args.url, zst_path)
        ingest_zst_file(zst_path, args.out_dir, args.max_games)
        if not args.keep_dumps:
            zst_path.unlink(missing_ok=True)
        return 0

    months = [m.strip() for m in args.months.split(",") if m.strip()]
    if not months:
        raise SystemExit("no months given")

    month_dirs: list[Path] = []
    for month in months:
        month_dirs.append(
            process_month(
                month,
                args.out_dir,
                dumps_dir,
                args.max_games,
                keep_dump=args.keep_dumps,
            )
        )

    if len(month_dirs) == 1:
        for name in ("games.csv", "moves.csv"):
            src = month_dirs[0] / name
            dest = args.out_dir / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dest)
    else:
        merge_month_dirs(month_dirs, args.out_dir)

    if not args.keep_month_dirs:
        month_root = args.out_dir / "months"
        if month_root.exists():
            shutil.rmtree(month_root)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
