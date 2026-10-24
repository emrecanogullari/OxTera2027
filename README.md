# Chess Think-Time Coach

A Manifest V3 browser extension that, while you practise against a bot on Lichess, suggests a think-time budget for the current position and nudges you when you exceed it.

It comments only on time. It never suggests a move. It stays inactive in games against humans.

The working spec is [docs/project-plan.md](docs/project-plan.md). Stockfish workers: [database_work/stockfish_access.md](database_work/stockfish_access.md). Outcome models: [database_work/model_training_access.md](database_work/model_training_access.md).

## Repo layout

| Path | Role |
|---|---|
| `ingest/` | Stream and filter Lichess PGN dumps |
| `sql/` | Tiger Data schema, metrics, lookup-table queries |
| `annotate/` | Stockfish MultiPV difficulty features |
| `model/` | Analysis, knee detection, optional LightGBM |
| `extension/` | Chrome MV3 overlay |
| `api/` | Optional FastAPI host for v2 |
| `docs/` | Product plan |

## Initial data slice

One monthly Lichess dump, rated blitz only (`180+0` and `300+0`), Elo 1000–2200, games that already have `[%clk]` and `[%eval]`.

## Cut order

chess.com → Gemini → voice → v2 model → Stockfish features. Clock-only buckets still demo.
