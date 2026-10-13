"""
run_pipeline.py
================
Entry point 2 of 2. The full PRODUCTION pipeline:

    010-gmm-pipeline.py   -> GMM segmentation per country, using
                              config.GMM_N_COMPONENTS[country], plus PCA
                              reporting (consumers_met_pca.csv, PCA.txt) -
                              this used to be a separate 030-pca-pipeline.py
                              stage that re-fit its own PCA from scratch on
                              010's output; it's now folded into 010 so
                              there's a single PCA fit per country, used for
                              both clustering and reporting. 030 is no
                              longer part of this pipeline.
    020-stats-pipeline.py -> cluster statistics per country

Run run_cluster_selection.py FIRST if you haven't already chosen a cluster
count per country for the feature set(s) you're about to run - this script
does not sweep or validate k, it trusts whatever is in the
gmm_n_components_feat{12,30,32}.json file config.py loads.

Feature sets
------------
config.py now resolves a FEATURE_SET ("12" / "30" / "32") from the
FEATURE_SET environment variable at import time, and derives every
feature-tagged path (GMM_CONFIG_PATH, CLUSTER_SELECTION_OUTPUT,
PCA_SCORES_OUTPUT, ...) from it. Because those constants are computed once
when config.py is imported, the only reliable way to run more than one
feature set in a single invocation is to run each one in its own
subprocess with FEATURE_SET set beforehand - mutating os.environ after
config has already been imported would NOT update the already-derived
constants, and every stage script (010, 020, ...) does `import config`
itself, which would just reuse the cached module.

Usage
-----
    python run_pipeline.py                    # runs FEATURE_SET 12, 30, and 32 in turn
    python run_pipeline.py --feature-set 30    # runs just feature set 30
    FEATURE_SET=30 python run_pipeline.py      # same, via env var (back-compat)
    python run_pipeline.py --combine-countries # pool all countries into one shared GMM fit

--combine-countries pools every country in config.LANDEN into a single PCA
+ GMM fit at stage 010 (shared segments across countries) instead of
fitting one model per country. Requires config.GMM_N_COMPONENTS (and the
covariance/init-setup config) to have an entry keyed by the joined country
label (e.g. "DE+FR+NL") - see 010-gmm-pipeline.py and run
run_cluster_selection.py --combine-countries first to generate that label
and its recommended k. When running the full feature-set sweep (no
--feature-set given), the flag is forwarded to every per-feature-set
subprocess.

Each stage script also still runs standalone (e.g. `python 020-stats-pipeline.py`)
if you only need to re-run one step for whatever FEATURE_SET is in its
environment.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
import config

ALL_FEATURE_SETS = ["12", "30", "32"]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--feature-set",
        choices=[*ALL_FEATURE_SETS, "all"],
        default=None,
        help="Which FEATURE_SET to run. Omit (or pass 'all') to run 12, 30, and 32 in turn.",
    )
    parser.add_argument(
        "--combine-countries",
        action="store_true",
        help=(
            "Pool all countries in config.LANDEN into a single GMM fit "
            "(shared segments) at stage 010, instead of fitting one model "
            "per country. Requires config.GMM_N_COMPONENTS (and covariance/"
            "init-setup config) to have an entry for the joined country "
            "label - see run_cluster_selection.py --combine-countries."
        ),
    )

    parser.add_argument(
        "--recluster", 
        action="store_true",
        help=("Do new clustering on the majority cluster. "
              "This functionality only works after previous clustering has been done. "
              "It will create a new cluster_selection csv file with the reclustered results."),
    )
    parser.add_argument(
        "--recluster-path", type=str, default=None,
        help=("Path to the CSV file containing the results that have to be reclustered.")
    )


    return parser.parse_args()


# ---------------------------------------------------------------------------
# Feature-set resolution has to happen BEFORE `import config`, because
# config.py reads the FEATURE_SET env var exactly once, at import time, and
# every downstream constant (file paths, GMM_CONFIG, feature columns, ...)
# is derived from it right then. If FEATURE_SET was already set in the
# environment (e.g. by a parent process spawning us, or by the user doing
# `FEATURE_SET=30 python run_pipeline.py`), we treat this as a single-run
# invocation for that one feature set, same as before. Otherwise we default
# to running the full sweep.
# ---------------------------------------------------------------------------
_args = _parse_args()
_env_feature_set = os.environ.get("FEATURE_SET")

if _args.feature_set and _args.feature_set != "all":
    os.environ["FEATURE_SET"] = _args.feature_set
    _RUN_MODE = "single"
elif _args.feature_set == "all":
    _RUN_MODE = "all"
elif _env_feature_set:
    # Backward compatible: respect a pre-set env var as a single run.
    _RUN_MODE = "single"
else:
    _RUN_MODE = "all"


def _run_all_feature_sets(combine_countries: bool) -> None:
    """Orchestrator mode: spawn one subprocess per feature set.

    Each subprocess gets its own fresh Python process (and therefore its
    own fresh `import config`), so FEATURE_SET-derived paths and the
    per-feature-set gmm_n_components_feat{N}.json config are resolved
    correctly and independently for each run.
    """
    script_path = str(Path(__file__).resolve())
    results: dict[str, bool] = {}

    print(f"=== Running full pipeline for feature sets: {ALL_FEATURE_SETS} ===")
    for feature_set in ALL_FEATURE_SETS:
        print(f"\n--- Feature set {feature_set}: starting (subprocess) ---")
        child_env = os.environ.copy()
        child_env["FEATURE_SET"] = feature_set
        cmd = [sys.executable, script_path, "--feature-set", feature_set]
        if combine_countries:
            cmd.append("--combine-countries")
        if _args.recluster:
            cmd.append("--recluster")
        if _args.recluster_path:
            cmd.append("--recluster-path")
            cmd.append(_args.recluster_path)

        proc = subprocess.run(cmd, env=child_env)
        success = proc.returncode == 0
        results[feature_set] = success
        status = "OK" if success else f"FAILED (exit code {proc.returncode})"
        print(f"--- Feature set {feature_set}: {status} ---")

    print("\n=== Pipeline sweep summary ===")
    for feature_set, success in results.items():
        print(f"  feat{feature_set}: {'OK' if success else 'FAILED'}")

    if not all(results.values()):
        failed = [fs for fs, ok in results.items() if not ok]
        raise SystemExit(f"Pipeline failed for feature set(s): {failed}")


if _RUN_MODE == "all":
    _run_all_feature_sets(_args.combine_countries)
    raise SystemExit(0)

# ---------------------------------------------------------------------------
# Single-feature-set run (FEATURE_SET is now fixed in the environment).
# ---------------------------------------------------------------------------
import importlib.util  # noqa: E402

from logging_utils import get_logger  # noqa: E402

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
    log.info("Starting production pipeline (FEATURE_SET=%s) for countries: %s",
              config.FEATURE_SET, LANDEN)
    log.info("Using GMM_N_COMPONENTS: %s (default for unlisted countries: %d)",
              config.GMM_N_COMPONENTS, config.GMM_N_COMPONENTS_DEFAULT)
    if _args.combine_countries:
        log.info("--combine-countries set: stage 010 will pool all countries into one shared GMM fit.")
    if _args.recluster:
        log.info("--recluster set: stage  will re-run clustering, ignoring any existing results.")
    if _args.recluster_path:
        log.info("--recluster-path set: stage  will save its reclustered results to %s", _args.recluster_path)

    gmm = _load_stage("010-gmm-pipeline.py")
    stats = _load_stage("011-stats-pipeline.py")

    log.info("=== Stage 1/2 (feat%s): GMM segmentation + PCA reporting ===", config.FEATURE_SET)
    gmm.run(landen=LANDEN, exclude_terms=EXCLUDE_TERMS, combine_countries=_args.combine_countries, recluster=_args.recluster, recluster_path=_args.recluster_path)

    log.info("=== Stage 2/2 (feat%s): Cluster statistics ===", config.FEATURE_SET)
    stats.run(landen=LANDEN, exclude_terms=EXCLUDE_TERMS, combine_countries=_args.combine_countries)

    log.info("Pipeline complete for FEATURE_SET=%s.", config.FEATURE_SET)


if __name__ == "__main__":
    main()