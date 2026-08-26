"""Static server for the Claude Design `.dc.html` boards.

The boards are Claude Design canvas documents: the page body is wrapped in
`<x-dc>`, and `support.js` hides that raw template immediately, then fetches
React 18 UMD from unpkg (with SRI) before rendering. On a machine behind a
TLS-intercepting proxy the SRI check fails and every board renders blank, so
this server can inject a locally vendored React ahead of `support.js`.

Nothing under the design folder is modified — the injection happens in the
response body only.

    python tools/design_server.py --port 8777

Serves an index of the boards at http://127.0.0.1:<port>/.
"""

import argparse
import html
import mimetypes
import os
import posixpath
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import unquote, quote

VENDOR_PREFIX = "/__dcvendor/"
SUPPORT_TAG = b'<script src="./support.js"></script>'


class BoardHandler(SimpleHTTPRequestHandler):
    root = "."
    vendor = None  # directory holding react*.min.js, or None

    def _vendor_tags(self):
        if not self.vendor:
            return b""
        return (
            b'<script src="' + VENDOR_PREFIX.encode() + b'react.production.min.js"></script>'
            b'<script src="' + VENDOR_PREFIX.encode() + b'react-dom.production.min.js"></script>'
        )

    def _send_bytes(self, body, ctype):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = unquote(self.path.split("?", 1)[0].split("#", 1)[0])

        if path == "/":
            return self._send_bytes(self._index().encode("utf-8"), "text/html; charset=utf-8")

        if path.startswith(VENDOR_PREFIX):
            if not self.vendor:
                return self.send_error(404, "no vendored React configured")
            name = posixpath.basename(path)
            full = os.path.join(self.vendor, name)
            if not os.path.isfile(full):
                return self.send_error(404, "vendored file not found: %s" % name)
            with open(full, "rb") as fh:
                return self._send_bytes(fh.read(), "text/javascript; charset=utf-8")

        if path.endswith(".dc.html"):
            full = os.path.join(self.root, path.lstrip("/").replace("/", os.sep))
            if not os.path.isfile(full):
                return self.send_error(404, "board not found")
            with open(full, "rb") as fh:
                body = fh.read()
            tags = self._vendor_tags()
            if tags and SUPPORT_TAG in body:
                body = body.replace(SUPPORT_TAG, tags + SUPPORT_TAG, 1)
            return self._send_bytes(body, "text/html; charset=utf-8")

        return SimpleHTTPRequestHandler.do_GET(self)

    def _index(self):
        boards = sorted(f for f in os.listdir(self.root) if f.endswith(".dc.html"))
        rows = "\n".join(
            '<li><a href="/%s">%s</a></li>' % (quote(b), html.escape(b[:-8]))
            for b in boards
        )
        react = "local vendored React" if self.vendor else "React from unpkg (CDN)"
        return (
            "<!doctype html><meta charset=utf-8><title>Design boards</title>"
            "<style>body{background:#06090E;color:#E8EBE9;font:16px/1.6 system-ui;"
            "padding:56px 64px}h1{font-weight:300;letter-spacing:-.02em}"
            "a{color:#E8873A;text-decoration:none}a:hover{text-decoration:underline}"
            "li{margin:.5em 0}code{color:rgba(232,235,233,.5);font-size:13px}</style>"
            "<h1>Claude Design boards</h1><ul>%s</ul><p><code>%s &middot; %s</code></p>"
            % (rows, html.escape(self.root), react)
        )

    def log_message(self, fmt, *a):
        sys.stderr.write("%s %s\n" % (self.address_string(), fmt % a))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=os.path.join("design", "Claude Design Iteration 1"))
    ap.add_argument("--port", type=int, default=8777)
    ap.add_argument("--vendor", default=None,
                    help="directory with react.production.min.js and react-dom.production.min.js")
    args = ap.parse_args()

    root = os.path.abspath(args.dir)
    if not os.path.isdir(root):
        sys.exit("design dir not found: %s" % root)

    vendor = os.path.abspath(args.vendor) if args.vendor else None
    if vendor and not os.path.isdir(vendor):
        sys.exit("vendor dir not found: %s" % vendor)

    mimetypes.add_type("text/javascript", ".js")
    BoardHandler.root = root
    BoardHandler.vendor = vendor
    BoardHandler.directory = root

    handler = lambda *a, **k: BoardHandler(*a, directory=root, **k)
    srv = HTTPServer(("127.0.0.1", args.port), handler)
    print("serving %s on http://127.0.0.1:%d/  (react: %s)"
          % (root, args.port, "vendored" if vendor else "unpkg"), flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
