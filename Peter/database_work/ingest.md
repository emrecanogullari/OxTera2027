# Ingest runbook

Do not decompress a monthly dump. Recent files are about **29 GB compressed** (September 2026: `lichess_db_standard_rated_2026-09.pgn.zst`, 29,224,520,887 bytes). Uncompressed they will not fit comfortably on a laptop.

Ingest runs on **Vultr**. The **C++** parser in `ingest/cpp` writes CSV. Tiger Data is loaded with `\copy` after a small sample looks sane. Python `ingest/ingest.py` is the unit-test spec, not the dump path.

## What one kept game becomes

| Table | One row is | Source |
|---|---|---|
| `games` | the game | PGN headers |
| `moves` | a ply with both `[%clk]` and `[%eval]` | movetext comments |

Think time is **not** computed here. Phase 2 SQL does `clk_before - clk_after + increment`.

Filters (frozen):

- `Event` = `Rated Blitz game` (drops arenas / berserk)
- `TimeControl` in `180+0`, `300+0`
- both Elos in 1000–2200
- `Termination` = `Normal`
- movetext contains `[%eval` and `[%clk`
- last move is dropped if it has no eval (common)

## 0. Prove the parser on the laptop

From `Peter/` (PowerShell):

```powershell
python -m unittest ingest.tests.test_ingest
cd ingest\cpp; powershell -File compile.ps1; cd ..\..
New-Item -ItemType Directory -Force data | Out-Null
Get-Content ingest\tests\fixtures\sample.pgn | ingest\cpp\build\ingest.exe --out-dir data
python ingest\validate.py --dir data
```

Expect two kept games (`KeepGame1`, `KeepGame2`), four moves on the first, two on the second (the unevaluated last ply is dropped).

## 1. On Vultr, check size then stream

```bash
curl -sI "https://database.lichess.org/standard/lichess_db_standard_rated_2026-09.pgn.zst" | grep -i content-length
```

Install `zstd` if needed. Build ingest first (`ingest/cpp`). Stream a **probe** of 200 kept games (stopping curl early is fine; `zstd` will complain about truncation):

```bash
mkdir -p data ingest/cpp/build
# Windows: powershell -File ingest/cpp/compile.ps1
# else:    make -C ingest/cpp
curl -L "https://database.lichess.org/standard/lichess_db_standard_rated_2026-09.pgn.zst" \
  | zstd -dc \
  | ingest/cpp/build/ingest --out-dir data --max-games 200
python ingest/validate.py --dir data
```

Read `validate.py` output: ply gaps are expected when a last move has no eval. Color mismatches and unknown `game_id`s are not.

## 2. Create empty tables

```bash
psql "$DATABASE_URL" -f sql/001_schema.sql
```

Load the 200-game probe:

```bash
psql "$DATABASE_URL" -f sql/002_copy.sql
```

Spot-check:

```sql
SELECT COUNT(*) FROM games;
SELECT COUNT(*) FROM moves;
SELECT * FROM games LIMIT 5;
SELECT * FROM moves WHERE game_id = (SELECT game_id FROM games LIMIT 1) ORDER BY ply;
```

Pick one `game_id`, open `https://lichess.org/<game_id>`, and confirm ply count (minus a possible unevaluated last move), clocks, and that evals are White-centric.

## 3. Full month, then indexes

Truncate the probe, rerun ingest **without** `--max-games`, `\copy` again, **then** indexes:

```bash
psql "$DATABASE_URL" -c "TRUNCATE moves, games;"
curl -L "https://database.lichess.org/standard/lichess_db_standard_rated_2026-09.pgn.zst" \
  | zstd -dc \
  | ingest/cpp/build/ingest --out-dir data
psql "$DATABASE_URL" -f sql/002_copy.sql
psql "$DATABASE_URL" -f sql/003_indexes.sql
```

Do not create the secondary indexes before COPY.

## Gotchas

- Premoves show near-zero think time later; leave them in CSV, flag in metrics (`think_s < 0.3`).
- First move of each side has no previous clock; SQL uses `base`.
- Increment is already in `clk_after`. The think formula still **adds** `inc`.
- `eval` in the dump is **pawns**; the parser stores **centipawns** (`0.17` → `17`). Mate `#3` / `#-2` → `±10000`.
- Dedup is on `game_id` from the Site URL.
