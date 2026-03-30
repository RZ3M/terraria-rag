"""
INGESTION/run_ingestion.py — Main ingestion orchestrator.

Run with:
    python INGESTION/run_ingestion.py [--resume] [--limit N]

Options:
    --resume    Resume from last checkpoint (skip already-indexed pages)
    --limit N   Process only the first N pages (for testing)
    --verbose   Enable debug logging
"""

import argparse
import logging
import sys
import time
from pathlib import Path

# Ensure the project root is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tqdm import tqdm

from COMMON.config import (
    LOG_LEVEL,
    LOG_FORMAT,
    INGESTION_STATE_FILE,
    FETCH_BATCH_SIZE,
)
from COMMON.qdrant_client import create_collection, collection_exists
from INGESTION.fetcher import (
    fetch_all_page_titles,
    fetch_page_content,
)
from INGESTION.chunker import chunk_page
from INGESTION.embedder import embed_chunks
from INGESTION.indexer import (
    index_chunks,
    load_ingestion_state,
    save_chunks_to_disk,
)

logger = logging.getLogger("run_ingestion")


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format=LOG_FORMAT,
    )


def run_full_ingestion(
    resume: bool = True,
    limit: int = 0,
    verbose: bool = False,
) -> None:
    """
    Run the full ingestion pipeline.

    1. Fetch all wiki page titles (or load cached list)
    2. For each page: fetch content, chunk, embed, index
    3. Track progress in ingestion_state.json for resume support
    """
    log_level = "DEBUG" if verbose else LOG_LEVEL
    setup_logging(log_level)

    logger.info("=" * 60)
    logger.info("Terraria RAG — Full Ingestion Pipeline")
    logger.info("=" * 60)

    # Ensure Qdrant collection exists
    if not collection_exists():
        logger.info("Creating Qdrant collection...")
        create_collection()
    else:
        logger.info("Qdrant collection already exists.")

    # Load ingestion state
    state = load_ingestion_state() if resume else {"version": 1, "total_pages_processed": 0, "total_chunks_indexed": 0, "pages": {}}
    indexed_pages = set(int(k) for k in state.get("pages", {}).keys())

    logger.info(f"Starting ingestion. {len(indexed_pages)} pages already indexed.")
    if limit > 0:
        logger.info(f"Limit set: processing first {limit} pages only.")

    # Fetch page list
    logger.info("Fetching wiki page list...")
    start_time = time.time()

    all_pages = list(fetch_all_page_titles(exclude_redirects=True, namespaces=[0]))

    if limit > 0:
        all_pages = all_pages[:limit]

    total_pages = len(all_pages)
    logger.info(f"Found {total_pages} pages to process. "
                f"({indexed_pages.__len__()} already indexed, "
                f"{total_pages - len(indexed_pages)} to process)")

    # Filter out already-indexed pages if resuming
    if resume:
        pages_to_process = [p for p in all_pages if p.page_id not in indexed_pages]
    else:
        pages_to_process = all_pages

    logger.info(f"Processing {len(pages_to_process)} pages...")

    total_chunks_all_time = state.get("total_chunks_indexed", 0)
    total_pages_all_time = state.get("total_pages_processed", 0)

    # Process pages with progress bar
    for page in tqdm(pages_to_process, desc="Ingesting pages", unit="page"):
        page_start = time.time()

        try:
            # Fetch content (uses cache)
            wiki_page = fetch_page_content(page.title)
            if wiki_page is None or not wiki_page.exists:
                logger.warning(f"Skipping empty/placeholder page: {page.title}")
                continue

            # Chunk
            chunks = chunk_page(wiki_page)
            if not chunks:
                logger.debug(f"No chunks generated for: {page.title}")
                # Mark as processed anyway to avoid re-fetching
                state["pages"][str(page.page_id)] = {
                    "title": page.title,
                    "chunks_indexed": 0,
                    "last_updated": time.time(),
                }
                continue

            # Embed
            chunk_vector_pairs = list(embed_chunks(chunks))

            # Index
            vectors_only = [v for _, v in chunk_vector_pairs]
            chunks_only = [c for c, _ in chunk_vector_pairs]
            chunks_indexed = index_chunks(chunks_only, vectors_only)
            total_chunks_all_time += chunks_indexed
            total_pages_all_time += 1

            # Update state
            state["pages"][str(page.page_id)] = {
                "title": page.title,
                "chunks_indexed": chunks_indexed,
                "last_updated": time.time(),
            }
            state["total_chunks_indexed"] = total_chunks_all_time
            state["total_pages_processed"] = total_pages_all_time

            # Save state every 10 pages
            if total_pages_all_time % 10 == 0:
                save_ingestion_state(state)

            # Save chunks to disk for debugging
            try:
                save_chunks_to_disk(chunks_only)
            except Exception as e:
                logger.warning(f"Failed to save chunks to disk: {e}")

            elapsed = time.time() - page_start
            rate = len(chunks_only) / elapsed if elapsed > 0 else 0
            tqdm.write(
                f"  ✓ {page.title} → {chunks_indexed} chunks "
                f"({rate:.1f} chunks/s | total: {total_chunks_all_time})"
            )

        except Exception as e:
            logger.error(f"Failed to process page '{page.title}': {e}")
            continue

    # Final state save
    save_ingestion_state(state)

    elapsed_total = time.time() - start_time
    logger.info("=" * 60)
    logger.info(f"Ingestion complete!")
    logger.info(f"  Pages processed: {total_pages_all_time}")
    logger.info(f"  Total chunks indexed: {total_chunks_all_time}")
    logger.info(f"  Time elapsed: {elapsed_total:.1f}s")
    logger.info(f"  Avg rate: {total_pages_all_time / elapsed_total:.2f} pages/s")
    logger.info("=" * 60)


def run_preview(limit: int = 10) -> None:
    """
    Run a small preview of the pipeline — fetch and chunk a few pages,
    no indexing. Useful for testing without committing to full ingestion.
    """
    setup_logging("DEBUG")

    logger.info(f"Preview mode: processing first {limit} pages (no indexing)")

    # Fetch pages lazily — stop as soon as we have enough
    all_pages = fetch_all_page_titles(exclude_redirects=True, namespaces=[0])
    collected = 0

    for page in all_pages:
        if collected >= limit:
            break

        wiki_page = fetch_page_content(page.title)
        if wiki_page is None:
            continue

        chunks = chunk_page(wiki_page)
        print(f"\n{'=' * 60}")
        print(f"Page: {page.title}")
        print(f"URL: {wiki_page.url}")
        print(f"Content length: {len(wiki_page.content)} chars")
        print(f"Chunks produced: {len(chunks)}")
        for i, chunk in enumerate(chunks[:3]):  # show first 3
            print(f"  Chunk {i}: [{chunk.section_path}] "
                  f"(~{chunk.tokens_estimate} tokens)\n"
                  f"    {chunk.content[:150]}...")

        if len(chunks) > 3:
            print(f"  ... and {len(chunks) - 3} more chunks")

        collected += 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Terraria RAG — Ingestion Pipeline")
    parser.add_argument("--resume", action="store_true", default=True,
                        help="Resume from last checkpoint (default: True)")
    parser.add_argument("--no-resume", dest="resume", action="store_false",
                        help="Start fresh (reprocess all pages)")
    parser.add_argument("--limit", type=int, default=0,
                        help="Limit to N pages (0 = all pages)")
    parser.add_argument("--preview", action="store_true",
                        help="Run preview mode (no indexing, just fetch+chunk)")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Enable debug logging")

    args = parser.parse_args()

    if args.preview:
        run_preview(limit=args.limit or 10)
    else:
        run_full_ingestion(
            resume=args.resume,
            limit=args.limit,
            verbose=args.verbose,
        )


if __name__ == "__main__":
    main()
