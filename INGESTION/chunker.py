"""
INGESTION/chunker.py — Semantic chunking of parsed wiki sections.

Chunks parsed sections into size-limited pieces suitable for embedding
and retrieval. Key design:
- Chunks are bounded by ~512 tokens
- Split on paragraph boundaries when possible
- Maintain 50-token overlap across chunk boundaries
- Each chunk carries metadata about its position in the page
"""

import logging
import math
from typing import Iterator

from COMMON.config import (
    CHUNK_MAX_TOKENS,
    CHUNK_OVERLAP_TOKENS,
    CHUNK_HTML_STRIP,
    WIKI_BASE_URL,
)
from COMMON.types import WikiChunk, WikiPage
from INGESTION.parser import ParsedSection, parse_wiki_page, infer_category

logger = logging.getLogger(__name__)


def chunk_page(wiki_page: WikiPage) -> list[WikiChunk]:
    """
    Parse a wiki page and produce a list of WikiChunk objects.

    Parameters
    ----------
    wiki_page : WikiPage
        The raw wiki page with content.

    Returns
    -------
    list[WikiChunk]
        Ordered list of chunks from this page.
    """
    sections = parse_wiki_page(wiki_page)

    if not sections:
        logger.debug(f"No sections parsed for page: {wiki_page.title}")
        return []

    # Infer category from title and content
    category, subcategory = infer_category(wiki_page.title, wiki_page.content)

    chunks: list[WikiChunk] = []
    chunk_index = 0

    for section in sections:
        # Strip HTML if configured
        if CHUNK_HTML_STRIP:
            section_text = section.content_text
        else:
            section_text = section.content_html

        if not section_text or len(section_text.strip()) < 50:
            continue

        # Check if the whole section fits in one chunk
        section_tokens = _estimate_tokens(section_text)

        if section_tokens <= CHUNK_MAX_TOKENS:
            chunks.append(WikiChunk(
                wiki_title=wiki_page.title,
                wiki_url=wiki_page.url,
                section_path=section.path,
                chunk_index=chunk_index,
                content=section_text,
                raw_html=section.content_html if not CHUNK_HTML_STRIP else "",
                category=category,
                subcategory=subcategory,
                tokens_estimate=section_tokens,
            ))
            chunk_index += 1
        else:
            # Split section into smaller chunks
            section_chunks = _split_by_paragraph(
                section_text,
                section,
                wiki_page,
                category,
                subcategory,
                chunk_index,
            )
            chunks.extend(section_chunks)
            chunk_index += len(section_chunks)

    return chunks


def _split_by_paragraph(
    text: str,
    section: ParsedSection,
    wiki_page: WikiPage,
    category: str,
    subcategory: str,
    start_index: int,
) -> list[WikiChunk]:
    """
    Split a large section into smaller chunks by paragraph.

    Attempts to keep paragraphs intact. Falls back to sentence splitting
    if paragraphs are too large. Maintains CHUNK_OVERLAP_TOKENS overlap.
    """
    # Split on double newlines (paragraphs)
    paragraphs = text.split("\n\n")
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    if not paragraphs:
        # Fallback: split by single newlines
        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]

    chunks: list[WikiChunk] = []
    current_chunk_parts: list[str] = []
    current_token_count = 0
    chunk_idx = start_index

    def _make_chunk(parts: list[str], idx: int) -> WikiChunk:
        content = " ".join(parts)
        return WikiChunk(
            wiki_title=wiki_page.title,
            wiki_url=wiki_page.url,
            section_path=section.path,
            chunk_index=idx,
            content=content,
            raw_html="",
            category=category,
            subcategory=subcategory,
            tokens_estimate=_estimate_tokens(content),
        )

    for para in paragraphs:
        para_tokens = _estimate_tokens(para)

        if para_tokens > CHUNK_MAX_TOKENS:
            # Single paragraph too large — split by sentence
            sentence_chunks = _split_by_sentence(
                para, section, wiki_page, category, subcategory, chunk_idx
            )
            chunks.append(sentence_chunks)
            chunk_idx += 1
            current_chunk_parts = []
            current_token_count = 0
        elif current_token_count + para_tokens <= CHUNK_MAX_TOKENS:
            current_chunk_parts.append(para)
            current_token_count += para_tokens
        else:
            # Current chunk is full — save it and start new one
            if current_chunk_parts:
                chunks.append(_make_chunk(current_chunk_parts, chunk_idx))
                chunk_idx += 1

            # Handle overlap
            if CHUNK_OVERLAP_TOKENS > 0 and current_chunk_parts:
                overlap_text = " ".join(current_chunk_parts)
                overlap_tokens = _estimate_tokens(overlap_text)

                # Include as many previous paragraphs as fit in overlap
                overlap_parts: list[str] = []
                for part in reversed(current_chunk_parts):
                    part_tokens = _estimate_tokens(part)
                    if overlap_tokens + part_tokens <= CHUNK_OVERLAP_TOKENS:
                        overlap_parts.insert(0, part)
                        overlap_tokens += part_tokens
                    else:
                        break

                if overlap_parts:
                    current_chunk_parts = overlap_parts + [para]
                    current_token_count = overlap_tokens + para_tokens
                else:
                    current_chunk_parts = [para]
                    current_token_count = para_tokens
            else:
                current_chunk_parts = [para]
                current_token_count = para_tokens

    # Don't forget the last chunk
    if current_chunk_parts:
        chunks.append(_make_chunk(current_chunk_parts, chunk_idx))

    return chunks


def _split_by_sentence(
    text: str,
    section: ParsedSection,
    wiki_page: WikiPage,
    category: str,
    subcategory: str,
    start_index: int,
) -> WikiChunk:
    """
    Split a very large paragraph by sentence boundaries.
    Returns a single chunk (caller handles iteration if multiple chunks needed).
    """
    import re
    # Split on sentence-ending punctuation followed by space
    sentences = re.split(r"(?<=[.!?])\s+", text)

    chunks: list[WikiChunk] = []
    current_parts: list[str] = []
    current_tokens = 0
    idx = start_index

    for sentence in sentences:
        s_tokens = _estimate_tokens(sentence)
        if current_tokens + s_tokens <= CHUNK_MAX_TOKENS:
            current_parts.append(sentence)
            current_tokens += s_tokens
        else:
            if current_parts:
                chunks.append(WikiChunk(
                    wiki_title=wiki_page.title,
                    wiki_url=wiki_page.url,
                    section_path=section.path,
                    chunk_index=idx,
                    content=" ".join(current_parts),
                    raw_html="",
                    category=category,
                    subcategory=subcategory,
                    tokens_estimate=current_tokens,
                ))
                idx += 1
            current_parts = [sentence]
            current_tokens = s_tokens

    if current_parts:
        chunks.append(WikiChunk(
            wiki_title=wiki_page.title,
            wiki_url=wiki_page.url,
            section_path=section.path,
            chunk_index=idx,
            content=" ".join(current_parts),
            raw_html="",
            category=category,
            subcategory=subcategory,
            tokens_estimate=current_tokens,
        ))

    # Return the first chunk; caller should iterate if more are needed
    return chunks[0] if chunks else WikiChunk(
        wiki_title=wiki_page.title,
        wiki_url=wiki_page.url,
        section_path=section.path,
        chunk_index=start_index,
        content=text[: CHUNK_MAX_TOKENS * 4],  # rough truncate
        category=category,
        subcategory=subcategory,
        tokens_estimate=CHUNK_MAX_TOKENS,
    )


def _estimate_tokens(text: str) -> int:
    """
    Rough token estimate: ~4 characters per token for English text.
    More accurate would use a tokenizer, but that's slow for large docs.
    """
    if not text:
        return 0
    return max(1, len(text) // 4)


def chunk_pages(pages: Iterator[WikiPage]) -> Iterator[list[WikiChunk]]:
    """
    Process an iterator of wiki pages, yielding chunk lists per page.

    Parameters
    ----------
    pages : Iterator[WikiPage]
        Iterator of raw wiki pages.

    Yields
    ------
    list[WikiChunk]
        Chunks for each page in order.
    """
    for page in pages:
        chunks = chunk_page(page)
        if chunks:
            yield chunks
