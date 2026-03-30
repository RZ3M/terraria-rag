"""
INGESTION/html_fetcher.py — Scrapling-based HTML fetching.

Fetches rendered wiki pages using Scrapling (stealthy browser automation)
to bypass anti-bot protections and get fully-expanded content including
crafting recipes that the MediaWiki API cannot return.

Requires: pip install "scrapling[all]>=0.4.1"
           scrapling install --force   # download browser dependencies
"""

import json
import logging
import re
import time
from pathlib import Path
from typing import Optional

from COMMON.config import (
    WIKI_BASE_URL,
    RAW_PAGES_DIR,
    FETCH_REQUEST_DELAY_SEC,
)

try:
    from scrapling.fetchers import StealthySession
    SCRAPLING_AVAILABLE = True
except ImportError:
    SCRAPLING_AVAILABLE = False

logger = logging.getLogger(__name__)


def _t(elem) -> str:
    """Get text content from a Scrapling element as a plain string."""
    return str(elem.get_all_text())


# ---------------------------------------------------------------------------
# Page content extraction
# ---------------------------------------------------------------------------

def _extract_title(page) -> str:
    """Extract the page/item name."""
    for sel in ("#firstHeading", ".firstHeading", "h1#firstHeading"):
        elems = page.css(sel)
        if elems:
            return _t(elems[0]).strip()
    return ""


def _extract_infobox(page) -> str:
    """Extract item stats from the infobox table."""
    parts = []
    for infobox in page.css(".item.infobox, table.infobox"):
        for row in infobox.css("tr"):
            cells = row.css("th, td")
            if len(cells) >= 2:
                label = _t(cells[0]).strip().rstrip(":")
                value = _t(cells[1]).strip()
                if label and value:
                    parts.append(f"{label}: {value}")
            elif len(cells) == 1:
                # Icon-only cells — look for nested item links
                for link in cells[0].css("a"):
                    link_title = link.attrib.get("title", "")
                    if link_title and ":" not in link_title:
                        name = _t(link).strip()
                        if name:
                            parts.append(name)
    return " | ".join(parts)


def _extract_sections(page) -> list[tuple[str, str]]:
    """
    Extract all article sections with their headings and content.
    Walks sibling elements between h2 headings.

    Returns list of (heading, content_text) tuples.
    """
    sections = []

    article = page.css("#mw-content-text, .mw-parser-output, #bodyContent")
    if not article:
        return sections

    article = article[0]
    h2s = article.css("h2")

    for i, h2 in enumerate(h2s):
        heading = _t(h2).strip()

        # Skip navigation/metadata sections
        skip_keywords = ("navigation", "contents", "references", "external links",
                         "see also", "retrieved from", "category")
        if any(kw in heading.lower() for kw in skip_keywords):
            continue

        # Collect content until the next h2
        content_parts = []
        current = h2.next

        # Stop at next h2
        while current is not None and current.tag != "h2":
            tag = current.tag

            if tag in ("p",):
                txt = _t(current).strip()
                if txt:
                    content_parts.append(txt)

            elif tag in ("ul", "ol"):
                for li in current.css("li"):
                    li_text = _t(li).strip()
                    if li_text:
                        content_parts.append(f"• {li_text}")

            elif tag == "div":
                txt = _t(current).strip()
                if txt:
                    # Check if it's a recipe table
                    if current.css("table"):
                        table_text = _parse_recipe_table(current)
                        if table_text:
                            content_parts.append(table_text)
                    else:
                        content_parts.append(txt)

            elif tag == "table":
                table_text = _parse_recipe_table(current)
                if table_text:
                    content_parts.append(table_text)

            elif tag in ("h3", "h4"):
                # Sub-heading — include its text too
                sub_txt = _t(current).strip()
                if sub_txt:
                    content_parts.append(f"[{sub_txt}]")

            current = current.next

        if heading or content_parts:
            sections.append((heading or "Intro", "\n".join(content_parts)))

    return sections


def _parse_recipe_table(elem) -> str:
    """Parse a recipe/result table into readable text."""
    lines = []

    # Find the result (what the recipe creates)
    for result_cell in elem.css(".result-item, .result-item-name, td.result-item"):
        result_name = _t(result_cell).strip()
        if result_name:
            lines.append(f"Creates: {result_name}")

    # Find ingredient rows — typically in tbody > tr
    for tr in elem.css("tbody tr, table tr"):
        cells = [c for c in tr.css("td, th")]
        if len(cells) < 2:
            continue

        cell_texts = [_t(c).strip() for c in cells]
        # Check if this looks like an ingredient row
        non_empty = [c for c in cell_texts if c]
        if not non_empty:
            continue

        # Format as: ingredient1 | ingredient2 | ... | station
        # Usually: [item name] | [quantity] | [crafting station]
        row_str = " | ".join(non_empty)
        lines.append(f"  {row_str}")

    if not lines:
        # Fallback: just dump the table text
        table_text = _t(elem)
        if table_text.strip():
            lines.append(table_text.strip())

    return "\n".join(lines) if lines else ""


def _extract_crafting_tree(page) -> str:
    """
    Extract the crafting tree diagram as text.
    Walks from the 'Crafting tree' h3 section.
    """
    lines = []

    all_h2s = page.css("h2")
    for h2 in all_h2s:
        h2_text = _t(h2).strip()
        if "crafting" not in h2_text.lower():
            continue

        # Walk siblings until next h2
        current = h2.next
        while current is not None and current.tag != "h2":
            # Look for the crafting tree div
            if current.tag == "div":
                div_text = _t(current).strip()
                if div_text:
                    # Filter to just item names (links)
                    item_names = []
                    for link in current.css("a"):
                        title = link.attrib.get("title", "")
                        if title and ":" not in title:
                            name = _t(link).strip()
                            if name:
                                item_names.append(name)

                    # Remove duplicates while preserving order
                    seen = set()
                    for name in item_names:
                        if name not in seen:
                            seen.add(name)
                            lines.append(f"  - {name}")

            elif current.tag in ("h3", "h4"):
                sub_text = _t(current).strip()
                if sub_text and sub_text.lower() not in ("recipes",):
                    lines.append(f"[{sub_text}]")

            current = current.next

    # Deduplicate while preserving order
    seen = set()
    unique_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped not in seen:
            seen.add(stripped)
            unique_lines.append(line)

    return "\n".join(unique_lines)


def _build_article_text(page) -> str:
    """Build full article text from sections."""
    sections = _extract_sections(page)
    output = []

    for heading, content in sections:
        if content.strip():
            if heading and heading != "Intro":
                output.append(f"\n## {heading}\n{content.strip()}")
            else:
                output.append(content.strip())

    return "\n".join(output)


# ---------------------------------------------------------------------------
# HTML Fetcher
# ---------------------------------------------------------------------------

class HTMLFetcher:
    """
    Fetches rendered wiki pages using Scrapling's stealthy browser.

    Gets fully-expanded content including crafting recipes, which the
    MediaWiki API cannot provide (templates like {{recipes}} are returned
    as raw template markup, not expanded content).

    Results are cached to DATA_DIR/html_cache/ for fast re-runs.
    """

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        delay_sec: float = FETCH_REQUEST_DELAY_SEC,
        headless: bool = True,
    ):
        if not SCRAPLING_AVAILABLE:
            raise ImportError(
                "scrapling is not installed. Run:\n"
                "  pip install 'scrapling[all]>=0.4.1'\n"
                "  scrapling install --force"
            )

        self.cache_dir = Path(cache_dir) if cache_dir else RAW_PAGES_DIR / "html_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.delay_sec = delay_sec
        self.headless = headless

    def _cache_path(self, title: str) -> Path:
        safe = title.replace("/", "_").replace("\\", "_").replace(":", "_")[:200]
        return self.cache_dir / f"html_{safe}.json"

    def _from_cache(self, title: str) -> Optional[dict]:
        path = self._cache_path(title)
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, KeyError, ValueError):
                pass
        return None

    def _to_cache(self, title: str, data: dict) -> None:
        path = self._cache_path(title)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Cache write failed for {title}: {e}")

    def fetch(self, title: str, use_cache: bool = True) -> Optional[dict]:
        """
        Fetch a wiki page via Scrapling.

        Returns a dict:
          - title: str
          - url: str
          - content: str (full article text)
          - infobox: str (item stats)
          - crafting: str (crafting tree items)
          - raw_sections: list of (heading, content)
        """
        if use_cache:
            cached = self._from_cache(title)
            if cached:
                logger.debug(f"HTML cache hit: {title}")
                return cached

        url = WIKI_BASE_URL + title.replace(" ", "_")
        logger.info(f"Fetching (Scrapling): {title}")

        try:
            with StealthySession(headless=self.headless) as session:
                page = session.fetch(url, timeout=30000)

                title_text = _extract_title(page)
                infobox = _extract_infobox(page)
                sections = _extract_sections(page)
                article_text = _build_article_text(page)
                crafting_tree = _extract_crafting_tree(page)

                result = {
                    "title": title_text or title,
                    "url": url,
                    "infobox": infobox,
                    "crafting": crafting_tree,
                    "content": article_text,
                    "sections": sections,
                    "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                }

                self._to_cache(title, result)
                logger.info(f"Fetched and cached: {title} ({len(article_text)} chars)")

                time.sleep(self.delay_sec)
                return result

        except Exception as e:
            logger.error(f"Failed to fetch {title}: {e}")
            return None


# ---------------------------------------------------------------------------
# Standalone CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s")

    if len(sys.argv) < 2:
        print("Usage: python html_fetcher.py <page_title>")
        sys.exit(1)

    fetcher = HTMLFetcher()
    title = sys.argv[1]

    result = fetcher.fetch(title)
    if result:
        print(f"=== {result['title']} ===")
        print(f"URL: {result['url']}")
        print()
        if result["infobox"]:
            print("--- INFOBOX ---")
            print(result["infobox"])
            print()
        if result["crafting"]:
            print("--- CRAFTING TREE ---")
            print(result["crafting"])
            print()
        print("--- ARTICLE (first 4000 chars) ---")
        print(result["content"][:4000])
    else:
        print(f"Failed to fetch: {title}")
