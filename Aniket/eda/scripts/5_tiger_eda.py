"""Step 5 (Tiger): the same EDA as 3_eda.py on the Tiger games, with the Stockfish features added -> reports_tiger/

  python scripts/5_tiger_eda.py

Same reports as reports/, for each label (think_time, blunder, blunder_next5):
  reports_tiger/<label>/ranking.png + ranking.md   every feature's strength (eta), overall and by Elo band
  reports_tiger/<label>/blitz.png                  label vs the top features and every sf_* one, one line per Elo band
  reports_tiger/<label>/clock_in_position.png      (blunder labels) time pressure at fixed win%
and reports_tiger/feature_ranking.csv, reports_tiger/feature_redundancy.png, plus
  reports_tiger/stockfish_summary.md               where each sf_* feature ranks, and what it overlaps with
Features: the 23 of FEATURE_SET.md plus the sf_* Stockfish ones (oracle/tiger.py). The database holds blitz only,
so there is no speeds.png.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

from oracle.config import DATA, ELO_BANDS, LABELS, ROOT  # noqa: E402
from oracle.eda import feature_corr, prepare, run_all  # noqa: E402
from oracle.features import FEATURES  # noqa: E402
from oracle.tiger import SF_FEATURES  # noqa: E402

OUT = ROOT / "reports_tiger"


def summary(m: pd.DataFrame, picks: dict[str, list[str]]) -> str:
    """One table per label: each Stockfish feature's rank among all features, and its closest existing feature."""
    rank = pd.read_csv(OUT / "feature_ranking.csv")
    corr = feature_corr({"blitz": prepare(m)}, list(FEATURES) + list(SF_FEATURES))
    lines = ["# Stockfish features vs the FEATURE_SET.md features (Tiger blitz games)", "",
             f"{m['game_id'].nunique():,} games, {len(m):,} moves. eta = correlation ratio (0-1), rho = Spearman "
             "(sign = direction), 'inside Elo bands' = mean eta within each rating band. 'closest existing feature' = "
             "the FEATURE_SET.md feature with the largest |Spearman rho| to it (>= 0.8 = near-duplicate).", ""]
    for label in LABELS:
        r = rank[rank["label"] == label].set_index("feature")
        order = list(r["eta"].sort_values(ascending=False).index)
        lines += [f"## {label}", "", f"Top 8 (no near-duplicates): **{', '.join(picks[label])}**", "",
                  "| feature | rank (of %d) | eta | eta inside Elo bands | rho | closest existing feature |" % len(order),
                  "|---|---:|---:|---:|---:|---|"]
        for f in SF_FEATURES:
            x = r.loc[f]
            near = corr.loc[f, list(FEATURES)].abs().idxmax()
            band = x[[f"eta_{b}" for b in ELO_BANDS]].mean()
            lines.append(f"| `{f}` | {order.index(f) + 1} | {x['eta']:.3f} | {band:.3f} | {x['rho']:+.3f} | "
                         f"`{near}` ({corr.loc[f, near]:+.2f}) |")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    t0 = time.time()
    p = DATA / "tiger" / "moves.parquet"
    if not p.exists():
        raise SystemExit(f"{p} not found. Run scripts/4_tiger_fetch.py first.")
    m = pd.read_parquet(p)
    print(f"tiger blitz: {m['game_id'].nunique():,} games, {m['blunder'].notna().sum():,} labelled moves")
    picks = run_all({"blitz": m}, OUT, log=lambda msg: print(f"{msg}  ({time.time() - t0:.0f}s)"),
                    features={**FEATURES, **SF_FEATURES}, also_show=tuple(SF_FEATURES))
    print("\nrecommended features (top 8, no near-duplicates):")
    for label, feats in picks.items():
        print(f"  {label:13s} {', '.join(feats)}")
    text = summary(m, picks)
    (OUT / "stockfish_summary.md").write_text(text, encoding="utf-8")
    print("\n" + text)


if __name__ == "__main__":
    main()
