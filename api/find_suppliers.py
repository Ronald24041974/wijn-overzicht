import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from lib.auth import require_admin
from lib.helpers import BaseHandler, get_anthropic_client


class handler(BaseHandler):
    def do_POST(self):
        if not require_admin(self): return
        try:
            data = self.read_json()
            client = get_anthropic_client()
            name    = data.get("name", "")
            wtype   = data.get("type", "")
            grape   = data.get("grape", "")
            country = data.get("country", "")
            region  = data.get("region", "")
            year    = data.get("year", "")
            prompt = f"""Je bent een wijnexpert en online shopping specialist voor de Nederlandse markt.

Zoek de 3 tot 5 beste online wijnwinkels (Nederland/België) voor deze wijn:
Naam: "{name}" | Soort: {wtype} | Druif: {grape} | {country} / {region} | Jaar: {year}

Criteria:
1. Betrouwbaarheid & online reviews (Trustpilot, Google Reviews)
2. Goedkoopste TOTAALPRIJS inclusief standaard verzendkosten voor een bestelling van minimaal 3 flessen

Geef UITSLUITEND een geldig JSON-array terug, gesorteerd van goedkoopste naar duurste totalFor3:
[
  {{
    "name": "Winkelnaam",
    "url": "https://...",
    "pricePerBottle": 0.00,
    "shipping": 0.00,
    "freeShippingFrom": 0,
    "totalFor3": 0.00,
    "reviewScore": 4.5,
    "reviewPlatform": "Trustpilot",
    "notes": "Korte toelichting max 80 tekens."
  }}
]"""
            message = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            text = message.content[0].text.strip()
            if "```" in text:
                parts = text.split("```")
                text = parts[1] if len(parts) > 1 else parts[0]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip().rstrip("`").strip()
            self.json_response(200, json.loads(text))
        except Exception as e:
            self.json_response(500, {"message": str(e)})
