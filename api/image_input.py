import sys, os, base64, time
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from lib.auth import require_admin
from lib.helpers import BaseHandler, download_image
from lib.db import get_db
from lib.image import remove_background, has_transparency, normalize_transparent, make_thumbnail
from urllib.parse import urlparse, parse_qs


class handler(BaseHandler):
    def do_POST(self):
        if not require_admin(self): return
        parsed = urlparse(self.path)
        mode = parse_qs(parsed.query).get("mode", [""])[0]
        try:
            data = self.read_json()
            name = (data.get("name") or "").strip()
            if not name:
                self.json_response(400, {"message": "Naam is vereist."})
                return
            if mode == "url":
                image_url = (data.get("imageUrl") or "").strip()
                if not image_url:
                    self.json_response(400, {"message": "imageUrl is vereist."})
                    return
                img_bytes = download_image(image_url)
                if not img_bytes:
                    raise ValueError("Kon de afbeelding niet downloaden van de opgegeven URL.")
            elif mode == "data":
                image_data = (data.get("imageData") or "").strip()
                if not image_data:
                    self.json_response(400, {"message": "imageData is vereist."})
                    return
                img_bytes = base64.b64decode(image_data)
            else:
                self.json_response(400, {"message": "Onbekende modus."})
                return
            processed = remove_background(img_bytes) if not has_transparency(img_bytes) else normalize_transparent(img_bytes)
            thumb = make_thumbnail(processed)
            now = int(time.time())
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE wines SET image_data=%s, thumb_data=%s, updatedat=%s WHERE name=%s",
                        (processed, thumb, now, name)
                    )
                conn.commit()
            self.json_response(200, {"ok": True, "updatedAt": now})
        except Exception as e:
            self.json_response(500, {"message": str(e)})
