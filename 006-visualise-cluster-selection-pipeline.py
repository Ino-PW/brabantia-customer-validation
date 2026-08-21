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
- The Davies-Bouldin and Calinski-Harabasz subplots were plotting against
  columns that don't exist (`CLUSTER_SELECTION_N_DAVIES_BOULDIN` /
  `CLUSTER_SELECTION_N_CALINKSI_HARABASZ`) instead of the shared x-axis,
  `n_clusters`. All three metrics now share the same x-axis.

New in this version
--------------------
- The k-sweep in cluster_selection.csv is run across multiple GMM
  covariance types (full / tied / diag / spherical, in the `type`
  column). Each subplot now draws one line per covariance type instead
  of a single aggregate line, so you can compare model complexity vs.
  score per country.
- Added combine_countries, mirroring 005/010: if cluster_selection.csv
  was produced with countries pooled into one sweep, pass
  combine_countries=True here too so this plots that single joined-label
  group instead of failing to find per-country rows.

Output
------
- /figures/cluster_selection_{land}.png
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

import config
from logging_utils import get_logger

log = get_logger("006-visualise")

# Name of the column holding the GMM covariance_type ('full', 'tied',
# 'diag', 'spherical') in cluster_selection.csv. Defaults to the actual
# CSV column name ("type"); override via config.CLUSTER_SELECTION_COVARIANCE_TYPE_COL
# if your config.py names it differently.
COVARIANCE_TYPE_COL = getattr(config, "CLUSTER_SELECTION_COVARIANCE_TYPE_COL", "type")


def _plot_metric(ax, sub_df: pd.DataFrame, x_col: str, y_col: str, group_label: str, ylabel: str, cov_col: str | None) -> None:
    """Plot one metric onto ax, one line per covariance type if cov_col is available."""
    if cov_col and cov_col in sub_df.columns:
        for cov_type, cov_df in sub_df.groupby(cov_col):
            cov_df = cov_df.sort_values(x_col)
            ax.plot(cov_df[x_col], cov_df[y_col], marker="o", label=str(cov_type))
        ax.legend(title="covariance_type", fontsize="small")
    else:
        ax.plot(sub_df[x_col], sub_df[y_col], marker="o")

    ax.set_title(f"Cluster count selection - {group_label}")
    ax.set_xlabel("Number of clusters (k)")
    ax.set_ylabel(ylabel)
    ax.set_xticks(sorted(sub_df[x_col].unique()))


def run(landen: list[str], visualise_path: Path | None = None, combine_countries: bool = False) -> None:
    """
    Parameters
    ----------
    landen : list[str]
        Countries to plot. Defaults to config.LANDEN when None.
    visualise_path : Path | None
        Plot a specific cluster_selection CSV instead of config.CLUSTER_SELECTION_OUTPUT.
    combine_countries : bool, default False
        Must match whatever was passed to 005-cluster-selection-pipeline.py.
        - False (default): one figure per country, filtering cluster_selection.csv
          rows where `land` equals that country's code.
        - True: cluster_selection.csv was produced with all of `landen` pooled
          into one sweep, so `land` holds the joined label (e.g. "DE+FR+NL")
          instead of individual country codes - this plots that one group
          instead of looping per country.
    """
    landen = landen if landen is not None else config.LANDEN

    if not config.CLUSTER_SELECTION_OUTPUT.exists() and visualise_path is None:
        raise FileNotFoundError(
            f"{config.CLUSTER_SELECTION_OUTPUT} not found - run 005-cluster-selection-pipeline.py first."
        )
    elif visualise_path is not None:
        log.info("Using visualisation input file %s", visualise_path)
        config.CLUSTER_SELECTION_OUTPUT = visualise_path

    df = pd.read_csv(config.CLUSTER_SELECTION_OUTPUT)

    required_cols = {config.LAND_COL, config.CLUSTER_SELECTION_N_CLUSTERS_COL, config.CLUSTER_SELECTION_SILHOUETTE_COL}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"{config.CLUSTER_SELECTION_OUTPUT} is missing expected column(s): {missing}")

    cov_col = COVARIANCE_TYPE_COL if COVARIANCE_TYPE_COL and COVARIANCE_TYPE_COL in df.columns else None
    if COVARIANCE_TYPE_COL and cov_col is None:
        log.warning(
            "Configured covariance-type column %r not found in %s; falling back to single-line plots.",
            COVARIANCE_TYPE_COL,
            config.CLUSTER_SELECTION_OUTPUT,
        )

    # In combined mode there's a single group covering every country in
    # `landen`, labelled the same way 005/010 label it ("+".join(sorted(...))).
    # In default mode each country is its own group, same as before.
    if combine_countries:
        group_labels = ["+".join(sorted(landen))]
    else:
        group_labels = list(landen)

    for group_label in group_labels:
        land_df = df[df[config.LAND_COL] == group_label].sort_values(config.CLUSTER_SELECTION_N_CLUSTERS_COL)

        if land_df.empty:
            log.warning("No rows found for %s in %s, skipping.", group_label, config.CLUSTER_SELECTION_OUTPUT)
            continue

        fig, axes = plt.subplots(1, 3, figsize=(18, 5))

        _plot_metric(
            axes[0],
            land_df,
            config.CLUSTER_SELECTION_N_CLUSTERS_COL,
            config.CLUSTER_SELECTION_SILHOUETTE_COL,
            group_label,
            "Silhouette score",
            cov_col,
        )

        _plot_metric(
            axes[1],
            land_df,
            config.CLUSTER_SELECTION_N_CLUSTERS_COL,
            config.CLUSTER_SELECTION_DAVIES_BOULDIN,
            group_label,
            "Davies Bouldin score",
            cov_col,
        )

        _plot_metric(
            axes[2],
            land_df,
            config.CLUSTER_SELECTION_N_CLUSTERS_COL,
            config.CLUSTER_SELECTION_CALINKSI_HARABASZ,
            group_label,
            "Calinksi Harabasz score",
            cov_col,
        )

        fig.tight_layout()

        out_path = config.FIGURES_DIR / f"cluster_selection_{group_label}_{config.FEATURE_TAG}.png"
        fig.savefig(out_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        log.info("Saved %s", out_path)


if __name__ == "__main__":
    run()