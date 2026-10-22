"""Tests for the personal-notes write tools and the explicit save."""

import subprocess

import pytest

from book_library_mcp.git_ops import list_pending_changes, save_changes
from book_library_mcp.notes import add_book_quote, format_quote, write_personal_notes


def test_format_quote_has_four_parts():
    block = format_quote("Time is finite.", "Oliver Burkeman", "Four Thousand Weeks",
                         "ch. 1", "The premise of the book.", themes=["Time"])
    assert block == (
        '> "Time is finite."\n'
        "> — Oliver Burkeman, *Four Thousand Weeks*, ch. 1\n"
        "\n"
        "- **Why:** The premise of the book.\n"
        "- **Links:** #quote/time"
    )


def test_format_quote_requires_why():
    with pytest.raises(ValueError):
        format_quote("text", "A", "T", "", "")


def test_add_book_quote_replaces_the_empty_placeholder(temp_library):
    book = temp_library / "sample-book"
    (book / "personal-notes/README.md").write_text("# Personal Notes\n")
    res = add_book_quote(book, title="Sample Book", author="Jane Doe", text="Practise.",
                         why="It is the point.", today="2026-10-22")
    assert res == {"path": "sample-book/personal-notes/README.md", "created": True}
    note = (book / "personal-notes/README.md").read_text()
    assert note.startswith("# Sample Book: personal notes\n")
    assert "← [Back to Sample Book](../README.md)" in note
    assert note.index("Quotes & Highlights") < note.index('"Practise."') < note.index("---")
    assert "*Last Updated: 2026-10-22*" in note


def test_add_book_quote_keeps_existing_notes(temp_library):
    book = temp_library / "sample-book"
    res = add_book_quote(book, title="Sample Book", author="Jane Doe", text="One.",
                         why="First.", today="2026-10-22")
    add_book_quote(book, title="Sample Book", author="Jane Doe", text="Two.", why="Second.")
    assert res["created"] is False
    note = (book / "personal-notes/README.md").read_text()
    assert "deliberate practice scheduling" in note
    assert note.count("Quotes & Highlights") == 1
    assert note.index('"One."') < note.index('"Two."')


def test_write_personal_notes_replaces_the_file(temp_library):
    book = temp_library / "sample-book"
    res = write_personal_notes(book, "# New\n\nText.")
    assert res == {"path": "sample-book/personal-notes/README.md"}
    assert (book / "personal-notes/README.md").read_text() == "# New\n\nText.\n"


def test_write_personal_notes_refuses_empty(temp_library):
    with pytest.raises(ValueError):
        write_personal_notes(temp_library / "sample-book", "  \n")


def test_save_changes_commits_and_pushes(temp_git_library):
    book = temp_git_library / "sample-book"
    add_book_quote(book, title="Sample Book", author="Jane Doe", text="Saved.", why="Test.")
    assert list_pending_changes(temp_git_library) == [
        {"status": " M", "path": "sample-book/personal-notes/README.md"}
    ]
    result = save_changes(temp_git_library)
    assert result.committed and result.pushed
    assert result.message == "notes: sample-book/personal-notes/README.md"
    assert list_pending_changes(temp_git_library) == []
    origin_log = subprocess.run(
        ["git", "-C", str(temp_git_library.parent / "origin.git"), "log", "--oneline", "-1"],
        capture_output=True, text=True, check=True,
    ).stdout
    assert "notes: sample-book" in origin_log


def test_save_changes_with_nothing_to_save(temp_git_library):
    result = save_changes(temp_git_library)
    assert not result.committed and not result.pushed
