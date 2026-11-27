"""Conservative artwork format identification without external decoders."""

from __future__ import annotations

import struct
import zlib

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MAX_ARTWORK_BYTES = 2 * 1024 * 1024
MAX_DIMENSION = 4096


def _valid_dimensions(width: int, height: int) -> bool:
    return 0 < width <= MAX_DIMENSION and 0 < height <= MAX_DIMENSION


def _valid_png_header(payload: bytes) -> bool:
    width, height = struct.unpack(">II", payload[:8])
    bit_depth, color_type, compression, filtering, interlace = payload[8:]
    supported_depths = {
        0: {1, 2, 4, 8, 16},
        2: {8, 16},
        3: {1, 2, 4, 8},
        4: {8, 16},
        6: {8, 16},
    }
    return (
        _valid_dimensions(width, height)
        and bit_depth in supported_depths.get(color_type, set())
        and compression == 0
        and filtering == 0
        and interlace in {0, 1}
    )


def _is_png(data: bytes) -> bool:
    if not data.startswith(PNG_SIGNATURE):
        return False
    position = len(PNG_SIGNATURE)
    saw_ihdr = False
    saw_idat = False
    while position + 12 <= len(data):
        length = int.from_bytes(data[position : position + 4], "big")
        if length > len(data) - position - 12:
            return False
        kind = data[position + 4 : position + 8]
        payload = data[position + 8 : position + 8 + length]
        checksum = int.from_bytes(data[position + 8 + length : position + 12 + length], "big")
        if zlib.crc32(kind + payload) & 0xFFFFFFFF != checksum:
            return False
        if position == len(PNG_SIGNATURE):
            if kind != b"IHDR" or length != 13:
                return False
            if not _valid_png_header(payload):
                return False
            saw_ihdr = True
        elif kind == b"IHDR":
            return False
        if kind == b"IDAT":
            saw_idat = True
        position += length + 12
        if kind == b"IEND":
            return bool(saw_ihdr and saw_idat and length == 0 and position == len(data))
    return False


_JPEG_FRAMES = frozenset({0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB})


def _valid_jpeg_frame(data: bytes, position: int, length: int) -> bool:
    if length < 7:
        return False
    height = int.from_bytes(data[position + 3 : position + 5], "big")
    width = int.from_bytes(data[position + 5 : position + 7], "big")
    return _valid_dimensions(width, height)


def _valid_jpeg_scan(data: bytes, position: int) -> bool:
    if position + 2 > len(data):
        return False
    length = int.from_bytes(data[position : position + 2], "big")
    return length >= 6 and position + length < len(data) - 2


def _is_jpeg(data: bytes) -> bool:
    if not data.startswith(b"\xff\xd8\xff") or not data.endswith(b"\xff\xd9"):
        return False
    position = 2
    saw_frame = False
    while position + 4 <= len(data):
        if data[position] != 0xFF:
            return False
        while position < len(data) and data[position] == 0xFF:
            position += 1
        if position >= len(data):
            return False
        marker = data[position]
        position += 1
        if marker == 0xDA:  # Start of scan: entropy coding is decoder-owned.
            return saw_frame and _valid_jpeg_scan(data, position)
        if marker in {0x00, 0x01, 0xD8, 0xD9} or 0xD0 <= marker <= 0xD7:
            return False
        if position + 2 > len(data):
            return False
        length = int.from_bytes(data[position : position + 2], "big")
        if length < 2 or position + length > len(data):
            return False
        if marker in _JPEG_FRAMES:
            if not _valid_jpeg_frame(data, position, length):
                return False
            saw_frame = True
        position += length
    return False


def _is_webp(data: bytes) -> bool:
    if data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        return False
    if int.from_bytes(data[4:8], "little") != len(data) - 8 or len(data) < 30:
        return False
    kind = data[12:16]
    length = int.from_bytes(data[16:20], "little")
    if 20 + length + (length % 2) > len(data):
        return False
    payload = data[20 : 20 + length]
    if kind == b"VP8 ":
        if len(payload) < 10 or payload[3:6] != b"\x9d\x01\x2a":
            return False
        width = int.from_bytes(payload[6:8], "little") & 0x3FFF
        height = int.from_bytes(payload[8:10], "little") & 0x3FFF
    elif kind == b"VP8L":
        if len(payload) < 5 or payload[0] != 0x2F:
            return False
        dimensions = int.from_bytes(payload[1:5], "little")
        width = (dimensions & 0x3FFF) + 1
        height = ((dimensions >> 14) & 0x3FFF) + 1
    elif kind == b"VP8X":
        if len(payload) < 10:
            return False
        width = int.from_bytes(payload[4:7], "little") + 1
        height = int.from_bytes(payload[7:10], "little") + 1
    else:
        return False
    return _valid_dimensions(width, height)


def detect_artwork_type(data: bytes) -> str | None:
    """Inspect bounded PNG/JPEG/WebP framing and dimensions, without decoding pixels.

    This cannot guarantee that compressed pixel data decodes successfully.
    """
    if not isinstance(data, bytes) or not 24 <= len(data) <= MAX_ARTWORK_BYTES:
        return None
    if _is_png(data):
        return "image/png"
    if _is_jpeg(data):
        return "image/jpeg"
    if _is_webp(data):
        return "image/webp"
    return None
