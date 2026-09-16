"""Backups: one timestamped directory per run, holding what was overwritten."""

from __future__ import annotations

import datetime as dt

from collectors import paths
from collectors.sinks.backup import Backups


def test_snapshot_mirrors_the_dataset_path(tmp_path, monkeypatch):
    dataset = tmp_path / "Dataset"
    target = dataset / "Consumption" / "bi_emoney.csv"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"before\r\n")
    monkeypatch.setattr(paths, "DATASET", dataset)

    backups = Backups(stamp="2026-09-15T000000Z", root=dataset / "Backup")
    saved = backups.snapshot(target)
    assert saved == dataset / "Backup" / "2026-09-15T000000Z" / "Consumption" / "bi_emoney.csv"
    assert saved.read_bytes() == b"before\r\n"


def test_a_file_is_snapshotted_once_per_run(tmp_path, monkeypatch):
    dataset = tmp_path / "Dataset"
    target = dataset / "Consumption" / "x.csv"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"first")
    monkeypatch.setattr(paths, "DATASET", dataset)

    backups = Backups(stamp="s", root=dataset / "Backup")
    backups.snapshot(target)
    target.write_bytes(b"second")
    backups.snapshot(target)
    # The snapshot is the state before the run, not before the latest write.
    assert (dataset / "Backup" / "s" / "Consumption" / "x.csv").read_bytes() == b"first"


def test_a_missing_target_is_not_backed_up(tmp_path):
    backups = Backups(stamp="s", root=tmp_path / "Backup")
    assert backups.snapshot(tmp_path / "nope.csv") is None
    assert not (tmp_path / "Backup").exists()


def test_backups_can_be_disabled(tmp_path):
    target = tmp_path / "x.csv"
    target.write_bytes(b"data")
    backups = Backups(stamp="s", root=tmp_path / "Backup", enabled=False)
    assert backups.snapshot(target) is None
    assert not (tmp_path / "Backup").exists()


def test_prune_keeps_the_newest_and_never_touches_the_hand_made_backup(tmp_path):
    root = tmp_path / "Backup"
    for stamp in ("2026-09-01T000000Z", "2026-09-08T000000Z", "2026-09-15T000000Z"):
        (root / stamp).mkdir(parents=True)
    # The pre-existing flattened backup must survive: it is not ours to delete.
    (root / "Traditional Market").mkdir(parents=True)
    (root / "bi_seki.csv").write_bytes(b"x")

    removed = Backups(stamp="new", root=root).prune(keep=2)
    assert [p.name for p in removed] == ["2026-09-01T000000Z"]
    assert (root / "Traditional Market").exists()
    assert (root / "bi_seki.csv").exists()
    assert (root / "2026-09-15T000000Z").exists()


def test_run_stamp_sorts_chronologically():
    early = paths.run_stamp(dt.datetime(2026, 9, 1, tzinfo=dt.timezone.utc))
    late = paths.run_stamp(dt.datetime(2026, 9, 15, tzinfo=dt.timezone.utc))
    assert early < late and len(early) == 18
