"""Paths, the 9 feature vectors, and modelling settings shared by every step."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EDA = ROOT.parent / "eda"
sys.path.insert(0, str(EDA))  # reuse the EDA's parser + feature code: identical features for training and testing

TRAIN_DATA = EDA / "data"     # <speed>/moves.parquet from the EDA pull (2,000 games per speed)
TEST_DATA = ROOT / "test_data"
MODELS = ROOT / "models"
REPORTS = ROOT / "reports"

SPEEDS = ("bullet", "blitz", "classical")
TARGETS = {  # target name -> label column
    "think_time": "time_spent",
    "blunder": "blunder",
    "blunder_next5": "blunder_next5",
}

# The 9 feature vectors (eda/FEATURE_SET.md), strongest first.
FEATURES = {
    "bullet": {
        "think_time": ["avg_self_spent", "base", "prev_opp_spent", "prev_self_spent", "ply",
                       "clock_self", "inc", "n_captures", "n_legal", "elo_self"],
        "blunder": ["last_swing", "wp_self", "abs_cp", "mat_diff", "n_captures", "mat_total",
                    "n_legal", "prior_blunders_self", "clock_opp", "clock_ratio", "elo_self"],
        "blunder_next5": ["wp_self", "last_swing", "abs_cp", "mat_diff", "mat_total", "n_captures",
                          "n_legal", "clock_self", "clock_ratio", "prev_opp_spent", "elo_self"],
    },
    "blitz": {
        "think_time": ["ply", "prev_opp_spent", "avg_self_spent", "prev_self_spent", "clock_self",
                       "n_legal", "clock_ratio", "n_captures", "inc", "abs_cp", "elo_self"],
        "blunder": ["last_swing", "wp_self", "abs_cp", "mat_total", "mat_diff", "n_captures",
                    "clock_opp", "prior_blunders_self", "avg_self_spent", "prev_self_spent", "elo_self"],
        "blunder_next5": ["wp_self", "last_swing", "abs_cp", "mat_total", "mat_diff", "n_captures",
                          "clock_opp", "n_legal", "prev_opp_spent", "clock_ratio", "elo_self"],
    },
    "classical": {
        "think_time": ["prev_self_spent", "avg_self_spent", "prev_opp_spent", "ply", "n_legal",
                       "frac_self", "clock_ratio", "n_captures", "abs_cp", "wp_self", "elo_self"],
        "blunder": ["last_swing", "wp_self", "abs_cp", "mat_diff", "n_captures", "ply",
                    "elo_self", "n_legal", "prior_blunders_self", "frac_self"],
        "blunder_next5": ["wp_self", "last_swing", "abs_cp", "mat_diff", "mat_total", "elo_self",
                          "n_captures", "n_legal", "frac_self", "clock_self"],
    },
}

# Per speed, every feature any of its 3 models needs (eda/FEATURE_SET.md arrays). This is the input vector of the
# C++ predictor (cpp/), in exactly this order.
SUPERSETS = {
    "bullet": ["clock_self", "clock_opp", "clock_ratio", "base", "inc",
               "prev_self_spent", "avg_self_spent", "prev_opp_spent",
               "elo_self", "ply", "mat_total", "mat_diff", "n_legal", "n_captures",
               "wp_self", "abs_cp", "last_swing", "prior_blunders_self"],
    "blitz": ["clock_self", "clock_opp", "clock_ratio", "inc",
              "prev_self_spent", "avg_self_spent", "prev_opp_spent",
              "elo_self", "ply", "mat_total", "mat_diff", "n_legal", "n_captures",
              "wp_self", "abs_cp", "last_swing", "prior_blunders_self"],
    "classical": ["clock_self", "clock_ratio", "frac_self",
                  "prev_self_spent", "avg_self_spent", "prev_opp_spent",
                  "elo_self", "ply", "mat_total", "mat_diff", "n_legal", "n_captures",
                  "wp_self", "abs_cp", "last_swing", "prior_blunders_self"],
}

# Domain knowledge the model may be forced to respect (+1 = prediction can only go up as the
# feature goes up, -1 = only down). Applied only if cross-validation shows it costs no accuracy.
MONOTONE = {
    "think_time": {"avg_self_spent": 1, "prev_self_spent": 1, "prev_opp_spent": 1,
                   "clock_self": 1, "frac_self": 1, "inc": 1, "base": 1},
    "blunder": {"elo_self": -1, "clock_self": -1, "frac_self": -1},
    "blunder_next5": {"elo_self": -1, "clock_self": -1, "frac_self": -1},
}

THINK_QUANTILES = (0.1, 0.5, 0.9)   # think-time prediction = median, with an 80% range
CV_FOLDS = 5                        # grouped by game: a game's moves are never split across folds
SEED = 0

# Test games: the training pull scanned the first 1,122,353 games of 2026-09. Skipping 1.5M
# puts the test games a few hours later, so they cannot overlap with training.
TEST_SKIP = 1_500_000
TEST_GAMES = 100
