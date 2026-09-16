"""The runner's collector selection.

One rule here is load-bearing and easy to break by accident: `all` is meant to
be cheap enough to run habitually, so the ibid scrape -- 45 minutes of browser
against about 4 for everything else -- is excluded from it while staying a
valid target of its own.
"""

from __future__ import annotations

import pytest

from collectors import cli


def _select(*argv: str) -> list[str]:
    return cli._selected(cli.build_parser().parse_args(list(argv)))


def test_all_excludes_the_slow_scrape_but_keeps_everything_else():
    selected = _select("all")
    assert "ibid" not in selected
    cheap = [
        name
        for indicator, names in cli.INDICATORS.items()
        if indicator not in cli.OPT_IN
        for name in names
    ]
    assert selected == cheap


def test_all_is_the_default_target():
    assert _select() == _select("all")


def test_the_opt_in_indicator_is_still_a_target_of_its_own():
    """Excluding it from `all` must not remove the command that runs it."""
    assert _select("vehicle_listings") == ["ibid"]
    assert "vehicle_listings" in cli.build_parser().parse_args(["vehicle_listings"]).target


@pytest.mark.parametrize("target", ["all", "consumption", "food_prices"])
def test_only_overrides_the_target(target):
    """`--only ibid` has to work whichever target it is paired with."""
    assert _select(target, "--only", "ibid") == ["ibid"]


def test_only_preserves_order_and_drops_duplicates():
    assert _select("--only", "bi_seki", "--only", "pihps", "--only", "bi_seki") == [
        "bi_seki",
        "pihps",
    ]


def test_every_indicator_names_collectors_that_exist():
    """Catches a rename that would silently drop a collector from every run."""
    for indicator, names in cli.INDICATORS.items():
        assert names, indicator
        for name in names:
            assert name in cli.COLLECTORS, f"{indicator} -> {name}"


def test_every_collector_is_reachable_from_some_indicator():
    """A collector in no indicator could only ever run via --only."""
    wired = {name for names in cli.INDICATORS.values() for name in names}
    assert wired == set(cli.COLLECTORS)


def test_opt_in_names_real_indicators():
    assert cli.OPT_IN <= set(cli.INDICATORS)


def test_a_deferred_indicator_explains_itself_and_does_not_fail(capsys):
    """Unemployment has no collector yet; it should say why, not error."""
    assert cli.main(["unemployment"]) == 0
    out = capsys.readouterr().out
    assert "not available" in out and "BPS_API_KEY" in out


def test_all_announces_what_it_skipped(capsys, monkeypatch):
    """A silent omission reads as a bug the first time listings look stale.

    The collectors are stubbed so this asserts the real printed output without
    touching the network.
    """

    class Report:
        written = False
        warnings: list = []
        revisions: list = []

        def describe(self) -> str:
            return "stub: no change"

    ran: list[str] = []

    def stub(name):
        def collect(**_options):
            ran.append(name)
            return [Report()]

        return collect

    monkeypatch.setattr(cli, "COLLECTORS", {n: stub(n) for n in cli.COLLECTORS})

    assert cli.main(["all", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "skipping vehicle_listings (slow)" in out
    assert "run.py vehicle_listings" in out
    assert "ibid" not in ran


def test_an_explicit_target_does_not_announce_a_skip(capsys, monkeypatch):
    """The notice belongs to `all`; asking for one indicator is not a surprise."""

    class Report:
        written = False
        warnings: list = []
        revisions: list = []

        def describe(self) -> str:
            return "stub: no change"

    monkeypatch.setattr(
        cli, "COLLECTORS", {n: (lambda **_o: [Report()]) for n in cli.COLLECTORS}
    )
    assert cli.main(["vehicle_listings", "--dry-run"]) == 0
    assert "skipping" not in capsys.readouterr().out


# ------------------------------------------------------------- the schedule


def test_the_cadence_groups_select_what_the_cron_will_run():
    assert _select("weekly") == ["pihps", "ibid"]
    assert _select("monthly") == [
        "bi_spip",
        "bi_seki",
        "bi_consumer_survey",
        "ojk_dpk",
        "magpieiq",
    ]


def test_every_collector_is_either_scheduled_or_deliberately_not():
    """The test that earns its keep.

    A collector belonging to no cadence is invisible until someone notices a
    stale dataset months later, so a new one must be put in a group or listed
    in UNSCHEDULED with a reason.
    """
    scheduled = {name for names in cli.GROUPS.values() for name in names}
    accounted = scheduled | set(cli.UNSCHEDULED)
    assert accounted == set(cli.COLLECTORS), set(cli.COLLECTORS) ^ accounted


def test_no_collector_is_scheduled_on_two_cadences():
    seen: set[str] = set()
    for names in cli.GROUPS.values():
        for name in names:
            assert name not in seen, name
            seen.add(name)


def test_every_scheduled_name_is_a_real_collector():
    for cadence, names in cli.GROUPS.items():
        for name in names:
            assert name in cli.COLLECTORS, f"{cadence} -> {name}"


def test_qris_is_the_only_unscheduled_collector_and_says_why():
    """ASPI blocks datacentre addresses, so a cron could only log the block."""
    assert set(cli.UNSCHEDULED) == {"qris"}
    assert "datacentre" in cli.UNSCHEDULED["qris"]
    assert "qris" not in {n for names in cli.GROUPS.values() for n in names}


def test_the_quarterly_group_is_reserved_and_explains_itself(capsys):
    """No BPS module exists, so it must say so rather than fail or go quiet."""
    assert cli.GROUPS["quarterly"] == ()
    assert cli.main(["quarterly"]) == 0
    out = capsys.readouterr().out
    assert "nothing scheduled yet" in out and "BPS_API_KEY" in out


def test_the_cadences_are_valid_targets_and_only_still_overrides_them():
    for cadence in cli.GROUPS:
        assert cli.build_parser().parse_args([cadence]).target == cadence
    assert _select("weekly", "--only", "bi_seki") == ["bi_seki"]


def test_full_and_overlap_reach_the_collectors_that_accept_them():
    """They are threaded by signature, so a collector that ignores them is fine."""
    args = cli.build_parser().parse_args(["monthly", "--full", "--overlap", "6"])
    options = cli._options(cli.COLLECTORS["bi_seki"], args, sess=None, backups=None)
    assert options["full"] is True and options["overlap"] == 6
    # magpieiq takes neither; passing them would be a TypeError.
    assert "full" not in cli._options(cli.COLLECTORS["magpieiq"], args, sess=None, backups=None)
