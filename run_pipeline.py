"""
run_pipeline.py
================
Entry point 2 of 2. The full PRODUCTION pipeline:

    010-gmm-pipeline.py   -> GMM segmentation per country, using
                              config.GMM_N_COMPONENTS[country]
    020-stats-pipeline.py -> cluster statistics per country
    030-pca-pipeline.py   -> PCA per country

Run run_cluster_selection.py FIRST if you haven't already chosen a cluster
count per country - this script does not sweep or validate k, it trusts
whatever is in the config.GMM_N_COMPONENTS dict.

LANDEN and EXCLUDE_TERMS are defined as globals right here, so you can
override which countries / excluded columns the whole pipeline uses from
a single place, without editing any of the individual stage scripts.
They default to the values in config.py.

Usage
-----
    python run_pipeline.py

Each stage script also still runs standalone (e.g. `python 020-stats-pipeline.py`)
if you only need to re-run one step.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import config
from logging_utils import get_logger

log = get_logger("run-pipeline")

# --------------------------------------------------------------------------
# Global pipeline parameters - edit here to change behaviour for every stage.
# --------------------------------------------------------------------------
LANDEN = config.LANDEN
EXCLUDE_TERMS = config.EXCLUDE_TERMS


def _load_stage(filename: str):
    """Import a numbered, hyphenated stage script (e.g. '010-gmm-pipeline.py') as a module.

    Regular `import` doesn't work on filenames with hyphens/leading digits,
    so stages are loaded by file path instead.
    """
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
    log.info("Starting production pipeline for countries: %s", LANDEN)
    log.info("Using GMM_N_COMPONENTS: %s (default for unlisted countries: %d)",
              config.GMM_N_COMPONENTS, config.GMM_N_COMPONENTS_DEFAULT)

    gmm = _load_stage("010-gmm-pipeline.py")
    stats = _load_stage("020-stats-pipeline.py")
    pca = _load_stage("030-pca-pipeline.py")

    log.info("=== Stage 1/3: GMM segmentation ===")
    gmm.run(landen=LANDEN)

    log.info("=== Stage 2/3: Cluster statistics ===")
    stats.run(landen=LANDEN, exclude_terms=EXCLUDE_TERMS)

    log.info("=== Stage 3/3: PCA ===")
    pca.run(landen=LANDEN, exclude_terms=EXCLUDE_TERMS)

    log.info("Pipeline complete.")


if __name__ == "__main__":
    main()
