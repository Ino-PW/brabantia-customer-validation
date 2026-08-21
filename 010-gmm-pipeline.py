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

Combined mode
-------------
By default this fits a separate PCA + GMM per country. Pass
combine_countries=True to run() (or --combine-countries on the CLI) to
instead pool every country in `landen` into a single PCA + GMM fit, so all
of them share the same segments. See run()'s docstring for details - you'll
need a config.GMM_N_COMPONENTS entry (and covariance/init-setup) keyed by
the joined country label, e.g. "DE+FR+NL", matching what
005-cluster-selection-pipeline.py --combine-countries produces.

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


def _build_pca_report_block(group_label: str, group_size: int, numeric_scaled: pd.DataFrame,
                             pca: PCA, loadings_df: pd.DataFrame) -> str:
    """Build the same human-readable PCA summary block 030 used to log/save.

    `group_label` is either a single country code (default per-country mode)
    or a joined label like "DE+FR+NL" when countries were pooled via
    combine_countries=True in run().
    """
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
        f"=== {group_label} (n={group_size}) ===\n"
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
                         best_init_setup: int, group_label: str):
    """Fit a GMM on the rows passed in and return labels/probabilities attached.

    `df_country` may hold a single country's rows (default mode) or rows
    pooled across several countries (combine_countries=True in run()) - this
    function doesn't care either way, it just fits on whatever rows it's
    given and labels the PCA report with `group_label`.

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
            group_label, config.PCA_N_COMPONENTS
        )
    elif config.PCA_N_COMPONENTS < 1:
        pca = PCA(n_components = config.PCA_N_COMPONENTS)
        log.info(
            "=== %s: config.PCA_N_COMPONENTS = %d and is < 1, so PCA will keep only the specified number of components ===",
            group_label, config.PCA_N_COMPONENTS
        )
    pca_scores = pca.fit_transform(numeric_scaled)

    pca_scores_df = pd.DataFrame(
        pca_scores,
        columns=[f"PC{i + 1}" for i in range(pca.n_components_)],
        index=numeric_scaled.index,
    )

    log.info(
        "%s: PCA reduced %d features to %d components (%.1f%% variance explained).",
        group_label, numeric_scaled.shape[1], pca.n_components_,
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

    pca_report_block = _build_pca_report_block(group_label, len(df_country), numeric_scaled, pca, loadings_df)
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


def run(landen: list[str] | None = None, exclude_terms: list[str] | None = None,
        combine_countries: bool = False) -> dict[str, pd.DataFrame]:
    """
    Parameters
    ----------
    landen : list[str] | None
        Countries to include. Defaults to config.LANDEN when None.
    exclude_terms : list[str] | None
        Substrings used to pick which columns get carried into the PCA
        report output. Defaults to config.EXCLUDE_TERMS when None.
    combine_countries : bool, default False
        - False (default, original behaviour): fit a separate PCA + GMM
          PER country, using config.get_n_components(country) etc. to look
          up that country's chosen settings.
        - True: pool all rows from every country in `landen` into a single
          dataset and fit ONE PCA + ONE GMM across all of them combined -
          i.e. every country shares the same segments. The pooled group is
          looked up in config.get_n_components(...) etc. under the joined
          label (e.g. "DE+FR+NL", matching what
          005-cluster-selection-pipeline.py --combine-countries produces),
          so add that label to config.GMM_N_COMPONENTS (and the covariance/
          init-setup dicts) once you've picked a k for it.
          The pooled result is then split back out per actual country
          before saving, so results/consumers_{country}.csv,
          results/consumers_met_segmenten_per_land.csv, and the PCA report
          outputs keep their normal per-country shape - only the fit itself
          is shared, not the bookkeeping. segment_globaal (country + "_" +
          segment) will show the same segment ids repeating across
          countries, since the segments came from one shared model.
    """
    landen = landen if landen is not None else config.LANDEN
    exclude_terms = exclude_terms if exclude_terms is not None else config.EXCLUDE_TERMS

    df = load_and_clean(config.GMM_INPUT_PATH)
    log.info("Data loaded: %d rows, %d columns.", len(df), len(df.columns))

    # Each "group" is (label_used_for_config_lookup_and_reporting, countries_in_it).
    # Default mode: one group per country. Combined mode: a single group
    # containing every country in `landen`, labelled by joining their codes.
    if combine_countries:
        groups = [("+".join(sorted(landen)), list(landen))]
    else:
        groups = [(country, [country]) for country in landen]

    dfs_per_country: dict[str, pd.DataFrame] = {}
    pca_scores_per_country: dict[str, pd.DataFrame] = {}
    pca_txt_blocks: list[str] = []

    for group_label, countries_in_group in groups:
        n_components = config.get_n_components(group_label)
        covariance_type = config.get_covariance_type(group_label)
        best_init_setup = config.get_best_init_setup(group_label)
        log.info("=== Processing %s (n_components=%d, covariance_type=%s, best_init_setup=%d) ===",
                  group_label, n_components, covariance_type, best_init_setup)
        if combine_countries:
            log.info(
                "=== %s: combined mode - pooling %d countries into one fit (%s) ===",
                group_label, len(countries_in_group), ", ".join(countries_in_group),
            )
        df_group = df[df[config.COUNTRY_COL].isin(countries_in_group)]

        if df_group.empty:
            log.warning("No rows found for %s, skipping.", group_label)
            continue

        log.info("%d rows found for %s.", len(df_group), group_label)
        df_result, pca_scores_df, pca_report_block = fit_gmm_for_country(
            df_group, n_components, covariance_type, best_init_setup, group_label
        )
        pca_scores_per_country[group_label] = pca_scores_df
        pca_txt_blocks.append(pca_report_block)

        if combine_countries:
            # The fit was pooled, but downstream code (per-country CSVs,
            # segment_globaal, etc.) expects one entry per actual country -
            # split the shared result back out by the original country column.
            for actual_country, df_country_slice in df_result.groupby(config.COUNTRY_COL):
                dfs_per_country[actual_country] = df_country_slice
        else:
            dfs_per_country[group_label] = df_result

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
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--combine-countries",
        action="store_true",
        help=(
            "Pool all countries in config.LANDEN into a single PCA + GMM fit "
            "(shared segments) instead of fitting one model per country. "
            "Requires config.GMM_N_COMPONENTS (and covariance/init-setup "
            "config) to have an entry for the joined label, e.g. \"DE+FR+NL\" "
            "- see 005-cluster-selection-pipeline.py --combine-countries."
        ),
    )
    args = parser.parse_args()

    run(combine_countries=args.combine_countries)