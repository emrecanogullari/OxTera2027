"""Step 3: score the 9 models on the fresh test games -> reports/RESULTS.md + reports/<speed>/*.png

  python 3_evaluate.py

For each speed: predict the three numbers for every test move, compare with the real labels, and
score against simple baselines. 95% intervals come from resampling whole test games (1,000 times).
Per-move predictions are saved to test_data/<speed>/predictions.parquet.
"""
import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import roc_curve

from config import MODELS, REPORTS, SPEEDS, TARGETS, TEST_DATA, TRAIN_DATA
from modelling import CUTOFF_RULES, binary_scores, choose_cutoff, flag_scores, predict_moves, think_scores
from oracle.config import COLORS, GRID, INK, INK_2, RED
from oracle.eda import _save, style, wilson

N_BOOT = 1000
RNG = np.random.default_rng(0)
NAMES = {"think_time": "think time", "blunder": "blunder", "blunder_next5": "blunder in next 5"}
# flag vs actual: quiet (no flag, no event), false alarm, missed, caught
OUTCOME_COLORS = {"quiet": "#e8e7e3", "false alarm": "#f2a541", "missed": "#e34948", "caught": "#1baf7a"}
RULE_TEXT = {"accuracy": "max accuracy", "f1": "best F1", "balanced": "max balanced accuracy"}


# --------------------------------------------------------------------------- #
def bootstrap(groups: np.ndarray, fn, keys: tuple, n: int = N_BOOT) -> dict:
    """95% intervals of fn(row_index)[key] when whole games are resampled with replacement."""
    rows = [np.flatnonzero(groups == g) for g in pd.unique(groups)]
    vals = {k: [] for k in keys}
    for _ in range(n):
        r = fn(np.concatenate([rows[i] for i in RNG.integers(0, len(rows), len(rows))]))
        for k in keys:
            vals[k].append(r[k])
    return {f"{k}_ci": tuple(np.nanpercentile(v, [2.5, 97.5])) for k, v in vals.items()}


def eval_binary(b: dict, d: pd.DataFrame, p: np.ndarray) -> dict:
    y = d[b["label"]].to_numpy(float)
    base = b["baselines"]["base_rate"]
    s = binary_scores(y, p, base)
    s.update(bootstrap(d["game_id"].to_numpy(), lambda i: binary_scores(y[i], p[i], base),
                       ("auc", "pr_auc", "brier_skill", "log_loss_skill", "top10_precision", "top10_recall")))
    s["baseline"] = binary_scores(y, np.full(len(y), base), base)
    s["cv"] = b["cv"]["table"]["trees (chosen)"]
    # the 1/0 flag at the cutoff chosen on training games, plus what the other cutoff rules would have given
    c = b["cutoff"]
    s["flags"] = flag_scores(y, p, c)
    s["flags"].update(bootstrap(d["game_id"].to_numpy(), lambda i: flag_scores(y[i], p[i], c),
                                ("precision", "recall", "f1", "accuracy")))
    s["flags"]["rule"] = b["cutoff_rule"]
    s["cv_flags"] = b["cv_flags"]
    yo, po = oof_labels(b), b["cv"]["oof"]
    s["cutoff_options"] = {rule: flag_scores(y, p, choose_cutoff(yo, po, rule)) for rule in CUTOFF_RULES}
    # per player-game: predicted number of events (sum of chances) vs the real number
    pg = pd.DataFrame({"g": d["game_id"].to_numpy(), "c": d["color"].to_numpy(), "p": p, "y": y}) \
        .groupby(["g", "c"]).agg(pred=("p", "sum"), real=("y", "sum"))
    s["per_game"] = {"n": len(pg), "corr": pg["pred"].corr(pg["real"]), "mae": (pg["pred"] - pg["real"]).abs().mean(),
                     "mean_real": pg["real"].mean()}
    return s


def lookup_median(train: pd.DataFrame, test: pd.DataFrame, col: str, label: str) -> np.ndarray:
    """Training median of the label within deciles of `col` (edges from the training games)."""
    edges = np.unique(np.nanquantile(train[col], np.linspace(0, 1, 11)))
    edges[0], edges[-1] = -np.inf, np.inf
    med = train.groupby(pd.cut(train[col], edges), observed=True)[label].median()
    return pd.cut(test[col], edges).map(med).astype(float).fillna(train[label].median()).to_numpy()


def eval_think(b: dict, d: pd.DataFrame, pred: pd.DataFrame) -> dict:
    t = d[b["label"]].to_numpy(float)
    lo, md, hi = (pred[c].to_numpy(float) for c in ("think_low", "think_median", "think_high"))
    s = think_scores(t, md, lo, hi)
    s.update(bootstrap(d["game_id"].to_numpy(), lambda i: think_scores(t[i], md[i], lo[i], hi[i]),
                       ("mae_s", "within_2x", "coverage_80", "spearman")))
    tr = pd.read_parquet(TRAIN_DATA / b["speed"] / "moves.parquet")
    tr = tr[tr[b["label"]].notna()]
    gm = float(tr[b["label"]].median())
    rules = {  # simple rules, all learned from the training games of this speed
        "always the typical time": np.full(len(t), gm),
        "typical time at this clock": lookup_median(tr, d, "clock_self", b["label"]),
        "typical time at this move number": lookup_median(tr, d, "ply", b["label"]),
        "my average so far this game": np.floor(d["avg_self_spent"].fillna(gm)).to_numpy(),
        "repeat my last think time": d["prev_self_spent"].fillna(gm).to_numpy(),
    }
    s["baselines"] = {k: think_scores(t, v) for k, v in rules.items()}
    # paired comparison with the best rule (picked on the test games, which favours the rule)
    best = min(rules, key=lambda k: s["baselines"][k]["mae_s"])
    bp = rules[best]

    def paired(i):
        a, c = think_scores(t[i], md[i]), think_scores(t[i], bp[i])
        return {"d_mae": a["mae_s"] - c["mae_s"], "d_w2": a["within_2x"] - c["within_2x"]}

    s["vs_best"] = {"rule": best, "d_mae": s["mae_s"] - s["baselines"][best]["mae_s"],
                    "d_w2": s["within_2x"] - s["baselines"][best]["within_2x"],
                    **bootstrap(d["game_id"].to_numpy(), paired, ("d_mae", "d_w2"))}
    s["cv"] = b["cv"]["table"]["trees (chosen)"]
    return s


# --------------------------------------------------------------------------- #
# figures
def oof_labels(b: dict) -> np.ndarray:
    """Labels behind the stored cross-validation predictions (same rows, same order as training)."""
    if "oof_y" in b["cv"]:
        return b["cv"]["oof_y"]
    return pd.read_parquet(TRAIN_DATA / b["speed"] / "moves.parquet", columns=[b["label"]]).dropna()[b["label"]].to_numpy()


def plot_flags(name: str, b: dict, d: pd.DataFrame, p: np.ndarray, s: dict, out) -> None:
    """The 1/0 flag vs the real 1/0 label: how the cutoff was chosen, the confusion matrix on the test
    games, and every test game move by move."""
    y = d[b["label"]].to_numpy(int)
    c, f = b["cutoff"], s["flags"]
    fig = plt.figure(figsize=(15, 10))
    gs = fig.add_gridspec(2, 2, height_ratios=[1, 1.35], width_ratios=[1.35, 1])

    ax = fig.add_subplot(gs[0, 0])
    acc_ax = ax.twinx()
    grid = np.linspace(0.005, 0.8, 160)
    po, yo = b["cv"]["oof"], oof_labels(b)
    curves = {"precision": ("flags that were real (precision)", "#2a78d6"),
              "recall": ("1s caught (recall)", RED), "f1": ("F1 (balance of both)", INK)}
    for pp, yy, ls in ((po, yo, "-"), (p, y, "--")):  # training (cross-validation), test
        sc = [flag_scores(yy, pp, g) for g in grid]
        for r in sc:  # precision of a handful of flags is just noise: hide it below 30 flagged moves
            if r["tp"] + r["fp"] < 30:
                r["precision"] = np.nan
        for k, (lab, col) in curves.items():
            ax.plot(100 * grid, [r[k] for r in sc], ls=ls, color=col, lw=1.8 if ls == "-" else 1.2,
                    label=lab if ls == "-" else None)
        acc_ax.plot(100 * grid, [100 * r["accuracy"] for r in sc], ls=ls, color="#8a8984", lw=1.4 if ls == "-" else 1,
                    label="accuracy: all moves right (right axis)" if ls == "-" else None)
    always0 = 100 * (1 - yo.mean())
    acc_ax.axhline(always0, color="#8a8984", lw=0.8, ls=(0, (1, 3)))
    acc_ax.text(79, always0, "always 0 ", fontsize=7, color=INK_2, ha="right", va="bottom")
    acc_ax.set_ylim(always0 - 25, min(100, always0 + 4))
    acc_ax.set_ylabel("accuracy (%)", color=INK_2)
    acc_ax.grid(False)
    shown_c = min(c, 0.8)
    ax.axvline(100 * shown_c, color=INK_2, ls=":", lw=1.2)
    ax.text(100 * shown_c, 0.98, f" cutoff {100 * c:.1f}%\n ({RULE_TEXT[b['cutoff_rule']]} on\n training games)",
            fontsize=8, va="top", ha="left" if c < 0.6 else "right", color=INK)
    ax.set_xlim(0, 80)
    ax.set_ylim(0, 1.02)
    ax.set_xlabel("cutoff: flag the move if predicted chance ≥ this (%)")
    ax.set_ylabel("share")
    ax.set_title("Choosing the cutoff (solid = training, dashed = test)")
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = acc_ax.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="lower left", fontsize=7.5, frameon=True)

    ax = fig.add_subplot(gs[0, 1])
    cells = {(0, 0): ("quiet", "00", f["tn"]), (0, 1): ("false alarm", "10", f["fp"]),
             (1, 0): ("missed", "01", f["fn"]), (1, 1): ("caught", "11", f["tp"])}
    for (r, k), (lab, code, n) in cells.items():
        ax.add_patch(plt.Rectangle((k, 1 - r), 1, 1, color=OUTCOME_COLORS[lab]))
        row_total = (f["tn"] + f["fp"]) if r == 0 else (f["fn"] + f["tp"])
        ax.text(k + 0.5, 1.5 - r, f"{code} {lab}\n{n:,}\n({100 * n / max(row_total, 1):.0f}% of row)", ha="center",
                va="center", fontsize=10, color=INK, fontweight="bold" if code in ("00", "11") else "normal")
    ax.set_xlim(0, 2)
    ax.set_ylim(0, 2)
    ax.set_xticks([0.5, 1.5], ["flag = 0", "flag = 1"])
    ax.set_yticks([1.5, 0.5], ["actual 0", f"actual 1 ({name})"])
    ax.grid(False)
    ax.set_title(f"Test games: flag vs actual (cutoff {100 * c:.1f}%)")
    ax.text(1, -0.32, f"precision {pct(f['precision'])}   recall {pct(f['recall'])}   F1 {f['f1']:.2f}   "
                      f"accuracy {100 * f['accuracy']:.1f}% (always 0: {100 * f['accuracy_always_no']:.1f}%)",
            ha="center", fontsize=8.5, color=INK_2)

    ax = fig.add_subplot(gs[1, :])
    t = d.assign(p=p, move=(d["ply"] + 1) // 2)
    t["code"] = np.select([(t["p"] >= c) & (t[b["label"]] == 1), (t["p"] < c) & (t[b["label"]] == 1), t["p"] >= c],
                          [3, 2, 1], 0)  # 0 quiet, 1 false alarm, 2 missed, 3 caught
    keys = t.groupby(["game_id", "color"]).agg(ev=(b["label"], "sum"), n=("move", "max")) \
        .sort_values(["ev", "n"], ascending=False).index
    M = np.full((len(keys), int(t["move"].max())), np.nan)
    pos = {k: i for i, k in enumerate(keys)}
    for (g, col), q in t.groupby(["game_id", "color"]):
        M[pos[(g, col)], q["move"].to_numpy() - 1] = q["code"].to_numpy()
    from matplotlib.colors import ListedColormap
    cmap = ListedColormap(list(OUTCOME_COLORS.values()))
    cmap.set_bad("white")
    ax.imshow(np.ma.masked_invalid(M), aspect="auto", interpolation="nearest", cmap=cmap, vmin=-0.5, vmax=3.5)
    ax.grid(False)
    ax.set_xlabel("move number")
    ax.set_ylabel(f"{len(keys)} player-games\n(sorted by number of {name} events)")
    ax.set_yticks([])
    handles = [plt.Rectangle((0, 0), 1, 1, color=OUTCOME_COLORS[k]) for k in OUTCOME_COLORS]
    counts = {"quiet": ("00", f["tn"]), "false alarm": ("10", f["fp"]), "missed": ("01", f["fn"]), "caught": ("11", f["tp"])}
    ax.legend(handles, [f"{counts[k][0]} {k} ({counts[k][1]:,})" for k in OUTCOME_COLORS], loc="lower right", ncol=4,
              fontsize=8, frameon=True)
    ax.set_title("Every test game, move by move: each row is one player in one game")
    fig.suptitle(f"{b['speed']} / {name}: 1/0 flag vs actual on 100 new games", fontsize=11, fontweight="bold", color=INK, y=1.0)
    fig.tight_layout()
    _save(fig, out, f"Codes: first digit = flag, second = actual. Cutoff chosen on training games only "
                    f"({RULE_TEXT[b['cutoff_rule']]}); the test games did not influence it.")


def plot_binary(name: str, b: dict, d: pd.DataFrame, p: np.ndarray, s: dict, out) -> None:
    y = d[b["label"]].to_numpy(int)
    fig, axs = plt.subplots(1, 3, figsize=(15, 4.3))
    ax = axs[0]
    fpr, tpr, _ = roc_curve(y, p)
    ax.plot(fpr, tpr, color=RED, lw=2, label=f"model, AUC {s['auc']:.3f} ({s['auc_ci'][0]:.3f}-{s['auc_ci'][1]:.3f})")
    ax.plot([0, 1], [0, 1], color=INK_2, ls="--", lw=1, label="coin flip, AUC 0.5")
    ax.set_xlabel("false alarms (share of safe moves flagged)")
    ax.set_ylabel("share of real blunders caught")
    ax.set_title("Ranking: risky moves above safe ones?")
    ax.legend(loc="lower right")

    ax = axs[1]
    edges = np.unique(np.quantile(p, np.linspace(0, 1, 11)))
    bins = np.clip(np.searchsorted(edges, p, side="right") - 1, 0, len(edges) - 2)
    t = pd.DataFrame({"p": p, "y": y, "b": bins}).groupby("b").agg(p=("p", "mean"), k=("y", "sum"), n=("y", "size"))
    lo, hi = wilson(t["k"], t["n"])
    ax.errorbar(100 * t["p"], 100 * t["k"] / t["n"], yerr=[100 * (t["k"] / t["n"] - lo), 100 * (hi - t["k"] / t["n"])],
                fmt="o-", color=RED, ms=4, capsize=2, label="test games (95% interval)")
    oof, yo = b["cv"]["oof"], oof_labels(b)
    eo = np.unique(np.quantile(oof, np.linspace(0, 1, 11)))
    bo = np.clip(np.searchsorted(eo, oof, side="right") - 1, 0, len(eo) - 2)
    to = pd.DataFrame({"p": oof, "y": yo, "b": bo}).groupby("b").mean()
    ax.plot(100 * to["p"], 100 * to["y"], "s--", color=INK_2, ms=3, lw=1, label="training games (cross-validation)")
    m = max(100 * t["p"].max(), 100 * (t["k"] / t["n"]).max()) * 1.05
    ax.plot([0, m], [0, m], color=INK_2, lw=0.8, ls=":")
    ax.set_xlabel("predicted chance (%)")
    ax.set_ylabel("what actually happened (%)")
    ax.set_title("Calibration: does 20% mean 20%?")
    ax.legend(loc="upper left")

    ax = axs[2]
    rate = 100 * t["k"] / t["n"]
    ax.bar(range(len(t)), rate, color=[RED if i == len(t) - 1 else "#f0a8a7" for i in range(len(t))])
    ax.axhline(100 * y.mean(), color=INK, ls="--", lw=1, label=f"test average {100 * y.mean():.1f}%")
    ax.set_xticks(range(len(t)), [f"{i + 1}" for i in range(len(t))])
    ax.set_xlabel("predicted risk decile (1 = safest 10% of moves, 10 = riskiest)")
    ax.set_ylabel(f"actual {name} rate (%)")
    ax.set_title("Actual rate by predicted risk")
    ax.legend()
    fig.suptitle(f"{b['speed']} / {name}: {len(y):,} test moves from 100 new games", fontsize=11,
                 fontweight="bold", color=INK, y=1.02)
    fig.tight_layout()
    _save(fig, out)


def plot_think(b: dict, d: pd.DataFrame, pred: pd.DataFrame, s: dict, out) -> None:
    t = d[b["label"]].to_numpy(float)
    lo, md, hi = (pred[c].to_numpy(float) for c in ("think_low", "think_median", "think_high"))
    fig, axs = plt.subplots(1, 3, figsize=(15, 4.3))
    ax = axs[0]
    jit = RNG.uniform(-0.35, 0.35, (2, len(t)))
    ax.scatter(np.log1p(md) + 0.06 * jit[0], np.log1p(t) + 0.06 * jit[1], s=3, alpha=0.15, color=COLORS[b["speed"]])
    mx = np.log1p(max(t.max(), md.max()))
    ax.plot([0, mx], [0, mx], color=INK, lw=1, ls="--", label="perfect")
    ticks = [0, 1, 2, 5, 10, 30, 60, 180, 600]
    ticks = [v for v in ticks if np.log1p(v) <= mx * 1.02]
    ax.set_xticks(np.log1p(ticks), ticks)
    ax.set_yticks(np.log1p(ticks), ticks)
    ax.set_xlabel("predicted think time (s, median)")
    ax.set_ylabel("actual think time (s)")
    ax.set_title(f"Every test move (Spearman {s['spearman']:.2f})")
    ax.legend(loc="upper left")

    ax = axs[1]
    df = pd.DataFrame({"t": t, "lo": lo, "md": md, "hi": hi})
    df["b"] = pd.qcut(df["md"].rank(method="first"), 10, labels=False)
    g = df.groupby("b").agg(md=("md", "median"), lo=("lo", "median"), hi=("hi", "median"),
                            a10=("t", lambda v: v.quantile(.1)), a50=("t", "median"), a90=("t", lambda v: v.quantile(.9)))
    x = range(len(g))
    ax.fill_between(x, g["lo"], g["hi"], color=COLORS[b["speed"]], alpha=0.2, label="predicted 80% range (median)")
    ax.plot(x, g["md"], color=COLORS[b["speed"]], marker="o", label="predicted median")
    ax.plot(x, g["a50"], color=INK, marker="s", ls="--", label="actual median")
    ax.plot(x, g["a10"], color=INK_2, ls=":", lw=1, label="actual 10% / 90%")
    ax.plot(x, g["a90"], color=INK_2, ls=":", lw=1)
    ax.set_xticks(list(x), [str(i + 1) for i in x])
    ax.set_xlabel("predicted think-time decile (1 = fastest predicted)")
    ax.set_ylabel("seconds")
    ax.set_title(f"Range covers {100 * s['coverage_80']:.0f}% of moves (target 80%)")
    ax.legend(fontsize=7)

    ax = axs[2]
    rows = [("model", s)] + list(s["baselines"].items())
    labels = [r[0] for r in rows]
    w2 = [100 * r[1]["within_2x"] for r in rows]
    mae = [r[1]["mae_s"] for r in rows]
    yy = np.arange(len(rows))
    ax.barh(yy, w2, color=[COLORS[b["speed"]]] + [GRID] * (len(rows) - 1))
    for i, (v, e) in enumerate(zip(w2, mae)):
        ax.text(v, i, f" {v:.0f}%   (avg error {e:.1f}s)", va="center", fontsize=7.5)
    ax.set_yticks(yy, labels)
    ax.invert_yaxis()
    ax.set_xlim(0, 115)
    ax.set_xlabel("% of moves predicted within 2x of the real time")
    ax.set_title("Model vs simple rules")
    fig.suptitle(f"{b['speed']} / think time: {len(t):,} test moves from 100 new games", fontsize=11,
                 fontweight="bold", color=INK, y=1.02)
    fig.tight_layout()
    _save(fig, out)


def plot_example(speed: str, moves: pd.DataFrame, pred: pd.DataFrame, cutoffs: dict, out) -> str:
    """One test game, one player: predicted risk and think time vs what happened, move by move.
    Chosen neutrally as the player-game with the most blunders (ties: longest game)."""
    m = moves.join(pred)
    k = m.groupby(["game_id", "color"]).agg(bl=("blunder", "sum"), n=("ply", "size")).sort_values(["bl", "n"], ascending=False)
    gid, color = k.index[0]
    g = m[(m["game_id"] == gid) & (m["color"] == color)].sort_values("ply")
    x = (g["ply"] + 1) // 2
    fig, axs = plt.subplots(2, 1, figsize=(12, 6), sharex=True)
    ax = axs[0]
    ax.plot(x, 100 * g["p_blunder"], color=RED, marker="o", ms=3, label="predicted chance of blunder now")
    ax.plot(x, 100 * g["p_blunder_next5"], color=INK_2, ls="--", lw=1.2, label="predicted chance of blunder within 5 moves")
    bl = g[g["blunder"] == 1]
    ax.scatter((bl["ply"] + 1) // 2, 100 * bl["p_blunder"], s=140, facecolors="none", edgecolors=INK, lw=2,
               label="actual blunder", zorder=5)
    ax.axhline(100 * cutoffs["blunder"], color=RED, ls=":", lw=1, label=f"flag cutoff, blunder now ({100 * cutoffs['blunder']:.1f}%)")
    ax.axhline(100 * cutoffs["blunder_next5"], color=INK_2, ls=":", lw=1,
               label=f"flag cutoff, within 5 ({100 * cutoffs['blunder_next5']:.1f}%)")
    ax.set_ylabel("%")
    ax.set_ylim(bottom=0)
    ax.legend(loc="upper left", fontsize=7.5)
    ax.set_title(f"{speed}: game {gid}, {color} (rated {int(g['elo_self'].iloc[0])}), "
                 f"{int(g['base'].iloc[0])}+{int(g['inc'].iloc[0])}", color=INK)
    ax = axs[1]
    ax.fill_between(x, g["think_low"], g["think_high"], color=COLORS[speed], alpha=0.2, step="mid", label="predicted 80% range")
    ax.plot(x, g["think_median"], color=COLORS[speed], drawstyle="steps-mid", label="predicted think time")
    ax.scatter(x, g["time_spent"], color=INK, s=12, zorder=5, label="actual think time")
    ax.set_xlabel("move number")
    ax.set_ylabel("seconds")
    ax.legend(loc="upper left", fontsize=7.5)
    ax2 = ax.twinx()
    ax2.plot(x, g["clock_self"], color=INK_2, lw=0.8, ls=":")
    ax2.set_ylabel("clock left (dotted, s)", color=INK_2)
    ax2.grid(False)
    fig.tight_layout()
    _save(fig, out, "Example chosen as the test player-game with the most blunders, not as a best case.")
    return f"{gid} ({color})"


def elo_check(speed: str, bundles: dict) -> pd.DataFrame:
    """Does one model per speed work for every rating? Uses the cross-validation predictions on the
    2,000 training games (each move predicted by a model that never saw its game)."""
    from oracle.config import ELO_BANDS, ELO_EDGES
    from sklearn.metrics import roc_auc_score

    tr = pd.read_parquet(TRAIN_DATA / speed / "moves.parquet")
    rows = []
    for target, b in bundles.items():
        d = tr[tr[b["label"]].notna()].reset_index(drop=True)
        band = pd.cut(d["elo_self"], ELO_EDGES, labels=ELO_BANDS, right=False)
        oof = b["cv"]["oof"]
        for name in ELO_BANDS:
            k = (band == name).to_numpy()
            y = d.loc[k, b["label"]].to_numpy(float)
            r = {"speed": speed, "target": target, "elo": name, "moves": int(k.sum())}
            if target == "think_time":
                lo, md, hi = oof[k, 0], oof[k, 1], oof[k, 2]
                r.update(mae=np.mean(np.abs(md - y)), within_2x=np.mean(np.abs(np.log2((y + 1) / (md + 1))) <= 1),
                         coverage=np.mean((y >= lo) & (y <= hi)))
            else:
                p = oof[k]
                r.update(actual=y.mean(), predicted=p.mean(), auc=roc_auc_score(y, p))
            rows.append(r)
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
def ci(s: dict, k: str, as_pct: bool = False) -> str:
    lo, hi = s[f"{k}_ci"]
    f = (lambda v: f"{100 * v:.0f}%") if as_pct else (lambda v: f"{v:.3f}")
    return f"{f(s[k])} ({f(lo)}–{f(hi)})"


def pct(v, digits: int = 0) -> str:
    return "–" if v is None or np.isnan(v) else f"{100 * v:.{digits}f}%"


def main() -> None:
    style()
    results, examples, sizes, elo = {}, {}, {}, []
    for speed in SPEEDS:
        moves = pd.read_parquet(TEST_DATA / speed / "moves.parquet")
        bundles = {t: joblib.load(MODELS / speed / f"{t}.joblib") for t in TARGETS}
        elo.append(elo_check(speed, bundles))
        pred = predict_moves(bundles, moves)
        moves.join(pred).to_parquet(TEST_DATA / speed / "predictions.parquet", index=False)
        out = REPORTS / speed
        sizes[speed] = (moves["game_id"].nunique(), len(moves), bundles["blunder"]["train_games"],
                        bundles["blunder"]["train_rows"])
        for target, b in bundles.items():
            d = moves[moves[b["label"]].notna()]
            if target == "think_time":
                s = eval_think(b, d, pred.loc[d.index])
                plot_think(b, d, pred.loc[d.index], s, out / "think_time.png")
            else:
                p = pred.loc[d.index, f"p_{target}"].to_numpy()
                s = eval_binary(b, d, p)
                plot_binary(NAMES[target], b, d, p, s, out / f"{target}.png")
                plot_flags(NAMES[target], b, d, p, s, out / f"{target}_flags.png")
            results[(speed, target)] = s
            print(f"{speed:10s} {target:14s} " + (f"MAE {s['mae_s']:.2f}s  within2x {s['within_2x']:.3f}  cover {s['coverage_80']:.3f}"
                                                  if target == "think_time" else
                                                  f"AUC {s['auc']:.3f}  PR-AUC {s['pr_auc']:.3f}  Brier skill {s['brier_skill']:.3f}"))
        examples[speed] = plot_example(speed, moves, pred, {t: bundles[t]["cutoff"] for t in ("blunder", "blunder_next5")},
                                       out / "example_game.png")
    (REPORTS / "RESULTS.md").write_text(results_md(results, examples, sizes, pd.concat(elo)), encoding="utf-8")
    print(f"wrote {REPORTS / 'RESULTS.md'}")


def elo_md(E: pd.DataFrame) -> list[str]:
    from oracle.config import ELO_BANDS
    L = ["## Does one model work for every rating?", "",
         "Cross-validation predictions on the 2,000 training games per speed, split by the mover's rating "
         "(the 100 test games are too few to split five ways).", ""]
    for target in ("blunder", "blunder_next5"):
        q = E[E["target"] == target]
        L += [f"**{NAMES[target]}**: AUC, and actual vs predicted rate", "",
              "| speed | " + " | ".join(ELO_BANDS) + " |", "|---|" + "---|" * len(ELO_BANDS)]
        for sp in SPEEDS:
            r = q[q["speed"] == sp].set_index("elo")
            L.append(f"| {sp} | " + " | ".join(
                f"{r.loc[b, 'auc']:.2f}, {100 * r.loc[b, 'actual']:.1f}% vs {100 * r.loc[b, 'predicted']:.1f}%" for b in ELO_BANDS) + " |")
        L.append("")
    q = E[E["target"] == "think_time"]
    L += ["**think time**: within 2x, and how often the 80% range covered the real time", "",
          "| speed | " + " | ".join(ELO_BANDS) + " |", "|---|" + "---|" * len(ELO_BANDS)]
    for sp in SPEEDS:
        r = q[q["speed"] == sp].set_index("elo")
        L.append(f"| {sp} | " + " | ".join(
            f"{100 * r.loc[b, 'within_2x']:.0f}%, covers {100 * r.loc[b, 'coverage']:.0f}%" for b in ELO_BANDS) + " |")
    return L + [""]


def results_md(R: dict, examples: dict, sizes: dict, E: pd.DataFrame) -> str:
    L = ["# Test results: 9 models on 100 new games per speed", "",
         "Models trained on all 2,000 EDA games per speed; tested on 100 games per speed pulled later the same "
         "day (zero overlap). Brackets = 95% interval from resampling test games.", "",
         "| speed | training (games / moves) | test (games / moves) |", "|---|---:|---:|"]
    for s, (tg, tm, trg, trm) in sizes.items():
        L.append(f"| {s} | {trg:,} / {trm:,} | {tg} / {tm:,} |")
    L += ["", "## Blunder models (A: blunder now, B: blunder in next 5)", "",
          "| speed | target | AUC | PR-AUC (base rate) | top-10% flagged: hit rate / blunders caught | "
          "Brier skill | predicted vs actual count | CV AUC (training) |",
          "|---|---|---|---|---|---|---|---|"]
    for (sp, t), s in R.items():
        if t == "think_time":
            continue
        L.append(f"| {sp} | {NAMES[t]} | {ci(s, 'auc')} | {s['pr_auc']:.3f} ({s['rate']:.3f}) | "
                 f"{100 * s['top10_precision']:.0f}% / {100 * s['top10_recall']:.0f}% | {ci(s, 'brier_skill')} | "
                 f"{s['expected']:.0f} vs {s['positives']} | {s['cv']['auc']:.3f} |")
    L += ["", "- **AUC**: pick a random move that was a blunder and one that wasn't; AUC = how often the model gave the "
          "blunder the higher risk (0.5 = coin flip, 1 = perfect).",
          "- **PR-AUC**: how precise the alarms are across all thresholds; compare with the base rate (what a "
          "random guess gets).",
          "- **Top-10% flagged**: flag the 10% riskiest moves; hit rate = share of flags that were blunders, "
          "caught = share of all blunders that were flagged.",
          "- **Brier skill**: how much smaller the average squared gap between predicted chance and outcome (0/1) is "
          "than always guessing the training base rate (0 = no better, 1 = perfect).",
          "- **Accuracy at a 50% threshold** is not shown in the table because it is misleading for rare events: "
          "'never a blunder' already scores 95%. It is in the per-speed sections.", "",
          "## 1/0 flags: flag = 1 if predicted chance ≥ cutoff", ""]
    rule = next(s["flags"]["rule"] for (sp, t), s in R.items() if t != "think_time")
    L += [f"Each cutoff was chosen on the training games (cross-validation predictions) by the rule **{RULE_TEXT[rule]}** "
          f"({CUTOFF_RULES[rule]}), then applied unchanged to the test games. Codes: first digit = flag, second = actual.", "",
          "| speed | target | cutoff | moves flagged | 00 quiet | 11 caught | 10 false alarm | 01 missed | "
          "flags that were real (precision) | 1s caught (recall) | F1 | accuracy (always 0) |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for (sp, t), s in R.items():
        if t == "think_time":
            continue
        f = s["flags"]
        L.append(f"| {sp} | {NAMES[t]} | {100 * f['cutoff']:.1f}% | {100 * f['flagged']:.1f}% | {f['tn']:,} | {f['tp']} | "
                 f"{f['fp']} | {f['fn']} | {pct(f['precision'])} ({pct(f['precision_ci'][0])}–{pct(f['precision_ci'][1])}) | "
                 f"{pct(f['recall'])} ({pct(f['recall_ci'][0])}–{pct(f['recall_ci'][1])}) | {f['f1']:.2f} | "
                 f"{100 * f['accuracy']:.1f}% ({100 * f['accuracy_always_no']:.1f}%) |")
    L += ["", "**Same models, other ways to pick the cutoff** (each chosen on the training games, scored on the test games):", "",
          "| speed | target | rule | cutoff | moves flagged | accuracy | 0s right | 1s right | flags that were real |",
          "|---|---|---|---|---|---|---|---|---|"]
    for (sp, t), s in R.items():
        if t == "think_time":
            continue
        for r, f in s["cutoff_options"].items():
            L.append(f"| {sp} | {NAMES[t]} | {r}{' (used)' if r == s['flags']['rule'] else ''} | {100 * f['cutoff']:.1f}% | "
                     f"{100 * f['flagged']:.1f}% | {100 * f['accuracy']:.1f}% | {100 * f['specificity']:.1f}% | "
                     f"{100 * f['recall']:.1f}% | {pct(f['precision'])} |")
    L += ["", f"- **accuracy**: {CUTOFF_RULES['accuracy']}. For rare events it flags a move only when a blunder is more "
          "likely than not, so it flags almost nothing.",
          f"- **f1**: {CUTOFF_RULES['f1']}.",
          f"- **balanced**: {CUTOFF_RULES['balanced']}. Gets most 0s *and* most 1s right as rates, at the cost of many "
          "false alarms.", "",
          "## Think-time models", "",
          "| speed | avg error (MAE) | typical error (median) | within 2x of real time | 80% range covers | "
          "rank correlation | best simple rule (MAE / within 2x) | model minus best rule (MAE / within 2x) | CV MAE (training) |",
          "|---|---|---|---|---|---|---|---|---|"]
    for (sp, t), s in R.items():
        if t != "think_time":
            continue
        v = s["vs_best"]
        bs = s["baselines"][v["rule"]]
        L.append(f"| {sp} | {s['mae_s']:.2f}s ({s['mae_s_ci'][0]:.2f}–{s['mae_s_ci'][1]:.2f}) | {s['median_ae_s']:.1f}s | "
                 f"{ci(s, 'within_2x', as_pct=True)} | {ci(s, 'coverage_80', as_pct=True)} | {s['spearman']:.2f} | "
                 f"{v['rule']}: {bs['mae_s']:.2f}s / {100 * bs['within_2x']:.0f}% | "
                 f"{v['d_mae']:+.2f}s ({v['d_mae_ci'][0]:+.2f} to {v['d_mae_ci'][1]:+.2f}) / "
                 f"{100 * v['d_w2']:+.1f} pts ({100 * v['d_w2_ci'][0]:+.1f} to {100 * v['d_w2_ci'][1]:+.1f}) | "
                 f"{s['cv']['mae_s']:.2f}s |")
    L += ["", "- **MAE**: average |predicted median − actual seconds|. The median is used because think times are "
          "very skewed (most moves are fast, a few take minutes).",
          "- **Within 2x**: prediction is between half and double the real time (on seconds + 1).",
          "- **80% range covers**: share of moves whose real time fell inside the predicted low–high range.", ""]
    L += elo_md(E)
    for sp in SPEEDS:
        L += [f"## {sp}", ""]
        for t in TARGETS:
            s = R[(sp, t)]
            if t == "think_time":
                L += ["### think time", "", f"![think time](./{sp}/think_time.png)", "",
                      "| model / rule | MAE | median error | within 2x | bias (pred − actual) |", "|---|---:|---:|---:|---:|",
                      f"| **model** | {s['mae_s']:.2f}s | {s['median_ae_s']:.1f}s | {100 * s['within_2x']:.1f}% | {s['bias_s']:+.2f}s |"]
                for n, bs in s["baselines"].items():
                    L.append(f"| {n} | {bs['mae_s']:.2f}s | {bs['median_ae_s']:.1f}s | {100 * bs['within_2x']:.1f}% | {bs['bias_s']:+.2f}s |")
                L += ["", f"Median predicted range width: {s['width_s']:.0f}s. A negative bias is expected: the median of "
                      "a skewed distribution sits below its average.", ""]
            else:
                b0 = s["baseline"]
                L += [f"### {NAMES[t]}", "", f"![{t}](./{sp}/{t}.png)", "",
                      f"- {s['n']:,} moves, {s['positives']} actual ({100 * s['rate']:.1f}%); model expected "
                      f"{s['expected']:.0f}.",
                      f"- Accuracy if we call 'blunder' when risk ≥ 50%: {100 * s['accuracy_at_50']:.1f}% vs "
                      f"{100 * s['accuracy_always_no']:.1f}% for always saying 'no' (why accuracy is the wrong yardstick here).",
                      f"- Flagging the riskiest 10% of moves: {100 * s['top10_precision']:.0f}% of flags were real "
                      f"(vs {100 * s['rate']:.1f}% at random, {s['top10_lift']:.1f}x), catching "
                      f"{100 * s['top10_recall']:.0f}% of all {NAMES[t]} events.",
                      f"- Log-loss skill {ci(s, 'log_loss_skill')} and Brier skill {ci(s, 'brier_skill')} vs "
                      f"always guessing the training rate ({100 * b0['rate']:.1f}% actual here). "
                      f"Calibration error (ECE) {100 * s['ece']:.1f} points."]
                if t == "blunder":
                    pg = s["per_game"]
                    L.append(f"- Per player-game ({pg['n']} of them): predicted vs real number of blunders correlate "
                             f"{pg['corr']:.2f}; average miss {pg['mae']:.2f} blunders (players made {pg['mean_real']:.2f} on average).")
                f = s["flags"]
                L += [f"- **1/0 flag** (cutoff {100 * f['cutoff']:.1f}%, {RULE_TEXT[f['rule']]}): 00 quiet {f['tn']:,}, "
                      f"11 caught {f['tp']}, 10 false alarms {f['fp']}, 01 missed {f['fn']}: precision {pct(f['precision'])}, "
                      f"recall {pct(f['recall'])}, F1 {f['f1']:.2f}; accuracy {100 * f['accuracy']:.1f}% vs "
                      f"{100 * f['accuracy_always_no']:.1f}% for always 0.", "", f"![{t} flags](./{sp}/{t}_flags.png)"]
                L.append("")
        L += ["### example game", "", f"![example](./{sp}/example_game.png)", "",
              f"Player-game {examples[sp]}: the test game with the most blunders by one player.", ""]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
