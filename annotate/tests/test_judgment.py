from __future__ import annotations

import unittest

from annotate.lichess_judgment import lichess_judgment


class LichessJudgment(unittest.TestCase):
    def test_thresholds(self) -> None:
        self.assertEqual(lichess_judgment(9.9), "ok")
        self.assertEqual(lichess_judgment(10), "inaccuracy")
        self.assertEqual(lichess_judgment(20), "mistake")
        self.assertEqual(lichess_judgment(30), "blunder")
        self.assertIsNone(lichess_judgment(None))


if __name__ == "__main__":
    unittest.main()
