import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from lib.auth import check_auth, require_admin
from lib.helpers import BaseHandler
from lib.db import get_db, resolve_owner_id, get_wine_owner
from urllib.parse import urlparse, parse_qs

# Samengevoegd uit (voormalig) wine_thumb.py + wine_image.py om onder de Vercel-limiet
# van 12 functies in api/ te blijven (zie CLAUDE.md). Publieke paden /api/wine-thumb en
# /api/wine-image blijven ongewijzigd, vercel.json stuurt beide hierheen met ?variant=.


class handler(BaseHandler):
    def do_GET(self):
        auth = check_auth(self)
        if not auth: return
        username, role = auth
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        wine_id = (params.get("id", [""])[0]).strip()
        variant = (params.get("variant", ["thumb"])[0]).strip()
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
                cur.execute("SELECT thumb_data, image_data FROM wines WHERE id=%s", (wine_id,))
                row = cur.fetchone()
        if not row:
            self.send_error(404)
            return
        if variant == "full":
            img_bytes = bytes(row["image_data"] or b"")
        else:
            img_bytes = bytes(row["thumb_data"] or row["image_data"] or b"")
        if not img_bytes:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(img_bytes)))
        self.send_header("Cache-Control", "public, max-age=31536000, immutable")
        self.end_headers()
        self.wfile.write(img_bytes)

    def do_DELETE(self):
        auth = require_admin(self)
        if not auth: return
        username, role = auth
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        wine_id = (params.get("id", [""])[0]).strip()
        if not wine_id:
            self.json_response(400, {"message": "Wijn-id is vereist."})
            return
        owner = get_wine_owner(wine_id)
        own_id = resolve_owner_id(username, role)
        if owner is None or owner != own_id:
            self.json_response(404, {"message": "Wijn niet gevonden."})
            return
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE wines SET image_data=NULL, thumb_data=NULL, proposed_data=NULL, proposed_at=0 WHERE id=%s",
                    (wine_id,)
                )
            conn.commit()
        self.json_response(200, {"ok": True, "removed": True})
