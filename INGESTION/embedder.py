"""
INGESTION/embedder.py — Embed wiki chunks using sentence-transformers.

Provides batch embedding of WikiChunks. Each chunk's content is embedded
using the shared embedding model. Embeddings are returned alongside
the chunk metadata for indexing.
"""

import logging
from typing import Iterator, Optional

from COMMON.config import EMBEDDING_BATCH_SIZE
from COMMON.embedding_model import embed_texts, get_embedding_model
from COMMON.types import WikiChunk

logger = logging.getLogger(__name__)


def embed_chunks(
    chunks: list[WikiChunk],
    batch_size: int = EMBEDDING_BATCH_SIZE,
) -> Iterator[tuple[WikiChunk, list[float]]]:
    """
    Embed a list of WikiChunks and yield (chunk, vector) pairs.

    Parameters
    ----------
    chunks : list[WikiChunk]
        Chunks to embed.
    batch_size : int
        Batch size for the embedding model.

    Yields
    ------
    tuple[WikiChunk, list[float]]
        Each chunk paired with its embedding vector.
    """
    # Ensure model is loaded
    get_embedding_model()

    texts = [chunk.content for chunk in chunks]
    embeddings = embed_texts(texts, batch_size=batch_size, normalize=True)

    for chunk, vector in zip(chunks, embeddings):
        yield chunk, vector


def embed_chunks_streaming(
    chunk_iterator: Iterator[list[WikiChunk]],
    batch_size: int = EMBEDDING_BATCH_SIZE,
) -> Iterator[tuple[WikiChunk, list[float]]]:
    """
    Stream chunks from multiple pages, embedding in batches.

    Accumulates chunks until batch_size is reached, then yields
    batched embeddings. Ensures chunks from the same page stay together
    when possible.

    Parameters
    ----------
    chunk_iterator : Iterator[list[WikiChunk]]
        Iterator yielding chunk lists (one list per page).
    batch_size : int
        Embedding batch size.

    Yields
    ------
    tuple[WikiChunk, list[float]]
        Individual (chunk, vector) pairs.
    """
    buffer: list[WikiChunk] = []

    for page_chunks in chunk_iterator:
        for chunk in page_chunks:
            buffer.append(chunk)

            if len(buffer) >= batch_size:
                # Embed the full buffer
                for result in embed_chunks(buffer, batch_size=batch_size):
                    yield result
                buffer = []

    # Flush remaining
    if buffer:
        for result in embed_chunks(buffer, batch_size=batch_size):
            yield result


def estimate_total_chunks(pages_or_count: int, avg_chunks_per_page: float = 5.0) -> int:
    """
    Rough estimate of total chunks for progress reporting.

    Parameters
    ----------
    pages_or_count : int
        Number of pages to process.
    avg_chunks_per_page : float
        Estimated average chunks per page.

    Returns
    -------
    int
        Estimated total chunks.
    """
    return int(pages_or_count * avg_chunks_per_page)
