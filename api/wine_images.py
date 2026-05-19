import sys, os, re, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from lib.auth import check_auth
from lib.helpers import BaseHandler, vivino_search_html, download_image, get_anthropic_client, sanitize_filename
from lib.db import get_db
from lib.image import remove_background, has_transparency, normalize_transparent
from urllib.parse import urlparse, parse_qs, quote

_TYPE_HINTS = {
    "Rood": "red wine bottle",
    "Wit": "white wine bottle",
    "Rosé": "rosé wine bottle",
    "Mousserende": "sparkling wine bottle",
    "Dessertwijn": "dessert wine bottle",
}


def _find_online_and_store_proposed(name: str, wine_type: str, year: str) -> bool:
    try:
        client = get_anthropic_client()
    except ValueError:
        return False
    type_hint = _TYPE_HINTS.get(wine_type, "")
    year_part = f" {year}" if year else ""
    search_label = f"{name}{year_part} {type_hint}".strip()
    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}],
            messages=[{"role": "user", "content": (
                f'Zoek een PRODUCTFOTO van de wijnfles "{search_label}" '
                "(bij voorkeur op witte of neutrale achtergrond). "
                "Kijk op vivino.com, wine-searcher.com, wijnhandel-sites of de producent. "
                "Geef ALLEEN een JSON-array met directe afbeelding-URLs "
                '(.jpg/.jpeg/.png/.webp): ["https://...", "https://..."]. Max 5 URLs. Geen uitleg.'
            )}],
        )
        urls = []
        for block in response.content:
            if getattr(block, "type", "") == "text" and block.text:
                text = block.text.strip()
                if "```" in text:
                    parts = text.split("```")
                    text = parts[1].lstrip("json").strip() if len(parts) > 1 else text
                m = re.search(r'\[.*?\]', text, re.DOTALL)
                if m:
                    try:
                        found = json.loads(m.group())
                        urls = [u for u in found if isinstance(u, str) and u.startswith("http")]
                    except Exception:
                        pass
        for url in urls[:5]:
            img_bytes = download_image(url)
            if not img_bytes or len(img_bytes) < 2000:
                continue
            try:
                processed = remove_background(img_bytes) if not has_transparency(img_bytes) else normalize_transparent(img_bytes)
                with get_db() as conn:
                    with conn.cursor() as cur:
                        cur.execute("UPDATE wines SET proposed_data=%s WHERE name=%s", (processed, name))
                    conn.commit()
                return True
            except Exception:
                continue
    except Exception:
        pass
    return False


class handler(BaseHandler):
    def do_GET(self):
        if not check_auth(self): return
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        name = (params.get("name", [""])[0]).strip()
        wine_type = (params.get("type", [""])[0]).strip()
        year = (params.get("year", [""])[0]).strip()
        if not name:
            self.send_error(400)
            return
        type_hint = _TYPE_HINTS.get(wine_type, "")
        query = f"{name} {type_hint}".strip() if type_hint else name
        html = vivino_search_html(query)
        matches = re.findall(r'bottle_medium&quot;:&quot;(//images\.vivino\.com/thumbs/[^&]+)&quot;', html)
        urls = [f"https:{m}" for m in dict.fromkeys(matches)][:6]
        if urls:
            self.json_response(200, {"images": urls, "source": "vivino", "proposed": None})
            return
        found = _find_online_and_store_proposed(name, wine_type, year)
        proposed_url = f"/api/proposed-image?name={quote(name)}" if found else None
        self.json_response(200, {"images": [], "source": "internet", "proposed": proposed_url})
