import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from lib.auth import check_auth, require_admin
from lib.helpers import BaseHandler
from lib.db import ensure_cabinets_schema, list_cabinets, create_cabinets, resolve_owner_id
from urllib.parse import urlparse, parse_qs


class handler(BaseHandler):
    def do_GET(self):
        auth = check_auth(self)
        if not auth: return
        username, role = auth
        ensure_cabinets_schema()
        parsed = urlparse(self.path)
        requested_owner = parse_qs(parsed.query).get("owner", [None])[0]
        owner_id = resolve_owner_id(username, role, requested_owner)
        self.json_response(200, {"cabinets": list_cabinets(owner_id)})

    def do_POST(self):
        auth = require_admin(self)
        if not auth: return
        username, role = auth
        ensure_cabinets_schema()
        owner_id = resolve_owner_id(username, role)
        try:
            data = self.read_json()
            names = [str(n).strip() for n in (data.get("names") or []) if str(n).strip()]
            if not names:
                self.json_response(400, {"message": "Minimaal 1 wijnkastnaam is vereist."})
                return
            if len(names) > 50:
                self.json_response(400, {"message": "Maximaal 50 wijnkasten."})
                return
            cabinets = create_cabinets(owner_id, names)
            self.json_response(201, {"cabinets": cabinets})
        except Exception as e:
            self.json_response(400, {"message": str(e)})
