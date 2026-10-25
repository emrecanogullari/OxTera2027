#!/usr/bin/env python3
"""COPY local CSVs into Tiger Cloud and rebuild metrics + lookup_budgets."""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

import psycopg

TIGER = Path.home() / "AppData/Local/Programs/TigerCLI/tiger.exe"
SERVICE = "gethdbqtlo"
LOOKUP_VERSION = "full-2026-08-09"

# Child tables first so TRUNCATE ... CASCADE is unnecessary if FKs block.
TRUNCATE_TABLES = (
    "lookup_budgets",
    "best_next_move",
    "move_outcomes",
    "engine_features",
    "move_replay",
    "move_metrics",
    "moves",
    "games",
)


def tiger_exe() -> str:
    return str(TIGER) if TIGER.exists() else "tiger"


def tiger_uri(service: str) -> str:
    out = subprocess.check_output(
        [tiger_exe(), "db", "uri", service, "--with-password"],
        text=True,
    )
    return out.strip().splitlines()[-1]


def tiger_sql_file(service: str, path: Path) -> None:
    subprocess.check_call([tiger_exe(), "db", "query", service, "-f", str(path)])


def copy_csv(conn: psycopg.Connection, table: str, csv_path: Path) -> None:
    with csv_path.open("r", encoding="utf-8") as handle, conn.cursor() as cur:
        with cur.copy(f"COPY {table} FROM STDIN WITH (FORMAT csv, HEADER true)") as copy:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                copy.write(chunk)
    conn.commit()


def render_lookup_sql(sql_dir: Path, version: str) -> Path:
    template = (sql_dir / "005_lookup.sql").read_text(encoding="utf-8")
    # Replace the probe version string used in the checked-in SQL.
    rendered = template.replace("probe-1000-2026-09", version)
    tmp = Path(tempfile.mkstemp(prefix="lookup_", suffix=".sql")[1])
    tmp.write_text(rendered, encoding="utf-8")
    return tmp


def export_lookup(conn: psycopg.Connection, dest: Path, version: str) -> int:
    dest.parent.mkdir(parents=True, exist_ok=True)
    row = conn.execute(
        """
        SELECT COALESCE(
          json_object_agg(
            tc || '|' || rating_band::text || '|' || ply_phase || '|'
              || clk_frac_band || '|' || gap_band,
            json_build_object(
              'n', n,
              'p50', p50_s,
              'p75', p75_s,
              'budget', budget_s
            )
          ),
          '{}'::json
        )
        FROM lookup_budgets
        WHERE version = %s
        """,
        (version,),
    ).fetchone()
    payload = row[0]
    if isinstance(payload, str):
        payload = json.loads(payload)
    dest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    count = conn.execute(
        "SELECT COUNT(*) FROM lookup_budgets WHERE version = %s",
        (version,),
    ).fetchone()[0]
    return int(count)


def existing_relations(conn: psycopg.Connection) -> set[str]:
    rows = conn.execute(
        """
        SELECT relname FROM pg_class
        WHERE relkind = 'r' AND relnamespace = 'public'::regnamespace
        """
    ).fetchall()
    return {r[0] for r in rows}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--service", default=SERVICE)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--sql-dir", type=Path, default=Path("sql"))
    parser.add_argument("--lookup-version", default=LOOKUP_VERSION)
    parser.add_argument(
        "--lookup-json",
        type=Path,
        default=Path("extension/lookup_budgets.json"),
    )
    args = parser.parse_args()
    tiger_sql_file(args.service, args.sql_dir / "001_schema.sql")
    uri = tiger_uri(args.service)
    with psycopg.connect(uri) as conn:
        present = existing_relations(conn)
        to_wipe = [t for t in TRUNCATE_TABLES if t in present]
        if to_wipe:
            conn.execute("TRUNCATE " + ", ".join(to_wipe))
            conn.commit()
        copy_csv(
            conn,
            "games (game_id, white_elo, black_elo, base, inc, result, termination, utc_date)",
            args.data_dir / "games.csv",
        )
        copy_csv(
            conn,
            "moves (game_id, ply, color, san, clk_after_s, eval_cp, is_mate)",
            args.data_dir / "moves.csv",
        )
    tiger_sql_file(args.service, args.sql_dir / "004_metrics.sql")
    tiger_sql_file(args.service, args.sql_dir / "003_indexes.sql")
    lookup_sql = render_lookup_sql(args.sql_dir, args.lookup_version)
    try:
        tiger_sql_file(args.service, lookup_sql)
    finally:
        lookup_sql.unlink(missing_ok=True)
    with psycopg.connect(uri) as conn:
        n_games = conn.execute("SELECT COUNT(*) FROM games").fetchone()[0]
        n_moves = conn.execute("SELECT COUNT(*) FROM moves").fetchone()[0]
        n_metrics = conn.execute("SELECT COUNT(*) FROM move_metrics").fetchone()[0]
        n_lookup = export_lookup(conn, args.lookup_json, args.lookup_version)
        print(
            f"games={n_games} moves={n_moves} metrics={n_metrics} "
            f"lookup_cells={n_lookup} wrote {args.lookup_json}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
