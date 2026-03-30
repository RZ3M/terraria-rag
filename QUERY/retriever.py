"""
QUERY/retriever.py — Qdrant retrieval with metadata filtering.

Retrieves the most relevant wiki chunks for a given query,
optionally filtered by game state metadata.
"""

import logging
from typing import Optional

from qdrant_client.http import models as qdrant_models

from COMMON.config import (
    COLLECTION_NAME,
    TOP_K,
    RETRIEVAL_SCORE_THRESHOLD,
    EMBEDDING_DIM,
)
from COMMON.embedding_model import embed_single
from COMMON.qdrant_client import get_qdrant_client, collection_exists
from COMMON.types import RetrievalResult, WikiChunk

logger = logging.getLogger(__name__)


def build_qdrant_filter(
    category: Optional[str] = None,
    subcategory: Optional[str] = None,
    game_mode: Optional[str] = None,
    obtain_method: Optional[str] = None,
) -> Optional[qdrant_models.Filter]:
    """
    Build a Qdrant filter from game state parameters.

    Parameters
    ----------
    category : str, optional
        e.g. "Weapons", "Armor", "Biomes"
    subcategory : str, optional
        e.g. "Melee", "Head", "Ranged"
    game_mode : str, optional
        "Pre-Hardmode", "Hardmode", or "Post-Moon Lord"
    obtain_method : str, optional
        "Crafting", "Drop", "Purchase", "Fishing"

    Returns
    -------
    qdrant_models.Filter or None
        Qdrant filter object, or None for no filtering.
    """
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
        # game_mode is a list in the payload, so we use MatchAny
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


def retrieve(
    query_text: str,
    top_k: int = TOP_K,
    score_threshold: float = RETRIEVAL_SCORE_THRESHOLD,
    category: Optional[str] = None,
    subcategory: Optional[str] = None,
    game_mode: Optional[str] = None,
    obtain_method: Optional[str] = None,
    collection_name: str = COLLECTION_NAME,
) -> list[RetrievalResult]:
    """
    Retrieve the most relevant chunks for a query from Qdrant.

    Parameters
    ----------
    query_text : str
        Natural language query.
    top_k : int
        Number of vectors to retrieve from Qdrant (pre-filter).
    score_threshold : float
        Minimum cosine similarity to include a result.
    category, subcategory, game_mode, obtain_method : optional
        Metadata filters for game-state-aware retrieval.
    collection_name : str
        Qdrant collection name.

    Returns
    -------
    list[RetrievalResult]
        Sorted by relevance (highest score first).
    """
    if not collection_exists():
        logger.error("Qdrant collection does not exist. Run ingestion first.")
        return []

    client = get_qdrant_client()

    # Embed the query
    query_vector = embed_single(query_text)

    # Build filter
    qdrant_filter = build_qdrant_filter(
        category=category,
        subcategory=subcategory,
        game_mode=game_mode,
        obtain_method=obtain_method,
    )

    # Search Qdrant
    search_params = qdrant_models.SearchParams(
        hnsw_ef=128,  # runtime search depth
        exact=False,
    )

    results = client.search(
        collection_name=collection_name,
        query_vector=query_vector,
        query_filter=qdrant_filter,
        limit=top_k,
        search_params=search_params,
        with_payload=True,
        score_threshold=score_threshold,
    )

    retrieval_results = []
    for rank, result in enumerate(results, start=1):
        try:
            chunk = WikiChunk.from_payload(result.payload)
            retrieval_results.append(RetrievalResult(
                chunk=chunk,
                score=result.score,
                rank=rank,
            ))
        except Exception as e:
            logger.warning(f"Failed to reconstruct chunk from payload: {e}")
            continue

    logger.debug(
        f"Retrieved {len(retrieval_results)} chunks for query: "
        f"'{query_text[:50]}...' (threshold={score_threshold})"
    )

    return retrieval_results


def retrieve_raw(
    query_vector: list[float],
    top_k: int = TOP_K,
    score_threshold: float = RETRIEVAL_SCORE_THRESHOLD,
    category: Optional[str] = None,
    game_mode: Optional[str] = None,
    collection_name: str = COLLECTION_NAME,
) -> list[qdrant_models.ScoredPoint]:
    """
    Low-level Qdrant search returning raw scored points.
    Use this if you need direct access to Qdrant payloads.
    """
    if not collection_exists():
        return []

    client = get_qdrant_client()
    qdrant_filter = build_qdrant_filter(category=category, game_mode=game_mode)

    return client.search(
        collection_name=collection_name,
        query_vector=query_vector,
        query_filter=qdrant_filter,
        limit=top_k,
        score_threshold=score_threshold,
        with_payload=True,
    )
