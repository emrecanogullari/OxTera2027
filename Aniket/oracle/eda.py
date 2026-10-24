"""Features vs labels, per game speed and per Elo band. No models: only associations.

For every label (think_time, blunder, blunder_next5), speed and Elo band we measure:
  eta  correlation ratio, 0..1: how much of the label's variation is explained by
       which decile of the feature a move falls in. Like a correlation, but it also
       catches U/V shapes (e.g. wp_self). eta^2 = between-bin variance / total variance.
  rho  Spearman rank correlation: the direction (+ = higher feature -> higher label)
       and how monotone the link is.
think_time is measured on log(1 + seconds) so a few 5-minute thinks don't dominate.

Outputs (reports/<label>/):
  ranking.png        eta for every feature x (speed, Elo band), arrows = direction
  <speed>.png        label vs each relevant feature, one line per Elo band
  speeds.png         label vs each relevant feature, one line per speed
  clock_in_position.png  (blunder labels) time pressure inside fixed win% bands
  ranking.md         the table behind ranking.png
plus reports/feature_ranking.csv and reports/feature_redundancy.png
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .config import COLORS, ELO_BANDS, ELO_COLORS, ELO_EDGES, GRID, INK, INK_2, LABELS, RED, SPEEDS, SURFACE
from .features import FEATURE_COLS, FEATURES

GROUP_COLORS = {"clock": "#2a78d6", "players": "#1baf7a", "context": "#8a8984", "position": "#6250d6",
                "engine": "#eb6834"}
LOG_X = {"clock_self", "clock_opp", "prev_self_spent", "avg_self_spent", "prev_opp_spent", "base", "abs_cp"}
RNG = 0


def style() -> None:
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "axes.edgecolor": GRID, "axes.labelcolor": INK_2, "axes.titlecolor": INK,
        "axes.titlesize": 10, "axes.titleweight": "bold", "axes.labelsize": 8,
        "xtick.color": INK_2, "ytick.color": INK_2, "xtick.labelsize": 7, "ytick.labelsize": 7,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
        "axes.spines.top": False, "axes.spines.right": False,
        "legend.frameon": False, "legend.fontsize": 7, "lines.linewidth": 1.6,
        "font.size": 8, "figure.dpi": 110,
    })


def _save(fig, path: Path, note: str | None = None) -> Path:
    if note:
        fig.text(0.01, -0.01, note, fontsize=7, color=INK_2, ha="left", va="top")
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


def wilson(k, n, z: float = 1.96):
    """95% Wilson interval for a binomial rate (stable for rare events)."""
    k, n = np.asarray(k, float), np.asarray(n, float)
    with np.errstate(divide="ignore", invalid="ignore"):
        p = k / n
        den = 1 + z**2 / n
        ctr = (p + z**2 / (2 * n)) / den
        half = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / den
    return ctr - half, ctr + half


# --------------------------------------------------------------------------- #
# data
def prepare(moves: pd.DataFrame) -> pd.DataFrame:
    m = moves.copy()
    m["elo_band"] = pd.cut(m["elo_self"], ELO_EDGES, labels=ELO_BANDS, right=False)
    m["log_think"] = np.log1p(m["time_spent"])
    return m


def target(label: str) -> tuple[str, bool]:
    """(column used for statistics, is_binary)"""
    col = LABELS[label][0]
    return ("log_think", False) if col == "time_spent" else (col, True)


def _bins(x: pd.Series, k: int = 10) -> pd.Series:
    if x.nunique() <= 12:
        return x
    return pd.qcut(x, k, duplicates="drop")


def eta(x: pd.Series, y: pd.Series) -> float:
    ok = x.notna() & y.notna()
    x, y = x[ok], y[ok]
    if len(y) < 2000 or y.var() == 0 or x.nunique() < 2:
        return np.nan
    g = y.groupby(_bins(x), observed=True)
    between = (g.count() * (g.mean() - y.mean()) ** 2).sum()
    return float(np.sqrt(between / ((y - y.mean()) ** 2).sum()))


def spearman(x: pd.Series, y: pd.Series) -> float:
    ok = x.notna() & y.notna()
    if ok.sum() < 2000 or x[ok].nunique() < 2:
        return np.nan
    return float(x[ok].rank().corr(y[ok].rank()))


# --------------------------------------------------------------------------- #
# ranking
def ranking(data: dict[str, pd.DataFrame], max_rows: int = 600_000, log=print) -> pd.DataFrame:
    rows = []
    for label in LABELS:
        ycol, _ = target(label)
        for speed, m in data.items():
            d = m[m[ycol].notna()]
            d = d.sample(max_rows, random_state=RNG) if len(d) > max_rows else d
            games = d["game_id"].unique()
            half = set(np.random.default_rng(RNG).choice(games, len(games) // 2, replace=False))
            h1 = d["game_id"].isin(half)
            for f in FEATURE_COLS:
                r = {"label": label, "speed": speed, "feature": f, "group": FEATURES[f][0],
                     "eta": eta(d[f], d[ycol]), "rho": spearman(d[f], d[ycol]), "n": int(d[f].notna().sum()),
                     "eta_half_gap": abs(eta(d.loc[h1, f], d.loc[h1, ycol]) - eta(d.loc[~h1, f], d.loc[~h1, ycol]))}
                for band in ELO_BANDS:
                    b = d[d["elo_band"] == band]
                    r[f"eta_{band}"] = eta(b[f], b[ycol])
                rows.append(r)
            log(f"  ranked {label:13s} {speed}")
    return pd.DataFrame(rows)


def recommend(rank: pd.DataFrame, corr: pd.DataFrame, label: str, k: int = 8, max_rho: float = 0.8) -> list[str]:
    """The k strongest features (mean eta over speeds) that are not near-duplicates of a stronger pick
    (|Spearman rho| >= max_rho with an already-kept feature)."""
    s = rank[rank["label"] == label].groupby("feature")["eta"].mean().sort_values(ascending=False)
    keep = []
    for f in s.index:
        if len(keep) == k:
            break
        if all(abs(corr.loc[f, kf]) < max_rho for kf in keep):
            keep.append(f)
    return keep


def feature_corr(data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Spearman between features WITHIN each speed, averaged (pooling speeds would make every
    clock feature look like 'base', just because classical clocks are bigger)."""
    cs = [m.sample(min(len(m), 150_000), random_state=RNG)[FEATURE_COLS].corr(method="spearman")
          for m in data.values()]
    return sum(cs) / len(cs)


def plot_redundancy(corr: pd.DataFrame, out: Path) -> Path:
    from scipy.cluster.hierarchy import leaves_list, linkage
    from scipy.spatial.distance import squareform

    c = corr.fillna(0)
    order = [FEATURE_COLS[i] for i in leaves_list(linkage(squareform(1 - c.abs().to_numpy(), checks=False), "average"))]
    c = c.loc[order, order]
    fig, ax = plt.subplots(figsize=(9.5, 8))
    im = ax.imshow(c.to_numpy(), cmap="RdBu_r", vmin=-1, vmax=1)
    for i in range(len(order)):
        for j in range(len(order)):
            v = c.iat[i, j]
            if abs(v) >= 0.3 and i != j:
                ax.text(j, i, f"{v:.1f}", ha="center", va="center", fontsize=6, color=SURFACE if abs(v) > 0.7 else INK)
    ax.set_xticks(range(len(order)), order, rotation=90)
    ax.set_yticks(range(len(order)), order)
    for t in list(ax.get_xticklabels()) + list(ax.get_yticklabels()):
        t.set_color(GROUP_COLORS[FEATURES[t.get_text()][0]])
    ax.grid(False)
    ax.set_title("Which features say the same thing? (Spearman within each speed, averaged)")
    fig.colorbar(im, ax=ax, shrink=0.7)
    return _save(fig, out, "|rho| ≥ 0.8 = near-duplicates: keep one. Tick colour = feature group.")


def plot_ranking(rank: pd.DataFrame, label: str, out: Path) -> Path:
    r = rank[rank["label"] == label]
    order = r.groupby("feature")["eta"].mean().sort_values(ascending=False).index
    cols, heads = [], []
    for s in SPEEDS:
        for band in ["all"] + ELO_BANDS:
            cols.append((s, band))
            heads.append(f"{s}\nall" if band == "all" else band)
    M = np.full((len(order), len(cols)), np.nan)
    sign = np.zeros_like(M)
    for j, (s, band) in enumerate(cols):
        q = r[r["speed"] == s].set_index("feature").reindex(order)
        M[:, j] = q["eta"] if band == "all" else q[f"eta_{band}"]
        sign[:, j] = np.sign(q["rho"])
    fig, ax = plt.subplots(figsize=(15, 0.36 * len(order) + 1.8))
    im = ax.imshow(M, cmap="Reds", aspect="auto", vmin=0, vmax=np.nanmax(M))
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            if np.isfinite(M[i, j]):
                arrow = "↑" if sign[i, j] > 0 else "↓"
                ax.text(j, i, f"{M[i, j]:.2f}{arrow}", ha="center", va="center", fontsize=6,
                        color=SURFACE if M[i, j] > 0.6 * np.nanmax(M) else INK)
    for k in range(1, len(SPEEDS)):
        ax.axvline(k * (len(ELO_BANDS) + 1) - 0.5, color=INK, lw=1.5)
    ax.set_xticks(range(len(cols)), heads, fontsize=6.5)
    ax.set_yticks(range(len(order)), order)
    for t in ax.get_yticklabels():
        t.set_color(GROUP_COLORS[FEATURES[t.get_text()][0]])
    ax.grid(False)
    ax.set_title(f"{label}: how strongly each feature relates to it (eta), by speed and Elo band")
    fig.colorbar(im, ax=ax, shrink=0.6, pad=0.01)
    return _save(fig, out, "eta = correlation ratio (0 = no link, catches U-shapes too). ↑ = higher feature → higher "
                           f"{label}, ↓ = lower. Sorted by mean over speeds. Label colour = feature group.")


def ranking_md(rank: pd.DataFrame, label: str, keep: list[str]) -> str:
    r = rank[rank["label"] == label]
    e = r.pivot(index="feature", columns="speed", values="eta")[list(SPEEDS)]
    p = r.pivot(index="feature", columns="speed", values="rho")[list(SPEEDS)]
    gap = r.groupby("feature")["eta_half_gap"].max()
    band = r.groupby("feature")[[f"eta_{b}" for b in ELO_BANDS]].mean().mean(axis=1)
    t = pd.DataFrame({"mean_eta": e.mean(axis=1)}).join(e.add_prefix("eta_")).join(p.add_prefix("rho_"))
    t["eta_within_elo_bands"] = band
    t["split_half_gap"] = gap
    t = t.sort_values("mean_eta", ascending=False)
    col, meaning = LABELS[label]
    lines = [f"# {label}: {meaning}", "",
             f"Top 8 features that are not near-duplicates of a stronger one: **{', '.join(keep)}**", "",
             "| feature | meaning | keep | mean eta | " + " | ".join(f"eta {s}" for s in SPEEDS) + " | "
             + " | ".join(f"rho {s}" for s in SPEEDS) + " | eta inside Elo bands | split-half gap |",
             "|---|---|:-:|" + "---:|" * (2 * len(SPEEDS) + 3)]
    for f, x in t.iterrows():
        lines.append(f"| `{f}` | {FEATURES[f][1]} | {'✓' if f in keep else ''} | {x['mean_eta']:.3f} | "
                     + " | ".join(f"{x[f'eta_{s}']:.3f}" for s in SPEEDS) + " | "
                     + " | ".join(f"{x[f'rho_{s}']:+.3f}" for s in SPEEDS)
                     + f" | {x['eta_within_elo_bands']:.3f} | {x['split_half_gap']:.3f} |")
    lines += ["", "eta: correlation ratio over feature deciles (0-1, catches non-linear shapes). rho: Spearman "
              "(sign = direction). 'inside Elo bands' = mean eta computed within each rating band: if it is much "
              "lower than mean eta, the feature mostly stands in for rating. split-half gap = |eta(half A) - eta(half B)| "
              "over two random halves of the games (small = stable)."
              + (" think_time is measured as log(1 + seconds)." if col == "time_spent" else "")]
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# trend plots
def _curve(d: pd.DataFrame, f: str, ycol: str, binary: bool, edges, raw_y: str, min_n: int = 150):
    b = pd.cut(d[f], edges, include_lowest=True) if edges is not None else d[f]
    g = d.groupby(b, observed=True)
    t = pd.DataFrame({"x": g[f].median(), "n": g[raw_y].count(),
                      "y": g[raw_y].mean() * (100 if binary else 1)})
    if binary:
        lo, hi = wilson(g[raw_y].sum(), t["n"])
        t["lo"], t["hi"] = 100 * lo, 100 * hi
    return t[t["n"] >= min_n]


def _edges(x: pd.Series):
    x = x.dropna()
    if x.nunique() <= 12:
        return None
    e = np.unique(np.quantile(x, np.linspace(0, 1, 13)))
    e[-1] += 1e-9
    return e


def _ylabel(label: str) -> str:
    return "avg seconds" if label == "think_time" else f"% {label}"


def plot_by_elo(m: pd.DataFrame, speed: str, label: str, feats: list[str], out: Path) -> Path:
    ycol, binary = target(label)
    raw = LABELS[label][0]
    feats = [f for f in feats if f not in ("elo_self", "elo_opp")]  # constant-ish inside a band
    d = m[m[raw].notna()]
    cols = 4
    rows = int(np.ceil(len(feats) / cols))
    fig, axs = plt.subplots(rows, cols, figsize=(14, 2.9 * rows), squeeze=False)
    for ax, f in zip(axs.flat, feats):
        edges = _edges(d[f])
        for band, c in zip(ELO_BANDS, ELO_COLORS):
            t = _curve(d[d["elo_band"] == band], f, ycol, binary, edges, raw)
            ax.plot(t["x"], t["y"], color=c, marker="o", ms=2.5, label=band)
        t = _curve(d, f, ycol, binary, edges, raw)
        if binary:
            ax.fill_between(t["x"], t["lo"], t["hi"], color=INK, alpha=0.08, lw=0)
        ax.plot(t["x"], t["y"], color=INK, ls="--", lw=1.2, label="all ratings")
        if f in LOG_X and d[f].min() >= 0:
            ax.set_xscale("symlog", linthresh=1)
        ax.set_title(f, color=GROUP_COLORS[FEATURES[f][0]])
        ax.set_ylim(bottom=0)
    for ax in list(axs.flat)[len(feats):]:
        ax.axis("off")
    axs[0, 0].set_ylabel(_ylabel(label))
    axs[0, 0].legend(fontsize=6.5)
    fig.suptitle(f"{speed}: {label} vs its most relevant features, by rating", fontsize=11, fontweight="bold",
                 color=INK, y=1.0)
    fig.tight_layout()
    return _save(fig, out, f"x = median of each of 12 equal-count bins (all ratings pooled); points with < 150 moves "
                           f"hidden. Dashed = all ratings{' with 95% band' if binary else ''}. {LABELS[label][1]}.")


def plot_speeds(data: dict[str, pd.DataFrame], label: str, feats: list[str], out: Path) -> Path:
    ycol, binary = target(label)
    raw = LABELS[label][0]
    cols = 4
    rows = int(np.ceil(len(feats) / cols))
    fig, axs = plt.subplots(rows, cols, figsize=(14, 2.9 * rows), squeeze=False)
    for ax, f in zip(axs.flat, feats):
        for s, m in data.items():
            d = m[m[raw].notna()]
            t = _curve(d, f, ycol, binary, _edges(d[f]), raw)
            if binary:
                ax.fill_between(t["x"], t["lo"], t["hi"], color=COLORS[s], alpha=0.12, lw=0)
            ax.plot(t["x"], t["y"], color=COLORS[s], marker="o", ms=2.5, label=s)
        if f in LOG_X:
            ax.set_xscale("symlog", linthresh=1)
        ax.set_title(f, color=GROUP_COLORS[FEATURES[f][0]])
        ax.set_ylim(bottom=0)
    for ax in list(axs.flat)[len(feats):]:
        ax.axis("off")
    axs[0, 0].set_ylabel(_ylabel(label))
    axs[0, 0].legend()
    fig.suptitle(f"{label} vs its most relevant features: bullet vs blitz vs classical", fontsize=11,
                 fontweight="bold", color=INK, y=1.0)
    fig.tight_layout()
    return _save(fig, out, "Bins are computed per speed (clocks live on different scales). Clock-like x-axes are log scale.")


def plot_clock_in_position(data: dict[str, pd.DataFrame], label: str, out: Path) -> Path:
    """Raw blunder-vs-clock curves hide time pressure: low-clock positions are often already
    decided (and you cannot lose 20 points from a lost position). Hold win% fixed instead."""
    raw = LABELS[label][0]
    edges = [0, 5, 10, 20, 30, 60, 120, 300, 600, np.inf]
    names = ["<5s", "5-10s", "10-20s", "20-30s", "30-60s", "1-2m", "2-5m", "5-10m", "10m+"]
    bands = [(20, 35), (35, 50), (50, 65), (65, 80)]
    colors = ["#9ecae1", "#4292c6", "#eb6834", RED]
    fig, axs = plt.subplots(1, len(data), figsize=(15, 4), sharey=True)
    for ax, (s, m) in zip(axs, data.items()):
        d = m[m[raw].notna() & (m["ply"] >= 20)]  # the opening is full-clock AND near-blunder-free: drop it
        d = d.assign(cb=pd.cut(d["clock_self"], edges, labels=names, right=False))
        for (lo, hi), c in zip(bands, colors):
            q = d[(d["wp_self"] >= lo) & (d["wp_self"] < hi)]
            t = q.groupby("cb", observed=True)[raw].agg(["sum", "count"])
            t = t[t["count"] >= 150]
            l, h = wilson(t["sum"], t["count"])
            xs = [names.index(i) for i in t.index]
            ax.fill_between(xs, 100 * l, 100 * h, color=c, alpha=0.12, lw=0)
            ax.plot(xs, 100 * t["sum"] / t["count"], color=c, marker="o", ms=3, label=f"win% {lo}-{hi}")
        all_ = d[d["wp_self"].between(20, 80, inclusive="left")].groupby("cb", observed=True)[raw].agg(["mean", "count"])
        all_ = all_[all_["count"] >= 150]
        ax.plot([names.index(i) for i in all_.index], 100 * all_["mean"], color=INK, ls="--", lw=1.2, label="all 20-80")
        ax.set_xticks(range(len(names)), names, rotation=45)
        ax.invert_xaxis()
        ax.set_title(s, color=COLORS[s])
        ax.set_xlabel("clock_self (more time ← → less time)")
        ax.set_ylim(bottom=0)
    axs[0].set_ylabel(f"% {label}")
    axs[0].legend()
    fig.suptitle(f"Time pressure inside fixed win% bands: {label}", fontsize=11, fontweight="bold", color=INK, y=1.02)
    fig.tight_layout()
    return _save(fig, out, "Only contested positions (20-80% win chance, where a blunder is possible) after the opening "
                           "(ply ≥ 20). Points with < 150 moves hidden. 95% Wilson bands.")


# --------------------------------------------------------------------------- #
def run_all(data: dict[str, pd.DataFrame], out: Path, log=print) -> dict[str, list[str]]:
    style()
    data = {s: prepare(m) for s, m in data.items()}
    rank = ranking(data, log=log)
    corr = feature_corr(data)
    out.mkdir(parents=True, exist_ok=True)
    rank.to_csv(out / "feature_ranking.csv", index=False)
    plot_redundancy(corr, out / "feature_redundancy.png")
    picks = {}
    for label in LABELS:
        d = out / label
        keep = recommend(rank, corr, label)
        picks[label] = keep
        plot_ranking(rank, label, d / "ranking.png")
        (d / "ranking.md").write_text(ranking_md(rank, label, keep), encoding="utf-8")
        shown = keep + [f for f in ("clock_self", "elo_self") if f not in keep]  # always show clock + rating
        for s, m in data.items():
            plot_by_elo(m, s, label, shown, d / f"{s}.png")
        plot_speeds(data, label, shown, d / "speeds.png")
        if label != "think_time":
            plot_clock_in_position(data, label, d / "clock_in_position.png")
        log(f"  {label}: {', '.join(keep)}")
    return picks
