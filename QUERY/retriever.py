"""
QUERY/retriever.py — Qdrant retrieval with metadata filtering.

Retrieves the most relevant wiki chunks for a given query,
optionally filtered by game state metadata.

Strategy:
1. Extract capitalized Terraria item names from the expanded query
2. Query each item directly (no query expansion) — PRIMARY signal
3. Run an expanded semantic query — BACKUP for general context
4. Section quality re-ranking — Crafting/Used in boosted, References penalized
"""

import logging
import re
from typing import Optional

from qdrant_client.http import models as qdrant_models

from COMMON.config import (
    COLLECTION_NAME,
    TOP_K,
    RETRIEVAL_SCORE_THRESHOLD,
    RERANKER_MODEL,
    RERANK_TOP_N,
)
from COMMON.embedding_model import embed_single
from COMMON.qdrant_client import get_qdrant_client, collection_exists
from COMMON.types import RetrievalResult, WikiChunk
from QUERY.query_expander import expand_query, apply_section_quality

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cross-encoder reranker (lazy-loaded singleton)
# ---------------------------------------------------------------------------

_reranker = None


def _get_reranker():
    """Lazy-load the cross-encoder reranker on first use."""
    global _reranker
    if _reranker is None:
        try:
            from sentence_transformers import CrossEncoder
            _reranker = CrossEncoder(RERANKER_MODEL)
            logger.info(f"Reranker loaded: {RERANKER_MODEL}")
        except Exception as e:
            logger.warning(f"Reranker unavailable ({e}); skipping reranking.")
            _reranker = False  # sentinel: don't try again
    return _reranker if _reranker is not False else None


def _rerank(query: str, results: list[RetrievalResult], top_n: int) -> list[RetrievalResult]:
    """
    Re-score results with a cross-encoder and return top_n.

    Cross-encoders score (query, document) pairs directly, giving much
    better precision than bi-encoder cosine similarity alone.
    """
    reranker = _get_reranker()
    if reranker is None or not results:
        return results[:top_n]

    pairs = [(query, r.chunk.content) for r in results]
    try:
        scores = reranker.predict(pairs)
        for r, score in zip(results, scores):
            r.score = float(score)
        results.sort(key=lambda r: r.score, reverse=True)
    except Exception as e:
        logger.warning(f"Reranking failed: {e}; using original order.")

    return results[:top_n]


# Common English words to skip when extracting item names from queries.
# Must be lowercase — comparison uses w.lower() on line ~233.
SKIP_WORDS = {
    "the", "best", "good", "great", "how", "what", "where",
    "when", "which", "item", "setup", "build", "use", "using",
    "wall", "flesh", "world", "game", "boss", "first", "like",
    "help", "need", "want", "for", "and", "all", "most", "same",
    "guide", "hardmode", "desktop", "console", "mobile", "versions",
    "every", "with", "from", "this", "that", "these", "those",
    "your", "just", "very", "more", "only", "also", "will",
    "into", "make", "than", "then", "some", "over", "such",
    "day", "night", "one", "two", "new", "old", "big", "small",
    "get", "have", "does", "tell", "tips", "about", "beat", "fight",
    "should", "available", "give", "deal", "spawn", "move",
}


def build_qdrant_filter(
    category: Optional[str] = None,
    subcategory: Optional[str] = None,
    game_mode: Optional[str] = None,
    obtain_method: Optional[str] = None,
) -> Optional[qdrant_models.Filter]:
    """Build a Qdrant filter from game state parameters."""
    conditions = []

    if category:
        conditions.append(
            qdrant_models.FieldCondition(
                key="category",
                match=qdrant_models.MatchValue(value=category),
            )
        )
    if subcategory:
        conditions.append(
            qdrant_models.FieldCondition(
                key="subcategory",
                match=qdrant_models.MatchValue(value=subcategory),
            )
        )
    if game_mode:
        conditions.append(
            qdrant_models.FieldCondition(
                key="game_mode",
                match=qdrant_models.MatchAny(any=[game_mode]),
            )
        )
    if obtain_method:
        conditions.append(
            qdrant_models.FieldCondition(
                key="obtain_method",
                match=qdrant_models.MatchValue(value=obtain_method),
            )
        )

    if not conditions:
        return None

    return qdrant_models.Filter(must=conditions)


def _query_items_direct(
    client,
    collection_name: str,
    item_names: list[str],
    qdrant_filter,
    limit_per_item: int,
) -> list[RetrievalResult]:
    """
    Query each item name directly and return top results.

    Batches embeddings for efficiency — loads model once, encodes all items.
    Ensures specific items are found regardless of query phrasing.
    """
    if not item_names:
        return []

    results: list[RetrievalResult] = []
    for item_name in item_names:
        vector = embed_single(item_name)
        qdrant_results = client.query_points(
            collection_name=collection_name,
            query=vector,
            query_filter=qdrant_filter,
            limit=limit_per_item,
            search_params=qdrant_models.SearchParams(hnsw_ef=128, exact=False),
            with_payload=True,
            score_threshold=0.3,
            using="default",
        )
        for rank, result in enumerate(qdrant_results.points, start=1):
            try:
                chunk = WikiChunk.from_payload(result.payload)
                results.append(RetrievalResult(
                    chunk=chunk,
                    score=result.score,
                    rank=rank,
                ))
            except Exception:
                continue

    return results


def _extract_item_names(expanded_query: str) -> list[str]:
    """
    Extract capitalized Terraria item names from the expanded query.

    Strategy:
    1. Normalize query: lowercase, strip apostrophes for matching
    2. Match known multi-word item names (2-3 words) — consecutive word matching
    3. Add remaining individual capitalized words not in skip list

    Example:
        "... Musket Ball Ichor Shroomite Clockwork Assault Rifle ..."
        → ["Musket Ball", "Ichor", "Shroomite", "Clockwork Assault Rifle"]
    """
    # Split on non-letter to get raw words
    words_raw = re.split(r'[^A-Za-z\'\-]+', expanded_query)
    words = [w for w in words_raw if w]

    # Normalize words for matching (lowercase, strip apostrophes)
    words_norm = [w.lower().replace("'", "").replace("-", "") for w in words]

    # Known multi-word items (normalize for matching)
    KNOWN_ITEMS_3 = {
        ("clockwork", "assault", "rifle"): "Clockwork Assault Rifle",
        ("endless", "musket", "pouch"): "Endless Musket Pouch",
        ("astral", "hamaxe"): "Astral Hamaxe",
        ("true", "nights", "edge"): "True Night's Edge",
        ("true", "excalibur"): "True Excalibur",
        ("terra", "blade"): "Terra Blade",
        ("meowmere", "ii"): "Meowmere II",
        ("star", "wrath", "ii"): "Star Wrath II",
    }

    KNOWN_ITEMS_2 = {
        ("nights", "edge"): "Night's Edge",
        ("dark", "lance"): "Dark Lance",
        ("storm", "spear"): "Storm Spear",
        ("frost", "brand"): "Frost Brand",
        ("death", "sickle"): "Death Sickle",
        ("light", "disc"): "Light Disc",
        ("molten", "fury"): "Molten Fury",
        ("demon", "conch"): "Demon Conch",
        ("musket", "ball"): "Musket Ball",
        ("ichor", "bullet"): "Ichor Bullet",
        ("endless", "quiver"): "Endless Quiver",
        ("crystal", "dart"): "Crystal Dart",
        ("stinger", "dart"): "Stinger Dart",
        ("cursed", "dart"): "Cursed Dart",
        ("ichor", "dart"): "Ichor Dart",
        ("holy", "arrow"): "Holy Arrow",
        ("unholy", "arrow"): "Unholy Arrow",
        ("venom", "arrow"): "Venom Arrow",
        ("jesters", "arrow"): "Jester's Arrow",
        ("shroomite", "bar"): "Shroomite Bar",
        ("blade", "grass"): "Blade of Grass",
        ("titanium", "trident"): "Titanium Trident",
        ("adamantite", "glaive"): "Adamantite Glaive",
        ("cobalt", "naginata"): "Cobalt Naginata",
        ("palladium", "pike"): "Palladium Pike",
        ("orichalcum", "halberd"): "Orichalcum Halberd",
        ("orichalcum", "anvil"): "Orichalcum Anvil",
        ("mythril", "anvil"): "Mythril Anvil",
        ("blood", "butcherer"): "Blood Butcherer",
        ("flaming", "arrow"): "Flaming Arrow",
        ("bones", "thrower"): "Bone Thrower",
    }

    # Weapons by category (useful for direct querying).
    # Keys must be plain strings — comparison uses w_low (a string).
    WEAPON_CATS = {
        "ranged": "Ranged", "guns": "Guns", "bow": "Bow",
        "rifle": "Rifle", "shotgun": "Shotgun", "pistol": "Pistol",
        "bullet": "Bullet", "arrow": "Arrow", "dart": "Dart",
        "melee": "Melee", "sword": "Sword", "magic": "Magic",
        "staff": "Staff", "summon": "Summon", "minion": "Minion",
        "spear": "Spear", "flail": "Flail", "boomerang": "Boomerang",
        "thrown": "Thrown",
    }

    extracted: list[str] = []
    used_indices: set[int] = set()

    # Match 3-word items first
    for i in range(len(words_norm) - 2):
        key3 = (words_norm[i], words_norm[i+1], words_norm[i+2])
        if key3 in KNOWN_ITEMS_3:
            extracted.append(KNOWN_ITEMS_3[key3])
            used_indices.update([i, i+1, i+2])

    # Match 2-word items
    for i in range(len(words_norm) - 1):
        if i in used_indices:
            continue
        key2 = (words_norm[i], words_norm[i+1])
        if key2 in KNOWN_ITEMS_2:
            extracted.append(KNOWN_ITEMS_2[key2])
            used_indices.update([i, i+1])

    # Add remaining individual words (weapon categories + item names)
    for i, w in enumerate(words_raw):
        if i in used_indices:
            continue
        w_low = w.lower().replace("'", "")
        if w_low in SKIP_WORDS:
            continue
        if len(w) < 2:
            continue
        # Title-case the original word (preserving apostrophe)
        normalized = w.title().replace("'", "'")
        # Skip if it's a weapon category word
        if w_low in WEAPON_CATS:
            extracted.append(WEAPON_CATS[w_low])
            continue
        # Add as potential item
        extracted.append(normalized)

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for item in extracted:
        if item.lower() not in seen:
            seen.add(item.lower())
            unique.append(item)

    return unique


def retrieve(
    query_text: str,
    top_k: int = TOP_K,
    score_threshold: float = RETRIEVAL_SCORE_THRESHOLD,
    category: Optional[str] = None,
    subcategory: Optional[str] = None,
    game_mode: Optional[str] = None,
    obtain_method: Optional[str] = None,
    collection_name: str = COLLECTION_NAME,
    expand_query_flag: bool = True,
) -> list[RetrievalResult]:
    """
    Retrieve the most relevant chunks for a query from Qdrant.
    """
    if not collection_exists():
        logger.error("Qdrant collection does not exist. Run ingestion first.")
        return []

    client = get_qdrant_client()

    qdrant_filter = build_qdrant_filter(
        category=category,
        subcategory=subcategory,
        game_mode=game_mode,
        obtain_method=obtain_method,
    )

    results: list[RetrievalResult] = []

    # Compute expansion once — use original query for item extraction (expanded
    # query has too many noise terms), use expanded for the semantic embedding.
    expanded = expand_query(query_text) if expand_query_flag else query_text

    # ---- Strategy 1: Direct item name queries ----
    if expand_query_flag:
        # Extract items from the ORIGINAL query (not expanded — expansion adds
        # generic category words like "guns", "rifle" that pollute item search)
        item_names = _extract_item_names(query_text)

        logger.debug(f"Extracted item names: {item_names}")

        if item_names:
            item_results = _query_items_direct(
                client, collection_name, item_names, qdrant_filter,
                limit_per_item=3,
            )
            results.extend(item_results)

    # ---- Strategy 2: Expanded semantic query (top up) ----
    query_vector = embed_single(expanded)
    sem_results = client.query_points(
        collection_name=collection_name,
        query=query_vector,
        query_filter=qdrant_filter,
        limit=top_k * 2,
        search_params=qdrant_models.SearchParams(hnsw_ef=128, exact=False),
        with_payload=True,
        score_threshold=score_threshold,
        using="default",
    )
    for rank, result in enumerate(sem_results.points, start=1):
        try:
            chunk = WikiChunk.from_payload(result.payload)
            results.append(RetrievalResult(
                chunk=chunk,
                score=result.score,
                rank=rank,
            ))
        except Exception:
            continue

    # ---- Deduplicate by (wiki_title, section_path) ----
    # Keep the highest-scoring result for each unique chunk
    seen: dict[str, RetrievalResult] = {}
    for r in results:
        key = f"{r.chunk.wiki_title}::{r.chunk.section_path}"
        if key not in seen or r.score > seen[key].score:
            seen[key] = r

    results = list(seen.values())

    # ---- Sort by bi-encoder score before cross-encoder reranking ----
    results.sort(key=lambda r: r.score, reverse=True)

    # ---- Cross-encoder reranking (precise query-document scoring) ----
    # Rerank the top candidates; this fixes cases where bi-encoder similarity
    # is misled by surface-level word overlap.
    results = _rerank(query_text, results, top_n=top_k)

    # ---- Section quality boost (post-rerank, as a final tie-breaker) ----
    # Applied after cross-encoder so it only breaks ties, not overrides.
    results = apply_section_quality(results)

    logger.debug(
        f"Retrieved {len(results)} chunks for query: "
        f"'{query_text[:50]}...' (threshold={score_threshold})"
    )

    return results
