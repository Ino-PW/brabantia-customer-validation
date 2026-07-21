"""
Stage 010 - GMM segmentation
============================
Production fit. Loads the raw consumer table, scales it, fits a Gaussian
Mixture Model (tgmm) per country using the cluster count you chose in
config.GMM_N_COMPONENTS (see 005-cluster-selection-pipeline.py), and writes
the resulting segment labels back onto the original rows.

Run 005 (+ 006 for plots) first and fill in config.GMM_N_COMPONENTS with a
value per country before trusting this stage's output for production use -
it will warn per country if it's falling back to GMM_N_COMPONENTS_DEFAULT.

Outputs
-------
- results/consumers_{country}.csv                    (one file per country)
- results/consumers_met_segmenten_per_land.csv        (all countries combined)

Requires: pandas, scikit-learn, torch, tgmm
"""

from __future__ import annotations

import pandas as pd
import torch
from sklearn.preprocessing import StandardScaler
from tgmm import GaussianMixture

import config
from data_loading import load_and_clean, prepare_features
from logging_utils import get_logger

log = get_logger("010-gmm")


def fit_gmm_for_country(df_country: pd.DataFrame, n_components: int) -> pd.DataFrame:
    """Fit a GMM on the rows of a single country and return labels/probabilities attached."""
    df_features = prepare_features(df_country)
    log.info("Features: %s", df_features.columns.tolist())

    # Scaler is fit PER COUNTRY on purpose: comparing scaled values across
    # countries would compare countries against each other rather than
    # segmenting consumers within each country.
    scaler = StandardScaler()
    x_scaled = scaler.fit_transform(df_features.values)
    log.info("Features scaled with StandardScaler, shape: %s", x_scaled.shape)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    x_tensor = torch.tensor(x_scaled, dtype=torch.float32, device=device)
    log.info("Tensor created on device: %s", device)

    log.info("Training GMM with %d components...", n_components)
    gmm = GaussianMixture(
        n_components=n_components,
        covariance_type="diag",
        init_means="kmeans",
        n_init=10,
        random_state=0,
        reg_covar=1e-4,
    )
    gmm.fit(x_tensor)
    log.info("GMM training complete.")

    labels = gmm.predict(x_tensor).cpu().numpy()
    probs = gmm.predict_proba(x_tensor).cpu().numpy()

    df_result = df_country.copy()
    df_result["segment"] = labels

    prob_cols = [f"segment_{i}_kans" for i in range(n_components)]
    df_result[prob_cols] = probs

    log.info("Segment distribution: %s", pd.Series(labels).value_counts().to_dict())
    return df_result


def run(landen: list[str] | None = None) -> dict[str, pd.DataFrame]:
    landen = landen if landen is not None else config.LANDEN

    df = load_and_clean(config.GMM_INPUT_PATH)
    log.info("Data loaded: %d rows, %d columns.", len(df), len(df.columns))

    dfs_per_country: dict[str, pd.DataFrame] = {}
    for country in landen:
        n_components = config.get_n_components(country)
        log.info("=== Processing %s (n_components=%d) ===", country, n_components)
        df_country = df[df[config.COUNTRY_COL] == country]

        if df_country.empty:
            log.warning("No rows found for %s, skipping.", country)
            continue

        log.info("%d rows found for %s.", len(df_country), country)
        dfs_per_country[country] = fit_gmm_for_country(df_country, n_components)

    if not dfs_per_country:
        raise RuntimeError("No countries were processed - check the input data and config.LANDEN.")

    log.info("All countries processed: %s", list(dfs_per_country.keys()))

    for country, df_result in dfs_per_country.items():
        out_path = config.GMM_PER_COUNTRY_TEMPLATE.format(country=country)
        df_result.to_csv(out_path, index=False)
        log.info("Saved %s (%d rows).", out_path, len(df_result))

    df_total = pd.concat(dfs_per_country.values(), axis=0).sort_index()
    # "segment" is only unique WITHIN a country; add a globally unique id.
    df_total["segment_globaal"] = df_total[config.COUNTRY_COL] + "_" + df_total["segment"].astype(str)

    df_total.to_csv(config.GMM_COMBINED_OUTPUT, index=False)
    log.info("Saved combined output to %s (%d rows).", config.GMM_COMBINED_OUTPUT, len(df_total))

    for country, df_result in dfs_per_country.items():
        log.info("--- %s (%d rows total) ---\n%s", country, len(df_result), df_result["segment"].value_counts())

    return dfs_per_country


if __name__ == "__main__":
    run()
