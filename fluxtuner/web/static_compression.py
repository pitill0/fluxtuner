"""Selective gzip compression for public static Web assets."""

from pathlib import Path

from starlette.datastructures import Headers
from starlette.middleware.gzip import GZipMiddleware

COMPRESSIBLE_SUFFIXES = (".js", ".css", ".svg", ".webmanifest")


def _accepts_gzip(scope) -> bool:
    """Respect explicit gzip refusal in Accept-Encoding."""
    header = Headers(scope=scope).get("accept-encoding", "")
    for item in header.split(","):
        coding, _, parameters = item.strip().partition(";")
        if coding.strip().lower() != "gzip":
            continue
        for parameter in parameters.split(";"):
            name, separator, value = parameter.strip().partition("=")
            if separator and name.lower() == "q":
                try:
                    return float(value.strip()) > 0
                except ValueError:
                    return False
        return True
    return False


class StaticCompression:
    """Compress eligible static assets without touching binary or private routes."""

    def __init__(self, app):
        self.app = app
        self.compressed_app = GZipMiddleware(app, minimum_size=1000)
        self.static_directory = Path(app.directory).resolve()

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")

        if scope["type"] != "http" or not path.endswith(COMPRESSIBLE_SUFFIXES):
            await self.app(scope, receive, send)
            return

        root_path = scope.get("root_path", "")
        if root_path and path.startswith(root_path + "/"):
            relative_path = path[len(root_path) + 1 :]
        else:
            relative_path = path.lstrip("/")

        candidate = (self.static_directory / relative_path).resolve()
        if (
            not candidate.is_relative_to(self.static_directory)
            or not candidate.is_file()
            or candidate.stat().st_size < 1000
        ):
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)

        # Let StaticFiles handle HEAD and byte ranges without modification.
        if (
            scope.get("method") != "GET"
            or "range" in headers
            or "if-range" in headers
            or not _accepts_gzip(scope)
        ):
            await self.app(scope, receive, send)
            return

        # Avoid reusing identity ETags for compressed representations.
        # StaticFiles must not return 304 before compression is applied.
        filtered_headers = [
            (key, value)
            for key, value in scope.get("headers", [])
            if key.lower() not in (b"if-none-match", b"if-modified-since")
        ]
        compressed_scope = {**scope, "headers": filtered_headers}

        requested_etags = [
            item.strip()
            for key, value in scope.get("headers", [])
            if key.lower() == b"if-none-match"
            for item in value.split(b",")
            if item.strip()
        ]
        revalidated = False
        completed_304 = False

        async def send_with_gzip_validator(message):
            nonlocal revalidated, completed_304

            if message["type"] == "http.response.start":
                message = dict(message)
                headers = list(message.get("headers", []))
                compressed = any(
                    key.lower() == b"content-encoding" and value.lower() == b"gzip"
                    for key, value in headers
                )
                identity_etag = next(
                    (value for key, value in headers if key.lower() == b"etag"),
                    None,
                )
                headers = [(key, value) for key, value in headers if key.lower() != b"etag"]

                gzip_etag = None
                if compressed and identity_etag:
                    gzip_etag = b'W/"gzip-' + identity_etag.strip(b'W/"') + b'"'
                    headers.append((b"etag", gzip_etag))

                if (
                    message["status"] == 200
                    and gzip_etag is not None
                    and scope["method"] in ("GET", "HEAD")
                    and any(
                        candidate == b"*"
                        or candidate.removeprefix(b"W/") == gzip_etag.removeprefix(b"W/")
                        for candidate in requested_etags
                    )
                ):
                    revalidated = True
                    message["status"] = 304
                    headers = [
                        (key, value)
                        for key, value in headers
                        if key.lower()
                        not in (b"content-length", b"content-encoding", b"content-range")
                    ]

                message["headers"] = headers

            elif message["type"] == "http.response.body" and revalidated:
                if not completed_304:
                    completed_304 = True
                    await send(
                        {
                            "type": "http.response.body",
                            "body": b"",
                            "more_body": False,
                        }
                    )
                return

            await send(message)

        await self.compressed_app(compressed_scope, receive, send_with_gzip_validator)
