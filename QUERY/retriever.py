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

    # Qdrant 1.17+ API: query_points (replaces search)
    results = client.query_points(
        collection_name=collection_name,
        query=query_vector,
        query_filter=qdrant_filter,
        limit=top_k,
        search_params=qdrant_models.SearchParams(
            hnsw_ef=128,
            exact=False,
        ),
        with_payload=True,
        score_threshold=score_threshold,
        using="default",
    )

    retrieval_results = []
    for rank, result in enumerate(results.points, start=1):
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
