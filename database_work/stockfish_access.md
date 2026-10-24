# Stockfish annotation: how to use this database

This is the working Tiger Cloud database for Clock Coach. Your job is to run Stockfish MultiPV on positions we already reconstructed, then write difficulty features back. You do **not** need to parse PGN or compute think time.

Service is tagged **DEV** (writes are allowed). Do not point the Chrome extension at these tables.

## Connect

| | |
|---|---|
| Project | `kp0mtlh4wt` |
| Service name | `db-44476` |
| Service ID | `gethdbqtlo` |
| Region | `us-east-1` |
| Type | TimescaleDB / Postgres |
| Database | `tsdb` |
| User | `tsdbadmin` |

Install the [Tiger CLI](https://docs.tigerdata.com/) (Windows: `irm https://cli.tigerdata.com/install.ps1 | iex`). Then:

```powershell
tiger auth login
tiger service list
tiger db ping db-44476
tiger db query db-44476 -c "SELECT now();"
```

Interactive SQL (needs local `psql`):

```powershell
tiger db psql db-44476
```

Connection URI **without** embedding the password:

```powershell
tiger db uri db-44476
```

First connect will prompt for the `tsdbadmin` password. Save it with `tiger db save-password` so you are not pasting it into scripts. If you need a URI with the password for `psycopg`, `tiger db uri db-44476 --with-password` — treat that string as a secret; do not commit it.

Python:

```python
import subprocess, psycopg

uri = subprocess.check_output(
    ["tiger", "db", "uri", "db-44476", "--with-password"],
    text=True,
).strip().splitlines()[-1]
conn = psycopg.connect(uri)
```

Repo helper (same URI): `from ingest.load_tiger import tiger_uri`.

## What is already in the database

Probe slice: **1,000** rated Lichess blitz games from `lichess_db_standard_rated_2026-09`, filters `180+0` / `300+0`, Elo 1000–2200, `Event = Rated Blitz game`, `Termination = Normal`, clocks + evals present.

| Table | Rows (approx.) | You need it? |
|---|---|---|
| `games` | 1,000 | ratings, `base`/`inc` |
| `moves` | 62,662 | SAN, clock after the move, Lichess eval |
| `move_metrics` | 62,662 | think time, clock fraction, ply-phase, success label |
| `move_replay` | ~62,483 | **`fen_before`**, material, previous thinks, log clocks |
| `engine_features` | one row per replayed ply | **write your Stockfish output here** |
| `lookup_budgets` | 106 | ignore (clock-only test of the extension table) |

**7 games** did not fully replay (SAN gap or illegal move). They have `moves` but missing tail rows in `move_replay` / `engine_features`. Skip them.

Grain for everything you care about: **`(game_id, ply)`**. `ply` is 1-based half-move index. `fen_before` is the position **before** that ply’s move (the position the player was thinking about).

## Position you should analyse

```sql
SELECT
  e.game_id,
  e.ply,
  e.fen_before,
  m.color,          -- 'w' or 'b', side about to move
  r.material_total,
  r.material_advantage_mover,
  mm.elo,
  mm.tc,
  mm.ply_phase,
  mm.clk_frac
FROM engine_features e
JOIN moves m USING (game_id, ply)
JOIN move_replay r USING (game_id, ply)
JOIN move_metrics mm USING (game_id, ply)
WHERE e.gap IS NULL          -- not analysed yet
ORDER BY e.game_id, e.ply;
```

`fen_before` is a full FEN, including side to move. Feed it to Stockfish as-is. Do not replay SAN yourself unless you are debugging; that work is done.

Unclaimed / unfinished work is `engine_features.gap IS NULL`. After a successful analyse, `gap` is set, so a rerun skips those rows.

### Optional sample (do not require a full 62k on day one)

```sql
SELECT e.game_id, e.ply, e.fen_before
FROM engine_features e
JOIN move_metrics mm USING (game_id, ply)
WHERE e.gap IS NULL
  AND mm.premove IS FALSE
ORDER BY random()
LIMIT 5000;
```

Better: stratify with `ply_phase`, `clk_frac_band`, `rating_band` on `move_metrics` so openings do not dominate.

## What to write back

Update **only** the engine columns. Leave `fen_before` unchanged.

| Column | Meaning |
|---|---|
| `best_wp` | Win percent of the best MultiPV line, **side to move** |
| `second_wp` | Win percent of the second line, same POV |
| `gap` | `best_wp - second_wp` (how obvious the decision is) |
| `n_near_best` | How many MultiPV lines sit within a small wp margin of the best (e.g. 5 points) |
| `n_legal_moves` | `board.legal_moves` count from the FEN (python-chess is fine) |

Win percent from centipawns (Lichess curve, same as ingest):

```text
wp(cp) = 50 + 50 * (2 / (1 + exp(-0.00368208 * cp)) - 1)
```

Mate scores: clamp to ±10000 cp before that formula. Convert Stockfish’s score to the **mover’s** point of view (the FEN’s side to move).

Suggested engine settings (hackathon default): MultiPV 3–5, fixed depth **12** or a modest node cap, same settings on every row. Record depth in your worker logs; we can add a `depth` column later if you need it.

Example write:

```sql
UPDATE engine_features
SET
  best_wp = 58.2,
  second_wp = 51.0,
  gap = 7.2,
  n_near_best = 2,
  n_legal_moves = 31
WHERE game_id = $1 AND ply = $2;
```

Batch updates in a transaction. Do not `TRUNCATE engine_features` — that drops FENs.

## Rebuild FEN / material (only if replay is empty)

From repo root, Python 3.11+, packages `chess` and `psycopg`:

```powershell
python -m unittest annotate.tests.test_replay
python -m annotate.build_replay_features
tiger db query db-44476 -f sql/007_seed_engine_features.sql
```

That walks SAN from move 1, stores `move_replay`, then copies `fen_before` into `engine_features`. Safe to rerun: it replaces replay rows, then upserts FEN without clearing `gap` if you change the seed SQL — **current seed overwrites `fen_before` only**. If you add `ON CONFLICT` updates that touch `gap`, stop and change it.

## Column cheat sheet for the position

From `move_replay` (already computed):

- `fen_before` — board to analyse
- `material_white` / `material_black` / `material_total` — pawn units, K=0
- `material_advantage_white` — white minus black
- `material_advantage_mover` — positive if the side to move is ahead in material
- `prev_think_white_s` / `prev_think_black_s` — last finished think for each colour (`NULL` if they have not moved yet)
- `clk_before_s` / `opp_clk_s` — remaining clocks at the start of this think
- `log_clk_before` / `log_opp_clk` — `ln(1 + seconds)`

You do not need these for MultiPV. They are for joining difficulty to clock later.

## Conventions

- Do **not** use after-move eval as a feature. Lichess `moves.eval_cp` is the eval **after** the played move (White’s perspective). Your MultiPV is of `fen_before`.
- Split / hold-out is by **`game_id`**, never by ply. If you downsample, keep all plies of a game in the same bucket.
- Rated live games are out of scope for the product. This warehouse is historical rated PGN, which is allowed for training.

## Sanity checks after a batch

```sql
SELECT
  COUNT(*) AS rows,
  COUNT(gap) AS analysed,
  COUNT(*) FILTER (WHERE gap IS NULL) AS pending
FROM engine_features;

SELECT ROUND(AVG(gap)::numeric, 2) AS avg_gap,
       ROUND(percentile_cont(0.5) WITHIN GROUP (ORDER BY gap)::numeric, 2) AS median_gap
FROM engine_features
WHERE gap IS NOT NULL;
```

Expect many small gaps in quiet positions and a long tail. If every gap is 0, MultiPV is not actually returning distinct lines.

## Option B (job queue) is optional

You can run from `WHERE gap IS NULL` as above. A `annotation_jobs` claim table is **not** required until several workers fight over the same rows. If you add it later, key it `(game_id, ply)` and point `fen_before` at `engine_features` / `move_replay`.
