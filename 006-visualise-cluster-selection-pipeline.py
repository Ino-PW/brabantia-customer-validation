"""
Stage 006 - Visualise cluster count selection
================================================
Reads results/cluster_selection.csv (output of
005-cluster-selection-pipeline.py) and plots the silhouette score against
number of clusters (k) per country - the elbow plot used to choose your
per-country entries in the config.GMM_N_COMPONENTS dict before running
010-gmm-pipeline.py.

Fixes vs. the original visualisation script this replaced:
- `import matplotlib as plt` -> `import matplotlib.pyplot as plt`
  (the bare `matplotlib` module has no .plot()/.title()/etc.)
- Filters correctly per country instead of reading the unfiltered
  dataframe on every loop iteration
- Saves figures to disk (results/figures/) instead of only calling
  plt.show(), closing each figure afterwards so plots don't bleed into
  each other across countries
- Plots the real k-sweep from stage 005, not stats.csv (020's output),
  which only ever described a single already-chosen segmentation and was
  never a k-sweep in the first place

Output
------
- results/figures/cluster_selection_{land}.png
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd

import config
from logging_utils import get_logger

log = get_logger("006-visualise")


def run(landen: list[str] | None = None) -> None:
    landen = landen if landen is not None else config.LANDEN

    if not config.CLUSTER_SELECTION_OUTPUT.exists():
        raise FileNotFoundError(
            f"{config.CLUSTER_SELECTION_OUTPUT} not found - run 005-cluster-selection-pipeline.py first."
        )

    df = pd.read_csv(config.CLUSTER_SELECTION_OUTPUT)

    required_cols = {config.LAND_COL, config.CLUSTER_SELECTION_N_CLUSTERS_COL, config.CLUSTER_SELECTION_SILHOUETTE_COL}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"{config.CLUSTER_SELECTION_OUTPUT} is missing expected column(s): {missing}")

    for country in landen:
        land_df = df[df[config.LAND_COL] == country].sort_values(config.CLUSTER_SELECTION_N_CLUSTERS_COL)

        if land_df.empty:
            log.warning("No rows found for %s in %s, skipping.", country, config.CLUSTER_SELECTION_OUTPUT)
            continue

        fig, ax = plt.subplots()
        ax.plot(
            land_df[config.CLUSTER_SELECTION_N_CLUSTERS_COL],
            land_df[config.CLUSTER_SELECTION_SILHOUETTE_COL],
            marker="o",
        )
        ax.set_title(f"Cluster count selection - {country}")
        ax.set_xlabel("Number of clusters (k)")
        ax.set_ylabel("Silhouette score")
        ax.set_xticks(land_df[config.CLUSTER_SELECTION_N_CLUSTERS_COL])

        out_path = config.FIGURES_DIR / f"cluster_selection_{country}.png"
        fig.savefig(out_path, dpi=150, bbox_inches="tight")
        plt.close(fig)

        log.info("Saved %s", out_path)


if __name__ == "__main__":
    run()
