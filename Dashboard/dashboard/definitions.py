"""Official definitions, quoted verbatim from the publishers.

Nothing here is paraphrased.  Each entry is the sentence or sentences the
publisher itself uses, in the language it publishes them in, with the
document they come from; where the publisher also issues an English text,
that is quoted too.  A series with no entry is listed on its chart as having
no official definition rather than being given one of our own.

Three registries, each optional per item:

* :data:`SERIES` -- by series id: what one line on a chart measures.  Several
  series can share one entry (every e-money series shares Bank Indonesia's
  definition of Uang Elektronik).
* :data:`GROUPS` -- by ``(dataset key, group key)``: the concept a whole chart
  measures, shown before the per-series entries.
* :data:`DATASETS` -- by dataset key: the publisher's own description of the
  publication, shown in the page header.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

from .catalogue import Group


@dataclass(frozen=True)
class Definition:
    """One verbatim quote and where it comes from."""

    #: The term as the publisher names it (e.g. "Uang Elektronik").
    term: str
    #: The publisher's own words, unchanged.
    text: str
    #: The document the quote is taken from, as its title reads.
    source: str
    url: str
    #: The publisher's own English wording, when it issues one; never ours.
    english: str = ""
    #: A factual pointer from the term to the table row, never a definition of our own.
    note: str = ""


@dataclass(frozen=True)
class Entry:
    """A definition as it appears under a chart, with the labels of the series it covers."""

    labels: tuple[str, ...]
    definition: Definition


SERIES: dict[str, tuple[Definition, ...]] = {}
GROUPS: dict[tuple[str, str], tuple[Definition, ...]] = {}
DATASETS: dict[str, tuple[Definition, ...]] = {}


def populated() -> bool:
    """Whether any definitions have been entered at all.  An empty registry
    means the work has not been done, not that the publishers define nothing,
    so the pages say nothing until it is filled."""
    return bool(SERIES or GROUPS or DATASETS)


def for_dataset(dataset_key: str) -> tuple[Definition, ...]:
    return DATASETS.get(dataset_key, ())


def for_group(dataset_key: str, group: Group) -> list[Entry]:
    """The chart's definitions: the group's own first, then each distinct series
    definition once, with the labels of every series that shares it, in series order."""
    entries = [Entry((), definition) for definition in GROUPS.get((dataset_key, group.key), ())]
    shared: dict[Definition, list[str]] = {}
    for series_id in group.series:
        for definition in SERIES.get(series_id, ()):
            shared.setdefault(definition, []).append(group.label(series_id))
    entries.extend(Entry(tuple(labels), definition) for definition, labels in shared.items())
    return entries


def undefined(group: Group) -> list[str]:
    """Labels of the group's series that have no entry of their own."""
    return [group.label(series_id) for series_id in group.series if series_id not in SERIES]


def all_definitions() -> Iterator[Definition]:
    for registry in (SERIES, GROUPS, DATASETS):
        for definitions in registry.values():
            yield from definitions
