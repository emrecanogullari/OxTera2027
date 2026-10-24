from __future__ import annotations

import io
import unittest
from pathlib import Path

from ingest.ingest import ingest, parse_clock, parse_eval, parse_moves

FIXTURE = Path(__file__).parent / "fixtures" / "sample.pgn"


class EvalAndClock(unittest.TestCase):
    def test_clock_hms(self) -> None:
        self.assertEqual(parse_clock("0:02:58"), 178.0)

    def test_eval_pawns_to_cp(self) -> None:
        self.assertEqual(parse_eval("0.17"), (17, False))

    def test_mate_clamped(self) -> None:
        self.assertEqual(parse_eval("#3"), (10000, True))
        self.assertEqual(parse_eval("#-2"), (-10000, True))


class FixtureIngest(unittest.TestCase):
    def test_filters_and_rows(self) -> None:
        text = FIXTURE.read_text(encoding="utf-8")
        games, moves, stats = ingest(io.StringIO(text))
        self.assertEqual(stats["seen"], 6)
        self.assertEqual({g.game_id for g in games}, {"KeepGame1", "KeepGame2"})
        keep1 = [m for m in moves if m.game_id == "KeepGame1"]
        self.assertEqual(len(keep1), 4)
        self.assertEqual(keep1[0].clk_after_s, 178.0)
        self.assertEqual(keep1[0].eval_cp, 17)
        self.assertEqual(keep1[2].eval_cp, 10000)
        self.assertTrue(keep1[2].is_mate)
        keep2 = [m for m in moves if m.game_id == "KeepGame2"]
        self.assertEqual([m.ply for m in keep2], [1, 2])
        self.assertEqual(keep2[0].color, "w")
        self.assertEqual(keep2[1].color, "b")

    def test_last_move_without_eval_is_dropped(self) -> None:
        movetext = (
            "1. d4 { [%eval 0.20] [%clk 0:04:55] } "
            "1... Nf6 { [%eval 0.18] [%clk 0:04:58] } "
            "2. c4 { [%clk 0:04:40] } 0-1"
        )
        rows = parse_moves("KeepGame2", movetext)
        self.assertEqual([r.san for r in rows], ["d4", "Nf6"])


if __name__ == "__main__":
    unittest.main()
