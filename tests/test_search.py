"""Tests for ripgrep-backed search."""

from book_library_mcp.search import SearchHit, search_library


def test_search_finds_phrase_in_chapter(fixture_library):
    hits = search_library(fixture_library, "deep work")
    slugs = {h.slug for h in hits}
    assert "sample-book" in slugs


def test_search_returns_searchhit_records(fixture_library):
    [hit, *_rest] = search_library(fixture_library, "deep work")
    assert isinstance(hit, SearchHit)
    assert hit.slug == "sample-book"
    assert hit.line_number > 0
    assert "deep work" in hit.line.lower()


def test_search_unknown_phrase_returns_empty(fixture_library):
    hits = search_library(fixture_library, "xyzzy-no-such-phrase")
    assert hits == []
