from __future__ import annotations

import math
import unittest

from annotate.clock_features import ClockTracker, log_remaining_seconds
from annotate.fen_replay import replay_game
from annotate.material import PIECE_POINTS


class MaterialAndClock(unittest.TestCase):
    def test_start_position_material(self) -> None:
        rows = list(
            replay_game(
                game_id="KeepGame1",
                base=180,
                inc=0,
                moves=[
                    {"ply": 1, "color": "w", "san": "e4", "clk_after_s": 178},
                    {"ply": 2, "color": "b", "san": "e5", "clk_after_s": 179},
                    {"ply": 3, "color": "w", "san": "Nf3", "clk_after_s": 170},
                    {"ply": 4, "color": "b", "san": "Nc6", "clk_after_s": 160},
                ],
            )
        )
        self.assertEqual(len(rows), 4)
        self.assertTrue(rows[0]["fen_before"].startswith("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq"))
        self.assertEqual(rows[0]["material_total"], 78)
        self.assertEqual(rows[0]["material_advantage_white"], 0)
        self.assertEqual(rows[0]["material_advantage_mover"], 0)
        self.assertIsNone(rows[0]["prev_think_white_s"])
        self.assertIsNone(rows[0]["prev_think_black_s"])
        self.assertEqual(rows[0]["think_s"], 2)
        self.assertEqual(rows[1]["prev_think_white_s"], 2)
        self.assertIsNone(rows[1]["prev_think_black_s"])
        self.assertEqual(rows[2]["prev_think_white_s"], 2)
        self.assertEqual(rows[2]["prev_think_black_s"], 1)
        self.assertTrue(rows[1]["fen_before"].startswith("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq"))

    def test_capture_changes_advantage(self) -> None:
        rows = list(
            replay_game(
                game_id="cap",
                base=180,
                inc=0,
                moves=[
                    {"ply": 1, "color": "w", "san": "e4", "clk_after_s": 179},
                    {"ply": 2, "color": "b", "san": "d5", "clk_after_s": 179},
                    {"ply": 3, "color": "w", "san": "exd5", "clk_after_s": 178},
                    {"ply": 4, "color": "b", "san": "Qxd5", "clk_after_s": 178},
                ],
            )
        )
        # Material is of fen_before, so the capture shows up on the next ply.
        self.assertEqual(rows[2]["material_total"], 78)
        self.assertEqual(rows[3]["material_white"], 39)
        self.assertEqual(rows[3]["material_black"], 38)
        self.assertEqual(rows[3]["material_advantage_white"], 1)
        self.assertEqual(rows[3]["material_advantage_mover"], -1)

    def test_log_remaining(self) -> None:
        self.assertEqual(log_remaining_seconds(0), 0.0)
        self.assertAlmostEqual(log_remaining_seconds(math.e - 1), 1.0)

    def test_piece_values(self) -> None:
        self.assertEqual(sum(PIECE_POINTS.values()), 21)

    def test_increment_in_think(self) -> None:
        clocks = ClockTracker(base=180, inc=2)
        snap = clocks.snapshot("w", 178)
        self.assertEqual(snap["think_s"], 4)


if __name__ == "__main__":
    unittest.main()
