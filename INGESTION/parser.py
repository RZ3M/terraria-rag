"""
INGESTION/parser.py — HTML/wikitext parsing utilities.

Parses raw MediaWiki page content (wikitext) into structured sections.
Handles:
- Section heading extraction (== Heading == syntax)
- HTML tag stripping with cleanup
- Infobox extraction
- Table serialization
- Category inference
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from bs4 import BeautifulSoup, NavigableString, Tag

from COMMON.config import (
    CHUNK_HTML_STRIP,
    CHUNK_HEADING_TAGS,
    INFOBOX_TAGS,
    TABLE_ROW_SEPARATOR,
    TABLE_CELL_SEPARATOR,
    WIKI_CATEGORIES,
)
from COMMON.types import WikiPage

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Category inference
# ---------------------------------------------------------------------------

def infer_category(wiki_title: str, page_content: str) -> tuple[str, str]:
    """
    Attempt to infer the category and subcategory from page title and content.

    Returns
    -------
    tuple[str, str]
        (category, subcategory) — both may be empty strings if unknown.
    """
    title_lower = wiki_title.lower()
    content_lower = page_content.lower()[:5000]  # check first 5k chars

    # Weapon patterns
    weapon_types = {
        "Melee": ["sword", "spear", "axe", "hammer", "boomerang"],
        "Ranged": ["bow", "gun", "rifle", "shotgun", "pistol", "musket"],
        "Magic": ["wand", "staff", "book", "tome"],
        "Summon": ["summoning", "minion", "whip"],
        "Throwing": ["thrown", "knife", "grenade", "dart"],
    }

    # Armor slots
    armor_types = {
        "Head": ["helmet", "mask", "hat", "hood", "crown"],
        "Body": ["chestplate", "vest", "shirt", "tunic"],
        "Legs": ["greaves", "pants", "boots", "leggings"],
    }

    # Block/environment patterns
    biome_keywords = {
        "Biomes": ["surface", "underground", "cavern", "corruption", "crimson",
                   "hallow", "desert", "snow", "jungle", "ocean", "dungeon",
                   "temple", "lihzhard", "shimmer"],
        "Blocks": ["stone", "dirt", "sand", "mud", "clay", "ice", "snow",
                   "obsidian", "ash", "pearlstone", "ebonsand", " Crimsand"],
    }

    # Obtain method patterns
    obtain_patterns = {
        "Crafting": ["crafted", "crafting", "at an anvil", "at a work bench",
                     "in a bottle", "on a keg", "at the tinkerer's workshop"],
        "Drop": ["dropped by", "drops from", "drops by", "rare drop"],
        "Purchase": ["sold by", "available for", "bought for", "purchased"],
        "Fishing": ["caught with", "fishing", "caught during", "fish"],
        "Boss": ["boss", "summoned", "defeating", "moon lord", "plantera"],
        "Event": ["event", "blood moon", "solar eclipse", "pirate invasion",
                  "frost legion", "goblin army"],
    }

    category = ""
    subcategory = ""

    # Try to detect item type from title
    title_words = title_lower.replace("-", " ").replace("_", " ").split()
    title_set = set(title_words)

    for wtype, keywords in weapon_types.items():
        if any(kw in title_lower for kw in keywords) or any(kw in title_set for kw in keywords):
            category = "Weapons"
            subcategory = wtype
            break

    if not category:
        for atype, keywords in armor_types.items():
            if any(kw in title_lower for kw in keywords):
                category = "Armor"
                subcategory = atype
                break

    if not category:
        for btype, keywords in biome_keywords.items():
            if any(kw in title_lower for kw in keywords):
                category = btype
                break

    # Fallback: scan first 5k of content for category signals
    if not category:
        for cat, keywords in biome_keywords.items():
            if any(kw in content_lower for kw in keywords):
                category = cat
                break

    if not category:
        # Generic heuristics
        if any(w in title_lower for w in ["ore", "bar", "ingot"]):
            category = "Ores"
        elif any(w in title_lower for w in ["potion", "potion", "elixir", "flask"]):
            category = "Potions"
        elif any(w in title_lower for w in ["npc", "merchant", "guide", "nurse"]):
            category = "Town NPCs"
        elif any(w in title_lower for w in ["boss", "event"]):
            category = "Bosses"

    # Game mode inference
    hardmode_signals = ["hardmode", " post-", "post-", "moon lord", "plantera",
                        "golem", "fishron", "cultist", "lunatic"]
    post_ml_signals = ["moon lord", "solar", "stardust", "nebula", "vortex"]
    premade_signals = ["pre-hardmode", "prehardmode", "before hardmode"]

    game_modes = []
    if any(s in content_lower for s in premade_signals):
        game_modes.append("Pre-Hardmode")
    elif any(s in content_lower for s in post_ml_signals):
        game_modes = ["Hardmode", "Post-Moon Lord"]
    elif any(s in content_lower for s in hardmode_signals):
        game_modes = ["Hardmode"]

    return category, subcategory


# ---------------------------------------------------------------------------
# Section extraction
# ---------------------------------------------------------------------------

@dataclass
class ParsedSection:
    """A single section from a parsed wiki page."""
    heading: str          # e.g. "Crafting" or "Stats" or "" for intro
    heading_level: int    # 1=main, 2=h2, 3=h3, etc.
    path: str             # dot-joined path: "Night's Edge.Stats.Crafting"
    content_html: str     # HTML content between this heading and the next
    content_text: str     # stripped plain text
    raw_content: str      # original wikitext/HTML untouched


def parse_wiki_page(wiki_page: WikiPage) -> list[ParsedSection]:
    """
    Parse a wiki page's wikitext content into structured sections.

    Handles both wikitext (=== Heading ===) and HTML formats.
    Splits on headings to create semantic chunks.

    Parameters
    ----------
    wiki_page : WikiPage
        The raw wiki page with content from the MediaWiki API.

    Returns
    -------
    list[ParsedSection]
        List of sections in document order.
    """
    content = wiki_page.content

    # Detect format: HTML or wikitext
    is_html = content.strip().startswith("<") or "<html" in content.lower()

    if is_html:
        return _parse_html(content, wiki_page.title)
    else:
        return _parse_wikitext(content, wiki_page.title)


def _parse_html(html: str, page_title: str) -> list[ParsedSection]:
    """Parse HTML-format wiki content."""
    soup = BeautifulSoup(html, "lxml")

    sections: list[ParsedSection] = []
    current_heading = ""
    current_heading_level = 1
    current_path = page_title
    current_html_parts: list[str] = []
    heading_stack: list[tuple[str, int]] = [(page_title, 1)]

    for element in soup.body.children if soup.body else soup.children:
        if not isinstance(element, (Tag, NavigableString)):
            continue

        if isinstance(element, NavigableString):
            text = str(element).strip()
            if text:
                current_html_parts.append(str(element))
            continue

        tag_name = element.name.lower() if hasattr(element, 'name') else ""

        if tag_name in CHUNK_HEADING_TAGS:
            # Flush current section
            if current_html_parts:
                section_html = "".join(current_html_parts)
                sections.append(ParsedSection(
                    heading=current_heading,
                    heading_level=current_heading_level,
                    path=current_path,
                    content_html=section_html,
                    content_text=_strip_html(section_html),
                    raw_content=section_html,
                ))
                current_html_parts = []

            # Parse new heading
            heading_text = element.get_text(strip=True)
            level = int(tag_name[1])  # h2 -> 2, h3 -> 3

            # Manage heading stack for nested sections
            while heading_stack and heading_stack[-1][1] >= level:
                heading_stack.pop()

            heading_stack.append((heading_text, level))
            current_heading = heading_text
            current_heading_level = level
            current_path = ".".join(h[0] for h in heading_stack)

        else:
            current_html_parts.append(str(element))

    # Flush final section
    if current_html_parts:
        section_html = "".join(current_html_parts)
        sections.append(ParsedSection(
            heading=current_heading,
            heading_level=current_heading_level,
            path=current_path,
            content_html=section_html,
            content_text=_strip_html(section_html),
            raw_content=section_html,
        ))

    return sections


def _parse_wikitext(wikitext: str, page_title: str) -> list[ParsedSection]:
    """
    Parse wikitext-format wiki content.

    Wikitext headings: == Heading == (level 2), === Heading === (level 3), etc.
    """
    sections: list[ParsedSection] = []

    # Regex for wikitext headings: ==, ===, ==== etc.
    heading_pattern = re.compile(r"^(={2,4})\s*(.+?)\s*\1$", re.MULTILINE)

    last_end = 0
    heading_stack: list[tuple[str, int]] = [(page_title, 1)]

    for match in heading_pattern.finditer(wikitext):
        # Content before this heading
        if last_end < match.start():
            content = wikitext[last_end:match.start()]
            heading, level = heading_stack[-1]
            path = ".".join(h[0] for h in heading_stack)
            sections.append(ParsedSection(
                heading=heading,
                heading_level=level,
                path=path,
                content_html=content,
                content_text=_strip_wikitext(content),
                raw_content=content,
            ))

        # Parse new heading
        raw_heading = match.group(0)
        heading_text = match.group(2).strip()
        level = (len(match.group(1)) - 1)  # == -> 2, === -> 3

        while heading_stack and heading_stack[-1][1] >= level:
            heading_stack.pop()

        heading_stack.append((heading_text, level))
        last_end = match.end()

    # Final section
    if last_end < len(wikitext):
        content = wikitext[last_end:]
        heading, level = heading_stack[-1]
        path = ".".join(h[0] for h in heading_stack)
        sections.append(ParsedSection(
            heading=heading,
            heading_level=level,
            path=path,
            content_html=content,
            content_text=_strip_wikitext(content),
            raw_content=content,
        ))

    return sections


# ---------------------------------------------------------------------------
# HTML stripping
# ---------------------------------------------------------------------------

def _strip_html(html: str) -> str:
    """
    Strip HTML tags and normalize whitespace.
    """
    if not html:
        return ""
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text(separator=" ", strip=True)
    return _normalize_whitespace(text)


def _strip_wikitext(wikitext: str) -> str:
    """
    Strip common wikitext markup: ''' ''', [[]], {{}}, {| |}, etc.
    """
    if not wikitext:
        return ""

    text = wikitext

    # Remove template syntax {{ }}
    text = re.sub(r"\{\{[^}]+\}\}", "", text)

    # Remove table syntax {| |}
    text = re.sub(r"\{\|[^\}]*\|\}", "", text, flags=re.DOTALL)

    # Remove link syntax [[Link|Text]] -> Text
    text = re.sub(r"\[\[([^|\]]*\|)?([^\]]+)\]\]", r"\2", text)

    # Remove bold/italic ''' and ''
    text = re.sub(r"'''+", "", text)

    # Remove heading markers === ===
    text = re.sub(r"==+\s*", "", text)

    # Remove ref tags <ref>...</ref>
    text = re.sub(r"<ref[^>]*>.*?</ref>", "", text, flags=re.DOTALL)

    # Remove HTML tags
    text = re.sub(r"<[^>]+>", "", text)

    return _normalize_whitespace(text)


def _normalize_whitespace(text: str) -> str:
    """Collapse multiple spaces/newlines into single spaces."""
    text = re.sub(r"\s+", " ", text)
    return text.strip()
