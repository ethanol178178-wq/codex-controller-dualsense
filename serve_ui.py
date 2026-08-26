"""Serve only the public UI assets required by VibeCoding Controller Hub."""

from __future__ import annotations

import os
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse


HOST = "127.0.0.1"
PORT = 4173
ROOT = os.path.dirname(os.path.abspath(__file__))
PUBLIC_ASSETS = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/assets/dualsense-wireframe.png": ("assets/dualsense-wireframe.png", "image/png"),
}


def resolve_asset(raw_path: str) -> tuple[str, str] | None:
    """Resolve an exact allowlisted URL path to a local asset."""
    request_path = unquote(urlparse(raw_path).path)
    asset = PUBLIC_ASSETS.get(request_path)
    if asset is None:
        return None
    relative_path, content_type = asset
    return os.path.join(ROOT, *relative_path.split("/")), content_type


class PublicUiHandler(BaseHTTPRequestHandler):
    server_version = "DS5VibeHubUI/1.0"

    def _send_asset(self, include_body: bool) -> None:
        asset = resolve_asset(self.path)
        if asset is None:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        path, content_type = asset
        try:
            with open(path, "rb") as stream:
                body = stream.read()
        except OSError:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; connect-src http://127.0.0.1:37845; "
            "img-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "base-uri 'none'; frame-ancestors 'none'",
        )
        self.end_headers()
        if include_body:
            self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        self._send_asset(include_body=True)

    def do_HEAD(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        self._send_asset(include_body=False)


def main(stop_event: threading.Event | None = None) -> None:
    server = ThreadingHTTPServer((HOST, PORT), PublicUiHandler)
    print(f"VibeCoding Controller Hub UI listening on http://{HOST}:{PORT}")
    try:
        if stop_event is None:
            server.serve_forever()
        else:
            server.timeout = 0.25
            while not stop_event.is_set():
                server.handle_request()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
