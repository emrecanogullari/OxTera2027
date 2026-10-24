"""Fast regex parser for Lichess-database PGN.

Lichess dumps are machine-generated, so a regex tokenizer is ~20x faster than
python-chess and good enough. python-chess is only used later (features.py)
when we need the actual board.

Movetext looks like:
    1. e4 { [%eval 0.17] [%clk 0:03:00] } 1... c5?! { [%eval 0.55] [%clk 0:02:58] } ... 1-0
    - %clk  = mover's clock AFTER the move (h:mm:ss, whole seconds in most dumps)
    - %eval = Stockfish eval of the position AFTER the move, White's POV, pawns;
              '#-3' = mate in 3 for Black. Only ~6-10% of games are analysed.
"""
from __future__ import annotations

import math
import re
from typing import Iterable, Iterator, TextIO

from .config import SPEED_BOUNDS

HEADER_RE = re.compile(r'^\[(\w+)\s+"(.*)"\]\s*$')
TOKEN_RE = re.compile(
    r"\{(?P<comment>[^}]*)\}"
    r"|(?P<nag>\$\d+)"
    r"|(?P<moveno>\d+\.(?:\.\.)?)"
    r"|(?P<result>1-0|0-1|1/2-1/2|\*)"
    r"|(?P<san>[^\s{}]+)"
)
CLK_RE = re.compile(r"\[%clk\s+(\d+):(\d+):(\d+(?:\.\d+)?)\]")
EVAL_RE = re.compile(r"\[%eval\s+(#?)(-?\d+(?:\.\d+)?)")
SUFFIX_RE = re.compile(r"([?!]+)$")
NUMERIC_NAG = {"$1": "!", "$2": "?", "$3": "!!", "$4": "??", "$5": "!?", "$6": "?!"}


# --------------------------------------------------------------------------- #
# Splitting a PGN stream into games
# --------------------------------------------------------------------------- #
def iter_raw_games(lines: Iterable[str]) -> Iterator[tuple[dict, str, str]]:
    """Yield (headers, header_text, movetext) for each game in a line stream."""
    headers: dict = {}
    header_lines: list[str] = []
    move_lines: list[str] = []
    for line in lines:
        line = line.rstrip("\n")
        if line.startswith("["):
            if move_lines:  # a new game starts
                yield headers, "\n".join(header_lines), " ".join(move_lines)
                headers, header_lines, move_lines = {}, [], []
            m = HEADER_RE.match(line)
            if m:
                headers[m.group(1)] = m.group(2)
                header_lines.append(line)
        elif line.strip():
            move_lines.append(line.strip())
    if headers:
        yield headers, "\n".join(header_lines), " ".join(move_lines)


def read_pgn_file(fh: TextIO) -> Iterator[tuple[dict, str, str]]:
    return iter_raw_games(fh)


# --------------------------------------------------------------------------- #
# Header helpers
# --------------------------------------------------------------------------- #
def parse_time_control(tc: str) -> tuple[float, float]:
    """'180+2' -> (180, 2). '-' (correspondence) -> (nan, nan)."""
    if not tc or tc == "-" or "+" not in tc:
        return math.nan, math.nan
    base, inc = tc.split("+", 1)
    return float(base), float(inc)


def speed_of(base: float, inc: float) -> str:
    if math.isnan(base):
        return "correspondence"
    est = base + 40 * inc
    for bound, name in SPEED_BOUNDS:
        if est <= bound:
            return name
    return "classical"


def _int_or_nan(x: str | None) -> float:
    try:
        return int(x)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return math.nan


# --------------------------------------------------------------------------- #
# One game -> game row + ply rows
# --------------------------------------------------------------------------- #
def parse_game(headers: dict, movetext: str) -> tuple[dict, list[dict]]:
    site = headers.get("Site", "")
    game_id = site.rsplit("/", 1)[-1] if site else headers.get("GameId", "")
    base, inc = parse_time_control(headers.get("TimeControl", "-"))

    plies: list[dict] = []
    for m in TOKEN_RE.finditer(movetext):
        kind = m.lastgroup
        if kind == "san":
            tok = m.group("san")
            nag = ""
            sm = SUFFIX_RE.search(tok)
            if sm:
                nag, tok = sm.group(1), tok[: sm.start()]
            ply = len(plies) + 1
            plies.append({
                "game_id": game_id,
                "ply": ply,
                "color": "white" if ply % 2 else "black",
                "san": tok,
                "nag": nag,
                "clk_s": math.nan,
                "eval_cp": math.nan,   # White POV, centipawns
                "eval_mate": math.nan, # +n white mates in n, -n black mates
            })
        elif kind == "nag" and plies:
            plies[-1]["nag"] = NUMERIC_NAG.get(m.group("nag"), plies[-1]["nag"])
        elif kind == "comment" and plies:
            c = m.group("comment")
            cm = CLK_RE.search(c)
            if cm:
                h, mi, s = cm.groups()
                plies[-1]["clk_s"] = int(h) * 3600 + int(mi) * 60 + float(s)
            em = EVAL_RE.search(c)
            if em:
                if em.group(1) == "#":
                    plies[-1]["eval_mate"] = int(em.group(2))
                else:
                    plies[-1]["eval_cp"] = float(em.group(2)) * 100.0

    date = headers.get("UTCDate", headers.get("Date", "")).replace(".", "-")
    game = {
        "game_id": game_id,
        "utc": f"{date} {headers.get('UTCTime', '00:00:00')}",
        "event": headers.get("Event", ""),
        "white": headers.get("White", ""),
        "black": headers.get("Black", ""),
        "white_elo": _int_or_nan(headers.get("WhiteElo")),
        "black_elo": _int_or_nan(headers.get("BlackElo")),
        "result": headers.get("Result", "*"),
        "termination": headers.get("Termination", ""),
        "eco": headers.get("ECO", ""),
        "opening": headers.get("Opening", ""),
        "time_control": headers.get("TimeControl", "-"),
        "base_s": base,
        "inc_s": inc,
        "speed": speed_of(base, inc),
        "n_plies": len(plies),
        "has_clock": "%clk" in movetext,
        "has_eval": "%eval" in movetext,
    }
    return game, plies
