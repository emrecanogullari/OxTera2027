"""Paths and constants shared by every module."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"        # data/<speed>/games.pgn, games.parquet, moves.parquet
REPORTS = ROOT / "reports"  # reports/<label>/*.png, reports/FEATURES.md

# Monthly standard-rated dumps (~30 GB compressed). We STREAM them and stop early.
LICHESS_URL = "https://database.lichess.org/standard/lichess_db_standard_rated_{month}.pgn.zst"
DEFAULT_MONTH = "2026-09"

# Lichess speed categories, from estimated duration = base + 40 * increment (s).
SPEED_BOUNDS = [(29, "ultrabullet"), (179, "bullet"), (479, "blitz"), (1499, "rapid")]
# anything above -> "classical"; TimeControl "-" -> "correspondence"
SPEEDS = ("bullet", "blitz", "classical")

# Analysed games (with %eval) per game scanned, measured on the first 300k games of
# 2026-09: bullet 1/46, blitz 1/22, classical 1/593. Keeping every k-th bullet/blitz
# match makes all three samples span roughly the same days of the month.
EVERY = {"bullet": 12, "blitz": 24, "classical": 1}

# Win chance (Lichess formula):
#   win% = 50 + 50 * (2 / (1 + exp(-0.00368208 * cp)) - 1),  cp capped at +-1000, mate -> 0/100
# Blunder = the mover's win% falls by >= 20 points.
WC_K = 0.00368208
CP_CAP = 1000
BLUNDER_PTS = 20

ELO_EDGES = [0, 1200, 1500, 1800, 2100, 4000]
ELO_BANDS = ["<1200", "1200-1500", "1500-1800", "1800-2100", "2100+"]

# The three things we predict. Folder name -> (column, how to read it)
LABELS = {
    "think_time": ("time_spent", "seconds spent on the move"),
    "blunder": ("blunder", "move loses >= 20 win% points"),
    "blunder_next5": ("blunder_next5", "blunder on this move or my next 4"),
}

# Plot style
COLORS = {"bullet": "#2a78d6", "blitz": "#eb6834", "classical": "#1baf7a"}
ELO_COLORS = ["#c6dbef", "#9ecae1", "#6baed6", "#3182bd", "#08519c"]  # light = low rating
INK = "#0b0b0b"
INK_2 = "#52514e"
SURFACE = "#fcfcfb"
GRID = "#e4e3df"
RED = "#e34948"
