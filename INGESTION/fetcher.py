"""
INGESTION/fetcher.py — MediaWiki API fetching with caching.

Fetches the full Terraria wiki page list and individual page content
via the MediaWiki Action API. Implements polite rate-limiting, retries,
and local JSON caching to allow resumable ingestion.

API Docs: https://www.mediawiki.org/wiki/API:Main_page
"""

import json
import logging
import time
from pathlib import Path
from typing import Iterator, Optional

import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from COMMON.config import (
    WIKI_API_BASE,
    WIKI_BASE_URL,
    FETCH_BATCH_SIZE,
    FETCH_REQUEST_DELAY_SEC,
    FETCH_MAX_RETRIES,
    FETCH_MIN_PAGE_LENGTH,
    RAW_PAGES_DIR,
)
from COMMON.types import WikiPage

logger = logging.getLogger(__name__)

_session = requests.Session()
_session.headers.update({
    "User-Agent": "TerrariaRAGBot/1.0 (https://github.com/grapes/terraria-rag; educational project)"
})


# ---------------------------------------------------------------------------
# Low-level API calls
# ---------------------------------------------------------------------------

@retry(
    retry=retry_if_exception_type((requests.exceptions.HTTPError, requests.exceptions.Timeout)),
    stop=stop_after_attempt(FETCH_MAX_RETRIES),
    wait=wait_exponential(multiplier=2, min=5, max=60),
    reraise=True,
    before_sleep=lambda retry_state: logger.warning(
        f"Request failed (attempt {retry_state.attempt_number}), "
        f"retrying in {retry_state.next_action.sleep}s..."
    ),
)
def _api_get(params: dict, timeout: int = 30) -> dict:
    """
    Make a GET request to the wiki API with retry logic.
    Retries on 429 (rate limit) and 5xx errors with exponential backoff.
    """
    params["format"] = "json"
    response = _session.get(WIKI_API_BASE, params=params, timeout=timeout)

    # Handle rate limiting specifically
    if response.status_code == 429:
        # Check for Retry-After header
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            wait_time = int(retry_after)
        else:
            wait_time = 30  # default 30s
        logger.warning(f"Rate limited! Waiting {wait_time}s before retry.")
        time.sleep(wait_time)
        response = _session.get(WIKI_API_BASE, params=params, timeout=timeout)

    response.raise_for_status()
    return response.json()


def _be_polite():
    """Sleep between requests to avoid hammering the wiki."""
    time.sleep(FETCH_REQUEST_DELAY_SEC)


# ---------------------------------------------------------------------------
# Page list fetching
# ---------------------------------------------------------------------------

def fetch_all_page_titles(
    exclude_redirects: bool = True,
    namespaces: Optional[list[int]] = None,
) -> Iterator[WikiPage]:
    """
    Fetch all page titles from the wiki, iterating through all pages.

    Yields WikiPage objects with page_id, title, and url set.
    Content is NOT fetched here — use fetch_page_content() separately.

    Parameters
    ----------
    exclude_redirects : bool
        If True, skip redirect pages.
    namespaces : list[int], optional
        Filter to specific namespace IDs.
        MediaWiki namespace IDs:
        0 = Main (articles), 1 = Talk, 2 = User, etc.

    Yields
    ------
    WikiPage
        Lightweight page descriptor (no content yet).
    """
    continue_token: Optional[str] = None
    total_fetched = 0

    while True:
        _be_polite()

        params = {
            "action": "query",
            "list": "allpages",
            "aplimit": FETCH_BATCH_SIZE,
        }

        if exclude_redirects:
            params["apfilterredir"] = "nonredirects"

        if namespaces is not None:
            params["apnamespace"] = "|".join(str(n) for n in namespaces)

        if continue_token:
            params["apcontinue"] = continue_token

        data = _api_get(params)

        pages = data.get("query", {}).get("allpages", [])
        if not pages:
            break

        for page in pages:
            title = page["title"]
            # Skip subpages (language variants like "Page/ja", "Page/de", etc.)
            if "/" in title:
                logger.debug(f"Skipping subpage: {title}")
                continue

            wiki_page = WikiPage(
                page_id=page["pageid"],
                title=title,
                url=WIKI_BASE_URL + title.replace(" ", "_"),
                content="",  # not fetched yet
                is_redirect=page.get("redirect", False),
                length=page.get("length", 0),
            )
            total_fetched += 1
            yield wiki_page

        # Handle continue token for pagination
        continue_data = data.get("continue", {})
        continue_token = continue_data.get("apcontinue")
        if not continue_token:
            break

    logger.info(f"Finished fetching page list. Total pages found: {total_fetched}")


# ---------------------------------------------------------------------------
# Individual page content fetching
# ---------------------------------------------------------------------------

def fetch_page_content(title: str, cache_dir: Path = RAW_PAGES_DIR) -> Optional[WikiPage]:
    """
    Fetch the full content of a single wiki page.

    Uses MediaWiki's 'prop=revisions&rvslots=main' to get wikitext.
    Results are cached to cache_dir/title_id.json so re-runs are fast.

    Parameters
    ----------
    title : str
        Exact page title as it appears on the wiki.
    cache_dir : Path
        Directory to cache raw JSON responses.

    Returns
    -------
    WikiPage or None
        WikiPage with content populated, or None if the page was not found
        or is a redirect (and we're excluding redirects).
    """
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Sanitize title for use as a filename
    safe_title = title.replace("/", "_").replace("\\", "_").replace(":", "_")[:200]
    cache_file = cache_dir / f"{safe_title}.json"

    # Check cache first
    if cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cached = json.load(f)
            logger.debug(f"Cache hit for: {title}")
            return WikiPage(**cached)
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Corrupt cache for {title}, re-fetching: {e}")

    _be_polite()

    params = {
        "action": "query",
        "prop": "revisions",
        "rvprop": "content|ids|size|timestamp",
        "rvslots": "main",
        "titles": title,
        "explaintext": 0,  # keep HTML/wikitext
        "inprop": "url",
    }

    data = _api_get(params)
    pages = data.get("query", {}).get("pages", {})

    for page_id_str, page_data in pages.items():
        # pageid -1 means page doesn't exist
        if int(page_id_str) < 0:
            logger.warning(f"Page not found: {title}")
            return None

        revisions = page_data.get("revisions", [])
        if not revisions:
            logger.warning(f"No revisions for page: {title}")
            return None

        revision = revisions[0]
        slots = revision.get("slots", {}).get("main", {})
        content = slots.get("*", "") or ""

        wiki_page = WikiPage(
            page_id=int(page_id_str),
            title=page_data["title"],
            url=page_data.get("fullurl", WIKI_BASE_URL + page_data["title"].replace(" ", "_")),
            content=content,
            is_redirect=page_data.get("redirect", False),
            length=revision.get("size", 0),
        )

        # Cache the result
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump({
                    "page_id": wiki_page.page_id,
                    "title": wiki_page.title,
                    "url": wiki_page.url,
                    "content": wiki_page.content,
                    "is_redirect": wiki_page.is_redirect,
                    "length": wiki_page.length,
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Failed to cache {title}: {e}")

        return wiki_page

    return None


def fetch_pages_incremental(
    titles: list[str],
    cache_dir: Path = RAW_PAGES_DIR,
    skip_small: bool = True,
) -> Iterator[WikiPage]:
    """
    Fetch a batch of pages, skipping small/redirect pages.

    Parameters
    ----------
    titles : list[str]
        List of page titles to fetch.
    cache_dir : Path
        Cache directory for raw page JSON.
    skip_small : bool
        Skip pages shorter than FETCH_MIN_PAGE_LENGTH characters.

    Yields
    ------
    WikiPage
        Pages that pass the filters.
    """
    for title in titles:
        page = fetch_page_content(title, cache_dir)
        if page is None:
            continue
        if page.is_redirect:
            logger.debug(f"Skipping redirect: {title}")
            continue
        if skip_small and page.length < FETCH_MIN_PAGE_LENGTH:
            logger.debug(f"Skipping small page ({page.length} chars): {title}")
            continue
        yield page


# ---------------------------------------------------------------------------
# Get just the page list (without content) — for initial sitemap
# ---------------------------------------------------------------------------

def save_page_list(output_path: Path) -> int:
    """
    Fetch the full page list and save it as JSON for later use.

    Returns the total number of pages found.
    """
    pages = list(fetch_all_page_titles(exclude_redirects=True, namespaces=[0]))
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump([{
            "page_id": p.page_id,
            "title": p.title,
            "url": p.url,
            "length": p.length,
        } for p in pages], f, ensure_ascii=False, indent=2)

    logger.info(f"Saved {len(pages)} page titles to {output_path}")
    return len(pages)
