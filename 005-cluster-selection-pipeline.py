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
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler
from tgmm import GaussianMixture

import config
from data_loading import load_and_clean, prepare_features
from logging_utils import get_logger

log = get_logger("005-cluster-selection")


def _evaluate_k(x_tensor, x_scaled, k: int) -> dict:
    gmm = GaussianMixture(
        n_components=k,
        covariance_type="diag",
        init_means="kmeans",
        n_init=config.CLUSTER_SELECTION_N_INIT,
        random_state=config.CLUSTER_SELECTION_RANDOM_STATE,
        reg_covar=1e-4,
    )
    gmm.fit(x_tensor)
    labels = gmm.predict(x_tensor).cpu().numpy()

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

    result = {config.CLUSTER_SELECTION_N_CLUSTERS_COL: k, config.CLUSTER_SELECTION_SILHOUETTE_COL: sil}

    # Optional: only recorded if tgmm's GaussianMixture actually exposes these.
    for metric_name in ("bic", "aic"):
        method = getattr(gmm, metric_name, None)
        if callable(method):
            try:
                result[metric_name] = method(x_tensor)
            except Exception as exc:  # noqa: BLE001 - diagnostic stage, log and continue
                log.debug("Could not compute %s for k=%d: %s", metric_name, k, exc)

    return result


def run(landen: list[str] | None = None) -> pd.DataFrame:
    landen = landen if landen is not None else config.LANDEN

    df = load_and_clean(config.GMM_INPUT_PATH)
    log.info("Data loaded: %d rows, %d columns.", len(df), len(df.columns))

    all_rows = []

    for country in landen:
        df_country = df[df[config.COUNTRY_COL] == country]

        if df_country.empty:
            log.warning("No rows found for %s, skipping.", country)
            continue

        df_features = prepare_features(df_country)
        log.info(
            "=== %s: sweeping k=%d..%d over %d rows, %d features ===",
            country, config.CLUSTER_SELECTION_K_MIN, config.CLUSTER_SELECTION_K_MAX,
            len(df_features), df_features.shape[1],
        )

        scaler = StandardScaler()
        x_scaled = scaler.fit_transform(df_features.values)

        device = "cuda" if torch.cuda.is_available() else "cpu"
        x_tensor = torch.tensor(x_scaled, dtype=torch.float32, device=device)

        for k in range(config.CLUSTER_SELECTION_K_MIN, config.CLUSTER_SELECTION_K_MAX + 1):
            if len(df_features) <= k:
                log.warning("Skipping k=%d for %s: fewer rows (%d) than clusters.", k, country, len(df_features))
                continue

            log.info("%s: fitting k=%d...", country, k)
            row = _evaluate_k(x_tensor, x_scaled, k)
            row[config.LAND_COL] = country
            all_rows.append(row)

    if not all_rows:
        raise RuntimeError(
            "No cluster-selection results were produced - check the input data and config.LANDEN."
        )

    results_df = pd.DataFrame(all_rows)
    results_df.to_csv(config.CLUSTER_SELECTION_OUTPUT, index=False)
    log.info("Saved %s", config.CLUSTER_SELECTION_OUTPUT)

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
    run()
