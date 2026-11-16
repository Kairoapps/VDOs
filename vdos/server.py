"""Read-only file server for media/edited, meant to sit behind Tailscale Funnel.

- Binds to 127.0.0.1 only (Funnel proxies to it).
- Serves only files named like R20261111-003_v2_k7f3q9.mp4 directly inside media/edited.
- No directory listings, no other paths, GET/HEAD only, supports Range requests.
"""
from __future__ import annotations

import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import config

NAME = re.compile(r"^/(R\d{8}-\d{3}_v\d+_[0-9a-f]{6}\.mp4)$")


class Handler(BaseHTTPRequestHandler):
    server_version = "vdos"
    sys_version = ""

    def _resolve(self):
        m = NAME.match(self.path.split("?", 1)[0])
        if not m:
            return None
        p = config.load().path("edited") / m.group(1)
        return p if p.is_file() else None

    def _send(self, head: bool):
        p = self._resolve()
        if not p:
            self.send_error(404)
            return
        size = p.stat().st_size
        start, end = 0, size - 1
        rng = self.headers.get("Range")
        status = 200
        if rng:
            m = re.match(r"bytes=(\d*)-(\d*)$", rng.strip())
            if m:
                if m.group(1):
                    start = int(m.group(1))
                    end = int(m.group(2)) if m.group(2) else size - 1
                elif m.group(2):
                    start = max(0, size - int(m.group(2)))
                if start > end or start >= size:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{size}")
                    self.end_headers()
                    return
                end = min(end, size - 1)
                status = 206
        self.send_response(status)
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Cache-Control", "public, max-age=86400")
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        if head:
            return
        with open(p, "rb") as f:
            f.seek(start)
            left = end - start + 1
            while left > 0:
                chunk = f.read(min(1 << 20, left))
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    return
                left -= len(chunk)

    def do_GET(self):
        self._send(False)

    def do_HEAD(self):
        self._send(True)

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args))


def serve(port: int | None = None) -> None:
    port = port or config.load()["server"]["port"]
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"serving media/edited on http://127.0.0.1:{port}")
    httpd.serve_forever()
