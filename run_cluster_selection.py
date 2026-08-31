"""
run_cluster_selection.py
==========================
Entry point 1 of 2. Run this FIRST, before the full pipeline.

Sweeps candidate cluster counts per country (005) and plots the elbow
curves (006), so you can see how many segments make sense per country
BEFORE spending time on the full production GMM fit and everything
downstream of it (stats, PCA).

This is a SINGLE-feature-set script: it uses whatever FEATURE_SET is
already in the environment (or config.py's default if unset), the same
way every other stage script does. To sweep all three feature sets
(12/30/32) in one go, use run_feature_sweep.py, which spawns this script
once per feature set with FEATURE_SET set appropriately - don't add
feature-set looping here too, or you end up with two orchestrators
fighting over the same job.

Usage
-----
    python run_cluster_selection.py
    python run_cluster_selection.py --combine-countries
    FEATURE_SET=30 python run_cluster_selection.py

--combine-countries pools every country in config.LANDEN into a single
cluster-count sweep instead of one per country - use this if you want one
shared segmentation across countries rather than per-country segments. The
resulting rows in results/cluster_selection.csv are labelled with the
joined country codes (e.g. "DE+FR+NL"); use that same label as the key when
you edit config.GMM_N_COMPONENTS afterwards, and pass --combine-countries
to run_pipeline.py too so stage 010 fits the shared model 007 configured
for that label instead of falling back to per-country lookups. If you're
sweeping all feature sets via run_feature_sweep.py, pass --combine-countries
to that script instead and it'll forward this flag to every run.

This does not modify config.py for you. After reviewing
results/cluster_selection.csv and results/figures/cluster_selection_*.png,
edit the GMM_N_COMPONENTS dict in config.py with your chosen k per country,
then run:

    python run_pipeline.py
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

import config
from logging_utils import get_logger

log = get_logger("run-cluster-selection")

LANDEN = config.LANDEN


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--combine-countries",
        action="store_true",
        help=(
            "Pool all countries in config.LANDEN into a single cluster-count "
            "sweep instead of running one sweep per country."
        ),
    )
    return parser.parse_args()


def _load_stage(filename: str):
    path = Path(__file__).resolve().parent / filename
    if not path.exists():
        raise FileNotFoundError(f"Stage script not found: {path}")
    module_name = path.stem.replace("-", "_")
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def main() -> None:
    args = _parse_args()

    log.info("Sweeping cluster counts (FEATURE_SET=%s) for countries: %s", config.FEATURE_SET, LANDEN)
    if args.combine_countries:
        log.info("--combine-countries set: pooling all countries into a single sweep.")

    cluster_selection = _load_stage("005-cluster-selection-pipeline.py")
    visualise = _load_stage("006-visualise-cluster-selection-pipeline.py")
    update_config = _load_stage("007-update-config-from-cluster-selection.py")

    # log.info("=== Stage 1/3 (feat%s): Cluster count selection (k=%d..%d) ===",
    #          config.FEATURE_SET, config.CLUSTER_SELECTION_K_MIN, config.CLUSTER_SELECTION_K_MAX)
    cluster_selection.run(landen=LANDEN, covariance=config.COVARIANCE_TYPE,
                           combine_countries=args.combine_countries)

    log.info("=== Stage 2/3 (feat%s): Plot cluster count selection ===", config.FEATURE_SET)
    # If you wish to visualise a specific cluster_selection CSV file, pass it as visualise_path="path/to/file.csv"
    visualise.run(landen=LANDEN, combine_countries=args.combine_countries) #, visualise_path="results/cluster_selection_2026-08-11_11-49.csv")

    log.info("Done. Review results/figures/cluster_selection_*.png and "
              "results/cluster_selection.csv, then edit the GMM_N_COMPONENTS "
              "dict in config.py before running: python run_pipeline.py")

    log.info("=== Stage 3/3 (feat%s): Update GMM configuration ===", config.FEATURE_SET)
    update_config.run(combine_countries=args.combine_countries)

    log.info("Updated GMM configuration saved to gmm_n_components.json. Please review and update config.py accordingly.")



if __name__ == "__main__":
    main()
