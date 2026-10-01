"""Vercel Python function: POST /api/calc with the calculator's inputs as JSON. The code and data are bundled into _lib by tools/bundle_site.py."""
import os
import sys
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "_lib"))

from calc import server  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        self.path = "/api/calc"
        server.serve(self)

    def do_GET(self):
        self.path = "/api/calc" + (self.path[self.path.index("?"):] if "?" in self.path else "")
        server.serve(self)
