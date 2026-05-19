import sys, os, re, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from lib.auth import require_admin
from lib.helpers import BaseHandler, get_anthropic_client


def _fetch_suckling(name: str, year: str = "") -> float | None:
    try:
        client = get_anthropic_client()
    except ValueError:
        return None
    year_str = f" {int(year)}" if year and str(year).strip().isdigit() else ""
    try:
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=200,
            tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 2}],
            messages=[{"role": "user", "content": (
                f'Zoek de James Suckling score voor de wijn "{name}"{year_str}. '
                "Kijk op jamessuckling.com. "
                'Geef ALLEEN dit JSON: {"suckling": 95} of {"suckling": null}. Geen uitleg.'
            )}],
        )
        for block in resp.content:
            if getattr(block, "type", "") == "text" and block.text:
                m = re.search(r'\{[^}]*"suckling"[^}]*\}', block.text, re.DOTALL)
                if m:
                    data = json.loads(m.group())
                    score = data.get("suckling")
                    if score and isinstance(score, (int, float)) and 50 <= float(score) <= 100:
                        return float(score)
    except Exception:
        pass
    return None


class handler(BaseHandler):
    def do_POST(self):
        if not require_admin(self): return
        try:
            data = self.read_json()
            name = (data.get("name") or "").strip()
            year = str(data.get("year") or "").strip()
            if not name:
                self.json_response(400, {"message": "Naam is vereist."})
                return
            score = _fetch_suckling(name, year)
            self.json_response(200, {"suckling": score})
        except Exception as e:
            self.json_response(500, {"message": str(e)})
