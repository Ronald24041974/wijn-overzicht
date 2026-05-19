import sys, os, base64, time
sys.path.insert(0, os.path.dirname(__file__))
from _helpers import BaseHandler
from _db import get_db
from _image import remove_background, has_transparency, normalize_transparent, make_thumbnail


class handler(BaseHandler):
    def do_POST(self):
        try:
            data = self.read_json()
            name = (data.get("name") or "").strip()
            image_data = (data.get("imageData") or "").strip()
            if not name or not image_data:
                self.json_response(400, {"message": "Naam en afbeeldingsdata zijn vereist."})
                return
            img_bytes = base64.b64decode(image_data)
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
