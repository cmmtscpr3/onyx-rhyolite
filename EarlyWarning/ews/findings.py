"""Validation findings, and the log files written from them."""

from __future__ import annotations

import csv
import datetime as dt
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

STOP, WARN, INFO = "STOP", "WARN", "INFO"
SEVERITIES = (STOP, WARN, INFO)


@dataclass(frozen=True)
class Finding:
    check_id: str
    severity: str
    series_id: str
    ref_date: str
    message: str


class ValidationStop(RuntimeError):
    """Raised when at least one STOP finding means the data must not be used."""

    def __init__(self, findings: "Findings"):
        self.findings = findings
        stops = [f for f in findings.items if f.severity == STOP]
        lines = "\n".join(f"[{f.check_id}] {f.series_id} {f.ref_date} {f.message}".strip() for f in stops)
        super().__init__(f"{len(stops)} STOP finding(s):\n{lines}")


@dataclass
class Findings:
    """Collects findings across all steps of one run."""

    items: list[Finding] = field(default_factory=list)

    def add(self, check_id: str, severity: str, message: str, series_id: str = "", ref_date: object = "") -> None:
        if severity not in SEVERITIES:
            raise ValueError(f"unknown severity {severity!r}")
        self.items.append(Finding(check_id, severity, series_id, _date_text(ref_date), message))

    def count(self, severity: str) -> int:
        return sum(1 for f in self.items if f.severity == severity)

    @property
    def has_stop(self) -> bool:
        return self.count(STOP) > 0

    def raise_on_stop(self) -> None:
        if self.has_stop:
            raise ValidationStop(self)

    def sorted(self) -> list[Finding]:
        order = {s: i for i, s in enumerate(SEVERITIES)}
        return sorted(self.items, key=lambda f: (order[f.severity], f.check_id, f.series_id, f.ref_date))


def _date_text(value: object) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, (dt.date, dt.datetime)):
        return value.strftime("%Y-%m-%d")
    if hasattr(value, "strftime"):  # pandas Timestamp
        return value.strftime("%Y-%m-%d")
    return str(value)


# ---------------------------------------------------------------------------
# Log files

LOG_COLUMNS = ("run_time", "check_id", "severity", "series_id", "ref_date", "message")


def write_log_csv(findings: Findings, path: Path, run_time: dt.datetime) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    stamp = run_time.strftime("%Y-%m-%d %H:%M:%S")
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(LOG_COLUMNS)
        for f in findings.sorted():
            writer.writerow((stamp, f.check_id, f.severity, f.series_id, f.ref_date, f.message))


def write_log_txt(
    findings: Findings,
    path: Path,
    run_time: dt.datetime,
    today: dt.date,
    series_counts: dict[str, int] | None = None,
    flag_counts: dict[str, int] | None = None,
) -> str:
    """The readable log: summary, then findings grouped by severity and check."""
    lines = [f"EWS validation run - {run_time:%Y-%m-%d %H:%M} (data checked as of {today:%Y-%m-%d})"]
    if series_counts:
        total = sum(series_counts.values())
        parts = ", ".join(f"{n} {freq}" for freq, n in sorted(series_counts.items(), reverse=True))
        lines.append(f"Series checked: {total} ({parts})")
    result = "STOPPED" if findings.has_stop else "PASSED"
    lines.append(
        f"Result: {result} ({findings.count(STOP)} STOP, {findings.count(WARN)} WARN, {findings.count(INFO)} INFO)"
    )
    if findings.has_stop:
        lines.append("No data files were written. Fix the STOP items below and run again.")
    lines.append("")

    by_check = Counter(f.check_id for f in findings.items)
    if by_check:
        lines.append("Findings per check: " + ", ".join(f"{c} {n}" for c, n in sorted(by_check.items())))
        lines.append("")

    width = max((len(f.series_id) for f in findings.items), default=0)
    for severity in SEVERITIES:
        group = [f for f in findings.sorted() if f.severity == severity]
        lines.append(f"== {severity} ==" + ("  (none)" if not group else ""))
        for f in group:
            series = f.series_id.ljust(width) if f.series_id else "(all)".ljust(width)
            date = f.ref_date.ljust(10) if f.ref_date else " " * 10
            lines.append(f"[{f.check_id}] {series}  {date}  {f.message}")
        lines.append("")

    if flag_counts:
        lines.append("== Flags applied ==")
        lines.append(" | ".join(f"{flag} {n}" for flag, n in flag_counts.items()))
        lines.append("")

    text = "\n".join(lines)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return text
