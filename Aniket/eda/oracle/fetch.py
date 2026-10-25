"""Stream a Lichess monthly dump and keep N games of each speed in ONE pass.

A month of standard games is ~30 GB compressed, but .zst decompresses as a stream,
so we read from the HTTP response and stop as soon as every speed has N games.

    URL ──► HTTP stream ──► zstd ──► games ──► filter ──► data/<speed>/games.pgn
                                                (stop when all quotas are full)

Games in a monthly file are in time order. Classical analysed games are rare
(~1 in 600), so filling classical takes ~12M games (several days of the month);
bullet/blitz would fill in the first hour. `every` keeps only every k-th match of
the fast speeds so all three samples cover roughly the same days.
"""
from __future__ import annotations

import io
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from .pgn import iter_raw_games, parse_time_control, speed_of


@dataclass
class GameFilter:
    require_clock: bool = True
    require_eval: bool = True   # labels need engine evals
    min_plies: int = 10
    drop_terminations: tuple[str, ...] = ("Abandoned", "Rules infraction")

    def keep(self, headers: dict, movetext: str) -> bool:
        if headers.get("Termination", "") in self.drop_terminations:
            return False
        if self.require_clock and "%clk" not in movetext:
            return False
        if self.require_eval and "%eval" not in movetext:
            return False
        # cheap ply count: one '%clk' per ply if clocks exist, else count move numbers
        n = movetext.count("%clk") or movetext.count(". ") * 2
        return n >= self.min_plies


@dataclass
class FetchStats:
    scanned: int = 0
    kept: dict = field(default_factory=dict)
    seconds: float = 0.0


def open_text_stream(source: str) -> Iterator[str]:
    """Yield text lines from a URL or local .pgn / .pgn.zst file."""
    import zstandard as zstd

    if source.startswith(("http://", "https://")):
        import requests

        resp = requests.get(source, stream=True, timeout=60)
        resp.raise_for_status()
        raw = resp.raw
    else:
        p = Path(source)
        if p.suffix != ".zst":
            with open(p, encoding="utf-8") as fh:
                yield from fh
            return
        raw = open(p, "rb")
        resp = None

    dctx = zstd.ZstdDecompressor()
    reader = dctx.stream_reader(raw, read_size=1 << 20, read_across_frames=True)
    text = io.TextIOWrapper(io.BufferedReader(reader, buffer_size=1 << 20), encoding="utf-8", errors="replace")
    try:
        yield from text
    finally:
        text.close()
        if resp is not None:
            resp.close()  # drop the connection: we never read the rest of the file
        else:
            raw.close()


def fetch_by_speed(source: str, out_dir: Path, n_games: int, speeds: tuple[str, ...],
                   every: dict | None = None, flt: GameFilter | None = None,
                   progress: bool = True) -> FetchStats:
    """Write the first `n_games` games of each speed passing `flt` to out_dir/<speed>/games.pgn."""
    flt = flt or GameFilter()
    every = every or {}
    stats = FetchStats(kept={s: 0 for s in speeds})
    matched = {s: 0 for s in speeds}
    outs = {}
    for s in speeds:
        (out_dir / s).mkdir(parents=True, exist_ok=True)
        outs[s] = open(out_dir / s / "games.pgn", "w", encoding="utf-8")
    bar = None
    if progress:
        try:
            from tqdm import tqdm
            bar = tqdm(total=n_games * len(speeds), unit="game", desc="kept")
        except ImportError:
            pass

    t0 = time.time()
    lines = open_text_stream(source)
    try:
        for headers, header_text, movetext in iter_raw_games(lines):
            stats.scanned += 1
            s = speed_of(*parse_time_control(headers.get("TimeControl", "-")))
            if s not in outs or stats.kept[s] >= n_games or not flt.keep(headers, movetext):
                continue
            matched[s] += 1
            if (matched[s] - 1) % every.get(s, 1):
                continue
            outs[s].write(header_text + "\n\n" + movetext + "\n\n")
            stats.kept[s] += 1
            if bar:
                bar.update(1)
                if sum(stats.kept.values()) % 500 == 0:
                    bar.set_postfix(scanned=f"{stats.scanned / 1e6:.1f}M", **stats.kept)
            if all(k >= n_games for k in stats.kept.values()):
                break
    finally:
        lines.close()  # closes the HTTP connection early
        for f in outs.values():
            f.close()
        if bar:
            bar.close()
    stats.seconds = time.time() - t0
    return stats
