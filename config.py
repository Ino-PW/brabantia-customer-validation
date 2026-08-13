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

# --------------------------------------------------------------------------
# Directories
# --------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
RESULTS_DIR = BASE_DIR / "results"
FIGURES_DIR = RESULTS_DIR / "figures"

for _dir in (DATA_DIR, RESULTS_DIR, FIGURES_DIR):
    _dir.mkdir(parents=True, exist_ok=True)

COVARIANCE_TYPE = ['full', 'diag', 'spherical', 'tied_full', 'tied_diag', 'tied_spherical']
COVARIANCE = 'type'

# --------------------------------------------------------------------------
# Load GMM configuration from JSON file
# --------------------------------------------------------------------------
GMM_CONFIG_PATH = BASE_DIR / "gmm_n_components.json"

# Load the GMM configuration (n_clusters, best_init_setup, covariance_type)
try:
    with open(GMM_CONFIG_PATH, 'r') as f:
        GMM_CONFIG = json.load(f)
except FileNotFoundError:
    raise FileNotFoundError(
        f"GMM configuration file not found at {GMM_CONFIG_PATH}. "
        "Run the cluster selection script to generate it."
    )

# Extract n_clusters, best_init_setup, and covariance_type per country
GMM_N_COMPONENTS = {country: data["n_clusters"] for country, data in GMM_CONFIG.items()}
GMM_BEST_INIT_SETUP = {country: data["best_init_setup"] for country, data in GMM_CONFIG.items()}
GMM_COVARIANCE_TYPE = {country: data["covariance_type"] for country, data in GMM_CONFIG.items()}

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
now = datetime.now().strftime("%Y-%m-%d_%H-%M")
CLUSTER_SELECTION_OUTPUT = RESULTS_DIR / f"cluster_selection_{now}.csv"
CLUSTER_SELECTION_K_MIN = 3
CLUSTER_SELECTION_K_MAX = 15
CLUSTER_SELECTION_N_INIT = 5  # lower than production n_init=10: this runs K_MAX-K_MIN+1 times more fits
CLUSTER_SELECTION_SILHOUETTE_SAMPLE_SIZE = 5000  # cap rows used for silhouette (None = use all rows, slow on big data)
CLUSTER_SELECTION_RANDOM_STATE = 0
CLUSTER_SELECTION_N_CLUSTERS_COL = "n_clusters"
CLUSTER_SELECTION_SILHOUETTE_COL = "silhouette_score"
CLUSTER_SELECTION_N_DAVIES_BOULDIN = "n_clusters"
CLUSTER_SELECTION_DAVIES_BOULDIN = "davies_bouldin_score"
CLUSTER_SELECTION_N_CALINKSI_HARABASZ ="n_clusters"
CLUSTER_SELECTION_CALINKSI_HARABASZ = "calinski_harabasz_score"

INIT_SETUP = "best_init_setup"

PCA_N_COMPONENTS = 12 # 0.90  # keep however many components are needed to explain 90% of variance
PCA_SCORES_OUTPUT = RESULTS_DIR / "pca_scores.csv"
PCA_LOADINGS_OUTPUT = RESULTS_DIR / "pca_loadings.csv"

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


GMM_ID_COLS = [ID_COL]
GMM_EXTRA_EXCLUDE_COLS = ["order_number_functional_all","TOTAL_2024","TOTAL_2025",'TOTAL_OUTLET_JAN_2024', 'TOTAL_DROOG_MOLEN_2024', 'TOTAL_STEAM_WIN', 'TOTAL_DESIGN',
                           'TOTAL_OUTLET_JUL_2024', 'TOTAL_BACK_TO_SCHOOL', 'TOTAL_BINLINER', 'TOTAL_OUTLET_JAN_2025', 'TOTAL_DROOG_MOLEN_2025', 'TOTAL_OUTLET_JUL_2025', 
                           'TOTAL_MAKE_TAKE', 'TOTAL_NEWICON', 'TOTAL_PINK_STRIJKPLANK', 'TOTAL_POST_HOLIDAY', 'TOTAL_SPRING_SALES', 'TOTAL_BACK_TO_SCHOOL_SEASON', 'TOTAL_PRE_HOLIDAY', 'TOTAL_OFF_PEAK']  # dropped in addition to ID/country/categorical cols
GMM_FEATURE_COLS = ['TOTAL_PRODUCTS_IN_ORDER', 'TOTAL_ORDERLINE_SALES', 'ORDER_NUMBER_FUNCTIONAL_COUNT', 'TOTAL_BATHROOM_TOILET', 'TOTAL_FOOD_ENJOYMENT', 'TOTAL_WASTE_MANAGEMENT', 'TOTAL_LAUNDRY_CARING', 'TOTAL_SERVICE', 'TOTAL_OTHERS','NET_SALES', 'KOOPKRACHT', 'GENDER_ENCODED']

GMM_PER_COUNTRY_TEMPLATE = str(RESULTS_DIR / "consumers_{country}.csv")
GMM_COMBINED_OUTPUT = RESULTS_DIR / "consumers_met_segmenten_per_land.csv"

# --------------------------------------------------------------------------
# 010 - PCA stage
# --------------------------------------------------------------------------
# PCA_N_COMPONENTS = 2
PCA_TOP_N_FEATURES = 15
PCA_VARIANCE_TARGET = 1 #0.90  # used to report "components needed for 90% variance"

PCA_OUTPUT_CSV = RESULTS_DIR / "consumers_met_pca.csv"
PCA_OUTPUT_TXT = RESULTS_DIR / "PCA.txt"

# --------------------------------------------------------------------------
# 020 - Stats stage
# --------------------------------------------------------------------------
STATS_OUTPUT = RESULTS_DIR / "stats.csv"
SEGMENT_COL = "segment"

