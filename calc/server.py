"""Serving the calculator: one `respond` shared by the local server and the Vercel functions.

    python -m calc.server            # http://127.0.0.1:8765/api/calc and /api/preview, for `next dev` to forward to
"""
from __future__ import annotations

import gzip
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from calc import api

ROUTES = {"/api/calc": api.calculate, "/api/preview": api.preview}


def respond(path: str, body: bytes, accept_gzip: bool) -> tuple[int, dict, bytes]:
    fn = ROUTES.get(path.rstrip("/"))
    if fn is None:
        return 404, {"content-type": "application/json"}, b'{"error":"not found"}'
    try:
        params = json.loads(body or b"{}")
        if not isinstance(params, dict):
            raise ValueError
    except ValueError:
        return 400, {"content-type": "application/json"}, b'{"error":"the request body must be a JSON object"}'
    out = fn(params)
    data = json.dumps(out, separators=(",", ":")).encode("utf-8")
    headers = {"content-type": "application/json", "cache-control": "public, max-age=3600"}
    if accept_gzip:
        data, headers["content-encoding"] = gzip.compress(data, 6), "gzip"
    return (400 if "error" in out else 200), headers, data


def serve(handler: BaseHTTPRequestHandler) -> None:
    """Answer one request on a BaseHTTPRequestHandler: POST with a JSON body, or GET with ?q=<JSON>."""
    url = urlparse(handler.path)
    if handler.command == "POST":
        body = handler.rfile.read(int(handler.headers.get("content-length") or 0))
    else:
        body = (parse_qs(url.query).get("q") or ["{}"])[0].encode("utf-8")
    status, headers, data = respond(url.path, body, "gzip" in (handler.headers.get("accept-encoding") or ""))
    handler.send_response(status)
    for k, v in headers.items():
        handler.send_header(k, v)
    handler.send_header("content-length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


class Local(BaseHTTPRequestHandler):
    def do_POST(self):
        serve(self)

    def do_GET(self):
        serve(self)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    print(f"calculator API on http://127.0.0.1:{port}/api/calc", flush=True)
    ThreadingHTTPServer(("127.0.0.1", port), Local).serve_forever()
