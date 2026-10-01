"""End to end: output files, the log, STOP behaviour, reruns, and Dataset/ left untouched."""

from __future__ import annotations

import hashlib

import pandas as pd

from ews import load, paths, run

from conftest import TODAY

ARGS = ["--today", TODAY.isoformat()]


def _hash_tree(root):
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        digest.update(str(path.relative_to(root)).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def test_run_writes_outputs_and_leaves_dataset_untouched(tmp_path):
    before = _hash_tree(paths.DATASET)
    assert run.main([*ARGS, "--out", str(tmp_path)]) == 0
    assert _hash_tree(paths.DATASET) == before

    for name in ("observations.csv", "quality_report.csv", "validation_log.txt", "validation_log.csv"):
        assert (tmp_path / name).exists(), name
    for name in ("01_loaded.csv", "02_calendar.csv", "03_validated.csv", "04_transformed.csv"):
        assert (tmp_path / "steps" / name).exists(), name

    log = (tmp_path / "validation_log.txt").read_text()
    assert "Result: PASSED" in log
    for section in ("== STOP ==", "== WARN ==", "== INFO ==", "== Flags applied =="):
        assert section in log
    assert "[U4] bi_card_transactions.atm_debit.cards" in log


def test_rerun_is_identical(tmp_path):
    first, second = tmp_path / "a", tmp_path / "b"
    run.main([*ARGS, "--out", str(first)])
    run.main([*ARGS, "--out", str(second)])
    for name in ("observations.csv", "quality_report.csv", "steps/01_loaded.csv"):
        assert (first / name).read_bytes() == (second / name).read_bytes(), name


def test_stop_writes_only_the_log(tmp_path, monkeypatch):
    real = load.load_all

    def with_negative(inventory):
        loaded = real(inventory)
        frame = loaded.frame
        index = frame.index[frame["series_id"] == "bi_emoney.value"][5]
        frame.loc[index, ["raw_text", "raw_value"]] = ["-5", -5.0]
        return loaded

    monkeypatch.setattr(load, "load_all", with_negative)
    assert run.main([*ARGS, "--out", str(tmp_path)]) == 1
    assert sorted(p.name for p in tmp_path.iterdir()) == ["validation_log.csv", "validation_log.txt"]
    log = (tmp_path / "validation_log.txt").read_text()
    assert "Result: STOPPED" in log and "[Z1] bi_emoney.value" in log

    entries = pd.read_csv(tmp_path / "validation_log.csv")
    assert (entries["severity"] == "STOP").any()
