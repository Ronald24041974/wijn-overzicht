import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from lib.auth import require_admin
from lib.helpers import BaseHandler
from lib.db import ensure_wines_columns, resolve_owner_id, get_wine_row
from lib.suppliers import find_offers


class handler(BaseHandler):
    """Zoekt online webshops voor een wijn. Body: {rowNumber, bottles?} (eigen wijn, met
    owner-check) of losse velden {name, type, grape, country, region, year} voor een wijn
    die nog niet is opgeslagen. Antwoord: {wine, bottles, offers[]} — goedkoopste eerst."""

    def do_POST(self):
        auth = require_admin(self)
        if not auth: return
        username, role = auth
        try:
            data = self.read_json()
            try:
                bottles = max(1, min(int(data.get("bottles") or 3), 60))
            except (TypeError, ValueError):
                bottles = 3

            wine_id = int(data.get("rowNumber") or 0)
            if wine_id:
                ensure_wines_columns()
                owner_id = resolve_owner_id(username, role)
                wine = get_wine_row(wine_id, owner_id)
                if not wine:
                    self.json_response(404, {"message": "Wijn niet gevonden."})
                    return
            else:
                wine = {k: data.get(k) for k in ("name", "type", "grape", "country", "region", "year", "producer")}
                if not (wine.get("name") or "").strip():
                    self.json_response(400, {"message": "Naam is vereist."})
                    return

            offers = find_offers(wine, bottles)
            self.json_response(200, {"wine": wine, "bottles": bottles, "offers": offers})
        except Exception as e:
            self.json_response(500, {"message": str(e)})
