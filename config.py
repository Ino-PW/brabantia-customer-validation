"""
Shared configuration for the consumer-segmentation pipeline.

Every stage (005-cluster-selection, 006-visualise-cluster-selection,
010-gmm, 020-stats, 030-pca) imports its constants from here instead of
redefining them locally. Change a path, country list, or parameter once,
and every stage picks it up.
"""

from pathlib import Path
from datetime import datetime
import json
import os
import sys

# --------------------------------------------------------------------------
# Directories
# --------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
RESULTS_DIR = BASE_DIR / "results"
FIGURES_DIR = BASE_DIR / "figures"

for _dir in (DATA_DIR, RESULTS_DIR, FIGURES_DIR):
    _dir.mkdir(parents=True, exist_ok=True)

COVARIANCE_TYPE = ['full', 'diag', 'spherical', 'tied_full', 'tied_diag', 'tied_spherical']
COVARIANCE = 'type'

# --------------------------------------------------------------------------
# Feature-count sweep: which FEATURE_SET is active for this run
# --------------------------------------------------------------------------
# Selectable per run via the FEATURE_SET env var, so run_feature_sweep.py can
# run the 12/30/32-feature tests back-to-back without editing this file
# between runs. Resolved early because both the GMM config JSON filename
# (below) and the 005/006 output filenames (further down) are tagged with it.
#   "12" - the 12 curated GMM_FEATURE_COLS
#   "30" - 12 curated + the 18 seasonal/campaign TOTAL_* columns
#   "32" - 12 curated + the 18 seasonal columns + the 2 annual totals
FEATURE_SET = os.environ.get("FEATURE_SET", "12")  # "12" / "30" / "32"
RECLUSTER = os.environ.get("RECLUSTER", "0") == "1"
_VALID_FEATURE_SETS = {"12", "30", "32"}
if FEATURE_SET not in _VALID_FEATURE_SETS:
    raise ValueError(f"Unknown FEATURE_SET={FEATURE_SET!r}; expected one of {sorted(_VALID_FEATURE_SETS)}.")
FEATURE_TAG = f"feat{FEATURE_SET}"  # used to tag output filenames per run

# --------------------------------------------------------------------------
# Countries processed by every stage
# --------------------------------------------------------------------------
LANDEN = ["NL", "BE", "FR", "DE", "GB", "ES"]


# --------------------------------------------------------------------------
# Load GMM configuration from JSON file
# --------------------------------------------------------------------------
# 007-update-config-from-cluster-selection.py writes one JSON per feature
# set (gmm_n_components_feat12.json / feat30 / feat32), so each run loads
# the config that matches its own FEATURE_SET. Falls back to the legacy
# untagged gmm_n_components.json if a tagged file doesn't exist yet (e.g.
# before you've run 007 with this feature-set naming).
# if RECLUSTER is True:
GMM_CONFIG_PATH = BASE_DIR / f"gmm_n_components_{FEATURE_TAG}_herclustering.json"
# else:
    # # GMM_CONFIG_PATH = BASE_DIR / f"gmm_n_components_{FEATURE_TAG}_{'+'.join(LANDEN)}.json"
    # if not GMM_CONFIG_PATH.exists():
    #     GMM_CONFIG_PATH = BASE_DIR / f"gmm_n_components_{FEATURE_TAG}.json"

# Load the GMM configuration (n_clusters, best_init_setup, covariance_type)
try:
    with open(GMM_CONFIG_PATH, 'r') as f:
        GMM_CONFIG = json.load(f)

except FileNotFoundError:
    if not sys.argv[0].endswith("005-cluster-selection-pipeline.py") and not sys.argv[0].endswith("run_cluster_selection.py"):
        raise FileNotFoundError(
            f"GMM configuration file not found at {GMM_CONFIG_PATH}. "
            "Run the cluster selection script to generate it."
        )
    GMM_CONFIG = {}  # Empty config; will be populated by 005-cluster-selection-pipeline.py

# Extract n_clusters, best_init_setup, and covariance_type per country
GMM_N_COMPONENTS = {country: data["n_clusters"] for country, data in GMM_CONFIG.items()}
GMM_BEST_INIT_SETUP = {country: data["best_init_setup"] for country, data in GMM_CONFIG.items()}
GMM_COVARIANCE_TYPE = {country: data["covariance_type"] for country, data in GMM_CONFIG.items()}



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
# Feature selection - which raw columns feed the model
# --------------------------------------------------------------------------
# GMM_EXTRA_EXCLUDE_COLS_BASE is the untouched original list: excluding all
# 21 of these columns leaves exactly the 12 columns in GMM_FEATURE_COLS.
GMM_ID_COLS = [ID_COL]
GMM_EXTRA_EXCLUDE_COLS_BASE = ["order_number_functional_all","TOTAL_2024","TOTAL_2025",'TOTAL_OUTLET_JAN_2024', 'TOTAL_DROOG_MOLEN_2024', 'TOTAL_STEAM_WIN', 'TOTAL_DESIGN',
                           'TOTAL_OUTLET_JUL_2024', 'TOTAL_BACK_TO_SCHOOL', 'TOTAL_BINLINER', 'TOTAL_OUTLET_JAN_2025', 'TOTAL_DROOG_MOLEN_2025', 'TOTAL_OUTLET_JUL_2025', 
                           'TOTAL_MAKE_TAKE', 'TOTAL_NEWICON', 'TOTAL_PINK_STRIJKPLANK', 'TOTAL_POST_HOLIDAY', 'TOTAL_SPRING_SALES', 'TOTAL_BACK_TO_SCHOOL_SEASON', 'TOTAL_PRE_HOLIDAY', 'TOTAL_OFF_PEAK', 'TOTAL_SERVICE']  # dropped in addition to ID/country/categorical cols
GMM_FEATURE_COLS = ['TOTAL_PRODUCTS_IN_ORDER', 'TOTAL_ORDERLINE_SALES', 'ORDER_NUMBER_FUNCTIONAL_COUNT', 'TOTAL_BATHROOM_TOILET', 'TOTAL_FOOD_ENJOYMENT', 'TOTAL_WASTE_MANAGEMENT', 'TOTAL_LAUNDRY_CARING', 'TOTAL_OTHERS','NET_SALES', 'KOOPKRACHT', 'GENDER_ENCODED']

# Named variants of GMM_EXTRA_EXCLUDE_COLS, keyed by the FEATURE_SET
# resolved above.
#   "12" - exclude all 21 extra columns -> leaves the 12 curated GMM_FEATURE_COLS
#   "30" - exclude only the duplicate order-count col + the 2 annual totals
#          -> adds the 18 seasonal/campaign TOTAL_* columns back -> 30 features
#   "32" - exclude only the duplicate order-count col
#          -> adds the 18 seasonal columns + the 2 annual totals back -> 32 features
GMM_EXTRA_EXCLUDE_COLS_VARIANTS = {
    "12": GMM_EXTRA_EXCLUDE_COLS_BASE,
    "30": ["order_number_functional_all","TOTAL_SERVICE", "TOTAL_2024", "TOTAL_2025"],
    "32": ["order_number_functional_all","TOTAL_SERVICE"],
}
GMM_EXTRA_EXCLUDE_COLS = GMM_EXTRA_EXCLUDE_COLS_VARIANTS[FEATURE_SET]

# --------------------------------------------------------------------------
# 005 - Cluster count selection (runs BEFORE 010, directly on raw input data;
# does not depend on 010 having run)
# --------------------------------------------------------------------------
now = datetime.now().strftime("%Y-%m-%d_%H-%M")
CLUSTER_SELECTION_OUTPUT = RESULTS_DIR / f"cluster_selection_{FEATURE_TAG}_{now}.csv"
CLUSTER_SELECTION_K_MIN = 3
CLUSTER_SELECTION_K_MAX = 6
CLUSTER_SELECTION_N_INIT = 5  # lower than production n_init=10: this runs K_MAX-K_MIN+1 times more fits
CLUSTER_SELECTION_SILHOUETTE_SAMPLE_SIZE = 5000  # cap rows used for silhouette (None = use all rows, slow on big data)
CLUSTER_SELECTION_RANDOM_STATE = 0
CLUSTER_SELECTION_N_CLUSTERS_COL = "n_clusters"
CLUSTER_SELECTION_SILHOUETTE_COL = "silhouette_score"
CLUSTER_SELECTION_N_DAVIES_BOULDIN = "n_clusters"
CLUSTER_SELECTION_DAVIES_BOULDIN = "davies_bouldin_score"
CLUSTER_SELECTION_N_CALINKSI_HARABASZ ="n_clusters"
CLUSTER_SELECTION_CALINKSI_HARABASZ = "calinski_harabasz_score"

RECLUSTER_CLUSTER_SELECTION_OUTPUT = RESULTS_DIR / f"recluster/recluster_cluster_selection_{FEATURE_TAG}_{now}.csv"
RECLUSTER_CLUSTERING_OUTPUT = RESULTS_DIR / f"recluster/recluster_clustering_{FEATURE_TAG}_{now}.csv"
RECLUSTER_PCA_SCORES_OUTPUT = RESULTS_DIR / f"recluster/recluster_pca_scores_{FEATURE_TAG}_{now}.csv"
RECLUSTER_PCA_LOADINGS_OUTPUT = RESULTS_DIR / f"recluster/recluster_pca_loadings_{FEATURE_TAG}_{now}.csv"


INIT_SETUP = "best_init_setup"

PCA_N_COMPONENTS = 12 # 0.90  # keep however many components are needed to explain 90% of variance
PCA_SCORES_OUTPUT = RESULTS_DIR / f"pca_scores_{FEATURE_TAG}.csv"
PCA_LOADINGS_OUTPUT = RESULTS_DIR / f"pca_loadings_{FEATURE_TAG}.csv"

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

def get_best_init_setup(country: str) -> int:
    """Look up the best initialization setup for a country, falling back to the default."""
    if country not in GMM_BEST_INIT_SETUP:
        import warnings
        warnings.warn(
            f"No GMM_BEST_INIT_SETUP entry for '{country}'; using default=0.",
            stacklevel=2,
        )
    return GMM_BEST_INIT_SETUP.get(country, 0)

def get_covariance_type(country: str) -> str:
    """Look up the covariance type for a country, falling back to the default."""
    if country not in GMM_COVARIANCE_TYPE:
        import warnings
        warnings.warn(
            f"No GMM_COVARIANCE_TYPE entry for '{country}'; using default='full'.",
            stacklevel=2,
        )
    return GMM_COVARIANCE_TYPE.get(country, "full")


GMM_PER_COUNTRY_TEMPLATE = str(RESULTS_DIR / ("clusters_" + FEATURE_SET + "_" + now + "_{country}.csv"))
GMM_COMBINED_OUTPUT = str(RESULTS_DIR / ("clusters_" + FEATURE_SET + "_" + now + ".csv"))

# --------------------------------------------------------------------------
# 010 - PCA stage
# --------------------------------------------------------------------------
# PCA_N_COMPONENTS = 2
PCA_TOP_N_FEATURES = 10
PCA_VARIANCE_TARGET = 1 #0.90  # used to report "components needed for 90% variance"

PCA_OUTPUT_CSV = (RESULTS_DIR / ("consumers_met_pca_" + FEATURE_SET + "_" + now + ".csv"))
PCA_OUTPUT_TXT = (RESULTS_DIR / ("PCA_" + FEATURE_SET + "_" + now + ".txt"))

# --------------------------------------------------------------------------
# 020 - Stats stage
# --------------------------------------------------------------------------
STATS_OUTPUT = str(RESULTS_DIR / ("stats_" + FEATURE_SET + "_" + now + ".csv"))
SEGMENT_COL = "segment"
