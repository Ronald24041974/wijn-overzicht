import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from lib.helpers import BaseHandler
from lib.auth import (
    hash_password, verify_password, make_token, verify_token,
    get_token_from_request, check_auth, require_admin,
    set_auth_cookie, clear_auth_cookie,
)
from lib.db import (
    ensure_users_schema, get_user, list_users, create_user,
    delete_user, update_password, count_users, count_admins,
)
from urllib.parse import urlparse, parse_qs


def _valid_username(s: str) -> bool:
    return bool(s) and len(s) <= 40 and all(c.isalnum() or c in "-_." for c in s)


class handler(BaseHandler):

    def do_GET(self):
        parsed = urlparse(self.path)
        action = parse_qs(parsed.query).get("action", [""])[0]

        if action == "status":
            # Public: geeft terug of er al gebruikers bestaan (voor setup-detectie)
            ensure_users_schema()
            self.json_response(200, {"hasUsers": count_users() > 0})
            return

        if action == "users":
            auth = require_admin(self)
            if not auth:
                return
            ensure_users_schema()
            self.json_response(200, {"users": list_users()})
            return

        token = get_token_from_request(self)
        if token:
            result = verify_token(token)
            if result:
                username, role = result
                self.json_response(200, {"ok": True, "username": username, "role": role})
                return
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

        if action == "setup":
            ensure_users_schema()
            if count_users() > 0:
                self.json_response(409, {"message": "Er bestaan al gebruikers."})
                return
            try:
                data = self.read_json()
                username = (data.get("username") or "").strip()
                password = (data.get("password") or "").strip()
            except Exception:
                self.json_response(400, {"message": "Ongeldige request."})
                return
            if not _valid_username(username):
                self.json_response(400, {"message": "Ongeldige gebruikersnaam (alleen letters, cijfers, - _ .)."})
                return
            if len(password) < 8:
                self.json_response(400, {"message": "Wachtwoord te kort (minimaal 8 tekens)."})
                return
            create_user(username, hash_password(password), "admin")
            token = make_token(username, "admin")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            set_auth_cookie(self, token)
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True, "username": username, "role": "admin"}).encode())
            return

        if action == "add-user":
            auth = require_admin(self)
            if not auth:
                return
            ensure_users_schema()
            try:
                data = self.read_json()
                username = (data.get("username") or "").strip()
                password = (data.get("password") or "").strip()
                role = (data.get("role") or "readonly").strip()
            except Exception:
                self.json_response(400, {"message": "Ongeldige request."})
                return
            if not _valid_username(username):
                self.json_response(400, {"message": "Ongeldige gebruikersnaam."})
                return
            if len(password) < 8:
                self.json_response(400, {"message": "Wachtwoord te kort (minimaal 8 tekens)."})
                return
            if role not in ("admin", "readonly"):
                role = "readonly"
            if get_user(username):
                self.json_response(409, {"message": "Gebruikersnaam al in gebruik."})
                return
            create_user(username, hash_password(password), role)
            self.json_response(200, {"ok": True, "users": list_users()})
            return

        if action == "change-password":
            auth = check_auth(self)
            if not auth:
                return
            current_username, current_role = auth
            try:
                data = self.read_json()
                target = (data.get("username") or current_username).strip()
                new_pw = (data.get("newPassword") or "").strip()
            except Exception:
                self.json_response(400, {"message": "Ongeldige request."})
                return
            if target != current_username and current_role != "admin":
                self.json_response(403, {"message": "Geen toegang."})
                return
            if len(new_pw) < 8:
                self.json_response(400, {"message": "Wachtwoord te kort (minimaal 8 tekens)."})
                return
            ensure_users_schema()
            update_password(target, hash_password(new_pw))
            self.json_response(200, {"ok": True})
            return

        # Default: login
        try:
            data = self.read_json()
            username = (data.get("username") or "").strip()
            password = (data.get("password") or "").strip()
        except Exception:
            self.json_response(400, {"message": "Ongeldige request."})
            return

        if not username or not password:
            self.json_response(400, {"message": "Gebruikersnaam en wachtwoord zijn vereist."})
            return

        ensure_users_schema()
        user = get_user(username)
        if not user or not verify_password(password, user["password_hash"]):
            self.json_response(401, {"message": "Onjuiste gebruikersnaam of wachtwoord."})
            return

        token = make_token(username, user["role"])
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        set_auth_cookie(self, token)
        self.end_headers()
        self.wfile.write(json.dumps({"ok": True, "username": username, "role": user["role"]}).encode())

    def do_DELETE(self):
        auth = require_admin(self)
        if not auth:
            return
        current_username = auth[0]
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        username = (params.get("username", [""])[0]).strip()
        if not username:
            self.json_response(400, {"message": "Gebruikersnaam is vereist."})
            return
        if username == current_username:
            self.json_response(400, {"message": "Je kunt jezelf niet verwijderen."})
            return
        ensure_users_schema()
        user_row = get_user(username)
        if not user_row:
            self.json_response(404, {"message": "Gebruiker niet gevonden."})
            return
        if user_row["role"] == "admin" and count_admins() <= 1:
            self.json_response(400, {"message": "Kan de laatste beheerder niet verwijderen."})
            return
        delete_user(username)
        self.json_response(200, {"ok": True, "users": list_users()})
