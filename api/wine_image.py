import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from lib.auth import check_auth, require_admin
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
                cur.execute("SELECT image_data FROM wines WHERE name=%s", (name,))
                row = cur.fetchone()
        if not row or not row["image_data"]:
            self.send_error(404)
            return
        img_bytes = bytes(row["image_data"])
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(img_bytes)))
        self.send_header("Cache-Control", "public, max-age=31536000, immutable")
        self.end_headers()
        self.wfile.write(img_bytes)

    def do_DELETE(self):
        if not require_admin(self): return
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        name = (params.get("name", [""])[0]).strip()
        if not name:
            self.json_response(400, {"message": "Naam is vereist."})
            return
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE wines SET image_data=NULL, thumb_data=NULL, proposed_data=NULL WHERE name=%s",
                    (name,)
                )
            conn.commit()
        self.json_response(200, {"ok": True, "removed": True})
