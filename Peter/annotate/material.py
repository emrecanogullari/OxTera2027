"""Point counts and mover advantage from a python-chess board."""

from __future__ import annotations

import chess

PIECE_POINTS = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 0,
}


def side_material(board: chess.Board, color: chess.Color) -> int:
    return sum(
        PIECE_POINTS[piece.piece_type]
        for piece in board.piece_map().values()
        if piece.color == color
    )


def material_snapshot(board: chess.Board) -> tuple[int, int, int, int]:
    white = side_material(board, chess.WHITE)
    black = side_material(board, chess.BLACK)
    return white, black, white + black, white - black


def advantage_for_mover(white_minus_black: int, mover_is_white: bool) -> int:
    return white_minus_black if mover_is_white else -white_minus_black
