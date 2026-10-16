"""FastMCP server exposing book-library tools."""

from __future__ import annotations

import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP, Image

from book_library_mcp.catalog import load_catalog
from book_library_mcp.images import (
    find_book_infographic,
    find_chapter_infographic,
    list_chapter_infographics,
    prepare_image,
)
from book_library_mcp.search import search_library


def _resolve_library_root() -> Path:
    """Resolve the library root from env or by walking up from this module."""
    env = os.environ.get("BOOK_LIBRARY_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    # Fallback: src/book_library_mcp/server.py → mcp-server/ → book-library/
    return Path(__file__).resolve().parents[3]


def build_server(host: str = "127.0.0.1", port: int = 5102) -> FastMCP:
    """Build and return a configured FastMCP app. Called at startup and from tests."""
    library_root = _resolve_library_root()
    catalog = load_catalog(library_root)
    mcp = FastMCP("book-library", host=host, port=port)

    def _require_book(slug: str):
        book = catalog.get(slug)
        if book is None:
            raise ValueError(f"book not found: {slug!r}")
        return book

    @mcp.tool()
    def list_books() -> list[dict]:
        """List all books in the library: slug, title, author."""
        return [
            {"slug": b.slug, "title": b.title, "author": b.author}
            for b in catalog.all()
        ]

    @mcp.tool()
    def search_books(query: str) -> list[dict]:
        """Full-text search across all book content. Returns slug + line context."""
        return [
            {
                "slug": h.slug,
                "path": h.relative_path,
                "line": h.line_number,
                "text": h.line,
            }
            for h in search_library(library_root, query)
        ]

    @mcp.tool()
    def get_book_metadata(slug: str) -> dict:
        """Return the full metadata.yaml for one book."""
        book = _require_book(slug)
        return book.metadata

    @mcp.tool()
    def get_chapter_summary(slug: str, chapter: str) -> str:
        """Return the markdown of `chapter-summaries/<chapter>.md` for one book."""
        book = _require_book(slug)
        path = book.path / "chapter-summaries" / f"{chapter}.md"
        if not path.exists():
            raise ValueError(f"chapter not found: {slug}/{chapter}")
        return path.read_text()

    @mcp.tool()
    def get_action_items(slug: str) -> str:
        """Return the contents of action-items.md for one book."""
        book = _require_book(slug)
        path = book.path / "action-items.md"
        if not path.exists():
            raise ValueError(f"action-items.md not found for {slug}")
        return path.read_text()

    @mcp.tool()
    def get_personal_notes(slug: str) -> str:
        """Return aggregated personal-notes/ content for one book."""
        book = _require_book(slug)
        notes_dir = book.path / "personal-notes"
        if not notes_dir.is_dir():
            raise ValueError(f"personal-notes/ not found for {slug}")
        chunks: list[str] = []
        for md in sorted(notes_dir.glob("*.md")):
            chunks.append(f"# {md.name}\n\n{md.read_text()}")
        return "\n\n---\n\n".join(chunks)

    @mcp.tool()
    def get_book_infographic_text(slug: str, source: str = "chatgpt") -> str:
        """Return the contents of `<slug>_book_infographic_<source>.txt`.

        `source` is one of `chatgpt` (default) or `gemini`. Falls back to whichever
        variant exists if the requested one isn't present.
        """
        book = _require_book(slug)
        candidates = [
            book.path / f"{slug}_book_infographic_{source}.txt",
            book.path / f"{slug}_book_infographic_chatgpt.txt",
            book.path / f"{slug}_book_infographic_gemini.txt",
        ]
        for path in candidates:
            if path.exists():
                return path.read_text()
        raise ValueError(f"no infographic .txt found for {slug}")

    @mcp.tool()
    def list_infographics(slug: str) -> dict:
        """List one book's infographic images.

        `book` says whether a whole-book infographic exists; `chapters` names the
        chapters that have one. Pass a name to `get_infographic`.
        """
        book = _require_book(slug)
        return {
            "book": find_book_infographic(book.path, slug, None) is not None,
            "chapters": list_chapter_infographics(book.path),
        }

    @mcp.tool()
    def get_infographic(
        slug: str, chapter: str | None = None, source: str | None = None
    ) -> Image:
        """Return an infographic image for a whole book, or for one chapter.

        Omit `chapter` for the whole-book infographic; `source` (`chatgpt` or
        `gemini`) picks a variant where a book has both. Give `chapter` as in
        `get_chapter_summary`, e.g. `chapter-00-chapter-1`.
        """
        book = _require_book(slug)
        if chapter:
            path = find_chapter_infographic(book.path, chapter)
            if path is None:
                raise ValueError(f"no infographic for chapter: {slug}/{chapter}")
        else:
            path = find_book_infographic(book.path, slug, source)
            if path is None:
                raise ValueError(f"no book infographic for {slug}")
        data, fmt = prepare_image(path)
        return Image(data=data, format=fmt)

    return mcp
