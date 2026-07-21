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


def load_and_clean(input_path: Path) -> pd.DataFrame:
    """Load the raw input file and handle known data-quality issues."""
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    df = pd.read_csv(input_path)

    # KOOPKRACHT is loaded as a string in the source export; coerce to numeric.
    if "KOOPKRACHT" in df.columns:
        df["KOOPKRACHT"] = pd.to_numeric(df["KOOPKRACHT"].astype(str).str.strip(), errors="coerce")

    n_missing = int(df.isna().sum().sum())
    if n_missing > 0:
        missing_distribution = df.isna().sum()
        cols_with_missing = df.columns[df.isna().any()].tolist()
        log.warning(
            "Found %d missing values in columns %s; imputing with the column median.",
            n_missing,
            cols_with_missing,
        )
        log.debug("Missing-value distribution:\n%s", missing_distribution[missing_distribution > 0])

        # NOTE: this fills with the GLOBAL median across all countries. If
        # country distributions differ a lot, consider imputing per-country
        # instead (df.groupby(config.COUNTRY_COL).transform(...)).
        df = df.fillna(df.median(numeric_only=True))
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
