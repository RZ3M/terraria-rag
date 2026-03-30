"""
COMMON/embedding_model.py — Shared sentence-transformer embedding model.

Provides a singleton embedding model loaded once and reused across
the ingestion and query pipelines.
"""

import logging
from functools import lru_cache
from typing import Union

from sentence_transformers import SentenceTransformer

from COMMON.config import EMBEDDING_MODEL_NAME, EMBEDDING_DIM, EMBEDDING_BATCH_SIZE

logger = logging.getLogger(__name__)

# Global model instance (loaded once via lru_cache)
_model: SentenceTransformer | None = None


@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    """
    Load and return the shared sentence-transformer model.

    Downloads the model on first call and caches it.
    Uses all-MiniLM-L6-v2 by default (384d, fast and good quality).
    """
    global _model
    if _model is None:
        logger.info(f"Loading embedding model: {EMBEDDING_MODEL_NAME}")
        _model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        logger.info(f"Embedding model loaded. Output dim: {_model.get_sentence_embedding_dimension()}")
    return _model


def embed_texts(
    texts: Union[list[str], str],
    batch_size: int = EMBEDDING_BATCH_SIZE,
    normalize: bool = True,
) -> list[list[float]]:
    """
    Embed a list of texts (or a single text) using the shared model.

    Parameters
    ----------
    texts : list[str] or str
        Text(s) to embed.
    batch_size : int
        Batch size for GPU/CPU encoding.
    normalize : bool
        L2-normalize the output vectors (recommended for cosine similarity).

    Returns
    -------
    list[list[float]]
        List of embedding vectors, each of length EMBEDDING_DIM.
    """
    model = get_embedding_model()

    if isinstance(texts, str):
        texts = [texts]

    logger.debug(f"Embedding {len(texts)} texts with model {EMBEDDING_MODEL_NAME}")
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=len(texts) > 100,
        normalize_embeddings=normalize,
        convert_to_numpy=True,
    )

    return [row.tolist() for row in embeddings]


def embed_single(text: str) -> list[float]:
    """
    Embed a single text and return the vector.

    Returns
    -------
    list[float]
        Embedding vector of length EMBEDDING_DIM.
    """
    return embed_texts([text])[0]


def validate_embedding_dim(vector: list[float]) -> bool:
    """Check that a vector has the expected dimensionality."""
    return len(vector) == EMBEDDING_DIM
