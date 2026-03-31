"""
TESTS/eval_queries.py — Golden test set for retrieval evaluation.

Each test case defines a query and what we expect to find in the top-5
retrieved chunks. Used by eval_retrieval.py to measure recall and quality.
"""

from dataclasses import dataclass, field


@dataclass
class EvalCase:
    """A single evaluation test case."""
    query: str
    # Wiki page titles that should appear in top-5 results
    expected_titles: list[str]
    # Section path substrings (any of these is a hit)
    expected_sections: list[str] = field(default_factory=list)
    # Substrings that should appear in retrieved chunk content
    expected_content_contains: list[str] = field(default_factory=list)
    # Human-readable category for grouping results
    category: str = "general"
    # Notes on why this case is interesting/tricky
    notes: str = ""


# ---------------------------------------------------------------------------
# Evaluation cases
# ---------------------------------------------------------------------------

EVAL_CASES: list[EvalCase] = [

    # ---- Item lookups -------------------------------------------------------

    EvalCase(
        query="What is the Terra Blade?",
        expected_titles=["Terra Blade"],
        expected_sections=["Terra Blade"],
        expected_content_contains=["sword", "True"],
        category="item_lookup",
        notes="Flagship late-game sword; should be top result",
    ),

    EvalCase(
        query="What is the Zenith sword?",
        expected_titles=["Zenith"],
        expected_sections=["Zenith"],
        expected_content_contains=["sword", "Moon Lord"],
        category="item_lookup",
        notes="End-game weapon; direct title lookup",
    ),

    EvalCase(
        query="Tell me about the Clockwork Assault Rifle",
        expected_titles=["Clockwork Assault Rifle"],
        expected_sections=["Clockwork Assault Rifle"],
        expected_content_contains=["Wall of Flesh"],
        category="item_lookup",
        notes="Multi-word item name; dropped from Wall of Flesh",
    ),

    EvalCase(
        query="What does the Ankh Shield do?",
        expected_titles=["Ankh Shield"],
        expected_sections=["Ankh Shield"],
        expected_content_contains=["accessory", "immunity"],
        category="item_lookup",
        notes="Accessory with immunity effects",
    ),

    EvalCase(
        query="What is Night's Edge?",
        expected_titles=["Night's Edge"],
        expected_sections=["Night's Edge"],
        expected_content_contains=["sword", "craft"],
        category="item_lookup",
        notes="Apostrophe in item name — tests name extraction",
    ),

    # ---- Crafting recipes ---------------------------------------------------

    EvalCase(
        query="How do I craft Night's Edge?",
        expected_titles=["Night's Edge"],
        expected_sections=["Crafting", "crafting"],
        expected_content_contains=["Blade of Grass", "Muramasa"],
        category="crafting",
        notes="Requires 4 swords; crafting info should be prominent",
    ),

    EvalCase(
        query="What are the ingredients to make a Terra Blade?",
        expected_titles=["Terra Blade"],
        expected_sections=["Crafting", "crafting"],
        expected_content_contains=["True Night's Edge", "True Excalibur"],
        category="crafting",
        notes="Recipe chain; tests crafting section retrieval",
    ),

    EvalCase(
        query="How do I craft an Adamantite Sword?",
        expected_titles=["Adamantite Sword"],
        expected_sections=["Crafting", "crafting"],
        expected_content_contains=["Adamantite Bar", "Mythril Anvil"],
        category="crafting",
        notes="Hardmode sword with clear recipe",
    ),

    EvalCase(
        query="What materials do I need for a Molten Pickaxe?",
        expected_titles=["Molten Pickaxe"],
        expected_sections=["Crafting", "crafting"],
        expected_content_contains=["Hellstone Bar"],
        category="crafting",
        notes="Pre-hardmode best pickaxe",
    ),

    # ---- Boss strategy ------------------------------------------------------

    EvalCase(
        query="How do I beat the Wall of Flesh?",
        expected_titles=["Wall of Flesh"],
        expected_sections=["Wall of Flesh", "Tips", "Notes"],
        expected_content_contains=["Underworld", "guide"],
        category="boss_strategy",
        notes="First hardmode boss trigger; key fight",
    ),

    EvalCase(
        query="What is the best ranger setup for Wall of Flesh?",
        expected_titles=["Wall of Flesh"],
        expected_sections=[],
        expected_content_contains=[],
        category="boss_strategy",
        notes="Class + boss combo query; tests query expansion",
    ),

    EvalCase(
        query="How do I summon Skeletron?",
        expected_titles=["Skeletron"],
        expected_sections=["Skeletron", "Summoning"],
        expected_content_contains=["Old Man", "Dungeon"],
        category="boss_strategy",
        notes="NPC-triggered boss",
    ),

    EvalCase(
        query="Tips for fighting the Moon Lord",
        expected_titles=["Moon Lord"],
        expected_sections=["Moon Lord", "Tips", "Notes"],
        expected_content_contains=["Celestial"],
        category="boss_strategy",
        notes="Final boss; tips section retrieval",
    ),

    # ---- Stats / item properties --------------------------------------------

    EvalCase(
        query="What damage does the Adamantite Sword deal?",
        expected_titles=["Adamantite Sword"],
        expected_sections=[],
        expected_content_contains=["damage"],
        category="stats",
        notes="Stat lookup; requires infobox data to be in chunk",
    ),

    EvalCase(
        query="How much defense does Titanium armor give?",
        expected_titles=["Titanium armor"],
        expected_sections=[],
        expected_content_contains=["defense"],
        category="stats",
        notes="Armor defense lookup",
    ),

    # ---- Category / progression queries -------------------------------------

    EvalCase(
        query="What are the best pre-hardmode bows?",
        expected_titles=["Hellwing Bow", "Bee's Knees", "Marrow"],
        expected_sections=[],
        expected_content_contains=["bow"],
        category="progression",
        notes="Category query; should return multiple bow pages",
    ),

    EvalCase(
        query="What ores are available in hardmode?",
        expected_titles=["Cobalt Ore", "Mythril Ore", "Adamantite Ore"],
        expected_sections=[],
        expected_content_contains=["hardmode"],
        category="progression",
        notes="Hardmode ore unlocks; multiple pages",
    ),

    EvalCase(
        query="What is the first boss I should fight in Terraria?",
        expected_titles=["King Slime", "Eye of Cthulhu", "Slime"],
        expected_sections=[],
        expected_content_contains=[],
        category="progression",
        notes="Progression question; first bosses",
    ),

    # ---- Biome / location queries -------------------------------------------

    EvalCase(
        query="What enemies spawn in the Crimson biome?",
        expected_titles=["Crimson", "The Crimson"],
        expected_sections=["Crimson", "Enemies"],
        expected_content_contains=["enemy", "Face Monster"],
        category="biome",
        notes="Biome enemy list",
    ),

    EvalCase(
        query="How do I get to the Underworld?",
        expected_titles=["The Underworld", "Underworld"],
        expected_sections=[],
        expected_content_contains=["Hell", "lava"],
        category="biome",
        notes="Biome location",
    ),

    # ---- NPC queries --------------------------------------------------------

    EvalCase(
        query="What does the Arms Dealer sell?",
        expected_titles=["Arms Dealer"],
        expected_sections=["Arms Dealer"],
        expected_content_contains=["Musket Ball", "sell"],
        category="npc",
        notes="Merchant NPC inventory",
    ),

    EvalCase(
        query="How do I get the Goblin Tinkerer to move in?",
        expected_titles=["Goblin Tinkerer"],
        expected_sections=[],
        expected_content_contains=["Goblin Army", "rescue"],
        category="npc",
        notes="NPC unlock condition",
    ),
]


def get_cases_by_category(category: str) -> list[EvalCase]:
    """Filter eval cases by category."""
    return [c for c in EVAL_CASES if c.category == category]


def get_all_categories() -> list[str]:
    """Return all unique categories in the eval set."""
    return sorted(set(c.category for c in EVAL_CASES))


if __name__ == "__main__":
    print(f"Total eval cases: {len(EVAL_CASES)}")
    for cat in get_all_categories():
        cases = get_cases_by_category(cat)
        print(f"  {cat}: {len(cases)} cases")
