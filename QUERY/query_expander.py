"""
QUERY/query_expander.py — Query expansion for Terraria game terminology.

Maps natural player queries (e.g. "best ranger setup for wall of flesh")
to wiki-compatible search terms that match item names and game concepts.

Usage:
    expanded = expand_query("best ranger item setup for wall of flesh")
    # → "ranger ranged weapons guns bullets wall of flesh boss Clockwork Assault Rifle Ichor"
"""

import re
from typing import Optional


# ---------------------------------------------------------------------------
# Game terminology mappings
# ---------------------------------------------------------------------------

# Player class / build → weapon types
CLASS_TO_WEAPONS = {
    "ranger": ["ranged", "guns", "bow", "rifle", "shotgun", "pistol", "bullet", "arrow"],
    "warrior": ["melee", "sword", "spear", "axe", "hammer", "boomerang"],
    "mage": ["magic", "staff", "wand", "book", "tome"],
    "summoner": ["summon", "minion", "whip", "staff"],
    "thunker": ["thrown", "knife", "dart", "grenade"],
}

# Boss names (partial match) → specific terms
BOSS_TERMS = {
    "wall of flesh": [
        "Wall of Flesh", "guide", "hardmode", "Musket Ball", "Ichor", "Shroomite",
        "Clockwork Assault Rifle", "Endless Musket Pouch", "Molten Fury", "Flamethrower",
        "Demon Conch", "Astral Hamaxe", "Night's Edge", "Excalibur",
    ],
    "skeletron": [
        "Skeletron", "Dungeon", "Bone", "Flail", "Book",
    ],
    "queen slime": [
        "Queen Slime", "Crystal", "Slime", "Gel",
    ],
    "the destroyer": [
        "The Destroyer", "Mechdusa", "Cobalt", "Mythril", "Adamantite",
        "Giant Pearl", "Orichalcum",
    ],
    "retinazer": [
        "Retinazer", "Spysker", "Mechdusa",
    ],
    "skeletron prime": [
        "Skeletron Prime", "Mechdusa",
    ],
    "plantera": [
        "Plantera", "Temple", "Gems", "Amphibian", "Buccaneer",
    ],
    "golem": [
        "Golem", "Temple", "Lihzhard", "Picksaw",
    ],
    "duke fishron": [
        "Duke Fishron", "Frog", "Truffle",
    ],
    "moon lord": [
        "Moon Lord", "Celestial", "Meowmere", "Star Wrath", "S.D.M.G.",
        "Last Prism", "Lunar", "Solar", "Nebula", "Vortex", "Stardust",
    ],
    "empress of light": [
        "Empress of Light", "Hallow", "Terraprisma",
    ],
    "queen antlion": [
        "Queen Antlion", "Antlion", "Sand",
    ],
    "deerclops": [
        "Deerclops", "Snow", "Ice",
    ],
    "all bosses": [
        "boss", "tips", "arena", "strategy",
    ],
}

# Generic game terms → wiki-relevant terms
TERM_EXPANSION = {
    # Weapon types
    "gun": ["guns", "rifle", "shotgun", "pistol"],
    "bow": ["bow", "arrow", "arrows"],
    "sword": ["sword", "swords", "blade"],
    "staff": ["staff", "wand", "magic"],
    "spear": ["spear", "trident", "javelin"],
    "flail": ["flail", "chain"],
    "boomerang": ["boomerang"],
    "minion": ["minion", "summon", "summoning"],
    "whip": ["whip", "summon"],

    # Armor types
    "armor": ["armor", "helmet", "chestplate", "leggings", "set bonus"],

    # Game concepts
    "crafting": ["crafting", "recipe", "ingredients", "craft", "station"],
    "drop": ["drops", "rare drop", "chance", "1/", "loot"],
    "arena": ["arena", "battle", "strategy", "battlefield"],
    "biome": ["biome", "surface", "underground", "corruption", "crimson", "hallow", "jungle"],
    "hardmode": ["hardmode", "hard mode", "mechanical boss", "after hardmode"],
    "pre-hardmode": ["pre-hardmode", "pre hardmode", "pre-hard mode", "prehardmode"],
    "accessory": ["accessory", "accessories", "belt", "hook"],
    "mount": ["mount", "mounts", "riding"],
    "pet": ["pet", "pets", "light pet", "companion"],
    "potion": ["potion", "buff", "elixir"],
    "ammo": ["ammo", "ammunition", "bullet", "arrow", "dart"],
    "ore": ["ore", "ores", "bar", "metal"],
    "bar": ["bar", "metal", "smithing", "anvil"],
    "summon": ["summoning", "summon", "summoned", "boss summon"],
}


# ---------------------------------------------------------------------------
# Section quality boost scores
# ---------------------------------------------------------------------------

# Sections that are HIGH quality for game advice (boost these)
HIGH_QUALITY_SECTIONS = {
    "crafting recipes": 0.15,
    "used in": 0.15,
    "crafting": 0.10,
    "recipes": 0.10,
    "notes": 0.05,
    "tips": 0.03,
}

# Sections that are LOW quality (de-boost or skip)
LOW_QUALITY_SECTIONS = {
    "references": -0.20,
    "bestiary": -0.15,
    "history": -0.10,
    "trivia": -0.05,
    "gallery": -0.20,
    "see also": -0.05,
}


def expand_query(query: str) -> str:
    """
    Expand a natural language query with Terraria-specific terms.

    Maps player-class terminology, boss names, and game concepts to
    wiki-compatible terms that improve retrieval quality.

    Parameters
    ----------
    query : str
        Natural language player query.

    Returns
    -------
    str
        Expanded query string with additional terms.
    """
    query_lower = query.lower()
    expanded_terms: list[str] = []

    # Check for class/build mentions
    for cls, weapons in CLASS_TO_WEAPONS.items():
        if cls in query_lower:
            expanded_terms.extend(weapons)

    # Check for boss names → add specific terms
    for boss_keyword, terms in BOSS_TERMS.items():
        if boss_keyword in query_lower:
            expanded_terms.extend(terms)

    # Generic term expansion
    for term, expansions in TERM_EXPANSION.items():
        if term in query_lower:
            expanded_terms.extend(expansions)

    # Extract item names from query (capitalized words that are likely item names)
    # e.g. "Musket Ball" in query → add "Musket Ball"
    item_names = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', query)
    expanded_terms.extend(item_names)

    # Deduplicate while preserving order
    seen = set()
    unique_terms = []
    for term in expanded_terms:
        if term.lower() not in seen:
            seen.add(term.lower())
            unique_terms.append(term)

    if unique_terms:
        # Cap expansion to avoid diluting the embedding signal.
        # Sentence transformers average over all tokens, so adding 30+ loosely
        # related terms hurts more than it helps.
        MAX_EXPANSION_TERMS = 8
        unique_terms = unique_terms[:MAX_EXPANSION_TERMS]
        return f"{query} {' '.join(unique_terms)}"
    return query


def get_section_quality_score(section_path: str) -> float:
    """
    Return a quality boost/penalty for a section based on its name.

    Higher = better quality content for game advice.
    Applied as a score adjustment during retrieval reranking.

    Parameters
    ----------
    section_path : str
        e.g. "Terra Blade.Crafting.Used in" or "Wall of Flesh.Notes"

    Returns
    -------
    float
        Score adjustment in range [-0.2, +0.15].
    """
    section_lower = section_path.lower()

    # Check low quality first (penalties)
    for section, penalty in LOW_QUALITY_SECTIONS.items():
        if section in section_lower:
            return penalty

    # Check high quality (boosts)
    best_boost = 0.0
    for section, boost in HIGH_QUALITY_SECTIONS.items():
        if section in section_lower:
            best_boost = max(best_boost, boost)

    return best_boost


def apply_section_quality(
    results: list,
    min_quality_threshold: float = -0.1,
) -> list:
    """
    Re-score retrieval results by section quality.

    Moves high-quality sections (Crafting, Used in) up in the ranking,
    and pushes low-quality sections (References, Gallery) down.
    Results with quality below threshold are deprioritized but not removed.

    Parameters
    ----------
    results : list[RetrievalResult]
        Results from Qdrant retrieval.
    min_quality_threshold : float
        Minimum quality score. Sections below this get a heavy deprioritization.

    Returns
    -------
    list
        Re-scored and re-sorted results.
    """
    for result in results:
        quality = get_section_quality_score(result.chunk.section_path)
        # Combine relevance score with quality: weighted average
        # Prefer relevance but use quality as a tiebreaker
        adjusted = result.score + (quality * 0.5)
        result.score = max(0, adjusted)

    # Re-sort by adjusted score
    results.sort(key=lambda r: r.score, reverse=True)

    return results
