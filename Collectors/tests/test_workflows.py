"""The scheduler's GitHub Actions workflows.

A typo in a cron expression or a missing permission fails silently at 02:00 on
a Saturday, so the shape of these files is asserted rather than eyeballed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

from collectors import cli
from collectors.paths import REPO_ROOT

WORKFLOWS = sorted((REPO_ROOT / ".github" / "workflows").glob("collect-*.yml"))
#: The branch the datasets live on, and the one the workflows must land on.
BRANCH = "main"


def _load(path: Path) -> dict:
    document = yaml.safe_load(path.read_text())
    # PyYAML reads a bare `on:` key as the boolean True.
    document["on"] = document.get("on") or document[True]
    return document


def test_there_is_one_workflow_per_cadence():
    assert {path.stem.removeprefix("collect-") for path in WORKFLOWS} == set(cli.GROUPS)


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.stem)
def test_each_workflow_is_scheduled_and_manually_runnable(path):
    triggers = _load(path)["on"]
    cron = triggers["schedule"][0]["cron"]
    assert len(cron.split()) == 5, cron
    assert "workflow_dispatch" in triggers
    assert set(triggers["workflow_dispatch"]["inputs"]) == {"dry_run", "full"}


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.stem)
def test_each_workflow_may_write_and_never_runs_twice_at_once(path):
    document = _load(path)
    # Without write permission the commit step fails after doing all the work.
    assert document["permissions"]["contents"] == "write"
    # Two overlapping runs would write the same dataset files.
    assert document["concurrency"]["group"] == path.stem
    assert document["concurrency"]["cancel-in-progress"] is False


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.stem)
def test_each_workflow_targets_the_dataset_branch(path):
    """A run must land on the dataset branch, not on whatever branch it was
    dispatched from, and must name that branch rather than leave it to the
    trigger -- naming it is what a migration between repositories breaks."""
    document = _load(path)
    assert document["env"]["TARGET_BRANCH"] == BRANCH
    checkout = document["jobs"]["collect"]["steps"][0]
    assert checkout["with"]["ref"] == "${{ env.TARGET_BRANCH }}"
    # A shallow clone cannot rebase before pushing.
    assert checkout["with"]["fetch-depth"] == 0


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.stem)
def test_each_workflow_runs_its_own_cadence(path):
    cadence = path.stem.removeprefix("collect-")
    steps = _load(path)["jobs"]["collect"]["steps"]
    collect = next(s for s in steps if s.get("name") == "Collect")
    assert f"run.py {cadence}" in collect["run"]


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.stem)
def test_the_commit_step_touches_only_the_datasets(path):
    steps = _load(path)["jobs"]["collect"]["steps"]
    commit = next(s for s in steps if s.get("name") == "Commit refreshed datasets")
    assert "git add Dataset" in commit["run"]
    assert "git add -A" not in commit["run"]
    assert "no dataset changes" in commit["run"]     # a quiet run adds no commit
    assert "--rebase" in commit["run"]               # a manual commit must not break it
    assert "!inputs.dry_run" in commit["if"]


def test_only_the_weekly_run_installs_a_browser():
    """ibid needs one; nothing in the monthly or quarterly group does."""
    for path in WORKFLOWS:
        steps = _load(path)["jobs"]["collect"]["steps"]
        installs = any("playwright install" in str(s.get("run", "")) for s in steps)
        collect = next(s for s in steps if s.get("name") == "Collect")
        wants_browser = path.stem == "collect-weekly"
        assert installs is wants_browser, path.stem
        assert (collect.get("env", {}).get("CHROMIUM_PATH") == "auto") is wants_browser


def test_the_weekly_timeout_allows_for_the_long_scrape():
    """The ibid scrape measured 45 minutes; the others are minutes."""
    timeouts = {
        path.stem: _load(path)["jobs"]["collect"]["timeout-minutes"] for path in WORKFLOWS
    }
    assert timeouts["collect-weekly"] >= 90
    assert timeouts["collect-monthly"] <= 60
