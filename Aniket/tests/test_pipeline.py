"""Run with:  python -m pytest -q"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from oracle.eda import eta  # noqa: E402
from oracle.features import (FEATURE_COLS, add_clock_features, add_eval_features,  # noqa: E402
                             add_game_context, add_window_labels, build_tables, load_pgn, win_pct)
from oracle.fetch import GameFilter, fetch_by_speed  # noqa: E402
from oracle.pgn import parse_time_control, speed_of  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "mini.pgn"


@pytest.fixture(scope="module")
def tables():
    return build_tables(FIX, progress=False)


def row(m, gid, ply):
    return m[(m.game_id == gid) & (m.ply == ply)].iloc[0]


def test_time_control_and_speed():
    assert parse_time_control("180+2") == (180, 2)
    assert speed_of(60, 0) == "bullet" and speed_of(180, 2) == "blitz" and speed_of(1800, 0) == "classical"
    assert np.isnan(parse_time_control("-")[0])


def test_games_table(tables):
    g, _ = tables
    assert list(g.game_id) == ["fixt0001", "fixt0002", "fixt0003", "fixt0004"]
    assert np.isnan(g.set_index("game_id").loc["fixt0002", "black_elo"])  # '?' -> NaN
    assert g.has_eval.tolist() == [True, False, False, False]


def test_win_pct_matches_guide_worked_example():
    # +1.40 -> White 62.6%, +6.90 -> White 92.7%, Black drops 30.1 pts
    assert win_pct(140) == pytest.approx(62.6, abs=0.05)
    assert win_pct(690) == pytest.approx(92.7, abs=0.05)
    assert (100 - win_pct(140)) - (100 - win_pct(690)) == pytest.approx(30.1, abs=0.1)


def test_clock_features(tables):
    _, m = tables
    r = row(m, "fixt0001", 3)  # 2. Bc4 {clk 2:58}, 180+2: spent = 180 - 178 + 2
    assert r.clock_self == 180 and r.clk_after == 178 and r.time_spent == 4
    assert np.isnan(row(m, "fixt0001", 1).time_spent)  # first move untimed
    r = row(m, "fixt0002", 7)
    assert r.time_spent == 15 and r.clock_opp == 57 and r.prev_opp_spent == 2
    assert row(m, "fixt0003", 1).berserk and not row(m, "fixt0003", 2).berserk


def test_zero_base_time_control():
    g, mv = load_pgn(FIX, progress=False)
    g.loc[g.game_id == "fixt0001", "base_s"] = 0.0  # e.g. a 0+1 game
    m = add_clock_features(mv, g)
    assert np.isfinite(m[["frac_self", "clock_ratio"]].dropna()).all().all()
    assert m.loc[m.game_id == "fixt0001", "frac_self"].isna().all()


def test_blunder_label(tables):
    _, m = tables
    r = row(m, "fixt0001", 6)  # 3...Nf6?? allows mate in 1
    assert r.blunder == 1 and r.wp_after == 0
    assert row(m, "fixt0001", 7).last_swing == pytest.approx(r.wp_drop)
    assert m.loc[m.game_id == "fixt0001", "blunder"].iloc[1:5].eq(0).all()


def test_blunder_next5(tables):
    _, m = tables
    g1 = m[m.game_id == "fixt0001"].set_index("ply")["blunder_next5"]
    assert g1[[2, 4, 6]].eq(1).all()  # black's moves before/at 3...Nf6??
    assert g1[[1, 3, 5, 7]].eq(0).all()  # ply 1 and the mating move count as 0, game end is not censoring
    assert m.loc[m.game_id == "fixt0002", "blunder_next5"].isna().all()  # no evals -> no label


def test_board_features(tables):
    _, m = tables
    r = row(m, "fixt0001", 1)
    assert r.n_legal == 20 and r.mat_total == 78 and r.mat_diff == 0 and r.n_captures == 0
    r = row(m, "fixt0001", 5)  # before 3.Qh5: Bxf7+ is the only capture and only check
    assert r.n_captures == 1 and r.n_checks == 1


def test_no_peeking():
    """Changing ply k's own clock and eval must not change ply k's features."""
    g, mv = load_pgn(FIX, progress=False)

    def feats(mv_):
        m = add_game_context(add_window_labels(add_eval_features(add_clock_features(mv_, g))), g)
        return m.set_index(["game_id", "ply"], drop=False)[[c for c in FEATURE_COLS if c in m]]

    base = feats(mv)
    mv2 = mv.copy()
    k = (mv2.game_id == "fixt0001") & (mv2.ply == 6)
    mv2.loc[k, "clk_s"] = 10.0
    mv2.loc[k, ["eval_cp", "eval_mate"]] = [0.0, np.nan]
    pd.testing.assert_series_equal(base.loc[("fixt0001", 6)], feats(mv2).loc[("fixt0001", 6)])


def test_eta():
    rng = np.random.default_rng(0)
    x = pd.Series(rng.uniform(-1, 1, 20000))
    assert eta(x, x**2 + rng.normal(0, 0.05, len(x))) > 0.9  # catches a U-shape a correlation would miss
    assert eta(x, pd.Series(rng.normal(size=len(x)))) < 0.05


def test_fetch_by_speed(tmp_path):
    zstd = pytest.importorskip("zstandard")
    text = FIX.read_text()
    cut = text.index("[Event", 10)  # two frames, like the real dumps
    c = zstd.ZstdCompressor()
    src = tmp_path / "x.pgn.zst"
    src.write_bytes(c.compress(text[:cut].encode()) + c.compress(text[cut:].encode()))
    speeds = ("bullet", "blitz", "classical")
    st = fetch_by_speed(str(src), tmp_path, 10, speeds, flt=GameFilter(min_plies=4, require_eval=False), progress=False)
    assert st.scanned == 4 and st.kept == {"bullet": 1, "blitz": 2, "classical": 0}  # rapid game skipped
    st = fetch_by_speed(str(src), tmp_path, 10, speeds, flt=GameFilter(min_plies=4), progress=False)
    assert st.kept["blitz"] == 1 and (tmp_path / "blitz" / "games.pgn").read_text().count("[Event") == 1
