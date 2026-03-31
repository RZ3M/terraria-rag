"""
INGESTION/chunker.py — Semantic chunking of parsed wiki sections.

Chunks parsed sections into size-limited pieces suitable for embedding
and retrieval. Key design:
- Chunks are bounded by ~512 tokens
- Split on paragraph boundaries when possible
- Maintain 50-token overlap across chunk boundaries
- Each chunk carries metadata about its position in the page

Supports two content modes:
- Wikitext (via parse_wiki_page from parser.py)
- Rendered HTML (via parse_html_page from parser_html.py)
"""

import logging
import re
from typing import Iterator

from COMMON.config import (
    CHUNK_MAX_TOKENS,
    CHUNK_OVERLAP_TOKENS,
    CHUNK_HTML_STRIP,
)
from COMMON.types import WikiChunk, WikiPage
from INGESTION.parser import (
    ParsedSection, parse_wiki_page,
    infer_category, infer_game_mode, infer_obtain_method,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def chunk_page(wiki_page: WikiPage) -> list[WikiChunk]:
    """
    Parse a wikitext wiki page and produce a list of WikiChunk objects.

    Parameters
    ----------
    wiki_page : WikiPage
        The raw wiki page with wikitext content.

    Returns
    -------
    list[WikiChunk]
        Ordered list of chunks from this page.
    """
    sections = parse_wiki_page(wiki_page)
    return _chunk_sections(sections, wiki_page.title, wiki_page.url, wiki_page.content)


def chunk_html_page(
    wiki_page: WikiPage,
    article_text: str,
) -> list[WikiChunk]:
    """
    Chunk a rendered HTML wiki page.

    The html_fetcher produces plain-text article content (via _build_article_text)
    with markdown-style "## Heading" section markers, where HTML templates and
    recipe tables are already converted to readable text. This function parses
    that article text directly, preserving crafting recipes that would be lost
    in wikitext-only fetching.

    Parameters
    ----------
    wiki_page : WikiPage
        Wiki page metadata (title, url, etc.).
    article_text : str
        The article text content from html_fetcher (plain text with crafting data
        and "## Section" heading markers), OR raw HTML from MediaWiki
        action=parse&prop=text (in which case BeautifulSoup is used).

    Returns
    -------
    list[WikiChunk]
        Chunks from the article with full crafting information.
    """
    from bs4 import BeautifulSoup

    # html_fetcher's _build_article_text() produces plain text with "## Heading"
    # markers. If the content looks like that, parse directly without BeautifulSoup.
    if article_text.startswith("\n##") or (
        "## " in article_text[:200] and not article_text.startswith("<")
    ):
        sections = _parse_plain_text_sections(article_text, wiki_page.title)
    else:
        # Raw HTML — use BeautifulSoup + parser_html
        from INGESTION.parser_html import parse_html_page
        wiki_page.content = article_text
        sections = parse_html_page(wiki_page)

    return _chunk_sections(sections, wiki_page.title, wiki_page.url, article_text)


def _parse_plain_text_sections(text: str, page_title: str) -> list[ParsedSection]:
    """
    Parse plain-text article content with markdown-style section headings.
    Handles output from html_fetcher's _build_article_text().
    """

    sections = []
    current_heading = page_title
    current_level = 1
    current_content_lines = []

    def _flush():
        nonlocal current_content_lines, current_heading, current_level
        if current_content_lines:
            content_text = "\n".join(current_content_lines).strip()
            if content_text:
                sections.append(ParsedSection(
                    heading=current_heading,
                    heading_level=current_level,
                    path=current_heading,
                    content_html="",
                    content_text=content_text,
                    raw_content="",
                ))
            current_content_lines = []

    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("## ") or stripped.startswith("##\n"):
            _flush()
            current_heading = stripped.lstrip("#").strip()
            current_level = 2
        elif stripped.startswith("# ") or stripped.startswith("#\n"):
            _flush()
            current_heading = stripped.lstrip("#").strip()
            current_level = 1
        else:
            if stripped:
                current_content_lines.append(stripped)

    _flush()
    return sections


# ---------------------------------------------------------------------------
# Internal chunking logic
# ---------------------------------------------------------------------------

def _chunk_sections(
    sections: list[ParsedSection],
    wiki_title: str,
    wiki_url: str,
    page_content: str,
) -> list[WikiChunk]:
    """
    Core chunking logic shared by both wikitext and HTML parsers.

    Takes parsed sections and produces WikiChunk objects using the
    shared CHUNK_MAX_TOKENS, CHUNK_OVERLAP_TOKENS, and CHUNK_HTML_STRIP settings.
    """
    if not sections:
        logger.debug(f"No sections parsed for page: {wiki_title}")
        return []

    # Build a plain-text sample from the first few sections for metadata inference.
    # For HTML pages, page_content is raw HTML markup — the actual text is buried
    # inside it. Using parsed section text gives much better signal.
    section_text_sample = " ".join(
        s.content_text for s in sections[:5] if s.content_text
    )[:5000]
    inference_text = section_text_sample or page_content[:5000]

    category, subcategory = infer_category(wiki_title, inference_text)
    game_mode = infer_game_mode(inference_text)
    obtain_method = infer_obtain_method(inference_text)

    chunks: list[WikiChunk] = []
    chunk_index = 0

    for section in sections:
        if CHUNK_HTML_STRIP:
            section_text = section.content_text
        else:
            section_text = section.content_html

        if not section_text or len(section_text.strip()) < 50:
            continue

        section_tokens = _estimate_tokens(section_text)

        if section_tokens <= CHUNK_MAX_TOKENS:
            chunks.append(WikiChunk(
                wiki_title=wiki_title,
                wiki_url=wiki_url,
                section_path=section.path,
                chunk_index=chunk_index,
                content=section_text,
                raw_html=section.content_html if not CHUNK_HTML_STRIP else "",
                category=category,
                subcategory=subcategory,
                game_mode=game_mode,
                obtain_method=obtain_method,
                tokens_estimate=section_tokens,
            ))
            chunk_index += 1
        else:
            section_chunks = _split_by_paragraph(
                section_text,
                section,
                wiki_title,
                wiki_url,
                category,
                subcategory,
                game_mode,
                obtain_method,
                chunk_index,
            )
            chunks.extend(section_chunks)
            chunk_index += len(section_chunks)

    return chunks


def _split_by_paragraph(
    text: str,
    section: ParsedSection,
    wiki_title: str,
    wiki_url: str,
    category: str,
    subcategory: str,
    game_mode: list[str],
    obtain_method: str,
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
        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]

    chunks: list[WikiChunk] = []
    current_chunk_parts: list[str] = []
    current_token_count = 0
    chunk_idx = start_index

    def _make_chunk(parts: list[str], idx: int) -> WikiChunk:
        content = " ".join(parts)
        return WikiChunk(
            wiki_title=wiki_title,
            wiki_url=wiki_url,
            section_path=section.path,
            chunk_index=idx,
            content=content,
            raw_html="",
            category=category,
            subcategory=subcategory,
            game_mode=game_mode,
            obtain_method=obtain_method,
            tokens_estimate=_estimate_tokens(content),
        )

    for para in paragraphs:
        para_tokens = _estimate_tokens(para)

        if para_tokens > CHUNK_MAX_TOKENS:
            sentence_chunks = _split_by_sentence(
                para, section, wiki_title, wiki_url, category, subcategory,
                game_mode, obtain_method, chunk_idx
            )
            chunks.extend(sentence_chunks)
            chunk_idx += len(sentence_chunks)
            current_chunk_parts = []
            current_token_count = 0
        elif current_token_count + para_tokens <= CHUNK_MAX_TOKENS:
            current_chunk_parts.append(para)
            current_token_count += para_tokens
        else:
            if current_chunk_parts:
                chunks.append(_make_chunk(current_chunk_parts, chunk_idx))
                chunk_idx += 1

            if CHUNK_OVERLAP_TOKENS > 0 and current_chunk_parts:
                # Accumulate overlap from the END of the previous chunk.
                # Start at 0 and add parts until we hit the overlap budget.
                # (Previously started at full chunk size, so budget was always exceeded.)
                overlap_tokens = 0
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

    if current_chunk_parts:
        chunks.append(_make_chunk(current_chunk_parts, chunk_idx))

    return chunks


def _split_by_sentence(
    text: str,
    section: ParsedSection,
    wiki_title: str,
    wiki_url: str,
    category: str,
    subcategory: str,
    game_mode: list[str],
    obtain_method: str,
    start_index: int,
) -> list[WikiChunk]:
    """
    Split a very large paragraph by sentence boundaries.
    Returns ALL resulting chunks (previously only returned chunks[0]).
    """
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
                    wiki_title=wiki_title,
                    wiki_url=wiki_url,
                    section_path=section.path,
                    chunk_index=idx,
                    content=" ".join(current_parts),
                    raw_html="",
                    category=category,
                    subcategory=subcategory,
                    game_mode=game_mode,
                    obtain_method=obtain_method,
                    tokens_estimate=current_tokens,
                ))
                idx += 1
            current_parts = [sentence]
            current_tokens = s_tokens

    if current_parts:
        chunks.append(WikiChunk(
            wiki_title=wiki_title,
            wiki_url=wiki_url,
            section_path=section.path,
            chunk_index=idx,
            content=" ".join(current_parts),
            raw_html="",
            category=category,
            subcategory=subcategory,
            game_mode=game_mode,
            obtain_method=obtain_method,
            tokens_estimate=current_tokens,
        ))

    if not chunks:
        # Fallback: hard-truncate to fit model
        chunks = [WikiChunk(
            wiki_title=wiki_title,
            wiki_url=wiki_url,
            section_path=section.path,
            chunk_index=start_index,
            content=text[: CHUNK_MAX_TOKENS * 4],
            raw_html="",
            category=category,
            subcategory=subcategory,
            game_mode=game_mode,
            obtain_method=obtain_method,
            tokens_estimate=CHUNK_MAX_TOKENS,
        )]

    return chunks


def _estimate_tokens(text: str) -> int:
    """
    Rough token estimate: ~4 characters per token for English text.
    """
    if not text:
        return 0
    return max(1, len(text) // 4)


def chunk_pages(pages: Iterator[WikiPage]) -> Iterator[list[WikiChunk]]:
    """
    Process an iterator of wiki pages, yielding chunk lists per page.

    Yields
    ------
    list[WikiChunk]
        Chunks for each page in order.
    """
    for page in pages:
        chunks = chunk_page(page)
        if chunks:
            yield chunks
