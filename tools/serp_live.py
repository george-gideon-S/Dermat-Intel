"""Serve the Google Search review page live, filling in as the scraper captures each query.

The static report is a snapshot; this is the same page watching the run happen. It polls
`data.json` every 3 seconds, and the server rebuilds that payload from the run's own
checkpoints — so what you see is exactly what is on disk, never a separate in-memory view that
could drift from it.

    python tools/serp_live.py --run last
    python tools/serp_live.py --run guntur-ap_dermatology_both_2026-08-21 --port 8766

Leave it running; Ctrl-C stops it. It is read-only: it never writes into the run, so it is
safe to start, stop and restart while a scrape is in progress.
"""
# Embeddable-Python bootstrap: isolated mode keeps the script's own directory off sys.path.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import argparse
import http.server
import json
import os
import socket
import socketserver
import threading
import webbrowser

import config
from modules import runstore, serp_collector, serp_report
from modules import serp_session as S


class _Cache:
    """Rebuild the payload only when the run actually changed.

    Each poll would otherwise re-read every per-query page file, once per open browser tab.
    The fetch log is written after every capture, so its mtime and size are a faithful
    change signal for the whole run.
    """

    def __init__(self, run_dir):
        self.run_dir = run_dir
        self.stamp = None
        self.blob = b"{}"

    def _stamp(self):
        marks = []
        for path in (serp_collector.fetch_log_path(self.run_dir),
                     S.query_rows_path(self.run_dir),
                     S.lock_path(),
                     S.state_path(self.run_dir),
                     serp_collector.serp_dir(self.run_dir) / "BLOCKED.txt",
                     serp_collector.serp_dir(self.run_dir) / "listicles.json"):
            try:
                st = path.stat()
                marks.append((str(path), st.st_mtime_ns, st.st_size))
            except OSError:
                marks.append((str(path), 0, 0))
        # The parsed pages and interaction extras change WITHOUT the fetch log moving —
        # re-parsing saved HTML rewrites every page file and touches nothing else. Keying the
        # cache on the log alone meant the live page kept serving the old parse indefinitely.
        for sub in ("pages", "extras"):
            d = serp_collector.serp_dir(self.run_dir) / sub
            try:
                newest, count = 0, 0
                for f in d.glob("q*.json"):
                    count += 1
                    newest = max(newest, f.stat().st_mtime_ns)
                marks.append((sub, newest, count))
            except OSError:
                marks.append((sub, 0, 0))
        return tuple(marks)

    def payload(self) -> bytes:
        stamp = self._stamp()
        if stamp != self.stamp:
            qrows = S.load_query_rows(self.run_dir)
            data = serp_report.collect_data(self.run_dir, qrows=qrows)
            self.blob = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
            self.stamp = stamp
        return self.blob


def build_handler(run_dir, cache):
    live_page = serp_report.PAGE.replace("__DATA__", "null").encode("utf-8")

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(run_dir), **kw)

        def _send(self, blob: bytes, ctype: str) -> None:
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(blob)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(blob)

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            try:
                if path in ("/", "/index.html"):
                    return self._send(live_page, "text/html; charset=utf-8")
                if path == "/data.json":
                    return self._send(cache.payload(), "application/json; charset=utf-8")
            except (BrokenPipeError, ConnectionResetError):
                return          # the tab closed mid-response; not an error worth logging
            # everything else (screenshots, raw html) is served straight from the run dir
            return super().do_GET()

        def log_message(self, *a):
            pass                # a poll every 3 s would bury the console in access lines

    return Handler


class _Server(socketserver.ThreadingTCPServer):
    daemon_threads = True
    # NOT allow_reuse_address. On Windows SO_REUSEADDR does not mean "reclaim a dead socket",
    # it means "bind even though someone else already owns this port" — the bind SUCCEEDS and
    # the OS then hands each connection to whichever socket it likes. Pointed at 8766 while the
    # Maps UI was serving there, this page came up looking healthy and answered with the Maps
    # dataset. Fail loudly on a busy port instead.
    allow_reuse_address = False

    def server_bind(self):
        if os.name == "nt":
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Live Google SERP review page")
    p.add_argument("--run", required=True, metavar="RUN_ID", help="run id, or 'last'")
    p.add_argument("--port", type=int, default=8766)
    p.add_argument("--no-open", action="store_true", dest="no_open")
    args = p.parse_args(argv)

    run_id = args.run
    if run_id == "last":
        runs = runstore.list_runs(config.RUNS_DIR)
        if not runs:
            print("no runs yet.")
            return 2
        run_id = runs[0]["run_id"]

    run_dir = runstore.run_path(config.RUNS_DIR, run_id)
    if not runstore.read_manifest(run_dir):
        print(f"no such run: {run_id}")
        return 2

    cache = _Cache(run_dir)
    data = json.loads(cache.payload())
    meta = data["meta"]
    url = f"http://127.0.0.1:{args.port}/"

    print(f"live page : {url}")
    print(f"run       : {run_id}")
    print(f"at start  : {meta['captured']}/{meta['total']} captured, "
          f"{meta['total_blocks']} blocks")
    print(f"scraper   : {'running' if data['session']['running'] else 'not running'}")
    print("(leave this running; Ctrl-C to stop)")

    try:
        server = _Server(("127.0.0.1", args.port), build_handler(run_dir, cache))
    except OSError as exc:
        print(f"\ncannot serve on port {args.port}: {exc}")
        print("Something else is already listening there — the Maps review pages use 8765 "
              "and 8766. Pick another with --port.")
        return 2

    with server as httpd:
        if not args.no_open:
            threading.Timer(1.0, lambda: webbrowser.open(url)).start()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
