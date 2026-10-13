"""Consistent logging setup shared by every pipeline stage.

In addition to the stdout stream (for watching a run live), every logger
also writes to a shared logfile under results/logs/, so a completed run can
still be read back afterwards - useful for long unattended runs, or for
checking what happened in stage 005's k-sweep after the fact.
"""

import logging
import sys
from datetime import datetime

import config

# One logfile PER PROCESS, shared by every stage's logger (005, 010, 020,
# ..., run_pipeline, run_cluster_selection). Whichever entry point you run,
# all of its log lines end up interleaved, in order, in a single readable
# file - not scattered across one file per stage.
LOG_DIR = config.BASE_DIR/ "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / f"run_{datetime.now():%Y%m%d_%H%M%S}.log"

_FORMATTER = logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)s | %(message)s", "%H:%M:%S")


def _write_run_header() -> None:
    """Write one header line identifying how this process was started.

    Without this, a logfile full of interleaved stage output (e.g. 010,
    020, 030 all sharing one file from a run_pipeline.py run) gives no clue
    afterwards whether it came from run_pipeline.py, run_cluster_selection.py,
    or a single stage script run standalone (e.g. `python 030-pca-pipeline.py`).
    """
    entry_point = sys.argv[0] or "<interactive>"
    command_line = " ".join(sys.argv) if len(sys.argv) > 1 else entry_point
    header = (
        f"{'=' * 80}\n"
        f"Run started : {datetime.now():%Y-%m-%d %H:%M:%S}\n"
        f"Entry point : {entry_point}\n"
        f"Command     : {command_line}\n"
        f"{'=' * 80}\n"
    )
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(header)


_write_run_header()


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger that writes to stdout AND to a shared run logfile.

    Safe to call multiple times (e.g. once per script) without producing
    duplicate log lines or duplicate handlers. The logfile path for the
    current run is available as `logging_utils.LOG_FILE`.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(_FORMATTER)
        logger.addHandler(stream_handler)

        file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        file_handler.setFormatter(_FORMATTER)
        logger.addHandler(file_handler)

        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger
