# Blunder Oracle: feature EDA

Which features (known *before* a move) relate to the three things we want to predict,
in bullet, blitz and classical, and within rating bands?

| label | folder | what it is |
|---|---|---|
| C `time_spent` | `reports/think_time/` | seconds spent on the move |
| A `blunder` | `reports/blunder/` | the move loses ≥ 20 win% points |
| B `blunder_next5` | `reports/blunder_next5/` | blunder on this move or my next 4 |

**Start with [`reports/FEATURES.md`](reports/FEATURES.md)**: the recommended feature set per label and what the plots show.

## Run it

```bash
pip install -r requirements.txt
python -m pytest -q            # 11 tests, offline, ~2 s
python scripts/1_fetch.py      # 20k analysed games each of bullet/blitz/classical (~1.5-2 h: classical is rare)
python scripts/2_build.py      # PGN -> parquet tables (~10 min)
python scripts/3_eda.py        # plots + rankings -> reports/ (~10 min)
```

## Layout

```
oracle/              the code
  config.py          paths, speeds, Elo bands, labels, colours
  pgn.py             fast regex PGN parser (headers, moves, %clk, %eval)
  fetch.py           stream a Lichess month, keep N games per speed in one pass
  features.py        per-move features (FEATURES dict) + labels (LABEL_COLS)
  eda.py             eta/rho rankings, trend plots, redundancy
scripts/             1_fetch.py  2_build.py  3_eda.py
tests/               test_pipeline.py + fixtures/mini.pgn
data/<speed>/        games.pgn, games.parquet (1 row/game), moves.parquet (1 row/move)   [git-ignored]
reports/             FEATURES.md, feature_ranking.csv, feature_redundancy.png
  <label>/           ranking.png/.md, bullet.png, blitz.png, classical.png, speeds.png (+ clock_in_position.png)
```

## Data

- Lichess open database, standard rated, 2026-09, streamed (the month is ~30 GB; nothing big touches disk).
- Only games with clocks **and** engine evals (blunder labels need evals). Classical analysed games are
  ~1 in 600, so bullet/blitz keep every 12th/24th match: all three samples span the same days.
- Labels are computed **after** the move and are never features. `tests::test_no_peeking` enforces this.

## Data gotchas (handled in code)

- Clocks are whole seconds, so `time_spent` is quantised; each side's first move is untimed (NaN).
- Berserk (arena) games: half clock, no increment. Detected, increment zeroed.
- `%eval` is the eval after the move (White's POV); `wp_self` uses the eval after the previous ply.
- Mate scores map to win% 0/100. The only unlabelled plies are ply 1 and a final mating move.
- `blunder_next5`: the game ending is not censoring (no moves left = no blunders left), so end-of-game rows keep a label.
- 0+k time controls (no base time): `frac_self` is NaN.
