"""
Frontend integration sketch + smoke test for POST /predict.

What this file shows
--------------------
1. The exact JSON shape you must SEND to the API.
2. The exact JSON shape you will RECEIVE back.
3. Where to plug in your extension / UI code (look for "TEAMMATE:").

Run (server must already be up):
  cd Peter/api
  python test_client.py

From another device on the LAN, set BASE_URL to this machine's IP, e.g.:
  BASE_URL = "http://10.21.244.181:8000"
"""

from __future__ import annotations

import json
import sys
from typing import Any

import httpx

# ---------------------------------------------------------------------------
# Server address
# ---------------------------------------------------------------------------
# Same machine as the API:          http://127.0.0.1:8000
# Extension / teammate on LAN:      http://<host-LAN-IP>:8000
BASE_URL = "http://127.0.0.1:8000"


# ---------------------------------------------------------------------------
# 1) REQUEST — what you send
# ---------------------------------------------------------------------------
# POST {BASE_URL}/predict
# Content-Type: application/json
#
# Top-level fields:
#   speed    — "bullet" | "blitz" | "classical"  (picks feature key set)
#   game_id  — optional string for your own logging / UI correlation
#   features — object with EXACTLY the keys for that speed (see FEATURE_SET.md)
#
# Feature units: clocks / think times in seconds; wp_self in 0–100;
# elo_self and ply are integers. Do NOT send labels (time_spent, blunder).
#
# Required feature keys by speed (all must be present, no extras):
#   bullet (18):     clock_self, clock_opp, clock_ratio, base, inc,
#                    prev_self_spent, avg_self_spent, prev_opp_spent,
#                    elo_self, ply, mat_total, mat_diff, n_legal, n_captures,
#                    wp_self, abs_cp, last_swing, prior_blunders_self
#   blitz (17):      same as bullet but WITHOUT base
#   classical (16):  clock_self, clock_ratio, frac_self,
#                    prev_self_spent, avg_self_spent, prev_opp_spent,
#                    elo_self, ply, mat_total, mat_diff, n_legal, n_captures,
#                    wp_self, abs_cp, last_swing, prior_blunders_self

def build_predict_request() -> dict[str, Any]:
    """
    Build the JSON body for POST /predict.

    TEAMMATE: replace this hardcoded example with values read from the
    Lichess page (clocks, ply, rating, board features, etc.).
    Keep the same key names and nesting.
    """
    return {
        "speed": "blitz",
        "game_id": "dummy-blitz-001",  # optional; use null / omit if unused
        "features": {
            "clock_self": 142.0,
            "clock_opp": 155.0,
            "clock_ratio": 0.916,
            "inc": 0,
            "prev_self_spent": 3.0,
            "avg_self_spent": 4.5,
            "prev_opp_spent": 2.0,
            "elo_self": 1510,
            "ply": 28,
            "mat_total": 62,
            "mat_diff": 0,
            "n_legal": 34,
            "n_captures": 5,
            "wp_self": 48.2,
            "abs_cp": 12,
            "last_swing": 8.5,
            "prior_blunders_self": 1,
        },
    }


# ---------------------------------------------------------------------------
# 2) RESPONSE — what you get back (200 OK)
# ---------------------------------------------------------------------------
# {
#   "speed": "blitz",
#   "game_id": "dummy-blitz-001",          # echoed if you sent one
#   "predictions": {
#     "time_spent_s": 5.4,                 # point estimate think time (seconds)
#     "time_spent_p50_s": 4.0,             # typical / median (seconds)
#     "time_spent_p75_s": 7.0,             # nudge budget: warn if elapsed > this
#     "p_blunder": 0.12                    # blunder chance in [0, 1]
#   },
#   "model": {
#     "version": "oracle-cpp-v1",
#     "targets": ["time_spent", "blunder"]
#   }
# }
#
# Errors:
#   400 — bad speed or wrong feature keys → do not update the UI meters
#   network / connection fail → show "model offline"


def call_predict(request_body: dict[str, Any]) -> dict[str, Any]:
    """
    POST the request body to /predict and return the parsed JSON response.

    TEAMMATE: in the extension this is the same shape as:
      fetch(`${BASE_URL}/predict`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestBody),
      }).then(r => r.json())
    """
    res = httpx.post(f"{BASE_URL}/predict", json=request_body, timeout=5.0)
    if res.status_code == 400:
        raise ValueError(f"bad request (check speed / feature keys): {res.text}")
    res.raise_for_status()
    return res.json()


def apply_to_ui(response: dict[str, Any]) -> None:
    """
    Consume the /predict response.

    TEAMMATE: replace the prints below with your panel / overlay updates.
    Pull numbers only from response["predictions"].
    """
    preds = response["predictions"]

    # --- fields you will use in the UI ---
    think_point_s = preds["time_spent_s"]       # show as "typical think"
    think_p50_s = preds["time_spent_p50_s"]     # softer / median display
    think_budget_s = preds["time_spent_p75_s"]  # nudge when elapsed > this
    p_blunder = preds["p_blunder"]              # blunder meter, 0.0–1.0

    # TEAMMATE: your code goes here, e.g.
    #   updateThinkMeter(think_point_s, think_budget_s)
    #   updateBlunderMeter(p_blunder)
    #   if elapsed_s > think_budget_s: showNudge()
    print("=== fields for the UI ===")
    print(f"  typical think (s):  {think_point_s}")
    print(f"  median think (s):   {think_p50_s}")
    print(f"  nudge budget (s):   {think_budget_s}")
    print(f"  blunder chance:     {p_blunder}  (0–1)")
    print(f"  model version:      {response['model']['version']}")


# ---------------------------------------------------------------------------
# Smoke test — proves the server accepts the format above
# ---------------------------------------------------------------------------

def main() -> int:
    request_body = build_predict_request()

    print("=== request you send (POST /predict) ===")
    print(json.dumps(request_body, indent=2))
    print()

    try:
        health = httpx.get(f"{BASE_URL}/health", timeout=5.0)
        health.raise_for_status()
        print(f"GET /health -> {health.status_code} {health.json()}")

        response = call_predict(request_body)
    except httpx.ConnectError:
        print(
            f"Could not connect to {BASE_URL}. Start the server first:\n"
            "  uvicorn app:app --host 0.0.0.0 --port 8000",
            file=sys.stderr,
        )
        return 1
    except (httpx.HTTPError, ValueError) as exc:
        print(f"predict failed: {exc}", file=sys.stderr)
        return 1

    print()
    print("=== raw response JSON ===")
    print(json.dumps(response, indent=2))
    print()

    apply_to_ui(response)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
