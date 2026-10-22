"""End-to-end tests of the FastMCP tool surface (in-process)."""

import json

import pytest

from book_library_mcp.server import build_server


@pytest.fixture
def server(fixture_library, monkeypatch):
    monkeypatch.setenv("BOOK_LIBRARY_ROOT", str(fixture_library))
    return build_server()


@pytest.mark.asyncio
async def test_list_books_returns_one(server):
    result = await server.call_tool("list_books", {})
    books = _extract(result)
    assert len(books) == 1
    assert books[0]["slug"] == "sample-book"
    assert books[0]["title"].startswith("Sample Book")


@pytest.mark.asyncio
async def test_search_books_finds_phrase(server):
    result = await server.call_tool("search_books", {"query": "deep work"})
    hits = _extract(result)
    assert any(h["slug"] == "sample-book" for h in hits)


@pytest.mark.asyncio
async def test_get_book_metadata_round_trip(server):
    result = await server.call_tool("get_book_metadata", {"slug": "sample-book"})
    meta = _extract(result)
    assert meta["author"] == "Jane Doe"
    assert "testing" in meta["categories"]


@pytest.mark.asyncio
async def test_get_chapter_summary_returns_text(server):
    result = await server.call_tool(
        "get_chapter_summary", {"slug": "sample-book", "chapter": "chapter-01-intro"}
    )
    text = _extract(result)
    assert "Introduction" in text
    assert "deep work" in text.lower()


@pytest.mark.asyncio
async def test_get_action_items_returns_text(server):
    result = await server.call_tool("get_action_items", {"slug": "sample-book"})
    text = _extract(result)
    assert "deep work" in text.lower()


@pytest.mark.asyncio
async def test_get_personal_notes_returns_text(server):
    result = await server.call_tool("get_personal_notes", {"slug": "sample-book"})
    text = _extract(result)
    assert "deliberate practice" in text.lower()


@pytest.mark.asyncio
async def test_get_book_infographic_text_returns_text(server):
    result = await server.call_tool(
        "get_book_infographic_text", {"slug": "sample-book"}
    )
    text = _extract(result)
    assert "INFOGRAPHIC" in text


@pytest.mark.asyncio
async def test_get_book_metadata_unknown_slug_errors(server):
    with pytest.raises(Exception) as exc_info:
        await server.call_tool("get_book_metadata", {"slug": "nonexistent"})
    assert "nonexistent" in str(exc_info.value).lower() or "not found" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_list_infographics_skips_debug_images(server):
    result = await server.call_tool("list_infographics", {"slug": "sample-book"})
    listing = _extract(result)
    assert listing == {"book": True, "chapters": ["chapter-01-intro"]}


@pytest.mark.asyncio
async def test_get_infographic_returns_book_image(server):
    content = _content(await server.call_tool("get_infographic", {"slug": "sample-book"}))
    assert content.type == "image"
    assert content.mimeType == "image/jpeg"


@pytest.mark.asyncio
async def test_get_infographic_returns_chapter_image(server):
    result = await server.call_tool(
        "get_infographic", {"slug": "sample-book", "chapter": "chapter-01-intro"}
    )
    content = _content(result)
    assert content.type == "image"
    assert content.mimeType == "image/png"


@pytest.mark.asyncio
async def test_get_infographic_unknown_chapter_errors(server):
    with pytest.raises(Exception, match="no infographic"):
        await server.call_tool(
            "get_infographic", {"slug": "sample-book", "chapter": "chapter-02-broken"}
        )


def _content(call_tool_result):
    """Return the single content item of a call_tool result."""
    if isinstance(call_tool_result, tuple):
        call_tool_result = call_tool_result[0]
    (item,) = call_tool_result
    return item


def _extract(call_tool_result):
    """Pull the payload out of a FastMCP call_tool return.

    FastMCP 1.27 returns either:
    - a (content_list, structured_dict) tuple for tools returning lists/primitives
      (primitives are wrapped in {"result": value}, which we unwrap), or
    - just a content_list of TextContent for tools returning dicts (the JSON payload
      lives in the text content; we json.loads it).
    """
    if isinstance(call_tool_result, tuple) and len(call_tool_result) == 2:
        content, structured = call_tool_result
        if structured is not None:
            if isinstance(structured, dict) and set(structured.keys()) == {"result"}:
                return structured["result"]
            return structured
        return _from_content(content)
    if isinstance(call_tool_result, list):
        return _from_content(call_tool_result)
    return call_tool_result


def _from_content(content):
    for item in content or []:
        if getattr(item, "type", None) == "text":
            text = item.text
            try:
                return json.loads(text)
            except (json.JSONDecodeError, TypeError):
                return text
    return None


@pytest.fixture
def write_server(temp_library, monkeypatch):
    monkeypatch.setenv("BOOK_LIBRARY_ROOT", str(temp_library))
    return build_server()


@pytest.mark.asyncio
async def test_add_book_quote_uses_catalog_title_and_author(write_server, temp_library):
    result = await write_server.call_tool(
        "add_book_quote",
        {"slug": "sample-book", "text": "Practise daily.", "why": "The habit.",
         "location": "ch. 1", "themes": ["practice"]},
    )
    assert _extract(result) == {"path": "sample-book/personal-notes/README.md", "created": False}
    note = (temp_library / "sample-book/personal-notes/README.md").read_text()
    assert "> — Jane Doe, *Sample Book: A Test Fixture*, ch. 1" in note
    assert "#quote/practice" in note


@pytest.mark.asyncio
async def test_add_book_quote_unknown_book_errors(write_server):
    with pytest.raises(Exception, match="book not found"):
        await write_server.call_tool(
            "add_book_quote", {"slug": "no-such-book", "text": "x", "why": "y"}
        )
