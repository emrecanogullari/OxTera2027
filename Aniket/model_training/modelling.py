"""The 9 models: what they are, how they are tuned (cross-validation grouped by game), and how they are scored.

Model: gradient-boosted decision trees (sklearn HistGradientBoosting). They handle missing values,
non-linear shapes (e.g. the M-shaped win% curve) and interactions (e.g. clock x position) by themselves.
Cross-validation compares them against a linear model and a smooth additive model (splines, no
interactions) on every task, so the choice is checked, not assumed.

  blunder, blunder_next5   classifier with log loss, no class re-weighting -> calibrated probabilities
  think_time               three quantile models (10/50/90%) on log(1 + seconds + U[0,1)): the median is
                           the prediction, 10-90% the range, widened/narrowed by a conformal correction
                           so the range really covers ~80% of moves
"""
from __future__ import annotations

import time

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.impute import MissingIndicator, SimpleImputer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import QuantileTransformer, SplineTransformer, StandardScaler

from config import CV_FOLDS, FEATURES, MONOTONE, SEED, TARGETS, THINK_QUANTILES

LEARNING_RATE = 0.1
MAX_ITER = 800          # boosting rounds tried; the best number is picked on held-out games
STEP = 10               # score held-out games every 10 rounds
GRID = [{"max_leaf_nodes": leaves, "min_samples_leaf": leaf_rows}
        for leaves in (7, 15, 31, 63) for leaf_rows in (100, 500)]


# --------------------------------------------------------------------------- #
# targets and losses
def think_target(seconds) -> np.ndarray:
    """log(1 + seconds + U[0,1)). Clocks are whole seconds, so think time is discrete with huge ties
    (20% of bullet moves are '0 s'); quantile models on tied data give badly calibrated ranges.
    Spreading each second uniformly fixes that; floor() of the back-transform returns whole seconds."""
    s = np.asarray(seconds, float)
    return np.log1p(s + np.random.default_rng(SEED).uniform(0, 1, len(s)))


def to_seconds(log_pred) -> np.ndarray:
    return np.floor(np.expm1(np.asarray(log_pred, float))).clip(0)


def pinball(y, pred, q: float) -> float:
    d = np.asarray(y) - np.asarray(pred)
    return float(np.mean(np.maximum(q * d, (q - 1) * d)))


def logloss(y, p) -> float:
    p = np.clip(np.asarray(p, float), 1e-7, 1 - 1e-7)
    y = np.asarray(y, float)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def loss_fn(target: str, q: float | None):
    return (lambda y, p: pinball(y, p, q)) if target == "think_time" else logloss


# --------------------------------------------------------------------------- #
# model makers
def make_gbdt(target: str, features: list[str], params: dict, monotone: bool,
              n_iter: int | None = None, quantile: float | None = None):
    cst = [MONOTONE[target].get(f, 0) for f in features] if monotone else None
    common = dict(learning_rate=LEARNING_RATE, max_iter=n_iter or MAX_ITER, l2_regularization=1.0, early_stopping=False,
                  random_state=SEED, monotonic_cst=cst, **params)
    if target == "think_time":
        return HistGradientBoostingRegressor(loss="quantile", quantile=quantile, **common)
    return HistGradientBoostingClassifier(**common)


def make_linear(target: str, features: list[str], splines: bool):
    """Baselines: linear model, or a smooth additive model (one spline curve per feature, no interactions)."""
    num = [SimpleImputer(strategy="median")]
    if splines:  # quantile-transform first so the knots follow the data, robust to ties
        num += [QuantileTransformer(n_quantiles=200, random_state=SEED),
                SplineTransformer(n_knots=6, degree=3, extrapolation="constant")]
    pre = ColumnTransformer([("num", make_pipeline(*num), features),
                             ("missing", MissingIndicator(features="missing-only", error_on_new=False), features)])
    est = Ridge(alpha=1.0) if target == "think_time" else LogisticRegression(max_iter=3000)
    return make_pipeline(pre, StandardScaler(), est)


def predict(model, X: pd.DataFrame, target: str) -> np.ndarray:
    return model.predict(X) if target == "think_time" else model.predict_proba(X)[:, 1]


THINK_HEADS = dict(zip(THINK_QUANTILES, ("low", "median", "high")))


def think_time_predict(heads: dict, widen: float, X: pd.DataFrame) -> pd.DataFrame:
    """Think time from the saved model: three plain scikit-learn quantile models ('low' 10%, 'median' 50%,
    'high' 90%) that predict log(1 + seconds). Sort them per move so they never cross, shift the outer two by
    the conformal correction `widen` (learned on held-out games), convert back to whole seconds.
    That is the whole recipe, so anyone with scikit-learn can use the .joblib file without this code."""
    P = np.column_stack([heads[k].predict(X) for k in ("low", "median", "high")])
    P.sort(axis=1)
    P[:, 0] -= widen
    P[:, 2] += widen
    S = to_seconds(P)
    return pd.DataFrame({"low": S[:, 0], "median": S[:, 1], "high": S[:, 2]}, index=X.index)


# --------------------------------------------------------------------------- #
# cross-validation
def folds_for(groups) -> list[tuple[np.ndarray, np.ndarray]]:
    return list(GroupKFold(CV_FOLDS).split(np.zeros(len(groups)), groups=groups))


def cv_gbdt(target, features, params, monotone, X, y, folds, quantile=None, keep_oof=False):
    """Fit on each training fold, score the held-out games every STEP rounds.
    Returns per-fold loss curves (folds x steps) and, optionally, held-out predictions at every step."""
    lf = loss_fn(target, quantile)
    curves, oof = [], (np.full((len(y), MAX_ITER // STEP), np.nan, dtype=np.float32) if keep_oof else None)
    for tr, va in folds:
        mdl = make_gbdt(target, features, params, monotone, quantile=quantile).fit(X.iloc[tr], y[tr])
        staged = mdl.staged_predict(X.iloc[va]) if target == "think_time" else \
            (p[:, 1] for p in mdl.staged_predict_proba(X.iloc[va]))
        c = []
        for i, p in enumerate(staged):
            if (i + 1) % STEP == 0:
                c.append(lf(y[va], p))
                if keep_oof:
                    oof[va, len(c) - 1] = p
        curves.append(c)
    return np.array(curves), oof


def best_step(curves: np.ndarray) -> int:
    return int(np.argmin(curves.mean(axis=0)))


def cv_linear(target, features, splines, X, y, folds) -> np.ndarray:
    oof = np.full(len(y), np.nan)
    for tr, va in folds:
        p = predict(make_linear(target, features, splines).fit(X.iloc[tr], y[tr]), X.iloc[va], target)
        # a linear fit on log-seconds can extrapolate to absurd values; keep it inside the training range
        oof[va] = np.clip(p, y[tr].min(), y[tr].max()) if target == "think_time" else p
    return oof


def cv_constant(target, y, folds) -> np.ndarray:
    oof = np.full(len(y), np.nan)
    for tr, va in folds:
        oof[va] = np.median(y[tr]) if target == "think_time" else y[tr].mean()
    return oof


# --------------------------------------------------------------------------- #
# scoring
def binary_scores(y, p, base_rate: float) -> dict:
    y, p = np.asarray(y, float), np.asarray(p, float)
    k = max(1, int(round(0.1 * len(p))))
    top = np.argsort(-p, kind="stable")[:k]
    ll, ll0 = logloss(y, p), logloss(y, np.full(len(y), base_rate))
    br, br0 = np.mean((p - y) ** 2), np.mean((base_rate - y) ** 2)
    edges = np.unique(np.quantile(p, np.linspace(0, 1, 11)))
    b = np.clip(np.searchsorted(edges, p, side="right") - 1, 0, len(edges) - 2)
    ece = sum(abs(p[b == i].mean() - y[b == i].mean()) * (b == i).mean() for i in range(len(edges) - 1) if (b == i).any())
    return {
        "n": len(y), "positives": int(y.sum()), "rate": y.mean(), "expected": p.sum(),
        "auc": roc_auc_score(y, p) if 0 < y.mean() < 1 else np.nan,
        "pr_auc": average_precision_score(y, p) if y.sum() else np.nan,
        "log_loss": ll, "log_loss_skill": 1 - ll / ll0, "brier": br, "brier_skill": 1 - br / br0,
        "ece": ece, "top10_precision": y[top].mean(), "top10_recall": y[top].sum() / max(y.sum(), 1),
        "top10_lift": y[top].mean() / max(y.mean(), 1e-9),
        "accuracy_at_50": np.mean((p >= 0.5) == (y == 1)), "accuracy_always_no": 1 - y.mean(),
    }


CUTOFF_RULE = "f1"  # how the saved 1/0 cutoff is chosen; see choose_cutoff
CUTOFF_RULES = {"accuracy": "most moves right overall (0s and 1s together)",
                "f1": "balance of 'flags that are real' and 'events caught'",
                "balanced": "average of 'share of 0s right' and 'share of 1s right'"}


def choose_cutoff(y, p, rule: str = CUTOFF_RULE) -> float:
    """Cutoff for the 1/0 flag ('flag if chance >= cutoff'), always chosen on cross-validation predictions,
    i.e. on training games only. Rules: see CUTOFF_RULES. For rare events 'accuracy' ends up near 50%
    (flag only when a blunder is more likely than not), so it flags very few moves."""
    y, p = np.asarray(y, float), np.asarray(p, float)
    order = np.argsort(-p, kind="stable")
    ys, ps = y[order], p[order]
    tp, fp = np.cumsum(ys), np.cumsum(1 - ys)      # flag the i+1 highest chances
    pos, neg = ys.sum(), len(ys) - ys.sum()
    score, none = {
        "accuracy": ((tp + neg - fp) / len(ys), neg / len(ys)),
        "f1": (2 * tp / (tp + fp + pos), 0.0),
        "balanced": (0.5 * (tp / pos + (neg - fp) / neg), 0.5),
    }[rule]                                         # `none` = score of never flagging
    last_of_tie = np.r_[ps[1:] != ps[:-1], True]    # a cutoff can only sit between distinct chances
    score = np.where(last_of_tie, score, -np.inf)
    i = int(np.argmax(score))
    return float(ps[i]) if score[i] > none else float(np.nextafter(ps[0], 2.0))  # else: above every chance


def flag_scores(y, p, cutoff: float) -> dict:
    """How the 1/0 flag (chance >= cutoff) compares with the real 1/0 labels."""
    y, f = np.asarray(y, float) == 1, np.asarray(p, float) >= cutoff
    tp, fp, fn, tn = int((f & y).sum()), int((f & ~y).sum()), int((~f & y).sum()), int((~f & ~y).sum())
    precision = tp / (tp + fp) if tp + fp else np.nan
    recall = tp / (tp + fn) if tp + fn else np.nan
    specificity = tn / (tn + fp) if tn + fp else np.nan
    return {"cutoff": cutoff, "tp": tp, "fp": fp, "fn": fn, "tn": tn, "flagged": f.mean(),
            "precision": precision, "recall": recall, "specificity": specificity,
            "balanced_accuracy": (recall + specificity) / 2,
            "f1": 2 * tp / (2 * tp + fp + fn) if tp + fp + fn else np.nan,
            "accuracy": (tp + tn) / len(f), "accuracy_always_no": (tn + fp) / len(f)}


def think_scores(seconds, med, low=None, high=None) -> dict:
    t, med = np.asarray(seconds, float), np.asarray(med, float)
    err = med - t
    r = {"n": len(t), "mae_s": np.mean(np.abs(err)), "median_ae_s": np.median(np.abs(err)), "bias_s": err.mean(),
         "within_2x": np.mean(np.abs(np.log2((t + 1) / (med + 1))) <= 1),
         "spearman": pd.Series(med).corr(pd.Series(t), method="spearman")}
    if low is not None:
        low, high = np.asarray(low, float), np.asarray(high, float)
        r["coverage_80"] = np.mean((t >= low) & (t <= high))
        r["width_s"] = np.median(high - low)
    return r


# --------------------------------------------------------------------------- #
# selection + final fit for one (speed, target)
def train_one(speed: str, target: str, moves: pd.DataFrame, log=print) -> dict:
    from oracle.features import FEATURE_COLS

    t0 = time.time()
    col = TARGETS[target]
    features = FEATURES[speed][target]
    d = moves[moves[col].notna()].reset_index(drop=True)
    X, groups = d[FEATURE_COLS], d["game_id"].to_numpy()
    raw = d[col].to_numpy(float)
    y = think_target(raw) if target == "think_time" else raw.astype(int)
    folds = folds_for(groups)
    q50 = 0.5 if target == "think_time" else None
    lf = loss_fn(target, q50)
    tag = f"[{speed}/{target}]"

    # 1) tune tree size on held-out games
    search = []
    for params in GRID:
        curves, _ = cv_gbdt(target, features, params, False, X[features], y, folds, quantile=q50)
        s = best_step(curves)
        search.append({**params, "n_iter": (s + 1) * STEP, "cv_loss": curves.mean(axis=0)[s],
                       "fold_losses": curves[:, s]})
        log(f"{tag} leaves={params['max_leaf_nodes']:<3} min_leaf={params['min_samples_leaf']:<4} "
            f"rounds={(s + 1) * STEP:<4} loss={search[-1]['cv_loss']:.5f}  ({time.time() - t0:.0f}s)")
    best = min(search, key=lambda r: r["cv_loss"])
    params = {"max_leaf_nodes": best["max_leaf_nodes"], "min_samples_leaf": best["min_samples_leaf"]}

    # 2) monotone constraints: keep them unless they are clearly worse (by more than 1 standard error)
    curves_u, oof_u = cv_gbdt(target, features, params, False, X[features], y, folds, quantile=q50, keep_oof=True)
    curves_m, oof_m = cv_gbdt(target, features, params, True, X[features], y, folds, quantile=q50, keep_oof=True)
    su, sm = best_step(curves_u), best_step(curves_m)
    diff = curves_m[:, sm] - curves_u[:, su]
    use_mono = diff.mean() <= diff.std(ddof=1) / np.sqrt(len(diff))
    steps = sm if use_mono else su
    oof_main = (oof_m if use_mono else oof_u)[:, steps].astype(float)
    n_iter = (steps + 1) * STEP
    log(f"{tag} best leaves={params['max_leaf_nodes']} min_leaf={params['min_samples_leaf']}; monotone "
        f"{'kept' if use_mono else 'dropped'} (loss {curves_m[:, sm].mean():.5f} vs {curves_u[:, su].mean():.5f})")

    # 3) comparison: constant, linear, splines (no interactions), trees on ALL 23 features
    compare = {"constant": cv_constant(target, y, folds),
               "linear": cv_linear(target, features, False, X[features], y, folds),
               "splines (additive)": cv_linear(target, features, True, X[features], y, folds)}
    curves_all, oof_all = cv_gbdt(target, FEATURE_COLS, params, False, X[FEATURE_COLS], y, folds,
                                  quantile=q50, keep_oof=True)
    compare["trees, all 23 features"] = oof_all[:, best_step(curves_all)].astype(float)
    compare["trees (chosen)"] = oof_main
    log(f"{tag} baselines done ({time.time() - t0:.0f}s)")

    if target == "think_time":
        # 4) the 10% and 90% heads (own number of rounds), then the conformal correction
        heads_iter, oof_q = {0.5: n_iter}, {0.5: oof_main}
        for q in (0.1, 0.9):
            c, o = cv_gbdt(target, features, params, use_mono, X[features], y, folds, quantile=q, keep_oof=True)
            s = best_step(c)
            heads_iter[q], oof_q[q] = (s + 1) * STEP, o[:, s].astype(float)
        P = np.sort(np.column_stack([oof_q[q] for q in THINK_QUANTILES]), axis=1)
        # Conformal correction on the range users see: floor(expm1(low - w)) <= t <= floor(expm1(high + w))
        # holds for whole seconds t exactly when w >= log1p(t) - high and w > low - log1p(t + 1).
        conformity = np.maximum(np.log1p(raw) - P[:, 2], P[:, 0] - np.log1p(raw + 1))
        n = len(y)
        widen = float(np.quantile(conformity, min(1.0, np.ceil((n + 1) * 0.8) / n)))
        # plain scikit-learn objects keyed low/median/high: the .joblib loads without this code
        model = {THINK_HEADS[q]: make_gbdt(target, features, params, use_mono, heads_iter[q], q).fit(X[features], y)
                 for q in THINK_QUANTILES}
        lo, md, hi = to_seconds(P[:, 0] - widen), to_seconds(P[:, 1]), to_seconds(P[:, 2] + widen)
        cv_table = {name: think_scores(raw, to_seconds(o)) for name, o in compare.items()}
        cv_table["trees (chosen)"] = think_scores(raw, md, lo, hi)
        cv_table["repeat my last think time"] = think_scores(raw, d["prev_self_spent"].fillna(np.median(raw)))
        clock_bins = [0, 5, 15, 30, 60, 120, 300, 600, np.inf]
        cb = pd.cut(d["clock_self"], clock_bins, right=False)
        baselines = {"global_median": float(np.median(raw)), "clock_bins": clock_bins,
                     "clock_bin_median": d.groupby(cb, observed=True)[col].median().to_dict()}
        extra = {"heads_n_iter": heads_iter, "widen": widen, "quantiles": {v: k for k, v in THINK_HEADS.items()}}
    else:
        model = make_gbdt(target, features, params, use_mono, n_iter).fit(X[features], y)
        base = float(y.mean())
        cv_table = {name: binary_scores(y, o, base) for name, o in compare.items()}
        # the constant varies a hair between folds; by definition it cannot rank moves at all
        cv_table["constant"].update(auc=0.5, pr_auc=float(y.mean()), top10_lift=1.0)
        baselines = {"base_rate": base}
        cutoff = choose_cutoff(y, oof_main)
        extra = {"cutoff": cutoff, "cutoff_rule": CUTOFF_RULE, "cv_flags": flag_scores(y, oof_main, cutoff)}
        cf = extra["cv_flags"]
        log(f"{tag} flag cutoff {cutoff:.3f} (max {CUTOFF_RULE}; CV precision {cf['precision']:.3f}, recall "
            f"{cf['recall']:.3f}, F1 {cf['f1']:.3f}, accuracy {cf['accuracy']:.4f})")
    for name in compare:
        cv_table[name]["loss"] = lf(y, compare[name])
    log(f"{tag} done in {time.time() - t0:.0f}s")
    return {
        "speed": speed, "target": target, "label": col, "features": features, "model": model,
        "params": params, "n_iter": n_iter, "monotone": bool(use_mono),
        "monotone_features": {f: MONOTONE[target][f] for f in features if f in MONOTONE[target]} if use_mono else {},
        "train_games": int(d["game_id"].nunique()), "train_rows": len(d), "baselines": baselines,
        "cv": {"search": [{k: v for k, v in r.items() if k != "fold_losses"} for r in search],
               "table": cv_table, "monotone_loss_diff": float(diff.mean()),
               "oof": oof_main if target != "think_time" else np.column_stack([lo, md, hi]),
               "oof_y": raw},
        **extra,
    }


def load_bundle(path):
    import joblib
    return joblib.load(path)


def cutoff_for(bundle: dict, rule: str | None = None) -> float:
    """The saved cutoff, or the cutoff another rule would pick, recomputed from the bundle's own
    cross-validation predictions (training games), so switching rules needs no retraining."""
    if rule is None or rule == bundle.get("cutoff_rule"):
        return bundle["cutoff"]
    return choose_cutoff(bundle["cv"]["oof_y"], bundle["cv"]["oof"], rule)


def predict_moves(bundles: dict, moves: pd.DataFrame, rule: str | None = None) -> pd.DataFrame:
    """The three numbers for every move: think-time range, P(blunder), P(blunder in next 5),
    plus the 1/0 flags (chance >= cutoff; saved rule 'accuracy' unless another rule is given)."""
    out = pd.DataFrame(index=moves.index)
    tt = bundles["think_time"]
    out[["think_low", "think_median", "think_high"]] = \
        think_time_predict(tt["model"], tt["widen"], moves[tt["features"]]).to_numpy()
    for t in ("blunder", "blunder_next5"):
        b = bundles[t]
        out[f"p_{t}"] = b["model"].predict_proba(moves[b["features"]])[:, 1]
        out[f"flag_{t}"] = (out[f"p_{t}"] >= cutoff_for(b, rule)).astype(int)
    return out
