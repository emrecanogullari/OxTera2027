#!/usr/bin/env python3
"""Fill best_next_move from fen_before. Never deletes database rows."""

from __future__ import annotations

import argparse
import math
import os
import subprocess
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import chess
import psycopg

from ingest.load_tiger import tiger_uri

SERVICE = "db-44476"
DEPTH = 12
MULTIPV = 4
NEAR_WP = 5.0
MATE_CP = 10000
SCHEMA = Path(__file__).resolve().parents[1] / "sql" / "009_best_next_move.sql"
DEFAULT_ENGINE = Path(__file__).resolve().parents[1] / ".tools" / "stockfish"

READ_SQL = """
SELECT
  e.game_id,
  e.ply,
  m.color,
  m.san,
  e.fen_before,
  r.material_white,
  r.material_black,
  r.material_total,
  r.material_advantage_white,
  r.material_advantage_mover,
  r.prev_think_white_s,
  r.prev_think_black_s,
  r.clk_before_s,
  r.opp_clk_s,
  r.log_clk_before,
  r.log_opp_clk,
  mm.elo,
  mm.opp_elo,
  mm.elo_diff,
  mm.rating_band,
  mm.base,
  mm.inc,
  mm.tc,
  mm.clk_frac,
  mm.clk_frac_band,
  mm.ply_phase,
  mm.premove
FROM engine_features e
JOIN moves m USING (game_id, ply)
JOIN move_replay r USING (game_id, ply)
JOIN move_metrics mm USING (game_id, ply)
WHERE TRUE
ORDER BY e.game_id, e.ply
"""

INSERT_SQL = """
INSERT INTO best_next_move (
  game_id, ply, color, san, fen_before,
  material_white, material_black, material_total,
  material_advantage_white, material_advantage_mover,
  prev_think_white_s, prev_think_black_s,
  clk_before_s, opp_clk_s, log_clk_before, log_opp_clk,
  elo, opp_elo, elo_diff, rating_band, base, inc, tc,
  clk_frac, clk_frac_band, ply_phase, premove,
  best_possible_move, second_best_move,
  best_possible_move_wp, second_best_move_wp,
  gap, n_near_best, n_legal_moves
) VALUES (
  %s, %s, %s, %s, %s,
  %s, %s, %s, %s, %s,
  %s, %s,
  %s, %s, %s, %s,
  %s, %s, %s, %s, %s, %s, %s,
  %s, %s, %s, %s,
  %s, %s, %s, %s, %s, %s, %s
)
ON CONFLICT (game_id, ply) DO UPDATE SET
  best_possible_move = EXCLUDED.best_possible_move,
  second_best_move = EXCLUDED.second_best_move,
  best_possible_move_wp = EXCLUDED.best_possible_move_wp,
  second_best_move_wp = EXCLUDED.second_best_move_wp,
  gap = EXCLUDED.gap,
  n_near_best = EXCLUDED.n_near_best,
  n_legal_moves = EXCLUDED.n_legal_moves
"""


def wp_from_cp(cp: float) -> float:
    clamped = max(-MATE_CP, min(MATE_CP, cp))
    return 50.0 + 50.0 * (2.0 / (1.0 + math.exp(-0.00368208 * clamped)) - 1.0)


class Engine:
    def __init__(self, path: str) -> None:
        self.path = path
        self.proc = subprocess.Popen(
            [path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        self._send("uci")
        self._wait("uciok")
        self._send("setoption name Threads value 1")
        self._send("setoption name Hash value 64")
        self._send(f"setoption name MultiPV value {MULTIPV}")
        self._send("isready")
        self._wait("readyok")

    def close(self) -> None:
        if self.proc.poll() is None:
            self._send("quit")
            self.proc.wait(timeout=5)

    def _send(self, line: str) -> None:
        assert self.proc.stdin is not None
        self.proc.stdin.write(line + "\n")
        self.proc.stdin.flush()

    def _wait(self, token: str) -> None:
        assert self.proc.stdout is not None
        while True:
            line = self.proc.stdout.readline()
            if line == "":
                raise RuntimeError("stockfish closed")
            if token in line:
                return

    def analyse(self, fen: str) -> dict:
        legal = chess.Board(fen).legal_moves.count()
        self._send("ucinewgame")
        self._send("isready")
        self._wait("readyok")
        self._send(f"position fen {fen}")
        self._send(f"go depth {DEPTH}")
        assert self.proc.stdout is not None
        lines: dict[int, tuple[float, str]] = {}
        while True:
            raw = self.proc.stdout.readline()
            if raw == "":
                raise RuntimeError("stockfish closed during search")
            if raw.startswith("bestmove"):
                break
            parts = raw.split()
            if "multipv" not in parts or "pv" not in parts or "score" not in parts:
                continue
            if parts[0] != "info" or "depth" not in parts:
                continue
            depth = int(parts[parts.index("depth") + 1])
            if depth != DEPTH:
                continue
            multipv = int(parts[parts.index("multipv") + 1])
            score_at = parts.index("score")
            kind = parts[score_at + 1]
            value = int(parts[score_at + 2])
            cp = value * MATE_CP if kind == "mate" and value > 0 else (
                -MATE_CP if kind == "mate" else float(value)
            )
            move = parts[parts.index("pv") + 1]
            lines[multipv] = (cp, move)
        ordered = [lines[i] for i in sorted(lines)]
        best_move = ordered[0][1] if ordered else None
        second_move = ordered[1][1] if len(ordered) > 1 else None
        best_wp = wp_from_cp(ordered[0][0]) if ordered else None
        second_wp = wp_from_cp(ordered[1][0]) if len(ordered) > 1 else None
        gap = None if best_wp is None or second_wp is None else best_wp - second_wp
        near = 0
        if best_wp is not None:
            for cp, _move in ordered:
                if best_wp - wp_from_cp(cp) <= NEAR_WP:
                    near += 1
        return {
            "best_possible_move": best_move,
            "second_best_move": second_move,
            "best_possible_move_wp": best_wp,
            "second_best_move_wp": second_wp,
            "gap": gap,
            "n_near_best": near,
            "n_legal_moves": legal,
        }


_ENGINE: Engine | None = None


def _init_worker(path: str) -> None:
    global _ENGINE
    _ENGINE = Engine(path)


def _analyse_row(row: tuple) -> tuple | None:
    global _ENGINE
    assert _ENGINE is not None
    try:
        result = _ENGINE.analyse(row[4])
    except Exception as exc:
        print(f"skip {row[0]} {row[1]} {exc}", flush=True)
        try:
            _ENGINE.close()
        except Exception:
            pass
        _ENGINE = Engine(_ENGINE.path)
        return None
    return row + (
        result["best_possible_move"],
        result["second_best_move"],
        result["best_possible_move_wp"],
        result["second_best_move_wp"],
        result["gap"],
        result["n_near_best"],
        result["n_legal_moves"],
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--service", default=SERVICE)
    parser.add_argument("--engine", default=str(DEFAULT_ENGINE))
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    workers = args.workers or max(1, (os.cpu_count() or 2) - 1)

    tools = str(DEFAULT_ENGINE.parent)
    os.environ["PATH"] = tools + os.pathsep + os.environ.get("PATH", "")
    uri = tiger_uri(args.service)
    with psycopg.connect(
        uri,
        keepalives=1,
        keepalives_idle=30,
        keepalives_interval=10,
        keepalives_count=5,
    ) as conn:
        conn.execute(SCHEMA.read_text(encoding="utf-8"))
        conn.commit()
        rows = conn.execute(READ_SQL).fetchall()
        if args.limit:
            rows = rows[: args.limit]
        print(f"pending {len(rows)} workers {workers}", flush=True)
        if not rows:
            return 0
        done = 0
        with ProcessPoolExecutor(
            max_workers=workers,
            initializer=_init_worker,
            initargs=(args.engine,),
        ) as pool:
            batch: list[tuple] = []
            for item in pool.map(_analyse_row, rows, chunksize=8):
                if item is None:
                    continue
                batch.append(item)
                if len(batch) >= 50:
                    with conn.cursor() as cur:
                        cur.executemany(INSERT_SQL, batch)
                    conn.commit()
                    done += len(batch)
                    print(f"wrote {done}", flush=True)
                    batch.clear()
            if batch:
                with conn.cursor() as cur:
                    cur.executemany(INSERT_SQL, batch)
                conn.commit()
                done += len(batch)
                print(f"wrote {done}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
