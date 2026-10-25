"""Step 4 (Tiger): pull Peter's Tiger database (rated blitz games + Stockfish's top moves) -> data/tiger/

  python scripts/4_tiger_fetch.py             # ~1-2 min; needs the Tiger CLI, logged in (see oracle/tiger.py)
  python scripts/4_tiger_fetch.py --refresh   # pull the tables again (default: reuse data/tiger/db_*.parquet)

Writes data/tiger/:
  db_games.parquet, db_moves.parquet, db_best_next_move.parquet, db_move_metrics.parquet   the tables as pulled
  games.pgn                      those games as Lichess PGN (SAN, then clock + eval after every move)
  games.parquet, moves.parquet   our tables, built from games.pgn by the same code as 2_build.py, plus the sf_*
                                 Stockfish features (oracle/tiger.py) joined on (game_id, ply)
Games that don't fully replay in the database (a move was dropped at ingest) are left out.
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

from oracle.config import DATA  # noqa: E402
from oracle.features import build_tables  # noqa: E402
from oracle.tiger import SF_FEATURES, add_stockfish, query, to_pgn  # noqa: E402

OUT = DATA / "tiger"
SQL = {
    "games": "SELECT game_id, white_elo, black_elo, base, inc, result, termination, utc_date FROM games",
    "moves": "SELECT game_id, ply, color, san, clk_after_s, eval_cp, is_mate FROM moves",
    "best_next_move": "SELECT game_id, ply, fen_before, best_possible_move, second_best_move, best_possible_move_wp, "
                      "second_best_move_wp, gap, n_near_best, n_legal_moves FROM best_next_move",
    "move_metrics": "SELECT game_id, ply, think_s FROM move_metrics",  # only to check our think times against
}


def pull(refresh: bool) -> dict[str, pd.DataFrame]:
    OUT.mkdir(parents=True, exist_ok=True)
    tables = {}
    for name, sql in SQL.items():
        p = OUT / f"db_{name}.parquet"
        if p.exists() and not refresh:
            tables[name] = pd.read_parquet(p)
            continue
        t0 = time.time()
        tables[name] = query(sql)
        tables[name].to_parquet(p, index=False)
        print(f"  pulled {name:15s} {len(tables[name]):>8,} rows ({time.time() - t0:.0f}s)")
    return tables


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--refresh", action="store_true", help="pull the tables again")
    a = ap.parse_args()
    t = pull(a.refresh)

    # Keep games where every move has a Stockfish row (= the game replayed from SAN in the database)
    n_moves = t["moves"].groupby("game_id").size()
    n_sf = t["best_next_move"].groupby("game_id").size().reindex(n_moves.index, fill_value=0)
    ok = set(n_moves.index[n_sf == n_moves])
    print(f"{len(ok):,} of {len(n_moves):,} games have Stockfish on every move ({len(n_moves) - len(ok)} left out)")
    games = t["games"][t["games"]["game_id"].isin(ok)]
    moves = t["moves"][t["moves"]["game_id"].isin(ok)]
    (OUT / "games.pgn").write_text(to_pgn(games, moves), encoding="utf-8")

    g, m = build_tables(OUT / "games.pgn")
    m = add_stockfish(m, t["best_next_move"])

    # Checks: our replay vs the database's FEN, our think times vs the database's
    both = m["n_legal_moves"].notna() & m["n_legal"].notna()
    print(f"legal-move count, our replay = database FEN: {(m.loc[both, 'n_legal'] == m.loc[both, 'n_legal_moves']).mean():.2%} "
          f"of {both.sum():,} moves")
    th = m.merge(t["move_metrics"], on=["game_id", "ply"], how="left")
    th = th[th["time_spent"].notna()]
    print(f"think time, ours = database think_s: {((th['time_spent'] - th['think_s'].clip(lower=0)).abs() < 0.01).mean():.2%} "
          f"of {len(th):,} timed moves")
    for c in SF_FEATURES:
        print(f"  {c:16s} filled on {m[c].notna().mean():.1%} of moves, median {m[c].median():.2f}")

    g.to_parquet(OUT / "games.parquet", index=False)
    m.to_parquet(OUT / "moves.parquet", index=False)
    lab = m["blunder"].notna()
    print(f"\n{len(g):,} games, {len(m):,} moves, {lab.sum():,} labelled, blunder rate {m.loc[lab, 'blunder'].mean():.2%}, "
          f"blunder_next5 rate {m['blunder_next5'].mean():.2%}, median think {m['time_spent'].median():.0f}s -> {OUT}")


if __name__ == "__main__":
    main()
