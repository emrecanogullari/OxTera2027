"""Walk a game's SAN list and yield FEN-before each stored ply."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Any

import chess

from annotate.clock_features import ClockTracker
from annotate.material import advantage_for_mover, material_snapshot


def replay_game(
    *,
    game_id: str,
    base: float,
    inc: float,
    moves: Iterable[dict[str, Any]],
) -> Iterator[dict[str, Any]]:
    board = chess.Board()
    clocks = ClockTracker(base=base, inc=inc)
    expected_ply = 1
    for move in moves:
        ply = int(move["ply"])
        if ply != expected_ply:
            return
        try:
            fen_before = board.fen()
            white, black, total, adv_white = material_snapshot(board)
            color = move["color"]
            mover_white = color == "w"
            clock = clocks.snapshot(color, float(move["clk_after_s"]))
            yield {
                "game_id": game_id,
                "ply": ply,
                "fen_before": fen_before,
                "material_white": white,
                "material_black": black,
                "material_total": total,
                "material_advantage_white": adv_white,
                "material_advantage_mover": advantage_for_mover(adv_white, mover_white),
                **clock,
            }
            board.push_san(move["san"])
        except (ValueError, chess.InvalidMoveError, chess.IllegalMoveError, chess.AmbiguousMoveError):
            return
        expected_ply += 1
