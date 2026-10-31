"""Tests for the personal-notes write tools and the explicit save."""

import subprocess

import pytest

from book_library_mcp.git_ops import list_pending_changes, save_changes
from book_library_mcp.notes import (
    add_book_note,
    add_book_quote,
    format_quote,
    parse_annotations,
    read_highlights,
    write_highlights,
    write_personal_notes,
)


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


def test_format_quote_refuses_a_placeholder_why():
    with pytest.raises(ValueError, match="placeholder"):
        format_quote("text", "A", "T", "", "<your own sentence>")


def test_format_quote_names_the_speaker_first():
    block = format_quote("Make a love letter.", "Nancy Duarte", "Resonate", "ch. 3",
                         "A reminder.", said_by="Ken Haemer")
    assert block.splitlines()[1] == "> — Ken Haemer, quoted in Nancy Duarte, *Resonate*, ch. 3"


def test_add_book_quote_creates_a_missing_file(temp_library):
    book = temp_library / "sample-book"
    (book / "personal-notes/README.md").unlink()
    res = add_book_quote(book, title="Sample Book", author="Jane Doe", text="New.",
                         why="Because.", today="2026-10-27")
    assert res["created"] is True and res["replaced_placeholder"] is False


def test_add_book_quote_replaces_the_empty_placeholder(temp_library):
    book = temp_library / "sample-book"
    (book / "personal-notes/README.md").write_text("# Personal Notes\n")
    res = add_book_quote(book, title="Sample Book", author="Jane Doe", text="Practise.",
                         why="It is the point.", today="2026-10-22")
    assert res == {"path": "sample-book/personal-notes/README.md", "created": False,
                   "replaced_placeholder": True}
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
    assert res["created"] is False and res["replaced_placeholder"] is False
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


def test_format_quote_records_the_anchor_last():
    block = format_quote("Time is finite.", "O B", "F T W", "ch. 1", "Premise.",
                         anchor="epubcfi(/6/4!/4/2,/1:0,/1:15)")
    assert block.endswith("\n<!-- anchor: epubcfi(/6/4!/4/2,/1:0,/1:15) -->")


def test_anchor_rejects_a_comment_terminator():
    with pytest.raises(ValueError):
        format_quote("t", "A", "T", "", "w", anchor="x -->")


def test_add_book_note_adds_a_notes_section_before_the_footer(temp_library):
    book = temp_library / "sample-book"
    (book / "personal-notes/README.md").write_text("# Personal Notes\n")
    add_book_quote(book, title="Sample Book", author="Jane Doe", text="One.", why="First.",
                   today="2026-10-31")
    add_book_note(book, title="Sample Book", text="My own words.", location="ch. 2",
                  passage="The passage.", anchor="epubcfi(/6/8!/4/2)", today="2026-10-31")
    note = (book / "personal-notes/README.md").read_text()
    assert "### ch. 2 · 2026-10-31\n\n> The passage.\n\nMy own words.\n\n<!-- anchor:" in note
    assert note.index("Quotes & Highlights") < note.index("## 📝 Notes") < note.index("\n---\n")


def test_parse_annotations_reads_back_what_was_written(temp_library):
    book = temp_library / "sample-book"
    add_book_quote(book, title="Sample Book", author="Jane Doe", text="One line.",
                   why="It mattered.", location="ch. 1, p. 4", anchor="epubcfi(/6/4!/4)",
                   today="2026-10-31")
    add_book_quote(book, title="Sample Book", author="Jane Doe", text="No anchor.",
                   why="Made in chat.", today="2026-10-31")
    add_book_note(book, title="Sample Book", text="Thought.", location="ch. 2",
                  passage="Passage.", anchor="epubcfi(/6/8!/4)", today="2026-10-31")
    parsed = parse_annotations((book / "personal-notes/README.md").read_text())
    assert parsed["quotes"] == [
        {"kind": "quote", "text": "One line.", "location": "ch. 1, p. 4",
         "why": "It mattered.", "anchor": "epubcfi(/6/4!/4)"},
        {"kind": "quote", "text": "No anchor.", "location": "", "why": "Made in chat.",
         "anchor": ""},
    ]
    assert parsed["notes"] == [
        {"kind": "note", "text": "Thought.", "passage": "Passage.", "location": "ch. 2",
         "date": "2026-10-31", "anchor": "epubcfi(/6/8!/4)"},
    ]


def test_highlights_round_trip(temp_library):
    book = temp_library / "sample-book"
    assert read_highlights(book) == []
    res = write_highlights(book, [{"cfi": "epubcfi(/6/4!/4)", "text": "x", "color": "yellow"}])
    assert res == {"path": "sample-book/personal-notes/highlights.json", "count": 1}
    assert read_highlights(book) == [{"cfi": "epubcfi(/6/4!/4)", "text": "x", "color": "yellow"}]


def test_write_highlights_requires_cfi_and_text(temp_library):
    with pytest.raises(ValueError, match="cfi"):
        write_highlights(temp_library / "sample-book", [{"text": "x"}])


def test_save_with_paths_leaves_other_drafts_on_disk(temp_git_library):
    lib = temp_git_library
    (lib / "sample-book/personal-notes/README.md").write_text("# Mine\n")
    (lib / "sample-book/action-items.md").write_text("# Someone else's draft\n")
    result = save_changes(lib, message="notes", paths=["sample-book/personal-notes"])
    assert result.committed and result.pushed
    assert [p["path"] for p in list_pending_changes(lib)] == ["sample-book/action-items.md"]


def test_parse_annotations_reads_hand_written_quotes():
    note = (
        "## Quotes & Highlights\n\n"
        '> "Hard is the point." — on cold exposure\n\n'
        '> "Sunlight first."\n\n---\n'
    )
    quotes = parse_annotations(note)["quotes"]
    assert [(q["text"], q["why"]) for q in quotes] == [
        ("Hard is the point.", "on cold exposure"), ("Sunlight first.", "")
    ]
