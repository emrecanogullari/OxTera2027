"""Unit checks for live feature builder (no Stockfish required)."""

from __future__ import annotations

import math

from live_features import build_features, clear_sessions, model_speed_or_raise, speed_of


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
        }
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


def test_build_after_e4() -> None:
    clear_sessions()
    speed, feats, _ = build_features(
        {
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
        }
    )
    assert speed == "blitz"
    assert feats["ply"] == 2
    assert feats["mat_total"] == 78
    assert feats["n_legal"] == 20


if __name__ == "__main__":
    test_speed_of_buckets()
    test_model_speed_rejects_rapid()
    test_build_starting_position_blitz()
    test_build_after_e4()
    print("ok")
