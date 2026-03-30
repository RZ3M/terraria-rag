"""COMMON — shared utilities, config, types for Terraria RAG."""

from COMMON.config import *
from COMMON.types import (
    WikiChunk,
    WikiPage,
    RetrievalResult,
    QueryResult,
    GameState,
)
from COMMON.qdrant_client import (
    get_qdrant_client,
    collection_exists,
    create_collection,
    ensure_collection_exists,
    get_collection_info,
)
from COMMON.embedding_model import (
    get_embedding_model,
    embed_texts,
    embed_single,
)

__all__ = [
    # config
    "WIKI_API_BASE",
    "WIKI_BASE_URL",
    "COLLECTION_NAME",
    "EMBEDDING_DIM",
    "EMBEDDING_MODEL_NAME",
    "TOP_K",
    "RETRIEVE_K",
    "CHUNK_MAX_TOKENS",
    "CHUNK_OVERLAP_TOKENS",
    "MINIMAX_API_KEY",
    "OPENROUTER_API_KEY",
    "SYSTEM_PROMPT",
    "USER_PROMPT_TEMPLATE",
    "DEFAULT_GAME_STATE",
    # types
    "WikiChunk",
    "WikiPage",
    "RetrievalResult",
    "QueryResult",
    "GameState",
    # client
    "get_qdrant_client",
    "collection_exists",
    "create_collection",
    "ensure_collection_exists",
    "get_collection_info",
    # embeddings
    "get_embedding_model",
    "embed_texts",
    "embed_single",
]
