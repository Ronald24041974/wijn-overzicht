from http.server import BaseHTTPRequestHandler
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from lib.auth import check_auth
from lib.db import get_db, load_wines, add_wine, update_wine, serialize_wine
from lib.helpers import BaseHandler
from urllib.parse import urlparse, parse_qs


class handler(BaseHandler):

    def do_GET(self):
        if not check_auth(self): return
        self.json_response(200, {"wines": load_wines()})

    def do_POST(self):
        if not check_auth(self): return
        try:
            data = self.read_json()
            wine = add_wine(data)
            self.json_response(201, {"wine": wine, "wines": load_wines()})
        except Exception as e:
            self.json_response(400, {"message": str(e)})

    def do_PATCH(self):
        if not check_auth(self): return
        try:
            patch = self.read_json()
            wine = update_wine(patch)
            self.json_response(200, {"wine": wine, "wines": load_wines()})
        except Exception as e:
            self.json_response(400, {"message": str(e)})

    def do_DELETE(self):
        if not check_auth(self): return
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        row_number = (params.get("rowNumber", [""])[0]).strip()
        if not row_number:
            self.json_response(400, {"message": "rowNumber is vereist."})
            return
        try:
            wine_id = int(row_number)
        except ValueError:
            self.json_response(400, {"message": "Ongeldig rowNumber."})
            return
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT name FROM wines WHERE id=%s", (wine_id,))
                row = cur.fetchone()
                if not row:
                    self.json_response(404, {"message": "Wijn niet gevonden."})
                    return
                cur.execute("DELETE FROM wines WHERE id=%s", (wine_id,))
            conn.commit()
        self.json_response(200, {"ok": True, "wines": load_wines()})
