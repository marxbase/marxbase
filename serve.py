#!/usr/bin/env python3
"""Local preview server for dist/ that tells the browser never to cache, so a rebuilt site always shows up.
  python3 serve.py [port] [folder]      (folder defaults to dist)"""
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class NoCache(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    folder = sys.argv[2] if len(sys.argv) > 2 else "dist"
    handler = partial(NoCache, directory=str(Path(__file__).parent / folder))
    print(f"MarxBase preview of {folder} at http://localhost:{port}/index.html (Ctrl+C to stop)")
    ThreadingHTTPServer(("127.0.0.1", port), handler).serve_forever()
