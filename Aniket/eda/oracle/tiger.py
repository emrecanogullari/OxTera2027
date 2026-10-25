"""Peter's Tiger Cloud database: rated blitz games with Stockfish's top moves for every position.

Service db-44476 (TimescaleDB / Postgres), read through the Tiger CLI, so no password passes through this code:
log in once with `tiger auth login`, then `tiger db save-password db-44476`. Tables used (Peter/database_work/):
  games           ratings, time control, result
  moves           SAN, clock and Lichess eval AFTER each move
  best_next_move  Stockfish 19, MultiPV 4, depth 12, on the position BEFORE each move (fen_before): the best and
                  2nd-best move with their win%, the gap, and how many of the 4 lines are within 5 win% of the best

The games are rebuilt as Lichess-style PGN and go through our own feature code (features.build_tables), so the
23 features and 3 labels mean exactly what FEATURE_SET.md says. The Stockfish features are joined on
(game_id, ply). They all describe the position before the move: nothing about the move that was played.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

from .config import CP_CAP, WC_K
from .features import win_pct

SERVICE = "db-44476"
MATE_CP = 10000  # how the database stores a mate score
NUMERIC_TYPES = {"int2", "int4", "int8", "float4", "float8", "numeric"}

SF_FEATURES = {
    "sf_best_wp": ("stockfish", "Stockfish's best move: my win% (depth 12)"),
    "sf_gap": ("stockfish", "win% gap: Stockfish's best move minus its 2nd best"),
    "sf_n_near_best": ("stockfish", "of Stockfish's top 4 moves, how many are within 5 win% of the best"),
    "sf_vs_lichess": ("stockfish", "|Stockfish win% - Lichess win%| for this position: how unsure the eval is"),
    "sf_best_capture": ("stockfish", "1 if Stockfish's best move is a capture"),
    "sf_best_check": ("stockfish", "1 if Stockfish's best move gives check"),
}


# --------------------------------------------------------------------------- #
# reading the database
def tiger_cli() -> str:
    for p in (os.environ.get("TIGER"), shutil.which("tiger"), str(Path.home() / ".local" / "bin" / "tiger")):
        if p and Path(p).exists():
            return p
    raise SystemExit("Tiger CLI not found. Install it (curl -fsSL https://cli.tigerdata.com | sh), then run "
                     f"`tiger auth login` and `tiger db save-password {SERVICE}`.")


def _redact(text: str) -> str:
    return re.sub(r"(postgres(?:ql)?://[^:/\s]+:)[^@\s]+@", r"\1***@", text)


def query(sql: str) -> pd.DataFrame:
    """One SELECT on the database, as a DataFrame. Read-only session: nothing here can write to the database."""
    cmd = [tiger_cli(), "db", "query", SERVICE, "--read-only", "-o", "json", "--timeout", "15m",
           "--version-check=false", "--color=false", "--analytics=false", "-c", sql]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=1000)
    if r.returncode != 0:
        raise SystemExit(f"tiger db query failed ({r.returncode}):\n{_redact(r.stderr or r.stdout).strip()}")
    # {"result_sets": [{"columns": [{"name", "type"}], "rows": [[...]]}]}, every value as text, NULL as null
    rs = json.loads(r.stdout)["result_sets"][-1]
    df = pd.DataFrame(rs["rows"], columns=[c["name"] for c in rs["columns"]])
    for c in rs["columns"]:
        if c["type"] in NUMERIC_TYPES:
            df[c["name"]] = pd.to_numeric(df[c["name"]])
        elif c["type"] == "bool":
            df[c["name"]] = df[c["name"]].map({"t": True, "f": False})
    return df


# --------------------------------------------------------------------------- #
# database rows -> Lichess PGN, so features.build_tables computes our features from them
def _clock(s: float) -> str:
    h, rest = divmod(float(s), 3600)
    mi, sec = divmod(rest, 60)
    return f"{int(h)}:{int(mi):02d}:" + (f"{int(sec):02d}" if sec.is_integer() else f"{sec:05.2f}")


def _eval(cp: int, is_mate: bool) -> str:
    # the database keeps only a mate's sign (+-10000); our features only use the sign too (win% 0 or 100)
    return ("#1" if cp > 0 else "#-1") if is_mate else f"{cp / 100:.2f}"


def to_pgn(games: pd.DataFrame, moves: pd.DataFrame) -> str:
    """Lichess-style PGN: headers, then SAN with { [%eval ..] [%clk ..] } after every move."""
    g = games.set_index("game_id")
    out = []
    for gid, mv in moves.sort_values(["game_id", "ply"]).groupby("game_id", sort=False):
        r = g.loc[gid]
        out += ['[Event "Rated Blitz game"]', f'[Site "https://lichess.org/{gid}"]',
                f'[UTCDate "{pd.Timestamp(r["utc_date"]):%Y.%m.%d}"]', f'[Result "{r["result"]}"]',
                f'[WhiteElo "{r["white_elo"]}"]', f'[BlackElo "{r["black_elo"]}"]',
                f'[TimeControl "{r["base"]}+{r["inc"]}"]', f'[Termination "{r["termination"]}"]', ""]
        toks = []
        for ply, san, clk, cp, mate in zip(mv["ply"], mv["san"], mv["clk_after_s"], mv["eval_cp"], mv["is_mate"]):
            toks.append(f"{(ply + 1) // 2}." if ply % 2 else f"{ply // 2}...")
            toks.append(f"{san} {{ [%eval {_eval(cp, mate)}] [%clk {_clock(clk)}] }}")
        out += [" ".join(toks + [r["result"]]), ""]
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------- #
# Stockfish features
def lichess_scale(wp: pd.Series) -> pd.Series:
    """A database win% (no cap, mate = +-10000 cp) put on our Lichess-eval scale (cap +-1000 cp, mate 0/100),
    so Stockfish and Lichess evals of the same position can be compared."""
    x = ((wp - 50) / 50).clip(-1 + 1e-15, 1 - 1e-15)
    cp = np.log((1 + x) / (1 - x)) / WC_K
    mate = cp.abs() >= MATE_CP * 0.9
    return pd.Series(win_pct(cp.clip(-CP_CAP, CP_CAP), np.where(mate, np.sign(cp), np.nan)), index=wp.index)


def _best_move_kind(fen: str, uci: str) -> tuple[float, float]:
    import chess
    if not isinstance(fen, str) or not isinstance(uci, str):
        return np.nan, np.nan
    board = chess.Board(fen)
    mv = chess.Move.from_uci(uci)
    return float(board.is_capture(mv)), float(board.gives_check(mv))


def add_stockfish(m: pd.DataFrame, bnm: pd.DataFrame) -> pd.DataFrame:
    """Join best_next_move onto our move table and derive the sf_* features."""
    b = bnm.rename(columns={"best_possible_move_wp": "sf_best_wp", "gap": "sf_gap", "n_near_best": "sf_n_near_best"})
    m = m.merge(b[["game_id", "ply", "fen_before", "best_possible_move", "second_best_move", "second_best_move_wp",
                   "sf_best_wp", "sf_gap", "sf_n_near_best", "n_legal_moves"]], on=["game_id", "ply"], how="left")
    m["sf_vs_lichess"] = (lichess_scale(m["sf_best_wp"]) - m["wp_self"]).abs()
    kinds = [_best_move_kind(f, u) for f, u in zip(m["fen_before"], m["best_possible_move"])]
    m["sf_best_capture"], m["sf_best_check"] = (np.array(k, float) for k in zip(*kinds))
    for c in SF_FEATURES:
        m[c] = m[c].astype(float)
    return m
