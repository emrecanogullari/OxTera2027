"""Build oracle feature vectors from a live RawGameState (extension scrape).

Formulas match Aniket/eda/oracle/features.py + FEATURE_SET.md.
Engine features use Stockfish when available; otherwise NaN (tree models handle missing).
"""

from __future__ import annotations

import math
import os
import shutil
import threading
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
_PAGE: dict[str, "PageLedger"] = {}
_ENGINE: chess.engine.SimpleEngine | None = None
_ENGINE_PATH: str | None = None
_ENGINE_MISSING = False  # True only when binary cannot be found / never starts
_ENGINE_LOCK = threading.Lock()


def _require_engine_strict() -> bool:
    return os.environ.get("OXTERA_REQUIRE_ENGINE", "").strip().lower() in {"1", "true", "yes"}


def _drop_engine() -> None:
    """Forget a dead engine so the next call can spawn a fresh Stockfish."""
    global _ENGINE, _ENGINE_PATH
    eng = _ENGINE
    _ENGINE = None
    if eng is not None:
        try:
            eng.quit()
        except Exception:  # noqa: BLE001
            try:
                eng.close()
            except Exception:  # noqa: BLE001
                pass


def _get_engine() -> chess.engine.SimpleEngine | None:
    global _ENGINE, _ENGINE_PATH, _ENGINE_MISSING
    if _ENGINE is not None:
        return _ENGINE
    if _ENGINE_MISSING:
        return None
    path = find_stockfish()
    if not path:
        _ENGINE_MISSING = True
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
        _ENGINE = None
        if _require_engine_strict():
            raise EngineUnavailableError(f"failed to start Stockfish at {path}: {exc}") from exc
        return None


def evaluate_board(
    board: chess.Board,
    depth: int | None = None,
    movetime: float | None = None,
) -> EvalSnapshot:
    if depth is not None:
        limit = chess.engine.Limit(depth=depth)
    else:
        limit = chess.engine.Limit(time=0.02 if movetime is None else movetime)

    with _ENGINE_LOCK:
        for attempt in range(2):
            engine = _get_engine()
            if engine is None:
                return EvalSnapshot()
            try:
                info = engine.analyse(board, limit)
                score = info["score"].white()
                if score.is_mate():
                    return EvalSnapshot(cp=None, mate=score.mate())
                return EvalSnapshot(cp=float(score.score(mate_score=CP_CAP)), mate=None)
            except (chess.engine.EngineTerminatedError, chess.engine.EngineError, OSError) as exc:
                # Process died mid-game under load — drop and respawn once.
                _drop_engine()
                if attempt == 0:
                    continue
                if _require_engine_strict():
                    raise EngineUnavailableError(f"Stockfish died: {exc}") from exc
                return EvalSnapshot()
    return EvalSnapshot()


def _board_from_fen(fen: str) -> chess.Board:
    try:
        return chess.Board(fen)
    except ValueError as exc:
        raise LiveFeatureError(f"invalid fen: {exc}") from exc


def _board_from_state(raw: dict[str, Any]) -> tuple[chess.Board, bool]:
    """Return the board and whether the move list was the source.

    The move list carries castling and en passant. If its piece placement
    disagrees with the pieces read off the page, the page wins.
    """
    sans = [str(s).strip() for s in (raw.get("moves_san") or []) if str(s).strip()]
    moves_uci = [str(u).strip() for u in (raw.get("moves_uci") or []) if str(u).strip()]
    fen = raw.get("fen") or None
    screen = _board_from_fen(fen) if fen else None

    if sans:
        board = chess.Board()
        try:
            for i, san in enumerate(sans):
                board.push_san(san)
        except ValueError as exc:
            if screen is not None:
                return screen, False
            raise LiveFeatureError(f"invalid san at index {i} ({san!r}): {exc}") from exc
        if screen is not None and board.board_fen() != screen.board_fen():
            return screen, False
        return board, True

    if screen is not None:
        return screen, False

    board = chess.Board()
    for i, uci in enumerate(moves_uci):
        try:
            board.push_uci(uci)
        except ValueError as exc:
            raise LiveFeatureError(f"invalid move at index {i} ({uci!r}): {exc}") from exc
    return board, True


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


def _nan_pad(values: list[float], index: int) -> None:
    while len(values) <= index:
        values.append(math.nan)


def _think_seconds(clk_before: float | None, clk_after: float | None, inc: float, first_move: bool) -> float:
    """Aniket's think time. Each side's first move is empty, not zero."""
    if first_move or clk_before is None or clk_after is None:
        return math.nan
    return max(0.0, clk_before - clk_after + inc)


@dataclass
class PageLedger:
    """One live game. Clocks and evals are kept so the next turn does not recompute them."""

    game_id: str
    human: Color
    base_s: float
    inc_s: float
    sans: list[str] = field(default_factory=list)
    board: chess.Board = field(default_factory=chess.Board)
    white_clock: float | None = None
    black_clock: float | None = None
    spent: list[float] = field(default_factory=lambda: [math.nan])
    wp_white: list[float] = field(default_factory=lambda: [math.nan])
    cp_white: list[float] = field(default_factory=lambda: [math.nan])
    drop: list[float] = field(default_factory=lambda: [math.nan])
    berserk: dict[str, bool] = field(default_factory=lambda: {"white": False, "black": False})
    saw_clock: dict[str, bool] = field(default_factory=lambda: {"white": False, "black": False})
    html_clocks: list[float | None] = field(default_factory=list)


def _page_ledger(raw: dict[str, Any]) -> PageLedger:
    game_id = str(raw.get("game_id") or "unknown")
    human: Color = "black" if str(raw.get("color", "white")).lower().startswith("b") else "white"
    base_s = float(raw["base_s"])
    inc_s = float(raw["inc_s"])
    ledger = _PAGE.get(game_id)
    if ledger is None or ledger.human != human or ledger.base_s != base_s or ledger.inc_s != inc_s:
        ledger = PageLedger(game_id=game_id, human=human, base_s=base_s, inc_s=inc_s)
        _PAGE[game_id] = ledger
    return ledger


def _absolute_clocks(raw: dict[str, Any], human: Color) -> tuple[float, float]:
    """Bottom clock is the human's clock. Return white, black."""
    bottom = float(raw["clock_self_s"])
    top = float(raw["clock_opp_s"])
    if human == "white":
        return bottom, top
    return top, bottom


def _note_berserk(ledger: PageLedger, side: str, clock: float) -> None:
    if ledger.saw_clock[side]:
        return
    ledger.saw_clock[side] = True
    if ledger.base_s > 0 and clock < 0.9 * ledger.base_s:
        ledger.berserk[side] = True


def _replay(ledger: PageLedger, sans: list[str]) -> list[str] | None:
    """Push new moves. None means the list jumped, so old think times are dropped."""
    if sans[: len(ledger.sans)] == ledger.sans:
        added = sans[len(ledger.sans) :]
        for san in added:
            try:
                ledger.board.push_san(san)
            except ValueError as exc:
                raise LiveFeatureError(f"invalid san {san!r}: {exc}") from exc
        ledger.sans = list(sans)
        return added
    board = chess.Board()
    for san in sans:
        try:
            board.push_san(san)
        except ValueError as exc:
            raise LiveFeatureError(f"invalid san {san!r}: {exc}") from exc
    ledger.board = board
    ledger.sans = list(sans)
    ledger.spent = [math.nan]
    ledger.wp_white = [math.nan]
    ledger.cp_white = [math.nan]
    ledger.drop = [math.nan]
    ledger.white_clock = None
    ledger.black_clock = None
    ledger.html_clocks = []
    return None


def _record_spend(ledger: PageLedger, added: list[str] | None, white_clk: float, black_clk: float) -> None:
    if added is None:
        return
    if len(added) != 1 or ledger.white_clock is None or ledger.black_clock is None:
        for _ in added:
            ledger.spent.append(math.nan)
        return
    mover = "white" if (len(ledger.sans) % 2 == 1) else "black"
    before = ledger.white_clock if mover == "white" else ledger.black_clock
    after = white_clk if mover == "white" else black_clk
    ply = len(ledger.sans)
    inc = 0.0 if ledger.berserk[mover] else ledger.inc_s
    ledger.spent.append(_think_seconds(before, after, inc, ply <= 2))


def _check_move_clocks(ledger: PageLedger, raw: dict[str, Any], white_clk: float, black_clk: float) -> None:
    clocks = raw.get("move_clocks")
    if not clocks:
        return
    sans = ledger.sans
    if len(clocks) != len(sans):
        raise LiveFeatureError("move clocks do not line up with the move list")
    if sans:
        printed = clocks[-1]
        if printed is not None:
            mover_white = len(sans) % 2 == 1
            big = white_clk if mover_white else black_clk
            if abs(float(printed) - big) > 1.0:
                raise LiveFeatureError(
                    f"clock on {sans[-1]} is {printed}s, the board clock is {big}s"
                )
    for index, printed in enumerate(clocks):
        if printed is None or index >= len(ledger.html_clocks):
            continue
        previous = ledger.html_clocks[index]
        if previous is not None and abs(float(printed) - float(previous)) > 1.0:
            raise LiveFeatureError(f"move {index + 1} clock changed from {previous}s to {printed}s")
    ledger.html_clocks = [None if value is None else float(value) for value in clocks]


def _fill_spends_from_printed_clocks(ledger: PageLedger) -> None:
    """Use per-move clocks from the page when we did not watch those moves happen."""
    clocks = ledger.html_clocks
    if not clocks or any(value is None for value in clocks):
        return
    if any(not math.isnan(value) for value in ledger.spent[1:]):
        return
    prev = {"white": None, "black": None}
    spent = [math.nan]
    for index, clk_after in enumerate(clocks):
        ply = index + 1
        mover = "white" if ply % 2 == 1 else "black"
        inc = 0.0 if ledger.berserk[mover] else ledger.inc_s
        spent.append(_think_seconds(prev[mover], clk_after, inc, ply <= 2))
        prev[mover] = clk_after
    ledger.spent = spent


def _earlier_spends(ledger: PageLedger, side: str, ply: int) -> tuple[float, float]:
    start = 1 if side == "white" else 2
    values: list[float] = []
    cursor = start
    while cursor < ply:
        if cursor < len(ledger.spent) and not math.isnan(ledger.spent[cursor]):
            values.append(ledger.spent[cursor])
        cursor += 2
    if not values:
        return math.nan, math.nan
    return values[-1], sum(values) / len(values)


def _prior_blunders(ledger: PageLedger, side: str, ply: int) -> float:
    start = 1 if side == "white" else 2
    count = 0
    cursor = start
    while cursor < ply:
        if cursor < len(ledger.drop) and not math.isnan(ledger.drop[cursor]) and ledger.drop[cursor] >= BLUNDER_PTS:
            count += 1
        cursor += 2
    return float(count)


def _search_position(board: chess.Board, *, engine_depth: int | None, movetime: float | None) -> EvalSnapshot:
    if movetime == 0:
        return EvalSnapshot()
    if engine_depth is not None:
        return evaluate_board(board, depth=engine_depth)
    return evaluate_board(board, movetime=0.02 if movetime is None else movetime)


def _build_from_placement(
    raw: dict[str, Any],
    *,
    engine_depth: int | None,
    movetime: float | None,
) -> tuple[str, dict[str, float], bool]:
    """Lichess path: replay the move list, keep it only if it matches the piece picture."""
    required = ("base_s", "inc_s", "clock_self_s", "clock_opp_s", "elo_self", "color", "placement")
    missing = [key for key in required if raw.get(key) is None]
    if missing:
        raise LiveFeatureError(f"missing required fields: {missing}")

    base_s = float(raw["base_s"])
    inc_s = float(raw["inc_s"])
    speed = model_speed_or_raise(base_s, inc_s)
    ledger = _page_ledger(raw)
    white_clk, black_clk = _absolute_clocks(raw, ledger.human)
    sans = [str(san).strip() for san in (raw.get("moves_san") or []) if str(san).strip()]
    # Berserk is "the clock at move 1 is under 90% of the base". A later clock is not that.
    if not sans:
        _note_berserk(ledger, "white", white_clk)
        _note_berserk(ledger, "black", black_clk)
    saved = (
        list(ledger.sans),
        ledger.board.copy(stack=True),
        list(ledger.spent),
        list(ledger.wp_white),
        list(ledger.cp_white),
        list(ledger.drop),
        ledger.white_clock,
        ledger.black_clock,
        list(ledger.html_clocks),
    )
    try:
        added = _replay(ledger, sans)
        picture = str(raw["placement"]).split()[0]
        if ledger.board.board_fen() != picture:
            raise LiveFeatureError("piece picture does not match the move list")
        side = "white" if ledger.board.turn == chess.WHITE else "black"
        asked = raw.get("side_to_move")
        if asked is not None and str(asked).lower() not in {side, side[0]}:
            raise LiveFeatureError(f"highlighted clock says {asked} to move, move list says {side}")
        _record_spend(ledger, added, white_clk, black_clk)
        _check_move_clocks(ledger, raw, white_clk, black_clk)
        _fill_spends_from_printed_clocks(ledger)
    except LiveFeatureError:
        (
            ledger.sans,
            ledger.board,
            ledger.spent,
            ledger.wp_white,
            ledger.cp_white,
            ledger.drop,
            ledger.white_clock,
            ledger.black_clock,
            ledger.html_clocks,
        ) = saved
        raise
    ledger.white_clock = white_clk
    ledger.black_clock = black_clk

    ply = len(ledger.sans) + 1
    clock_self = white_clk if side == "white" else black_clk
    clock_opp = black_clk if side == "white" else white_clk
    if side == ledger.human:
        elo_self = float(raw["elo_self"])
    elif raw.get("elo_opp") is None:
        raise LiveFeatureError("missing opponent rating")
    else:
        elo_self = float(raw["elo_opp"])

    prev_self, avg_self = _earlier_spends(ledger, side, ply)
    prev_opp = ledger.spent[ply - 1] if ply - 1 < len(ledger.spent) else math.nan

    wp_self = math.nan
    abs_cp = math.nan
    last_swing = math.nan
    engine_used = False
    if ply > 1 and movetime != 0:
        snap = _search_position(ledger.board, engine_depth=engine_depth, movetime=movetime)
        engine_used = snap.cp is not None or snap.mate is not None or _ENGINE is not None
        if snap.cp is not None or snap.mate is not None:
            _nan_pad(ledger.wp_white, ply - 1)
            _nan_pad(ledger.cp_white, ply - 1)
            ledger.wp_white[ply - 1] = snap.wp_white
            if snap.mate is not None:
                ledger.cp_white[ply - 1] = float(CP_CAP if snap.mate > 0 else -CP_CAP)
                abs_cp = float(CP_CAP)
            else:
                ledger.cp_white[ply - 1] = float(snap.cp or 0.0)
                abs_cp = abs(float(snap.cp or 0.0))
            wp_self = snap.wp_white if side == "white" else 100.0 - snap.wp_white
            finished = ply - 1
            before = ledger.wp_white[finished - 1] if finished - 1 < len(ledger.wp_white) else math.nan
            after = ledger.wp_white[finished]
            if finished >= 2 and not math.isnan(before) and not math.isnan(after):
                if finished % 2 == 1:
                    swing = before - after
                else:
                    swing = (100.0 - before) - (100.0 - after)
                _nan_pad(ledger.drop, finished)
                ledger.drop[finished] = swing
                last_swing = swing
    elif ply == 1 and movetime != 0:
        engine_used = find_stockfish() is not None and not _ENGINE_MISSING

    pos = position_features(ledger.board)
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
        "last_swing": last_swing,
        "prior_blunders_self": _prior_blunders(ledger, side, ply),
    }
    return speed, {key: features[key] for key in FEATURE_KEYS_BY_SPEED[speed]}, engine_used


def build_features(
    raw: dict[str, Any],
    *,
    engine_depth: int | None = None,
    movetime: float | None = None,
) -> tuple[str, dict[str, float], bool]:
    """Return (model_speed, feature_dict, engine_used)."""
    if raw.get("placement"):
        return _build_from_placement(raw, engine_depth=engine_depth, movetime=movetime)
    if engine_depth is None:
        engine_depth = 12
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
    board, used_move_list = _board_from_state(raw)
    if used_move_list and raw.get("ply") is not None:
        ply = int(raw["ply"])
    elif used_move_list and board.move_stack:
        ply = len(board.move_stack) + 1
    else:
        # Piece placement only. Its fullmove and side describe the screen,
        # including when a longer move list was rejected.
        ply = (board.fullmove_number - 1) * 2 + (1 if board.turn == chess.WHITE else 2)
    if (ply % 2 == 1) != (board.turn == chess.WHITE):
        ply = (board.fullmove_number - 1) * 2 + (1 if board.turn == chess.WHITE else 2)

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
        snap = evaluate_board(board, depth=engine_depth)
        engine_used = snap.cp is not None or snap.mate is not None or _ENGINE is not None

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
    if board.move_stack and engine_used:
        # Eval after previous ply (position before last move) vs now for swing tracking.
        prev_board = board.copy(stack=True)
        try:
            prev_board.pop()
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
    _PAGE.clear()


def warm_engine() -> None:
    """Start Stockfish once, so the first move does not pay for process startup."""
    _get_engine()


def shutdown_engine() -> None:
    global _ENGINE, _ENGINE_PATH, _ENGINE_MISSING
    _drop_engine()
    _ENGINE_PATH = None
    # Do not set _ENGINE_MISSING — allow a later warm/predict to find Stockfish again.
