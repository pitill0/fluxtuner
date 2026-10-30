"""Serve verified static snapshots from bounded, immutable in-memory copies."""

from __future__ import annotations

import asyncio
import gzip
import hashlib
import json
import mimetypes
import stat
from collections import OrderedDict
from pathlib import Path

from starlette.responses import Response

from fluxtuner.web.static_builds import MANIFEST_NAME, verify_static_snapshot
from fluxtuner.web.static_compression import _accepts_gzip

IMMUTABLE = "public, max-age=31536000, immutable"
NO_STORE = "no-store"
MAX_BUILD_BYTES = 16 * 1024 * 1024
MAX_CACHED_BYTES = 64 * 1024 * 1024


def _safe_components(path: Path) -> bool:
    """Reject symlinks in all existing components of a storage path."""
    try:
        absolute = path.absolute()
        for component in (*reversed(absolute.parents), absolute):
            if stat.S_ISLNK(component.lstat().st_mode):
                return False
    except OSError:
        return False
    return True


def _load_build(root: Path, build_id: str) -> dict[str, bytes] | None:
    directory = root / build_id
    if not _safe_components(directory) or not verify_static_snapshot(directory, build_id):
        return None
    try:
        raw_manifest = (directory / MANIFEST_NAME).read_bytes()
        if hashlib.sha256(raw_manifest).hexdigest()[:16] != build_id:
            return None
        manifest = json.loads(raw_manifest)
        files = manifest["files"]
        if not isinstance(files, dict):
            return None
        result: dict[str, bytes] = {}
        size = 0
        for relative, expected in files.items():
            if not isinstance(relative, str) or not isinstance(expected, str):
                return None
            parts = relative.split("/")
            if any(part in ("", ".", "..") for part in parts) or "\\" in relative:
                return None
            candidate = directory.joinpath(*parts)
            if not _safe_components(candidate):
                return None
            data = candidate.read_bytes()
            if hashlib.sha256(data).hexdigest() != expected:
                return None
            size += len(data)
            if size > MAX_BUILD_BYTES:
                return None
            result[relative] = data
        return result
    except (OSError, ValueError, TypeError, KeyError):
        return None


def _etag_matches(header: str, etag: str) -> bool:
    return any(
        token.strip() == "*" or token.strip().removeprefix("W/") == etag.removeprefix("W/")
        for token in header.split(",")
    )


def _range_bytes(header: str, length: int) -> tuple[int, int] | None:
    if not header.startswith("bytes=") or "," in header:
        return None
    start_text, separator, end_text = header[6:].partition("-")
    if not separator or not (start_text or end_text):
        return None
    try:
        if start_text:
            first = int(start_text)
            last = int(end_text) if end_text else length - 1
        else:
            suffix = int(end_text)
            first = max(0, length - suffix)
            last = length - 1
        if first < 0 or last < first or first >= length or (not start_text and suffix == 0):
            return None
        return first, min(last, length - 1)
    except ValueError:
        return None


class StaticBuildHTTP:
    """Serve immutable bytes; never reopen a cached build during an HTTP response."""

    def __init__(self, root: Path) -> None:
        self.root = root.absolute()
        self._cache: OrderedDict[str, dict[str, bytes]] = OrderedDict()
        self._cached_bytes = 0
        self._lock = asyncio.Lock()

    async def _build(self, build_id: str) -> dict[str, bytes] | None:
        async with self._lock:
            cached = self._cache.get(build_id)
            if cached is not None:
                self._cache.move_to_end(build_id)
                return cached
            loaded = await asyncio.to_thread(_load_build, self.root, build_id)
            if loaded is None:
                return None
            size = sum(map(len, loaded.values()))
            while self._cache and self._cached_bytes + size > MAX_CACHED_BYTES:
                _old_id, old = self._cache.popitem(last=False)
                self._cached_bytes -= sum(map(len, old.values()))
            self._cache[build_id] = loaded
            self._cached_bytes += size
            return loaded

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            return
        method = scope.get("method", "GET")
        if method not in ("GET", "HEAD"):
            await Response(
                status_code=405, headers={"Allow": "GET, HEAD", "Cache-Control": NO_STORE}
            )(scope, receive, send)
            return
        path = scope.get("path", "")
        prefix = scope.get("root_path", "")
        if prefix and path.startswith(prefix + "/"):
            relative = path[len(prefix) + 1 :]
        elif not prefix:
            relative = path.lstrip("/")
        else:
            relative = ""
        build_id, slash, asset = relative.partition("/")
        parts = asset.split("/")
        valid = (
            bool(slash)
            and len(build_id) == 16
            and all(char in "0123456789abcdef" for char in build_id)
            and all(part not in ("", ".", "..") for part in parts)
            and "\\" not in asset
            and "\x00" not in asset
            and MANIFEST_NAME not in parts
        )
        if not valid:
            await Response(status_code=404, headers={"Cache-Control": NO_STORE})(
                scope, receive, send
            )
            return
        build = await self._build(build_id)
        if build is None or asset not in build:
            await Response(status_code=404, headers={"Cache-Control": NO_STORE})(
                scope, receive, send
            )
            return
        data = build[asset]
        digest = hashlib.sha256(data).hexdigest()
        identity_etag = f'"{digest}"'
        request_headers = {k.lower(): v.decode("latin1") for k, v in scope.get("headers", [])}
        range_header = request_headers.get(b"range")
        if_range = request_headers.get(b"if-range")
        use_range = (
            range_header is not None
            and bool(range_header)
            and "," not in range_header
            and (if_range is None or if_range == identity_etag)
        )
        gzip_ok = (
            not use_range
            and not range_header
            and len(data) >= 1000
            and asset.endswith((".js", ".css", ".svg", ".webmanifest"))
            and _accepts_gzip(scope)
        )
        etag = f'W/"gzip-{digest}"' if gzip_ok else identity_etag
        headers = {"Cache-Control": IMMUTABLE, "ETag": etag, "Vary": "Accept-Encoding"}
        if request_headers.get(b"if-none-match") and _etag_matches(
            request_headers[b"if-none-match"], etag
        ):
            await Response(status_code=304, headers=headers)(scope, receive, send)
            return
        if use_range and range_header:
            segment = _range_bytes(range_header, len(data))
            if segment is None:
                headers["Content-Range"] = f"bytes */{len(data)}"
                headers["Cache-Control"] = NO_STORE
                await Response(status_code=416, headers=headers)(scope, receive, send)
                return
            first, last = segment
            body = data[first : last + 1]
            headers["Content-Range"] = f"bytes {first}-{last}/{len(data)}"
            status = 206
        else:
            body = data
            status = 200
            if gzip_ok:
                body = gzip.compress(data, mtime=0)
                headers["Content-Encoding"] = "gzip"
        headers["Accept-Ranges"] = "bytes"
        headers["Content-Length"] = str(len(body))
        media_type, _ = mimetypes.guess_type(asset)
        await Response(
            content=body if method == "GET" else b"",
            status_code=status,
            headers=headers,
            media_type=media_type or "application/octet-stream",
        )(scope, receive, send)
