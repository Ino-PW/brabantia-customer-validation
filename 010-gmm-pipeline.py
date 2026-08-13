"""
Stage 010 - GMM segmentation (+ PCA reporting, formerly stage 030)
====================================================================
Production fit. Loads the raw consumer table, scales it, runs PCA, fits a
Gaussian Mixture Model (tgmm) per country using the cluster count you chose
in config.GMM_N_COMPONENTS (see 005-cluster-selection-pipeline.py), and
writes the resulting segment labels back onto the original rows.

Run 005 (+ 006 for plots) first and fill in config.GMM_N_COMPONENTS with a
value per country before trusting this stage's output for production use -
it will warn per country if it's falling back to GMM_N_COMPONENTS_DEFAULT.

Merged with the former stage 030-pca-pipeline.py
--------------------------------------------------
030 used to re-fit its own PCA from scratch on 010's *output* (the
already-segmented combined file), on a slightly different input than the
PCA that actually drove clustering here. That meant "consumers_met_pca.csv"
and "PCA.txt" described a PCA space that was NOT the one the segments
actually lived in - easy to misread as ground truth for the clustering.

010 always computed its own PCA per country internally (to feed the GMM)
but threw the scores/loadings away. This stage now keeps them and writes
out exactly what 030 used to, so there is a single PCA fit per country,
used both for clustering AND for reporting:
    - results/consumers_met_pca.csv   (PCA scores joined onto ID/segment cols)
    - results/PCA.txt                 (variance explained, loadings, etc.)

030-pca-pipeline.py has been removed from the pipeline; run_pipeline.py no
longer calls it. The file is kept as a thin deprecation stub in case
anything still imports it directly.

Outputs
-------
- results/consumers_{country}.csv                    (one file per country)
- results/consumers_met_segmenten_per_land.csv        (all countries combined)
- results/consumers_met_pca.csv                       (PCA scores, formerly from 030)
- results/PCA.txt                                     (PCA report, formerly from 030)

Requires: pandas, scikit-learn, torch, tgmm
"""

from __future__ import annotations

import pandas as pd
import torch
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from tgmm import GaussianMixture

import config
from data_loading import load_and_clean, prepare_features
from logging_utils import get_logger

log = get_logger("010-gmm")


def _build_pca_report_block(country: str, group_size: int, numeric_scaled: pd.DataFrame,
                             pca: PCA, loadings_df: pd.DataFrame) -> str:
    """Build the same human-readable PCA summary block 030 used to log/save."""
    expl_var = pca.explained_variance_
    expl_var_rat = pca.explained_variance_ratio_
    cum_var = expl_var_rat.cumsum()
    singular_values = pca.singular_values_

    top_features = ""
    pc_cols = [c for c in loadings_df.columns if c.startswith("PC")]
    for col in pc_cols:
        sorted_loadings = loadings_df[col].abs().sort_values(ascending=False)
        top_features += (
            f"Top {config.PCA_TOP_N_FEATURES} features for {col}:\n"
            f"{loadings_df.loc[sorted_loadings.index[:config.PCA_TOP_N_FEATURES], col]}\n\n"
        )

    # Number of components needed for the target variance (unbounded PCA, for reference only)
    pca_full = PCA().fit(numeric_scaled)
    cum_full = pca_full.explained_variance_ratio_.cumsum()
    n_for_target = int((cum_full >= config.PCA_VARIANCE_TARGET).argmax() + 1)

    block = (
        f"=== {country} (n={group_size}) ===\n"
        f"Samples: {numeric_scaled.shape[0]}, Features: {numeric_scaled.shape[1]}\n"
        f"Features used: {list(numeric_scaled.columns)}\n\n"
        f"Explained variance:                {expl_var}\n"
        f"Explained variance ratio:          {expl_var_rat}\n"
        f"Cumulative explained variance ratio:  {cum_var}\n"
        f"Singular values:                  {singular_values}\n"
        f"Components needed for {config.PCA_VARIANCE_TARGET:.0%} variance: {n_for_target} (of {numeric_scaled.shape[1]} features)\n\n"
        f"PCA loadings (weight per component per feature):\n{loadings_df[pc_cols]}\n\n"
        f"{top_features}"
        f"{'-' * 80}\n\n"
    )
    return block


def fit_gmm_for_country(df_country: pd.DataFrame, n_components: int, covariance_type: str,
                         best_init_setup: int, country: str):
    """Fit a GMM on the rows of a single country and return labels/probabilities attached.

    Returns
    -------
    df_result : pd.DataFrame        original rows + segment label + segment probabilities
    pca_scores_df : pd.DataFrame    PCA scores used for clustering, indexed like df_country
    pca_report_block : str          the human-readable PCA summary (variance, loadings, ...)
    """
    df_features = prepare_features(df_country)
    log.info("Features: %s", df_features.columns.tolist())

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
            country, config.PCA_N_COMPONENTS
        )
    elif config.PCA_N_COMPONENTS < 1:
        pca = PCA(n_components = config.PCA_N_COMPONENTS)
        log.info(
            "=== %s: config.PCA_N_COMPONENTS = %d and is < 1, so PCA will keep only the specified number of components ===",
            country, config.PCA_N_COMPONENTS
        )
    pca_scores = pca.fit_transform(numeric_scaled)

    pca_scores_df = pd.DataFrame(
        pca_scores,
        columns=[f"PC{i + 1}" for i in range(pca.n_components_)],
        index=numeric_scaled.index,
    )

    log.info(
        "%s: PCA reduced %d features to %d components (%.1f%% variance explained).",
        country, numeric_scaled.shape[1], pca.n_components_,
        100 * pca.explained_variance_ratio_.sum(),
    )

    # Loadings: how much each ORIGINAL feature contributes to each retained
    # component. This is the SAME PCA fit used for clustering below, so
    # (unlike the old 030) this report is guaranteed to describe the space
    # the segments actually live in.
    loadings_df = pd.DataFrame(
        pca.components_.T,
        columns=[f"PC{i + 1}" for i in range(pca.n_components_)],
        index=numeric_scaled.columns,
    )

    pca_report_block = _build_pca_report_block(country, len(df_country), numeric_scaled, pca, loadings_df)
    log.info(pca_report_block)

    # Clustering runs on the PCA-reduced representation rather than the
    # raw standardized features - denser, decorrelated components tend
    # to give GMM covariance estimation an easier time in high-dim cases.
    device = "cuda" if torch.cuda.is_available() else "cpu"
    x_tensor = torch.tensor(pca_scores, dtype=torch.float32, device=device)
    log.info("Tensor created on device: %s", device)

    log.info("Training GMM with %d components...", n_components)
    gmm = GaussianMixture(
        n_components=n_components,
        covariance_type=covariance_type,
        init_means="kmeans",
        n_init=config.CLUSTER_SELECTION_N_INIT,
        random_state=best_init_setup,
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
    return df_result, pca_scores_df, pca_report_block


def run(landen: list[str] | None = None, exclude_terms: list[str] | None = None) -> dict[str, pd.DataFrame]:
    landen = landen if landen is not None else config.LANDEN
    exclude_terms = exclude_terms if exclude_terms is not None else config.EXCLUDE_TERMS

    df = load_and_clean(config.GMM_INPUT_PATH)
    log.info("Data loaded: %d rows, %d columns.", len(df), len(df.columns))

    dfs_per_country: dict[str, pd.DataFrame] = {}
    pca_scores_per_country: dict[str, pd.DataFrame] = {}
    pca_txt_blocks: list[str] = []

    for country in landen:
        n_components = config.get_n_components(country)
        covariance_type = config.get_covariance_type(country)
        best_init_setup = config.get_best_init_setup(country)
        log.info("=== Processing %s (n_components=%d, covariance_type=%s, best_init_setup=%d) ===",
                  country, n_components, covariance_type, best_init_setup)
        df_country = df[df[config.COUNTRY_COL] == country]

        if df_country.empty:
            log.warning("No rows found for %s, skipping.", country)
            continue

        log.info("%d rows found for %s.", len(df_country), country)
        df_result, pca_scores_df, pca_report_block = fit_gmm_for_country(
            df_country, n_components, covariance_type, best_init_setup, country
        )
        dfs_per_country[country] = df_result
        pca_scores_per_country[country] = pca_scores_df
        pca_txt_blocks.append(pca_report_block)

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

    # --- PCA reporting (formerly 030-pca-pipeline.py) --------------------
    # Join each country's PCA scores (the ones actually used for clustering)
    # onto the combined, segmented output - same shape/columns 030 used to
    # produce, but now guaranteed to be the same PCA space as the segments.
    pca_scores_all = pd.concat(pca_scores_per_country.values())
    df_with_pca = df_total.join(pca_scores_all)  # join on index

    pc_cols = list(pca_scores_all.columns)
    exclude_cols = [c for c in df_total.columns if any(term in c.lower() for term in exclude_terms)]
    keep_cols = [config.ID_COL] + pc_cols + exclude_cols
    df_pca_output = df_with_pca[keep_cols]

    df_pca_output.to_csv(config.PCA_OUTPUT_CSV, index=False)
    config.PCA_OUTPUT_TXT.write_text("\n".join(pca_txt_blocks))
    log.info("Saved %s and %s (PCA space matches the one used for clustering above).",
              config.PCA_OUTPUT_CSV, config.PCA_OUTPUT_TXT)

    return dfs_per_country


if __name__ == "__main__":
    run()