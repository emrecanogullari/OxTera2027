"""Unit checks for live feature builder (no Stockfish required)."""

from __future__ import annotations

import math

import chess

import live_features
from live_features import (
    LiveFeatureError,
    build_features,
    clear_sessions,
    model_speed_or_raise,
    shutdown_engine,
    speed_of,
    win_pct,
)


def test_speed_of_buckets() -> None:
    assert speed_of(60, 0) == "bullet"
    assert speed_of(180, 2) == "blitz"
    assert speed_of(1800, 0) == "classical"
    assert speed_of(600, 0) == "rapid"


def test_model_speed_rejects_rapid() -> None:
    try:
        model_speed_or_raise(600, 0)
        raise AssertionError("expected LiveFeatureError")
    except Exception as exc:
        assert "rapid" in str(exc)


def test_build_starting_position_blitz() -> None:
    clear_sessions()
    speed, feats, _engine = build_features(
        {
            "client_id": "test-client-a",
            "site": "chesscom",
            "game_id": "t1",
            "color": "white",
            "base_s": 180,
            "inc_s": 2,
            "elo_self": 1500,
            "clock_self_s": 180,
            "clock_opp_s": 180,
            "moves_uci": [],
            "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            "ply": 1,
        },
        engine_depth=1,
    )
    assert speed == "blitz"
    assert feats["clock_self"] == 180
    assert feats["clock_opp"] == 180
    assert feats["clock_ratio"] == 1.0
    assert feats["inc"] == 2
    assert feats["elo_self"] == 1500
    assert feats["ply"] == 1
    assert feats["mat_total"] == 78
    assert feats["mat_diff"] == 0
    assert feats["n_legal"] == 20
    assert feats["n_captures"] == 0
    assert math.isnan(feats["prev_self_spent"])
    assert "base" not in feats  # blitz superset has no base


def test_moves_san_checked_against_pieces() -> None:
    clear_sessions()
    speed, feats, _ = build_features(
        {
            "client_id": "test-client-a",
            "site": "chesscom",
            "game_id": "t3",
            "color": "white",
            "base_s": 180,
            "inc_s": 0,
            "elo_self": 1165,
            "clock_self_s": 178,
            "clock_opp_s": 176,
            "moves_san": ["e4", "e5", "d4", "exd4"],
            "fen": "rnbqkbnr/pppp1ppp/8/8/3pP3/8/PPP2PPP/RNBQKBNR w KQkq - 0 3",
            "ply": 5,
        },
        engine_depth=1,
    )
    assert speed == "blitz"
    assert feats["ply"] == 5
    assert feats["mat_total"] == 77
    assert feats["mat_diff"] == -1
    assert feats["n_captures"] > 0


def test_piece_placement_wins_when_move_list_disagrees() -> None:
    clear_sessions()
    _speed, feats, _ = build_features(
        {
            "client_id": "test-client-a",
            "site": "lichess",
            "game_id": "t4",
            "color": "white",
            "base_s": 300,
            "inc_s": 0,
            "elo_self": 1101,
            "clock_self_s": 300,
            "clock_opp_s": 300,
            "moves_san": ["e4", "e5", "d4", "exd4"],
            "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            "ply": 5,
        },
        engine_depth=1,
    )
    assert feats["ply"] == 1
    assert feats["mat_total"] == 78
    assert feats["n_legal"] == 20
    assert feats["n_captures"] == 0


def _live(
    game_id: str,
    color: str,
    side: str,
    white_clk: float,
    black_clk: float,
    sans: list[str],
    placement: str,
    *,
    client_id: str = "test-client-a",
):
    bottom, top = (white_clk, black_clk) if color == "white" else (black_clk, white_clk)
    return {
        "client_id": client_id,
        "site": "lichess",
        "game_id": game_id,
        "color": color,
        "side_to_move": side,
        "base_s": 180,
        "inc_s": 2,
        "elo_self": 1500,
        "elo_opp": 1600,
        "clock_self_s": bottom,
        "clock_opp_s": top,
        "placement": placement,
        "moves_san": sans,
        "ply": len(sans) + 1,
    }


def test_lichess_rejects_a_picture_that_disagrees() -> None:
    clear_sessions()
    start = chess.Board().board_fen()
    try:
        build_features(
            _live("reject", "white", "white", 180, 180, ["e4"], start),
            movetime=0,
        )
        raise AssertionError("expected the piece check to fail")
    except LiveFeatureError as exc:
        assert "piece picture" in str(exc)
    # The rejected move must not stick. The real start position still works.
    _speed, feats, _ = build_features(
        _live("reject", "white", "white", 180, 180, [], start),
        movetime=0,
    )
    assert feats["ply"] == 1
    assert feats["n_legal"] == 20
    assert math.isnan(feats["prev_self_spent"])
    assert math.isnan(feats["prev_opp_spent"])


def test_lichess_clocks_follow_training_rules() -> None:
    clear_sessions()
    board = chess.Board()
    start = board.board_fen()
    board.push_san("e4")
    after_e4 = board.board_fen()
    board.push_san("e5")
    after_e5 = board.board_fen()
    board.push_san("Nf3")
    after_nf3 = board.board_fen()

    cps = {start: 20.0, after_e4: 30.0, after_e5: 25.0, after_nf3: 28.0}
    original = live_features.evaluate_board

    def fake(board, depth=None, movetime=None):
        return live_features.EvalSnapshot(cp=cps[board.board_fen()])

    live_features.evaluate_board = fake
    try:
        _speed, opening, _ = build_features(
            _live("clocks", "white", "white", 180, 180, [], start)
        )
        assert opening["ply"] == 1
        assert opening["clock_self"] == 180
        assert opening["mat_total"] == 78
        assert math.isnan(opening["prev_self_spent"])
        assert math.isnan(opening["wp_self"])

        _speed, black_turn, _ = build_features(
            _live("clocks", "white", "black", 180, 180, ["e4"], after_e4)
        )
        assert black_turn["ply"] == 2
        assert black_turn["clock_self"] == 180
        assert black_turn["elo_self"] == 1600
        assert math.isnan(black_turn["prev_opp_spent"])
        assert math.isnan(black_turn["last_swing"])

        _speed, white_again, _ = build_features(
            _live("clocks", "white", "white", 180, 176, ["e4", "e5"], after_e5)
        )
        black_drop = (100.0 - win_pct(30)) - (100.0 - win_pct(25))
        assert white_again["clock_self"] == 180
        assert white_again["clock_opp"] == 176
        assert math.isnan(white_again["prev_self_spent"])
        assert math.isnan(white_again["prev_opp_spent"])
        assert white_again["last_swing"] == black_drop
        assert white_again["n_legal"] == 29

        _speed, after_second, _ = build_features(
            _live("clocks", "white", "black", 170, 176, ["e4", "e5", "Nf3"], after_nf3)
        )
        # 180 at the start of White's second move, 170 after it, plus the 2s increment.
        assert after_second["prev_opp_spent"] == 12
        assert math.isnan(after_second["prev_self_spent"])
        assert after_second["prior_blunders_self"] == 0
    finally:
        live_features.evaluate_board = original
        clear_sessions()


def test_printed_move_clock_must_match_the_board_clock() -> None:
    clear_sessions()
    board = chess.Board()
    board.push_san("e4")
    raw = _live("printed", "white", "black", 180, 180, ["e4"], board.board_fen())
    raw["move_clocks"] = [100]
    try:
        build_features(raw, movetime=0)
        raise AssertionError("expected the printed clock to be rejected")
    except LiveFeatureError as exc:
        assert "clock on e4" in str(exc)


def test_build_after_e4() -> None:
    clear_sessions()
    speed, feats, _ = build_features(
        {
            "client_id": "test-client-a",
            "site": "lichess",
            "game_id": "t2",
            "color": "black",
            "base_s": 180,
            "inc_s": 0,
            "elo_self": 1600,
            "clock_self_s": 180,
            "clock_opp_s": 175,
            "moves_uci": ["e2e4"],
            "ply": 2,
        },
        engine_depth=1,
    )
    assert speed == "blitz"
    assert feats["ply"] == 2
    assert feats["mat_total"] == 78
    assert feats["n_legal"] == 20


def test_client_id_isolates_same_game_id() -> None:
    """Two clients sharing a platform game_id must not share spend ledgers."""
    clear_sessions()
    board = chess.Board()
    start = board.board_fen()
    board.push_san("e4")
    after_e4 = board.board_fen()

    build_features(
        _live("shared-game", "white", "white", 180, 180, [], start, client_id="client-a"),
        movetime=0,
    )
    build_features(
        _live("shared-game", "white", "black", 170, 180, ["e4"], after_e4, client_id="client-a"),
        movetime=0,
    )
    # Client B starts fresh on the same game_id — no spend history from A.
    _speed, feats_b, _ = build_features(
        _live("shared-game", "white", "black", 170, 180, ["e4"], after_e4, client_id="client-b"),
        movetime=0,
    )
    assert math.isnan(feats_b["prev_opp_spent"])
    assert "client-a:shared-game" in live_features._PAGE
    assert "client-b:shared-game" in live_features._PAGE


def test_missing_client_id_rejected() -> None:
    clear_sessions()
    try:
        build_features(
            {
                "site": "chesscom",
                "game_id": "t-missing",
                "color": "white",
                "base_s": 180,
                "inc_s": 0,
                "elo_self": 1500,
                "clock_self_s": 180,
                "clock_opp_s": 180,
                "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
                "ply": 1,
            },
            movetime=0,
        )
        raise AssertionError("expected LiveFeatureError for missing client_id")
    except LiveFeatureError as exc:
        assert "client_id" in str(exc)


if __name__ == "__main__":
    test_speed_of_buckets()
    test_model_speed_rejects_rapid()
    test_build_starting_position_blitz()
    test_moves_san_checked_against_pieces()
    test_piece_placement_wins_when_move_list_disagrees()
    test_lichess_rejects_a_picture_that_disagrees()
    test_lichess_clocks_follow_training_rules()
    test_printed_move_clock_must_match_the_board_clock()
    test_build_after_e4()
    test_client_id_isolates_same_game_id()
    test_missing_client_id_rejected()
    shutdown_engine()
    print("ok")
