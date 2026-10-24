# Chess Think-Time Coach: Project Plan

A browser extension that, while you practise against a bot on Lichess (and later chess.com), tells you when you are taking too long on a move, based on a model trained on the Lichess open database.

---

## 1. Goal and scope

**Goal:** Given the current game context (clock, rating, phase, position difficulty), suggest a think-time budget and nudge the user when they exceed it.

**In scope**
- Training on Lichess standard rated games with `[%clk]` and `[%eval]` annotations
- A lookup-table model (v1) with an optional parametric model (v2)
- A Manifest V3 browser extension, Lichess first, chess.com second
- Use only in practice games against a bot

**Out of scope**
- Live advice in games against humans (violates fair-play rules on both sites)
- Move suggestions of any kind: the tool only comments on time

---

## 2. Architecture

```
Lichess dump (.pgn.zst)
        |  stream + filter (Vultr)
        v
 CSV / Parquet  --COPY-->  Tiger Data (Postgres)
                                |  SQL metrics (think time, eval loss)
                                |  + Stockfish MultiPV difficulty features (Vultr)
                                v
                        Feature table
                                |  train (Python, LightGBM)
                                v
              Analysis: success vs think-time curves
                                |
              +-----------------+------------------+
              v                                    v
   v1: lookup table (JSON)               v2: parametric model (ONNX)
              |                                    |
              +----------> Extension <-------------+
                       (optional API on Vultr)
```

**Sponsor mapping**

| Sponsor | Role |
|---|---|
| Tiger Data | Primary store for games, moves, metrics, and lookup tables |
| Vultr | Ingest, Stockfish annotation, training, optional API host |
| Eleven Labs | Optional voice nudge ("time to move") |
| Gemini API | Optional plain-language explanation of the suggestion or post-game summary |
| Snowflake / Presage / Solana | Not used (Snowflake is an alternative store; the other two have no natural role) |

---

## 3. Key definitions

### 3.1 Think time
For each move: `think = clk_before - clk_after + increment`, where `clk_before` is the same player's previous `clk_after` (or the base time for their first move).

### 3.2 Success (the label)
A raw "positive eval delta" is not usable: the position's value before your move already reflects your best option, so your move can at best match it, and deltas are essentially minus centipawn loss. Use win-probability loss instead.

- Win probability from centipawns: `wp(cp) = 50 + 50 * (2 / (1 + exp(-0.00368208 * cp)) - 1)` (check the constant against Lichess's documentation)
- From the mover's point of view: `loss = wp_before - wp_after`
- **Success** (binary): `loss < 5` percentage points (tunable). Also keep `loss` itself as a continuous target.

### 3.3 Recommended budget
For each context bucket, the budget is the think time beyond which extra time stops improving success (the "knee" of the success-versus-time curve). Fallback: the 75th percentile of typical think time in that bucket.

---

## 4. Step-by-step plan

### Phase 0: Setup
1. Create the repo with this layout:
   ```
   /ingest        parser + loaders
   /sql           schema, metrics, lookup-table queries
   /annotate      Stockfish MultiPV runner
   /model         training and analysis notebooks
   /extension     MV3 extension
   /api           optional FastAPI service
   /docs          this plan
   ```
2. Provision a Vultr instance (several CPU cores, enough disk for one month of dump data) and a Tiger Data service.
3. Install on Vultr: Python, `zstd`, `psql`, Stockfish.
4. Decide the initial slice: one monthly dump, blitz only (`180+0` and `300+0`), rating 1000 to 2200.

### Phase 1: Ingest
1. Download one monthly file from database.lichess.org (check its size first; recent months are tens of GB).
2. Stream it: `zstd -dc file.pgn.zst | ingest/cpp/build/ingest`. Do not decompress to disk.
3. Parse with a plain-text reader (no board replay). Keep a game only if:
   - movetext contains `[%eval` and `[%clk`
   - `Event` is `Rated Blitz game` (excludes arena tournaments, where berserk halves the clock)
   - both Elos are within range
   - termination is normal
   - `TimeControl` is in your chosen set
4. Per game write one row to `games`: `game_id` (from the Site URL), `white_elo`, `black_elo`, `base`, `inc`, `result`, `termination`, `utc_date`.
5. Per move write one row to `moves`: `game_id`, `ply`, `color`, `san`, `clk_after_s` (seconds), `eval_cp` (centipawns, White's perspective), `is_mate`. Clamp mate evals to a large signed value such as ±10000 and set `is_mate`.
6. Validate on a small sample: ply counts match known games, clocks decrease monotonically per player, evals look sane.
7. Create tables in Tiger Data:
   ```sql
   CREATE TABLE games (
     game_id text PRIMARY KEY, white_elo int, black_elo int,
     base int, inc int, result text, termination text, utc_date date);

   CREATE TABLE moves (
     game_id text, ply int, color char(1), san text,
     clk_after_s real, eval_cp int, is_mate boolean,
     PRIMARY KEY (game_id, ply));
   ```
8. Bulk load with `\copy` (or psycopg `copy`). Build secondary indexes after loading.
9. Scale up only after the full pipeline works end to end on one month.

**Gotchas:** premoves give near-zero think times; the first move of each side has no previous clock; the last move may lack an eval; deduplicate on `game_id` if files overlap.

### Phase 2: Metrics (SQL)
Build a `move_metrics` table with window functions.

```sql
CREATE TABLE move_metrics AS
WITH base AS (
  SELECT m.game_id, m.ply, m.color, m.clk_after_s, m.eval_cp,
         g.base, g.inc,
         CASE WHEN m.color = 'w' THEN g.white_elo ELSE g.black_elo END AS elo,
         LAG(m.clk_after_s) OVER w_player AS prev_clk,
         LAG(m.eval_cp)     OVER w_game   AS eval_before_white
  FROM moves m
  JOIN games g USING (game_id)
  WINDOW w_player AS (PARTITION BY m.game_id, m.color ORDER BY m.ply),
         w_game   AS (PARTITION BY m.game_id ORDER BY m.ply)
)
SELECT game_id, ply, color, elo, base, inc,
       COALESCE(prev_clk, base) AS clk_before_s,
       clk_after_s,
       COALESCE(prev_clk, base) - clk_after_s + inc AS think_s,
       -- evals are from White's view; flip for Black
       CASE WHEN color = 'w' THEN eval_before_white ELSE -eval_before_white END AS eval_before_mover,
       CASE WHEN color = 'w' THEN eval_cp           ELSE -eval_cp           END AS eval_after_mover
FROM base;
```

Then add:
- `clk_frac = clk_before_s / base`
- `wp_before`, `wp_after` using the win-probability formula, and `wp_loss = wp_before - wp_after`
- `success = (wp_loss < 5)`
- `phase` from ply buckets (e.g. opening <= 20, middlegame 21 to 60, endgame > 60)
- `time_trouble = clk_frac < 0.1`
- `premove = think_s < 0.3` (flag, and exclude from training)

Sanity checks: distribution of `think_s` (right-skewed), fraction of negative values (data errors), and `wp_loss` distribution (mostly small, long tail).

### Phase 3: Position-difficulty features (Stockfish)
Eval-only data does not tell you how hard a decision was. Add engine-based features for a sample.

1. Sample a few hundred thousand to a few million positions, stratified by rating band, phase, and clock fraction.
2. For sampled games, replay with python-chess to reconstruct `fen_before`.
3. Run Stockfish with MultiPV (e.g. 3 to 5 lines) at a fixed modest depth or node count, in parallel across Vultr cores.
4. Store per position:
   - `best_wp`, `second_wp`, `gap = best_wp - second_wp`
   - `n_near_best` = number of lines within a small win-probability margin of the best
   - `entropy` of a softmax over line scores (optional)
   - `n_legal_moves`
5. Join back to `move_metrics` by `(game_id, ply)`.
6. Check the separate Lichess evaluations database on database.lichess.org; if it fits, it may supply multi-line evals by FEN and save engine time.

### Phase 4: Analysis and model
1. Hold out data **by game (or by player)**, not by move, to avoid leakage.
2. **Baseline:** predict log think time from clock features only; this shows how much is explained by clock management alone.
3. **Success analysis:** within buckets of similar difficulty, clock state, rating, and phase, plot success rate against think-time quantile. Because players think longer on harder positions, a naive pooled plot will mislead; always condition on difficulty.
4. Find the **knee** per bucket (smallest think time whose success rate is within a tolerance of the bucket's maximum, or where the marginal gain per extra second falls below a threshold). Enforce a minimum sample count per cell.
5. **Optional v2:** LightGBM (or quantile regression) with continuous inputs: rating, clock fraction, ply, difficulty features. Predict P(success | features, think time) or the think-time quantiles directly. Evaluate with MAE on log time and calibration of success probabilities.
6. Compare both against the simple "fraction of remaining clock" heuristic. If you can't beat it, the project should say so.

### Phase 5: Build the lookup table (v1)
1. Choose bucket edges, for example:
   - time control: 180+0, 300+0, ...
   - rating band: 200-point steps
   - phase: opening, middlegame, endgame
   - clock fraction: <10%, 10 to 30%, 30 to 60%, >60%
   - difficulty (gap): 4 buckets
2. For each bucket compute: sample count, recommended budget (knee), typical upper bound (p75), and p50.
3. Handle sparse cells: merge adjacent buckets or fall back to a coarser parent cell; store the count so the extension can know confidence.
4. Export as JSON keyed by a compact string, e.g. `"180+0|1400|mid|2|1" -> {budget, p75, n}`. Expect around a thousand entries and tens of KB.
5. Store the table in Tiger Data too (versioned), so the API can serve it if needed.
6. Sanity check that budgets rise with difficulty and fall as the clock gets low.

### Phase 6: Extension (MV3)
1. Start with Lichess games against the computer. Add chess.com later (its DOM differs and changes often).
2. Content script:
   - read the player's clock, the opponent's clock, the ply count, and the side to move from the page DOM (verify selectors in dev tools; they can change)
   - track when the current turn started
3. Difficulty feature: run Stockfish WASM (in a web worker) on the current position with MultiPV to get the gap bucket. Run it only while it is the user's turn, and keep depth small.
4. Compute the bucket key, look up the budget, and compare with elapsed time on the current move.
5. UI: a small overlay showing elapsed versus budget. At the threshold, show a visual nudge; optionally play a voice cue via Eleven Labs (pre-generate a few short clips and bundle them to avoid API latency).
6. Settings: sensitivity (use p50, knee, or p75), sound on/off, enable only for bot games.
7. Detect bot games explicitly and stay inactive otherwise.

### Phase 7: Optional API and extras
1. FastAPI service on Vultr loading the v2 model (ONNX) and answering budget queries; Tiger Data holds the tables behind it.
2. Or run the v2 model in the browser with onnxruntime-web and skip the server.
3. Gemini API: turn the numbers into a short explanation ("three close candidate moves here, so a longer think is typical") or a post-game time-usage summary.
4. Post-game panel: per-move think time versus budget, with the moves where you overspent.

### Phase 8: Evaluation and polish
1. Offline: calibration of success probability, error versus the clock-fraction baseline, per-rating-band performance.
2. Online (practice): test with real bot games; check that nudges feel neither constant nor absent. Tune thresholds.
3. Write up limitations (see Section 6).
4. Prepare the demo: a short recorded game with the overlay, plus a slide showing the success-versus-time curve.

---

## 5. Suggested timeline (adjust to your deadline)

| Block | Work | Exit criterion |
|---|---|---|
| 1 | Setup, ingest one month, validate | `games` and `moves` populated and sane |
| 2 | SQL metrics, clock-only baseline | `move_metrics` built; baseline error known |
| 3 | Stockfish difficulty features (sample) | Features joined to metrics |
| 4 | Success analysis, knee detection, lookup table | JSON table exported and sanity-checked |
| 5 | Extension MVP on Lichess with the JSON | Working nudge in a bot game |
| 6 | Polish: voice, Gemini explanation, v2 model if time | Demo ready |

Cut order if time runs short: drop chess.com, drop Gemini, drop voice, drop v2, drop Stockfish features (use clock-only buckets). The clock-only version still works as a demo.

---

## 6. Risks and limitations

- **Descriptive, not causal.** Human think times reflect how people actually play, including time wasted. The knee is a heuristic, not a proven optimum.
- **Confounding.** Hard positions take longer and also have lower success rates; always condition on difficulty.
- **Information loss.** Bucketing collapses different positions into the same budget.
- **Sparse cells.** Rare combinations have noisy statistics; use minimum counts and fallbacks.
- **Eval noise.** Lichess evals come from varying engine depths; use thresholds, not exact deltas.
- **Selection bias.** Only games with eval annotations are used; they may differ from the average game.
- **DOM fragility.** Site markup changes can break the extension.
- **Fair play.** Keep the tool restricted to practice games against bots and comment only on time, never on moves.
- **Cost.** Compute dominates. Suspend or shut down instances when idle, and check each sponsor's current pricing and any hackathon credits.

---

## 7. Deliverables checklist

- [ ] Ingest script and a loaded month of data in Tiger Data
- [ ] `move_metrics` table with think time, win-probability loss, and success label
- [ ] Stockfish MultiPV difficulty features for a sample
- [ ] Analysis notebook with success-versus-time curves and the baseline comparison
- [ ] Versioned lookup-table JSON
- [ ] MV3 extension working on Lichess bot games
- [ ] (Optional) v2 parametric model, API, voice nudge, Gemini explanation
- [ ] README and short write-up of method and limitations