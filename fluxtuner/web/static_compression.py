"""Selective gzip compression for public static Web assets."""

from starlette.middleware.gzip import GZipMiddleware

COMPRESSIBLE_SUFFIXES = (".js", ".css", ".svg", ".webmanifest")


class StaticCompression:
    """Compress eligible static assets without touching binary or private routes."""

    def __init__(self, app):
        self.app = app
        self.compressed_app = GZipMiddleware(app, minimum_size=1000)

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")

        if scope["type"] != "http" or not path.endswith(COMPRESSIBLE_SUFFIXES):
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        accepts_gzip = b"gzip" in headers.get(b"accept-encoding", b"").lower()

        if not accepts_gzip:
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

        async def send_without_identity_etag(message):
            if message["type"] == "http.response.start":
                message = dict(message)
                message["headers"] = [
                    (key, value)
                    for key, value in message.get("headers", [])
                    if key.lower() != b"etag"
                ]
            await send(message)

        await self.compressed_app(compressed_scope, receive, send_without_identity_etag)
