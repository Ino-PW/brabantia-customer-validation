"""
Stage 030 - PCA
================
Reads the combined, segmented file (output of 010-gmm-pipeline) and runs a
per-country PCA for dimensionality reduction / exploratory analysis.

Renumbered from 020 -> 030: this stage doesn't feed 040-visualise (which
reads stats.csv from stage 020), so it's placed after stats instead of
before it. See config.py for shared paths/parameters.

Fixes vs. the original version:
- PCA(n_components=...) instead of the invalid PCA(N_PCA_COMPONENTS=...)
- pca.n_components_ instead of the nonexistent pca.N_PCA_COMPONENTS_
  (both of these raised errors / AttributeErrors before)

Outputs
-------
- results/consumers_met_pca.csv
- results/PCA.txt
"""

from __future__ import annotations

import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

import config
from logging_utils import get_logger

log = get_logger("030-pca")


def run(landen: list[str] | None = None, exclude_terms: list[str] | None = None) -> pd.DataFrame:
    landen = landen if landen is not None else config.LANDEN
    exclude_terms = exclude_terms if exclude_terms is not None else config.EXCLUDE_TERMS

    if not config.GMM_COMBINED_OUTPUT.exists():
        raise FileNotFoundError(
            f"{config.GMM_COMBINED_OUTPUT} not found - run 010-gmm-pipeline.py first."
        )

    df = pd.read_csv(config.GMM_COMBINED_OUTPUT)

    if config.COUNTRY_COL not in df.columns:
        raise ValueError(f"Column '{config.COUNTRY_COL}' not found. Available columns: {list(df.columns)}")

    df = df[df[config.COUNTRY_COL].isin(landen)]

    exclude_cols = [c for c in df.columns if any(term in c.lower() for term in exclude_terms)]
    log.info("Excluded from PCA (%d columns): %s", len(exclude_cols), exclude_cols)

    all_pca_scores = []
    txt_blocks = []

    for country, group in df.groupby(config.COUNTRY_COL):
        log.info("=== %s (n=%d) ===", country, len(group))

        numeric_cols = group.select_dtypes(include="number").drop(columns=exclude_cols, errors="ignore")

        n_missing = int(numeric_cols.isna().sum().sum())
        if n_missing > 0:
            cols_with_missing = numeric_cols.columns[numeric_cols.isna().any()].tolist()
            log.warning("%d missing values found in %s, filling with column mean.", n_missing, cols_with_missing)
            numeric_cols = numeric_cols.fillna(numeric_cols.mean(numeric_only=True))
        else:
            log.info("No missing values found.")

        if len(numeric_cols) <= config.PCA_N_COMPONENTS:
            log.warning(
                "Skipping %s: too few rows (%d) for %d PCA components.",
                country, len(numeric_cols), config.PCA_N_COMPONENTS,
            )
            continue

        scaler = StandardScaler()
        numeric_scaled = pd.DataFrame(
            scaler.fit_transform(numeric_cols),
            columns=numeric_cols.columns,
            index=numeric_cols.index,
        )

        pca = PCA(n_components=config.PCA_N_COMPONENTS)
        pca_scores = pca.fit_transform(numeric_scaled)

        pca_df = pd.DataFrame(
            pca_scores,
            columns=[f"PC{i + 1}" for i in range(pca.n_components_)],
            index=numeric_cols.index,
        )
        all_pca_scores.append(pca_df)

        expl_var = pca.explained_variance_
        expl_var_rat = pca.explained_variance_ratio_
        cum_var = expl_var_rat.cumsum()
        singular_values = pca.singular_values_

        loadings = pd.DataFrame(
            pca.components_.T,
            columns=[f"PC{i + 1}" for i in range(pca.n_components_)],
            index=numeric_cols.columns,
        )

        top_features = ""
        for col in loadings.columns:
            sorted_loadings = loadings[col].abs().sort_values(ascending=False)
            top_features += (
                f"Top {config.PCA_TOP_N_FEATURES} features for {col}:\n"
                f"{loadings.loc[sorted_loadings.index[:config.PCA_TOP_N_FEATURES], col]}\n\n"
            )

        # Number of components needed for the target variance (unbounded PCA, for reference only)
        pca_full = PCA().fit(numeric_scaled)
        cum_full = pca_full.explained_variance_ratio_.cumsum()
        n_for_target = int((cum_full >= config.PCA_VARIANCE_TARGET).argmax() + 1)

        block = (
            f"=== {country} (n={len(group)}) ===\n"
            f"Samples: {numeric_cols.shape[0]}, Features: {numeric_cols.shape[1]}\n"
            f"Features used: {list(numeric_cols.columns)}\n\n"
            f"Explained variance:                {expl_var}\n"
            f"Explained variance ratio:          {expl_var_rat}\n"
            f"Cumulative explained variance ratio:  {cum_var}\n"
            f"Singular values:                  {singular_values}\n"
            f"Components needed for {config.PCA_VARIANCE_TARGET:.0%} variance: {n_for_target} (of {numeric_cols.shape[1]} features)\n\n"
            f"PCA loadings (weight per component per feature):\n{loadings}\n\n"
            f"{top_features}"
            f"{'-' * 80}\n\n"
        )
        log.info(block)
        txt_blocks.append(block)

    if not all_pca_scores:
        raise RuntimeError("No country produced PCA scores - check row counts vs. config.PCA_N_COMPONENTS.")

    config.PCA_OUTPUT_TXT.write_text("\n".join(txt_blocks))

    pca_scores_all = pd.concat(all_pca_scores)
    df_with_pca = df.join(pca_scores_all)  # join on index, safer than concat if row order changed

    pc_cols = list(pca_scores_all.columns)
    keep_cols = [config.ID_COL] + pc_cols + exclude_cols
    df_output = df_with_pca[keep_cols]

    df_output.to_csv(config.PCA_OUTPUT_CSV, index=False)
    log.info("Done. Output written to %s and %s", config.PCA_OUTPUT_CSV, config.PCA_OUTPUT_TXT)

    return df_output


if __name__ == "__main__":
    run()
