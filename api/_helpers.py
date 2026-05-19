import json
import re
import time
import io
import base64
import os
import ssl
import urllib.request
from urllib.parse import urlparse, parse_qs, quote
from http.server import BaseHTTPRequestHandler


_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE


class BaseHandler(BaseHTTPRequestHandler):
    def json_response(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length))

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def log_message(self, *args):
        pass


def sanitize_filename(name: str) -> str:
    name = name.lower().strip()
    name = re.sub(r"[^\w\s-]", "", name)
    name = re.sub(r"[\s_-]+", "_", name)
    return name[:80]


def get_anthropic_client():
    import anthropic
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key or len(key) < 20:
        raise ValueError("ANTHROPIC_API_KEY ontbreekt of is ongeldig.")
    return anthropic.Anthropic(api_key=key)


def download_image(url: str) -> bytes | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8, context=_ssl_ctx) as r:
            return r.read()
    except Exception:
        return None


def vivino_search_html(query: str) -> str:
    url = f"https://www.vivino.com/search/wines?q={quote(query)}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8, context=_ssl_ctx) as r:
            return r.read().decode("utf-8", errors="ignore")
    except Exception:
        return ""
