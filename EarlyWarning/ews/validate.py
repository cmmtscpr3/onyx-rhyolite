"""Step 3 -- the gate between the raw files and everything else.

Each check answers one question about the data and records a finding:

* **STOP** -- the data is unusable; the run writes no data files.
* **WARN** -- usable but suspicious; logged for review.
* **INFO** -- recorded only.

Two passes:

* :func:`check_loaded` runs on the readings as loaded: file structure (S1-S3),
  units (U1, U2), non-numbers (Z5), series coverage (M5, M6), and duplicate
  dates (D1, D2), which it resolves.
* :func:`check_aligned` runs on the regular timeline from ``calendar``:
  missing periods (M1-M4), the final duplicate guard (D4), zeros/negatives
  (Z1), hidden unit switches (U3), and one-off spikes (U4).  It then applies
  ``data_issues.csv`` and marks the latest periods provisional.

See ``DataFoundation/VALIDATION_CALENDAR.md`` for the reasoning behind each check.
"""

from __future__ import annotations

import datetime as dt
import math
from pathlib import Path

import numpy as np
import pandas as pd

from . import paths
from .calendar import iso_monday
from .findings import INFO, STOP, WARN, Findings
from .inventory import KNOWN_EXCLUDED
from .load import GROUPS, Loaded, normalise

# Thresholds (see VALIDATION_CALENDAR.md, part A)
LONG_GAP = 3                 # M2: periods
MAX_MISSING_SHARE = 0.05     # M3
PROVISIONAL_PERIODS = 2      # latest periods the sources still revise
SPIKE_Z = 8.0                # U4: robust z of the change
SPIKE_FLOOR = 0.01           # U4: minimum spread of log changes (1%)
SPIKE_REVERSAL = 0.5         # U4: next change undoes at least half
UNIT_JUMPS = tuple(math.log(10 ** k) for k in (1, 2, 3))   # U3: x10, x100, x1000
UNIT_TOLERANCE = 0.3         # U3: in log units
UNIT_PERSIST = 3             # U3: periods the new level must hold

FLAG_ORDER = ("missing", "masked_error", "review", "provisional", "ok")


# ---------------------------------------------------------------------------
# Pass 1: as loaded

def check_loaded(loaded: Loaded, inventory: pd.DataFrame, findings: Findings) -> pd.DataFrame:
    """Structure, units, numbers and coverage; resolves duplicate dates. Returns de-duplicated readings."""
    frame = loaded.frame
    _check_pihps_structure(loaded, findings)
    _check_numbers(frame, findings)
    _check_units(frame, inventory, findings)
    _check_monthly_dates(frame, findings)
    _check_coverage(frame, inventory, loaded.extra_ids, findings)
    return _dedupe_source_dates(frame, findings)


def _check_pihps_structure(loaded: Loaded, findings: Findings) -> None:
    expected = [normalise(name) for name, _ in GROUPS]
    for info in loaded.pihps_files:
        # U2: prices must be in rupiah
        if "rp" not in normalise(info.commodity_header):
            findings.add("U2", STOP, f"{info.path}: header reads {info.commodity_header!r}, expected 'Komoditas (Rp)'")
        # S1: the 10 commodity groups, by name
        found = [normalise(name) for name in info.group_names]
        if sorted(found) != sorted(expected):
            missing = sorted(set(expected) - set(found))
            extra = sorted(set(found) - set(expected))
            findings.add(
                "S1", STOP,
                f"{info.path}: commodity groups do not match the expected 10 "
                f"(missing: {missing or 'none'}; unexpected: {extra or 'none'})",
            )
        # S2: every week header is a date
        for cell in info.bad_header_cells:
            findings.add("S2", STOP, f"{info.path}: header cell {cell!r} is not a date")


def _check_numbers(frame: pd.DataFrame, findings: Findings) -> None:
    """Z5: text that is neither a number nor a recognised 'missing' mark."""
    blank = frame["raw_text"].fillna("").astype(str).str.strip().isin(["", "-"])
    bad = frame[frame["raw_value"].isna() & ~blank]
    for row in bad.itertuples():
        findings.add("Z5", STOP, f"value {row.raw_text!r} is not a number ({row.source_file})", row.series_id, row.source_date)


def _check_units(frame: pd.DataFrame, inventory: pd.DataFrame, findings: Findings) -> None:
    """U1: the unit label in the SPIP files must match the inventory."""
    spip = frame[~frame["series_id"].str.startswith("pihps.")]
    for (series_id, unit), group in spip.groupby(["series_id", "unit"]):
        expected = inventory.loc[series_id, "unit"]
        if unit != expected:
            findings.add(
                "U1", STOP,
                f"unit is {unit!r} in the file but {expected!r} in the inventory ({len(group)} rows)",
                series_id, group["source_date"].min(),
            )


def _check_monthly_dates(frame: pd.DataFrame, findings: Findings) -> None:
    """S3: monthly dates must parse and fall on the 1st of the month."""
    monthly = frame[frame["frequency"] == "monthly"]
    bad = monthly[monthly["source_date"].isna() | (monthly["source_date"].dt.day != 1)]
    for row in bad.itertuples():
        findings.add("S3", STOP, "monthly date is missing or not the 1st of the month", row.series_id, row.source_date)


def _check_coverage(frame: pd.DataFrame, inventory: pd.DataFrame, extra_ids: set[str], findings: Findings) -> None:
    present = set(frame["series_id"])
    for series_id in inventory.index:
        if series_id not in present:
            findings.add("M5", STOP, "series in the inventory was not found in its source file", series_id)
    for series_id in sorted(extra_ids):
        if series_id in KNOWN_EXCLUDED:
            findings.add("M6", INFO, f"left out on purpose: {KNOWN_EXCLUDED[series_id]}", series_id)
        else:
            findings.add("M6", WARN, "new series in the source file, not in the inventory (ignored)", series_id)


def _dedupe_source_dates(frame: pd.DataFrame, findings: Findings) -> pd.DataFrame:
    """D1/D2: one reading per series per source date.

    Preference: the file whose year matches the date (the Traditional Market
    2023 workbook repeats all of 2024), then a reading that has a value.
    """
    frame = frame.copy()
    frame["_year_match"] = frame["file_year"] == frame["source_date"].dt.year
    frame["_has_value"] = frame["raw_value"].notna()
    dup_mask = frame.duplicated(["series_id", "source_date"], keep=False)
    dups = frame[dup_mask]

    if not dups.empty:
        same_counts: dict[tuple[str, str], int] = {}
        for (series_id, date), group in dups.groupby(["series_id", "source_date"]):
            values = group["raw_value"].dropna().unique()
            files = " vs ".join(sorted(group["source_file"].map(lambda p: Path(p).name).unique()))
            if len(values) > 1:
                findings.add(
                    "D2", WARN,
                    f"conflicting values {', '.join(f'{v:g}' for v in sorted(values))} ({files}); "
                    f"kept the file whose year matches the date",
                    series_id, date,
                )
            else:
                same_counts[(series_id, files)] = same_counts.get((series_id, files), 0) + 1
        for (series_id, files), n in sorted(same_counts.items()):
            findings.add("D1", INFO, f"{n} dates repeated with the same value ({files}); kept one copy", series_id)

    frame = frame.sort_values(["series_id", "source_date", "_year_match", "_has_value"], kind="stable")
    frame = frame.drop_duplicates(["series_id", "source_date"], keep="last")
    return frame.drop(columns=["_year_match", "_has_value"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Pass 2: on the regular timeline

def expected_latest(frequency: str, today: dt.date) -> pd.Timestamp:
    """The newest period each source should have by ``today`` (check M4).

    * PIHPS is collected every Saturday; that run fills the week it falls in.
    * BI SPIP publishes month M around the 15th of month M+2.
    """
    today = pd.Timestamp(today)
    if frequency == "weekly":
        last_saturday = today - pd.Timedelta(days=(today.weekday() - 5) % 7)
        return iso_monday(last_saturday)
    anchor = today - pd.Timedelta(days=15)
    return pd.Timestamp(anchor.year, anchor.month, 1) - pd.DateOffset(months=2)


def _runs(missing: np.ndarray) -> list[tuple[int, int]]:
    """(start index, length) of each run of True."""
    runs, start = [], None
    for i, flag in enumerate(missing):
        if flag and start is None:
            start = i
        elif not flag and start is not None:
            runs.append((start, i - start))
            start = None
    if start is not None:
        runs.append((start, len(missing) - start))
    return runs


def _check_missing(series_id: str, group: pd.DataFrame, today: dt.date, findings: Findings) -> None:
    missing = group["raw_value"].isna().to_numpy()
    dates = group["ref_date"].to_numpy()
    n_missing = int(missing.sum())
    if n_missing:
        listed = ", ".join(pd.Timestamp(d).strftime("%Y-%m-%d") for d in dates[missing][:10])
        more = f" (+{n_missing - 10} more)" if n_missing > 10 else ""
        findings.add("M1", INFO, f"{n_missing} missing period(s): {listed}{more}", series_id)
    for start, length in _runs(missing):
        if length > LONG_GAP:
            findings.add("M2", WARN, f"{length} periods missing in a row", series_id, pd.Timestamp(dates[start]))
    share = n_missing / len(group)
    if share > MAX_MISSING_SHARE:
        findings.add("M3", WARN, f"{share:.1%} of periods missing (limit {MAX_MISSING_SHARE:.0%})", series_id)
    frequency = group["frequency"].iloc[0]
    with_value = group.loc[group["raw_value"].notna(), "ref_date"]
    latest = with_value.max() if not with_value.empty else pd.NaT
    expected = expected_latest(frequency, today)
    if pd.isna(latest):
        findings.add("M4", WARN, "series has no values at all", series_id)
    elif latest < expected:
        findings.add(
            "M4", WARN,
            f"latest value is {latest:%Y-%m-%d}, expected {expected:%Y-%m-%d} by {today:%Y-%m-%d} (feed may be stale)",
            series_id, latest,
        )


def _check_jumps(series_id: str, group: pd.DataFrame, findings: Findings) -> None:
    """U3 (unit switch that persists) and U4 (one-off spike that reverses), on log changes."""
    values = group["raw_value"].to_numpy(dtype=float)
    dates = group["ref_date"].to_numpy()
    with np.errstate(divide="ignore", invalid="ignore"):
        x = np.where(values > 0, np.log(values), np.nan)
    d = np.diff(x)                              # d[i] = change from period i to i+1
    finite = d[np.isfinite(d)]
    if finite.size < 10:
        return

    # U3: a step of about x10 / x100 / x1000 whose new level holds.
    for i, step in enumerate(d):
        if not np.isfinite(step):
            continue
        for jump in UNIT_JUMPS:
            if abs(abs(step) - jump) <= UNIT_TOLERANCE:
                after = x[i + 1: i + 1 + UNIT_PERSIST]
                if after.size == UNIT_PERSIST and np.all(np.abs(after - x[i] - step) <= UNIT_TOLERANCE):
                    factor = f"x{math.exp(jump):,.0f}"
                    direction = "up" if step > 0 else "down"
                    findings.add(
                        "U3", WARN,
                        f"level steps {direction} about {factor} (actual x{math.exp(abs(step)):,.0f}) "
                        f"and stays: possible unit change",
                        series_id, pd.Timestamp(dates[i + 1]),
                    )

    # U4: a big move that comes straight back.
    median = float(np.median(finite))
    spread = max(1.4826 * float(np.median(np.abs(finite - median))), SPIKE_FLOOR)
    for i in range(len(d) - 1):
        now, nxt = d[i], d[i + 1]
        if not (np.isfinite(now) and np.isfinite(nxt)):
            continue
        z = (now - median) / spread
        if abs(z) > SPIKE_Z and np.sign(nxt) == -np.sign(now) and abs(nxt) >= SPIKE_REVERSAL * abs(now):
            findings.add(
                "U4", WARN,
                f"one-off spike: {_pct(now)} then {_pct(nxt)} next period (robust z {z:+.0f}); likely data error",
                series_id, pd.Timestamp(dates[i + 1]),
            )


def _pct(log_change: float) -> str:
    ratio = math.exp(log_change)
    if ratio >= 3 or ratio <= 1 / 3:
        return f"x{ratio:.2g}" if ratio >= 1 else f"/{1 / ratio:.2g}"
    return f"{(ratio - 1) * 100:+.1f}%"


def load_issues(path: Path = paths.DATA_ISSUES) -> pd.DataFrame:
    if not Path(path).exists():
        return pd.DataFrame(columns=["series_id", "ref_date", "action", "reason"])
    issues = pd.read_csv(path, dtype=str, keep_default_na=False, comment="#")
    issues["ref_date"] = pd.to_datetime(issues["ref_date"], format="%Y-%m-%d")
    return issues


def _apply_issues(frame: pd.DataFrame, issues: pd.DataFrame, findings: Findings) -> None:
    """``data_issues.csv``: ``review`` flags a value; ``mask`` blanks it. Weekly dates snap to their Monday."""
    for row in issues.itertuples():
        pattern = row.series_id
        if pattern.endswith("*"):
            in_series = frame["series_id"].str.startswith(pattern[:-1])
        else:
            in_series = frame["series_id"] == pattern
        weekly_date = iso_monday(row.ref_date)
        on_date = ((frame["frequency"] == "weekly") & (frame["ref_date"] == weekly_date)) | (
            (frame["frequency"] == "monthly") & (frame["ref_date"] == row.ref_date)
        )
        hit = in_series & on_date & frame["raw_value"].notna()
        if not hit.any():
            findings.add("I1", WARN, f"data_issues.csv row matches no observation ({row.action}: {row.reason})", pattern, row.ref_date)
            continue
        if row.action == "mask":
            frame.loc[hit, "_masked"] = True
        elif row.action == "review":
            frame.loc[hit, "_review"] = True
        else:
            findings.add("I1", WARN, f"unknown action {row.action!r} in data_issues.csv (use 'review' or 'mask')", pattern, row.ref_date)


def check_aligned(
    aligned: pd.DataFrame,
    findings: Findings,
    today: dt.date,
    issues: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Missing periods, duplicates, zeros, unit switches, spikes; then flags. Returns the validated table."""
    frame = aligned.copy()

    # D4: the final guard
    dup = frame[frame.duplicated(["series_id", "ref_date"], keep=False)]
    for (series_id, date), _ in dup.groupby(["series_id", "ref_date"]):
        findings.add("D4", STOP, "more than one row for this period after alignment", series_id, date)

    # Z1: log needs strictly positive values
    bad = frame[frame["raw_value"].notna() & (frame["raw_value"] <= 0)]
    for row in bad.itertuples():
        findings.add("Z1", STOP, f"value {row.raw_value:g} is zero or negative", row.series_id, row.ref_date)

    for series_id, group in frame.groupby("series_id", sort=True):
        _check_missing(series_id, group, today, findings)
        _check_jumps(series_id, group, findings)

    # Flags
    frame["_masked"] = False
    frame["_review"] = False
    if issues is not None and not issues.empty:
        _apply_issues(frame, issues, findings)

    frame["value"] = frame["raw_value"].where(~frame["_masked"])
    rank = frame[frame["raw_value"].notna()].groupby("series_id")["ref_date"].rank(ascending=False, method="first")
    frame["is_provisional"] = False
    frame.loc[rank.index, "is_provisional"] = rank <= PROVISIONAL_PERIODS

    flag = np.select(
        [frame["raw_value"].isna(), frame["_masked"], frame["_review"], frame["is_provisional"]],
        ["missing", "masked_error", "review", "provisional"],
        default="ok",
    )
    frame["quality_flag"] = flag
    return frame.drop(columns=["_masked", "_review"])


# ---------------------------------------------------------------------------
# Quality report

QUALITY_COLUMNS = (
    "series_id", "frequency", "start", "end", "n_expected", "n_values", "n_missing", "pct_missing",
    "longest_gap", "n_review", "n_masked", "n_provisional", "confidence",
)


def _confidence(frequency: str, n_expected: int, pct_missing: float, longest_gap: int) -> str:
    cycle = 52 if frequency == "weekly" else 12
    if n_expected >= 3 * cycle and pct_missing < 0.05 and longest_gap <= LONG_GAP:
        return "high"
    if n_expected >= 2 * cycle and pct_missing < 0.15:
        return "medium"
    return "low"


def quality_report(validated: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for series_id, group in validated.groupby("series_id", sort=True):
        missing = group["value"].isna().to_numpy()
        runs = _runs(missing)
        longest = max((length for _, length in runs), default=0)
        n = len(group)
        n_missing = int(missing.sum())
        pct = n_missing / n
        frequency = group["frequency"].iloc[0]
        with_value = group.loc[group["value"].notna(), "ref_date"]
        rows.append({
            "series_id": series_id,
            "frequency": frequency,
            "start": with_value.min().strftime("%Y-%m-%d"),
            "end": with_value.max().strftime("%Y-%m-%d"),
            "n_expected": n,
            "n_values": n - n_missing,
            "n_missing": n_missing,
            "pct_missing": round(pct * 100, 2),
            "longest_gap": longest,
            "n_review": int((group["quality_flag"] == "review").sum()),
            "n_masked": int((group["quality_flag"] == "masked_error").sum()),
            "n_provisional": int(group["is_provisional"].sum()),
            "confidence": _confidence(frequency, n, pct, longest),
        })
    return pd.DataFrame(rows, columns=list(QUALITY_COLUMNS))


def flag_counts(validated: pd.DataFrame) -> dict[str, int]:
    counts = validated["quality_flag"].value_counts()
    return {flag: int(counts.get(flag, 0)) for flag in FLAG_ORDER}
