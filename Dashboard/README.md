# Dashboard

A tracker for the indicators the collectors keep under `Dataset/`: one line chart
per group of series, bucketed by the publisher and dataset each series comes
from. Streamlit is the main app; the same code writes a self-contained offline
HTML file.

```bash
pip install -r Dashboard/requirements.txt
streamlit run Dashboard/app.py                  # the app, at http://localhost:8501
python Dashboard/export_html.py                 # Dashboard/dist/indonesia-indicators.html
```

## Pages

| Section | Page | Series file(s) |
|---|---|---|
| Overview | Freshness of every dataset | all |
| Food prices | PIHPS weekly food prices, 31 commodities at three market levels | `Dataset/Food Prices/PIHPS/**` |
| Bank Indonesia | SPIP payment system statistics: one tab each for e-money, cards, and currency and BI-RTGS, one chart at a time | `bi_emoney`, `bi_card_transactions`, `bi_payment_system` |
| Bank Indonesia | SEKI: GDP by expenditure, deposits by owner group | `bi_seki` |
| Bank Indonesia | Survei Konsumen: confidence indices, budget shares | `bi_consumer_survey` |
| OJK | SPI third-party funds (stale at source since June 2025) | `ojk_dpk` |
| Other sources | ASPI QRIS (transcribed, quarterly) | `qris_transactions` |
| Other sources | Magpie IQ e-commerce GMV | `ecommerce_gmv` |
| Other sources | ibid vehicle auctions: lots in auction and lots sold each week, then lots and listed price by brand and model, and by grade and model year within one of them | `ibid_car_data`, `ibid_motor_data` |

Every line chart has a **Show as** switch with two settings: the level as
published, or the % change over the interval that dataset's own publication
frequency calls for.

| Frequency | Compared with | Pages |
|---|---|---|
| weekly | a week earlier | PIHPS food prices |
| monthly | a month earlier | SPIP, SEKI deposits, Survei Konsumen, OJK, e-commerce GMV |
| quarterly or rarer | a year earlier | SEKI GDP, SPIP cash intensity, QRIS |

A quarterly series has too few observations either side for a shorter
comparison to say much, which is why it is the one case that still looks back a
year. Comparisons are made by date rather than by position, so a period a
source did not publish leaves a gap instead of being silently compared against
an older observation, and none of them is seasonally adjusted. A chart carries
one unit and one y-axis; the change is how series of different scale are put
side by side. Under each chart a table gives the latest value per series and
its change on the previous observation and on a year earlier (percentages,
or points for series that are already percentages or indices). Plotly's range
buttons (1y / 3y / 5y / All) and the slider under the x-axis zoom the time span.

The ibid page is the exception to the one-line-chart-per-group rule. Its rows
are lots, not a series, so its one chart over time is drawn from the auction
dates: each tab opens on the **lots in auction each week against the lots
sold**, which is as close to a weekly sold volume as the listings get. ibid
marks a lot Terjual once its auction has been held and nothing on file is
marked unsold, so the sold line counts the lots whose auction had been run when
each was last read, not the ones that found a buyer; the lines part where the
auctions are still to come and where a lot dropped off the site before a scrape
could see it sold. Weeks the scrapes did not cover day by day -- taking their
reaches together, so two scrapes that meet cover the week they meet in -- are
drawn with a hollow point and count short on both lines.

Under that come two layers of breakdown. **Brand** or **model** names the
vehicle; open one of them up in **Within** and **grade** or **model year** says
what condition and age do to its price. Only one layer is on screen at a time,
and a brand or model is offered for opening only once it has enough lots to
survive being cut again. The two charts under the bar answer the same pair of
questions of whichever cut is chosen: how many lots, and at what price. Brand
and model are ranked by lots and read down the side; grade and model year keep
their own order and run along the bottom, because their sequence is the point.
Every chart is cut to what stays readable and the table beneath it lists every
row.

The price boxes span the middle half of the lots with the median marked, and
their whiskers stop at the 5th and 95th percentile. One lot at eight times the
price of the rest is common enough here to flatten every box in the chart, so
the true cheapest and dearest sit in the table and the hover instead. A
category with fewer than eight lots is left out of the price chart, since its
range would be an accident of which two vehicles happened to come up.

A lot's title is split
into brand, model and trim on the way in: the model is the single word after
the brand, so an Avanza G and an Avanza Veloz both count as an Avanza, and the
handful of nameplates whose first word never stands alone, Gran Max, Grand
Livina, Range Rover, Santa Fe and Strada Triton, keep both words. The trim is
kept in its own column rather than folded into the model, which is what used to
split one Gran Max into four.

Line charts were chosen as the first, simplest tracker. The project's
methodology note (`docs/methodology.md` on the repository's default branch,
commit `40fa6e7`) lays out later layers: percentile heatmaps, breadth counts and
composite indices. None of that is built yet.

## Official definitions

Every chart has an **Official definitions** expander and every page an
**Official description** one, mirrored in the offline HTML. The text in them
is the publisher's own: Bank Indonesia's per-table SPIP and SEKI metadata, its
Survei Konsumen metadata and reports, its regulations, OJK's Statistik
Perbankan Indonesia and the Banking Law, the QRIS regulation, the PIHPS FAQ,
Magpie IQ's methodology page and ibid's general terms. Nothing is paraphrased:
each entry in `dashboard/definitions.py` is a verbatim quote in the language
it was published in, the publisher's own English wording where one exists,
and the document and URL it comes from. Where a publisher defines only part
of what a series shows (say, the components of an aggregate row) or nothing at
all, the entry's note says so, and a series with no entry is listed under its
chart as having no official definition rather than being given one of ours.
To add an entry, quote the document, keep the quote checkable against it, and
register it under the series id, the chart group or the dataset key.

## Keeping it updated

The app reads the files under `Dataset/` when it starts and caches them until
any file's size or modification time changes, so:

- **Streamlit Community Cloud** (recommended): at share.streamlit.io choose
  *New app*, repository `cmmtscpr3/Indonesia-Indicators`, branch
  `Indonesia-indicators-dashboard`, main file `Dashboard/app.py`. Community
  Cloud installs `Dashboard/requirements.txt` and redeploys on every push, so
  each dataset commit the collectors make is live within minutes. Nothing else
  to schedule.
- **Locally**: `git pull` then reload the browser tab; the sidebar shows when
  the data files last changed.

The offline file is not committed (it is several megabytes and would change
with every collection). Build it with `export_html.py`, or in the app press
**Prepare offline HTML** in the sidebar and download it. It opens with no
network connection: Plotly is embedded in the file.

## Layout

```
Dashboard/
  app.py                 Streamlit entrypoint: sections and pages (st.navigation)
  export_html.py         writes the offline HTML
  requirements.txt       app dependencies (Community Cloud reads this file)
  requirements-dev.txt   + pytest
  dashboard/
    catalogue.py         the buckets: datasets, their groups of series, labels, notes
    definitions.py       the publishers' own definitions, quoted verbatim, by series, chart and dataset
    data.py              loaders, through the collectors' own readers
    transform.py         the per-frequency comparisons, latest-value tables, weekly auction counts, freshness
    figures.py           the line chart, the weekly pair, the ranked bar and the range box (Plotly)
    theme.py             palette and Plotly template
    charts.py            data + choices -> a chart with its table (no Streamlit)
    export.py            the offline HTML
    ui.py                Streamlit pieces shared by pages
    pages/               one module per page, each with render()
  tests/                 pytest, offline, against the real Dataset/
```

`data.py` imports `collectors.sinks.long_csv`, `collectors.sinks.wide_xlsx`
and `collectors.dates` from `Collectors/`, so the dashboard reads the files
exactly as the collectors write them.

## Adding a dataset

1. If it is a long series CSV the collectors already write, add a `Dataset`
   to `catalogue.DATASETS` with one `Group` per unit of measurement (series
   ids in the order their colours should be assigned, labels, defaults).
2. Add a page module under `dashboard/pages/` (for a plain page,
   `ui.render_dataset("<key>")` is all it takes) and register it in `app.py`.
3. Add the publisher's definitions of its series to `dashboard/definitions.py`,
   quoted verbatim with their source document; the page shows them under each
   chart.
4. Run the tests: `cd Dashboard && python -m pytest`. They check that every
   catalogued series exists, that every default chart builds, that every page
   renders, and that every definition points at a catalogued series and cites
   a source.

## Tests

```bash
pip install -r Dashboard/requirements-dev.txt
cd Dashboard && python -m pytest
```

All offline. The loaders and charts are checked against the real files under
`Dataset/`, and each page is run through Streamlit's `AppTest` harness.
