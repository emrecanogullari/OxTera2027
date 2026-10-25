"""Build oracle feature vectors from a live RawGameState (extension scrape).

Formulas match Aniket/eda/oracle/features.py + FEATURE_SET.md.
Engine features use Stockfish when available; otherwise NaN (tree models handle missing).
"""

from __future__ import annotations

import math
import os
import shutil
from dataclasses import dataclass, field
from typing import Any, Literal

import chess
import chess.engine

Color = Literal["white", "black"]
Site = Literal["chesscom", "lichess"]

# Lichess estimated duration buckets (Aniket/eda/oracle/config.py).
SPEED_BOUNDS = [(29, "ultrabullet"), (179, "bullet"), (479, "blitz"), (1499, "rapid")]
MODEL_SPEEDS = frozenset({"bullet", "blitz", "classical"})

WC_K = 0.00368208
CP_CAP = 1000
BLUNDER_PTS = 20
PIECE_VALUES = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}

FEATURE_KEYS_BY_SPEED: dict[str, list[str]] = {
    "bullet": [
        "clock_self", "clock_opp", "clock_ratio", "base", "inc",
        "prev_self_spent", "avg_self_spent", "prev_opp_spent",
        "elo_self", "ply", "mat_total", "mat_diff", "n_legal", "n_captures",
        "wp_self", "abs_cp", "last_swing", "prior_blunders_self",
    ],
    "blitz": [
        "clock_self", "clock_opp", "clock_ratio", "inc",
        "prev_self_spent", "avg_self_spent", "prev_opp_spent",
        "elo_self", "ply", "mat_total", "mat_diff", "n_legal", "n_captures",
        "wp_self", "abs_cp", "last_swing", "prior_blunders_self",
    ],
    "classical": [
        "clock_self", "clock_ratio", "frac_self",
        "prev_self_spent", "avg_self_spent", "prev_opp_spent",
        "elo_self", "ply", "mat_total", "mat_diff", "n_legal", "n_captures",
        "wp_self", "abs_cp", "last_swing", "prior_blunders_self",
    ],
}


class LiveFeatureError(ValueError):
    """Bad live input (maps to HTTP 400)."""


class EngineUnavailableError(RuntimeError):
    """Stockfish required but not found (maps to HTTP 503 when strict)."""


def speed_of(base: float, inc: float) -> str:
    if math.isnan(base):
        return "correspondence"
    est = base + 40 * inc
    for bound, name in SPEED_BOUNDS:
        if est <= bound:
            return name
    return "classical"


def model_speed_or_raise(base: float, inc: float) -> str:
    speed = speed_of(base, inc)
    if speed not in MODEL_SPEEDS:
        raise LiveFeatureError(
            f"no trained model for speed '{speed}' "
            f"(base={base}, inc={inc}; est={base + 40 * inc:.0f}s). "
            "Only bullet, blitz, and classical are supported."
        )
    return speed


def win_pct(cp: float | None, mate: int | None = None) -> float:
    """Lichess win% 0–100 from White's POV."""
    if mate is not None:
        return 100.0 if mate > 0 else 0.0
    if cp is None or (isinstance(cp, float) and math.isnan(cp)):
        return math.nan
    cp = max(-CP_CAP, min(CP_CAP, float(cp)))
    return 50.0 + 50.0 * (2.0 / (1.0 + math.exp(-WC_K * cp)) - 1.0)


def position_features(board: chess.Board) -> dict[str, float]:
    me, them = board.turn, not board.turn
    mat_self = sum(v * len(board.pieces(pt, me)) for pt, v in PIECE_VALUES.items())
    mat_opp = sum(v * len(board.pieces(pt, them)) for pt, v in PIECE_VALUES.items())
    n_legal = n_capt = 0
    for mv in board.legal_moves:
        n_legal += 1
        n_capt += int(board.is_capture(mv))
    return {
        "n_legal": float(n_legal),
        "n_captures": float(n_capt),
        "mat_total": float(mat_self + mat_opp),
        "mat_diff": float(mat_self - mat_opp),
    }


def find_stockfish() -> str | None:
    env = os.environ.get("STOCKFISH_PATH", "").strip()
    if env and os.path.isfile(env):
        return env
    return shutil.which("stockfish") or shutil.which("stockfish.exe")


@dataclass
class EvalSnapshot:
    """White-POV eval after a ply (or at root before any move)."""

    cp: float | None = None
    mate: int | None = None

    @property
    def wp_white(self) -> float:
        return win_pct(self.cp, self.mate)


@dataclass
class GameSession:
    """Per-game rolling state for spend history and eval/blunder tracking."""

    game_id: str
    color: Color
    base_s: float
    inc_s: float
    self_spents: list[float] = field(default_factory=list)
    prev_opp_spent: float = math.nan
    prior_blunders_self: int = 0
    last_wp_drop: float = math.nan  # opponent's last swing into our turn
    # Eval after each completed ply, White POV; index 0 = start position
    evals_after_ply: list[EvalSnapshot] = field(default_factory=list)
    last_clock_self: float | None = None
    last_clock_opp: float | None = None
    last_ply: int = 0


_SESSIONS: dict[str, GameSession] = {}
_ENGINE: chess.engine.SimpleEngine | None = None
_ENGINE_PATH: str | None = None
_ENGINE_FAILED = False


def _require_engine_strict() -> bool:
    return os.environ.get("OXTERA_REQUIRE_ENGINE", "").strip().lower() in {"1", "true", "yes"}


def _get_engine() -> chess.engine.SimpleEngine | None:
    global _ENGINE, _ENGINE_PATH, _ENGINE_FAILED
    if _ENGINE is not None:
        return _ENGINE
    if _ENGINE_FAILED:
        return None
    path = find_stockfish()
    if not path:
        _ENGINE_FAILED = True
        if _require_engine_strict():
            raise EngineUnavailableError(
                "Stockfish not found. Set STOCKFISH_PATH or install stockfish on PATH."
            )
        return None
    try:
        _ENGINE = chess.engine.SimpleEngine.popen_uci(path)
        _ENGINE_PATH = path
        return _ENGINE
    except Exception as exc:  # noqa: BLE001
        _ENGINE_FAILED = True
        if _require_engine_strict():
            raise EngineUnavailableError(f"failed to start Stockfish at {path}: {exc}") from exc
        return None


def evaluate_board(board: chess.Board, depth: int = 12) -> EvalSnapshot:
    engine = _get_engine()
    if engine is None:
        return EvalSnapshot()
    limit = chess.engine.Limit(depth=depth)
    info = engine.analyse(board, limit)
    score = info["score"].white()
    if score.is_mate():
        mate = score.mate()
        return EvalSnapshot(cp=None, mate=mate)
    return EvalSnapshot(cp=float(score.score(mate_score=CP_CAP)), mate=None)


def _board_from_state(moves_uci: list[str], fen: str | None) -> chess.Board:
    if fen:
        try:
            return chess.Board(fen)
        except ValueError as exc:
            raise LiveFeatureError(f"invalid fen: {exc}") from exc
    board = chess.Board()
    for i, uci in enumerate(moves_uci):
        try:
            board.push_uci(uci)
        except ValueError as exc:
            raise LiveFeatureError(f"invalid move at index {i} ({uci!r}): {exc}") from exc
    return board


def _session_for(raw: dict[str, Any]) -> GameSession:
    game_id = str(raw.get("game_id") or "unknown")
    color: Color = "black" if str(raw.get("color", "white")).lower().startswith("b") else "white"
    base_s = float(raw["base_s"])
    inc_s = float(raw["inc_s"])
    sess = _SESSIONS.get(game_id)
    if sess is None or sess.color != color or sess.base_s != base_s:
        sess = GameSession(game_id=game_id, color=color, base_s=base_s, inc_s=inc_s)
        _SESSIONS[game_id] = sess
    return sess


def _update_spend_history(sess: GameSession, clock_self: float, clock_opp: float, ply: int) -> None:
    """Infer think times from successive clock readings when the extension does not send them."""
    if sess.last_ply > 0 and ply > sess.last_ply and sess.last_clock_self is not None:
        # Our previous think finished; opponent may have moved too.
        spent_self = sess.last_clock_self - clock_self + sess.inc_s
        if spent_self >= 0:
            sess.self_spents.append(spent_self)
        if sess.last_clock_opp is not None:
            spent_opp = sess.last_clock_opp - clock_opp + sess.inc_s
            if spent_opp >= 0:
                sess.prev_opp_spent = spent_opp
    sess.last_clock_self = clock_self
    sess.last_clock_opp = clock_opp
    sess.last_ply = ply


def build_features(raw: dict[str, Any], *, engine_depth: int = 12) -> tuple[str, dict[str, float], bool]:
    """Return (model_speed, feature_dict, engine_used)."""
    required = ("base_s", "inc_s", "clock_self_s", "clock_opp_s", "elo_self", "color")
    missing = [k for k in required if k not in raw or raw[k] is None]
    if missing:
        raise LiveFeatureError(f"missing required fields: {missing}")

    base_s = float(raw["base_s"])
    inc_s = float(raw["inc_s"])
    speed = model_speed_or_raise(base_s, inc_s)

    clock_self = float(raw["clock_self_s"])
    clock_opp = float(raw["clock_opp_s"])
    elo_self = float(raw["elo_self"])
    moves_uci = list(raw.get("moves_uci") or [])
    fen = raw.get("fen")
    ply = int(raw["ply"]) if raw.get("ply") is not None else len(moves_uci) + 1

    board = _board_from_state(moves_uci, fen)
    pos = position_features(board)

    color: Color = "black" if str(raw["color"]).lower().startswith("b") else "white"
    # Side to move should match our colour when it is our turn.
    if (board.turn == chess.WHITE) != (color == "white"):
        # Still compute features for the position on the board; colour is for spend/eval POV.
        pass

    sess = _session_for(raw)

    # Prefer explicit spend fields from the extension when present.
    if raw.get("prev_self_spent") is not None:
        prev_self = float(raw["prev_self_spent"])
    else:
        _update_spend_history(sess, clock_self, clock_opp, ply)
        prev_self = sess.self_spents[-1] if sess.self_spents else math.nan

    if raw.get("avg_self_spent") is not None:
        avg_self = float(raw["avg_self_spent"])
    elif sess.self_spents:
        avg_self = sum(sess.self_spents) / len(sess.self_spents)
    else:
        avg_self = math.nan

    if raw.get("prev_opp_spent") is not None:
        prev_opp = float(raw["prev_opp_spent"])
    else:
        prev_opp = sess.prev_opp_spent

    if raw.get("prior_blunders_self") is not None:
        prior_blunders = float(raw["prior_blunders_self"])
    else:
        prior_blunders = float(sess.prior_blunders_self)

    # Engine features: eval of the position we are facing (= after opponent's last move).
    engine_used = find_stockfish() is not None and not _ENGINE_FAILED
    snap = evaluate_board(board, depth=engine_depth)
    engine_used = _ENGINE is not None

    if snap.cp is None and snap.mate is None:
        wp_self = math.nan
        abs_cp = math.nan
        last_swing = sess.last_wp_drop
    else:
        wp_white = snap.wp_white
        wp_self = wp_white if color == "white" else 100.0 - wp_white
        if snap.mate is not None:
            abs_cp = float(CP_CAP)
        else:
            abs_cp = abs(float(snap.cp or 0.0))
        last_swing = sess.last_wp_drop

    # Update session after we have a prediction for next turn's last_swing / blunders.
    # When we later see the opponent move, the extension will call again; we track
    # wp_drop once we re-evaluate after our move is in moves_uci.
    if len(moves_uci) > 0 and engine_used:
        # Eval after previous ply (position before last move) vs now for swing tracking.
        prev_board = chess.Board()
        try:
            for uci in moves_uci[:-1]:
                prev_board.push_uci(uci)
            prev_snap = evaluate_board(prev_board, depth=engine_depth)
            if prev_snap.cp is not None or prev_snap.mate is not None:
                prev_wp_w = prev_snap.wp_white
                now_wp_w = snap.wp_white
                # Last mover's colour is opposite of current side to move.
                last_was_white = board.turn == chess.BLACK
                if last_was_white:
                    wp_drop = prev_wp_w - now_wp_w
                else:
                    wp_drop = (100.0 - prev_wp_w) - (100.0 - now_wp_w)
                sess.last_wp_drop = wp_drop
                last_mover_is_self = (last_was_white and color == "white") or (
                    (not last_was_white) and color == "black"
                )
                if last_mover_is_self and wp_drop >= BLUNDER_PTS:
                    # Count completed self-blunders into prior for *next* call; for this
                    # call prior_blunders was already snapshotted above.
                    sess.prior_blunders_self += 1
                last_swing = sess.last_wp_drop if not last_mover_is_self else last_swing
        except ValueError:
            pass

    features: dict[str, float] = {
        "clock_self": clock_self,
        "clock_opp": clock_opp,
        "clock_ratio": clock_self / max(clock_opp, 1.0),
        "frac_self": (clock_self / base_s) if base_s > 0 else math.nan,
        "base": base_s,
        "inc": inc_s,
        "prev_self_spent": prev_self,
        "avg_self_spent": avg_self,
        "prev_opp_spent": prev_opp,
        "elo_self": elo_self,
        "ply": float(ply),
        "mat_total": pos["mat_total"],
        "mat_diff": pos["mat_diff"],
        "n_legal": pos["n_legal"],
        "n_captures": pos["n_captures"],
        "wp_self": wp_self,
        "abs_cp": abs_cp,
        "last_swing": last_swing if not (isinstance(last_swing, float) and math.isnan(last_swing)) else math.nan,
        "prior_blunders_self": prior_blunders,
    }

    keys = FEATURE_KEYS_BY_SPEED[speed]
    return speed, {k: features[k] for k in keys}, engine_used


def clear_sessions() -> None:
    _SESSIONS.clear()


def shutdown_engine() -> None:
    global _ENGINE, _ENGINE_PATH, _ENGINE_FAILED
    if _ENGINE is not None:
        try:
            _ENGINE.quit()
        except Exception:  # noqa: BLE001
            pass
    _ENGINE = None
    _ENGINE_PATH = None
    _ENGINE_FAILED = False
