"""Random-predict MVP: validated request in, random contract-shaped response out."""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

Speed = Literal["bullet", "blitz", "classical"]

_CONTRACT = json.loads((Path(__file__).with_name("dummy_predict.json")).read_text(encoding="utf-8"))
FEATURE_KEYS_BY_SPEED: dict[str, list[str]] = {
    speed: list(keys) for speed, keys in _CONTRACT["feature_keys_by_speed"].items()
}

# (low, high) seconds for random think-time draws; order will be enforced as p50 <= point <= p75
_TIME_RANGES: dict[Speed, tuple[float, float]] = {
    "bullet": (0.5, 4.0),
    "blitz": (1.0, 12.0),
    "classical": (5.0, 60.0),
}

app = FastAPI(title="OxTera predict (random MVP)", version="random-mvp-v0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class PredictRequest(BaseModel):
    speed: Speed
    game_id: str | None = None
    features: dict[str, float | int]


class Predictions(BaseModel):
    time_spent_s: float
    time_spent_p50_s: float
    time_spent_p75_s: float
    p_blunder: float = Field(ge=0.0, le=1.0)


class ModelInfo(BaseModel):
    version: str
    targets: list[str]


class PredictResponse(BaseModel):
    speed: Speed
    game_id: str | None = None
    predictions: Predictions
    model: ModelInfo


def _validate_features(speed: Speed, features: dict[str, Any]) -> None:
    expected = set(FEATURE_KEYS_BY_SPEED[speed])
    got = set(features)
    missing = sorted(expected - got)
    extra = sorted(got - expected)
    if missing or extra:
        parts: list[str] = []
        if missing:
            parts.append(f"missing: {missing}")
        if extra:
            parts.append(f"unknown: {extra}")
        raise HTTPException(status_code=400, detail=f"features for {speed}: " + "; ".join(parts))


def _random_predictions(speed: Speed) -> Predictions:
    lo, hi = _TIME_RANGES[speed]
    a, b, c = sorted(random.uniform(lo, hi) for _ in range(3))
    return Predictions(
        time_spent_p50_s=round(a, 2),
        time_spent_s=round(b, 2),
        time_spent_p75_s=round(c, 2),
        p_blunder=round(random.uniform(0.0, 1.0), 3),
    )


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.post("/predict", response_model=PredictResponse)
def predict(body: PredictRequest) -> PredictResponse:
    _validate_features(body.speed, body.features)
    return PredictResponse(
        speed=body.speed,
        game_id=body.game_id,
        predictions=_random_predictions(body.speed),
        model=ModelInfo(version="random-mvp-v0", targets=["time_spent", "blunder"]),
    )
