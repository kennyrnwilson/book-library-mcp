"""Infographic images: find them on disk and prepare them for an MCP client."""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image as PILImage

# Claude scales any image down to this long edge, so sending more is waste.
MAX_EDGE = 1568
# The API rejects an image over 5 MB once base64-encoded (4/3 larger).
MAX_BYTES = 3_750_000
# Formats a client accepts as they are. Anything else (the library has TIFFs)
# is re-encoded.
PASSTHROUGH = {"JPEG": "jpeg", "PNG": "png", "WEBP": "webp"}

# The pipeline writes these next to the real image when a render goes wrong.
_REJECT_SUFFIXES = (".debug.png", ".error.png")


def _usable(path: Path) -> bool:
    return path.is_file() and not path.name.endswith(_REJECT_SUFFIXES)


def find_book_infographic(book_dir: Path, slug: str, source: str | None) -> Path | None:
    """Return the whole-book infographic, preferring `source` if given.

    Older books have `<slug>_book_infographic_<chatgpt|gemini>.png`; newer ones
    have a single `<slug>_book_infographic.png`.
    """
    names = [f"{slug}_book_infographic_{source}.png"] if source else []
    names += [
        f"{slug}_book_infographic.png",
        f"{slug}_book_infographic_chatgpt.png",
        f"{slug}_book_infographic_gemini.png",
    ]
    for name in names:
        if _usable(book_dir / name):
            return book_dir / name
    return None


def find_chapter_infographic(book_dir: Path, chapter: str) -> Path | None:
    """Return `chapter-summaries/<chapter>_infographic.png`, if present."""
    path = book_dir / "chapter-summaries" / f"{chapter}_infographic.png"
    return path if _usable(path) else None


def list_chapter_infographics(book_dir: Path) -> list[str]:
    """Return the chapter names that have an infographic, in order."""
    chapters_dir = book_dir / "chapter-summaries"
    if not chapters_dir.is_dir():
        return []
    suffix = "_infographic.png"
    return sorted(
        p.name[: -len(suffix)] for p in chapters_dir.glob(f"*{suffix}") if _usable(p)
    )


def prepare_image(path: Path) -> tuple[bytes, str]:
    """Return (bytes, format) for a client, re-encoding only when needed.

    The file extension is not trusted: most `.png` infographics are JPEGs.
    """
    raw = path.read_bytes()
    with PILImage.open(io.BytesIO(raw)) as img:
        fmt = PASSTHROUGH.get(img.format or "")
        if fmt and max(img.size) <= MAX_EDGE and len(raw) <= MAX_BYTES:
            return raw, fmt
        img = img.convert("RGB")
        img.thumbnail((MAX_EDGE, MAX_EDGE))
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=90)
        return out.getvalue(), "jpeg"
