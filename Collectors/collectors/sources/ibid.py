"""ibid (Astra) second-hand vehicle auctions — motorcycles and cars.

Adapted from the working notebook scraper.  The selectors and the in-page
extraction function are kept as they were written, because they encode real
knowledge about this markup that is not recoverable from the DOM alone: that
``div.mb-1.w-100`` is a generic utility class matching several nodes so the one
holding a rupiah figure has to be picked out; that the sold state lives in an
``img[alt]`` inside an overlay rather than in any text; that the date row is a
``justify-content-between`` flex whose children must be read separately or they
concatenate into ``"12 Aug 2026Jakarta"``; and that the same overlay has to be
skipped when choosing the vehicle photo.

``ibid.astra.co.id`` is a React single-page app behind F5 BIG-IP: the HTML is a
3 KB shell and every card is rendered client-side, so there is no
requests-and-regex route and a browser is required.  The app does call a JSON
API, but its base URL is AES-encrypted in the bundle; driving the public pages
the way a visitor does is both simpler and more durable.

Two categories are collected, from the slugs in the site's own bundle:
``motor-bekas`` and ``mobil-bekas``.  (``hve-bekas`` and ``lifestyle-bekas``
also exist and are out of scope.)  Pagination is walked until a page yields no
cards rather than to a fixed last page, because the real extent moves — the
uploaded data was 62 pages of motorcycles and 123 of cars.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import os
import re
from dataclasses import dataclass
from urllib.parse import urlencode, urljoin

from .. import paths
from ..errors import SourceUnavailable
from ..model import Listing

BASE = "https://www.ibid.astra.co.id"

#: Where a pre-installed Chromium may already live.  Playwright pins a browser
#: build per release, so a pip-installed Playwright and an image-provided
#: browser routinely disagree about the build number; pointing at the binary
#: avoids re-downloading one, which some runners forbid outright.  Override
#: with ``CHROMIUM_PATH``.
_CHROMIUM_CANDIDATES = (
    "/opt/pw-browsers/chromium",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/usr/bin/google-chrome",
)


def chromium_path() -> str | None:
    """An existing Chromium binary, or ``None`` to let Playwright choose."""
    explicit = os.environ.get("CHROMIUM_PATH")
    if explicit == "auto":
        # Let Playwright use the build it pins.  The candidate list exists for
        # runners that forbid downloading one; where `playwright install` has
        # run, its own build is correct and the runner's Chrome is not -- and
        # GitHub's ubuntu-latest ships /usr/bin/google-chrome, so without this
        # the candidate list would hand Playwright a mismatched browser.
        return None
    if explicit:
        return explicit
    for candidate in _CHROMIUM_CANDIDATES:
        if os.path.exists(candidate):
            return candidate
    return None

CONFIG = {
    "expected_per_page": 24,      # warns if a page returns a different count
    "delay_between_pages": 2000,  # ms, be polite
    "scroll_delay": 900,          # ms between scroll steps (triggers lazy-loaded cards)
    "max_scrolls": 15,
    "page_timeout": 60000,
    "card_timeout": 30000,        # how long to wait for the first card to appear
    "max_pages": 400,             # a guard, not the expected end; see module docstring
    "empty_retries": 3,           # an empty page is retried before it ends the walk
    "retry_delay": 4000,          # ms before retrying an empty or failed page
}

#: What ibid's own front end shows when its backend fails.  Observed twice in a
#: row on ``mobil-bekas`` and then fine on the third attempt, while
#: ``motor-bekas`` served normally throughout -- so it is transient and
#: per-category.  It must never be read as "no more pages": that would end the
#: walk early and silently truncate the scrape.
UPSTREAM_ERROR = "upstream request failed"

SELECTORS = {
    "card": [
        "div.col-lg-3.col-md-4.col-6.px-2.mb-4.d-flex",
        "div[class*='col-lg-3'][class*='mb-4'][class*='d-flex']",
    ],
    "grade": [".grade-box"],
    "title": ["[class*='title-objek-lelang']"],
    "year": ["div.ellipsis", "[class*='ellipsis']"],
    "price": ["div.mb-1.w-100", "[class*='mb-1'][class*='w-100']"],
    "date": [
        "div.px-0.mb-1.d-flex.justify-content-between.w-100.text-ibid-black3",
        "[class*='text-ibid-black3']",
    ],
    "sold": ["div.sold-object", "[class*='sold-object']"],
    # Regex (case-insensitive) matched against the badge img's alt attribute.
    # The site labels these in Indonesian; "sold" is kept as a fallback in case
    # the alt text varies by locale.
    "sold_alt": "terjual|sold",
    # Bundled app assets, not vehicle photos: the card renders
    # /static/media/noimage.*.png when a listing has no photo, alongside the
    # calendar and location icons.  Reporting one as the image would overwrite
    # a real photo URL already on file with a placeholder.
    "asset_prefix": "/static/media/",
}


@dataclass(frozen=True, slots=True)
class Category:
    """One listing category and the dataset file it maintains."""

    slug: str
    prefix: str

    @property
    def url(self) -> str:
        return f"{BASE}/cari-lelang/{self.slug}"

    @property
    def path(self):
        return paths.consumption_csv(self.prefix)


CATEGORIES = (
    Category(slug="motor-bekas", prefix="ibid_motor_data"),
    Category(slug="mobil-bekas", prefix="ibid_car_data"),
)

# Runs inside the page: pulls one row per card.
EXTRACT_JS = r"""
(cfg) => {
    // Try each selector in a list, return the first element that matches.
    const pick = (root, list) => {
        for (const sel of list) {
            const el = root.querySelector(sel);
            if (el) return el;
        }
        return null;
    };
    const pickAll = (root, list) => {
        for (const sel of list) {
            const els = root.querySelectorAll(sel);
            if (els.length) return Array.from(els);
        }
        return [];
    };
    // innerText respects rendered layout; textContent is the safety net for
    // nodes that are present but not laid out yet.
    const raw = (el) => (el ? (el.innerText || el.textContent || '') : '');
    const txt = (el) => (el ? raw(el).trim().replace(/\s+/g, ' ') || null : null);

    const cards = pickAll(document, cfg.card);

    return cards.map((card, i) => {
        // 'div.mb-1.w-100' is a generic utility class and usually matches more
        // than one node, so prefer whichever one actually holds a rupiah figure.
        const priceCandidates = pickAll(card, cfg.price);
        const priceEl =
            priceCandidates.find((d) => /rp/i.test(raw(d))) ||
            priceCandidates[0] ||
            null;

        // Sold badge: the overlay div must contain an img flagged as sold.
        const soldRe = new RegExp(cfg.sold_alt || 'terjual|sold', 'i');
        const soldBox = pick(card, cfg.sold);
        let sold = false;
        let soldLabel = null;
        if (soldBox) {
            const img = soldBox.querySelector('img');
            const alt = img ? (img.getAttribute('alt') || '') : '';
            if (soldRe.test(alt)) {
                sold = true;
                soldLabel = alt;
            }
        }

        // The date row is a justify-content-between flex, so it usually holds
        // two children (date on the left, location/lot on the right). Read them
        // separately — concatenated they'd run together as "12 Aug 2026Jakarta".
        const dateEl = pick(card, cfg.date);
        const dateParts = dateEl
            ? Array.from(dateEl.children).map(txt).filter(Boolean)
            : [];

        const link = card.querySelector('a[href]');

        // Skip the sold badge overlay, the bundled icons, and the "no image"
        // placeholder, so this is a real vehicle photo or nothing at all.
        const assets = cfg.asset_prefix || '/static/media/';
        const img = Array.from(card.querySelectorAll('img[src]')).find((im) => {
            if (soldBox && soldBox.contains(im)) return false;
            if ((im.getAttribute('src') || '').indexOf(assets) === 0) return false;
            return !soldRe.test(im.getAttribute('alt') || '');
        }) || null;

        return {
            position:   i + 1,
            grade:      txt(pick(card, cfg.grade)),
            title:      txt(pick(card, cfg.title)),
            year_build: txt(pick(card, cfg.year)),
            price_raw:  txt(priceEl),
            listed_raw:   dateParts.length ? dateParts.join(' | ') : txt(dateEl),
            listed_parts: dateParts,
            sold:       sold,
            sold_label: soldLabel,
            href:       link ? link.getAttribute('href') : null,
            image:      img ? img.getAttribute('src') : null,
            card_text:  raw(card).trim().replace(/\s+/g, ' ').slice(0, 400),
        };
    });
}
"""


def page_url(base: str, n: int) -> str:
    return f"{base}?{urlencode({'page': n})}"


def parse_price(raw: str | None) -> int | None:
    """``'Rp 85.000.000'`` -> ``85000000``.  ``None`` when there is no figure."""
    if not raw:
        return None
    digits = re.sub(r"[^\d]", "", raw)
    return int(digits) if digits else None


def run_stamp(now: dt.datetime | None = None) -> str:
    """The ``scraped_at_utc`` value for listings first seen in this run.

    Formatted like the values already in the files (``2026-08-17T05:43:59``):
    seconds precision, no offset suffix.
    """
    now = now or dt.datetime.now(dt.timezone.utc)
    return now.replace(tzinfo=None, microsecond=0).isoformat(timespec="seconds")


def rows_to_listings(rows: list[dict], *, page: int, stamp: str, base: str = BASE) -> list[Listing]:
    """Turn one page of extracted cards into listings.

    Pure, so the tests exercise it against a recorded payload rather than a
    browser.  A card with no link is dropped: without a url there is no id, and
    an unidentifiable listing cannot be merged into an accumulating file.
    """
    out: list[Listing] = []
    for row in rows:
        href = row.get("href")
        if not href:
            continue
        parts = row.get("listed_parts") or []
        out.append(
            Listing(
                url=urljoin(base, href),
                page=page,
                position=int(row.get("position") or (len(out) + 1)),
                grade=row.get("grade") or "",
                title=row.get("title") or "",
                year_build=row.get("year_build") or "",
                price_raw=row.get("price_raw") or "",
                price_idr=parse_price(row.get("price_raw")),
                listed_raw=row.get("listed_raw") or "",
                listed_left=parts[0] if len(parts) > 0 else "",
                listed_right=parts[1] if len(parts) > 1 else "",
                sold=bool(row.get("sold")),
                sold_label=row.get("sold_label") or "",
                image=row.get("image") or "",
                scraped_at=stamp,
                card_text=row.get("card_text") or "",
            )
        )
    return out


async def _scroll(page, card_sel: str) -> None:
    """Scroll down in steps so lazy-loaded cards and images render."""
    last = 0
    for _ in range(CONFIG["max_scrolls"]):
        await page.evaluate("window.scrollBy(0, window.innerHeight * 0.9)")
        await page.wait_for_timeout(CONFIG["scroll_delay"])
        count = await page.locator(card_sel).count()
        at_bottom = await page.evaluate(
            "(window.innerHeight + window.scrollY) >= (document.body.scrollHeight - 50)"
        )
        if at_bottom and count == last:
            break
        last = count
    # Settle, then jump back up so nothing is mid-animation when we read.
    await page.wait_for_timeout(500)
    await page.evaluate("window.scrollTo(0, 0)")


async def _scrape_page(page, category: Category, n: int) -> tuple[list[dict], bool]:
    """One page of cards, and whether the site reported an upstream failure."""
    url = page_url(category.url, n)
    await page.goto(url, wait_until="domcontentloaded", timeout=CONFIG["page_timeout"])

    card_sel = SELECTORS["card"][0]
    try:
        await page.wait_for_selector(card_sel, timeout=CONFIG["card_timeout"])
    except Exception:
        # Fall back to the looser selector before concluding the page is empty.
        card_sel = SELECTORS["card"][1]
        try:
            await page.wait_for_selector(card_sel, timeout=8000)
        except Exception:
            return [], await _shows_upstream_error(page)

    await _scroll(page, card_sel)
    rows = await page.evaluate(EXTRACT_JS, SELECTORS)
    return rows, False


async def _shows_upstream_error(page) -> bool:
    try:
        body = await page.inner_text("body")
    except Exception:  # noqa: BLE001 - a page we cannot even read is not a clean end
        return True
    return UPSTREAM_ERROR in body.lower()


async def _scrape_page_with_retries(
    page, category: Category, n: int, *, verbose: bool
) -> tuple[list[dict], bool]:
    """Retry an empty page before believing it.

    An empty page means one of two very different things -- the end of the
    results, or a backend hiccup -- and getting it wrong truncates the scrape.
    Retrying costs a few seconds and tells them apart.
    """
    upstream = False
    for attempt in range(1, CONFIG["empty_retries"] + 1):
        try:
            rows, upstream = await _scrape_page(page, category, n)
        except Exception as exc:  # noqa: BLE001 - one bad page must not lose the run
            rows, upstream = [], True
            if verbose:
                print(f"      page {n} attempt {attempt} failed: {type(exc).__name__}: {exc}")
        if rows:
            if verbose:
                flag = "" if len(rows) == CONFIG["expected_per_page"] else "  <-- unexpected count"
                sold = sum(1 for r in rows if r.get("sold"))
                print(f"      page {n}: {len(rows)} listings ({sold} sold){flag}")
            return rows, False
        if attempt < CONFIG["empty_retries"]:
            if verbose:
                print(f"      page {n}: empty, retrying ({attempt}/{CONFIG['empty_retries']})")
            await page.wait_for_timeout(CONFIG["retry_delay"])
    return [], upstream


async def _scrape_category(
    browser, category: Category, *, stamp: str, max_pages: int, verbose: bool
) -> list[Listing]:
    context = await browser.new_context(
        viewport={"width": 1600, "height": 1000},
        locale="id-ID",
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
    )
    page = await context.new_page()
    listings: list[Listing] = []
    warnings: list[str] = []
    try:
        for n in range(1, max_pages + 1):
            rows, upstream = await _scrape_page_with_retries(page, category, n, verbose=verbose)
            if not rows:
                if upstream:
                    # Stop, but say so: the remaining pages were not read, and
                    # calling that "complete" would quietly lose listings.
                    warnings.append(
                        f"{category.slug}: stopped at page {n} after "
                        f"{CONFIG['empty_retries']} attempts -- the site reported an "
                        f"upstream failure, so pages {n}+ were not read this run"
                    )
                break
            listings.extend(rows_to_listings(rows, page=n, stamp=stamp))
            await page.wait_for_timeout(CONFIG["delay_between_pages"])
        else:
            warnings.append(
                f"{category.slug}: hit the {max_pages}-page guard; there may be more"
            )
    finally:
        await context.close()
    return listings, warnings


async def _scrape_one(category: Category, *, stamp: str, max_pages: int, verbose: bool):
    """Launch a browser, walk one category, close it again.

    One browser per category rather than one per run, so a category that
    finishes can be written before the next one starts -- see ``collect``.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise SourceUnavailable(
            "playwright is not installed; pip install -r Collectors/requirements.txt"
        ) from exc

    async with async_playwright() as p:
        options = {
            "headless": True,
            "args": ["--no-sandbox", "--disable-dev-shm-usage"],
        }
        executable = chromium_path()
        if executable:
            options["executable_path"] = executable
        try:
            browser = await p.chromium.launch(**options)
        except Exception as exc:  # noqa: BLE001
            raise SourceUnavailable(
                f"could not start Chromium ({executable or 'playwright default'}): {exc}"
            ) from exc
        try:
            return await _scrape_category(
                browser, category, stamp=stamp, max_pages=max_pages, verbose=verbose
            )
        finally:
            await browser.close()


def collect(
    *,
    sess=None,
    since: dt.date | None = None,
    dry_run: bool = False,
    backups=None,
    categories=None,
    max_pages: int | None = None,
    verbose: bool = True,
    now: dt.datetime | None = None,
):
    """Scrape both categories and accumulate them into their dataset files.

    ``sess`` and ``since`` are accepted for the common collector signature and
    unused: this source is driven by a browser, and it keeps every listing it
    has ever seen rather than a window of them.
    """
    from ..sinks import listings_csv

    wanted = tuple(categories or CATEGORIES)
    stamp = run_stamp(now)
    pages = max_pages or CONFIG["max_pages"]

    reports = []
    unavailable = []
    for category in wanted:
        if verbose:
            print(f"   {category.slug}")
        # Scraped and written one category at a time.  Both categories together
        # are a few hundred pages and half an hour; holding every listing until
        # the end would mean a failure on the last page of the second category
        # discarded the first one too.
        try:
            listings, warnings = scrape_category(
                category, stamp=stamp, max_pages=pages, verbose=verbose
            )
        except SourceUnavailable as exc:
            print(f"      {category.slug}: {exc}")
            unavailable.append(category.slug)
            continue

        if not listings:
            # Nothing parsed is never written: an accumulating file must not be
            # rewritten from an empty scrape.
            unavailable.append(category.slug)
            continue
        report = listings_csv.upsert(
            category.path, listings, dry_run=dry_run, backups=backups
        )
        report.warnings = warnings
        reports.append(report)

    if unavailable and not reports:
        raise SourceUnavailable(
            f"ibid returned no listings for {', '.join(unavailable)}; "
            f"dataset files left untouched"
        )
    if unavailable:
        reports[0].warnings.append(
            f"no listings for {', '.join(unavailable)}; those files were left untouched"
        )
    return reports


def scrape_category(category: Category, *, stamp: str, max_pages: int, verbose: bool):
    """One category's listings, driving the async scrape from sync code."""
    return asyncio.run(
        _scrape_one(category, stamp=stamp, max_pages=max_pages, verbose=verbose)
    )
