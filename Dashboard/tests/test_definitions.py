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


def test_consumer_survey_is_defined_from_bank_indonesia_documents():
    dataset = catalogue.BY_KEY["consumer_survey"]
    assert definitions.populated(dataset)
    assert not definitions.populated(catalogue.BY_KEY["ibid"]) or definitions.DATASETS.get("ibid")
    confidence = definitions.for_group("consumer_survey", catalogue.group("consumer_survey", "confidence"))
    terms = [entry.definition.term for entry in confidence]
    assert terms[0].startswith("Indeks saldo bersih")  # the group's own entry comes first
    assert any(term.startswith("Indeks Keyakinan Konsumen (IKK)") for term in terms)
    # The six component indices share one entry, listed once with all six labels.
    components = next(entry for entry in confidence if entry.definition.term.startswith("Pertanyaan inti"))
    assert len(components.labels) == 6
    assert all("bi.go.id" in definition.url for definition in definitions.all_definitions() if definition.term.startswith("Indeks"))
    assert definitions.undefined(catalogue.group("consumer_survey", "share_saving")) == []


def test_every_dataset_has_official_definitions():
    for dataset in catalogue.DATASETS:
        assert definitions.populated(dataset), dataset.key
        assert definitions.for_dataset(dataset.key), f"{dataset.key} has no description of its publication"
    # Series the publishers do not define are listed as such, not invented.
    assert set(definitions.undefined(catalogue.group("seki", "deposits"))) == {
        "Cooperatives",
        "Other private sector (includes households)",
        "All owners",
    }
