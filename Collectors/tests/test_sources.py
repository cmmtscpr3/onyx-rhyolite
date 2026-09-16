"""The parsers, against payloads recorded from the live sources.

Every test here is offline.  A source being down must never turn the suite red,
because that would hide a real parser regression behind an unrelated outage.
"""

from __future__ import annotations

import datetime as dt

import pytest

from collectors.sources import bi_consumer_survey as sk
from collectors import model
from collectors.sources import bi_seki, bi_spip, ibid, ojk_dpk, pihps

SELECTORS_ASSET_PREFIX = ibid.SELECTORS["asset_prefix"]

# --------------------------------------------------------------------- PIHPS


def test_pihps_weekly_window_anchors_on_new_years_day():
    """The returned weekday follows start_date, which is why this matters.

    Asking from 1 January reproduces the column dates already in that year's
    workbook; asking from any other day interleaves a second, offset series.
    """
    assert pihps.window(2026, today=dt.date(2026, 9, 15)) == (
        dt.date(2026, 1, 1),
        dt.date(2026, 9, 15),
    )
    assert pihps.window(2025, today=dt.date(2026, 9, 15)) == (
        dt.date(2025, 1, 1),
        dt.date(2025, 12, 31),
    )


def test_pihps_covers_the_three_market_folders_that_exist():
    assert [m.directory for m in pihps.MARKETS] == [
        "Traditional Market",
        "Modern Market",
        "Wholesale",
    ]
    # Produsen (price_type_id 4) is published but has no folder here.
    assert 4 not in {m.price_type_id for m in pihps.MARKETS}


def test_pihps_rejects_a_year_before_the_portals_history():
    with pytest.raises(ValueError, match="2018"):
        pihps.collect(years=[2017])


def test_pihps_values_pass_through_as_the_portal_wrote_them(pihps_grid):
    """No float round-trip, so no rounding and no separator guessing."""
    grid = pihps.grid_from_response(pihps_grid)
    beras = next(r for r in grid.rows if r.name == "Beras")
    sample = grid.cell(beras, grid.weeks[-1])
    assert "," in sample and sample.replace(",", "").isdigit()


def test_pihps_keeps_the_group_and_variety_levels_apart(pihps_grid):
    grid = pihps.grid_from_response(pihps_grid)
    groups = {r.name for r in grid.rows if r.level == 1}
    varieties = {r.name for r in grid.rows if r.level == 2}
    assert "Beras" in groups and "Beras Kualitas Bawah I" in varieties
    assert not groups & varieties


def test_pihps_ignores_rows_without_a_name():
    grid = pihps.grid_from_response([{"no": "", "name": "  ", "level": 1, "01/01/2026": "1,000"}])
    assert grid.rows == []


# ---------------------------------------------------------------------- SPIP


def test_spip_config_marks_every_ambiguous_total_exact():
    """'Volume Transaksi' is a prefix of 'Volume Transaksi Belanja'.

    Without `exact`, the total silently captures one of its own components.
    """
    for spec in bi_spip.load_config():
        subs = {row.sub: row for row in spec.rows}
        for row in spec.rows:
            shadowed = [
                other
                for other in spec.rows
                if other is not row
                and other.match.casefold().startswith(row.match.casefold())
                and other.match.casefold() != row.match.casefold()
            ]
            if shadowed:
                assert row.exact, f"{spec.table}/{row.sub} is a prefix of {[s.sub for s in shadowed]}"
        assert len(subs) == len(spec.rows)


def test_spip_parses_settlement_media_into_the_expected_series(fixtures):
    content = (fixtures / "bi_spip_tabel_2.xls").read_bytes()
    spec = next(s for s in bi_spip.load_config() if s.table == "TABEL_2")
    observations = bi_spip.parse_table(content, spec)
    assert {o.series_id for o in observations} == {
        "bi_payment_system.narrow_money",
        "bi_payment_system.currency_in_circulation",
        "bi_payment_system.demand_deposits_rupiah",
        "bi_payment_system.emoney_instruments_outstanding",
    }
    assert {o.ref_period for o in observations} == {"M"}
    assert {o.geo_id for o in observations} == {"0000"}
    assert min(o.ref_date for o in observations) == dt.date(2012, 1, 1)
    # The unit comes from the workbook, so the count series must not be money.
    units = {o.series_id: o.unit for o in observations}
    assert units["bi_payment_system.narrow_money"] == "IDR billion"
    assert units["bi_payment_system.emoney_instruments_outstanding"] == "million instruments"


def test_spip_never_dates_the_same_reading_twice(fixtures):
    content = (fixtures / "bi_spip_tabel_2.xls").read_bytes()
    spec = next(s for s in bi_spip.load_config() if s.table == "TABEL_2")
    keys = [o.key for o in bi_spip.parse_table(content, spec)]
    assert len(keys) == len(set(keys))


def test_spip_since_filters_history(fixtures):
    content = (fixtures / "bi_spip_tabel_2.xls").read_bytes()
    spec = next(s for s in bi_spip.load_config() if s.table == "TABEL_2")
    observations = bi_spip.parse_table(content, spec, since=dt.date(2025, 1, 1))
    assert observations and min(o.ref_date for o in observations) >= dt.date(2025, 1, 1)


# ---------------------------------------------------------------------- SEKI


def test_seki_dates_each_quarter_exactly_once(fixtures):
    """VII.3's year headers drift right of their block from 2021 on.

    Forward-filling the year therefore stores two values for some quarters;
    block-based dating is what stops that.
    """
    content = (fixtures / "bi_seki_tabel7_3.xlsx").read_bytes()
    spec = next(s for s in bi_seki.load_config() if s.table == "TABEL7_3")
    observations = bi_seki.parse_table(content, spec)
    keys = [o.key for o in observations]
    assert len(keys) == len(set(keys))
    assert {o.ref_period for o in observations} == {"Q"}
    assert {o.ref_date.month for o in observations} <= {1, 4, 7, 10}


def test_seki_household_consumption_is_a_plausible_share_of_gdp(fixtures):
    content = (fixtures / "bi_seki_tabel7_3.xlsx").read_bytes()
    spec = next(s for s in bi_seki.load_config() if s.table == "TABEL7_3")
    by = {}
    for obs in bi_seki.parse_table(content, spec):
        by.setdefault(obs.series_id, {})[obs.ref_date] = obs.value
    household = by["bi_seki.gdp_expenditure_current.household_consumption"]
    gdp = by["bi_seki.gdp_expenditure_current.gdp"]
    shares = [household[d] / gdp[d] for d in sorted(set(household) & set(gdp))]
    assert shares and all(0.4 < share < 0.7 for share in shares)


def test_seki_deposit_groups_partition_the_total(fixtures):
    """The five top-level groups add up; households nests inside one of them.

    Adding `households` alongside `other_private_sector` double-counts, so the
    partition is asserted without it.
    """
    content = (fixtures / "bi_seki_tabel1_18.xlsx").read_bytes()
    spec = next(s for s in bi_seki.load_config() if s.table == "TABEL1_18")
    by = {}
    for obs in bi_seki.parse_table(content, spec):
        by.setdefault(obs.series_id, {})[obs.ref_date] = obs.value
    base = "bi_seki.deposits_by_owner."
    groups = [
        base + name
        for name in (
            "other_financial_institutions",
            "local_government",
            "state_nonfinancial_business",
            "private_nonfinancial_business",
            "other_private_sector",
        )
    ]
    dates = sorted(set.intersection(*[set(by[g]) for g in groups], set(by[base + "total"])))
    assert dates
    for date in dates:
        assert sum(by[g][date] for g in groups) == pytest.approx(by[base + "total"][date], rel=1e-4)
    households = by[base + "households"]
    for date in sorted(set(households) & set(by[base + "other_private_sector"])):
        assert households[date] < by[base + "other_private_sector"][date]


def test_seki_stops_before_the_memo_items(fixtures):
    content = (fixtures / "bi_seki_tabel1_18.xlsx").read_bytes()
    spec = next(s for s in bi_seki.load_config() if s.table == "TABEL1_18")
    assert spec.stop_at == "Memo Items"
    labels = {o.notes.get("label", "") for o in bi_seki.parse_table(content, spec)}
    assert not any("Pemerintah Pusat" in label for label in labels)
    assert not any("Bukan Penduduk" in label for label in labels)


# ------------------------------------------------------------ consumer survey


def test_consumer_survey_ikk_is_the_mean_of_its_two_halves(fixtures):
    """BI's own identity, and the sharpest available check on the parse."""
    content = (fixtures / "bi_consumer_survey.xlsx").read_bytes()
    by = {}
    for obs in sk.parse_workbook(content):
        by.setdefault(obs.series_id, {})[obs.ref_date] = obs.value
    ikk, ike, iek = (by["bi_consumer_survey." + n] for n in ("ikk", "ike", "iek"))
    dates = sorted(set(ikk) & set(ike) & set(iek))
    assert len(dates) > 100
    for date in dates:
        assert ikk[date] == pytest.approx((ike[date] + iek[date]) / 2, abs=0.15)


def test_consumer_survey_income_shares_sum_to_100(fixtures):
    content = (fixtures / "bi_consumer_survey.xlsx").read_bytes()
    by = {}
    for obs in sk.parse_workbook(content):
        by.setdefault(obs.series_id, {})[obs.ref_date] = obs.value
    base = "bi_consumer_survey.expenditure_share."
    total_bracket = [base + n for n in ("consumption", "loan_instalment", "saving")]
    dates = sorted(set.intersection(*[set(by[s]) for s in total_bracket]))
    assert dates
    for date in dates:
        assert sum(by[s][date] for s in total_bracket) == pytest.approx(100.0, abs=0.6)
    assert all(by[s][dates[0]] is not None for s in total_bracket)


def test_consumer_survey_is_national_only(fixtures):
    """Tabel 6's eighteen cities are deliberately not collected."""
    content = (fixtures / "bi_consumer_survey.xlsx").read_bytes()
    observations = sk.parse_workbook(content)
    assert {o.geo_id for o in observations} == {"0000"}
    assert sk.SCOPES == ("national",)


def test_consumer_survey_keeps_ability_and_willingness_apart(fixtures):
    content = (fixtures / "bi_consumer_survey.xlsx").read_bytes()
    series = {o.series_id for o in sk.parse_workbook(content)}
    assert "bi_consumer_survey.expenditure_share.saving" in series
    assert "bi_consumer_survey.durable_goods_purchase" in series


def test_consumer_survey_lets_discontinued_series_end(fixtures):
    """BI still ships the rows; they are empty after December 2019.

    An empty cell must produce no observation, never a zero.
    """
    content = (fixtures / "bi_consumer_survey.xlsx").read_bytes()
    by = {}
    for obs in sk.parse_workbook(content):
        by.setdefault(obs.series_id, {})[obs.ref_date] = obs.value
    live = max(by["bi_consumer_survey.ikk"])
    stopped = max(by["bi_consumer_survey.price_expectation_3m"])
    assert stopped < live
    assert 0.0 not in by["bi_consumer_survey.price_expectation_3m"].values()


def test_consumer_survey_release_urls_use_indonesian_month_names():
    assert sk.release_url(2026, 8).endswith("SK-Agustus-2026.aspx")
    assert list(sk.previous_months(dt.date(2026, 1, 15), 3)) == [
        (2026, 1),
        (2025, 12),
        (2025, 11),
    ]


# ----------------------------------------------------------------------- OJK


def test_ojk_index_parsing_returns_releases_newest_first():
    html = """
      <a href="/id/kanal/perbankan/data-dan-statistik/statistik-perbankan-indonesia/Pages/Statistik-Perbankan-Indonesia---Januari-2025.aspx">
        Statistik Perbankan Indonesia - Januari 2025</a>
      <a href="/id/kanal/perbankan/data-dan-statistik/statistik-perbankan-indonesia/Pages/Statistik-Perbankan-Indonesia---Juni-2025.aspx">
        Statistik Perbankan Indonesia - Juni 2025</a>
      <a href="/id/somewhere/else.aspx">Laporan Tahunan 2025</a>
    """
    releases = ojk_dpk.parse_index(html)
    assert [r.label for r in releases] == ["2025-06", "2025-01"]
    assert releases[0].page_url.startswith("https://ojk.go.id/")


def test_ojk_uses_the_bare_host_not_www():
    """www.ojk.go.id closes the TLS connection mid-exchange from some egress."""
    assert ojk_dpk.BASE == "https://ojk.go.id"
    assert "//ojk.go.id" in ojk_dpk.INDEX_URL


def test_ojk_national_composition_adds_up(fixtures):
    content = (fixtures / "ojk_spi_dpk_jun2025.xlsx").read_bytes()
    release = ojk_dpk.Release(
        month=dt.date(2025, 6, 1),
        page_url="https://ojk.go.id/x",
        title="Statistik Perbankan Indonesia - Juni 2025",
    )
    observations = ojk_dpk.parse_workbook(content, release)
    assert observations
    assert {o.geo_id for o in observations} == {"0000"}
    assert {o.unit for o in observations} == {"IDR billion"}
    by = {}
    for obs in observations:
        by.setdefault(obs.series_id, {})[obs.ref_date] = obs.value
    base = "ojk_dpk.composition."
    parts = [base + n for n in ("giro", "tabungan", "simpanan_berjangka")]
    dates = sorted(set.intersection(*[set(by[p]) for p in parts], set(by[base + "total"])))
    assert dates
    for date in dates:
        assert sum(by[p][date] for p in parts) == pytest.approx(by[base + "total"][date], rel=1e-4)


def test_ojk_sheet_rule_excludes_the_nesting_variants():
    """Five DPK sheet names nest, so exclusions decide which one is read."""
    wanted, unwanted = ojk_dpk.SHEET_NATIONAL_COMPOSITION
    assert set(wanted) == {"komp", "dpk"}
    # BPR is a different bank population; KBMI regroups by capital tier; per-Lok
    # is the provincial cut, which this national-only dataset does not want.
    assert {"bpr", "kbmi", "lok"} <= set(unwanted)


# ---------------------------------------------------------------------- ibid


def test_ibid_collects_the_two_categories_that_have_files():
    assert [(c.slug, c.path.name) for c in ibid.CATEGORIES] == [
        ("motor-bekas", "ibid_motor_data.csv"),
        ("mobil-bekas", "ibid_car_data.csv"),
    ]


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Rp 6.700.000", 6700000),
        ("Rp 155.500.000", 155500000),
        ("Rp 1", 1),
        ("", None),
        (None, None),
        ("-", None),
    ],
)
def test_ibid_price_parsing(raw, expected):
    assert ibid.parse_price(raw) == expected


def test_ibid_run_stamp_matches_the_shape_already_in_the_files():
    """The uploaded rows read 2026-08-17T05:43:59 -- seconds, no offset."""
    stamp = ibid.run_stamp(dt.datetime(2026, 9, 15, 6, 38, 46, 123456, tzinfo=dt.timezone.utc))
    assert stamp == "2026-09-15T06:38:46"


def test_ibid_parses_recorded_cards_into_listings(ibid_cards):
    listings = ibid.rows_to_listings(ibid_cards["page_1"], page=1, stamp="2026-09-15T00:00:00")
    assert listings
    first = listings[0]
    assert first.key.isdigit()
    assert first.page == 1 and first.position == 1
    assert first.price_idr == ibid.parse_price(first.price_raw)
    assert first.scraped_at == "2026-09-15T00:00:00"
    assert first.url.startswith("https://www.ibid.astra.co.id/detail-lelang/")


def test_ibid_reads_the_sold_badge(ibid_cards):
    sold = ibid.rows_to_listings(ibid_cards["page_40"], page=40, stamp="s")
    assert sold and all(listing.sold for listing in sold)
    assert all(listing.sold_label for listing in sold)
    unsold = ibid.rows_to_listings(ibid_cards["page_1"], page=1, stamp="s")
    assert not any(listing.sold for listing in unsold)
    assert all(listing.sold_label == "" for listing in unsold)


def test_ibid_puts_the_single_date_part_on_the_left(ibid_cards):
    """The date row has one child in practice, so listed_right stays empty.

    It is empty in 100% of the rows of both uploaded files; the column is kept
    because the markup allows a second child.
    """
    listings = ibid.rows_to_listings(ibid_cards["page_1"], page=1, stamp="s")
    assert all(listing.listed_left for listing in listings)
    assert all(listing.listed_right == "" for listing in listings)


def test_ibid_drops_a_card_with_no_link(ibid_cards):
    """No url means no id, and an unidentifiable listing cannot be merged."""
    rows = [dict(ibid_cards["page_1"][0], href=None)]
    assert ibid.rows_to_listings(rows, page=1, stamp="s") == []


def test_ibid_listing_id_ignores_the_tracking_parameter():
    """entry_point varies and contains a space; it must not split a listing."""
    base = "https://www.ibid.astra.co.id/detail-lelang/motor/honda-beat/722340913165"
    assert model.listing_id(base) == "722340913165"
    assert model.listing_id(f"{base}?entry_point=Product Listing") == "722340913165"
    assert model.listing_id(f"{base}?entry_point=Search") == "722340913165"


def test_ibid_upstream_failure_is_not_the_end_of_the_results():
    """Observed live: mobil-bekas served this twice, then 24 cards.

    Reading it as "no more pages" would end the walk and silently truncate the
    scrape, so an empty page is retried before it is believed.
    """
    assert ibid.UPSTREAM_ERROR == "upstream request failed"
    assert ibid.CONFIG["empty_retries"] >= 2


def test_ibid_prefers_a_preinstalled_chromium(monkeypatch, tmp_path):
    """Playwright pins a browser build; runners may forbid downloading one."""
    monkeypatch.setenv("CHROMIUM_PATH", str(tmp_path / "chrome"))
    assert ibid.chromium_path() == str(tmp_path / "chrome")
    monkeypatch.delenv("CHROMIUM_PATH")
    monkeypatch.setattr(ibid, "_CHROMIUM_CANDIDATES", (str(tmp_path / "absent"),))
    assert ibid.chromium_path() is None


def test_ibid_ignores_bundled_assets_when_choosing_the_photo():
    """The card renders /static/media/noimage.png when there is no photo.

    Reporting it as the image overwrote real photo URLs already on file with a
    placeholder. The filter lives in the in-page extractor, so this pins the
    configuration it reads and the fact that the extractor consults it.
    """
    assert SELECTORS_ASSET_PREFIX == "/static/media/"
    assert "cfg.asset_prefix" in ibid.EXTRACT_JS
    assert "indexOf(assets) === 0" in ibid.EXTRACT_JS


def test_ibid_passes_the_extracted_image_through_untouched(ibid_cards):
    """Policy about placeholders belongs in the extractor and the sink.

    rows_to_listings stays a faithful transcription, so what the browser saw is
    what the tests see.
    """
    row = ibid_cards["page_1"][0]
    listing = ibid.rows_to_listings([row], page=1, stamp="s")[0]
    assert listing.image == (row.get("image") or "")
