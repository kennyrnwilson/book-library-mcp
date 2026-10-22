"""FastMCP server exposing book-library tools."""

from __future__ import annotations

import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP, Image

from book_library_mcp.catalog import load_catalog
from book_library_mcp.git_ops import list_pending_changes as _list_pending
from book_library_mcp.git_ops import save_changes as _save_changes
from book_library_mcp.images import (
    find_book_infographic,
    find_chapter_infographic,
    list_chapter_infographics,
    prepare_image,
)
from book_library_mcp.notes import add_book_quote as _add_book_quote
from book_library_mcp.notes import write_personal_notes as _write_personal_notes
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

    # ---- Write tools (one file per book; filesystem only, no git) --------------

    @mcp.tool()
    def add_book_quote(
        slug: str,
        text: str,
        why: str,
        location: str = "",
        themes: list[str] | None = None,
        links: list[str] | None = None,
    ) -> dict:
        """Append a quote to one book's personal notes, `<slug>/personal-notes/README.md`.

        Writes the quote, a source line (the book's author and title, plus a location
        such as "ch. 11, p. 213"), a "Why" line in the user's words, and links plus one
        `#quote/<theme>` tag per theme. Ask the user why the quote mattered if they
        have not said. Does not commit: call `save_book_changes` once the user approves.
        """
        book = _require_book(slug)
        return _add_book_quote(book.path, title=book.title, author=book.author, text=text,
                               why=why, location=location, themes=themes, links=links)

    @mcp.tool()
    def write_personal_notes(slug: str, content: str) -> dict:
        """Replace one book's personal notes, `<slug>/personal-notes/README.md`, with `content`.

        Read them first with `get_personal_notes`, and send back the whole file. Does
        not commit: call `save_book_changes` once the user approves.
        """
        book = _require_book(slug)
        return _write_personal_notes(book.path, content)

    # ---- Git tools (explicit-save model) ---------------------------------------

    @mcp.tool()
    def list_pending_book_changes() -> list[dict]:
        """Return uncommitted changes in the book library (parsed git status)."""
        return _list_pending(library_root)

    @mcp.tool()
    def save_book_changes(message: str | None = None) -> dict:
        """Stage all changes in the book library, commit, and push origin main.

        ONLY call this tool when the user has explicitly approved the change
        ("save it", "commit that", "looks good, push it"). Drafts iterated in
        chat without explicit approval should remain uncommitted on disk.
        """
        result = _save_changes(library_root, message=message)
        return {
            "committed": result.committed,
            "pushed": result.pushed,
            "commit_sha": result.commit_sha,
            "message": result.message,
            "pending_count": len(result.pending),
        }

    return mcp
