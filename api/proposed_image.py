import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from lib.auth import check_auth
from lib.helpers import BaseHandler
from lib.db import get_db
from urllib.parse import urlparse, parse_qs


class handler(BaseHandler):
    def do_GET(self):
        if not check_auth(self): return
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        name = (params.get("name", [""])[0]).strip()
        if not name:
            self.send_error(400)
            return
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT proposed_data FROM wines WHERE name=%s", (name,))
                row = cur.fetchone()
        if not row or not row["proposed_data"]:
            self.send_error(404)
            return
        img_bytes = bytes(row["proposed_data"])
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(img_bytes)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(img_bytes)
