# Collectors

Scrapers that **update** the datasets under `Dataset/` from their published
sources. They merge; they never replace. Every file is copied into
`Dataset/Backup/<run stamp>/` immediately before it is first changed, so the
previous version of anything a run touched is always recoverable.

```bash
pip install -r Collectors/requirements.txt

python Collectors/run.py food_prices          # PIHPS weekly, current year, 3 markets
python Collectors/run.py consumption          # SPIP + SEKI + consumer survey + OJK + QRIS
python Collectors/run.py vehicle_listings     # ibid auctions (browser; opt-in, see below)
python Collectors/run.py all --dry-run        # show the diff, write nothing
```

## Schedule

Three GitHub Actions workflows in `.github/workflows/`, one per cadence:

| Cadence | Collectors | Cron (UTC) | Local |
|---|---|---|---|
| `weekly` | `pihps`, `ibid` | `0 2 * * 6` | Sat 09:00 WIB |
| `monthly` | `bi_spip`, `bi_seki`, `bi_consumer_survey`, `ojk_dpk`, `magpieiq` | `0 3 15 * *` | 15th 10:00 WIB |
| `quarterly` | *(reserved for BPS)* | `0 4 20 1,4,7,10 *` | 20th 11:00 WIB |

The cadence lives in `cli.GROUPS`, not in the YAML, so `python Collectors/run.py weekly` is
exactly what the cron runs. A run that finds new data commits it straight to `main`,
touching `Dataset/` only; a run that finds nothing writes nothing and adds no commit.

Saturday for the weekly run because PIHPS anchors its weekly column to the weekday of 1
January — or the next Monday when that is a weekend — so the anchor shifts every year (2026
Thu, 2025 Wed, 2024 Mon). A Saturday run catches that week's column whatever the anchor is,
where a fixed weekday slot would drift in and out of lag.

Three things to know:

- **`schedule` fires only from the repository's default branch**, and only from the copy of
  the workflow file that lives there. `main` is the default here and is also where the
  datasets live, so a cron change has to reach `main` before it takes effect. The workflows
  check out and push `TARGET_BRANCH` (`main`) explicitly rather than following the trigger,
  so a `workflow_dispatch` from a feature branch still lands its data on `main` — which also
  means that branch name is the one thing to change if these files are ever moved to another
  repository.
- **GitHub disables scheduled workflows after 60 days of repository inactivity.** Committed
  data counts as activity, so a live schedule sustains itself; a long quiet spell does not.
- **`qris` is on no schedule.** ASPI blocks datacentre addresses, so a cron could only ever
  log the block. It stays manual — see the caveat below. `cli.UNSCHEDULED` records that, and
  a test asserts every collector is either scheduled or listed there with a reason, so a new
  collector cannot be forgotten.

## Incremental collection

Runs narrow to the periods actually missing from the datasets. Nothing is ever replaced —
the sinks merge and dedupe, so a re-run is a no-op — this is only about not re-reading
history needlessly.

| Collector | What narrows |
|---|---|
| `pihps` | **The request.** Starts from an existing column ~8 weeks back instead of 1 January: 8 columns instead of 37. |
| `ojk_dpk` | **The downloads.** Releases already on file are skipped entirely — measured 150s → 4.6s, because it was re-fetching three ~35 MB workbooks it already had. |
| `bi_spip`, `bi_seki`, `bi_consumer_survey` | **Only the parse.** Each URL is a static `.xls`/zip carrying the whole history with no date parameter, so the download happens regardless; what stops is re-emitting months already stored. |
| `magpieiq` | Nothing — one page carries the whole series. |

**The PIHPS rule, because it is not obvious.** The portal does not answer "data since X", it
answers "a weekly grid anchored on X". Measured against the real 2026 workbook (37 Thursday
columns): starting from an existing column eight weeks back returns eight Thursdays; starting
from that date **plus two days** returns *Mondays*. An off-lattice start would add a second,
parallel set of columns rather than extending the file. So the start is always either 1
January or a date already in the workbook — never an arithmetic offset from the newest one.

**The trade-off.** Narrowing means a source restating an *older* period is no longer seen, and
BI does restate. Hence an overlap rather than a hard watermark: the last few periods are
re-read and re-checked every run (`--overlap N`, default 3 periods, 8 weeks for PIHPS), and
`--full` turns narrowing off for a complete pass. The watermark is taken per series family,
not per file — `bi_seki.csv` holds monthly deposits beside quarterly national accounts, whose
newest dates are months apart.

**Deduplication** is explicit in both CSV sinks. The series sinks keep the **first** of a
duplicated reading, because a payload listing the same `(series_id, ref_date)` twice is a
defect and nothing marks the later copy as better; the listings sink keeps the **later**
sighting, because a paginated scrape can legitimately see a listing twice while inventory
shifts and a vehicle that sold mid-scrape should end up sold. Either way the count is reported
separately from revisions — it used to be counted as a revision against a file it never
touched.

## Running by hand

`all` covers food prices and consumption and takes about four minutes. It
deliberately **excludes** `vehicle_listings`: that scrape drives a browser over a
few hundred pages and took 45 minutes, which would make the one command you
should be able to run habitually the one you avoid. `all` prints a line naming
what it skipped, so stale listings are never a silent surprise.

## What each collector does

| Collector | Source | Writes | Cadence |
|---|---|---|---|
| `pihps` | [PIHPS weekly food prices](https://www.bi.go.id/hargapangan) | `Dataset/Food Prices/PIHPS/<Market>/Tabel Harga Berdasarkan Daerah <year>.xlsx` × 3 | weekly |
| `bi_spip` | BI payment & transaction system, `TABEL_{5e,5a,5c,1,2}.xls` | `bi_emoney.csv`, `bi_card_transactions.csv`, `bi_payment_system.csv` | monthly |
| `bi_seki` | BI SEKI `TABEL{7_3,7_4,1_18}.xls` | `bi_seki.csv` | monthly + quarterly |
| `bi_consumer_survey` | BI Survei Konsumen data-series zip | `bi_consumer_survey.csv` | monthly |
| `ojk_dpk` | OJK Statistik Perbankan Indonesia | `ojk_dpk.csv` | monthly (see caveat) |
| `qris` | [ASPI QRIS statistics](https://aspi-indonesia.or.id/statistik-qris/) | `qris_transactions.csv` | monthly (see caveat) |
| *(none)* | QRIS charts, transcribed by hand | `qris_transactions.csv` | quarterly, 2023 Q1 – 2026 Q1 |
| `magpieiq` | [Magpie IQ e-commerce data pages](https://magpieiq.com/data/shopee-gmv-trend-indonesia-2026/) | `ecommerce_gmv.csv` | monthly (see caveat) |
| `ibid` | [ibid auctions](https://www.ibid.astra.co.id/cari-lelang/motor-bekas) | `ibid_motor_data.csv`, `ibid_car_data.csv` | on demand |

All targets are under `Dataset/Consumption/`. Most are **long series tables** — one row
per date per series. The two ibid files are **listings tables** — one row per vehicle —
and have their own sink and their own rules; see below. The two sinks refuse each
other's files, because cross-wiring them would destroy the target rather than merely
fail.

## The rules it holds to

**A re-run changes nothing.** The upsert key is `(series_id, ref_date)` for the
long CSVs, `(commodity, week)` for the food-price workbooks, and the auction's own
listing id for the ibid files. Running twice in a row leaves the files byte-identical
the second time and takes no backup — verified by the test suite and by the live dry
runs.

**Missing is missing.** PIHPS writes `-` when a market did not report. A dash
never overwrites a price that is already there, because it is not evidence the
old price was wrong. A real value *does* overwrite a real value — the sources
revise — and every such revision is reported rather than applied silently.

**The file's own format wins.** `bi_seki.csv` has eight columns and the other
three have six; a six-column file is never "upgraded". Row ordering, the existing
full-precision values (`819.1179999999999`), and line endings are all preserved
exactly — note that the series CSVs are **CRLF** while the two ibid files are **LF**.
Rows a run did not touch are re-emitted as the exact strings that were read.

**Rows are matched by label, not by row number.** BI reshapes these tables
without notice, and a fixed row index fails silently by reading the wrong
component — which is worse than failing, because the number still looks
plausible.

**A blocked source raises.** WAF interstitials arrive as HTTP 200 carrying
HTML. They are detected and raised on, so a block page can never be parsed into
an empty dataset.

**Listings accumulate, and two columns are frozen.** A re-scrape of ibid updates the
price and sold status of a vehicle already on file and appends the ones it has not
seen. Nothing is ever dropped — a vehicle that sold and left the site keeps its row,
which is the point: that is what turns a listings page into a resale price series.
`scraped_at_utc` records when a listing was *first* seen and `page`/`position` record
where it sat in the scrape that found it, so all three are written once and never
refreshed. Stamping them afresh each run would rewrite both files and drop an
identical backup every run, for no new information.

## Caveats worth knowing

- **Unemployment is not collected yet.** BPS Sakernas is published only through
  the BPS WebAPI, which needs a free key from
  [webapi.bps.go.id/developer](https://webapi.bps.go.id/developer); the BPS
  website itself answers 403 from a foreign runner, so there is no second
  route. `python Collectors/run.py unemployment` says so rather than failing.
  Adding it is one module plus one entry in `cli.COLLECTORS`.
- **OJK is stale at source.** Its public index has listed nothing since **June
  2025**; every later month returns 404. The collector discovers releases
  dynamically, so it will pick new ones up automatically, and meanwhile reports
  the staleness as a warning. For a *current* reading of deposits by households
  and businesses, use `bi_seki.deposits_by_owner.*` — SEKI table I.18 was
  refreshed in September 2026 and carries the by-owner split directly.
- **Those deposit groups do not all add up.** `households` nests inside
  `other_private_sector`, so adding the two double-counts.
- **Household consumption** comes from SEKI VII.3/VII.4, which republishes the
  BPS quarterly national accounts with BPS credited and needs no key. It is
  stored under `bi_seki.*` ids so a future BPS collector can never silently mix
  with it.
- **Food prices are national averages.** The file name says *Berdasarkan
  Daerah* ("by region"), but the grid has no geographic dimension: rows are a
  two-level commodity hierarchy and columns are weeks.
- **Only the current year's workbook is updated** by default. `--year 2023`
  backfills deliberately; that matters because
  `Traditional Market/... 2023.xlsx` is two years wide and duplicates the 2024
  file, so it is best left alone unless asked for.
- **OJK takes a couple of minutes** — three ~35 MB workbooks of fifty-odd
  sheets each.
- **QRIS cannot be fetched from a datacentre.** ASPI sits behind Cloudflare and
  answers *every* path with a 403 "Sorry, you have been blocked", `/robots.txt`
  included. It is an IP-level WAF block, not a challenge: a real Chromium with an
  `id-ID` locale gets the same page, and a re-terminating egress proxy owns the
  outbound TLS handshake so changing browser engines cannot change the fingerprint
  Cloudflare sees. Two consequences. First, **the live fetch path is unverified
  against the real page** — it is written for a runner that is not blocked. Second,
  there is a route that always works: save the page in a browser and parse it with
  no network at all.

  ```bash
  python Collectors/run.py consumption --only qris --html ~/Downloads/statistik-qris.html
  ```

  The parser handles both shapes these pages use — a data table in the markup, and a
  Highcharts/Chart.js config in a script — and de-duplicates when a page carries the
  same numbers as both. Its units and series names are inferred from the labels, so
  check them against the page on the first real run. Note also that **BI publishes no
  QRIS table at all**: all 34 SPIP tables were checked, so there is no fallback source.
- **The e-commerce GMV figures are one vendor's estimates, and are read off a
  chart.** Magpie IQ derives them from SKU-level tracking; they are not reported
  platform figures. The charts are server-rendered inline SVG, so the collector
  reads the `<polyline>` and inverts the pixel-to-dollar axis — which recovers
  what Magpie IQ *plotted*, to about $0.4M on the $200M-gridline pages and $40K
  on Tokopedia's. Accurate enough to match the pages' own prose: the extracted
  Shopee peak is $419.1M against "about $419M in the October 2024 sales season",
  and Tokopedia's latest month $5.94M against "$5.96M".

  Two traps in that markup, both pinned by tests. The peak month's dot carries
  an extra class (`dp-dot dp-dot--peak`), so a parser matching `class="dp-dot"`
  exactly drops one point and shifts every date — read the polyline instead. And
  every page ships `"temporalCoverage": "2023-07/2026-05"` while Tokopedia's
  chart starts Jul '24 and TikTok Shop's Jun '24, so the months are anchored on
  the x-axis label, never on the JSON-LD. Two guards catch a regression rather
  than storing it: the series must end on the month the page states in prose,
  and the highlighted peak must equal the series maximum.

  **Licensing is a live question, not a technical one.** The pages mark the
  dataset `isAccessibleForFree: false` under `magpieiq.com/terms` and sell the
  exact figures as a product, so check those terms before republishing this
  series — they advertise an API, which would be the cleaner route.
- **Part of `qris_transactions.csv` is transcribed, not collected.** Four series
  — `qris_transactions.{volume,value}.{total,off_us}`, 52 observations covering
  2023 Q1 to 2026 Q1 — were read off the printed data labels of a published
  QRIS chart, because ASPI's own page is unreachable (above). There is no
  scraper behind them, so they will not update themselves; extending the series
  means transcribing the next chart.

  They share a file with the `qris` collector but cannot collide with it: the
  transcribed ids are three-level (`qris_transactions.volume.total`) while the
  collector emits two-level ones (`qris_transactions.volume`), so the two
  sources coexist under one prefix rather than overwriting each other. A test
  pins that.

  Two things to know about the figures themselves. **They are quarterly**,
  confirmed against the source: each figure is a quarter, dated to its final
  month, which is what the chart's x-axis (months 3/6/9/12 under year bands) and
  its "Q1"/"Q4" annotations describe. **And the chart is internally inconsistent**: its printed growth annotations
  do not follow from its own printed bar labels. It states Q1 2026 volume up
  116.43% year-on-year where the labels give 107.4%, and up 9.56% on Q4 2025
  where the labels give 14.7%. The bars are what is stored, because the Off-Us
  share they imply moves smoothly from 78% to 90% across all 13 quarters, which
  a misread digit would break; the annotations look like a stale overlay from an
  earlier version of the deck. `tests/test_qris_dataset.py` encodes those
  invariants, because a hand-keyed dataset fails by mistyped digit rather than
  by layout change.
- **ibid needs a browser, is the slowest collector by far, and is opt-in.** It is
  a React single-page app behind F5 BIG-IP — the HTML is a 3 KB shell — so there
  is no requests-and-regex route. Both categories together are a few hundred
  pages at a 2-second politeness delay; the first full run took 45 minutes, which
  is why `all` leaves it out. Run it with `run.py vehicle_listings`. Its backend is also
  intermittently flaky: `mobil-bekas` served "upstream request failed" twice in a
  row and then 24 cards on the third attempt, while `motor-bekas` was fine
  throughout. An empty page is therefore retried before it is believed, because
  reading a hiccup as "no more pages" would silently truncate the scrape; if it
  persists, the run stops and *says* the remaining pages were not read.
- **Browsers are not downloaded.** Playwright pins a browser build per release, so
  set `CHROMIUM_PATH` (or keep `/opt/pw-browsers/chromium`) rather than running
  `playwright install`. If Chromium cannot verify TLS behind a corporate proxy, import
  that proxy's CA into the NSS store with
  `certutil -A -n proxy-ca -t "C,," -i <ca>.crt -d sql:$HOME/.pki/nssdb` — never
  disable verification.

## Flags

| Flag | Effect |
|---|---|
| `--dry-run` | Parse, report the diff, write nothing and take no backup |
| `--only NAME` | Run one collector (repeatable) |
| `--year YYYY` | Food prices: which year's workbook (repeatable) |
| `--html PATH` | QRIS: parse a page saved from a browser instead of fetching it |
| `--max-pages N` | ibid: stop after N pages per category |
| `--full` | Re-read all history instead of only what is missing |
| `--overlap N` | Periods of collected history to re-read anyway (default 3; 8 weeks for PIHPS) |
| `--since YYYY-MM-DD` | Ignore observations before this date |
| `--no-backup` | Skip the snapshot |
| `--keep N` | Keep only the newest N backup snapshots |
| `--verbose` | List every revision |

## Tests

```bash
cd Collectors && python3 -m pytest
```

All offline against recorded payloads in `tests/fixtures/`. A source being down never
turns the suite red, because that would hide a real parser regression behind an
unrelated outage. The merge layer is additionally checked against the real `Dataset/`
files: every series CSV and both ibid files must round-trip byte-identically, and all
24 PIHPS workbooks must round-trip losslessly.

The two QRIS fixtures are the exception: they are **synthetic stand-ins**, clearly
marked as such in their own header comments, because the real page could not be
recorded from here. They test the parser's logic, which is real code; they do not
prove it matches ASPI's markup.

## Layout

```
Collectors/
  run.py                    entry point
  requirements.txt
  collectors/
    cli.py                  argparse surface and the run loop
    paths.py                every path, anchored to __file__ rather than the cwd
    http.py                 session with retries, browser UA, block-page detection
    excelio.py              workbook reading: format sniffing, header discovery, block dating
    dates.py                Indonesian month/quarter parsing, unit normalisation
    model.py                Obs - the one row shape every collector produces
    errors.py               SourceUnavailable / SourceStale
    sinks/
      backup.py             timestamped snapshots
      long_csv.py           upsert into the long series CSVs, preserving each file's format
      wide_xlsx.py          merge into the wide PIHPS workbooks
      listings_csv.py       accumulate the ibid listings, one row per vehicle
    sources/                one module per source
    config/                 row-label -> series_id maps, matched by label
  tests/
```

`http.py`, `excelio.py` and `dates.py`, and the parsers and configs in
`sources/`, are ported from an earlier collection pipeline that predates this
repository. What is new here is the sink layer: that pipeline wrote to a Parquet
store, whereas these collectors write back into the dataset files that already
exist, in the formats they already use.
