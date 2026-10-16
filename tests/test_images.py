"""Tests for infographic lookup and image preparation."""

import io

from PIL import Image as PILImage

from book_library_mcp.images import MAX_EDGE, find_book_infographic, prepare_image


def test_prepare_passes_small_jpeg_through_despite_png_name(tmp_path):
    path = tmp_path / "x.png"
    PILImage.new("RGB", (40, 30)).save(path, format="JPEG")
    data, fmt = prepare_image(path)
    assert fmt == "jpeg"
    assert data == path.read_bytes()


def test_prepare_converts_tiff_to_jpeg(tmp_path):
    path = tmp_path / "x.png"
    PILImage.new("RGB", (40, 30)).save(path, format="TIFF")
    data, fmt = prepare_image(path)
    assert fmt == "jpeg"
    assert PILImage.open(io.BytesIO(data)).format == "JPEG"


def test_prepare_shrinks_large_image(tmp_path):
    path = tmp_path / "x.png"
    PILImage.new("RGB", (3000, 1500)).save(path, format="PNG")
    data, _ = prepare_image(path)
    assert max(PILImage.open(io.BytesIO(data)).size) == MAX_EDGE


def test_find_book_infographic_prefers_requested_source(tmp_path):
    for source in ("chatgpt", "gemini"):
        (tmp_path / f"b_book_infographic_{source}.png").write_bytes(b"x")
    assert find_book_infographic(tmp_path, "b", "gemini").name.endswith("_gemini.png")
    assert find_book_infographic(tmp_path, "b", None).name.endswith("_chatgpt.png")
