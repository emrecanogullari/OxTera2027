# Clock coach: understanding and build plan

A Chrome extension on Lichess that, from the current position and the clocks, says how likely you are to win and how likely the move you are about to play is a blunder. A thin border lights up when that blunder risk is coming from thinking too little or too long. The models are trained on old Lichess games and judged on games they never saw.

This is a hackathon product. The board already exists. We add the prediction.

---

## End goal

Someone opens Lichess with the extension installed and a small local server running. On a game replay, an analysis board, or an unrated game, a panel shows:

- **Win chance** for the side about to move, as win / draw / loss
- **Blunder chance** for the move they are currently thinking about
- A short reason: rushing, overthinking, or clock danger

The page itself stays readable. Only a border around the screen glows, stronger when the risk is higher, and it fades when the risk drops. The numbers move while the clock ticks. Thinking longer, or having less time left, changes them without a refresh.

Separately, on a held-out slice of real games, we show that those numbers mean something: when the model says 70%, about 70% of those positions ended as a win, and the moves it called likely blunders really were blunders when Stockfish scored them.

Done means all of the following exist:

1. A trained win model and a trained blunder model, saved to disk
2. A written test report on the untouched 35% of games, including a comparison against simple baselines
3. A local server that scores one snapshot in well under a second
4. A Chrome extension that reads a Lichess position and clocks, calls that server, and draws the panel and the border
5. A replay of one held-out game where the panel’s prediction and the real result can be shown side by side

The extension never suggests a move, never highlights a square, and never plays for the user. It only talks about time and risk.

---

## What we are claiming

Time is part of the position. Two boards can show the same pieces and have very different futures if one player has 12 seconds and the other has 2 minutes. A fast move in a sharp position is a different kind of risk from a long think that eats the rest of the clock.

The model learns those patterns from human games, not from a perfect engine. Stockfish is used offline as a judge of whether a move was a blunder. The thing we predict is how humans actually played under a clock.

---

## The Markov choice

A full game has dozens of earlier moves. Feeding every previous ply into the model makes the input huge, and most of that history is already sitting in the current position.

We use the Markov assumption: the chance of what happens next depends on the current state, not on the path that reached it. The current state is the snapshot below. Clocks, the position, the rating, the time control, and how long the player has been thinking on this move are enough.

This is not a textbook Markov chain. A chain would store a transition probability for every possible chess position. There are far too many positions. We keep the assumption and train an ordinary model that maps the snapshot to two probabilities.

One extra lag is allowed inside the snapshot, because it is still “where things stand right now”:

- how long this player thought on their previous move
- how much the evaluation swung on the previous move, once Stockfish has labeled the game

The full move list from move 1 is not a model input.

---

## The snapshot

Every training row, and every live request, is one moment when a player is about to move.

### Position

Computed from the FEN with `python-chess`. These describe the board without storing the game history.

| Feature | What it is |
| --- | --- |
| `side_to_move` | White or black, the player we score |
| `ply` | Half-move number |
| `pieces_left` | Total pieces on the board |
| `material_balance` | Pawn-units of the side to move, minus the opponent (pawn 1, knight 3, bishop 3, rook 5, queen 9) |
| `queens_on` | Whether queens are still on |
| `legal_moves` | Number of legal moves, a stand-in for how tangled the position is |
| `in_check` | Whether the side to move is in check |
| `can_castle` | Whether that side can still castle |

If the strong path below is turned on, add the engine’s view of this position **before** the move:

| Feature | What it is |
| --- | --- |
| `eval_cp` | Centipawns for the side to move, before they move |
| `eval_winpercent` | That eval turned into a 0–100 win percent |

The evaluation after the move is a label, never a feature. Putting it in the features would tell the model the answer.

### Clocks

| Feature | What it is |
| --- | --- |
| `my_clock` | Seconds left for the side to move, at the start of the think |
| `opp_clock` | Seconds left for the opponent |
| `clock_ratio` | `my_clock / (my_clock + opp_clock)` |
| `clock_diff` | `my_clock - opp_clock` |
| `initial_seconds` | Starting clock from the time control |
| `increment` | Increment in seconds |
| `time_pressure` | `my_clock / initial_seconds` |
| `low_30` / `low_10` | Whether `my_clock` is under 30s or under 10s |

### The think

| Feature | What it is |
| --- | --- |
| `think_seconds` | Seconds spent on this move. In the data this is the finished think. Live, it is how long the clock has been running on this turn |
| `think_share` | `think_seconds / my_clock` at the start of the think |
| `prev_think_seconds` | This player’s previous think |
| `instant` | Think under 1 second |
| `long_think` | Think greater than both 8 seconds and 25% of the clock they started the turn with |

### Who is playing

| Feature | What it is |
| --- | --- |
| `my_elo` | Rating of the side to move |
| `opp_elo` | Opponent rating |
| `elo_diff` | `my_elo - opp_elo` |
| `tc_bullet` / `tc_blitz` / `tc_rapid` | One-hot time-control bucket |

Missing ratings are filled with the training median, and a `rating_missing` flag is set.

---

## Two models

Both models see the same snapshot. They answer different questions and have different labels.

### Win model

**Question:** from this snapshot, how does the game end for the side about to move?

**Label:** `win`, `draw`, or `loss`. Resignations, checkmates, and time forfeits all count. A clock that is about to fall to zero is allowed to pull the win chance down, because those games really ended that way.

**Model:** LightGBM multiclass classifier. The panel prints the three probabilities.

### Blunder model

**Question:** if the player commits to a move after this much thinking, how likely is that move a blunder?

**Label:** 1 if the move is a blunder by the rule in the next section, otherwise 0.

**Model:** LightGBM binary classifier. Blunders are the minority, so training uses class balancing. The panel prints the probability, not a hard yes/no.

A move can be a blunder because it was rushed or because the player sat until the position and the clock both got worse. The model is free to learn a U-shape: very short thinks and very expensive thinks can both be risky, and a moderate think in a calm position can be safe. We do not hard-code “longer is safer.”

---

## What counts as a blunder

Stockfish scores the position before the move and after the move, from the mover’s point of view.

Centipawns are converted to a win percent with the Lichess curve:

```text
winning_chances = 2 / (1 + exp(-0.00368208 * cp)) - 1     # from -1 to 1
win_percent     = 50 + 50 * winning_chances               # from 0 to 100
```

Mate scores are turned into a large centipawn value before that formula (`mate in 1` is treated as about 10000 centipawns for the side that is mating, and the opposite for the side that is getting mated). Any move that goes from “not a forced loss” to “forced mate against me” is a blunder.

**Blunder:** the mover’s win percent drops by 30 points or more.

**Mistake (not the training label, useful in the report):** a drop of 20 points or more.

**Inaccuracy (report only):** a drop of 10 points or more.

Before training, check this rule on one game that Lichess has already analyzed. If Lichess’s `??` marks disagree with ours, adopt Lichess’s cutoffs and write the final numbers in this file. The definition stays frozen after that. Changing it after seeing the test score is not allowed.

The engine depth used for labels is **depth 12**, one line, same settings for every position. A blunder is “bad compared with this engine,” not “bad compared with God.” That is fine as long as every row is judged the same way.

---

## Think time from a PGN clock

Lichess stores the clock **after** the move, in a comment like `{ [%clk 0:02:58] }`. The increment is already included in that number. The time control header looks like `[TimeControl "180+2"]`.

```text
think_seconds = clock_before - clock_after + increment
```

For the first move of each side, `clock_before` is the starting time.

Worked example, 180+2, White’s first move, comment `[%clk 0:02:58]`:

```text
think_seconds = 180 - 178 + 2 = 4
```

An instant move can show a clock of `0:03:02`, because the increment arrived and almost no time was spent:

```text
think_seconds = 180 - 182 + 2 = 0
```

Negative results from lag get clipped to 0. Moves with a missing clock are dropped. Games with no clock comments are dropped.

---

## Where the data comes from

Source: the Lichess open database, standard rated games, one month.

- Index: [https://database.lichess.org/standard/](https://database.lichess.org/standard/)
- File name shape: `lichess_db_standard_rated_YYYY-MM.pgn.zst`
- License: CC0
- Clocks are in the move comments. Evaluations are only present on games someone analyzed, so we do not depend on them. We run Stockfish ourselves.

A single month is on the order of **30 GB compressed**. Do not decompress a month onto a laptop. Stream it and stop.

```bash
curl -L "https://database.lichess.org/standard/lichess_db_standard_rated_2026-09.pgn.zst" \
  | zstd -dc \
  | python training/parse_pgn.py --max-games 8000 --out data/moves.parquet
```

Stopping `curl` early is acceptable. `zstd -dc` will end with a truncation error after the games we already wrote. That is the intended way to take a sample.

### Which games we keep

- Rated standard chess
- A parseable `TimeControl` with an increment field (bullet, blitz, or rapid)
- Both sides have a clock on every kept move
- The game lasted at least 10 ply (throws out instant aborts)
- Termination is a normal result or time forfeit

Bullet, blitz, and rapid all stay in. The time-control bucket is a feature, because a 10-second think means opposite things in bullet and in rapid. Correspondence games stay out.

Default sample: **8,000 games**. That is enough to train and still small enough to label overnight. If Stockfish is too slow on the day, drop to 3,000 games before touching the test set. Write the final count in the report.

### Personal games, later

If the extension can see a Lichess username, a second pass can download that user’s recent games from `https://lichess.org/api/games/user/{username}?clocks=true` and estimate their typical think time. The live snapshot then includes `think_seconds / this_player_median_think`. Until that exists, the rating and the time control stand in for “a player like you.” This pass is optional. The demo does not depend on it.

---

## The 65 / 35 cut

The database is used for two jobs, and a game may only be in one of them.

| Slice | Share of games | Job |
| --- | --- | --- |
| Train pool | 65% | Fit the models. Inside this pool, use about 80% to fit and 20% to decide trees and early stopping |
| Test | 35% | Touch once, at the end, to compare predictions with what those games actually did |

Rules:

- Split on **game id**, never on moves. Every ply of a game is in the same slice. A random move split leaks the player, the opening, and the result into both sides, and the test score becomes a lie.
- Stratify on result (win / draw / loss from White’s point of view) and on time-control bucket, so the test set still contains time forfeits and draws.
- Seed is `27`. Same seed, same split.
- Fit every median, every calibration, and every threshold on the train pool only.
- The test set is not for choosing the blunder cutoff, the model type, or the border threshold.

Suggested check on a 8,000-game sample: about 5,200 train-pool games and 2,800 test games. Move counts will be higher, because each game contributes many rows.

---

## How we compare predictions with real games

The test report is part of the product, not a side note. It answers “would this number have been right on games we did not train on?”

### Win chance

For every test row we store the predicted win probability for the side to move, then the real result.

- **Log loss** and **Brier score** on the three-way outcome
- **Calibration table:** bucket predictions (0–10%, 10–20%, …). In the 70–80% bucket, the actual win rate should land near that band. This is the main picture to show
- **Slices,** reported separately, because this is where time should matter:
  - `my_clock` under 30 seconds
  - `my_clock` under 10 seconds
  - `think_seconds` under 1
  - `think_share` over 0.25
  - time-forfeit games only

### Blunder chance

For every test move we store the predicted blunder probability and the Stockfish label.

- ROC AUC
- Average precision
- A calibration table in the same style as the win model
- Blunder rate by think-time bucket (0–1s, 1–3s, 3–8s, 8–20s, 20s+) next to the model’s average prediction in that bucket

### Baselines the report must include

The model has to beat something obvious, or the number is just a gadget.

| Baseline | What it predicts | Why it is there |
| --- | --- | --- |
| Outcome frequency | Always the training win/draw/loss rates | Floor for the win model |
| Clock-only model | Same model family, clocks and think time, no position features | Shows that the board still matters |
| Position-only model | Material, mobility, ply, no clocks | Shows that the clock adds something the pieces do not |
| Blunder frequency | Always the training blunder rate | Floor for the blunder model |

The sentence we want from the slices: on low-clock positions, the full model beats the position-only model. If it does not, say so in the report. A hackathon demo can survive an honest negative. It cannot survive a hidden one.

### One game, played back

Pick one test game that contains a time scramble. Step through it ply by ply. Show the predicted win chance beside the eventual result, and mark the moves that were real blunders. This is the “compare with the observed match” view, and it is the fallback demo if the extension misbehaves.

---

## Live behavior

Historical rows are finished moves: we know how long they eventually thought. Live, the think is still going. Every half second the extension sends the snapshot again with a larger `think_seconds`. The blunder model returns the risk of committing **now**, after this much thought.

That is an approximation. The training set only contains thinks players actually finished, not every second they considered along the way. For the hackathon we accept it: the curve at 6 seconds means “moves that were played after about 6 seconds, in states like this, were blunders this often.”

### When the border lights

The border has two colors and an off state. It is a glow around the viewport, `pointer-events: none`, so it never blocks clicks. Opacity follows the risk, capped so the page stays readable. A short fade (about 300ms) keeps it from flickering.

Hysteresis, so it does not strobe around a threshold:

- Turn **on** when the triggering probability crosses **0.35**
- Turn **off** when it falls under **0.28**

Colors:

| State | Color | When |
| --- | --- | --- |
| Off | none | Risk under the off threshold |
| Rush | amber | Blunder probability is high and `think_seconds` is under 2, or the move is still in the instant band |
| Slow | red | Blunder probability is high, or win chance has dropped, while `think_share` is over 0.25 or `my_clock` is under 15 seconds |

If both rules fire, slow wins. Running out of time is the more urgent fact.

The panel text matches the color: “rushing” or “this think is eating the clock.” The border does not flash for a mild risk.

---

## Fair play

Lichess treats engine help during a rated game as cheating. This extension is a coach built from engine-labeled data. Even without showing a best move, a live blunder warning changes how someone plays.

Supported surfaces:

- Lichess analysis board
- Replay of a finished game
- Unrated games and games against the computer, for the demo only

Rated games are out of scope. The extension should detect a rated live round if it can, and refuse to show advice there. The README and the demo script say this out loud.

---

## Tech stack

### Training and server

| Piece | Choice | Why |
| --- | --- | --- |
| Language | Python 3.11+ | Parsing, modeling, and the server in one language |
| PGN and boards | `python-chess` | Clocks, FENs, legal moves, talking to Stockfish |
| Tables | `pandas` + `pyarrow` | Move rows in Parquet |
| Models | `lightgbm` | Strong on mixed numeric features, fast to train, easy to save |
| Model files | `joblib` | Load from the server |
| Server | `fastapi` + `uvicorn` | One POST endpoint the extension can call |
| Engine | Stockfish binary | Offline labels. Optional live eval, off by default |
| Compression | `zstandard` CLI (`zstd`) | Stream the monthly dump |

Install:

```bash
brew install stockfish zstd
python -m venv .venv
source .venv/bin/activate
pip install python-chess pandas pyarrow lightgbm scikit-learn joblib fastapi uvicorn numpy
```

`scikit-learn` is there for the train/test split, calibration, and metrics.

### Extension

| Piece | Choice | Why |
| --- | --- | --- |
| Browser | Chrome, Manifest V3 | The surface we committed to |
| UI | Plain HTML/CSS/JS content script | No build step |
| Board | Lichess, already open | We do not draw a chessboard |
| Model runtime | The local Python server | Porting LightGBM into the extension is a stretch goal we are not taking |

No React, no backend host in the cloud, no database server. Parquet files and two model files are the storage.

### What we considered and set aside

- **Chess.com.** The page is hostile to readers, and the data we can actually train on is Lichess.
- **A board we build ourselves.** Lichess already has the board, the clocks, and the rules.
- **A giant transition table.** That is the Markov chain we are not building.
- **A neural net on raw boards.** LightGBM on the snapshot is trainable during a hackathon and easier to explain.
- **Downloading a full month.** Stream a sample.

---

## Architecture

```text
Lichess page
  position, clocks, think timer
        |
        | content script, twice a second
        v
Chrome extension panel + border
        |
        | POST http://127.0.0.1:8000/predict
        v
FastAPI
  features from FEN + clocks
  win model, blunder model
        ^
        | loaded once at startup
        |
  model_win.joblib
  model_blunder.joblib
        ^
        |
  training pipeline
  stream PGN -> rows -> Stockfish labels -> 65/35 split -> LightGBM
```

Live Stockfish is not on this path unless we explicitly enable the strong position features. The default server scores a FEN with `python-chess` only, so the request stays fast and the extension still works offline from the engine.

---

## Repository layout

```text
clock-coach/
  README.md
  requirements.txt
  data/                      # gitignored, large
    moves.parquet
    labeled.parquet
  models/
    model_win.joblib
    model_blunder.joblib
    feature_list.json
    train_medians.json
  training/
    parse_pgn.py             # stream PGN, write one row per move
    label_stockfish.py       # add evals and blunder labels
    train.py                 # split, fit, save
    evaluate.py              # the 35% report
  server/
    app.py                   # POST /predict, GET /health
    features.py              # the same feature code train and serve use
  extension/
    manifest.json
    content.js
    panel.css
    read_board.js            # FEN + clocks from the Lichess page
  report/
    metrics.md               # written by evaluate.py, pasted into the demo
```

`training/features.py` and `server/features.py` must be the same code. Duplicate formulas will make live numbers disagree with the report. Put the feature function in one module and import it from both.

---

## Training pipeline

### 1. Parse

Read games from stdin until `--max-games` kept games. For each kept move, write a row with the FEN **before** the move, both clocks at the start of the think, `think_seconds`, ratings, time control, ply, and the eventual result from the mover’s point of view.

Also store `game_id` and a `row_id`. The split uses `game_id`.

### 2. Label

For each row, ask Stockfish for the position before the move and the position after the move that was played.

```python
score = info["score"].pov(mover).score(mate_score=10000)
```

Use the mover’s point of view both times. `cp_loss = score_before - score_after`. Convert both scores with the win-percent formula. `blunder = winpercent_drop >= 30`.

Save `eval_cp` and `eval_winpercent` from the **before** position only. Do not save the after-eval as a feature column. Keep `blunder` and the drop in a label column.

Run several Stockfish processes, one per core. Depth 12. If a position takes too long, cap it at 100ms and record `eval_capped` so we can drop those rows if they look noisy.

### 3. Features

Add the position features from the FEN. Drop rows with missing clocks or missing labels. Write `labeled.parquet`.

### 4. Split and train

```text
games -> 65% train pool, 35% test, stratified, seed 27
train pool -> 80% fit, 20% early stopping
```

Train the win model and the blunder model. Save the models, the column order, and the medians used to fill missing ratings.

### 5. Evaluate

Run `evaluate.py` once on the test games. Write `report/metrics.md` with the metrics, the calibration tables, the slices, and the baselines. Generate the ply-by-ply JSON for one scramble game at `report/demo_game.json`.

---

## Server contract

`GET /health` returns `{ "ok": true }`.

`POST /predict`

```json
{
  "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
  "my_clock": 176.0,
  "opp_clock": 180.0,
  "think_seconds": 4.2,
  "prev_think_seconds": 2.0,
  "initial_seconds": 180,
  "increment": 2,
  "my_elo": 1510,
  "opp_elo": 1480,
  "time_control": "blitz"
}
```

```json
{
  "win": 0.46,
  "draw": 0.32,
  "loss": 0.22,
  "blunder": 0.18,
  "border": "off",
  "intensity": 0.0,
  "reason": "ok"
}
```

`border` is `off`, `rush`, or `slow`. `intensity` is between 0 and 1 and becomes the border opacity. `reason` is `ok`, `rushing`, or `eating_clock`.

Invalid FEN returns 400. If the server is down, the extension shows “model offline” and draws no border.

---

## Extension

### Manifest

- Manifest V3
- Content script on `https://lichess.org/*`
- Host permission for `http://127.0.0.1:8000/*` only
- No broad site access, no remote code

### Reading the page

Lichess class names can change. Confirm these on the day and adjust `read_board.js` only.

- Clocks live in `.rclock-top` and `.rclock-bottom`. The active clock has a running state. Read the text in `.time`.
- Whose clock is “mine” depends on board orientation. `orientation-black` on the board wrap means the bottom clock is Black.
- Pieces are `piece` elements inside the chessground board. Their square comes from the transform and the orientation. Rebuild the FEN from the piece list with `chess.js` in the content script, or send a piece map to the server and let `python-chess` build the FEN. Rebuilding every tick avoids replaying the whole game.
- Ratings are the numbers next to the usernames. If a page has none, send `null`.
- Think time: when the active clock flips to the side to move, store `performance.now()`. `think_seconds` is the time since that flip. Reset on every move.

Parse clock text `m:ss` and `h:mm:ss` into seconds. A clock that shows tenths in a time scramble still parses.

### Panel

A fixed box in a corner, away from the Lichess clocks:

```text
Win 46%    Draw 32%    Loss 22%
Blunder if you move now: 18%
```

The third line appears only when the border is on.

### Border

A full-viewport layer, no pointer events, a colored outline only, opacity from `intensity` with a cap around 0.75. The center of the page is untouched.

### Loop

Every 500ms, if the FEN or the think time has changed, POST `/predict` and update the panel. Skip the request if the FEN failed to parse. Never queue more than one request; drop stale responses.

### Rated-game refusal

If the page is a live rated game, render nothing and log a single console line. Replay and analysis keep working.

---

## Demo script

About one minute.

1. Open the held-out scramble replay. Start at a calm position: moderate win chance, low blunder chance, no border.
2. Step to a move the player made in under a second. The blunder chance jumps. If that move really was a blunder, say so.
3. Step into the time scramble. The win chance leaves the engine-looking value and drops because the clock is gone. The border goes red on the long think that spends the last seconds.
4. Cut to the calibration picture: “when we said about 70% on games we did not train on, this is how often they won.”
5. One sentence on the split: 65% of games trained the model, 35% stayed untouched until this check.

---

## Work plan

Three tracks can run in parallel after the column list is frozen. The feature list in this file is that freeze. Changing a feature later means relabeling is not required, but retraining is, and the server and the trainer must change together.

### Track A — data and labels

- [ ] Create the repo layout, venv, and `requirements.txt`
- [ ] Implement `parse_pgn.py` and the think-time formula, with the worked 180+2 example as a unit test
- [ ] Stream one month and write about 8,000 games to `moves.parquet`
- [ ] Confirm the blunder cutoff on one Lichess-analyzed game, then lock it
- [ ] Implement `label_stockfish.py` and produce `labeled.parquet`
- [ ] Spot-check 20 rows by hand: clocks, side to move, and a obvious blunder

### Track B — models and the test

- [ ] Implement the shared feature function
- [ ] Split by game, seed 27, 65 / 35, stratified
- [ ] Train both LightGBM models with early stopping inside the train pool
- [ ] Run the test report with baselines and clock slices
- [ ] Export `report/demo_game.json` for the scramble replay
- [ ] Save models, column order, and medians

### Track C — server and extension

- [ ] Implement `POST /predict` and `GET /health` against a tiny fake model first, so the extension can be built before training finishes
- [ ] Swap in the real models without changing the JSON contract
- [ ] Read clocks, orientation, and a FEN from Lichess
- [ ] Draw the panel and the border with hysteresis
- [ ] Refuse to advise on rated live games
- [ ] Show “model offline” when the server is down

### Together, at the end

- [ ] Play back the held-out game through the panel
- [ ] Run the live loop on an analysis board or an unrated game and confirm the border tracks a rushed move and a long think
- [ ] Read the test report once more and put the calibration result in the demo
- [ ] Write a short README: how to start the server, how to load the extension, and the rated-game rule

---

## Risks and backups

| Risk | What we do |
| --- | --- |
| The monthly file is enormous | Stream and stop at 8,000 games. Never unzip the whole month |
| Stockfish labeling is too slow | Drop to 3,000 games or depth 10. Keep the split rules |
| Lichess markup changed and the FEN reader fails | Fall back to `report/demo_game.json` played through the same panel. The test report still stands |
| The clock features do not beat the position-only baseline | Show that result. Tune only inside the train pool, then accept the test number |
| The extension would be used in a rated game | It stays silent there |
| Live Stockfish would make requests slow | Leave it off. Position features come from `python-chess` |

The replay-plus-report path is the demo we can guarantee. The glowing border on a live Lichess clock is the demo we want on top of it.

---

## Decisions already made

- The product is a Lichess companion, not a new chess site
- The state is the current snapshot, under the Markov assumption, implemented as a normal model
- Two outputs: win/draw/loss, and blunder probability
- The border warns about rushing and about a think that is eating the clock
- Data is a streamed Lichess sample, labeled by Stockfish
- 65% of games train, 35% of games test, split by whole game
- The test comparison is calibration against real results, plus baselines
- Python, LightGBM, FastAPI, and a plain Chrome extension
- No suggested moves

## Defaults we can still change before training starts

| Choice | Default |
| --- | --- |
| Month | `lichess_db_standard_rated_2026-09.pgn.zst` |
| Sample size | 8,000 games |
| Engine depth | 12 |
| Blunder | 30 point drop in win percent, after the one-game check |
| Split seed | 27 |
| Border on / off | 0.35 / 0.28 |
| Personal rating curve | Off until the core demo works |

---

## Glossary

| Term | Meaning |
| --- | --- |
| Snapshot | The current position, clocks, think time, ratings, and time control |
| Markov assumption | The next prediction uses the snapshot only, not the whole game |
| Think time | Seconds used on this move, from the clocks |
| Blunder | A move that drops the mover’s Stockfish win percent by 30 points or more |
| Train pool | 65% of games, the only data allowed to shape the model |
| Test | 35% of games, used once to compare predictions with real outcomes |
| Border | A non-blocking outline that glows when the current think is risky |
