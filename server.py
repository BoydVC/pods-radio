"""Pods Radio server: http://127.0.0.1:4849 (stdlib, local only, read-only). Supports HTTP Range for audio seeking."""
import json, mimetypes, os, re
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
WEB, EPS = os.path.join(HERE, "web"), os.path.join(HERE, "episodes")
PORT = int(os.environ.get("PORT", 4849))


def podcast_feed(host):
    """Pods Radio as a podcast: RSS 2.0 with enclosures, built from episodes/index.json (local network only)."""
    from email.utils import format_datetime
    from datetime import datetime
    from xml.sax.saxutils import escape as x
    idx = json.load(open(os.path.join(EPS, "index.json"))) if os.path.exists(os.path.join(EPS, "index.json")) else {"episodes": []}
    base = f"http://{host}"
    items = []
    for m in idx["episodes"]:
        e = json.load(open(os.path.join(EPS, m["date"], "episode.json")))
        pub = datetime.fromisoformat(e["window"][1])
        desc = " · ".join(f"[{int(c['start'] // 60)}:{int(c['start'] % 60):02d}] {c['title']}" for c in e["chapters"])
        items.append(f"""<item><title>{x(e['title'])}</title><guid isPermaLink="false">pods-radio-{m['date']}</guid><pubDate>{format_datetime(pub)}</pubDate>
<link>{base}/e/{m['date']}</link><description>{x(desc)}</description><itunes:duration>{int(e['duration'])}</itunes:duration>
<enclosure url="{base}/episodes/{m['date']}/{x(e['audio'])}" length="{e['bytes']}" type="audio/mpeg"/></item>""")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"><channel><title>Pods Radio</title><link>{base}/</link>
<description>Auto-produced daily show from the feeds Boyd's Pods bot watches. Feed titles, dates and descriptions only.</description><language>en-us</language>
{''.join(items)}</channel></rss>"""


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8", extra=None):
        if isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _file(self, path, ctype=None):
        size = os.path.getsize(path)
        ctype = ctype or mimetypes.guess_type(path)[0] or "application/octet-stream"
        rng = self.headers.get("Range")
        start, end = 0, size - 1
        m = re.match(r"bytes=(\d*)-(\d*)", rng or "")
        if m:
            if m.group(1):
                start = int(m.group(1))
                end = int(m.group(2)) if m.group(2) else size - 1
            else:
                start = max(0, size - int(m.group(2)))
            end = min(end, size - 1)
            if start > end:
                self.send_response(416); self.send_header("Content-Range", f"bytes */{size}"); self.end_headers(); return
        n = end - start + 1
        self.send_response(206 if m else 200)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(n))
        if m:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        if self.command == "HEAD":
            return
        with open(path, "rb") as f:
            f.seek(start)
            left = n
            while left > 0:
                chunk = f.read(min(65536, left))
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    return
                left -= len(chunk)

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        p = urlparse(self.path).path
        if p == "/api/health":
            idx = os.path.join(EPS, "index.json")
            n = len(json.load(open(idx))["episodes"]) if os.path.exists(idx) else 0
            return self._send(200, json.dumps({"ok": True, "episodes": n}))
        if p == "/api/index":
            f = os.path.join(EPS, "index.json")
            return self._send(200, open(f, "rb").read()) if os.path.exists(f) else self._send(200, json.dumps({"episodes": [], "error": "no episodes built yet"}))
        if p == "/feed.xml":
            return self._send(200, podcast_feed(self.headers.get("Host") or f"127.0.0.1:{PORT}"), "application/rss+xml; charset=utf-8")
        m = re.match(r"^/api/episode/(\d{4}-\d{2}-\d{2})$", p)
        if m:
            f = os.path.join(EPS, m.group(1), "episode.json")
            return self._send(200, open(f, "rb").read()) if os.path.exists(f) else self._send(404, json.dumps({"error": "no such episode"}))
        m = re.match(r"^/episodes/(\d{4}-\d{2}-\d{2})/([\w.\-]+)$", p)
        if m:
            f = os.path.join(EPS, m.group(1), m.group(2))
            if os.path.isfile(f) and not f.endswith(".wav"):
                return self._file(f, "audio/mpeg" if f.endswith(".mp3") else ("text/markdown; charset=utf-8" if f.endswith(".md") else None))
            return self._send(404, "not found", "text/plain")
        if p.startswith("/e/") and not re.match(r"^/e/\d{4}-\d{2}-\d{2}$", p):
            p = p[2:]                      # relative assets requested from a /e/<date> deep link
        if p in ("/", "/index.html") or re.match(r"^/e/\d{4}-\d{2}-\d{2}$", p):
            p = "/index.html"
        f = os.path.normpath(os.path.join(WEB, p.lstrip("/")))
        if f.startswith(WEB) and os.path.isfile(f):
            return self._file(f, "font/ttf" if f.endswith(".ttf") else None)
        self._send(404, "not found", "text/plain")


class S(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == "__main__":
    print(f"Pods Radio on http://127.0.0.1:{PORT}", flush=True)
    S(("127.0.0.1", PORT), H).serve_forever()
