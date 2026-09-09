"""
Stage 005 - Cluster count selection
=====================================
Runs BEFORE 010-gmm-pipeline.py, directly on the raw input data - it does
NOT depend on 010 having run. For each country, fits a GMM for a range of
cluster counts (config.CLUSTER_SELECTION_K_MIN..K_MAX) and scores each with
the silhouette score (higher is better, range -1 to 1), plus BIC/AIC when
the underlying model exposes them.

The point: know how many segments make sense PER COUNTRY before spending
time on the full production fit and everything downstream of it.

This does NOT automatically update config.GMM_N_COMPONENTS - there's no
single "correct" answer a script should pick for you (silhouette, BIC, and
business interpretability often disagree). Run this stage, run
006-visualise-cluster-selection-pipeline.py to plot the elbow curves, look
at results/cluster_selection.csv, then edit the config.GMM_N_COMPONENTS
dict in config.py with your chosen k per country before running
010-gmm-pipeline.py.

Output
------
- results/cluster_selection.csv   (land, n_clusters, silhouette_score, bic*, aic*)

* bic/aic columns are only included if the tgmm GaussianMixture exposes
  .bic()/.aic() methods; if not, those columns are simply absent and you
  can rely on the silhouette score alone.

Requires: pandas, torch, tgmm, scikit-learn
"""

from __future__ import annotations

import pandas as pd
import torch
from sklearn.metrics import silhouette_score, davies_bouldin_score, calinski_harabasz_score
from sklearn.preprocessing import StandardScaler
from tgmm import ClusteringMetrics, GaussianMixture
from sklearn.decomposition import PCA

import config
from data_loading import load_and_clean, prepare_features
from logging_utils import get_logger

log = get_logger("005-cluster-selection")


def _evaluate_k(x_tensor, x_scaled, k: int, covariance_type) -> dict:
    gmm = GaussianMixture(
        n_components=k,
        covariance_type= covariance_type,
        init_means="kmeans",
        n_init=config.CLUSTER_SELECTION_N_INIT,
        random_state=config.CLUSTER_SELECTION_RANDOM_STATE,
        reg_covar=1e-4,
    )
    gmm.fit(x_tensor)
    labels = gmm.predict(x_tensor)

    n_unique_labels = len(set(labels))
    if n_unique_labels < 2:
        log.warning(
            "k=%d collapsed to %d actual cluster(s) (empty components); "
            "silhouette score is undefined for this k, recording NaN.",
            k, n_unique_labels,
        )
        sil = float("nan")
    else:
        sample_size = config.CLUSTER_SELECTION_SILHOUETTE_SAMPLE_SIZE
        sample_size = min(sample_size, len(x_scaled)) if sample_size else None
        sil = silhouette_score(
            x_scaled, labels,
            sample_size=sample_size,
            random_state=config.CLUSTER_SELECTION_RANDOM_STATE,
        )
        davies_bouldin = davies_bouldin_score(x_scaled, labels)
        calinski_harabasz = calinski_harabasz_score(x_scaled, labels)

    result = {config.COVARIANCE:covariance_type, config.CLUSTER_SELECTION_N_CLUSTERS_COL: k, config.CLUSTER_SELECTION_SILHOUETTE_COL: sil,
              config.CLUSTER_SELECTION_N_DAVIES_BOULDIN:k, config.CLUSTER_SELECTION_DAVIES_BOULDIN: davies_bouldin,
              config.CLUSTER_SELECTION_N_CALINKSI_HARABASZ:k, config.CLUSTER_SELECTION_CALINKSI_HARABASZ: calinski_harabasz, config.INIT_SETUP:gmm.best_random_state_}

    # BIC/AIC: tgmm doesn't expose these as instance methods on GaussianMixture -
    # they live on ClusteringMetrics as static functions keyed off lower_bound_.
    lower_bound = getattr(gmm, "lower_bound_", None)
    if lower_bound is not None:
        try:
            result["bic"] = ClusteringMetrics.bic_score(
                lower_bound, x_tensor.detach().cpu(), n_components=k,
                covariance_type=gmm.covariance_type,
            )
            result["aic"] = ClusteringMetrics.aic_score(
                lower_bound, x_tensor.detach().cpu(), n_components=k,
                covariance_type=gmm.covariance_type,
            )
        except Exception as exc:  
            log.debug("Could not compute bic/aic for k=%d: %s", k, exc)

    return result


def run(landen: list[str], covariance: list[str], combine_countries: bool = False, recluster: bool = False, recluster_path: str = None) -> pd.DataFrame:
    """
    Parameters
    ----------
    landen : list[str]
        Countries to include. Defaults to config.LANDEN when None.
    covariance : list[str]
        Covariance types to sweep (e.g. from config.COVARIANCE_TYPE).
    combine_countries : bool, default False
        - False (default, original behaviour): loop over `landen` and fit a
          separate GMM sweep PER country - i.e. each country gets its own
          PCA and its own k=K_MIN..K_MAX silhouette/BIC/AIC curve.
        - True: pool all rows from every country in `landen` into a single
          dataset and run ONE PCA + ONE k-sweep across all of them combined.
          Useful when you want a single cross-country segmentation instead
          of per-country segments. The resulting rows in
          results/cluster_selection.csv and the PCA outputs are labelled
          with the joined country codes (e.g. "DE+FR+NL") instead of a
          single country, and the original per-row country is preserved in
          a `config.COUNTRY_COL` column in the PCA scores output so you can
          still inspect cluster composition by country afterwards.
    """
    landen = landen if landen is not None else config.LANDEN
    
    country_specific_recluster = {}
    if recluster and recluster_path is not None:
        log.info("Reclustering on the majority cluster from %s", recluster_path)
        file_name = recluster_path.split('/')[-1]
        stats_path = config.RESULTS_DIR / file_name.replace("cluster", "stats")
        stats_df = pd.read_csv(stats_path)
        for land in landen:
            land_stats = stats_df[land].sort_values(by='n_points', ascending=False)
            majority_cluster = land_stats.iloc[0]["segment"]
            country_specific_recluster[land] = majority_cluster
            log.info("Country: %s, Majority Cluster: %s", land, majority_cluster)

        df = load_and_clean(recluster_path, country_specific_recluster)
        
    else:
        log.info("Loading and cleaning data from %s", config.GMM_INPUT_PATH)
        df = load_and_clean(config.GMM_INPUT_PATH)

    log.info("Data loaded: %d rows, %d columns.", len(df), len(df.columns))

    # Each "group" is (label_used_for_output_rows, list_of_country_codes_in_it).
    # Default mode: one group per country. Combined mode: a single group
    # containing every country in `landen`, labelled by joining their codes.
    if combine_countries:
        groups = [("+".join(sorted(landen)), list(landen))]
    else:
        groups = [(country, [country]) for country in landen]

    all_rows = []
    all_pca_scores = []
    all_pca_loadings = []
    for covariance_type in covariance:
        for group_label, countries_in_group in groups:

            log.info(f"Running with the following Covariance: '{covariance_type}' out of the possible {config.COVARIANCE_TYPE}")

            df_country = df[df[config.COUNTRY_COL].isin(countries_in_group)]

            if df_country.empty:
                log.warning("No rows found for %s, skipping.", group_label)
                continue

            df_features = prepare_features(df_country)
            log.info(
                "=== %s: sweeping k=%d..%d over %d rows, %d features ===",
                group_label, config.CLUSTER_SELECTION_K_MIN, config.CLUSTER_SELECTION_K_MAX,
                len(df_features), df_features.shape[1],
            )
            if combine_countries:
                log.info(
                    "=== %s: combined mode - %d countries pooled into one fit (%s) ===",
                    group_label, len(countries_in_group), ", ".join(countries_in_group),
                )

            scaler = StandardScaler()
            numeric_scaled = pd.DataFrame(
                scaler.fit_transform(df_features),
                columns=df_features.columns,
                index=df_features.index,
            )

            if  config.PCA_N_COMPONENTS is None or config.PCA_N_COMPONENTS >= 1:
                pca = PCA(n_components = len(df_features.columns))
                log.info(
                    "=== %s: config.PCA_N_COMPONENTS = %d and is >= 1 or None, so PCA will keep all features ===",
                    group_label, config.PCA_N_COMPONENTS
                )
            elif config.PCA_N_COMPONENTS < 1:
                pca = PCA(n_components = config.PCA_N_COMPONENTS)
                log.info(
                    "=== %s: config.PCA_N_COMPONENTS = %d and is < 1, so PCA will keep only the specified number of components ===",
                    group_label, config.PCA_N_COMPONENTS
                )
                
            pca_scores = pca.fit_transform(numeric_scaled)

            pca_df = pd.DataFrame(
                pca_scores,
                columns=[f"PC{i + 1}" for i in range(pca.n_components_)],
                index=numeric_scaled.index,
            )
            pca_df[config.LAND_COL] = group_label
            pca_df[config.COVARIANCE] = covariance_type
            if combine_countries:
                # Preserve which actual country each pooled row came from,
                # since config.LAND_COL now holds the combined group label.
                pca_df[config.COUNTRY_COL] = df_country.loc[numeric_scaled.index, config.COUNTRY_COL].values
            all_pca_scores.append(pca_df)

            log.info(
                "%s: PCA reduced %d features to %d components (%.1f%% variance explained).",
                group_label, numeric_scaled.shape[1], pca.n_components_,
                100 * pca.explained_variance_ratio_.sum(),
            )

            # Loadings: how much each ORIGINAL feature contributes to each
            # retained component. Use this (weighted by explained_variance_ratio_
            # below) to spot features that barely show up anywhere - candidates
            # to drop from prepare_features() for future runs.
            loadings_df = pd.DataFrame(
                pca.components_.T,
                columns=[f"PC{i + 1}" for i in range(pca.n_components_)],
                index=numeric_scaled.columns,
            )
            loadings_df[config.LAND_COL] = group_label
            loadings_df[config.COVARIANCE] = covariance_type
            loadings_df["feature"] = loadings_df.index
            for i in range(pca.n_components_):
                loadings_df[f"PC{i + 1}_explained_variance_ratio"] = pca.explained_variance_ratio_[i]
            all_pca_loadings.append(loadings_df.reset_index(drop=True))

            # Clustering runs on the PCA-reduced representation rather than the
            # raw standardized features - denser, decorrelated components tend
            # to give GMM covariance estimation an easier time in high-dim cases.
            x_scaled = pca_scores

            device = "cuda" if torch.cuda.is_available() else "cpu"
            x_tensor = torch.tensor(x_scaled, dtype=torch.float32, device=device)

            for k in range(config.CLUSTER_SELECTION_K_MIN, config.CLUSTER_SELECTION_K_MAX + 1):
                try:
                    if len(df_features) <= k:
                        log.warning("Skipping k=%d for %s: fewer rows (%d) than clusters.", k, group_label, len(df_features))
                        continue

                    log.info("%s: fitting k=%d...", group_label, k)
                    row = _evaluate_k(x_tensor, x_scaled, k, covariance_type)
                    row[config.LAND_COL] = group_label
                    all_rows.append(row)

                except Exception as e:
                    log.warning(f"{group_label} in cluster {k} with covariance type {covariance_type} led to {e}") 

    if recluster and recluster_path is not None:
        log.info("Reclustering cluster selection completed. Saving results to %s", config.RECLUSTER_CLUSTER_SELECTION_OUTPUT)
        results_df = pd.DataFrame(all_rows)
        results_df.to_csv(config.RECLUSTER_CLUSTER_SELECTION_OUTPUT, index=False)
        log.info("Saved %s", config.RECLUSTER_CLUSTER_SELECTION_OUTPUT)

        if all_pca_scores:
            pca_scores_df = pd.concat(all_pca_scores)
            pca_scores_df.to_csv(config.RECLUSTER_PCA_SCORES_OUTPUT, index=True)
            log.info("Saved %s", config.RECLUSTER_PCA_SCORES_OUTPUT)

        if all_pca_loadings:
            pca_loadings_df = pd.concat(all_pca_loadings, ignore_index=True)
            pca_loadings_df.to_csv(config.RECLUSTER_PCA_LOADINGS_OUTPUT, index=False)
            log.info(
                "Saved %s - inspect this to see which original features "
                "barely contribute to any retained component (drop candidates).",
                config.RECLUSTER_PCA_LOADINGS_OUTPUT,
            )
        _log_recommendations(results_df)

    else:    
        results_df = pd.DataFrame(all_rows)
        results_df.to_csv(config.CLUSTER_SELECTION_OUTPUT, index=False)
        log.info("Saved %s", config.CLUSTER_SELECTION_OUTPUT)

        if all_pca_scores:
            pca_scores_df = pd.concat(all_pca_scores)
            pca_scores_df.to_csv(config.PCA_SCORES_OUTPUT, index=True)
            log.info("Saved %s", config.PCA_SCORES_OUTPUT)

        if all_pca_loadings:
            pca_loadings_df = pd.concat(all_pca_loadings, ignore_index=True)
            pca_loadings_df.to_csv(config.PCA_LOADINGS_OUTPUT, index=False)
            log.info(
                "Saved %s - inspect this to see which original features "
                "barely contribute to any retained component (drop candidates).",
                config.PCA_LOADINGS_OUTPUT,
            )
        _log_recommendations(results_df)

    return results_df

def _log_recommendations(results_df: pd.DataFrame) -> None:
    best_per_country = (
        results_df.dropna(subset=[config.CLUSTER_SELECTION_SILHOUETTE_COL])
        .sort_values(config.CLUSTER_SELECTION_SILHOUETTE_COL, ascending=False)
        .groupby(config.LAND_COL)
        .first()
    )

    log.info("=" * 60)
    log.info("Best silhouette score per country (highest isn't automatically")
    log.info("'correct' - check the elbow plot too, a slightly lower k is")
    log.info("often more interpretable for a business audience):")
    for country, row in best_per_country.iterrows():
        log.info(
            "  %-4s k=%d  silhouette=%.4f",
            country, int(row[config.CLUSTER_SELECTION_N_CLUSTERS_COL]), row[config.CLUSTER_SELECTION_SILHOUETTE_COL],
        )
    log.info("=" * 60)
    log.info(
        "Next: run 006-visualise-cluster-selection-pipeline.py for elbow plots, "
        "then edit the GMM_N_COMPONENTS dict in config.py with your chosen k per "
        "country before running 010-gmm-pipeline.py."
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--combine-countries",
        action="store_true",
        help=(
            "Pool all countries in config.LANDEN into a single k-sweep "
            "instead of running one sweep per country."
        ),
    )
    parser.add_argument(
        "--recluster", 
        action="store_true",
        help=("Do new clustering on the majority cluster. "
              "This functionality only works after previous clustering has been done. "
              "It will create a new cluster_selection csv file with the reclustered results."),
    )
    parser.add_argument(
        "--recluster-path", type=str, default=None,
        help=("Path to the CSV file containing the results that have to be reclustered.")
    )
    args = parser.parse_args()

    run(config.LANDEN, config.COVARIANCE_TYPE, combine_countries=args.combine_countries, recluster=args.recluster, recluster_path=args.recluster_path)