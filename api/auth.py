import sys, os, json, traceback
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from lib.helpers import BaseHandler
from lib.auth import (
    hash_password, verify_password, make_token, verify_token,
    get_token_from_request, check_auth, require_admin,
    set_auth_cookie, clear_auth_cookie,
    generate_totp_secret, get_totp_uri, verify_totp,
    make_challenge_token, verify_challenge_token,
)
from lib.db import (
    ensure_users_schema, get_user, list_users, create_user,
    delete_user, update_password, count_users, count_admins,
    get_totp_secret, set_totp_secret,
)
from urllib.parse import urlparse, parse_qs


def _valid_username(s: str) -> bool:
    return bool(s) and len(s) <= 100 and all(c.isalnum() or c in "-_.@+" for c in s)


def _send_authed(handler, username: str, role: str):
    """Stuur 200-response met auth-cookie, gebruik dezelfde headers-flow als json_response."""
    token = make_token(username, role)
    body = json.dumps({"ok": True, "username": username, "role": role}, ensure_ascii=False).encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    set_auth_cookie(handler, token)
    handler.end_headers()
    handler.wfile.write(body)


class handler(BaseHandler):

    def do_GET(self):
        try:
            self._do_GET()
        except Exception:
            self.json_response(500, {"message": "Serverfout: " + traceback.format_exc()})

    def _do_GET(self):
        parsed = urlparse(self.path)
        action = parse_qs(parsed.query).get("action", [""])[0]

        if action == "status":
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
                ensure_users_schema()
                totp_secret = get_totp_secret(username)
                self.json_response(200, {"ok": True, "username": username, "role": role, "totpEnabled": bool(totp_secret)})
                return
        self.json_response(401, {"message": "Niet ingelogd."})

    def do_POST(self):
        try:
            self._do_POST()
        except Exception:
            self.json_response(500, {"message": "Serverfout: " + traceback.format_exc()})

    def _do_POST(self):
        parsed = urlparse(self.path)
        action = parse_qs(parsed.query).get("action", ["login"])[0]

        # ── Uitloggen ──────────────────────────────────────────────────────────
        if action == "logout":
            body = b'{"ok":true}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            clear_auth_cookie(self)
            self.end_headers()
            self.wfile.write(body)
            return

        # ── Eerste admin aanmaken ──────────────────────────────────────────────
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
                self.json_response(400, {"message": "Ongeldig e-mailadres."})
                return
            if len(password) < 8:
                self.json_response(400, {"message": "Wachtwoord te kort (minimaal 8 tekens)."})
                return
            pw_hash = hash_password(password)
            create_user(username, pw_hash, "admin")
            _send_authed(self, username, "admin")
            return

        # ── 2FA verificatie na wachtwoord-check ───────────────────────────────
        if action == "verify-2fa":
            try:
                data = self.read_json()
                challenge = (data.get("challengeToken") or "").strip()
                code      = (data.get("code") or "").strip()
            except Exception:
                self.json_response(400, {"message": "Ongeldige request."})
                return
            username = verify_challenge_token(challenge)
            if not username:
                self.json_response(401, {"message": "Sessie verlopen. Log opnieuw in."})
                return
            ensure_users_schema()
            secret = get_totp_secret(username)
            if not secret or not verify_totp(secret, code):
                self.json_response(401, {"message": "Onjuiste verificatiecode."})
                return
            user = get_user(username)
            _send_authed(self, username, user["role"])
            return

        # ── 2FA instellen: genereer geheim ────────────────────────────────────
        if action == "setup-2fa":
            auth = check_auth(self)
            if not auth:
                return
            username = auth[0]
            ensure_users_schema()
            if get_totp_secret(username):
                self.json_response(409, {"message": "2FA is al ingeschakeld. Schakel het eerst uit."})
                return
            secret = generate_totp_secret()
            uri    = get_totp_uri(secret, username)
            self.json_response(200, {"secret": secret, "uri": uri})
            return

        # ── 2FA bevestigen: code controleren en opslaan ───────────────────────
        if action == "confirm-2fa":
            auth = check_auth(self)
            if not auth:
                return
            username = auth[0]
            try:
                data   = self.read_json()
                secret = (data.get("secret") or "").strip()
                code   = (data.get("code") or "").strip()
            except Exception:
                self.json_response(400, {"message": "Ongeldige request."})
                return
            if not verify_totp(secret, code):
                self.json_response(400, {"message": "Onjuiste code. Probeer opnieuw."})
                return
            ensure_users_schema()
            set_totp_secret(username, secret)
            self.json_response(200, {"ok": True})
            return

        # ── 2FA uitschakelen ──────────────────────────────────────────────────
        if action == "disable-2fa":
            auth = check_auth(self)
            if not auth:
                return
            current_username, current_role = auth
            try:
                data   = self.read_json()
                target = (data.get("username") or current_username).strip()
            except Exception:
                target = current_username
            if target != current_username and current_role != "admin":
                self.json_response(403, {"message": "Geen toegang."})
                return
            ensure_users_schema()
            set_totp_secret(target, None)
            self.json_response(200, {"ok": True})
            return

        # ── Gebruiker toevoegen (admin) ────────────────────────────────────────
        if action == "add-user":
            auth = require_admin(self)
            if not auth:
                return
            ensure_users_schema()
            try:
                data     = self.read_json()
                username = (data.get("username") or "").strip()
                password = (data.get("password") or "").strip()
                role     = (data.get("role") or "readonly").strip()
            except Exception:
                self.json_response(400, {"message": "Ongeldige request."})
                return
            if not _valid_username(username):
                self.json_response(400, {"message": "Ongeldig e-mailadres."})
                return
            if len(password) < 8:
                self.json_response(400, {"message": "Wachtwoord te kort (minimaal 8 tekens)."})
                return
            if role not in ("admin", "readonly"):
                role = "readonly"
            if get_user(username):
                self.json_response(409, {"message": "Dit e-mailadres is al in gebruik."})
                return
            create_user(username, hash_password(password), role)
            self.json_response(200, {"ok": True, "users": list_users()})
            return

        # ── Wachtwoord wijzigen ────────────────────────────────────────────────
        if action == "change-password":
            auth = check_auth(self)
            if not auth:
                return
            current_username, current_role = auth
            try:
                data   = self.read_json()
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

        # ── Standaard: inloggen ────────────────────────────────────────────────
        try:
            data     = self.read_json()
            username = (data.get("username") or "").strip()
            password = (data.get("password") or "").strip()
        except Exception:
            self.json_response(400, {"message": "Ongeldige request."})
            return

        if not username or not password:
            self.json_response(400, {"message": "E-mailadres en wachtwoord zijn vereist."})
            return

        ensure_users_schema()
        user = get_user(username)
        if not user or not verify_password(password, user["password_hash"]):
            self.json_response(401, {"message": "Onjuist e-mailadres of wachtwoord."})
            return

        secret = get_totp_secret(username)
        if secret:
            challenge = make_challenge_token(username)
            self.json_response(200, {"require2fa": True, "challengeToken": challenge})
            return

        _send_authed(self, username, user["role"])

    def do_DELETE(self):
        try:
            self._do_DELETE()
        except Exception:
            self.json_response(500, {"message": "Serverfout: " + traceback.format_exc()})

    def _do_DELETE(self):
        auth = require_admin(self)
        if not auth:
            return
        current_username = auth[0]
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        username = (params.get("username", [""])[0]).strip()
        if not username:
            self.json_response(400, {"message": "E-mailadres is vereist."})
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
