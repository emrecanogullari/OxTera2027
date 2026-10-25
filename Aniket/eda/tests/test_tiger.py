"""The Tiger database path (oracle/tiger.py), offline. Run with:  python -m pytest -q"""
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from oracle.features import FEATURE_COLS, LABEL_COLS, build_tables, load_pgn, win_pct  # noqa: E402
from oracle.tiger import MATE_CP, add_stockfish, lichess_scale, to_pgn  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "mini.pgn"


def db_wp(cp):
    """Win% as the database stores it: no cap."""
    return 50 + 50 * (2 / (1 + math.exp(-0.00368208 * cp)) - 1)


def test_pgn_round_trip(tmp_path):
    """Game -> database rows (as Peter's ingest stores them) -> PGN -> our features: same as from the original."""
    g, p = load_pgn(FIX, progress=False)
    g, p = g[g.game_id == "fixt0001"], p[p.game_id == "fixt0001"]
    p = p[(p.eval_cp.notna() | p.eval_mate.notna()) & p.clk_s.notna()]  # ingest drops moves without eval or clock
    mate = p.eval_mate.notna()
    moves = pd.DataFrame({"game_id": p.game_id, "ply": p.ply, "san": p.san, "clk_after_s": p.clk_s,
                          "eval_cp": np.where(mate, np.sign(p.eval_mate) * MATE_CP, p.eval_cp).round().astype(int),
                          "is_mate": mate})
    games = pd.DataFrame({"game_id": g.game_id, "white_elo": g.white_elo.astype(int), "black_elo": g.black_elo.astype(int),
                          "base": g.base_s.astype(int), "inc": g.inc_s.astype(int), "result": g.result,
                          "termination": g.termination, "utc_date": g.utc.dt.date})
    (tmp_path / "db.pgn").write_text(to_pgn(games, moves))

    cols = ["game_id"] + FEATURE_COLS + LABEL_COLS
    _, ref = build_tables(FIX, progress=False)
    ref = ref.loc[(ref.game_id == "fixt0001") & ref.ply.isin(moves.ply), cols].reset_index(drop=True)
    _, got = build_tables(tmp_path / "db.pgn", progress=False)
    assert len(moves) == 6 and len(got) == 6  # the final mating move has no eval: dropped, as in the database
    pd.testing.assert_frame_equal(got[cols].reset_index(drop=True), ref, check_dtype=False)


def test_lichess_scale():
    cps = [0, 300, -800, 1500, -3000]
    got = lichess_scale(pd.Series([db_wp(c) for c in cps] + [db_wp(MATE_CP), db_wp(-MATE_CP)]))
    np.testing.assert_allclose(got[:5], win_pct(np.array(cps, float)), atol=1e-6)  # cap at +-1000 cp, like ours
    assert got.iloc[5] == 100 and got.iloc[6] == 0  # mate -> 100 / 0, like ours


def test_add_stockfish():
    start = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    scandi = "rnbqkbnr/ppp1pppp/8/3p4/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2"
    m = pd.DataFrame({"game_id": ["a", "a"], "ply": [1, 3], "wp_self": [np.nan, 55.0]})
    bnm = pd.DataFrame({"game_id": ["a", "a"], "ply": [1, 3], "fen_before": [start, scandi],
                        "best_possible_move": ["e2e4", "e4d5"], "second_best_move": ["d2d4", "b1c3"],
                        "best_possible_move_wp": [52.94, 58.0], "second_best_move_wp": [52.12, 51.0],
                        "gap": [0.83, 7.0], "n_near_best": [4, 1], "n_legal_moves": [20, 31]})
    out = add_stockfish(m, bnm)
    assert out.sf_best_capture.tolist() == [0.0, 1.0] and out.sf_best_check.tolist() == [0.0, 0.0]
    assert np.isnan(out.sf_vs_lichess[0])  # ply 1 has no Lichess eval before it
    assert abs(out.sf_vs_lichess[1] - 3.0) < 1e-9  # 58 vs 55, both inside the +-1000 cp cap
    assert out.sf_gap.tolist() == [0.83, 7.0] and out.sf_n_near_best.tolist() == [4.0, 1.0]
