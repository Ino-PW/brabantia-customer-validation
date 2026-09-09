"""
Visualise stats CSV (output of stage 020).

Usage:
    python visualise_stats.py                          # reads results/stats*.csv
    python visualise_stats.py --input path/to/stats.csv
    python visualise_stats.py --input path/to/stats.csv --output figures/
"""

import argparse
import glob
import os

import matplotlib.gridspec as gridspec
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

COLORS = ["#2563eb", "#d97706", "#059669", "#dc2626", "#7c3aed", "#ea580c"]

CAT_COLS = [
    "TOTAL_BATHROOM_TOILET_mean",
    "TOTAL_FOOD_ENJOYMENT_mean",
    "TOTAL_WASTE_MANAGEMENT_mean",
    "TOTAL_LAUNDRY_CARING_mean",
    # "TOTAL_SERVICE_mean",
]
CAT_LABELS = ["Bathroom", "Food", "Waste", "Laundry", ]#"Service"]


def _style_ax(ax):
    ax.set_facecolor("#f8fafc")
    ax.tick_params(colors="#475569", labelsize=8)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    for spine in ["bottom", "left"]:
        ax.spines[spine].set_color("#cbd5e1")


def plot_country(sub: pd.DataFrame, land: str, output_dir: str) -> None:
    sub = sub.reset_index(drop=True)
    n = len(sub)
    colors = COLORS[:n]
    seg_labels = [f"Seg {s}" for s in sub["segment"]]
    x = np.arange(n)
    w = 0.4

    fig = plt.figure(figsize=(18, 12), facecolor="#ffffff")
    fig.suptitle(f"{land} — Cluster Statistics", fontsize=16, fontweight="bold",
                 color="#0f172a", y=0.98)
    gs = gridspec.GridSpec(3, 3, figure=fig, hspace=0.45, wspace=0.35)

    # 1. Customer size
    ax1 = fig.add_subplot(gs[0, 0])
    bars = ax1.bar(seg_labels, sub["n_points"], color=colors, width=0.6)
    for bar, pct in zip(bars, sub["pct_of_total"]):
        ax1.text(bar.get_x() + bar.get_width() / 2,
                 bar.get_height() + sub["n_points"].max() * 0.01,
                 f"{pct}%", ha="center", va="bottom", fontsize=8, color="#475569")
    ax1.set_title("Customers per segment", color="#475569", fontsize=10)

    # 2. Net sales vs orderline sales
    ax2 = fig.add_subplot(gs[0, 1])
    ax2.bar(x - w / 2, sub["NET_SALES_mean"], width=w, color="#3b82f6", label="Net Sales", alpha=0.9)
    ax2.bar(x + w / 2, sub["TOTAL_ORDERLINE_SALES_mean"], width=w, color="#f59e0b", label="Orderline", alpha=0.9)
    ax2.set_xticks(x)
    ax2.set_xticklabels(seg_labels)
    ax2.set_title("Mean sales (€)", color="#475569", fontsize=10)
    ax2.legend(fontsize=8, facecolor="#f1f5f9", labelcolor="#475569", framealpha=0.8)

    # 3. Koopkracht
    ax3 = fig.add_subplot(gs[0, 2])
    ax3.bar(seg_labels, sub["KOOPKRACHT_mean"] / 1000, color=colors)
    ax3.set_title("Avg Koopkracht (€k)", color="#475569", fontsize=10)

    # 4. Category radar
    ax4 = fig.add_subplot(gs[1, 0], polar=True)
    angles = np.linspace(0, 2 * np.pi, len(CAT_COLS), endpoint=False).tolist()
    angles += angles[:1]
    ax4.set_xticks(angles[:-1])
    ax4.set_xticklabels(CAT_LABELS, color="#475569", fontsize=8)
    ax4.set_facecolor("#f8fafc")
    ax4.spines["polar"].set_color("#cbd5e1")
    ax4.yaxis.set_tick_params(labelcolor="#94a3b8", labelsize=7)
    for i, row in sub.iterrows():
        vals = row[CAT_COLS].tolist() + [row[CAT_COLS[0]]]
        ax4.plot(angles, vals, color=colors[i], linewidth=1.5, label=f"Seg {row['segment']}")
        ax4.fill(angles, vals, color=colors[i], alpha=0.12)
    ax4.set_title("Category spend profile", color="#475569", fontsize=10, pad=14)
    ax4.legend(loc="upper right", bbox_to_anchor=(1.35, 1.15), fontsize=8,
               facecolor="#f1f5f9", labelcolor="#475569", framealpha=0.8)

    # 5. Products per order
    ax5 = fig.add_subplot(gs[1, 1])
    ax5.bar(seg_labels, sub["TOTAL_PRODUCTS_IN_ORDER_mean"], color=colors)
    ax5.set_title("Avg products per order", color="#475569", fontsize=10)

    # 6. Orders per customer
    ax6 = fig.add_subplot(gs[1, 2])
    ax6.bar(seg_labels, sub["ORDER_NUMBER_FUNCTIONAL_COUNT_mean"], color=colors)
    ax6.set_title("Avg orders per customer", color="#475569", fontsize=10)

    # 7. Per-cluster silhouette
    ax7 = fig.add_subplot(gs[2, 0])
    sil_colors = ["#059669" if v >= 0 else "#dc2626" for v in sub["silhouette_mean"]]
    ax7.bar(seg_labels, sub["silhouette_mean"], color=sil_colors)
    ax7.axhline(0, color="#94a3b8", linewidth=0.8, linestyle="--")
    ax7.set_title("Per-cluster silhouette mean", color="#475569", fontsize=10)

    # 8. Quality metrics text
    ax8 = fig.add_subplot(gs[2, 1])
    ax8.axis("off")
    ax8.set_facecolor("#f8fafc")
    ax8.text(0.5, 1.0, "Model quality metrics", ha="center", va="top",
             color="#475569", fontsize=10, transform=ax8.transAxes)
    metrics = [
        ("Overall silhouette", sub["overall_silhouette_score"].iloc[0], False),
        ("Calinski-Harabasz",  sub["overall_calinski_harabasz_score"].iloc[0], False),
        ("Davies-Bouldin",     sub["overall_davies_bouldin_score"].iloc[0], True),
    ]
    y = 0.78
    for label, val, lower_better in metrics:
        good = val < 1.0 if lower_better else val > 0.1
        color = "#059669" if good else "#dc2626"
        note = "↓ better" if lower_better else "↑ better"
        ax8.text(0.05, y, f"{label}  ({note})", color="#64748b", fontsize=9, transform=ax8.transAxes)
        ax8.text(0.95, y, f"{val:.4f}", color=color, fontsize=9,
                 fontweight="bold", ha="right", transform=ax8.transAxes)
        y -= 0.22

    # 9. 2024 vs 2025
    ax9 = fig.add_subplot(gs[2, 2])
    if "TOTAL_2024_mean" in sub.columns and "TOTAL_2025_mean" in sub.columns:
        ax9.bar(x - w / 2, sub["TOTAL_2024_mean"], width=w, color="#6366f1", label="2024", alpha=0.9)
        ax9.bar(x + w / 2, sub["TOTAL_2025_mean"], width=w, color="#ec4899", label="2025", alpha=0.9)
        ax9.set_xticks(x)
        ax9.set_xticklabels(seg_labels)
        ax9.set_title("Mean spend: 2024 vs 2025", color="#475569", fontsize=10)
        ax9.legend(fontsize=8, facecolor="#f1f5f9", labelcolor="#475569", framealpha=0.8)
    else:
        ax9.axis("off")

    for ax in [ax1, ax2, ax3, ax5, ax6, ax7, ax9]:
        _style_ax(ax)

    out_path = os.path.join(output_dir, f"stats_{land}.png")
    fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor="#ffffff")
    plt.close(fig)
    print(f"Saved {out_path}")


def run(input_path: str, output_dir: str) -> None:
    os.makedirs(output_dir, exist_ok=True)
    df = pd.read_csv(input_path)
    print(f"Loaded {input_path}: {len(df)} rows, {df['land'].nunique()} countries.")

    for land in sorted(df["land"].dropna().unique()):
        plot_country(df[df["land"] == land], land, output_dir)

    print(f"\nAll figures written to {output_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Visualise stage 020 stats CSV.")
    parser.add_argument(
        "--input", default=None,
        help="Path to stats CSV. If omitted, picks the newest results/stats*.csv.",
    )
    parser.add_argument(
        "--output", default="figures/",
        help="Directory to write PNGs into (default: figures/).",
    )
    args = parser.parse_args()

    if args.input:
        input_path = args.input
    else:
        candidates = glob.glob("results/stats*.csv")
        if not candidates:
            raise FileNotFoundError("No results/stats*.csv found. Pass --input explicitly.")
        input_path = max(candidates, key=os.path.getmtime)
        print(f"Auto-selected: {input_path}")

    run(input_path, args.output)