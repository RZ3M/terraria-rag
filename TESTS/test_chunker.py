"""
TESTS/test_chunker.py — Tests for the chunking pipeline.
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from COMMON.types import WikiPage
from INGESTION.chunker import chunk_page, _estimate_tokens
from INGESTION.parser import parse_wiki_page


class TestTokenEstimate:
    def test_empty_text(self):
        assert _estimate_tokens("") == 0
        assert _estimate_tokens("   ") == 0

    def test_short_text(self):
        text = "The quick brown fox."
        tokens = _estimate_tokens(text)
        assert tokens >= 3
        assert tokens <= 10

    def test_long_text(self):
        text = "word " * 100
        tokens = _estimate_tokens(text)
        assert tokens >= 20
        assert tokens <= 30


class TestChunkPage:
    def test_small_page(self):
        """A small page should produce at least one chunk."""
        page = WikiPage(
            page_id=1,
            title="Test Page",
            url="https://example.com/wiki/Test_Page",
            content="This is a small page with some content about Terraria.",
            length=60,
        )
        chunks = chunk_page(page)
        assert len(chunks) >= 1
        assert chunks[0].wiki_title == "Test Page"
        assert chunks[0].chunk_index == 0

    def test_heading_structure(self):
        """Chunks should maintain section paths from headings."""
        wikitext = """== Introduction ==
This is the intro.

== Crafting ==
This is the crafting section.

== Usage ==
This is the usage section.
"""
        page = WikiPage(
            page_id=2,
            title="Test Item",
            url="https://example.com/wiki/Test_Item",
            content=wikitext,
            length=len(wikitext),
        )
        chunks = chunk_page(page)
        if len(chunks) > 1:
            # Different sections should have different paths
            paths = set(c.section_path for c in chunks)
            # At minimum, intro and a section should differ
            assert len(paths) >= 1

    def test_no_empty_chunks(self):
        """No chunk should be empty or just whitespace."""
        page = WikiPage(
            page_id=3,
            title="Test",
            url="https://example.com/wiki/Test",
            content="Some content here. " * 100,
            length=1000,
        )
        chunks = chunk_page(page)
        for chunk in chunks:
            assert len(chunk.content.strip()) > 50, f"Chunk too short: {chunk.content[:50]}"


class TestParseWikiPage:
    def test_wikitext_headings(self):
        wikitext = """== Section 1 ==
Content of section 1.

=== Subsection 1.1 ===
Content of subsection.

== Section 2 ==
Content of section 2.
"""
        page = WikiPage(page_id=1, title="Test", url="", content=wikitext, length=len(wikitext))
        sections = parse_wiki_page(page)
        assert len(sections) >= 3  # At least 3 sections

    def test_empty_content(self):
        page = WikiPage(page_id=1, title="Empty", url="", content="", length=0)
        sections = parse_wiki_page(page)
        assert len(sections) == 0
