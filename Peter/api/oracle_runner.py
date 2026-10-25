"""Run Aniket's C++ oracle_predict (or an equivalent in-process loader).

Packs the /predict feature dict into the headered CSV the CLI expects, then maps
think_low/median/high + p_blunder back into the extension contract.
"""

from __future__ import annotations

import csv
import io
import math
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

ORACLE_DIR = Path(__file__).resolve().parents[2] / "Aniket" / "model_training" / "cpp"
MODEL_PATHS = {
    "bullet": ORACLE_DIR / "models" / "bullet.txt",
    "blitz": ORACLE_DIR / "models" / "blitz.txt",
    "classical": ORACLE_DIR / "models" / "classical.txt",
}

OUTPUT_FIELDS = (
    "think_low",
    "think_median",
    "think_high",
    "p_blunder",
    "flag_blunder",
    "p_blunder_next5",
    "flag_blunder_next5",
)


@dataclass(frozen=True)
class OraclePrediction:
    think_low: float
    think_median: float
    think_high: float
    p_blunder: float
    flag_blunder: int
    p_blunder_next5: float
    flag_blunder_next5: int


def features_to_csv(feature_keys: list[str], features: dict[str, float | int]) -> str:
    """One-move CSV with a header row; column order matches FEATURE_SET / SUPERSETS."""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(feature_keys)
    row: list[str] = []
    for key in feature_keys:
        value = features[key]
        if value is None or (isinstance(value, float) and math.isnan(value)):
            row.append("nan")
        else:
            row.append(str(float(value)))
    writer.writerow(row)
    return buf.getvalue()


def _binary_runs_here(path: Path) -> bool:
    """Skip checked-in binaries built for another OS (e.g. macOS Mach-O on Windows)."""
    try:
        magic = path.read_bytes()[:4]
    except OSError:
        return False
    if os.name == "nt":
        return magic.startswith(b"MZ")  # PE
    # ELF or Mach-O (incl. fat/universal)
    return magic in {b"\x7fELF", b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xce", b"\xca\xfe\xba\xbe"}


def _oracle_binary() -> Path | None:
    for name in ("oracle_predict.exe", "oracle_predict"):
        path = ORACLE_DIR / name
        if path.is_file() and _binary_runs_here(path):
            return path
    return None


def _parse_prediction_csv(stdout: str) -> OraclePrediction:
    reader = csv.DictReader(io.StringIO(stdout.strip()))
    rows = list(reader)
    if len(rows) != 1:
        raise RuntimeError(f"oracle_predict returned {len(rows)} rows, expected 1")
    row = rows[0]
    missing = [k for k in OUTPUT_FIELDS if k not in row]
    if missing:
        raise RuntimeError(f"oracle_predict missing columns: {missing}")
    return OraclePrediction(
        think_low=float(row["think_low"]),
        think_median=float(row["think_median"]),
        think_high=float(row["think_high"]),
        p_blunder=float(row["p_blunder"]),
        flag_blunder=int(float(row["flag_blunder"])),
        p_blunder_next5=float(row["p_blunder_next5"]),
        flag_blunder_next5=int(float(row["flag_blunder_next5"])),
    )


def _run_cli(speed: str, csv_text: str) -> OraclePrediction:
    binary = _oracle_binary()
    if binary is None:
        raise FileNotFoundError("oracle_predict binary not found")
    model = MODEL_PATHS[speed]
    if not model.is_file():
        raise FileNotFoundError(f"model file missing: {model}")
    proc = subprocess.run(
        [str(binary), str(model)],
        input=csv_text,
        capture_output=True,
        text=True,
        cwd=str(ORACLE_DIR),
        timeout=10,
        check=False,
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}"
        raise RuntimeError(f"oracle_predict failed: {err}")
    return _parse_prediction_csv(proc.stdout)


# ---------------------------------------------------------------------------
# In-process fallback (same .txt format as oracle_model.hpp) for hosts where
# the checked-in binary is the wrong OS (e.g. macOS Mach-O on Windows).
# ---------------------------------------------------------------------------


class _Booster:
    __slots__ = ("baseline", "roots", "nodes")

    def __init__(self) -> None:
        self.baseline = 0.0
        self.roots: list[int] = []
        # each node: (feature, t, left, right, missing_left); feature < 0 => leaf, t = leaf value
        self.nodes: list[tuple[int, float, int, int, bool]] = []

    def score(self, x: list[float]) -> float:
        s = self.baseline
        for root in self.roots:
            i = root
            while True:
                feature, t, left, right, missing_left = self.nodes[i]
                if feature < 0:
                    s += t
                    break
                v = x[feature]
                go_left = missing_left if math.isnan(v) else (v <= t)
                i = left if go_left else right
        return s


class _Model:
    def __init__(self, path: Path) -> None:
        tokens = path.read_text(encoding="utf-8").split()
        it = iter(tokens)

        def take() -> str:
            try:
                return next(it)
            except StopIteration as exc:
                raise RuntimeError(f"{path}: truncated model file") from exc

        def take_float() -> float:
            return float(take())

        if take() != "oracle-model" or int(take()) != 1:
            raise RuntimeError(f"{path}: not an oracle-model v1 file")
        if take() != "speed":
            raise RuntimeError(f"{path}: bad header")
        self.speed = take()
        if take() != "features":
            raise RuntimeError(f"{path}: bad header")
        n = int(take())
        self.features = [take() for _ in range(n)]
        self.think = [_Booster(), _Booster(), _Booster()]
        self.blunder = _Booster()
        self.next5 = _Booster()
        self.widen = math.nan
        self.cut_blunder = math.nan
        self.cut_next5 = math.nan
        seen = 0
        while True:
            tag = take()
            if tag == "end":
                break
            if tag == "booster":
                name, _kind = take(), take()
                self._booster(name).baseline = take_float()
                n_trees = int(take())
                for _ in range(n_trees):
                    if take() != "tree":
                        raise RuntimeError(f"{path}: bad tree header")
                    n_nodes = int(take())
                    offset = len(self._booster(name).nodes)
                    self._booster(name).roots.append(offset)
                    for i in range(n_nodes):
                        feature = int(take())
                        if feature < 0:
                            leaf = take_float()
                            self._booster(name).nodes.append((-1, leaf, 0, 0, False))
                        else:
                            threshold = take_float()
                            missing_left = int(take()) != 0
                            left = int(take())
                            right = int(take())
                            self._booster(name).nodes.append(
                                (feature, threshold, offset + left, offset + right, missing_left)
                            )
                seen += 1
            elif tag == "widen":
                self.widen = take_float()
            elif tag == "cutoff":
                name = take()
                cutoff = take_float()
                if name == "blunder":
                    self.cut_blunder = cutoff
                elif name == "blunder_next5":
                    self.cut_next5 = cutoff
                else:
                    raise RuntimeError(f"{path}: unknown cutoff '{name}'")
            else:
                raise RuntimeError(f"{path}: unexpected '{tag}'")
        if seen != 5 or math.isnan(self.widen) or math.isnan(self.cut_blunder) or math.isnan(self.cut_next5):
            raise RuntimeError(f"{path}: incomplete model file")

    def _booster(self, name: str) -> _Booster:
        return {
            "think_low": self.think[0],
            "think_median": self.think[1],
            "think_high": self.think[2],
            "blunder": self.blunder,
            "blunder_next5": self.next5,
        }[name]

    def predict(self, x: list[float]) -> OraclePrediction:
        if len(x) != len(self.features):
            raise ValueError(f"{self.speed} model expects {len(self.features)} features, got {len(x)}")
        q = [self.think[0].score(x), self.think[1].score(x), self.think[2].score(x)]
        q.sort()
        q[0] -= self.widen
        q[2] += self.widen

        def seconds(log1p_s: float) -> float:
            return max(0.0, math.floor(math.expm1(log1p_s)))

        def sigmoid(z: float) -> float:
            return 1.0 / (1.0 + math.exp(-z))

        p_blunder = sigmoid(self.blunder.score(x))
        p_next5 = sigmoid(self.next5.score(x))
        return OraclePrediction(
            think_low=seconds(q[0]),
            think_median=seconds(q[1]),
            think_high=seconds(q[2]),
            p_blunder=p_blunder,
            flag_blunder=int(p_blunder >= self.cut_blunder),
            p_blunder_next5=p_next5,
            flag_blunder_next5=int(p_next5 >= self.cut_next5),
        )


_MODEL_CACHE: dict[str, _Model] = {}


def _run_inprocess(speed: str, feature_keys: list[str], features: dict[str, float | int]) -> OraclePrediction:
    model_path = MODEL_PATHS[speed]
    if not model_path.is_file():
        raise FileNotFoundError(f"model file missing: {model_path}")
    model = _MODEL_CACHE.get(speed)
    if model is None:
        model = _Model(model_path)
        _MODEL_CACHE[speed] = model
    if model.features != feature_keys:
        # Prefer the model's declared order; feature_keys from the API contract should match.
        keys = model.features
    else:
        keys = feature_keys
    x: list[float] = []
    for key in keys:
        value = features[key]
        if value is None or (isinstance(value, float) and math.isnan(value)):
            x.append(math.nan)
        else:
            x.append(float(value))
    return model.predict(x)


def predict(speed: str, feature_keys: list[str], features: dict[str, float | int]) -> OraclePrediction:
    """Prefer the C++ CLI; fall back to the in-process loader if it cannot run."""
    csv_text = features_to_csv(feature_keys, features)
    force_py = os.environ.get("OXTERA_ORACLE_PYTHON", "").strip() in {"1", "true", "yes"}
    if not force_py:
        try:
            return _run_cli(speed, csv_text)
        except (FileNotFoundError, OSError, subprocess.SubprocessError, RuntimeError):
            pass
    return _run_inprocess(speed, feature_keys, features)
