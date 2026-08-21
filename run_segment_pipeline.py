"""
040 - Segment overview stage
=============================
Reads the stats stage output (config.STATS_OUTPUT) and produces:

  1. A segment-size summary (counts + % of total)
  2. A key-metric comparison table across segments
  3. A category comparison table across segments
  4. A log-scale bar chart of segment sizes
  5. Small-multiples bar charts comparing key/category metrics across segments

Like every other stage, all paths and column names come from config.py -
no CLI arguments. Run directly:

    python 040-segment-overview.py
"""

from pathlib import Path

import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import config

# --------------------------------------------------------------------------
# Metrics to compare, derived from config.GMM_FEATURE_COLS so this stage
# stays in sync automatically if the feature list changes.
# --------------------------------------------------------------------------
CATEGORY_METRICS = [
    c for c in config.GMM_FEATURE_COLS
    if c.startswith("TOTAL_") and c not in ("TOTAL_PRODUCTS_IN_ORDER", "TOTAL_ORDERLINE_SALES")
]
KEY_METRICS = [c for c in config.GMM_FEATURE_COLS if c not in CATEGORY_METRICS]

OUTPUT_DIR = Path("segment_overview")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_stats() -> pd.DataFrame:
    if not config.STATS_OUTPUT.exists():
        raise FileNotFoundError(
            f"Stats file not found at {config.STATS_OUTPUT}. Run 020-stats first."
        )
    df = pd.read_csv(config.STATS_OUTPUT)
    if config.SEGMENT_COL not in df.columns:
        raise ValueError(f"Expected a '{config.SEGMENT_COL}' column in {config.STATS_OUTPUT}.")
    return df.sort_values(config.SEGMENT_COL).reset_index(drop=True)


def segment_size_summary(df: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in [config.SEGMENT_COL, "n_points", "pct_of_total"] if c in df.columns]
    return df[cols].copy()


def key_metric_comparison(df: pd.DataFrame, metrics: list[str]) -> pd.DataFrame:
    mean_cols = {m: f"{m}_mean" for m in metrics if f"{m}_mean" in df.columns}
    missing = [m for m in metrics if f"{m}_mean" not in df.columns]
    if missing:
        print(f"[warn] skipping metrics not found in {config.STATS_OUTPUT.name}: {missing}")

    out = df[[config.SEGMENT_COL] + list(mean_cols.values())].copy()
    out = out.rename(columns={v: k for k, v in mean_cols.items()})
    return out.set_index(config.SEGMENT_COL).round(2)


def silhouette_summary(df: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in df.columns if "silhouette" in c.lower()]
    if not cols:
        return pd.DataFrame()
    return df[[config.SEGMENT_COL] + cols].round(3)


def plot_segment_sizes(df: pd.DataFrame, outpath) -> None:
    d = df.sort_values(config.SEGMENT_COL, ascending=False)
    fig, ax = plt.subplots(figsize=(7, 0.6 * len(d) + 1.5))
    ax.barh(d[config.SEGMENT_COL].astype(str), d["n_points"], color="#2a78d6")
    ax.set_xscale("log")
    ax.set_xlabel("Customers (log scale)")
    ax.set_ylabel("Segment")
    ax.set_title("Segment size")
    for y, (n, pct) in enumerate(zip(d["n_points"], d.get("pct_of_total", [None] * len(d)))):
        label = f"{n:,}" + (f"  ({pct:.2f}%)" if pct is not None else "")
        ax.text(n * 1.05, y, label, va="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(outpath, dpi=150)
    plt.close(fig)


def plot_metric_comparison(comparison: pd.DataFrame, title: str, outpath) -> None:
    metrics = comparison.columns.tolist()
    if not metrics:
        return
    ncols = min(3, len(metrics))
    nrows = (len(metrics) + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(4 * ncols, 3 * nrows))
    axes = axes.flatten() if len(metrics) > 1 else [axes]

    for ax, metric in zip(axes, metrics):
        vals = comparison[metric]
        ax.bar(vals.index.astype(str), vals.values, color="#2a78d6")
        ax.set_title(metric, fontsize=10)
        ax.set_xlabel("Segment", fontsize=8)
        ax.set_ylabel("Mean value per segment", fontsize=8)
        ax.tick_params(labelsize=8)

    for ax in axes[len(metrics):]:
        ax.axis("off")

    fig.suptitle(title, fontsize=12)
    fig.tight_layout()
    fig.savefig(outpath, dpi=150)
    plt.close(fig)


def run_for_subset(df: pd.DataFrame, outdir, label: str) -> None:
    outdir.mkdir(parents=True, exist_ok=True)

    sizes = segment_size_summary(df)
    comparison = key_metric_comparison(df, KEY_METRICS)
    categories = key_metric_comparison(df, CATEGORY_METRICS)
    silhouette = silhouette_summary(df)

    print(f"\n=== [{label}] Segment sizes ===")
    print(sizes.to_string(index=False))

    print(f"\n=== [{label}] Key metric comparison (mean per segment) ===")
    print(comparison.to_string())

    print(f"\n=== [{label}] Category comparison (mean per segment) ===")
    print(categories.to_string())

    if not silhouette.empty:
        print(f"\n=== [{label}] Silhouette metrics ===")
        print(silhouette.to_string(index=False))

    plot_segment_sizes(df, outdir / "segment_sizes.png")
    plot_metric_comparison(comparison, "Average value by segment", outdir / "key_metric_comparison.png")
    plot_metric_comparison(categories, "Average value by segment", outdir / "category_comparison.png")

    sizes.to_csv(outdir / "segment_sizes.csv", index=False)
    comparison.to_csv(outdir / "key_metric_comparison.csv")
    categories.to_csv(outdir / "category_comparison.csv")
    if not silhouette.empty:
        silhouette.to_csv(outdir / "silhouette.csv", index=False)

    print(f"[{label}] saved to: {outdir.resolve()}")


def run() -> None:
    df = load_stats()

    if config.LAND_COL in df.columns and df[config.LAND_COL].nunique() > 1:
        for land, sub in df.groupby(config.LAND_COL):
            run_for_subset(sub.reset_index(drop=True), OUTPUT_DIR / land, land)
    else:
        run_for_subset(df, OUTPUT_DIR, "all")


if __name__ == "__main__":
    run()