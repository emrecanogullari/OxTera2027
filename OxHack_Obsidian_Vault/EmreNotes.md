## TLDR:
Under OxTera2027 Folder: Make commands
- `make test` runs the checks
- `make examples` shows one clear choice and one close call
- `make replay` scores the short sample game
- `make watch GAME_ID=theid` follows a live Lichess game
- `make pgn PGN=path/to/game.pgn` scores a saved game
- `make fetch GAME_ID=theid` downloads a finished game and scores it




## TLBSR (Too Long But Still Read) 
The engine currently takes a chess position and a list of candidate moves, then says which move looks most likely, how sure that move is, and whether the choice is clear or a close call. It can also check that guess after the real move is played. It lives in `OxTera2027/Emre` and is run with `make` from `OxTera2027` or from the OxHack2027 folder.

**What it can do now**
- Read a position as FEN, from a live Lichess game or a saved PGN file.
- List legal moves and throw out illegal ones. Standard chess only.
- Take candidate moves with a score, a confidence, and a confidence spread. At most 64 moves.
- Drop moves it is not confident about. The cautious confidence is confidence minus its spread, and the cutoff is 0.5.
- Compare the best score with the second best. A big gap is labeled **clear best**. A small gap is labeled **many close moves**.
- Report the likely move, its chance, and the variance. Variance is how spread out the chances are: 0 means one move took all the chance, and a number near 1 means the chance is split.
- Score a guess as a hit or a miss once the played move arrives.
- Keep the white and black clocks with the position. They are not used in the math yet.
- Show a small panel at `http://127.0.0.1:8765/` while watching a live game. The shown move stays put when two moves are almost tied, so the display does not flicker.

Fow now, the database is a fake table with two scripted positions: the start of a game, and the position after e4 start. One function, `to_candidates`, is the only place that knows the outside row names (`move` or `uci`, `score`, `confidence`, `std`, `n`). A real database can replace the fake table without changing the judgment.

**What each command does**

| Command                         | What happens                                                                                                                                                                    |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `make test`                     | Runs the automatic checks: clear choice, close call, illegal move dropped, low confidence dropped, clocks from a stream line, replay hit and miss, sticky hold and sticky swap. |
| `make examples`                 | Judges two made-up lists on the starting position. One is a clear e2e4. The other is a close call among e2e4, d2d4, and g1f3.                                                   |
| `make replay`                   | Walks a two-move sample. The first guess hits (e2e4). The second misses (it guessed c7c5, the game played e7e5).                                                                |
| `make watch GAME_ID=...`        | Follows that Lichess game, judges each new position, and serves the panel.                                                                                                      |
| `make pgn PGN=path/to/game.pgn` | Reads a saved game and scores each move against the fake table.                                                                                                                 |
| `make fetch GAME_ID=...`        | Downloads a finished Lichess game and scores it the same way.                                                                                                                   |

**What it cannot do yet**

A real game has almost no rows in the fake table, so `watch`, `pgn`, and `fetch` will mostly report no move, or a miss. Lichess also delays a public live game by three moves. The engine does not remove that delay.

The clocks are saved and then ignored. `apply_timing` returns the chances unchanged. There is no trained timing model, no blunder chance, and no win chance. There is no screen reading and no browser extension.

**What is needed next**

1. The real database, in place of the fake table. It should return moves with a score, a confidence, a confidence spread, and a count, looked up by the position.
2. The timing model, which would use the clocks already stored on the position and adjust the chances inside `apply_timing`.