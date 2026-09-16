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
| Bank Indonesia | SPIP payment system statistics: e-money, cards, indicators | `bi_emoney`, `bi_card_transactions`, `bi_payment_system` |
| Bank Indonesia | SEKI: GDP by expenditure, deposits by owner group | `bi_seki` |
| Bank Indonesia | Survei Konsumen: confidence indices, budget shares | `bi_consumer_survey` |
| OJK | SPI third-party funds (stale at source since June 2025) | `ojk_dpk` |
| Other sources | ASPI QRIS (transcribed, quarterly) | `qris_transactions` |
| Other sources | Magpie IQ e-commerce GMV | `ecommerce_gmv` |
| Other sources | ibid vehicle auctions: weekly median listed price, lots per week | `ibid_car_data`, `ibid_motor_data` |

Every chart has a **Show as** switch: level, year-on-year % change, or an index
set to 100 at the first observation from the chosen start year. The last two
put series of different scale on one axis, which is why no chart here has a
second y-axis. Under each chart a table gives the latest value per series and
its change on the previous observation and on a year earlier (percentages,
or points for series that are already percentages or indices). Plotly's range
buttons (1y / 3y / 5y / All) and the slider under the x-axis zoom the time span.

Line charts were chosen as the first, simplest tracker. The project's
methodology note (`docs/methodology.md` on the repository's default branch,
commit `40fa6e7`) lays out later layers: percentile heatmaps, breadth counts and
composite indices. None of that is built yet.

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
    data.py              loaders, through the collectors' own readers
    transform.py         show-as arithmetic, latest-value tables, weekly medians, freshness
    figures.py           the line chart (Plotly)
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
3. Run the tests: `cd Dashboard && python -m pytest`. They check that every
   catalogued series exists, that every default chart builds, and that every
   page renders.

## Tests

```bash
pip install -r Dashboard/requirements-dev.txt
cd Dashboard && python -m pytest
```

All offline. The loaders and charts are checked against the real files under
`Dataset/`, and each page is run through Streamlit's `AppTest` harness.
