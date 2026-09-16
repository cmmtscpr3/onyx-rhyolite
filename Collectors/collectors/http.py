"""One HTTP session factory for every collector.

Three things live here because every collector needs them and none should
reimplement them:

* **Retries.**  ``bi.go.id`` closes connections mid-handshake often enough that
  a single attempt fails several times an hour.  Connection errors are retried,
  not just HTTP 5xx.
* **A browser user agent.**  Some Indonesian portals answer the default
  python-requests agent with a block page and a browser agent with data; that
  is the portal's rule, not an attempt to hide what we are.
* **Block-page detection.**  A WAF interstitial arrives as HTTP 200 carrying
  HTML.  ``fetch`` raises on one rather than returning it, so a block page can
  never be parsed into data by accident and silently emptied into a dataset.
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass
from typing import Any, Mapping

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .dates import now_utc

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

DEFAULT_TIMEOUT = (15, 180)  # connect, read

#: A probe answers "can this runner read this source", so it gets a much
#: tighter budget than a fetch.  A host that hangs is a finding; waiting three
#: minutes for it does not change the finding.
PROBE_TIMEOUT = (5, 15)


class FetchError(RuntimeError):
    """A source could not be read."""

    def __init__(self, message: str, *, url: str) -> None:
        super().__init__(message)
        self.url = url


class BlockedError(FetchError):
    """The source answered, but with a block page rather than data."""


#: Substrings that mark a WAF interstitial rather than the requested document.
#: Checked only on small text/html responses, so a data file that happens to
#: contain one of these words is not rejected.
_BLOCK_MARKERS = (
    "waf block",
    "akses ini ditolak",
    "this access is blocked by our security system",
    "attention required! | cloudflare",
)
_BLOCK_SCAN_LIMIT = 200_000


def session(
    *,
    total_retries: int = 4,
    backoff: float = 2.0,
    headers: Mapping[str, str] | None = None,
) -> requests.Session:
    """A session with browser headers and retries on connection errors."""
    retry = Retry(
        total=total_retries,
        connect=total_retries,
        read=total_retries,
        status=total_retries,
        backoff_factor=backoff,
        status_forcelist=(429, 500, 502, 503, 504, 520, 521, 522, 524),
        allowed_methods=frozenset({"GET", "HEAD", "POST"}),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_maxsize=8)
    sess = requests.Session()
    sess.mount("https://", adapter)
    sess.mount("http://", adapter)
    sess.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
    )
    if headers:
        sess.headers.update(headers)
    return sess


def looks_blocked(response: requests.Response) -> bool:
    """True when a 200 carries a WAF interstitial instead of the document."""
    if not response.ok:
        return False
    content_type = response.headers.get("Content-Type", "").lower()
    if "html" not in content_type and "text" not in content_type:
        return False
    if len(response.content) > _BLOCK_SCAN_LIMIT:
        return False
    body = response.content[:_BLOCK_SCAN_LIMIT].decode("utf-8", "replace").lower()
    return any(marker in body for marker in _BLOCK_MARKERS)


@dataclass(frozen=True, slots=True)
class Payload:
    """Bytes fetched from a source, with the provenance a collector reports."""

    url: str
    content: bytes
    obtained_at: dt.datetime
    content_type: str

    def text(self, encoding: str = "utf-8") -> str:
        return self.content.decode(encoding, "replace")

    def json(self) -> Any:
        return json.loads(self.text())


def fetch(
    url: str,
    *,
    sess: requests.Session | None = None,
    params: Mapping[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
    obtained_at: dt.datetime | None = None,
    timeout: tuple[int, int] = DEFAULT_TIMEOUT,
) -> Payload:
    """GET ``url``, raising rather than returning anything unparseable."""
    sess = sess or session()
    obtained_at = obtained_at or now_utc()
    try:
        response = sess.get(
            url,
            params=dict(params or {}),
            headers=dict(headers or {}),
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise FetchError(f"{type(exc).__name__} fetching {url}: {exc}", url=url) from exc

    if looks_blocked(response):
        raise BlockedError(
            f"{url} answered {response.status_code} with a block page", url=response.url
        )
    if not response.ok:
        raise FetchError(f"{url} answered HTTP {response.status_code}", url=response.url)

    return Payload(
        url=response.url,
        content=response.content,
        obtained_at=obtained_at,
        content_type=response.headers.get("Content-Type", ""),
    )


@dataclass(frozen=True, slots=True)
class ProbeResult:
    url: str
    reachable: bool
    status: int | None
    detail: str


def probe(
    url: str,
    *,
    sess: requests.Session | None = None,
    timeout: tuple[int, int] = PROBE_TIMEOUT,
) -> ProbeResult:
    """Can this runner read this source?  Never raises."""
    sess = sess or session(total_retries=1, backoff=0.5)
    try:
        response = sess.get(url, timeout=timeout, stream=True)
    except requests.RequestException as exc:
        return ProbeResult(url, False, None, f"{type(exc).__name__}: {exc}"[:200])
    try:
        if looks_blocked(response):
            return ProbeResult(url, False, response.status_code, "WAF block page")
        if not response.ok:
            return ProbeResult(
                url, False, response.status_code, f"HTTP {response.status_code}"
            )
        return ProbeResult(url, True, response.status_code, "ok")
    finally:
        response.close()
