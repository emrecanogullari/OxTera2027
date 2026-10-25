# BlunderBot

A Chrome overlay for a live Chess.com or Lichess game. On your turn it shows two numbers for the position in front of you:

- how long a player in this kind of spot usually thinks
- the chance that the move you are about to play will be a blunder

A blunder here means the move drops your win chance by 20 points or more. The panel does not name a move. It scores the situation before you choose one.

## How a turn works

Once the pieces and the move list have settled, the page script reads the board, both clocks, the ratings, the time control, and the move names. It sends that snapshot to a small API. The API turns the snapshot into the same kind of input format the models were trained on, runs the models, and returns JSON. The overlay prints the think time in seconds and the blunder chance as a percent.

The page itself never calls the server. A background script does, so an HTTPS chess site can talk to an HTTP API. The address is `backendBase` in the extension’s local storage. If it has never been set, the background script uses `http://10.21.244.181:8000`.

One request is made per new position. A ticking clock does not send another one.

## What calculates the numbers

The main brain of the system is a Machine Learning algorithm that has been trained on the following inputs:

| Input | Meaning |
|---|---|
| `clock_self`, `clock_opp` | seconds left for you and your opponent as you start thinking |
| `clock_ratio` | your clock divided by theirs |
| `base`, `inc` | starting time and the increment. Bullet uses `base`. Classical uses `frac_self` (your clock divided by the start time) instead of the opponent’s clock and the increment |
| `prev_self_spent`, `avg_self_spent`, `prev_opp_spent` | your last think, your average think so far, and their last think, in seconds |
| `elo_self` | your rating, read from the page |
| `ply` | half-move number. 1 is White’s first move |
| `mat_total`, `mat_diff` | material on the board, and your material minus theirs. Pawn 1, knight 3, bishop 3, rook 5, queen 9. The start is 78 and 0 |
| `n_legal`, `n_captures` | legal moves in the position, and how many of them capture |
| `wp_self` | your win percent, 0–100, from the Stockfish score |
| `abs_cp` | how decided the position is: the absolute centipawn score, mate mapped to 1000 |
| `last_swing` | how many win-percent points the previous move changed for the player who made it |
| `prior_blunders_self` | how many of your earlier moves already dropped your win percent by 20 or more |



During a game **Stockfish** reads the position. The live path searches it to depth 12, once for the current board and once for the board before the last move. That search produces a centipawn score from White’s point of view. The score is capped at ±1000. A mate is treated as a win or a loss. Centipawns become a win percent with the Lichess curve:

`win% = 50 + 50 × (2 / (1 + exp(−0.00368208 × cp)) − 1)`

If you are Black, your win percent is `100 − white’s win percent`. Stockfish is found from `STOCKFISH_PATH`, or from `stockfish` on `PATH`. If it is not running, the eval fields are left empty and the blunder chance falls back to a low baseline, about 1–3%. That number is not a real read of the position.

**The models** are gradient-boosted trees (`HistGradientBoosting`), trained on analysed Lichess games: 2,000 games each for bullet, blitz, and classical. There are three targets per speed: seconds you will spend on this move, the chance this move is a blunder, and the chance a blunder happens on this move or one of your next four. The trees were exported to text files under `Aniket/model_training/cpp/models/`. The API loads those files once at startup and walks the trees in process. It does not start a new program for each move.

The speed is chosen from the clock on the page. Estimated length is `base seconds + 40 × increment`. Up to 179 seconds is bullet, up to 479 is blitz, and 1500 or more is classical. A 3+0 game and a 3+2 game are both blitz. Rapid and ultrabullet have no model, so the API rejects them.

## What goes into a prediction

Every row describes the position **before** you move. The model for that speed sees only its own columns, in a fixed order.

The panel uses two fields from the reply: `predictions.time_spent_s` (the median think time) and `predictions.p_blunder` (a probability from 0 to 1). The JSON also includes a low and high think time and the next-five-moves blunder chance. `p_blunder` is the chance the drop will be at least 20 points. It is not the size of the drop.

## How to Run the extension

##### How to run the analysis server in the compute device

1. Install [Stockfish](https://stockfishchess.org/) and either put it on your `PATH` or set `STOCKFISH_PATH` to the binary.
2. Start the API from this repo:

```bash
cd Peter/api
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000
```

Health check: `GET http://127.0.0.1:8000/health` should return `{"ok": true}`.

3. Point the extension at that server. The default is `http://10.21.244.181:8000`. For a server on this machine, open the service-worker console on `chrome://extensions` and run `chrome.storage.local.set({ backendBase: "http://127.0.0.1:8000" })`. The host must also be listed under `host_permissions` in `Frontend/manifest.json`. Localhost, `10.21.244.181`, and any host on port 8000 are already listed.
4. In Chrome, open `chrome://extensions`, turn on **Developer mode**, choose **Load unpacked**, and select the `Frontend` folder. After you change `background.js` or `manifest.json`, click **Reload** on that card.
5. Open a bullet, blitz, or classical game on Chess.com or Lichess. A **Coach HUD** appears at the top right. Drag it by the panel. On your turn it reads the board, then shows the think time and the blunder percent.

## Where the code lives

| Path                     | What it is                                                                                                                                     |
| ------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| `Frontend/`              | Chrome extension: page readers, HUD, and the background request                                                                                |
| `Peter/api/`             | FastAPI server, live feature builder, model runner                                                                                             |
| `Aniket/eda/`            | Feature definitions and the training tables                                                                                                    |
| `Aniket/model_training/` | The nine trained models and the exported tree files                                                                                            |
| `Peter/`                 | PGN ingest, database, and Stockfish annotation for the training set                                                                            |
| `Emre/`                  | Separate C++ work on choosing a move. The HUD does not call it. Mostly used for data parsing and algo work, get data for the model to train on |
