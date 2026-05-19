import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from _helpers import BaseHandler
from _db import get_db


class handler(BaseHandler):
    def do_POST(self):
        try:
            data = self.read_json()
            name = (data.get("name") or "").strip()
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute("UPDATE wines SET proposed_data=NULL WHERE name=%s", (name,))
                conn.commit()
            self.json_response(200, {"ok": True})
        except Exception as e:
            self.json_response(500, {"message": str(e)})
