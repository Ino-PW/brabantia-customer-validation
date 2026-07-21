"""
run_cluster_selection.py
==========================
Entry point 1 of 2. Run this FIRST, before the full pipeline.

Sweeps candidate cluster counts per country (005) and plots the elbow
curves (006), so you can see how many segments make sense per country
BEFORE spending time on the full production GMM fit and everything
downstream of it (stats, PCA).

Usage
-----
    python run_cluster_selection.py

This does not modify config.py for you. After reviewing
results/cluster_selection.csv and results/figures/cluster_selection_*.png,
edit the GMM_N_COMPONENTS dict in config.py with your chosen k per country,
then run:

    python run_pipeline.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import config
from logging_utils import get_logger

log = get_logger("run-cluster-selection")

LANDEN = config.LANDEN


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
    log.info("Sweeping cluster counts for countries: %s", LANDEN)

    cluster_selection = _load_stage("005-cluster-selection-pipeline.py")
    visualise = _load_stage("006-visualise-cluster-selection-pipeline.py")

    log.info("=== Stage 1/2: Cluster count selection (k=%d..%d) ===",
              config.CLUSTER_SELECTION_K_MIN, config.CLUSTER_SELECTION_K_MAX)
    cluster_selection.run(landen=LANDEN)

    log.info("=== Stage 2/2: Plot cluster count selection ===")
    visualise.run(landen=LANDEN)

    log.info("Done. Review results/figures/cluster_selection_*.png and "
              "results/cluster_selection.csv, then edit the GMM_N_COMPONENTS "
              "dict in config.py before running: python run_pipeline.py")


if __name__ == "__main__":
    main()
