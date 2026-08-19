"""Wikipedia REST summary API client — free reference photo lookup (plan 2.2).

Best-effort: any failure (404, 5xx, network error, no thumbnail) returns
``None`` rather than raising, since this is a nice-to-have illustration, not
something that should block the add-plant flow.
"""

import logging
import re
import time

import httpx

LOG = logging.getLogger(__name__)

_BASE_URL = "https://en.wikipedia.org/api/rest_v1/page/summary"

# Wikipedia's REST API rejects requests with no User-Agent (HTTP 403) per its
# robot policy (https://w.wiki/4wJS) — a descriptive UA with contact info is
# required, an empty/default one is not enough.
_HEADERS = {"User-Agent": "Droplet/1.0 (self-hosted plant watering tracker; no public contact)"}


def _strip_cultivar(page_title: str) -> str | None:
    """Cultivar/variety names (e.g. ``Syngonium podophyllum 'Neon Robusta'``)
    almost never have their own Wikipedia page, so a lookup for the full name
    404s and (without this) permanently leaves that species without a
    reference image. Returns the base species name with any quoted cultivar
    suffix removed, or ``None`` if there was nothing to strip."""
    base = re.split(r"['\u2018\u2019\"\u201c\u201d]", page_title, maxsplit=1)[0].strip()
    return base if base and base != page_title else None


async def _fetch_summary_thumbnail(page_title: str, timeout: float, client: httpx.AsyncClient) -> str | None:
    slug = page_title.strip().replace(" ", "_")
    url = f"{_BASE_URL}/{slug}"

    start = time.monotonic()
    try:
        response = await client.get(url, timeout=timeout, headers=_HEADERS)
        response.raise_for_status()
    except httpx.HTTPError:
        LOG.info("Wikipedia lookup failed for %r after %.2fs", page_title, time.monotonic() - start, exc_info=True)
        return None
    LOG.info("Wikipedia lookup for %r took %.2fs", page_title, time.monotonic() - start)

    data = response.json()
    thumbnail = data.get("thumbnail")
    if not thumbnail:
        return None
    return thumbnail.get("source")


async def fetch_reference_image_url(
    page_title: str, timeout: float = 10.0, *, client: httpx.AsyncClient | None = None
) -> str | None:
    """`client` should be the shared, app-wide AsyncClient (see app.main) so
    this reuses pooled connections; a private client is created for the
    duration of the call when none is supplied (e.g. in tests/scripts)."""
    if client is not None:
        return await _fetch_reference_image_url(page_title, timeout, client)

    async with httpx.AsyncClient() as owned_client:
        return await _fetch_reference_image_url(page_title, timeout, owned_client)


async def _fetch_reference_image_url(page_title: str, timeout: float, client: httpx.AsyncClient) -> str | None:
    image = await _fetch_summary_thumbnail(page_title, timeout, client)
    if image:
        return image

    base_name = _strip_cultivar(page_title)
    if base_name:
        image = await _fetch_summary_thumbnail(base_name, timeout, client)
    return image

