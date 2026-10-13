"""
Stage 020 - Cluster statistics
===============================
Reads each country's segmented file (output of 010-gmm-pipeline) and
computes per-cluster statistics (e.g. silhouette scores, feature summaries).

Renumbered from 030 -> 020: this stage depends only on 010's output, not
on PCA (030). Keeping it directly after 010 makes the numbering reflect the
real data flow, and means 040-visualise (which reads this stage's output)
follows immediately after it.

The cluster-statistics helpers below used to live in a separate utils.py.
That module isn't part of this package and had to be supplied separately,
so 020 was the only stage in the pipeline that couldn't run standalone out
of the box. utils.py has been removed and its functions (previously
compute_cluster_statistics / flatten_cluster_statistics, plus the smaller
helpers they called) are now defined directly in this file - it's the only
stage that ever used them, so nothing is lost by inlining them here.

Output
------
- results/stats.csv          (per-country mode, default)
- results/stats_combined.csv (combine_countries=True)

Requires: pandas, numpy, scikit-learn
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import (
    calinski_harabasz_score,
    davies_bouldin_score,
    silhouette_samples,
    silhouette_score,
)

import config
from logging_utils import get_logger

log = get_logger("020-stats")


# --------------------------------------------------------------------------
# Cluster-statistics helpers (formerly utils.py)
# --------------------------------------------------------------------------

def compute_descriptive_stats(df: pd.DataFrame, feature_cols: list, label_col: str) -> pd.DataFrame:
    """
    Per-cluster descriptive statistics: count, mean, std, min, max, median
    for each numeric feature.

    Returns a DataFrame with a MultiIndex column (feature, stat).
    """
    grouped = df.groupby(label_col)[feature_cols]
    stats = grouped.agg(["count", "mean", "std", "min", "median", "max"])
    return stats


def compute_quality_metrics(df: pd.DataFrame, feature_cols: list, label_col: str) -> dict:
    """
    Overall cluster-quality metrics (require >= 2 clusters, and no noise-only
    labels like -1 dominating the data if you're using DBSCAN/HDBSCAN).

    - Silhouette score: [-1, 1], higher is better (well-separated clusters)
    - Calinski-Harabasz index: higher is better (dense, well-separated clusters)
    - Davies-Bouldin index: lower is better (0 = perfect separation)
    """
    X = df[feature_cols].values
    labels = df[label_col].values

    n_unique = len(np.unique(labels))
    if n_unique < 2:
        raise ValueError("Need at least 2 clusters to compute quality metrics.")

    metrics = {
        "silhouette_score": silhouette_score(X, labels),
        "calinski_harabasz_score": calinski_harabasz_score(X, labels),
        "davies_bouldin_score": davies_bouldin_score(X, labels),
    }
    return metrics


def compute_per_cluster_silhouette(df: pd.DataFrame, feature_cols: list, label_col: str) -> pd.DataFrame:
    """
    Average silhouette width *per cluster* (not just the overall average).
    Useful for spotting which specific clusters are poorly separated.
    """
    X = df[feature_cols].values
    labels = df[label_col].values

    sample_silhouette = silhouette_samples(X, labels)
    temp = df[[label_col]].copy()
    temp["silhouette"] = sample_silhouette

    per_cluster = temp.groupby(label_col)["silhouette"].agg(["mean", "std", "min", "max"])
    per_cluster.columns = [f"silhouette_{c}" for c in per_cluster.columns]
    return per_cluster


def compute_cluster_sizes(df: pd.DataFrame, label_col: str) -> pd.DataFrame:
    """Cluster sizes and their share of the total dataset."""
    sizes = df[label_col].value_counts().sort_index()
    sizes_df = sizes.to_frame("n_points")
    sizes_df["pct_of_total"] = (sizes_df["n_points"] / len(df) * 100).round(2)
    return sizes_df


def compute_cluster_statistics(df: pd.DataFrame, feature_cols: list, label_col: str = "cluster") -> dict:
    """
    Convenience wrapper that runs everything and returns a dict of results:
        {
            "sizes": DataFrame,
            "descriptive": DataFrame,
            "per_cluster_silhouette": DataFrame,
            "overall_quality": dict,
        }
    """
    results = {
        "sizes": compute_cluster_sizes(df, label_col),
        "descriptive": compute_descriptive_stats(df, feature_cols, label_col),
        "per_cluster_silhouette": compute_per_cluster_silhouette(df, feature_cols, label_col),
        "overall_quality": compute_quality_metrics(df, feature_cols, label_col),
    }
    return results


def flatten_cluster_statistics(results: dict) -> pd.DataFrame:
    """
    Flattens the dict returned by compute_cluster_statistics() into a single
    DataFrame: one row per cluster, with all descriptive stats, silhouette
    stats, sizes, and overall quality metrics as columns.
    """
    sizes = results["sizes"]

    # Flatten the MultiIndex descriptive stats (feature, stat) -> "feature_stat"
    descriptive = results["descriptive"].copy()
    descriptive.columns = [f"{feat}_{stat}" for feat, stat in descriptive.columns]

    per_cluster_sil = results["per_cluster_silhouette"]

    flat = sizes.join(descriptive).join(per_cluster_sil)

    # Overall quality metrics are dataset-level, so broadcast them to every row
    for metric_name, value in results["overall_quality"].items():
        flat[f"overall_{metric_name}"] = value

    flat = flat.reset_index()  # bring the cluster label out of the index into a column
    return flat


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _load_country(country: str) -> pd.DataFrame | None:
    """Load a single country's segmented CSV. Returns None if not found."""
    input_path = config.GMM_PER_COUNTRY_TEMPLATE.format(country=country)
    try:
        df = pd.read_csv(input_path)
        df[config.LAND_COL] = country  # ensure the country column is present
        return df
    except FileNotFoundError:
        log.warning(
            "No file found for %s at %s, skipping "
            "(did stage 010 run for this country?).",
            country,
            input_path,
        )
        return None


def _resolve_feature_cols(df: pd.DataFrame, exclude_terms: list[str]) -> list[str]:
    """Return numeric columns that don't match any exclude term."""
    exclude_cols = [c for c in df.columns if any(term in c.lower() for term in exclude_terms)]
    log.info("Excluded from statistics (%d columns): %s", len(exclude_cols), exclude_cols)
    return (
        df.select_dtypes(include="number")
        .drop(columns=exclude_cols, errors="ignore")
        .columns.tolist()
    )


# --------------------------------------------------------------------------
# Stage entry point
# --------------------------------------------------------------------------

def run(
    landen: list[str] | None = None,
    exclude_terms: list[str] | None = None,
    combine_countries: bool = False,
) -> pd.DataFrame:
    """
    Parameters
    ----------
    landen : list[str] | None
        Countries to process. Defaults to ``config.LANDEN``.
    exclude_terms : list[str] | None
        Column-name substrings to exclude from feature columns.
        Defaults to ``config.EXCLUDE_TERMS``.
    combine_countries : bool, default False
        When *False* (default) statistics are computed independently for each
        country and the ``config.LAND_COL`` column identifies the source.

        When *True* all country files are concatenated first and statistics
        are computed on the combined dataset as a whole.  The cluster label
        column (``config.SEGMENT_COL``) is used as-is, so this mode assumes
        clusters are comparable across countries (e.g. they were produced by
        a single cross-country GMM run, or cluster IDs were harmonised
        beforehand).  The ``config.LAND_COL`` column is *not* added in this
        mode because the result represents all countries jointly.  Output is
        written to ``config.STATS_COMBINED_OUTPUT`` instead of
        ``config.STATS_OUTPUT``.
    """
    landen = landen if landen is not None else config.LANDEN
    exclude_terms = exclude_terms if exclude_terms is not None else config.EXCLUDE_TERMS

    # ------------------------------------------------------------------ #
    # Load all requested country files                                    #
    # ------------------------------------------------------------------ #
    country_dfs: list[pd.DataFrame] = []
    for country in landen:
        log.info("Loading %s", country)
        df = _load_country(country)
        if df is not None:
            country_dfs.append(df)

    if not country_dfs:
        raise RuntimeError(
            "No country files were processed - check that stage 010 ran successfully."
        )

    # ------------------------------------------------------------------ #
    # Combined-countries mode                                             #
    # ------------------------------------------------------------------ #
    if combine_countries:
        log.info("combine_countries=True: pooling %d country files.", len(country_dfs))
        combined_df = pd.concat(country_dfs, ignore_index=True)

        # Exclude the country-identifier column itself from numeric features
        extra_exclude = [config.LAND_COL]
        all_exclude_terms = list(exclude_terms) + [t.lower() for t in extra_exclude]
        feature_cols = _resolve_feature_cols(combined_df, all_exclude_terms)

        results = compute_cluster_statistics(combined_df, feature_cols, config.SEGMENT_COL)
        statistics_df = flatten_cluster_statistics(results)

        # Record which countries contributed and how many rows each added
        country_counts = (
            combined_df[config.LAND_COL].value_counts().sort_index().to_dict()
        )
        group_label = "+".join(sorted(landen))
        statistics_df["source_countries"] = group_label
        statistics_df["n_countries"] = len(country_dfs)
        log.info(
            "Combined dataset: %d rows from %d countries: %s",
            len(combined_df),
            len(country_dfs),
            country_counts,
        )

        output_path = config.STATS_COMBINED_OUTPUT
        statistics_df.to_csv(output_path, index=False)
        log.info("Saved %s", output_path)
        return statistics_df
    
    else:
        log.info("combine_countries=False: computing statistics per country.")
        # ------------------------------------------------------------------ #
        # Per-country mode (original behaviour)                               #
        # ------------------------------------------------------------------ #
        all_results = []
        for df in country_dfs:
            country = df[config.LAND_COL].iloc[0]
            log.info("Processing %s", country)

            feature_cols = _resolve_feature_cols(df, exclude_terms)

            results = compute_cluster_statistics(df, feature_cols, config.SEGMENT_COL)
            results_df = flatten_cluster_statistics(results)
            results_df[config.LAND_COL] = country
            all_results.append(results_df)

            log.info("Finished %s", country)

        statistics_df = pd.concat(all_results, ignore_index=True)
        log.info("Combined statistics: %d rows.", len(statistics_df))

        statistics_df.to_csv(config.STATS_OUTPUT, index=False)
        log.info("Saved %s", config.STATS_OUTPUT)

        return statistics_df


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Stage 020 - Cluster statistics")
    parser.add_argument(
        "--combine-countries",
        action="store_true",
        default=False,
        help=(
            "Pool all country files into one dataset before computing statistics "
            "(writes to config.STATS_COMBINED_OUTPUT instead of config.STATS_OUTPUT)."
        ),
    )
    args = parser.parse_args()
    run(combine_countries=args.combine_countries)