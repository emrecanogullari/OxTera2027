#!/usr/bin/env python3
"""Reference Python parser for unit tests.

Live ingest is the C++ binary in ingest/cpp (see ingest/cpp/README.md):

    zstd -dc dump.pgn.zst | ingest/cpp/build/ingest.exe --out-dir data --max-games 200
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, TextIO

KEEP_EVENTS = frozenset({"Rated Blitz game"})
KEEP_TIME_CONTROLS = frozenset({"180+0", "300+0"})
KEEP_TERMINATIONS = frozenset({"Normal"})
ELO_MIN = 1000
ELO_MAX = 2200
MATE_CP = 10000

HEADER_RE = re.compile(r'^\[(\w+)\s+"(.*)"\]\s*$')
EVAL_RE = re.compile(r"\[%eval\s+([^\]]+)\]")
CLK_RE = re.compile(r"\[%clk\s+([^\]]+)\]")
SITE_ID_RE = re.compile(r"lichess\.org/([A-Za-z0-9]+)")
TIME_CONTROL_RE = re.compile(r"^(\d+)\+(\d+)$")
MOVE_NUMBER_RE = re.compile(r"^\d+\.+$")
NAG_RE = re.compile(r"^\$\d+$")
RESULT_TOKENS = frozenset({"1-0", "0-1", "1/2-1/2", "*"})
MATE_RE = re.compile(r"^#(-?\d+)$")


@dataclass(frozen=True)
class GameRow:
    game_id: str
    white_elo: int
    black_elo: int
    base: int
    inc: int
    result: str
    termination: str
    utc_date: str


@dataclass(frozen=True)
class MoveRow:
    game_id: str
    ply: int
    color: str
    san: str
    clk_after_s: float
    eval_cp: int
    is_mate: bool


def tag_dict(header_text: str) -> dict[str, str]:
    tags: dict[str, str] = {}
    for line in header_text.splitlines():
        match = HEADER_RE.match(line.strip())
        if match:
            tags[match.group(1)] = match.group(2)
    return tags


def game_id_from_site(site: str) -> str | None:
    match = SITE_ID_RE.search(site)
    return match.group(1) if match else None


def parse_elo(value: str | None) -> int | None:
    if value is None or value in {"", "?"}:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def parse_time_control(value: str) -> tuple[int, int] | None:
    match = TIME_CONTROL_RE.match(value)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def parse_utc_date(value: str | None) -> str | None:
    if not value or value.startswith("?"):
        return None
    return value.replace(".", "-")


def parse_clock(value: str) -> float | None:
    parts = value.strip().split(":")
    try:
        nums = [float(p) for p in parts]
    except ValueError:
        return None
    if len(nums) == 3:
        hours, minutes, seconds = nums
        return hours * 3600 + minutes * 60 + seconds
    if len(nums) == 2:
        minutes, seconds = nums
        return minutes * 60 + seconds
    if len(nums) == 1:
        return nums[0]
    return None


def parse_eval(value: str) -> tuple[int, bool] | None:
    token = value.strip()
    mate = MATE_RE.match(token)
    if mate:
        n = int(mate.group(1))
        if n == 0:
            return None
        sign = 1 if n > 0 else -1
        return sign * MATE_CP, True
    try:
        return int(round(float(token) * 100)), False
    except ValueError:
        return None


def iter_tokens(movetext: str) -> Iterator[tuple[str, str]]:
    i = 0
    n = len(movetext)
    while i < n:
        while i < n and movetext[i].isspace():
            i += 1
        if i >= n:
            break
        ch = movetext[i]
        if ch == "{":
            depth = 1
            i += 1
            start = i
            while i < n and depth:
                if movetext[i] == "{":
                    depth += 1
                elif movetext[i] == "}":
                    depth -= 1
                    if depth == 0:
                        break
                i += 1
            yield ("comment", movetext[start:i])
            i += 1
            continue
        if ch == "(":
            depth = 1
            i += 1
            while i < n and depth:
                if movetext[i] == "(":
                    depth += 1
                elif movetext[i] == ")":
                    depth -= 1
                elif movetext[i] == "{":
                    end = movetext.find("}", i)
                    i = n if end < 0 else end
                i += 1
            continue
        if ch == ";":
            end = movetext.find("\n", i)
            i = n if end < 0 else end + 1
            continue
        start = i
        while i < n and not movetext[i].isspace() and movetext[i] not in "{}()":
            i += 1
        yield ("token", movetext[start:i])


def parse_moves(game_id: str, movetext: str) -> list[MoveRow]:
    rows: list[MoveRow] = []
    pending_san: str | None = None
    ply = 0

    def flush(comment: str) -> None:
        nonlocal pending_san, ply
        if pending_san is None:
            return
        eval_match = EVAL_RE.search(comment)
        clk_match = CLK_RE.search(comment)
        pending_san = None
        if not eval_match or not clk_match:
            return
        parsed_eval = parse_eval(eval_match.group(1))
        clk = parse_clock(clk_match.group(1))
        if parsed_eval is None or clk is None:
            return
        eval_cp, is_mate = parsed_eval
        ply += 1
        rows.append(
            MoveRow(
                game_id=game_id,
                ply=ply,
                color="w" if ply % 2 == 1 else "b",
                san=san,
                clk_after_s=clk,
                eval_cp=eval_cp,
                is_mate=is_mate,
            )
        )

    san = ""
    for kind, value in iter_tokens(movetext):
        if kind == "comment":
            flush(value)
            continue
        token = value.strip()
        if not token or MOVE_NUMBER_RE.match(token) or NAG_RE.match(token):
            continue
        if token in RESULT_TOKENS:
            break
        pending_san = token.rstrip("?!").rstrip()
        san = pending_san
    return rows


def keep_headers(tags: dict[str, str]) -> GameRow | None:
    """Cheap filters from PGN tags only — skip movetext parse for most games."""
    if tags.get("Event") not in KEEP_EVENTS:
        return None
    if tags.get("Termination") not in KEEP_TERMINATIONS:
        return None
    time_control = tags.get("TimeControl", "")
    if time_control not in KEEP_TIME_CONTROLS:
        return None
    parsed_tc = parse_time_control(time_control)
    if parsed_tc is None:
        return None
    white_elo = parse_elo(tags.get("WhiteElo"))
    black_elo = parse_elo(tags.get("BlackElo"))
    if white_elo is None or black_elo is None:
        return None
    if not (ELO_MIN <= white_elo <= ELO_MAX and ELO_MIN <= black_elo <= ELO_MAX):
        return None
    game_id = game_id_from_site(tags.get("Site", ""))
    utc_date = parse_utc_date(tags.get("UTCDate") or tags.get("Date"))
    result = tags.get("Result")
    if not game_id or not utc_date or not result:
        return None
    base, inc = parsed_tc
    return GameRow(
        game_id=game_id,
        white_elo=white_elo,
        black_elo=black_elo,
        base=base,
        inc=inc,
        result=result,
        termination=tags["Termination"],
        utc_date=utc_date,
    )


def keep_game(tags: dict[str, str], movetext: str) -> GameRow | None:
    game = keep_headers(tags)
    if game is None:
        return None
    if "[%eval" not in movetext or "[%clk" not in movetext:
        return None
    return game


def iter_games(stream: TextIO) -> Iterator[tuple[str, str]]:
    header_lines: list[str] = []
    move_lines: list[str] = []
    in_moves = False

    def emit() -> tuple[str, str] | None:
        if not header_lines:
            return None
        return "\n".join(header_lines), "\n".join(move_lines)

    for raw in stream:
        line = raw.rstrip("\n")
        stripped = line.strip()
        if not stripped:
            if in_moves:
                game = emit()
                if game:
                    yield game
                header_lines = []
                move_lines = []
                in_moves = False
            elif header_lines:
                in_moves = True
            continue
        if stripped.startswith("[") and not in_moves:
            header_lines.append(stripped)
            continue
        in_moves = True
        move_lines.append(stripped)

    game = emit()
    if game:
        yield game


def iter_kept(
    stream: TextIO,
    *,
    max_games: int | None = None,
    max_seen: int | None = None,
    skip_ids: set[str] | None = None,
) -> Iterator[tuple[GameRow, list[MoveRow], dict[str, int]]]:
    """Yield kept games one at a time. Header filters run before movetext parse."""
    skip_ids = skip_ids or set()
    seen_ids: set[str] = set()
    stats = {
        "seen": 0,
        "kept": 0,
        "dupes": 0,
        "no_moves": 0,
        "filtered": 0,
        "skipped_existing": 0,
        "moves": 0,
    }

    for header_text, movetext in iter_games(stream):
        stats["seen"] += 1
        if stats["seen"] % 2000 == 0:
            print(
                f"progress seen={stats['seen']} kept={stats['kept']} filtered={stats['filtered']}",
                file=sys.stderr,
                flush=True,
            )
        if max_seen is not None and stats["seen"] > max_seen:
            break
        tags = tag_dict(header_text)
        game = keep_headers(tags)
        if game is None:
            stats["filtered"] += 1
            continue
        if game.game_id in skip_ids:
            stats["skipped_existing"] += 1
            continue
        if game.game_id in seen_ids:
            stats["dupes"] += 1
            continue
        if "[%eval" not in movetext or "[%clk" not in movetext:
            stats["filtered"] += 1
            continue
        move_rows = parse_moves(game.game_id, movetext)
        if not move_rows:
            stats["no_moves"] += 1
            continue
        seen_ids.add(game.game_id)
        stats["kept"] += 1
        stats["moves"] += len(move_rows)
        yield game, move_rows, stats
        if max_games is not None and stats["kept"] >= max_games:
            break


def ingest(
    stream: TextIO,
    *,
    max_games: int | None = None,
    max_seen: int | None = None,
    skip_ids: set[str] | None = None,
) -> tuple[list[GameRow], list[MoveRow], dict[str, int]]:
    games: list[GameRow] = []
    moves: list[MoveRow] = []
    stats = {
        "seen": 0,
        "kept": 0,
        "dupes": 0,
        "no_moves": 0,
        "filtered": 0,
        "skipped_existing": 0,
        "moves": 0,
    }
    for game, move_rows, stats in iter_kept(
        stream, max_games=max_games, max_seen=max_seen, skip_ids=skip_ids
    ):
        games.append(game)
        moves.extend(move_rows)
    return games, moves, stats


def write_csv(out_dir: Path, games: Iterable[GameRow], moves: Iterable[MoveRow]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    games_path = out_dir / "games.csv"
    moves_path = out_dir / "moves.csv"
    with games_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "game_id",
                "white_elo",
                "black_elo",
                "base",
                "inc",
                "result",
                "termination",
                "utc_date",
            ]
        )
        for game in games:
            writer.writerow(
                [
                    game.game_id,
                    game.white_elo,
                    game.black_elo,
                    game.base,
                    game.inc,
                    game.result,
                    game.termination,
                    game.utc_date,
                ]
            )
    with moves_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["game_id", "ply", "color", "san", "clk_after_s", "eval_cp", "is_mate"]
        )
        for move in moves:
            writer.writerow(
                [
                    move.game_id,
                    move.ply,
                    move.color,
                    move.san,
                    f"{move.clk_after_s:.3f}",
                    move.eval_cp,
                    "t" if move.is_mate else "f",
                ]
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Filter a Lichess PGN stream to CSV.")
    parser.add_argument("--out-dir", type=Path, default=Path("data"))
    parser.add_argument("--max-games", type=int, default=None, help="Stop after this many kept games.")
    parser.add_argument("--max-seen", type=int, default=None, help="Stop after this many raw games.")
    args = parser.parse_args(argv)

    games, moves, stats = ingest(
        sys.stdin,
        max_games=args.max_games,
        max_seen=args.max_seen,
    )
    write_csv(args.out_dir, games, moves)
    print(
        f"seen={stats['seen']} kept={stats['kept']} moves={len(moves)} "
        f"filtered={stats['filtered']} dupes={stats['dupes']} no_moves={stats['no_moves']}",
        file=sys.stderr,
    )
    print(f"wrote {args.out_dir / 'games.csv'} and {args.out_dir / 'moves.csv'}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
