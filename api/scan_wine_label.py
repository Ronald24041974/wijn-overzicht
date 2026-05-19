import sys, os, re, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from lib.auth import check_auth
from lib.helpers import BaseHandler, get_anthropic_client


def _scan_label(image_b64: str) -> dict:
    client = get_anthropic_client()
    vision_resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=600,
        messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": image_b64}},
            {"type": "text", "text": (
                "Je ziet een foto van een wijnfles of wijn-etiket. "
                "Lees het etiket en identificeer de wijn zo nauwkeurig mogelijk. "
                "Geef UITSLUITEND dit JSON-object terug:\n"
                '{"name":"volledige wijnnaam zoals op etiket","type":"Rood","grape":"Cabernet Sauvignon",'
                '"country":"Frankrijk","region":"Bordeaux","year":2020,"vivino":4.1,"currentPrice":35.0,'
                '"note":"Korte smaakbeschrijving max 120 tekens."}\n\n'
                "Regels:\n"
                "- name: producent + wijnnaam + appellation, zo volledig mogelijk\n"
                "- type: kies EXACT uit: Rood, Wit, Rosé, Mousserende, Dessertwijn\n"
                "- country: altijd in het Nederlands (France→Frankrijk, Italy→Italië, Spain→Spanje)\n"
                "- year: oogstjaar als geheel getal of null\n"
                "- vivino: realistische Vivino-score (3.5–4.8) of null\n"
                "- currentPrice: geschatte marktprijs EUR of null\n"
                "- note: smaakprofiel of herkomstinfo, max 120 tekens\n"
                "Geen uitleg, alleen JSON."
            )},
        ]}],
    )
    text = vision_resp.content[0].text.strip()
    if "```" in text:
        parts = text.split("```")
        text = parts[1].lstrip("json").strip() if len(parts) > 1 else parts[0]
    m = re.search(r'\{.*?\}', text, re.DOTALL)
    if not m:
        raise ValueError("Kon geen wijndata herkennen op het etiket.")
    data = json.loads(m.group())

    wine_name = data.get("name", "")
    if wine_name:
        try:
            year_str = f" {int(data['year'])}" if data.get("year") else ""
            search_query = f"{wine_name}{year_str} vivino james suckling rating price"
            web_resp = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=400,
                tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}],
                messages=[{"role": "user", "content": (
                    f'Zoek op Vivino en jamessuckling.com: "{search_query}". '
                    'Geef UITSLUITEND dit JSON terug:\n'
                    '{"vivino":4.2,"suckling":95,"currentPrice":28.5,"region":"Bourgogne","grape":"Pinot Noir","note":"max 120 tekens"}\n'
                    "Vul alleen in wat je online kunt verifiëren. Geen uitleg."
                )}],
            )
            for block in web_resp.content:
                if getattr(block, "type", "") == "text" and block.text:
                    wtext = block.text.strip()
                    if "```" in wtext:
                        parts = wtext.split("```")
                        wtext = parts[1].lstrip("json").strip() if len(parts) > 1 else wtext
                    wm = re.search(r'\{[^}]+\}', wtext, re.DOTALL)
                    if wm:
                        enriched = json.loads(wm.group())
                        for key, val in enriched.items():
                            if val and (not data.get(key) or key in ("vivino", "suckling", "currentPrice")):
                                data[key] = val
                        break
        except Exception:
            pass
    return data


class handler(BaseHandler):
    def do_POST(self):
        if not check_auth(self): return
        try:
            data = self.read_json()
            image_b64 = (data.get("imageData") or "").strip()
            if not image_b64:
                self.json_response(400, {"message": "imageData is vereist."})
                return
            result = _scan_label(image_b64)
            self.json_response(200, result)
        except Exception as e:
            self.json_response(500, {"message": str(e)})
