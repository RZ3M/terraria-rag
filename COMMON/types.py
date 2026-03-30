"""
COMMON/types.py — Shared dataclasses and types for the Terraria RAG system.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class WikiChunk:
    """
    A single chunk extracted from a wiki page.

    Attributes
    ----------
    wiki_title : str
        Original page title (e.g. "Night's Edge")
    wiki_url : str
        Canonical URL to the page
    section_path : str
        Dot-joined path of headings leading to this chunk
        (e.g. "Weapons.Melee Swords" or "Bosses.Wall of Flesh")
    chunk_index : int
        Position of this chunk within the page (0-indexed)
    content : str
        Text content of the chunk (HTML-stripped)
    raw_html : str
        Original HTML of the chunk (for tables/infoboxes)
    category : str
        Top-level wiki category (e.g. "Weapons")
    subcategory : str
        More specific subcategory (e.g. "Melee Swords")
    game_mode : list[str]
        Applicable game modes (e.g. ["Pre-Hardmode"] or ["Hardmode", "Post-Moon Lord"])
    obtain_method : str
        How items are obtained: "Crafting", "Drop", "Purchase", "Fishing", etc.
    tokens_estimate : int
        Rough token count for the content
    """
    wiki_title: str
    wiki_url: str
    section_path: str
    chunk_index: int
    content: str
    raw_html: str = ""
    category: str = ""
    subcategory: str = ""
    game_mode: list[str] = field(default_factory=list)
    obtain_method: str = ""
    tokens_estimate: int = 0

    def __post_init__(self):
        # Rough token estimate: ~4 chars per token for English
        if self.tokens_estimate == 0:
            self.tokens_estimate = len(self.content) // 4

    def to_payload(self) -> dict:
        """Convert to Qdrant payload dict."""
        return {
            "wiki_title": self.wiki_title,
            "wiki_url": self.wiki_url,
            "section_path": self.section_path,
            "chunk_index": self.chunk_index,
            "content": self.content,
            "raw_html": self.raw_html,
            "category": self.category,
            "subcategory": self.subcategory,
            "game_mode": self.game_mode,
            "obtain_method": self.obtain_method,
            "tokens_estimate": self.tokens_estimate,
        }

    @classmethod
    def from_payload(cls, payload: dict, vector: Optional[list[float]] = None):
        """Reconstruct from Qdrant payload."""
        return cls(
            wiki_title=payload["wiki_title"],
            wiki_url=payload["wiki_url"],
            section_path=payload["section_path"],
            chunk_index=payload["chunk_index"],
            content=payload["content"],
            raw_html=payload.get("raw_html", ""),
            category=payload.get("category", ""),
            subcategory=payload.get("subcategory", ""),
            game_mode=payload.get("game_mode", []),
            obtain_method=payload.get("obtain_method", ""),
            tokens_estimate=payload.get("tokens_estimate", 0),
        )


@dataclass
class WikiPage:
    """
    A raw wiki page fetched from the MediaWiki API.
    """
    page_id: int
    title: str
    url: str
    content: str  # wikitext or HTML
    is_redirect: bool = False
    length: int = 0

    @property
    def exists(self) -> bool:
        return self.content is not None and len(self.content) > 0


@dataclass
class RetrievalResult:
    """
    A single retrieval result from Qdrant.
    """
    chunk: WikiChunk
    score: float
    rank: int

    def __str__(self) -> str:
        return (
            f"[Rank {self.rank} | Score {self.score:.4f}] "
            f"{self.chunk.wiki_title} :: {self.chunk.section_path}\n"
            f"  {self.chunk.content[:200]}..."
        )


@dataclass
class QueryResult:
    """
    The result of a full query pipeline.
    """
    query_text: str
    retrieved_chunks: list[RetrievalResult]
    game_state: str
    llm_response: str
    provider: str  # "minimax" or "openrouter"
    latency_ms: float = 0.0

    @property
    def top_chunk(self) -> Optional[RetrievalResult]:
        return self.retrieved_chunks[0] if self.retrieved_chunks else None

    def summary(self) -> str:
        chunk_summaries = "\n".join(str(r) for r in self.retrieved_chunks)
        return (
            f"Query: {self.query_text}\n"
            f"Game State: {self.game_state}\n"
            f"Provider: {self.provider}\n"
            f"Latency: {self.latency_ms:.0f}ms\n"
            f"Retrieved {len(self.retrieved_chunks)} chunks:\n{chunk_summaries}\n"
            f"\nLLM Response:\n{self.llm_response}"
        )


@dataclass
class GameState:
    """
    Represents the player's current game state for filtering.
    Used to scope RAG retrieval to relevant wiki content.
    """
    is_hardmode: bool = False
    moon_lord_defeated: bool = False
    current_biomes: list[str] = field(default_factory=list)
    bosses_defeated: list[str] = field(default_factory=list)
    armor_tier: str = "Iron"  # Iron, Silver, Gold, Platinum, Hallowed, etc.
    weapons_tier: str = "Iron"
    current_npc: str = "Guide"  # which NPC is giving hints

    def to_filter_dict(self) -> dict:
        """Convert to Qdrant filter format."""
        filters = {}
        if self.is_hardmode:
            filters["game_mode"] = {"$or": [{"$eq": "Hardmode"}, {"$eq": "Post-Moon Lord"}]}
        else:
            filters["game_mode"] = {"$eq": "Pre-Hardmode"}
        return filters

    def to_prompt_string(self) -> str:
        """Human-readable string for the prompt."""
        lines = [
            f"Hardmode: {'Yes' if self.is_hardmode else 'No'}",
            f"Moon Lord defeated: {'Yes' if self.moon_lord_defeated else 'No'}",
            f"Current biomes: {', '.join(self.current_biomes) or 'Unknown'}",
            f"Bosses defeated: {', '.join(self.bosses_defeated) or 'None'}",
            f"Armor tier: {self.armor_tier}",
            f"Weapons tier: {self.weapons_tier}",
            f"Companion NPC: {self.current_npc}",
        ]
        return "\n".join(lines)
