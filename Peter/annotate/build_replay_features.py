#!/usr/bin/env python3
"""Replay every stored game: FEN-before, material, prev thinks, log clocks.

    python -m annotate.build_replay_features
"""

from __future__ import annotations

import argparse
import csv
import io
from collections import defaultdict
from pathlib import Path

import psycopg

from annotate.fen_replay import replay_game
from ingest.load_tiger import SERVICE, tiger_sql_file, tiger_uri

COLUMNS = [
    "game_id",
    "ply",
    "fen_before",
    "material_white",
    "material_black",
    "material_total",
    "material_advantage_white",
    "material_advantage_mover",
    "prev_think_white_s",
    "prev_think_black_s",
    "clk_before_s",
    "opp_clk_s",
    "log_clk_before",
    "log_opp_clk",
]


def fetch_games(conn: psycopg.Connection) -> list[tuple]:
    return conn.execute(
        "SELECT game_id, base, inc FROM games ORDER BY game_id"
    ).fetchall()


def fetch_moves(conn: psycopg.Connection) -> dict[str, list[dict]]:
    rows = conn.execute(
        """
        SELECT game_id, ply, color, san, clk_after_s
        FROM moves
        ORDER BY game_id, ply
        """
    ).fetchall()
    by_game: dict[str, list[dict]] = defaultdict(list)
    for game_id, ply, color, san, clk_after in rows:
        by_game[game_id].append(
            {
                "ply": ply,
                "color": color,
                "san": san,
                "clk_after_s": clk_after,
            }
        )
    return by_game


def build_rows(conn: psycopg.Connection) -> tuple[list[dict], dict[str, int]]:
    moves = fetch_moves(conn)
    rows: list[dict] = []
    stats = {"games": 0, "ok": 0, "stopped_early": 0, "empty": 0}
    for game_id, base, inc in fetch_games(conn):
        stats["games"] += 1
        game_moves = moves.get(game_id, [])
        if not game_moves:
            stats["empty"] += 1
            continue
        produced = list(
            replay_game(game_id=game_id, base=float(base), inc=float(inc), moves=game_moves)
        )
        rows.extend(produced)
        if len(produced) == len(game_moves):
            stats["ok"] += 1
        else:
            stats["stopped_early"] += 1
    return rows, stats


def copy_replay(conn: psycopg.Connection, rows: list[dict]) -> None:
    conn.execute("TRUNCATE move_replay")
    conn.commit()
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        out = dict(row)
        for key in ("prev_think_white_s", "prev_think_black_s"):
            if out.get(key) is None:
                out[key] = ""
        writer.writerow({k: out[k] for k in COLUMNS})
    buf.seek(0)
    with conn.cursor() as cur:
        with cur.copy(
            "COPY move_replay ("
            + ", ".join(COLUMNS)
            + ") FROM STDIN WITH (FORMAT csv, HEADER true, NULL '')"
        ) as copy:
            copy.write(buf.getvalue())
    conn.commit()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--service", default=SERVICE)
    parser.add_argument("--sql-dir", type=Path, default=Path("sql"))
    args = parser.parse_args()
    tiger_sql_file(args.service, args.sql_dir / "006_replay.sql")
    uri = tiger_uri(args.service)
    with psycopg.connect(uri) as conn:
        rows, stats = build_rows(conn)
        copy_replay(conn, rows)
        stored = conn.execute("SELECT COUNT(*) FROM move_replay").fetchone()[0]
    print(
        f"games={stats['games']} full_replay={stats['ok']} "
        f"stopped_early={stats['stopped_early']} empty={stats['empty']} "
        f"move_replay={stored}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
