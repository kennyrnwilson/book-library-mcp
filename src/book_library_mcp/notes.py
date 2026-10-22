"""Write tools for a book's personal notes: `<slug>/personal-notes/README.md`.

The personal notes hold the reader's own notes and quotes for a book, next to
the pipeline's summaries. These tools write that one file per book and nothing
else, and never commit: `save_book_changes` in `git_ops` is the only path from
disk to git history.

A quote takes the four-part shape of knowledge-library's literature notes:

    > "The quote."
    > — Author, *Title*, location

    - **Why:** one line on why it mattered
    - **Links:** #quote/theme
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

NOTES_FILE = Path("personal-notes") / "README.md"
QUOTES_HEADING = "## 💬 Quotes & Highlights"

_QUOTES_SECTION = re.compile(r"^## .*Quotes & Highlights.*$", re.MULTILINE)
_SECTION_END = re.compile(r"^(## |---$)", re.MULTILINE)
_LAST_UPDATED = re.compile(r"^\*Last [Uu]pdated: [^*]*\*$", re.MULTILINE)
# The placeholder each book's folder starts with.
_EMPTY = {"", "# Personal Notes"}


def _slugify(text: str) -> str:
    s = re.sub(r"['’‘\"`]+", "", text.lower())
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def notes_path(book_path: Path) -> Path:
    return book_path / NOTES_FILE


def new_notes(title: str, today: str) -> str:
    """The skeleton of a book's personal notes, for a book that has none yet."""
    return (
        f"# {title}: personal notes\n\n"
        f"← [Back to {title}](../README.md)\n\n"
        f"{QUOTES_HEADING}\n\n"
        "---\n\n"
        "**Tags:** #book\n\n"
        f"*Created: {today}*\n"
        f"*Last Updated: {today}*\n"
    )


def format_quote(
    text: str,
    author: str,
    title: str,
    location: str,
    why: str,
    themes: list[str] | None = None,
    links: list[str] | None = None,
) -> str:
    """Return one quote in the four-part shape, without surrounding blank lines."""
    text = text.strip().strip('"“”')
    if not text:
        raise ValueError("a quote needs its text")
    if not why.strip():
        raise ValueError("a quote needs a 'why': one line on why it mattered")
    source = f"— {author.strip()}, *{title.strip()}*"
    if location.strip():
        source += f", {location.strip()}"
    quoted = "\n".join(f"> {line}" if line else ">" for line in f'"{text}"'.splitlines())
    tags = [f"#quote/{_slugify(t)}" for t in (themes or []) if _slugify(t)]
    link_parts = [link.strip() for link in (links or []) if link.strip()] + tags
    lines = [quoted, f"> {source}", "", f"- **Why:** {why.strip()}"]
    if link_parts:
        lines.append(f"- **Links:** {' · '.join(link_parts)}")
    return "\n".join(lines)


def insert_quote(note: str, block: str, today: str) -> str:
    """Append `block` to the end of the note's quotes section, adding one if missing."""
    match = _QUOTES_SECTION.search(note)
    if match is None:
        footer = note.rfind("\n---\n")
        head, tail = (note[:footer], note[footer:]) if footer != -1 else (note, "\n")
        note = f"{head.rstrip()}\n\n{QUOTES_HEADING}\n{tail}"
        match = _QUOTES_SECTION.search(note)
    start = match.end()
    end_match = _SECTION_END.search(note, start)
    end = end_match.start() if end_match else len(note)
    body = note[start:end].rstrip()
    new_body = f"{body}\n\n{block}\n\n" if body else f"\n\n{block}\n\n"
    note = note[:start] + new_body + note[end:]
    return _LAST_UPDATED.sub(f"*Last Updated: {today}*", note)


def add_book_quote(
    book_path: Path,
    title: str,
    author: str,
    text: str,
    why: str,
    location: str = "",
    themes: list[str] | None = None,
    links: list[str] | None = None,
    today: str | None = None,
) -> dict:
    """Append a quote to a book's personal notes, creating them if they are empty."""
    today = today or date.today().isoformat()
    path = notes_path(book_path)
    existing = path.read_text() if path.is_file() else ""
    created = existing.strip() in _EMPTY
    note = new_notes(title, today) if created else existing
    block = format_quote(text, author, title, location, why, themes, links)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(insert_quote(note, block, today))
    return {"path": f"{book_path.name}/{NOTES_FILE.as_posix()}", "created": created}


def write_personal_notes(book_path: Path, content: str) -> dict:
    """Replace a book's personal notes with `content`."""
    if not content.strip():
        raise ValueError("refusing to write empty personal notes")
    path = notes_path(book_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content if content.endswith("\n") else content + "\n")
    return {"path": f"{book_path.name}/{NOTES_FILE.as_posix()}"}
