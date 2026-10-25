"""Predict API: feature vectors or live RawGameState in → oracle predictions out."""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from live_features import (
    EngineUnavailableError,
    LiveFeatureError,
    build_features,
    shutdown_engine,
    warm_engine,
)
from oracle_runner import predict as oracle_predict
from oracle_runner import preload as preload_oracle

logger = logging.getLogger("oxtera.predict")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

Speed = Literal["bullet", "blitz", "classical"]

_CONTRACT = json.loads((Path(__file__).with_name("dummy_predict.json")).read_text(encoding="utf-8"))
FEATURE_KEYS_BY_SPEED: dict[str, list[str]] = {
    speed: list(keys) for speed, keys in _CONTRACT["feature_keys_by_speed"].items()
}

MODEL_VERSION = "oracle-cpp-v1"

app = FastAPI(title="OxTera predict", version=MODEL_VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class PredictRequest(BaseModel):
    speed: Speed
    game_id: str | None = None
    features: dict[str, Any]

    @field_validator("speed", mode="before")
    @classmethod
    def _normalize_speed(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip().lower()
        return value


class LivePredictRequest(BaseModel):
    """Raw board/clock scrape from a site adapter (chess.com / Lichess)."""

    site: Literal["chesscom", "lichess"] = "chesscom"
    game_id: str | None = None
    color: Literal["white", "black"]
    base_s: float
    inc_s: float
    elo_self: float
    elo_opp: float | None = None
    clock_self_s: float
    clock_opp_s: float
    fen: str | None = None
    # Piece picture from the page, the ranks only, used to check the move list.
    placement: str | None = None
    side_to_move: Literal["white", "black"] | None = None
    moves_uci: list[str] = Field(default_factory=list)
    # SAN of the moves already played, read from the on-screen move list.
    moves_san: list[str] = Field(default_factory=list)
    # Remaining clock printed on each move, when the page has one.
    move_clocks: list[float | None] | None = None
    ply: int | None = None
    # Optional spend / tilt overrides from extension clock_history
    prev_self_spent: float | None = None
    avg_self_spent: float | None = None
    prev_opp_spent: float | None = None
    prior_blunders_self: float | None = None
    # When true, response includes raw input + derived feature vector (for HUD console).
    debug: bool = True


class Predictions(BaseModel):
    time_spent_s: float
    time_spent_p50_s: float
    time_spent_p75_s: float
    p_blunder: float = Field(ge=0.0, le=1.0)


class ModelInfo(BaseModel):
    version: str
    targets: list[str]


class LiveDebugInfo(BaseModel):
    engine_used: bool
    speed: Speed
    raw: dict[str, Any]
    features: dict[str, Any]
    note: str | None = None


class PredictResponse(BaseModel):
    speed: Speed
    game_id: str | None = None
    predictions: Predictions
    model: ModelInfo
    debug: LiveDebugInfo | None = None


def _jsonable_features(features: dict[str, float]) -> dict[str, Any]:
    """NaN → null so the browser console shows missing engine fields clearly."""
    out: dict[str, Any] = {}
    for k, v in features.items():
        if isinstance(v, float) and math.isnan(v):
            out[k] = None
        else:
            out[k] = v
    return out


def _coerce_number(key: str, value: Any) -> float:
    if value is None or value == "":
        return math.nan
    if isinstance(value, bool):
        raise HTTPException(status_code=400, detail=f"features.{key} must be a number, got boolean")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if text.lower() in {"", "nan", "na", "null", "none"}:
            return math.nan
        try:
            return float(text)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=f"features.{key} must be a number, got {value!r}",
            ) from exc
    raise HTTPException(status_code=400, detail=f"features.{key} must be a number, got {type(value).__name__}")


def _prepare_features(speed: Speed, features: dict[str, Any]) -> dict[str, float]:
    expected = FEATURE_KEYS_BY_SPEED[speed]
    expected_set = set(expected)
    got = set(features)
    missing = sorted(expected_set - got)
    extra = sorted(got - expected_set)
    if missing or extra:
        parts: list[str] = []
        if missing:
            parts.append(f"missing: {missing}")
        if extra:
            parts.append(f"unknown: {extra}")
        parts.append(f"expected {len(expected)} keys for {speed}: {expected}")
        raise HTTPException(status_code=400, detail=f"features for {speed}: " + "; ".join(parts))
    return {key: _coerce_number(key, features[key]) for key in expected}


def _run_oracle(
    speed: Speed,
    game_id: str | None,
    prepared: dict[str, float],
    *,
    version_suffix: str = "",
    debug: LiveDebugInfo | None = None,
) -> PredictResponse:
    keys = FEATURE_KEYS_BY_SPEED[speed]
    try:
        out = oracle_predict(speed, keys, prepared)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"model offline: {exc}") from exc
    return PredictResponse(
        speed=speed,
        game_id=game_id,
        predictions=Predictions(
            time_spent_s=out.think_median,
            time_spent_p50_s=out.think_median,
            time_spent_p75_s=out.think_high,
            p_blunder=round(out.p_blunder, 6),
        ),
        model=ModelInfo(version=MODEL_VERSION + version_suffix, targets=["time_spent", "blunder"]),
        debug=debug,
    )


@app.on_event("startup")
def _startup() -> None:
    preload_oracle()
    warm_engine()


@app.on_event("shutdown")
def _shutdown() -> None:
    shutdown_engine()


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.get("/predict/schema")
def predict_schema() -> dict[str, Any]:
    return {
        "endpoint": "POST /predict",
        "live_endpoint": "POST /predict/live",
        "speeds": list(FEATURE_KEYS_BY_SPEED),
        "feature_keys_by_speed": FEATURE_KEYS_BY_SPEED,
        "example": {
            "speed": "blitz",
            "game_id": "optional-id",
            "features": {k: 0.0 for k in FEATURE_KEYS_BY_SPEED["blitz"]},
        },
        "live_example": {
            "site": "chesscom",
            "game_id": "optional-id",
            "color": "white",
            "base_s": 180,
            "inc_s": 2,
            "elo_self": 1510,
            "clock_self_s": 142.0,
            "clock_opp_s": 155.0,
            "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            "moves_uci": [],
            "ply": 1,
        },
    }


@app.post("/predict", response_model=PredictResponse)
def predict(body: PredictRequest) -> PredictResponse:
    prepared = _prepare_features(body.speed, body.features)
    return _run_oracle(body.speed, body.game_id, prepared)


@app.post("/predict/live", response_model=PredictResponse)
def predict_live(body: LivePredictRequest) -> PredictResponse:
    raw = body.model_dump()
    debug_flag = bool(raw.pop("debug", True))
    logger.info(
        "predict/live raw site=%s game_id=%s color=%s ply=%s clocks=%s/%s tc=%s+%s fen=%s moves=%d",
        raw.get("site"),
        raw.get("game_id"),
        raw.get("color"),
        raw.get("ply"),
        raw.get("clock_self_s"),
        raw.get("clock_opp_s"),
        raw.get("base_s"),
        raw.get("inc_s"),
        (raw.get("fen") or "")[:40],
        len(raw.get("moves_uci") or []),
    )
    try:
        speed, features, engine_used = build_features(raw)
    except LiveFeatureError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except EngineUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"live feature build failed: {exc}") from exc

    feats_json = _jsonable_features(features)
    logger.info(
        "predict/live features speed=%s engine=%s %s",
        speed,
        engine_used,
        json.dumps(feats_json, default=str),
    )

    note = None
    if not engine_used:
        note = (
            "Stockfish not running — wp_self/abs_cp/last_swing/prior_blunders_self are null. "
            "Blunder model often collapses to a low baseline (~1–3%). "
            "Set STOCKFISH_PATH or install stockfish on PATH."
        )
    debug_info = None
    if debug_flag:
        debug_info = LiveDebugInfo(
            engine_used=engine_used,
            speed=speed,  # type: ignore[arg-type]
            raw={k: v for k, v in raw.items() if k != "debug"},
            features=feats_json,
            note=note,
        )

    suffix = "+engine" if engine_used else "+no-engine"
    return _run_oracle(
        speed,  # type: ignore[arg-type]
        body.game_id,
        features,
        version_suffix=suffix,
        debug=debug_info,
    )
