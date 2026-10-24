"""Lichess move judgments from win-percent loss.

Thresholds match Lichess analysis: blunder 30, mistake 20, inaccuracy 10
percentage points on the Lichess winning-chances curve.
"""

from __future__ import annotations


def lichess_judgment(wp_loss: float | None) -> str | None:
    if wp_loss is None:
        return None
    if wp_loss >= 30:
        return "blunder"
    if wp_loss >= 20:
        return "mistake"
    if wp_loss >= 10:
        return "inaccuracy"
    return "ok"
