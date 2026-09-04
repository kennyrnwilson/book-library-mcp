"""Entry point: `python -m book_library_mcp` (stdio server) or `--selftest`."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import traceback
from typing import Any

from book_library_mcp.server import build_server


def _coerce(call_tool_result: Any) -> Any:
    """Unwrap a FastMCP call_tool return into the bare payload.

    FastMCP 1.27 returns either a (content, structured) tuple — primitives are
    wrapped in {"result": value} — or a bare content list whose text item is the
    JSON-encoded payload.
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


def _from_content(content: Any) -> Any:
    for item in content or []:
        if getattr(item, "type", None) == "text":
            try:
                return json.loads(item.text)
            except (json.JSONDecodeError, TypeError):
                return item.text
    return None


def _selftest() -> int:
    server = build_server()

    async def run() -> int:
        try:
            books = _coerce(await server.call_tool("list_books", {}))
            slugs = [b["slug"] for b in books]
            if not slugs:
                print("selftest FAIL: list_books returned no books", file=sys.stderr)
                return 1
            slug = slugs[0]
            await server.call_tool("get_book_metadata", {"slug": slug})
            await server.call_tool("search_books", {"query": "the"})
            print(f"selftest OK: {len(slugs)} books, sampled slug={slug!r}")
            return 0
        except Exception:
            print("selftest FAIL:", file=sys.stderr)
            traceback.print_exc()
            return 1

    return asyncio.run(run())


def main() -> int:
    parser = argparse.ArgumentParser(prog="book-library-mcp")
    parser.add_argument(
        "--selftest",
        action="store_true",
        help="Instantiate the server, call core tools, exit 0/1.",
    )
    parser.add_argument(
        "--transport",
        default="stdio",
        choices=["stdio", "streamable-http"],
        help="Transport to use (default: stdio).",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind when using streamable-http transport (default: 127.0.0.1).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5102,
        help="Port to bind when using streamable-http transport (default: 5102).",
    )
    args = parser.parse_args()

    if args.selftest:
        return _selftest()

    server = build_server(host=args.host, port=args.port)
    if args.transport == "streamable-http":
        server.run(transport="streamable-http")
    else:
        server.run()  # stdio default
    return 0


if __name__ == "__main__":
    sys.exit(main())
