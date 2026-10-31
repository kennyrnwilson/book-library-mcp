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

A note takes a heading for where it was made, the passage it is about, then
the reader's own words:

    ### ch. 3 · 2026-10-31

    > the passage

    The note.

A quote or note made in the reading app ends with its place in the EPUB as an
HTML comment, `<!-- anchor: epubcfi(...) -->`, invisible when rendered.
`parse_annotations` reads both shapes back.
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

NOTES_FILE = Path("personal-notes") / "README.md"
HIGHLIGHTS_FILE = Path("personal-notes") / "highlights.json"
QUOTES_HEADING = "## 💬 Quotes & Highlights"
NOTES_HEADING = "## 📝 Notes"

_QUOTES_SECTION = re.compile(r"^## .*Quotes & Highlights.*$", re.MULTILINE)
_NOTES_SECTION = re.compile(r"^## .*\bNotes$", re.MULTILINE)
_ANCHOR = re.compile(r"^<!-- anchor: (.+?) -->$", re.MULTILINE)
_SECTION_END = re.compile(r"^(## |---$)", re.MULTILINE)
_LAST_UPDATED = re.compile(r"^\*Last [Uu]pdated: [^*]*\*$", re.MULTILINE)
# The placeholder each book's folder starts with.
_EMPTY = {"", "# Personal Notes"}
# A "why" such as "<your own sentence>": a template the user sent back unfilled.
_PLACEHOLDER = re.compile(r"<[^>]*>")


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


def anchor_comment(anchor: str) -> str:
    """The HTML comment that records where in the EPUB a quote or note was made."""
    anchor = anchor.strip()
    if "--" in anchor or "\n" in anchor:
        raise ValueError("an anchor cannot contain '--' or a line break")
    return f"<!-- anchor: {anchor} -->"


def format_quote(
    text: str,
    author: str,
    title: str,
    location: str,
    why: str,
    themes: list[str] | None = None,
    links: list[str] | None = None,
    said_by: str = "",
    anchor: str = "",
) -> str:
    """Return one quote in the four-part shape, without surrounding blank lines.

    `said_by` names the speaker when the book quotes someone else: the source line
    then reads "— Speaker, quoted in Author, *Title*". `anchor`, an EPUB CFI from
    the reading app, is kept as a trailing HTML comment.
    """
    text = text.strip().strip('"“”')
    if not text:
        raise ValueError("a quote needs its text")
    if not why.strip():
        raise ValueError("a quote needs a 'why': one line on why it mattered")
    if _PLACEHOLDER.search(why):
        raise ValueError("the 'why' is a placeholder; ask the user why the quote matters")
    source = f"— {author.strip()}, *{title.strip()}*"
    if said_by.strip():
        source = f"— {said_by.strip()}, quoted in {author.strip()}, *{title.strip()}*"
    if location.strip():
        source += f", {location.strip()}"
    quoted = "\n".join(f"> {line}" if line else ">" for line in f'"{text}"'.splitlines())
    tags = [f"#quote/{_slugify(t)}" for t in (themes or []) if _slugify(t)]
    link_parts = [link.strip() for link in (links or []) if link.strip()] + tags
    lines = [quoted, f"> {source}", "", f"- **Why:** {why.strip()}"]
    if link_parts:
        lines.append(f"- **Links:** {' · '.join(link_parts)}")
    if anchor.strip():
        lines.append(anchor_comment(anchor))
    return "\n".join(lines)


def format_note(text: str, location: str, today: str, passage: str = "",
                anchor: str = "") -> str:
    """Return one note in the heading-passage-text shape, without surrounding blank lines."""
    if not text.strip():
        raise ValueError("a note needs its text")
    heading = " · ".join(part for part in (location.strip(), today) if part)
    lines = [f"### {heading}", ""]
    if passage.strip():
        lines += [*(f"> {line}" if line else ">" for line in passage.strip().splitlines()), ""]
    lines.append(text.strip())
    if anchor.strip():
        lines += ["", anchor_comment(anchor)]
    return "\n".join(lines)


def _insert_in_section(note: str, section: re.Pattern, heading: str, block: str,
                       today: str) -> str:
    """Append `block` to the end of a level-2 section, adding the section if missing."""
    match = section.search(note)
    if match is None:
        footer = note.rfind("\n---\n")
        head, tail = (note[:footer], note[footer:]) if footer != -1 else (note, "\n")
        note = f"{head.rstrip()}\n\n{heading}\n{tail}"
        match = section.search(note)
    start = match.end()
    end_match = _SECTION_END.search(note, start)
    end = end_match.start() if end_match else len(note)
    body = note[start:end].rstrip()
    new_body = f"{body}\n\n{block}\n\n" if body else f"\n\n{block}\n\n"
    note = note[:start] + new_body + note[end:]
    return _LAST_UPDATED.sub(f"*Last Updated: {today}*", note)


def insert_quote(note: str, block: str, today: str) -> str:
    """Append `block` to the end of the note's quotes section, adding one if missing."""
    return _insert_in_section(note, _QUOTES_SECTION, QUOTES_HEADING, block, today)


def insert_note(note: str, block: str, today: str) -> str:
    """Append `block` to the end of the note's notes section, adding one if missing."""
    return _insert_in_section(note, _NOTES_SECTION, NOTES_HEADING, block, today)


def add_book_quote(
    book_path: Path,
    title: str,
    author: str,
    text: str,
    why: str,
    location: str = "",
    themes: list[str] | None = None,
    links: list[str] | None = None,
    said_by: str = "",
    anchor: str = "",
    today: str | None = None,
) -> dict:
    """Append a quote to a book's personal notes, creating them if they are empty.

    `created` is true only when the file did not exist. `replaced_placeholder` is
    true when the file held only the placeholder heading, which the notes replace.
    """
    today = today or date.today().isoformat()
    block = format_quote(text, author, title, location, why, themes, links, said_by, anchor)
    return _append(book_path, title, block, insert_quote, today)


def add_book_note(
    book_path: Path,
    title: str,
    text: str,
    location: str = "",
    passage: str = "",
    anchor: str = "",
    today: str | None = None,
) -> dict:
    """Append a note to a book's personal notes, creating them if they are empty."""
    today = today or date.today().isoformat()
    block = format_note(text, location, today, passage, anchor)
    return _append(book_path, title, block, insert_note, today)


def _append(book_path: Path, title: str, block: str, insert, today: str) -> dict:
    """Insert `block` into a book's personal notes; see `add_book_quote` for the flags."""
    path = notes_path(book_path)
    created = not path.is_file()
    existing = "" if created else path.read_text()
    empty = existing.strip() in _EMPTY
    note = new_notes(title, today) if empty else existing
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(insert(note, block, today))
    return {
        "path": f"{book_path.name}/{NOTES_FILE.as_posix()}",
        "created": created,
        "replaced_placeholder": empty and not created,
    }


def write_personal_notes(book_path: Path, content: str) -> dict:
    """Replace a book's personal notes with `content`."""
    if not content.strip():
        raise ValueError("refusing to write empty personal notes")
    path = notes_path(book_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content if content.endswith("\n") else content + "\n")
    return {"path": f"{book_path.name}/{NOTES_FILE.as_posix()}"}


# ---- Reading back -----------------------------------------------------------


def _section_body(note: str, section: re.Pattern) -> str:
    match = section.search(note)
    if match is None:
        return ""
    end_match = _SECTION_END.search(note, match.end())
    return note[match.end(): end_match.start() if end_match else len(note)]


def _pop_anchor(block: str) -> tuple[str, str]:
    match = _ANCHOR.search(block)
    if match is None:
        return block, ""
    return (block[: match.start()] + block[match.end():]).strip(), match.group(1).strip()


def _parse_quotes(body: str) -> list[dict]:
    quotes = []
    # A quote starts at a `> "` line that follows a blank line or the section start.
    for chunk in re.split(r"\n(?=> [\"“])", "\n" + body):
        chunk, anchor = _pop_anchor(chunk.strip())
        if not chunk.startswith(">"):
            continue
        quoted = [line[1:].strip() for line in chunk.splitlines() if line.startswith(">")]
        source = next((q for q in quoted if q.startswith("—")), "")
        text = " ".join(q for q in quoted if q and not q.startswith("—")).strip()
        # Older hand-written quotes carry a remark after the closing mark:
        # `"The words." — on cold exposure`.
        remark = ""
        inline = re.fullmatch(r'["“](.+?)["”]\s*(?:—\s*(.*))?', text)
        if inline:
            text, remark = inline.group(1), (inline.group(2) or "").strip()
        text = text.strip('"“”')
        # "— Author, *Title*, location": the location is whatever follows the title.
        loc = re.search(r"\*[^*]+\*,\s*(.+)$", source)
        why = re.search(r"^- \*\*Why:\*\*\s*(.+)$", chunk, re.MULTILINE)
        quotes.append({
            "kind": "quote",
            "text": text,
            "location": loc.group(1).strip() if loc else "",
            "why": why.group(1).strip() if why else remark,
            "anchor": anchor,
        })
    return quotes


def _parse_notes(body: str) -> list[dict]:
    notes = []
    for chunk in re.split(r"^### ", body, flags=re.MULTILINE)[1:]:
        heading, _, rest = chunk.partition("\n")
        rest, anchor = _pop_anchor(rest.strip())
        passage = "\n".join(line[1:].strip() for line in rest.splitlines() if line.startswith(">"))
        text = "\n".join(line for line in rest.splitlines() if not line.startswith(">")).strip()
        parts = [p.strip() for p in heading.split(" · ")]
        dated = bool(parts) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", parts[-1]) is not None
        notes.append({
            "kind": "note",
            "text": text,
            "passage": passage,
            "location": " · ".join(parts[:-1] if dated else parts),
            "date": parts[-1] if dated else "",
            "anchor": anchor,
        })
    return notes


def parse_annotations(note: str) -> dict:
    """The quotes and notes in a book's personal notes, as structured data."""
    return {
        "quotes": _parse_quotes(_section_body(note, _QUOTES_SECTION)),
        "notes": _parse_notes(_section_body(note, _NOTES_SECTION)),
    }


# ---- Highlights ---------------------------------------------------------------

_HIGHLIGHT_KEYS = {"cfi", "text"}


def read_highlights(book_path: Path) -> list[dict]:
    path = book_path / HIGHLIGHTS_FILE
    if not path.is_file():
        return []
    data = json.loads(path.read_text())
    return data.get("highlights", []) if isinstance(data, dict) else []


def write_highlights(book_path: Path, highlights: list[dict]) -> dict:
    """Replace a book's `personal-notes/highlights.json`. Each needs at least `cfi` and `text`."""
    for i, h in enumerate(highlights):
        missing = _HIGHLIGHT_KEYS - set(h) if isinstance(h, dict) else _HIGHLIGHT_KEYS
        if missing:
            raise ValueError(f"highlight {i} is missing {sorted(missing)}")
    path = book_path / HIGHLIGHTS_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": 1, "highlights": highlights}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    return {"path": f"{book_path.name}/{HIGHLIGHTS_FILE.as_posix()}", "count": len(highlights)}
