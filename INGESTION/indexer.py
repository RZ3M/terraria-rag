"""
INGESTION/indexer.py — Write embedded chunks to Qdrant.

Handles batch upserting of WikiChunks with their vectors and metadata
into the Qdrant collection. Tracks ingestion state for resume support.
"""

import json
import logging
import uuid
from pathlib import Path
from typing import Iterator, Optional

from qdrant_client.http import models as qdrant_models

from COMMON.config import (
    COLLECTION_NAME,
    QDRANT_HOST,
    QDRANT_PORT,
    INGESTION_STATE_FILE,
    CHUNKS_DIR,
)
from COMMON.qdrant_client import ensure_collection_exists, get_qdrant_client
from COMMON.types import WikiChunk

logger = logging.getLogger(__name__)

# Batch size for Qdrant upserts
UPSERT_BATCH_SIZE = 100


def load_ingestion_state() -> dict:
    """Load the ingestion state file."""
    if INGESTION_STATE_FILE.exists():
        try:
            with open(INGESTION_STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load ingestion state: {e}")
    return {
        "version": 1,
        "total_pages_processed": 0,
        "total_chunks_indexed": 0,
        "pages": {},  # page_id -> {title, chunks_indexed, last_updated}
    }


def save_ingestion_state(state: dict) -> None:
    """Persist ingestion state to disk."""
    INGESTION_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(INGESTION_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def save_chunks_to_disk(chunks: list[WikiChunk]) -> Path:
    """
    Save chunks to a JSONL file for debugging/resume.

    Returns the path to the saved file.
    """
    CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = chunks[0].wiki_title.replace("/", "_").replace("\\", "_").replace(":", "_")[:150]
    chunk_file = CHUNKS_DIR / f"{safe_name}.jsonl"

    with open(chunk_file, "w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk.to_payload(), ensure_ascii=False) + "\n")

    return chunk_file


def index_chunks(
    chunks: list[WikiChunk],
    vectors: list[list[float]],
    batch_size: int = UPSERT_BATCH_SIZE,
    collection_name: str = COLLECTION_NAME,
) -> int:
    """
    Upsert chunks and their vectors into Qdrant.

    Parameters
    ----------
    chunks : list[WikiChunk]
        Chunks to index.
    vectors : list[list[float]]
        Corresponding embedding vectors.
    batch_size : int
        Points per upsert batch.
    collection_name : str
        Qdrant collection name.

    Returns
    -------
    int
        Number of chunks indexed.
    """
    if len(chunks) != len(vectors):
        raise ValueError(f"Chunk count ({len(chunks)}) != vector count ({len(vectors)})")

    client = ensure_collection_exists()
    total_indexed = 0

    for batch_start in range(0, len(chunks), batch_size):
        batch_end = batch_start + batch_size
        batch_chunks = chunks[batch_start:batch_end]
        batch_vectors = vectors[batch_start:batch_end]

        points = []
        for chunk, vector in zip(batch_chunks, batch_vectors):
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{chunk.wiki_url}#{chunk.chunk_index}"))

            points.append(qdrant_models.PointStruct(
                id=point_id,
                vector={"default": vector},  # named vector for Qdrant 1.7+
                payload=chunk.to_payload(),
            ))

        client.upsert(
            collection_name=collection_name,
            points=points,
        )

        total_indexed += len(points)
        logger.debug(f"Indexed {len(points)} chunks (total: {total_indexed})")

    return total_indexed


def index_chunks_streaming(
    chunk_vector_pairs: Iterator[tuple[WikiChunk, list[float]]],
    batch_size: int = UPSERT_BATCH_SIZE,
) -> tuple[int, int]:
    """
    Stream-index chunk/vector pairs in batches.

    Accumulates pairs into batches, indexes them, and tracks progress.

    Parameters
    ----------
    chunk_vector_pairs : Iterator[tuple[WikiChunk, list[float]]]
        Streaming tuples of (chunk, vector).
    batch_size : int
        Indexing batch size.

    Returns
    -------
    tuple[int, int]
        (total_pages_indexed, total_chunks_indexed)
    """
    client = ensure_collection_exists()

    batch_chunks: list[WikiChunk] = []
    batch_vectors: list[list[float]] = []
    total_chunks = 0
    total_pages = 0
    last_page_title = ""

    for chunk, vector in chunk_vector_pairs:
        batch_chunks.append(chunk)
        batch_vectors.append(vector)

        if chunk.wiki_title != last_page_title:
            last_page_title = chunk.wiki_title
            total_pages += 1

        if len(batch_chunks) >= batch_size:
            # Group by page for batching (Qdrant upsert doesn't require grouping,
            # but we track page count separately)
            index_chunks(batch_chunks, batch_vectors, batch_size=batch_size)
            total_chunks += len(batch_chunks)
            logger.info(f"Progress: {total_chunks} chunks indexed ({total_pages} pages)")
            batch_chunks = []
            batch_vectors = []

    # Flush remaining
    if batch_chunks:
        index_chunks(batch_chunks, batch_vectors, batch_size=batch_size)
        total_chunks += len(batch_chunks)
        logger.info(f"Final: {total_chunks} chunks indexed ({total_pages} pages)")

    return total_pages, total_chunks


def delete_page_from_index(page_url: str) -> None:
    """
    Delete all chunks for a given page URL from the index.
    Useful for re-ingesting updated pages.
    """
    client = get_qdrant_client()
    # Qdrant scroll with filter to find points
    results, _ = client.scroll(
        collection_name=COLLECTION_NAME,
        scroll_filter={
            "must": [
                {
                    "key": "wiki_url",
                    "match": {"value": page_url},
                }
            ]
        },
        limit=1000,
    )

    if results:
        ids_to_delete = [r.id for r in results]
        client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=qdrant_models.PointIdsList(
                points=ids_to_delete,
            ),
        )
        logger.info(f"Deleted {len(ids_to_delete)} chunks for URL: {page_url}")
