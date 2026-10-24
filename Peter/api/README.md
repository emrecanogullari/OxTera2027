# Predict API (frontend contract)

The extension / frontend talks to the model over **JSON** via `POST /predict`.  
Until the real FastAPI service is up, use [`dummy_predict.json`](dummy_predict.json) as the contract and mock responses.

Feature names and units come from [`Aniket/FEATURE_SET.md`](../../Aniket/FEATURE_SET.md).

## Endpoints

| Method | Path | Body | Response |
|---|---|---|---|
| `GET` | `/health` | — | `{ "ok": true }` |
| `POST` | `/predict` | request JSON below | response JSON below |

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
    "version": "dummy-v0",
    "targets": ["time_spent", "blunder"]
  }
}
```

| Field | Meaning | UI use |
|---|---|---|
| `time_spent_s` | Point estimate of think time (s) | Primary “typical think” number |
| `time_spent_p50_s` | Median / typical (s) | Softer display |
| `time_spent_p75_s` | Upper typical / nudge budget (s) | When elapsed exceeds this → nudge |
| `p_blunder` | P(this move loses ≥ 20 win%) | Blunder chance meter (0–1) |

Field names are stable: swap dummy → live model without changing the frontend parser.

## Using the dummy file

1. Open [`dummy_predict.json`](dummy_predict.json).
2. Pick an entry under `examples` (e.g. `blitz_middlegame`).
3. Treat `request` as what you would `POST`, and `response` as what you render.
4. For local mocks: hardcode or import that `response` object; or stub `fetch` to return it when `POST /predict` is called.

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

Until the server exists, skip the network call and use `example.response` directly.

## Errors (planned)

| Status | When | Frontend |
|---|---|---|
| `400` | Missing/unknown feature keys, bad `speed` | Show “bad input”; do not update meters |
| `503` / network fail | Model offline | Show “model offline”; keep last good panel or hide |

## Related

- Feature definitions: [`Aniket/FEATURE_SET.md`](../../Aniket/FEATURE_SET.md)
- Product plan (v1 lookup JSON vs v2 API): [`../docs/project-plan.md`](../docs/project-plan.md)
- Older win/draw/loss sketch in the vault is **not** this contract — use this file instead.
