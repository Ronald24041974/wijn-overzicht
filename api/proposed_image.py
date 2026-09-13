import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from lib.auth import check_auth
from lib.helpers import BaseHandler
from lib.db import get_db, resolve_owner_id, get_wine_owner
from urllib.parse import urlparse, parse_qs


class handler(BaseHandler):
    def do_GET(self):
        auth = check_auth(self)
        if not auth: return
        username, role = auth
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        wine_id = (params.get("id", [""])[0]).strip()
        if not wine_id:
            self.send_error(400)
            return
        owner = get_wine_owner(wine_id)
        own_id = resolve_owner_id(username, role)
        if owner is None or (owner != own_id and role != "superadmin"):
            self.send_error(404)
            return
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT proposed_data FROM wines WHERE id=%s", (wine_id,))
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
