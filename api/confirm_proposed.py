import sys, os, time
sys.path.insert(0, os.path.dirname(__file__))
from _helpers import BaseHandler
from _db import get_db
from _image import make_thumbnail


class handler(BaseHandler):
    def do_POST(self):
        try:
            data = self.read_json()
            name = (data.get("name") or "").strip()
            if not name:
                self.json_response(400, {"message": "Naam is vereist."})
                return
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT proposed_data FROM wines WHERE name=%s", (name,))
                    row = cur.fetchone()
                if not row or not row["proposed_data"]:
                    self.json_response(404, {"message": "Geen voorgestelde afbeelding gevonden."})
                    return
                proposed = bytes(row["proposed_data"])
                thumb = make_thumbnail(proposed)
                now = int(time.time())
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE wines SET image_data=%s, thumb_data=%s, proposed_data=NULL, updatedat=%s WHERE name=%s",
                        (proposed, thumb, now, name)
                    )
                conn.commit()
            self.json_response(200, {"ok": True})
        except Exception as e:
            self.json_response(500, {"message": str(e)})
