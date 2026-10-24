#!/usr/bin/env python3
"""Sanity-check ingest CSV before COPY into Tiger Data."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path


def load_games(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_moves(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def report(games: list[dict[str, str]], moves: list[dict[str, str]]) -> int:
    errors = 0
    game_ids = {row["game_id"] for row in games}
    if len(game_ids) != len(games):
        print("ERROR: duplicate game_id in games.csv")
        errors += 1

    by_game: dict[str, list[dict[str, str]]] = defaultdict(list)
    orphan = 0
    for row in moves:
        if row["game_id"] not in game_ids:
            orphan += 1
        by_game[row["game_id"]].append(row)
    if orphan:
        print(f"ERROR: {orphan} move rows with unknown game_id")
        errors += 1

    missing_moves = [gid for gid in game_ids if gid not in by_game]
    if missing_moves:
        print(f"ERROR: {len(missing_moves)} games have no moves")
        errors += 1

    games_by_id = {row["game_id"]: row for row in games}
    ply_gaps = 0
    color_mismatch = 0
    clocks_by_player: list[float] = []
    evals: list[int] = []
    negative_think_proxy = 0
    for gid, rows in by_game.items():
        rows = sorted(rows, key=lambda item: int(item["ply"]))
        expected = 1
        last_clk: dict[str, float | None] = {"w": None, "b": None}
        game = games_by_id[gid]
        base = float(game["base"])
        inc = float(game["inc"])
        for row in rows:
            ply = int(row["ply"])
            color = row["color"]
            if ply != expected:
                ply_gaps += 1
            expected = ply + 1
            if color != ("w" if ply % 2 == 1 else "b"):
                color_mismatch += 1
            clk = float(row["clk_after_s"])
            evals.append(int(row["eval_cp"]))
            clocks_by_player.append(clk)
            prev = last_clk[color]
            before = base if prev is None else prev
            think = before - clk + inc
            if think < -0.05:
                negative_think_proxy += 1
            last_clk[color] = clk

    if ply_gaps:
        print(f"WARN: {ply_gaps} ply sequence gaps (last move often dropped for missing eval)")
    if color_mismatch:
        print(f"ERROR: {color_mismatch} color/ply mismatches")
        errors += 1

    print(f"games={len(games)} moves={len(moves)}")
    if clocks_by_player:
        print(
            f"clk_after_s min={min(clocks_by_player):.2f} "
            f"median={sorted(clocks_by_player)[len(clocks_by_player)//2]:.2f} "
            f"max={max(clocks_by_player):.2f}"
        )
    if evals:
        print(f"eval_cp min={min(evals)} max={max(evals)}")
    print(f"negative think_s proxy (before SQL)={negative_think_proxy}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", type=Path, default=Path("data"))
    args = parser.parse_args()
    games = load_games(args.dir / "games.csv")
    moves = load_moves(args.dir / "moves.csv")
    errors = report(games, moves)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
