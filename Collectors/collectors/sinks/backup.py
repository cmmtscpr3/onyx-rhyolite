"""Snapshot a dataset file before the first write of a run.

One directory per run, named for the run's UTC start, holding the *previous*
contents of every file that run went on to change:

    Dataset/Backup/2026-09-15T053946Z/Consumption/bi_emoney.csv
    Dataset/Backup/2026-09-15T053946Z/Food Prices/PIHPS/Wholesale/... 2026.xlsx

Paths under the snapshot mirror their paths under ``Dataset/``.  That is a
deliberate change from the flattened layout of the hand-made backup already in
the repository: flattening drops the category directory, so
``Consumption/bi_seki.csv`` and a future ``Unemployment/bi_seki.csv`` would
collide.  The existing flat files are left alone.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from .. import paths


@dataclass
class Backups:
    """Snapshots taken during one run."""

    stamp: str
    root: Path = field(default_factory=lambda: paths.BACKUP)
    enabled: bool = True
    taken: dict[Path, Path] = field(default_factory=dict)

    @property
    def directory(self) -> Path:
        return self.root / self.stamp

    def snapshot(self, target: Path) -> Path | None:
        """Copy ``target`` aside, once per run.  ``None`` when there is nothing to copy.

        Called immediately before a write, not at the start of the run, so a
        collector that finds no new data leaves no snapshot behind and quiet
        weeks do not accumulate identical copies.
        """
        target = Path(target)
        if not self.enabled or target in self.taken or not target.exists():
            return self.taken.get(target)
        try:
            relative = target.resolve().relative_to(paths.DATASET.resolve())
        except ValueError:
            relative = Path(target.name)
        destination = self.directory / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, destination)
        self.taken[target] = destination
        return destination

    def prune(self, keep: int | None) -> list[Path]:
        """Drop the oldest snapshot directories, keeping the newest ``keep``.

        Names sort chronologically because the stamp is ``%Y-%m-%dT%H%M%SZ``.
        """
        if not keep or keep < 1 or not self.root.exists():
            return []
        existing = sorted(
            (child for child in self.root.iterdir() if child.is_dir() and _is_stamp(child.name)),
            key=lambda child: child.name,
        )
        removed = []
        for stale in existing[:-keep]:
            shutil.rmtree(stale)
            removed.append(stale)
        return removed


#: Matches the stamp format this tool writes and nothing else, so pruning can
#: never reach the hand-made flat backup already in the repository.
_STAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{6}Z$")


def _is_stamp(name: str) -> bool:
    """Only prune directories this tool created, never the hand-made backup."""
    return bool(_STAMP.match(name))
