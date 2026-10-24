#!/usr/bin/env python3
"""Rebuild move_outcomes (Lichess judgments + mover game result) in Tiger.

    python -m annotate.build_outcomes
"""

from __future__ import annotations

import argparse
from pathlib import Path

from ingest.load_tiger import SERVICE, tiger_sql_file, tiger_uri
import psycopg


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--service", default=SERVICE)
    parser.add_argument("--sql-dir", type=Path, default=Path("sql"))
    args = parser.parse_args()
    tiger_sql_file(args.service, args.sql_dir / "008_outcomes.sql")
    uri = tiger_uri(args.service)
    with psycopg.connect(uri) as conn:
        n = conn.execute("SELECT COUNT(*) FROM move_outcomes").fetchone()[0]
        labelled = conn.execute(
            "SELECT COUNT(*) FROM move_outcomes WHERE blunder IS NOT NULL"
        ).fetchone()[0]
        blunders = conn.execute(
            "SELECT COUNT(*) FROM move_outcomes WHERE blunder IS TRUE"
        ).fetchone()[0]
        print(f"move_outcomes={n} with_judgment={labelled} blunders={blunders}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
