import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from lib.helpers import BaseHandler
from lib.auth import make_token, verify_token, get_token_from_request, set_auth_cookie, clear_auth_cookie
from urllib.parse import urlparse, parse_qs


class handler(BaseHandler):

    def do_GET(self):
        token = get_token_from_request(self)
        if token and verify_token(token):
            self.json_response(200, {"ok": True})
        else:
            self.json_response(401, {"message": "Niet ingelogd."})

    def do_POST(self):
        parsed = urlparse(self.path)
        action = parse_qs(parsed.query).get("action", ["login"])[0]

        if action == "logout":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            clear_auth_cookie(self)
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
            return

        try:
            data = self.read_json()
            password = (data.get("password") or "").strip()
        except Exception:
            self.json_response(400, {"message": "Ongeldige request."})
            return

        app_password = os.environ.get("APP_PASSWORD", "")
        if not app_password:
            self.json_response(500, {"message": "APP_PASSWORD is niet ingesteld."})
            return

        if password != app_password:
            self.json_response(401, {"message": "Onjuist wachtwoord."})
            return

        token = make_token()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        set_auth_cookie(self, token)
        self.end_headers()
        self.wfile.write(b'{"ok":true}')
