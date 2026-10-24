"""Previous-move think times and log remaining clock."""

from __future__ import annotations

import math
from dataclasses import dataclass


def log_remaining_seconds(seconds: float) -> float:
    """Natural log of remaining time. log1p so a 0s clock is 0, not -inf."""
    return math.log1p(max(seconds, 0.0))


@dataclass
class ClockTracker:
    base: float
    inc: float
    last_clk_after: dict[str, float | None]
    last_think: dict[str, float | None]

    def __init__(self, base: float, inc: float) -> None:
        self.base = base
        self.inc = inc
        self.last_clk_after = {"w": None, "b": None}
        self.last_think = {"w": None, "b": None}

    def opp_color(self, color: str) -> str:
        return "b" if color == "w" else "w"

    def clk_before(self, color: str) -> float:
        prev = self.last_clk_after[color]
        return self.base if prev is None else prev

    def opp_clk(self, color: str) -> float:
        prev = self.last_clk_after[self.opp_color(color)]
        return self.base if prev is None else prev

    def think_s(self, color: str, clk_after: float) -> float:
        return self.clk_before(color) - clk_after + self.inc

    def snapshot(self, color: str, clk_after: float) -> dict[str, float | None]:
        clk_before = self.clk_before(color)
        opp = self.opp_clk(color)
        think = self.think_s(color, clk_after)
        row = {
            "clk_before_s": clk_before,
            "opp_clk_s": opp,
            "think_s": think,
            "prev_think_white_s": self.last_think["w"],
            "prev_think_black_s": self.last_think["b"],
            "log_clk_before": log_remaining_seconds(clk_before),
            "log_opp_clk": log_remaining_seconds(opp),
        }
        self.last_think[color] = think
        self.last_clk_after[color] = clk_after
        return row
