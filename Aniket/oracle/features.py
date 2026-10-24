"""PGN games -> games table + one row per move (features known BEFORE the move, labels after).

One row = one moment where a player is about to move.

    clock_self ──(think: time_spent)──► move ──► clk_after (= clock_self - spent + inc)
    wp_self  = mover's win% BEFORE the move (eval after previous ply)
    wp_after = mover's win% AFTER the move
    wp_drop  = wp_self - wp_after  ──►  blunder if >= 20 points

THE GOLDEN RULE (no peeking): FEATURE_COLS are all known before the move.
LABEL_COLS use the future and must never be model inputs.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .config import BLUNDER_PTS, CP_CAP, WC_K
from .pgn import parse_game, read_pgn_file

PIECE_VALUES = {1: 1, 2: 3, 3: 3, 4: 5, 5: 9}  # pawn..queen (python-chess piece types)

# feature -> (group, meaning)
FEATURES = {
    "clock_self": ("clock", "seconds on my clock as I start thinking"),
    "clock_opp": ("clock", "seconds on opponent's clock"),
    "clock_ratio": ("clock", "clock_self / clock_opp"),
    "frac_self": ("clock", "clock_self / starting time (NaN for 0+k games)"),
    "prev_self_spent": ("clock", "my think time on my previous move"),
    "avg_self_spent": ("clock", "my average think time so far this game"),
    "prev_opp_spent": ("clock", "opponent's think time on their last move"),
    "elo_self": ("players", "my rating"),
    "elo_opp": ("players", "opponent's rating"),
    "elo_diff": ("players", "elo_self - elo_opp"),
    "base": ("context", "starting time (s)"),
    "inc": ("context", "increment (s)"),
    "ply": ("context", "half-move number"),
    "n_legal": ("position", "number of legal moves (complexity)"),
    "in_check": ("position", "1 if I am in check"),
    "n_captures": ("position", "legal captures available"),
    "n_checks": ("position", "legal checks available"),
    "mat_total": ("position", "total material on the board (game phase)"),
    "mat_diff": ("position", "my material - opponent's (P=1 N=B=3 R=5 Q=9)"),
    "wp_self": ("engine", "my engine win% before the move"),
    "abs_cp": ("engine", "absolute eval in centipawns (how decided the game is)"),
    "last_swing": ("engine", "win% my opponent gave away on their last move"),
    "prior_blunders_self": ("engine", "my blunders so far this game"),
}
FEATURE_COLS = list(FEATURES)
LABEL_COLS = ["time_spent", "blunder", "blunder_next5"]   # + helpers clk_after, wp_after, wp_drop


# --------------------------------------------------------------------------- #
def load_pgn(path: Path, limit: int | None = None, progress: bool = True) -> tuple[pd.DataFrame, pd.DataFrame]:
    games, plies = [], []
    with open(path, encoding="utf-8") as fh:
        it = read_pgn_file(fh)
        if progress:
            try:
                from tqdm import tqdm
                it = tqdm(it, unit="game", desc="parse")
            except ImportError:
                pass
        for i, (headers, _, movetext) in enumerate(it):
            if limit and i >= limit:
                break
            g, p = parse_game(headers, movetext)
            games.append(g)
            plies.extend(p)
    gdf = pd.DataFrame(games)
    mdf = pd.DataFrame(plies)
    gdf["utc"] = pd.to_datetime(gdf["utc"], errors="coerce")
    return gdf, mdf


# --------------------------------------------------------------------------- #
def win_pct(cp, mate=None):
    """Lichess win% (0-100) from White's POV. Works on scalars or Series."""
    cp = np.clip(cp, -CP_CAP, CP_CAP)
    wp = 50.0 + 50.0 * (2.0 / (1.0 + np.exp(-WC_K * cp)) - 1.0)
    if mate is not None:
        wp = np.where(pd.isna(mate), wp, np.where(np.asarray(mate) > 0, 100.0, 0.0))
    return wp


def add_clock_features(moves: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    m = moves.merge(games[["game_id", "base_s", "inc_s"]], on="game_id", how="left")
    m = m.rename(columns={"base_s": "base", "inc_s": "inc", "clk_s": "clk_after"})
    m = m.sort_values(["game_id", "ply"], kind="stable").reset_index(drop=True)

    side = m.groupby(["game_id", "color"], sort=False)
    prev_same = side["clk_after"].shift(1)
    first_clk = side["clk_after"].transform("first")
    # Berserk (arenas): player starts on half the base clock and gets no increment.
    m["berserk"] = first_clk < 0.9 * m["base"]
    inc_eff = m["inc"].where(~m["berserk"], 0.0)

    first_of_side = prev_same.isna()
    m["clock_self"] = prev_same.fillna(m["clk_after"])  # clock as the player STARTS thinking
    spent = m["clock_self"] - m["clk_after"] + inc_eff
    # Each side's first move is untimed on Lichess -> no meaningful think time.
    m["time_spent"] = spent.clip(lower=0).where(~first_of_side)

    g = m.groupby("game_id", sort=False)
    m["clock_opp"] = g["clk_after"].shift(1).where(m["ply"] > 1, m["base"]).where(m["clk_after"].notna())
    m["clock_ratio"] = m["clock_self"] / m["clock_opp"].clip(lower=1)
    # 0+k time controls (base 0) have no "share of starting time" -> NaN, not inf
    m["frac_self"] = m["clock_self"] / m["base"].where(m["base"] > 0)

    # Past think times. All shifted so the current move's own time is never used.
    m["prev_opp_spent"] = g["time_spent"].shift(1)
    side = m.groupby(["game_id", "color"], sort=False)
    m["prev_self_spent"] = side["time_spent"].shift(1)
    keys = [m["game_id"], m["color"]]
    csum = m["prev_self_spent"].fillna(0).groupby(keys, sort=False).cumsum()
    cnt = m["prev_self_spent"].notna().astype(int).groupby(keys, sort=False).cumsum()
    m["avg_self_spent"] = (csum / cnt).where(cnt > 0)
    return m


def add_eval_features(m: pd.DataFrame) -> pd.DataFrame:
    sign = np.where(m["color"] == "white", 1.0, -1.0)
    wp_after_white = pd.Series(win_pct(m["eval_cp"], m["eval_mate"]), index=m.index)
    wp_after_white[m["eval_cp"].isna() & m["eval_mate"].isna()] = np.nan
    g = m.groupby("game_id", sort=False)
    wp_before_white = wp_after_white.groupby(m["game_id"], sort=False).shift(1)

    m["wp_self"] = np.where(sign > 0, wp_before_white, 100 - wp_before_white)
    m["wp_after"] = np.where(sign > 0, wp_after_white, 100 - wp_after_white)
    m["wp_drop"] = m["wp_self"] - m["wp_after"]
    cp_before = g["eval_cp"].shift(1)
    m["abs_cp"] = cp_before.abs().where(g["eval_mate"].shift(1).isna(), CP_CAP)
    # Opponent's last move: how much did THEIR win% drop? (big = they just blundered)
    m["last_swing"] = m.groupby("game_id", sort=False)["wp_drop"].shift(1)

    m["blunder"] = (m["wp_drop"] >= BLUNDER_PTS).astype(float).where(m["wp_drop"].notna())
    # Earlier blunders by THIS player in this game (tilt). Only past plies count.
    prev_b = m.groupby(["game_id", "color"], sort=False)["blunder"].shift(1).fillna(0)
    m["prior_blunders_self"] = prev_b.groupby([m["game_id"], m["color"]], sort=False).cumsum()
    return m


def add_window_labels(m: pd.DataFrame, k: int = 5) -> pd.DataFrame:
    """blunder_next{k}: did this player blunder on this move or any of their next k-1?

    The game ending is NOT censoring: no more moves means no more blunders, so rows
    near the end keep a label (dropping them would drop blunder-then-resign games).
    In analysed games the only unlabelled plies are ply 1 (no eval before it) and a
    final checkmating move; neither can be a blunder, so both count as 0. Any other
    missing eval inside the window (with no blunder seen) leaves the label NaN.
    """
    last_ply = m.groupby("game_id", sort=False)["ply"].transform("max")
    analysed = m.groupby("game_id", sort=False)["blunder"].transform(lambda s: s.notna().any())
    b = m["blunder"].where(~(analysed & m["blunder"].isna() & ((m["ply"] == 1) | (m["ply"] == last_ply))), 0.0)
    keys = [m["game_id"], m["color"]]
    exists = pd.Series(1.0, index=m.index)
    hit = pd.Series(False, index=m.index)
    unknown = pd.Series(False, index=m.index)
    for j in range(k):
        bj = b.groupby(keys, sort=False).shift(-j)
        ej = exists.groupby(keys, sort=False).shift(-j).notna()  # False = game already over
        hit |= bj.eq(1)
        unknown |= ej & bj.isna()
    m[f"blunder_next{k}"] = np.where(hit, 1.0, np.where(unknown, np.nan, 0.0))
    return m


def add_game_context(m: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    g = games[["game_id", "white_elo", "black_elo", "speed", "utc"]]
    m = m.merge(g, on="game_id", how="left")
    white = m["color"] == "white"
    m["elo_self"] = np.where(white, m["white_elo"], m["black_elo"])
    m["elo_opp"] = np.where(white, m["black_elo"], m["white_elo"])
    m["elo_diff"] = m["elo_self"] - m["elo_opp"]
    return m.drop(columns=["white_elo", "black_elo"])


# --------------------------------------------------------------------------- #
def position_features(board) -> dict:
    """Features of the position the side-to-move is facing.

    Pure function of a python-chess Board, so the SAME code serves training and
    a live demo ('same feature code, no mismatch').
    """
    me, them = board.turn, not board.turn
    mat_self = sum(v * len(board.pieces(pt, me)) for pt, v in PIECE_VALUES.items())
    mat_opp = sum(v * len(board.pieces(pt, them)) for pt, v in PIECE_VALUES.items())
    n_legal = n_capt = n_chk = 0
    for mv in board.legal_moves:
        n_legal += 1
        n_capt += board.is_capture(mv)
        n_chk += board.gives_check(mv)
    return {"n_legal": n_legal, "in_check": int(board.is_check()), "n_captures": n_capt,
            "n_checks": n_chk, "mat_total": mat_self + mat_opp, "mat_diff": mat_self - mat_opp}


POSITION_COLS = ["n_legal", "in_check", "n_captures", "n_checks", "mat_total", "mat_diff"]


def add_board_features(m: pd.DataFrame, progress: bool = True) -> pd.DataFrame:
    """Replay every game with python-chess (the slow step: a few hundred games/s)."""
    import chess

    cols = {k: np.full(len(m), np.nan) for k in POSITION_COLS}
    items = list(m.groupby("game_id", sort=False).indices.values())
    if progress:
        try:
            from tqdm import tqdm
            items = tqdm(items, unit="game", desc="board")
        except ImportError:
            pass
    san = m["san"].to_numpy()
    for idx in items:
        board = chess.Board()
        for i in idx:  # m is sorted by (game_id, ply), so idx is in move order
            for k, v in position_features(board).items():
                cols[k][i] = v
            try:
                board.push_san(san[i])
            except ValueError:
                break  # corrupt movetext: leave rest of game NaN
    for k, v in cols.items():
        m[k] = v
    return m


# --------------------------------------------------------------------------- #
def load_moves(speed: str) -> pd.DataFrame:
    from .config import DATA
    p = DATA / speed / "moves.parquet"
    if not p.exists():
        raise SystemExit(f"{p} not found. Run scripts/1_fetch.py and scripts/2_build.py first.")
    return pd.read_parquet(p)


def build_tables(pgn_path: Path, limit: int | None = None, board: bool = True,
                 progress: bool = True) -> tuple[pd.DataFrame, pd.DataFrame]:
    games, moves = load_pgn(pgn_path, limit=limit, progress=progress)
    m = add_clock_features(moves, games)
    m = add_eval_features(m)
    m = add_window_labels(m)
    m = add_game_context(m, games)
    if board:
        m = add_board_features(m, progress=progress)
    keep = ["game_id", "color", "san", "speed", "utc", "berserk", "clk_after", "wp_after", "wp_drop"]  # ply is a feature
    return games, m[keep + FEATURE_COLS + LABEL_COLS]
