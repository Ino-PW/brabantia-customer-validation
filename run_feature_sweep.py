"""
run_feature_sweep.py
======================
Runs 005 -> 006 -> 007 (via run_cluster_selection.py) three times in a row,
once each for the 12 / 30 / 32-feature variants defined in config.py
(GMM_EXTRA_EXCLUDE_COLS_VARIANTS). Each run is a separate subprocess so
config.py gets re-imported fresh with the right FEATURE_SET env var -
imports are cached within a single process, so this can't be done by just
looping and re-importing config in-process.

Every run's outputs are tagged with the feature set so they don't
overwrite each other:
    results/cluster_selection_feat12_<timestamp>.csv
    results/cluster_selection_feat30_<timestamp>.csv
    results/cluster_selection_feat32_<timestamp>.csv
    results/pca_scores_feat12.csv / feat30 / feat32
    results/pca_loadings_feat12.csv / feat30 / feat32
    figures/cluster_selection_<country>_feat12.png / feat30 / feat32
    gmm_n_components_feat12.json / feat30 / feat32

Usage
-----
    python run_feature_sweep.py
    python run_feature_sweep.py --combine-countries

--combine-countries is forwarded to every run_cluster_selection.py
subprocess, so all three feature sets get pooled into a single
cluster-count sweep across config.LANDEN instead of one sweep per country.
See run_cluster_selection.py's docstring for what that changes about the
output (joined "DE+FR+NL"-style labels instead of per-country rows).

007-update-config-from-cluster-selection.py writes one gmm_n_components_<tag>.json
per feature set (it groups cluster_selection_*.csv files by their feat<N> tag
and keeps the newest file within each group), so nothing gets overwritten
between runs. To lock in a feature set for 010-gmm-pipeline.py, run it with
the matching FEATURE_SET env var set, e.g.:

    FEATURE_SET=30 python 010-gmm-pipeline.py

config.py automatically loads gmm_n_components_feat<FEATURE_SET>.json to match.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

FEATURE_SETS = ["12", "30", "32"]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--combine-countries",
        action="store_true",
        help=(
            "Forwarded to run_cluster_selection.py for every feature set: pool "
            "all countries in config.LANDEN into a single cluster-count sweep "
            "instead of running one sweep per country."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    repo_dir = Path(__file__).resolve().parent

    for feature_set in FEATURE_SETS:
        print(f"\n{'=' * 70}")
        print(f"=== Running cluster selection with FEATURE_SET={feature_set} ===")
        print(f"{'=' * 70}\n")

        env = os.environ.copy()
        env["FEATURE_SET"] = feature_set

        cmd = [sys.executable, "run_cluster_selection.py"]
        if args.combine_countries:
            cmd.append("--combine-countries")

        result = subprocess.run(
            cmd,
            cwd=repo_dir,
            env=env,
        )

        if result.returncode != 0:
            print(f"\nRun with FEATURE_SET={feature_set} failed (exit code {result.returncode}). Stopping sweep.")
            sys.exit(result.returncode)

    print("\nAll three feature-count runs complete.")
    print("Compare results/cluster_selection_feat12_*.csv, feat30_*.csv, feat32_*.csv")
    print("and results/figures/cluster_selection_<country>_feat{12,30,32}.png.")
    print("gmm_n_components_feat12.json / feat30.json / feat32.json were each written "
          "independently - pick a feature set for 010-gmm-pipeline.py by running it "
          "with the matching FEATURE_SET env var set.")


if __name__ == "__main__":
    main()
