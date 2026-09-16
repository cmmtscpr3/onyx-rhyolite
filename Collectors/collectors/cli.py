"""The runner.

One command per indicator, so a schedule can call the weekly one weekly and
the monthly one monthly:

    python Collectors/run.py food_prices                  # current year, 3 markets
    python Collectors/run.py food_prices --year 2025       # deliberate backfill
    python Collectors/run.py consumption --only bi_seki
    python Collectors/run.py all --dry-run                 # diff, write nothing

Nothing is written until a collector has parsed successfully, and every file is
copied into ``Dataset/Backup/<run stamp>/`` immediately before it is first
changed.  A collector that cannot read its source fails that source alone and
leaves every dataset untouched.
"""

from __future__ import annotations

import argparse
import datetime as dt
import inspect
import sys
from typing import Callable

from . import paths
from .errors import SourceUnavailable
from .http import session
from .sinks.backup import Backups
from .sources import bi_consumer_survey, bi_seki, bi_spip, ibid, magpieiq, ojk_dpk
from .sources import pihps, qris

#: Collector name -> the function that runs it.
COLLECTORS: dict[str, Callable] = {
    "pihps": pihps.collect,
    "bi_spip": bi_spip.collect,
    "bi_seki": bi_seki.collect,
    "bi_consumer_survey": bi_consumer_survey.collect,
    "ojk_dpk": ojk_dpk.collect,
    "qris": qris.collect,
    "magpieiq": magpieiq.collect,
    "ibid": ibid.collect,
}

#: Indicator -> the collectors that feed it.
INDICATORS: dict[str, tuple[str, ...]] = {
    "food_prices": ("pihps",),
    "consumption": (
        "bi_spip",
        "bi_seki",
        "bi_consumer_survey",
        "ojk_dpk",
        "qris",
        "magpieiq",
    ),
    "vehicle_listings": ("ibid",),
}

#: Indicators `all` skips, because they cost far more than everything else put
#: together: the ibid scrape drives a browser over a few hundred pages and took
#: 45 minutes against about 4 for the rest.  A cheap `all` is one people
#: actually run, so these are opt-in.  They stay in INDICATORS so that
#: `run.py vehicle_listings` still works and the positional choices are
#: unchanged.
OPT_IN: frozenset[str] = frozenset({"vehicle_listings"})

#: Cadence -> the collectors that run on it.  The schedule lives here rather
#: than in the workflow files, so `run.py weekly` is exactly what the cron runs
#: and a new collector is slotted in one place.
GROUPS: dict[str, tuple[str, ...]] = {
    "weekly": ("pihps", "ibid"),
    "monthly": ("bi_spip", "bi_seki", "bi_consumer_survey", "ojk_dpk", "magpieiq"),
    # Reserved.  There is no BPS source module yet, so this reports the same
    # BPS_API_KEY message as `unemployment` instead of failing; the cron exists
    # so that adding the collector is one module plus one entry here.  Note
    # bi_seki already carries the BPS quarterly national accounts on the
    # monthly run -- what is missing is Sakernas.
    "quarterly": (),
}

#: Collectors deliberately left off every schedule, and why.  Keeping them
#: named means the "nothing went unscheduled" test can tell a considered
#: omission from an oversight.
UNSCHEDULED: dict[str, str] = {
    "qris": (
        "ASPI blocks datacentre addresses, so a scheduled run could only ever "
        "log the block; run it by hand with --html against a saved page"
    ),
}

#: Requested, but not collectable yet.  Sakernas is published only through the
#: BPS WebAPI, which needs a free key from webapi.bps.go.id/developer, and the
#: BPS website answers 403 from a foreign runner, so there is no second route.
#: Named here so `all` can say so out loud instead of quietly skipping it.
DEFERRED: dict[str, str] = {
    "unemployment": (
        "BPS Sakernas needs BPS_API_KEY (free from webapi.bps.go.id/developer); "
        "no collector is installed yet"
    ),
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="Collectors",
        description="Update the datasets under Dataset/ from their published sources.",
    )
    parser.add_argument(
        "target",
        nargs="?",
        default="all",
        choices=sorted({"all", *INDICATORS, *GROUPS, *DEFERRED}),
        help="which indicator to update (default: all)",
    )
    parser.add_argument(
        "--only",
        action="append",
        metavar="NAME",
        choices=sorted(COLLECTORS),
        help="restrict to one collector; repeatable",
    )
    parser.add_argument(
        "--year",
        action="append",
        type=int,
        metavar="YYYY",
        help="food prices: which year's workbook to update; repeatable (default: this year)",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        metavar="N",
        help="ibid: stop after N pages per category (default: walk to the end)",
    )
    parser.add_argument(
        "--html",
        metavar="PATH",
        help="qris: parse a page saved from a browser instead of fetching it",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="re-read all history instead of only what is missing from the datasets",
    )
    parser.add_argument(
        "--overlap",
        type=int,
        metavar="N",
        help="periods of already-collected history to re-read anyway (default: 3)",
    )
    parser.add_argument(
        "--since",
        type=dt.date.fromisoformat,
        metavar="YYYY-MM-DD",
        help="ignore observations before this date",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report what would change and write nothing",
    )
    parser.add_argument("--no-backup", action="store_true", help="do not snapshot before writing")
    parser.add_argument(
        "--keep",
        type=int,
        metavar="N",
        help="after writing, keep only the newest N backup snapshots",
    )
    parser.add_argument("--verbose", action="store_true", help="list every revision")
    return parser


def _options(collect, args: argparse.Namespace, *, sess, backups) -> dict:
    """The keyword arguments one collector accepts, from its own signature.

    Collectors differ in what they can be narrowed by -- PIHPS takes whole
    years, most take a ``since`` date, QRIS can read a saved page, and ibid
    takes neither -- so the run loop asks each function what it accepts rather
    than testing its name.
    """
    options = {"sess": sess, "dry_run": args.dry_run, "backups": backups}
    accepted = inspect.signature(collect).parameters
    for flag, value in (
        ("years", args.year),
        ("since", args.since),
        ("html", args.html),
        ("max_pages", args.max_pages),
        ("full", args.full),
        ("overlap", args.overlap),
    ):
        if flag in accepted and value:
            options[flag] = value
    return options


def _selected(args: argparse.Namespace) -> list[str]:
    if args.only:
        return list(dict.fromkeys(args.only))
    if args.target == "all":
        return [
            name
            for indicator, names in INDICATORS.items()
            if indicator not in OPT_IN
            for name in names
        ]
    if args.target in GROUPS:
        return list(GROUPS[args.target])
    return list(INDICATORS.get(args.target, ()))


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.target in DEFERRED and not args.only:
        print(f"{args.target}: not available -- {DEFERRED[args.target]}")
        return 0

    names = _selected(args)
    if not names:
        if args.target in GROUPS:
            reason = DEFERRED.get("unemployment", "no collector is installed yet")
            print(f"{args.target}: nothing scheduled yet -- {reason}")
        else:
            print(f"nothing to do for {args.target!r}")
        return 0

    if args.target == "all" and not args.only:
        # Said out loud, because a silent omission reads as a bug the first time
        # someone expects fresh listings from `all`.
        for indicator in sorted(OPT_IN):
            print(f"-- skipping {indicator} (slow); run it with: run.py {indicator}")

    backups = Backups(stamp=paths.run_stamp(), enabled=not args.no_backup)
    sess = session()
    failures: list[str] = []
    wrote = False

    for name in names:
        print(f"== {name}")
        collect = COLLECTORS[name]
        try:
            reports = collect(**_options(collect, args, sess=sess, backups=backups))
        except SourceUnavailable as exc:
            # Not a failure: the source has nothing to give right now.
            print(f"   skipped: {exc}")
            continue
        except Exception as exc:  # noqa: BLE001 - reported per source, not swallowed
            # One source failing must not stop the others, and must not leave a
            # half-written file: every sink writes once, at the end, or not at all.
            failures.append(name)
            print(f"   FAILED: {type(exc).__name__}: {exc}")
            continue

        for report in reports:
            print(f"   {report.describe()}")
            wrote = wrote or getattr(report, "written", False)
            for warning in getattr(report, "warnings", []):
                print(f"   warning: {warning}")
            if args.verbose:
                for revision in getattr(report, "revisions", [])[:50]:
                    print(f"      revised {revision[0]} {revision[1]}: {revision[2]} -> {revision[3]}")

    if args.dry_run:
        print("\ndry run: nothing written")
    elif not wrote:
        print("\nno changes; nothing written and no backup taken")
    elif backups.taken:
        where = backups.directory.relative_to(paths.REPO_ROOT)
        print(f"\n{len(backups.taken)} previous version(s) saved to {where}")
        for stale in backups.prune(args.keep):
            print(f"pruned old snapshot {stale.name}")
    else:
        # Everything written was a brand-new file, so there was no previous
        # version to keep.  Saying otherwise would point at a directory that
        # does not exist.
        print("\nwrote new file(s); no existing data was replaced, so no backup was needed")

    if failures:
        print(f"\nfailed: {', '.join(failures)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
