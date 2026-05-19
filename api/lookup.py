import sys, os, json, re
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from lib.auth import check_auth
from lib.helpers import BaseHandler, get_anthropic_client


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
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    text = message.content[0].text.strip()
    if "```" in text:
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else parts[0]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip().rstrip("`").strip()
    return json.loads(text)


class handler(BaseHandler):
    def do_POST(self):
        if not check_auth(self): return
        try:
            data = self.read_json()
            name = (data.get("name") or "").strip()
            if not name:
                self.json_response(400, {"message": "Naam is vereist."})
                return
            result = _lookup_wine(name)
            self.json_response(200, result)
        except Exception as e:
            self.json_response(500, {"message": str(e)})
