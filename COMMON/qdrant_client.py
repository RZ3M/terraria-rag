"""
COMMON/qdrant_client.py — Shared Qdrant client singleton.

Provides a single Qdrant client instance for the entire application.
Manages collection creation and schema setup.
"""

import logging
from functools import lru_cache
from typing import Optional

from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models
from qdrant_client.http.exceptions import UnexpectedResponse

from COMMON.config import (
    QDRANT_HOST,
    QDRANT_PORT,
    COLLECTION_NAME,
    EMBEDDING_DIM,
    HNSW_M,
    HNSW_EF_CONSTRUCT,
    PAYLOAD_INDEX_FIELDS,
)

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_qdrant_client() -> QdrantClient:
    """
    Get the shared Qdrant client instance.

    Returns a QdrantClient connected to the configured host:port.
    """
    client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    logger.info(f"Qdrant client connected to {QDRANT_HOST}:{QDRANT_PORT}")
    return client


def collection_exists(client: Optional[QdrantClient] = None) -> bool:
    """Check if the terraria_wiki collection already exists."""
    if client is None:
        client = get_qdrant_client()
    try:
        client.get_collection(COLLECTION_NAME)
        return True
    except (UnexpectedResponse, Exception):
        return False


def create_collection(
    client: Optional[QdrantClient] = None,
    force_recreate: bool = False,
) -> None:
    """
    Create the terraria_wiki collection with the correct schema.

    Parameters
    ----------
    client : QdrantClient, optional
        Existing client. If None, creates one.
    force_recreate : bool
        If True, delete and recreate the collection even if it exists.
    """
    if client is None:
        client = get_qdrant_client()

    if collection_exists(client):
        if force_recreate:
            logger.warning(f"Force recreating collection '{COLLECTION_NAME}'")
            client.delete_collection(COLLECTION_NAME)
        else:
            logger.info(f"Collection '{COLLECTION_NAME}' already exists. Skipping.")
            return

    # Build payload index schemas for filterable fields
    payload_schema = {}
    for field in PAYLOAD_INDEX_FIELDS:
        payload_schema[field] = qdrant_models.PayloadSchemaType.KEYWORD

    # Add integer schema for numeric fields
    payload_schema["chunk_index"] = qdrant_models.PayloadSchemaType.INTEGER
    payload_schema["tokens_estimate"] = qdrant_models.PayloadSchemaType.INTEGER

    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config={
            "default": qdrant_models.VectorParams(
                size=EMBEDDING_DIM,
                distance=qdrant_models.Distance.COSINE,
                hnsw_config=qdrant_models.HnswConfigDiff(
                    m=HNSW_M,
                    ef_construct=HNSW_EF_CONSTRUCT,
                ),
            )
        },
        # Note: sparse vectors not used in this project
        # sparse_vectors_config=None,
    )

    # Set payload schema for filtering
    # Note: Qdrant 1.7+ uses client.create_field_index instead of payload_schema parameter
    # Keeping for backwards compat; the create_collection call is the important one
    for field_name, field_type in payload_schema.items():
        try:
            client.create_field_index(
                collection_name=COLLECTION_NAME,
                field_name=field_name,
                field_schema=field_type,
            )
        except Exception as e:
            logger.debug(f"Field index creation for '{field_name}' skipped or already exists: {e}")

    logger.info(f"Collection '{COLLECTION_NAME}' created successfully with {EMBEDDING_DIM}d vectors")


def ensure_collection_exists() -> QdrantClient:
    """
    Ensure the collection exists, creating it if necessary.
    Returns the shared client.
    """
    client = get_qdrant_client()
    if not collection_exists(client):
        create_collection(client)
    return client


def get_collection_info(client: Optional[QdrantClient] = None) -> dict:
    """Return basic info about the collection."""
    if client is None:
        client = get_qdrant_client()
    try:
        info = client.get_collection(COLLECTION_NAME)
        return {
            "name": COLLECTION_NAME,
            "points_count": info.points_count,
            "status": info.status,
            "dim": info.config.params.vectors["default"].size,
        }
    except Exception as e:
        return {"error": str(e)}
