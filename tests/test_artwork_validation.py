from __future__ import annotations

from pathlib import Path

import pytest

from fluxtuner.core.artwork_validation import detect_artwork_type

FIXTURES = Path(__file__).parent / "fixtures" / "artwork"


def test_rejects_non_image_content() -> None:
    assert detect_artwork_type(b"<svg xmlns='http://www.w3.org/2000/svg'></svg>") is None
    assert detect_artwork_type(b"<html>not an image</html>") is None
    assert detect_artwork_type(b"") is None


def test_rejects_truncated_png() -> None:
    assert detect_artwork_type(b"\x89PNG\r\n\x1a\n") is None


def test_rejects_oversized_payload() -> None:
    assert detect_artwork_type(b"x" * (2 * 1024 * 1024 + 1)) is None


@pytest.mark.parametrize(
    ("filename", "mime"),
    [("sample.png", "image/png"), ("sample.jpg", "image/jpeg"), ("sample.webp", "image/webp")],
)
def test_recognizes_real_image_samples(filename: str, mime: str) -> None:
    assert detect_artwork_type((FIXTURES / filename).read_bytes()) == mime


@pytest.mark.parametrize("filename", ["sample.png", "sample.jpg", "sample.webp"])
def test_rejects_truncated_real_samples(filename: str) -> None:
    payload = (FIXTURES / filename).read_bytes()
    assert detect_artwork_type(payload[: len(payload) // 2]) is None


def test_rejects_png_crc_tampering() -> None:
    payload = bytearray((FIXTURES / "sample.png").read_bytes())
    payload[20] ^= 1
    assert detect_artwork_type(bytes(payload)) is None


def test_rejects_bogus_jpeg_markers() -> None:
    payload = b"\xff\xd8\xff" + b"x" * 20 + b"\xff\xd9"
    assert detect_artwork_type(payload) is None


def test_rejects_bogus_webp_chunk() -> None:
    payload = b"RIFF" + (17).to_bytes(4, "little") + b"WEBP" + b"x" * 13
    assert detect_artwork_type(payload) is None
