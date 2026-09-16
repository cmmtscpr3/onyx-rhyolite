"""The official definitions: every entry points at something catalogued and is a sourced quote."""

from __future__ import annotations

from dashboard import catalogue, definitions


def test_every_definition_points_at_the_catalogue():
    series_ids = {sid for dataset in catalogue.DATASETS for group in dataset.groups for sid in group.series}
    assert set(definitions.SERIES) <= series_ids, set(definitions.SERIES) - series_ids
    group_keys = {(dataset.key, group.key) for dataset in catalogue.DATASETS for group in dataset.groups}
    assert set(definitions.GROUPS) <= group_keys, set(definitions.GROUPS) - group_keys
    assert set(definitions.DATASETS) <= set(catalogue.BY_KEY), set(definitions.DATASETS) - set(catalogue.BY_KEY)


def test_every_definition_is_a_sourced_quote():
    for definition in definitions.all_definitions():
        assert definition.term.strip() and definition.source.strip(), definition
        assert definition.text and definition.text == definition.text.strip(), definition.term
        assert definition.url.startswith("https://"), definition.url
        assert definition.english == definition.english.strip()


def test_for_group_lists_each_shared_definition_once():
    for dataset in catalogue.DATASETS:
        for group in dataset.groups:
            entries = definitions.for_group(dataset.key, group)
            seen = [entry.definition for entry in entries]
            assert len(seen) == len(set(seen)), f"{dataset.key}/{group.key} repeats a definition"
            for entry in entries:
                assert set(entry.labels) <= {group.label(sid) for sid in group.series}
            assert set(definitions.undefined(group)) <= {group.label(sid) for sid in group.series}
