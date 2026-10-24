# Pulling training rows (win / think time / blunder)

This is for the teammate training models from **pre-move** context. Outcomes live in `move_outcomes`. Do not use after-move eval as an input.

Service: **`db-44476`** (`gethdbqtlo`). Same login as [stockfish_access.md](stockfish_access.md).

```powershell
tiger auth login
tiger db query db-44476 -c "SELECT COUNT(*) FROM move_outcomes;"
```

## What you are predicting

| Label | Column | Notes |
|---|---|---|
| Game result for the side to move | `mover_result` | `win` / `draw` / `loss` from `games.result` |
| Decision time | `think_s` | seconds on this ply (`clk_before - clk_after + increment`) |
| Blunder | `blunder` | Lichess rule: win-percent drop **≥ 30** |

Also stored, same Lichess cutoffs:

- `inaccuracy`: drop ≥ 10
- `mistake`: drop ≥ 20
- `judgment`: `blunder` \| `mistake` \| `inaccuracy` \| `ok` (worst only)
- `wp_loss`: continuous drop (mover’s win percent)

Win percent is the Lichess curve already in `wp_from_cp`. First ply of a game often has `blunder IS NULL` (no eval before the move). Drop those rows for the blunder model.

Rebuild labels after metrics change:

```powershell
python -m annotate.build_outcomes
```

## Leakage (do not use as features)

These describe the **played move** or the **finished game**. Using them to predict blunder or result cheats.

- `moves.eval_cp`, `eval_after_mover`, `wp_after`, `wp_loss`, `success`
- `blunder`, `mistake`, `inaccuracy`, `judgment`
- `think_s`, `clk_after_s` (after this think)
- `mover_result`, `games.result`

`eval_before_mover` / `wp_before` **are** legal features: they are the position before the move.

`engine_gap` is legal only after Stockfish has filled `engine_features`. It is still NULL on this probe until annotation runs.

## Pull features + labels

Ready-made views:

```sql
-- Inputs only
SELECT * FROM model_features;

-- Targets only
SELECT * FROM model_labels;

-- Inner join, one row per ply (replay-missing games have NULL fen/material)
SELECT * FROM model_training_rows;
```

Typical train extract (skip premoves and unlabelled blunders):

```sql
SELECT *
FROM model_training_rows
WHERE premove IS FALSE
  AND think_s >= 0
  AND blunder IS NOT NULL;
```

Hold out **by game**, not by ply:

```sql
SELECT *
FROM model_training_rows
WHERE abs(hashtext(game_id)) % 10 >= 7;  -- ~30% of games; keep all plies of those ids
```

Better in Python: unique `game_id`, `train_test_split(..., stratify=mover_result)` on **games**, then keep all plies of those ids.

Pandas:

```python
import subprocess
import pandas as pd
import psycopg

uri = subprocess.check_output(
    ["tiger", "db", "uri", "db-44476", "--with-password"],
    text=True,
).strip().splitlines()[-1]

feature_cols = [
    "elo", "opp_elo", "elo_diff", "rating_band", "tc",
    "clk_before_s", "clk_frac", "clk_frac_band", "ply_phase",
    "eval_before_mover", "wp_before", "time_trouble",
    "material_total", "material_advantage_mover",
    "prev_think_white_s", "prev_think_black_s",
    "opp_clk_s", "log_clk_before", "log_opp_clk",
    "engine_gap", "n_near_best", "n_legal_moves",
]
label_cols = ["think_s", "mover_result", "blunder"]

sql = """
SELECT game_id, ply, """ + ", ".join(feature_cols + label_cols) + """
FROM model_training_rows
WHERE premove IS FALSE AND think_s >= 0
"""
with psycopg.connect(uri) as conn:
    df = pd.read_sql(sql, conn)
```

CSV dump (client machine):

```powershell
tiger db query db-44476 -c "COPY (SELECT * FROM model_training_rows WHERE premove IS FALSE) TO STDOUT WITH CSV HEADER" > training_rows.csv
```

If `COPY TO STDOUT` is blocked, use Python as above.

## Counts on the 1,000-game probe

After `build_outcomes`, check:

```sql
SELECT judgment, COUNT(*)
FROM move_outcomes
GROUP BY 1
ORDER BY 1;

SELECT mover_result, COUNT(*)
FROM move_outcomes
GROUP BY 1;

SELECT COUNT(*) FILTER (WHERE blunder) * 1.0 / COUNT(blunder) AS blunder_rate
FROM move_outcomes
WHERE blunder IS NOT NULL;
```

Blunders are rare. Use class weights or average precision, not accuracy.

## Grain

`(game_id, ply)` — same as Stockfish work. Join to `engine_features` when `gap` is filled if you want difficulty as an extra input.
