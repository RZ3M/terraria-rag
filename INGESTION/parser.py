"""
INGESTION/parser.py — HTML/wikitext parsing utilities.

Parses raw MediaWiki page content (wikitext) into structured sections.
Handles:
- Section heading extraction (== Heading == syntax)
- HTML tag stripping with cleanup
- Table serialization
- Category inference
"""

import logging
import re
from dataclasses import dataclass

from COMMON.types import WikiPage

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Category inference
# ---------------------------------------------------------------------------

def infer_category(wiki_title: str, page_content: str) -> tuple[str, str]:
    """
    Attempt to infer the category and subcategory from page title and content.
    """
    title_lower = wiki_title.lower()
    content_lower = page_content.lower()[:5000]

    weapon_types = {
        "Melee": ["sword", "spear", "axe", "hammer", "boomerang"],
        "Ranged": ["bow", "gun", "rifle", "shotgun", "pistol", "musket"],
        "Magic": ["wand", "staff", "book", "tome"],
        "Summon": ["summoning", "minion", "whip"],
        "Throwing": ["thrown", "knife", "grenade", "dart"],
    }

    armor_types = {
        "Head": ["helmet", "mask", "hat", "hood", "crown"],
        "Body": ["chestplate", "vest", "shirt", "tunic"],
        "Legs": ["greaves", "pants", "boots", "leggings"],
    }

    biome_keywords = {
        "Biomes": ["surface", "underground", "cavern", "corruption", "crimson",
                   "hallow", "desert", "snow", "jungle", "ocean", "dungeon",
                   "temple", "lihzhard", "shimmer"],
        "Blocks": ["stone", "dirt", "sand", "mud", "clay", "ice", "snow",
                   "obsidian", "ash", "pearlstone", "ebonsand", "Crimsand"],
    }

    category = ""
    subcategory = ""

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

    if not category:
        for cat, keywords in biome_keywords.items():
            if any(kw in content_lower for kw in keywords):
                category = cat
                break

    if not category:
        if any(w in title_lower for w in ["ore", "bar", "ingot"]):
            category = "Ores"
        elif any(w in title_lower for w in ["potion", "elixir", "flask"]):
            category = "Potions"
        elif any(w in title_lower for w in ["npc", "merchant", "guide"]):
            category = "Town NPCs"
        elif any(w in title_lower for w in ["boss", "event"]):
            category = "Bosses"

    return category, subcategory


# ---------------------------------------------------------------------------
# Section extraction
# ---------------------------------------------------------------------------

@dataclass
class ParsedSection:
    """A single section from a parsed wiki page."""
    heading: str
    heading_level: int
    path: str
    content_html: str
    content_text: str
    raw_content: str


def parse_wiki_page(wiki_page: WikiPage) -> list[ParsedSection]:
    """
    Parse a wiki page's wikitext content into structured sections.
    The Terraria wiki uses wikitext from the MediaWiki API.
    """
    content = wiki_page.content
    if not content:
        return []

    return _parse_wikitext(content, wiki_page.title)


def _parse_wikitext(wikitext: str, page_title: str) -> list[ParsedSection]:
    """
    Parse wikitext into sections by splitting on == Heading == lines.
    """
    sections: list[ParsedSection] = []
    heading_pattern = re.compile(r"^(={2,4})\s*(.+?)\s*\1$", re.MULTILINE)

    last_end = 0
    heading_stack: list[tuple[str, int]] = [(page_title, 1)]

    for match in heading_pattern.finditer(wikitext):
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

        heading_text = match.group(2).strip()
        level = len(match.group(1)) - 1

        while heading_stack and heading_stack[-1][1] >= level:
            heading_stack.pop()

        heading_stack.append((heading_text, level))
        last_end = match.end()

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
# Wikitext stripping
# ---------------------------------------------------------------------------

def _strip_wikitext(wikitext: str) -> str:
    """
    Strip wikitext markup, handling nested braces correctly.

    Handles: templates {{}}, tables {| |}, links [[]], bold ''',
    headings, ref tags, HTML.
    """
    if not wikitext:
        return ""

    text = wikitext

    # Strip templates using proper brace-counting (handles nesting)
    text = _strip_templates(text)

    # Remove table block syntax {| |}
    text = re.sub(r"\{\|[^\}]*\|\}", "", text, flags=re.DOTALL)

    # Wiki links: [[Link|Display]] -> Display, [[Link]] -> Link
    text = re.sub(r"\[\[([^|\]]*\|)?([^\]]+)\]\]", r"\2", text)
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)

    # Bold/italic ''' and ''
    text = re.sub(r"'''+", "", text)

    # Headings === ===
    text = re.sub(r"==+\s*", "", text)

    # <ref name="..." /> and <ref>...</ref>
    text = re.sub(r"<ref[^>]*/>", "", text)
    text = re.sub(r"<ref[^>]*>.*?</ref>", "", text, flags=re.DOTALL)

    # HTML tags
    text = re.sub(r"<[^>]+>", "", text)

    return _normalize_whitespace(text)


def _strip_templates(text: str) -> str:
    """
    Strip all {{...}} templates from wikitext using brace-counting.
    Correctly handles nested templates like {{foo|{{bar}}|baz}}.
    """
    result = []
    i = 0
    while i < len(text):
        if text[i:i+2] == "{{":
            # Find matching closing }}
            depth = 0
            j = i
            while j < len(text):
                if text[j:j+2] == "{{":
                    depth += 1
                    j += 2
                elif text[j:j+2] == "}}":
                    depth -= 1
                    j += 2
                    if depth == 0:
                        break
                else:
                    j += 1
            # Skip the entire template (i to j)
            i = j
        else:
            result.append(text[i])
            i += 1
    return "".join(result)


def _normalize_whitespace(text: str) -> str:
    """Collapse multiple spaces/newlines into single spaces."""
    text = re.sub(r"\s+", " ", text)
    return text.strip()
