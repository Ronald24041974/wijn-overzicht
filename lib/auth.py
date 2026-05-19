import hmac, hashlib, time, os, base64

COOKIE_MAX_AGE = 30 * 24 * 3600


def _secret() -> str:
    return os.environ.get("AUTH_SECRET", "changeme-set-auth-secret")


# ── Passwords ─────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
    return base64.b64encode(salt + key).decode()


def verify_password(password: str, stored: str) -> bool:
    try:
        raw = base64.b64decode(stored.encode())
        salt, key = raw[:16], raw[16:]
        new_key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
        return hmac.compare_digest(key, new_key)
    except Exception:
        return False


# ── Tokens ────────────────────────────────────────────────────────────────────
# Format: base64url( username + "\n" + role + "\n" + ts + "\n" + hmac )
# HMAC signs username\x00role\x00ts to avoid separator collisions.

def make_token(username: str, role: str) -> str:
    ts = str(int(time.time()))
    msg = f"{username}\x00{role}\x00{ts}"
    sig = hmac.new(_secret().encode(), msg.encode(), hashlib.sha256).hexdigest()
    payload = f"{username}\n{role}\n{ts}\n{sig}"
    return base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")


def verify_token(token_b64: str):
    """Returns (username, role) or None."""
    try:
        padded = token_b64 + "=" * (4 - len(token_b64) % 4)
        raw = base64.urlsafe_b64decode(padded.encode()).decode()
        username, role, ts, sig = raw.split("\n", 3)
        msg = f"{username}\x00{role}\x00{ts}"
        expected = hmac.new(_secret().encode(), msg.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        if int(time.time()) - int(ts) > COOKIE_MAX_AGE:
            return None
        return (username, role)
    except Exception:
        return None


# ── Cookie helpers ─────────────────────────────────────────────────────────────

def get_token_from_request(handler) -> str | None:
    for part in handler.headers.get("Cookie", "").split(";"):
        name, _, val = part.strip().partition("=")
        if name.strip() == "wijn_auth":
            return val.strip()
    return None


def set_auth_cookie(handler, token: str):
    handler.send_header(
        "Set-Cookie",
        f"wijn_auth={token}; HttpOnly; Secure; SameSite=Strict; Max-Age={COOKIE_MAX_AGE}; Path=/"
    )


def clear_auth_cookie(handler):
    handler.send_header(
        "Set-Cookie",
        "wijn_auth=; HttpOnly; Secure; SameSite=Strict; Max-Age=0; Path=/"
    )


# ── Auth checks ────────────────────────────────────────────────────────────────

def _send_error(handler, status: int, message: str):
    body = f'{{"message":"{message}"}}'.encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    handler.wfile.write(body)


def check_auth(handler):
    """Returns (username, role) or None. Sends 401 if not authenticated."""
    token = get_token_from_request(handler)
    if token:
        result = verify_token(token)
        if result:
            return result
    _send_error(handler, 401, "Niet ingelogd.")
    return None


def require_admin(handler):
    """Returns (username, role) or None. Sends 401 or 403 if not admin."""
    result = check_auth(handler)
    if result is None:
        return None
    username, role = result
    if role != "admin":
        _send_error(handler, 403, "Geen toegang.")
        return None
    return result
