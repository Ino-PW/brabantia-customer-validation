"""
Shared configuration for the consumer-segmentation pipeline.

Every stage (005-cluster-selection, 006-visualise-cluster-selection,
010-gmm, 020-stats, 030-pca) imports its constants from here instead of
redefining them locally. Change a path, country list, or parameter once,
and every stage picks it up.
"""

from pathlib import Path

# --------------------------------------------------------------------------
# Directories
# --------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
RESULTS_DIR = BASE_DIR / "results"
FIGURES_DIR = RESULTS_DIR / "figures"

for _dir in (DATA_DIR, RESULTS_DIR, FIGURES_DIR):
    _dir.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------------------------------
# Countries processed by every stage
# --------------------------------------------------------------------------
LANDEN = ["NL", "BE", "FR", "DE", "GB", "ES"]

# --------------------------------------------------------------------------
# Column naming conventions
# --------------------------------------------------------------------------
ID_COL = "master_person_key_md5"
COUNTRY_COL = "prd_country"
LAND_COL = "land"  # used in per-stage result tables (stats.csv, cluster_selection.csv)

# Columns containing any of these substrings are treated as cluster/segment
# labels and excluded from numeric modelling (PCA, stats aggregation, etc.)
EXCLUDE_TERMS = ["segment"]

# --------------------------------------------------------------------------
# 005 - Cluster count selection (runs BEFORE 010, directly on raw input data;
# does not depend on 010 having run)
# --------------------------------------------------------------------------
CLUSTER_SELECTION_OUTPUT = RESULTS_DIR / "cluster_selection.csv"
CLUSTER_SELECTION_K_MIN = 2
CLUSTER_SELECTION_K_MAX = 10
CLUSTER_SELECTION_N_INIT = 5  # lower than production n_init=10: this runs K_MAX-K_MIN+1 times more fits
CLUSTER_SELECTION_SILHOUETTE_SAMPLE_SIZE = 5000  # cap rows used for silhouette (None = use all rows, slow on big data)
CLUSTER_SELECTION_RANDOM_STATE = 0
CLUSTER_SELECTION_N_CLUSTERS_COL = "n_clusters"
CLUSTER_SELECTION_SILHOUETTE_COL = "silhouette_score"

# 006 (cluster-selection plot) reuses all of the CLUSTER_SELECTION_* constants
# above - no separate config section needed.

# --------------------------------------------------------------------------
# 010 - GMM stage
# --------------------------------------------------------------------------
GMM_INPUT_PATH = DATA_DIR / "amount_of_orders_data.csv"

# Number of GMM components (segments) PER COUNTRY. Fill these in after
# reviewing results/figures/cluster_selection_*.png from
# 005-cluster-selection-pipeline.py - don't just trust the default below.
# Any country not listed here falls back to GMM_N_COMPONENTS_DEFAULT.
GMM_N_COMPONENTS_DEFAULT = 6
GMM_N_COMPONENTS: dict[str, int] = {
    "NL": 6,
    "BE": 6,
    "FR": 6,
    "DE": 6,
    "GB": 6,
    "ES": 6,
}


def get_n_components(country: str) -> int:
    """Look up the chosen cluster count for a country, falling back to the default."""
    if country not in GMM_N_COMPONENTS:
        import warnings

        warnings.warn(
            f"No GMM_N_COMPONENTS entry for '{country}'; using GMM_N_COMPONENTS_DEFAULT={GMM_N_COMPONENTS_DEFAULT}. "
            f"Run 005-cluster-selection-pipeline.py and add an explicit entry.",
            stacklevel=2,
        )
    return GMM_N_COMPONENTS.get(country, GMM_N_COMPONENTS_DEFAULT)


GMM_ID_COLS = [ID_COL]
GMM_EXTRA_EXCLUDE_COLS = ["order_number_functional_all"]  # dropped in addition to ID/country/categorical cols

GMM_PER_COUNTRY_TEMPLATE = str(RESULTS_DIR / "consumers_{country}.csv")
GMM_COMBINED_OUTPUT = RESULTS_DIR / "consumers_met_segmenten_per_land.csv"

# --------------------------------------------------------------------------
# 020 - Stats stage
# --------------------------------------------------------------------------
STATS_OUTPUT = RESULTS_DIR / "stats.csv"
SEGMENT_COL = "segment"

# --------------------------------------------------------------------------
# 030 - PCA stage
# --------------------------------------------------------------------------
PCA_N_COMPONENTS = 2
PCA_TOP_N_FEATURES = 15
PCA_VARIANCE_TARGET = 0.90  # used to report "components needed for 90% variance"

PCA_OUTPUT_CSV = RESULTS_DIR / "consumers_met_pca.csv"
PCA_OUTPUT_TXT = RESULTS_DIR / "PCA.txt"
