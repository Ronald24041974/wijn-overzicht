import sys, os, json, re
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from urllib.parse import urlparse, parse_qs
from lib.auth import require_admin
from lib.helpers import BaseHandler, get_anthropic_client, message_text, MODEL_FAST
from lib.db import ensure_wines_columns, resolve_owner_id, get_wine_row, apply_vivino_match, load_wines
from lib.vivino import find_candidates


def _lookup_wine(name: str) -> dict:
    client = get_anthropic_client()
    prompt = f"""Je bent een ervaren wijnexpert met toegang tot Vivino, Wine-Searcher en andere wijnbronnen.

Geef informatie over de wijn: "{name}"

Geef UITSLUITEND een geldig JSON-object terug, zonder uitleg of markdown. Gebruik dit formaat:
{{
  "type": "Wit",
  "grape": "Chardonnay",
  "country": "Frankrijk",
  "region": "Bourgogne",
  "year": 2021,
  "vivino": 4.3,
  "currentPrice": 45.0,
  "note": "Korte beschrijving van de wijn, max 120 tekens."
}}

Regels:
- type: kies exact uit Rood, Wit, Rosé, Mousserende of Dessertwijn
- country: altijd in het Nederlands (France → Frankrijk, Italy → Italië enz.)
- year: het jaar als geheel getal als het in de naam staat, anders null
- vivino: realistische score op basis van producent/appellatie, één decimaal (bijv. 4.2)
- currentPrice: actuele marktprijs in EUR als decimaal getal (bijv. 38.5)
- note: beknopte tasting note of herkomstbeschrijving"""

    message = client.messages.create(
        model=MODEL_FAST,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    text = message_text(message)
    if "```" in text:
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else parts[0]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip().rstrip("`").strip()
    return json.loads(text)


class handler(BaseHandler):
    def do_POST(self):
        auth = require_admin(self)
        if not auth: return
        username, role = auth
        action = parse_qs(urlparse(self.path).query).get("action", [""])[0]
        try:
            data = self.read_json()
            if action == "vivino_search":
                self._vivino_search(data, username, role)
            elif action == "vivino_apply":
                self._vivino_apply(data, username, role)
            else:
                name = (data.get("name") or "").strip()
                if not name:
                    self.json_response(400, {"message": "Naam is vereist."})
                    return
                self.json_response(200, _lookup_wine(name))
        except Exception as e:
            self.json_response(500, {"message": str(e)})

    def _wine_for(self, data, username, role):
        ensure_wines_columns()
        owner_id = resolve_owner_id(username, role)
        wine_id = int(data.get("rowNumber") or 0)
        wine = get_wine_row(wine_id, owner_id) if wine_id else None
        if not wine:
            self.json_response(404, {"message": "Wijn niet gevonden."})
            return None, None
        return wine, owner_id

    def _vivino_search(self, data, username, role):
        wine, owner_id = self._wine_for(data, username, role)
        if not wine: return
        candidates = find_candidates(wine["name"], wine.get("year"), wine.get("type"))
        self.json_response(200, {"wine": wine, "candidates": candidates})

    def _vivino_apply(self, data, username, role):
        wine, owner_id = self._wine_for(data, username, role)
        if not wine: return
        cand = data.get("candidate") or {}
        if not cand.get("wineId"):
            self.json_response(400, {"message": "Geen kandidaat gekozen."})
            return
        updated = apply_vivino_match(wine["rowNumber"], owner_id, cand)
        self.json_response(200, {"wine": updated, "wines": load_wines(owner_id)})
