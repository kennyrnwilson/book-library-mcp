# book-library-mcp

MCP server that exposes a local book library to Claude clients.

The server reads a directory of books — each in its own folder with a
`metadata.yaml`, chapter summaries, action items, and personal notes — and
exposes them via MCP tools. The book content is private; this repo contains only
the server code.

## Tools

| Tool | Description |
|------|-------------|
| `list_books` | List all books: slug, title, author |
| `search_books` | Full-text search across all book content |
| `get_book_metadata` | Full metadata.yaml for one book |
| `get_chapter_summary` | One chapter summary markdown |
| `get_action_items` | action-items.md for one book |
| `get_personal_notes` | Aggregated personal-notes/ for one book |
| `get_book_infographic_text` | Infographic text file for one book |
| `list_infographics` | Whether a book has a whole-book infographic, and which chapters have one |
| `get_infographic` | The whole-book infographic, or one chapter's, as an image |
| `add_book_quote` | Append a quote to one book's `personal-notes/README.md`: the quote, a source line, a "Why" line, links and `#quote/<theme>` tags |
| `write_personal_notes` | Replace one book's `personal-notes/README.md` |
| `list_pending_book_changes` | Uncommitted changes in the library (parsed `git status`) |
| `save_book_changes` | Stage, commit and push `main` |

### Explicit-save model

The write tools only touch disk, and only `<book>/personal-notes/README.md`. They
never commit. `save_book_changes` stages, commits, rebases onto `origin/main` and
pushes. The LLM must only call it when the user explicitly approves ("save it",
"commit that", "looks good"). Saving needs a clone the server can write to, and a
deploy key with write access.

## Self-hosting

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- [ripgrep](https://github.com/BurntSushi/ripgrep) (`rg`) for `search_books`

### Expected library layout

```
book-library/
├── some-book/
│   ├── metadata.yaml          # title, author, source_folder, ...
│   ├── action-items.md
│   ├── chapter-summaries/
│   │   └── chapter-01-intro.md
│   └── personal-notes/
│       └── notes.md
└── another-book/
    └── ...
```

`metadata.yaml` minimum fields:

```yaml
title: Some Book
author: Jane Doe
source_folder: some-book   # slug; defaults to directory name if absent
```

### Install and run

```bash
git clone https://github.com/kennyrnwilson/book-library-mcp.git
cd book-library-mcp
uv sync
```

**stdio (Claude Desktop):**

```bash
BOOK_LIBRARY_ROOT=/path/to/book-library uv run python -m book_library_mcp
```

**Streamable HTTP (remote/VM):**

```bash
BOOK_LIBRARY_ROOT=/path/to/book-library uv run python -m book_library_mcp \
    --transport streamable-http --host 127.0.0.1 --port 5102
```

### Claude Desktop config (stdio)

```json
{
  "mcpServers": {
    "book-library": {
      "command": "uv",
      "args": ["run", "python", "-m", "book_library_mcp"],
      "cwd": "/path/to/book-library-mcp",
      "env": {
        "BOOK_LIBRARY_ROOT": "/path/to/book-library"
      }
    }
  }
}
```

### Self-test

```bash
BOOK_LIBRARY_ROOT=/path/to/book-library uv run python -m book_library_mcp --selftest
```

## Development

```bash
uv sync --extra dev
uv run pytest
uv run ruff check src/
```
