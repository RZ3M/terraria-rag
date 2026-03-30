"""
INGESTION/parser_html.py — HTML-based parser for MediaWiki rendered content.

Uses MediaWiki's action=parse&prop=text to get fully-rendered HTML.
Templates (like recipe boxes) are expanded into real HTML with actual
item names, stats, and tables — unlike wikitext which has raw {{templates}}.

Key design: split on h2 headings only. h3/h4 update the sub-path
without creating new sections — this prevents recipe tables and other
content from being orphaned between sub-headings.
"""

import logging
import re
from dataclasses import dataclass
from typing import Optional

from bs4 import BeautifulSoup

from COMMON.types import WikiPage

logger = logging.getLogger(__name__)


@dataclass
class ParsedSection:
    """A single section from a parsed wiki page."""
    heading: str
    heading_level: int
    path: str
    content_html: str
    content_text: str
    raw_content: str


def parse_html_page(wiki_page: WikiPage) -> list[ParsedSection]:
    """
    Parse rendered HTML content into structured sections.
    Only h2 headings create new sections; h3/h4 update the sub-path.
    """
    content = wiki_page.content
    if not content:
        return []

    soup = BeautifulSoup(content, "lxml")
    _remove_noise(soup)

    # Find the main content container — might have multiple classes including "mw-parser-output"
    container = None
    for div in soup.find_all("div"):
        classes = div.get("class") or []
        if "mw-parser-output" in classes:
            container = div
            break
    if not container:
        container = soup.find("body")
    if not container:
        container = soup

    sections: list[ParsedSection] = []
    heading_stack: list[tuple[str, int]] = [(wiki_page.title, 1)]
    current_html_parts: list[str] = []

    heading_tags = {"h1", "h2", "h3", "h4", "h5", "h6"}

    # Walk direct children of the container (not all descendants)
    for element in container.children:
        if not hasattr(element, 'name') or element.name is None:
            # Text node
            text = str(element).strip()
            if text:
                current_html_parts.append(str(element))
            continue

        tag_name = element.name.lower()

        if tag_name in heading_tags:
            # Strip the [edit] suffix from heading text
            heading_text = re.sub(r'\[edit\]$', '', element.get_text(strip=True))
            level = int(tag_name[1])

            if level == 2:
                # h2 — flush current section and start new one
                if current_html_parts:
                    section_html = "".join(current_html_parts)
                    section_path = ".".join(h[0] for h in heading_stack)
                    sections.append(ParsedSection(
                        heading=heading_stack[-1][0],
                        heading_level=heading_stack[-1][1],
                        path=section_path,
                        content_html=section_html,
                        content_text=_html_to_text(section_html),
                        raw_content=section_html,
                    ))
                    current_html_parts = []

                # Reset stack to h2 level
                heading_stack = [(wiki_page.title, 1), (heading_text, 2)]
                current_html_parts.append(str(element))

            elif level >= 3:
                # h3+ — update sub-path WITHOUT flushing content
                while heading_stack and heading_stack[-1][1] >= level:
                    heading_stack.pop()
                heading_stack.append((heading_text, level))
                # Add the heading element itself to content
                current_html_parts.append(str(element))

        else:
            # Non-heading element — add to current section
            current_html_parts.append(str(element))

    # Flush final section
    if current_html_parts:
        section_html = "".join(current_html_parts)
        section_path = ".".join(h[0] for h in heading_stack)
        heading_text = heading_stack[-1][0] if heading_stack else wiki_page.title
        sections.append(ParsedSection(
            heading=heading_text,
            heading_level=heading_stack[-1][1] if heading_stack else 1,
            path=section_path,
            content_html=section_html,
            content_text=_html_to_text(section_html),
            raw_content=section_html,
        ))

    return sections


def _remove_noise(soup: BeautifulSoup) -> None:
    """Remove navigation, edit links, references, and other non-content elements."""
    noise_patterns = [
        {"class": "mw-editsection"},
        {"class": "toc"},
        {"class": "navbox"},
        {"class": "printfooter"},
        {"id": "catlinks"},
        {"class": "references"},
    ]
    # Use a list() copy to avoid iterator invalidation during decompose
    for attrs in noise_patterns:
        for elem in list(soup.find_all(attrs=attrs)):
            elem.decompose()

    # Reference template dumps: remove <ol class="references"> (already caught)
    # Also remove the section divs that wrap reference lists — but NOT the main container
    for div in list(soup.find_all("div")):
        elem_class = div.get("class") or []
        # Protect the main article container
        if "mw-parser-output" in elem_class:
            continue
        # A reference section div contains the reference heading and list
        if (div.find("ol", class_="references") or div.find("ol", {"id": "references"})
                or div.find("div", class_="references")):
            div.decompose()
    """Remove navigation, edit links, references, and other non-content elements."""
    noise_patterns = [
        {"class": "mw-editsection"},
        {"class": "toc"},
        {"class": "navbox"},
        {"class": "printfooter"},
        {"id": "catlinks"},
        {"class": "references"},
    ]
    # Use a list() copy to avoid iterator invalidation during decompose
    for attrs in noise_patterns:
        for elem in list(soup.find_all(attrs=attrs)):
            elem.decompose()

    # Reference template dumps: remove <ol class="references"> (already caught)
    # Also remove the section divs that wrap reference lists
    for div in list(soup.find_all("div")):
        # A reference section div contains the reference heading and list
        if (div.find("ol", class_="references") or div.find("ol", {"id": "references"})
                or div.find("div", class_="references")):
            div.decompose()
        # Don't remove article content elements
        elem_class = div.get("class") or []
        if "mw-parser-output" in elem_class:
            continue


def _html_to_text(html: str) -> str:
    """
    Extract plain text from HTML, preserving structure.
    Converts recipe tables to readable text with actual item names.
    """
    soup = BeautifulSoup(html, "lxml")
    text_parts = []

    # Extract recipe tables with item names
    for table in soup.find_all("table", class_="recipes"):
        text_parts.append("\n[Crafting Recipe]\n")
        rows = table.find_all("tr")
        for row in rows:
            cells = []
            for cell in row.find_all(["th", "td"]):
                # Extract items from top-level ingredient divs only.
                # The Terraria wiki wraps each ingredient in <div class="ingredient">.
                # Nested ingredient divs = sub-recipes (don't count as top-level ingredients).
                ingredient_divs = cell.find_all("div", class_="ingredient", recursive=False)
                # Collect items from ingredient divs AND direct <a> links in the cell.
                # The Terraria wiki wraps some ingredient groups in an outer <a> link.
                # Strategy: collect top-level ingredient divs AND any direct <a> children
                # of the cell, then deduplicate.
                items = []
                seen_titles = set()

                # Direct <a> children of the cell (includes wrapping links like True Excalibur)
                for child in cell.children:
                    if hasattr(child, 'name') and child.name == "a":
                        title = child.get("title", "")
                        if title and not title.startswith("File:") and title not in seen_titles:
                            items.append(title)
                            seen_titles.add(title)

                # Direct child ingredient divs only (not nested ones)
                for child in cell.children:
                    if (hasattr(child, 'name') and child.name == "div"
                            and "ingredient" in child.get("class", [])):
                        # Direct <a> children of this ingredient div
                        for a in child.children:
                            if hasattr(a, 'name') and a.name == "a":
                                title = a.get("title", "")
                                if title and not title.startswith("File:") and title not in seen_titles:
                                    items.append(title)
                                    seen_titles.add(title)

                if items:
                    cells.append(" + ".join(items))
                else:
                    cell_text = cell.get_text(strip=True)
                    if cell_text:
                        cells.append(cell_text)
            if cells:
                text_parts.append(" | ".join(cells) + "\n")

    # Also extract crafting-tree style divs
    for div in soup.find_all("div", class_="crafter2"):
        text_parts.append(div.get_text(strip=True) + "\n")

    # Walk elements for regular text (skip content already in recipe tables)
    recipe_table_parents = set()
    for table in soup.find_all("table", class_="recipes"):
        for parent in table.parents:
            if hasattr(parent, 'name'):
                recipe_table_parents.add(id(parent))

    for element in soup.find_all(["p", "li", "h2", "h3", "h4", "div"]):
        tag = element.name.lower()
        text = element.get_text(strip=True)

        if not text or len(text) < 2:
            continue

        # Skip elements inside recipe tables
        for parent in element.parents:
            if id(parent) in recipe_table_parents:
                break
        else:
            if tag in ("h2", "h3", "h4"):
                text_parts.append(f"\n## {text}\n")
            elif tag == "li":
                text_parts.append(f"• {text}\n")
            elif tag == "p":
                text_parts.append(text + " ")

    text = "".join(text_parts)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" +", " ", text)
    return text.strip()
