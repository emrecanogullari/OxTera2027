# Predict API (frontend contract)

The extension / frontend talks to the model over **JSON** via `POST /predict`.

FastAPI packs each request into the CSV expected by Aniket’s [`oracle_predict`](../../Aniket/model_training/cpp/README.md), runs the model for that speed, and returns the extension contract in [`dummy_predict.json`](dummy_predict.json).

Feature names and units come from [`Aniket/FEATURE_SET.md`](../../Aniket/FEATURE_SET.md).

## Run the server

```bash
cd Peter/api
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000
```

`--host 0.0.0.0` listens on all interfaces so other devices on your LAN can reach the API (not just this PC).

**This machine**

- Health: `GET http://127.0.0.1:8000/health`
- Predict: `POST http://127.0.0.1:8000/predict`
- Docs: `http://127.0.0.1:8000/docs`

**Other devices on the same Wi‑Fi** — use this PC’s LAN IP (find with `ipconfig` → IPv4 on Wi‑Fi):

- Health: `GET http://<LAN-IP>:8000/health`
- Predict: `POST http://<LAN-IP>:8000/predict`
- Docs: `http://<LAN-IP>:8000/docs`

If another device cannot connect, allow inbound TCP 8000 in Windows Firewall.

`model.version` is `oracle-cpp-v1`. The server prefers the C++ `oracle_predict` binary under `Aniket/model_training/cpp/`; if that binary cannot run on this OS, it loads the same `models/<speed>.txt` files in-process.

## Smoke-test client

With the server running in another terminal:

```bash
cd Peter/api
python test_client.py
```

This POSTs `examples.blitz_middlegame.request` from `dummy_predict.json` and prints the JSON response.

## Endpoints

| Method | Path | Body | Response |
|---|---|---|---|
| `GET` | `/health` | — | `{ "ok": true }` |
| `GET` | `/predict/schema` | — | feature keys + live example |
| `POST` | `/predict` | pre-built feature JSON | response JSON below |
| `POST` | `/predict/live` | raw scrape (`site`, clocks, fen/moves, …) | same response shape |

Live path: extension site adapters POST raw state → `live_features.py` builds the speed + feature vector (python-chess + optional Stockfish via `STOCKFISH_PATH`) → `oracle_predict`.

**Dev base URL:** `http://127.0.0.1:8000`  
**Content-Type:** `application/json`

## Request

```json
{
  "speed": "blitz",
  "game_id": "optional-correlation-id",
  "features": { "...": "named features for that speed" }
}
```

- `speed` is one of `bullet`, `blitz`, `classical`.
- `features` must include **exactly** the keys listed for that speed in `FEATURE_SET.md` (also copied under `feature_keys_by_speed` in the dummy file).
- Do not send labels (`time_spent`, `blunder`) — those are outputs only.
- Values are numbers; clocks and think times are in **seconds**. `wp_self` is **0–100**. `elo_self` and `ply` are integers.

### Feature keys by speed

| Speed | Keys (count) |
|---|---|
| bullet | `clock_self`, `clock_opp`, `clock_ratio`, `base`, `inc`, `prev_self_spent`, `avg_self_spent`, `prev_opp_spent`, `elo_self`, `ply`, `mat_total`, `mat_diff`, `n_legal`, `n_captures`, `wp_self`, `abs_cp`, `last_swing`, `prior_blunders_self` (18) |
| blitz | same as bullet but **no** `base` (17) |
| classical | `clock_self`, `clock_ratio`, `frac_self`, `prev_self_spent`, `avg_self_spent`, `prev_opp_spent`, `elo_self`, `ply`, `mat_total`, `mat_diff`, `n_legal`, `n_captures`, `wp_self`, `abs_cp`, `last_swing`, `prior_blunders_self` (16) |

## Response

```json
{
  "speed": "blitz",
  "game_id": "optional-correlation-id",
  "predictions": {
    "time_spent_s": 5.4,
    "time_spent_p50_s": 4.0,
    "time_spent_p75_s": 7.0,
    "p_blunder": 0.12
  },
  "model": {
    "version": "oracle-cpp-v1",
    "targets": ["time_spent", "blunder"]
  }
}
```

| Field | Meaning | UI use |
|---|---|---|
| `time_spent_s` | Point estimate = model `think_median` (s) | Primary “typical think” number |
| `time_spent_p50_s` | Model `think_median` (s) | Softer display |
| `time_spent_p75_s` | Model `think_high` (upper of 80% range) | When elapsed exceeds this → nudge |
| `p_blunder` | Model `p_blunder` in [0, 1] | Blunder chance meter |

## Using the dummy file (offline mock)

1. Open [`dummy_predict.json`](dummy_predict.json).
2. Pick an entry under `examples` (e.g. `blitz_middlegame`).
3. Treat `request` as what you would `POST`, and `response` as what you render.
4. Or call the live MVP server instead of hardcoding `response`.

### Example scenarios in the fixture

| Key | Situation |
|---|---|
| `blitz_middlegame` | Normal midgame, moderate times |
| `bullet_tactical` | Sharp position, higher blunder risk |
| `classical_calm` | Long clocks, low blunder chance |
| `blitz_time_scramble_high_blunder` | Low clock, high `p_blunder` — good nudge / danger UI test |

### Minimal fetch sketch

```js
const res = await fetch("http://127.0.0.1:8000/predict", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(example.request),
});
const data = await res.json();
// data.predictions.p_blunder, data.predictions.time_spent_p75_s, ...
```

## Errors

| Status | When | Frontend |
|---|---|---|
| `400` | Missing/unknown feature keys, bad `speed` | Show “bad input”; do not update meters |
| `503` / network fail | Model offline | Show “model offline”; keep last good panel or hide |

## Related

- Feature definitions: [`Aniket/FEATURE_SET.md`](../../Aniket/FEATURE_SET.md)
- Product plan (v1 lookup JSON vs v2 API): [`../docs/project-plan.md`](../docs/project-plan.md)
- Older win/draw/loss sketch in the vault is **not** this contract — use this file instead.
