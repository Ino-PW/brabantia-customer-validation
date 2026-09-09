"""
Shared data loading / feature preparation for the GMM stages.

Both 005-cluster-selection-pipeline.py (explores candidate k values) and
010-gmm-pipeline.py (production fit) need to turn the same raw input into
the same feature matrix per country. Previously that logic was duplicated
across two scripts, which is exactly how they'd quietly drift apart (e.g.
one script's feature set changes and the other's doesn't, silently
invalidating whichever k you picked). It now lives here once.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

import config
from logging_utils import get_logger

log = get_logger("data-loading")


def load_and_clean(input_path: Path, country_specific_recluster: dict[str, int] = None) -> pd.DataFrame:
    """Load the raw input file and handle known data-quality issues."""
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    df = pd.read_csv(input_path)

    if country_specific_recluster != {} and country_specific_recluster is not None:
        df_copy = df.copy()
        log.info("Reclustering with country-specific cluster counts: %s", country_specific_recluster)

        mask = df['prd_country'].map(country_specific_recluster) == df['segment']
            
        df = df_copy[mask]

    # KOOPKRACHT is loaded as a string in the source export; coerce to numeric.
    if "KOOPKRACHT" in df.columns:
        df["KOOPKRACHT"] = pd.to_numeric(df["KOOPKRACHT"].astype(str).str.strip(), errors="coerce")

    n_missing = int(df.isna().sum().sum())
    if n_missing > 0:
        missing_distribution = df.isna().sum()
        numeric_cols_with_missing = df.select_dtypes(include="number").columns[
            df.select_dtypes(include="number").isna().any()
        ].tolist()
        non_numeric_cols_with_missing = [
            c for c in df.columns[df.isna().any()].tolist() if c not in numeric_cols_with_missing
        ]
        log.warning(
            "Found %d missing values. Imputing numeric columns %s with the per-country median.",
            n_missing,
            numeric_cols_with_missing,
        )
        if non_numeric_cols_with_missing:
            log.warning(
                "Non-numeric columns %s have missing values but will NOT be imputed.",
                non_numeric_cols_with_missing,
            )
        log.debug("Missing-value distribution:\n%s", missing_distribution[missing_distribution > 0])

    
        # NOTE: this fills with the median per country. 
        numeric_cols = df.select_dtypes(include="number").columns
        df[numeric_cols] = df.groupby(config.COUNTRY_COL)[numeric_cols].transform(lambda s: s.fillna(s.median()))
    else:
        log.info("No missing values found.")

    return df


def prepare_features(df_country: pd.DataFrame) -> pd.DataFrame:
    """Drop ID/country/categorical/segment-label columns, leaving only model features."""
    categorical_cols = df_country.select_dtypes(exclude="number").columns.tolist()
    exclude_cols = config.GMM_ID_COLS + [config.COUNTRY_COL] + config.GMM_EXTRA_EXCLUDE_COLS + categorical_cols
    df_features = df_country.drop(columns=exclude_cols, errors="ignore")

    # Defensive: if this ever runs against an already-segmented file (e.g. in
    # a notebook), strip out segment/probability columns too.
    segment_like = [c for c in df_features.columns if any(term in c.lower() for term in config.EXCLUDE_TERMS)]
    return df_features.drop(columns=segment_like, errors="ignore")
