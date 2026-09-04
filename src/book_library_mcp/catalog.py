"""Catalog: loads book metadata from a library root."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class Book:
    """One book's metadata, plus the path to its directory."""

    slug: str
    title: str
    author: str
    path: Path
    metadata: dict[str, Any] = field(default_factory=dict)


class Catalog:
    """In-memory map of slug → Book."""

    def __init__(self, books: list[Book]) -> None:
        self._books = {b.slug: b for b in books}

    def __len__(self) -> int:
        return len(self._books)

    def __iter__(self):
        return iter(self._books.values())

    def get(self, slug: str) -> Book | None:
        return self._books.get(slug)

    def all(self) -> list[Book]:
        return list(self._books.values())


def load_catalog(library_root: Path) -> Catalog:
    """Walk library_root, parse every metadata.yaml, return a Catalog."""
    books: list[Book] = []
    for metadata_path in sorted(library_root.glob("*/metadata.yaml")):
        book_dir = metadata_path.parent
        with metadata_path.open() as fh:
            data = yaml.safe_load(fh) or {}
        slug = data.get("source_folder") or book_dir.name
        title = data.get("title", slug)
        author = data.get("author", "Unknown")
        books.append(Book(slug=slug, title=title, author=author, path=book_dir, metadata=data))
    return Catalog(books)
