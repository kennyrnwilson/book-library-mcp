"""Tests for the catalog loader."""

from book_library_mcp.catalog import Book, load_catalog


def test_load_catalog_returns_one_book(fixture_library):
    catalog = load_catalog(fixture_library)
    assert len(catalog) == 1


def test_book_has_slug_and_title(fixture_library):
    [book] = load_catalog(fixture_library)
    assert isinstance(book, Book)
    assert book.slug == "sample-book"
    assert book.title.startswith("Sample Book")
    assert book.author == "Jane Doe"


def test_book_metadata_preserves_yaml(fixture_library):
    [book] = load_catalog(fixture_library)
    assert "testing" in book.metadata["categories"]
    assert book.metadata["infographics"]["chatgpt"].endswith(".txt")


def test_get_by_slug_returns_book(fixture_library):
    catalog = load_catalog(fixture_library)
    book = catalog.get("sample-book")
    assert book is not None
    assert book.slug == "sample-book"


def test_get_by_unknown_slug_returns_none(fixture_library):
    catalog = load_catalog(fixture_library)
    assert catalog.get("nonexistent") is None
