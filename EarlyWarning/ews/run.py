"""Run the Phase 1 pipeline: load -> calendar -> validate -> transform.

    cd EarlyWarning
    python -m ews.run                     # check against today's date
    python -m ews.run --today 2026-09-30  # check freshness as of a given date
    python -m ews.run --out /tmp/ews      # write somewhere else

Writes to ``EarlyWarning/data/`` (``Dataset/`` is only read):

* ``observations.csv``    -- the clean, aligned, transformed data (one row per series per period)
* ``quality_report.csv``  -- one row per series: coverage, gaps, flags, confidence
* ``validation_log.txt``  -- the readable log of every finding, for review
* ``validation_log.csv``  -- the same findings, for filtering
* ``steps/01_loaded.csv`` ... ``steps/04_transformed.csv`` -- each step's output

If any check returns STOP, only the two log files are written and the exit code is 1.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from . import calendar, inventory, load, paths, transform, validate
from .findings import Findings, ValidationStop, write_log_csv, write_log_txt


@dataclass
class Result:
    inventory: pd.DataFrame
    loaded: pd.DataFrame
    aligned: pd.DataFrame
    validated: pd.DataFrame
    observations: pd.DataFrame
    quality: pd.DataFrame
    findings: Findings


def pipeline(today: dt.date, inventory_frame: pd.DataFrame | None = None, issues: pd.DataFrame | None = None) -> Result:
    """Run every step in memory.  Raises ``ValidationStop`` (carrying the findings) on a STOP."""
    findings = Findings()
    inv = inventory_frame if inventory_frame is not None else inventory.load_inventory()

    loaded = load.load_all(inv)
    deduped = validate.check_loaded(loaded, inv, findings)
    findings.raise_on_stop()

    aligned = calendar.align(deduped, findings)
    validated = validate.check_aligned(
        aligned, findings, today, issues if issues is not None else validate.load_issues()
    )
    findings.raise_on_stop()

    observations = transform.transform(validated, inv)
    quality = validate.quality_report(validated)
    return Result(inv, loaded.frame, aligned, validated, observations, quality, findings)


def _csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = frame.copy()
    for column in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[column]):
            out[column] = out[column].dt.strftime("%Y-%m-%d")
    out.to_csv(path, index=False, lineterminator="\n")


def write_outputs(result: Result, out: Path) -> None:
    steps = out / "steps"
    _csv(result.loaded, steps / "01_loaded.csv")
    _csv(result.aligned, steps / "02_calendar.csv")
    _csv(result.validated, steps / "03_validated.csv")
    _csv(result.observations, steps / "04_transformed.csv")
    _csv(result.observations, out / "observations.csv")
    _csv(result.quality, out / "quality_report.csv")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--today", type=dt.date.fromisoformat, default=dt.date.today(),
                        help="date the freshness check (M4) is measured against; default today")
    parser.add_argument("--out", type=Path, default=paths.DATA_OUT, help="output folder; default EarlyWarning/data")
    args = parser.parse_args(argv)

    run_time = dt.datetime.now()
    out: Path = args.out
    try:
        result = pipeline(args.today)
    except ValidationStop as stop:
        text = write_log_txt(stop.findings, out / "validation_log.txt", run_time, args.today)
        write_log_csv(stop.findings, out / "validation_log.csv", run_time)
        print("\n".join(text.splitlines()[:4]))
        print(f"Log: {out / 'validation_log.txt'}")
        return 1

    write_outputs(result, out)
    series_counts = result.inventory["frequency"].value_counts().to_dict()
    text = write_log_txt(
        result.findings, out / "validation_log.txt", run_time, args.today,
        series_counts=series_counts, flag_counts=validate.flag_counts(result.validated),
    )
    write_log_csv(result.findings, out / "validation_log.csv", run_time)
    print("\n".join(text.splitlines()[:4]))
    print(f"Rows written: {len(result.observations):,} -> {out / 'observations.csv'}")
    print(f"Log: {out / 'validation_log.txt'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
