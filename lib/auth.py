import hmac, hashlib, time, os, base64, struct

COOKIE_MAX_AGE  = 30 * 24 * 3600
CHALLENGE_MAX_AGE = 5 * 60   # 2FA challenge: 5 minuten


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


# ── TOTP (RFC 6238) — alleen stdlib nodig ─────────────────────────────────────

def generate_totp_secret() -> str:
    return base64.b32encode(os.urandom(20)).decode()


def get_totp_uri(secret: str, username: str) -> str:
    from urllib.parse import quote
    label = quote(f"Wijnoverzicht:{username}")
    return f"otpauth://totp/{label}?secret={secret}&issuer=Wijnoverzicht&digits=6&period=30"


def _hotp(key_bytes: bytes, counter: int) -> str:
    msg = struct.pack(">Q", counter)
    h = hmac.new(key_bytes, msg, hashlib.sha1).digest()
    offset = h[-1] & 0x0F
    code = struct.unpack(">I", h[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(code % 1_000_000).zfill(6)


def verify_totp(secret_b32: str, code: str) -> bool:
    try:
        key = base64.b32decode(secret_b32.upper())
        t = int(time.time()) // 30
        for delta in (-1, 0, 1):
            if hmac.compare_digest(_hotp(key, t + delta), code.strip()):
                return True
        return False
    except Exception:
        return False


# ── Tokens ────────────────────────────────────────────────────────────────────
# Format: base64url( username + "\n" + kind + "\n" + ts + "\n" + hmac )
# kind = role voor auth-tokens, "2fa" voor challenge-tokens

def _make_token(username: str, kind: str) -> str:
    ts = str(int(time.time()))
    msg = f"{username}\x00{kind}\x00{ts}"
    sig = hmac.new(_secret().encode(), msg.encode(), hashlib.sha256).hexdigest()
    payload = f"{username}\n{kind}\n{ts}\n{sig}"
    return base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")


def _verify_token_raw(token_b64: str):
    """Returns (username, kind, ts) or None."""
    try:
        padded = token_b64 + "=" * (4 - len(token_b64) % 4)
        raw = base64.urlsafe_b64decode(padded.encode()).decode()
        username, kind, ts, sig = raw.split("\n", 3)
        msg = f"{username}\x00{kind}\x00{ts}"
        expected = hmac.new(_secret().encode(), msg.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        return (username, kind, int(ts))
    except Exception:
        return None


def make_token(username: str, role: str) -> str:
    return _make_token(username, role)


def verify_token(token_b64: str):
    """Returns (username, role) or None."""
    result = _verify_token_raw(token_b64)
    if not result:
        return None
    username, role, ts = result
    if role in ("2fa",):
        return None
    if int(time.time()) - ts > COOKIE_MAX_AGE:
        return None
    return (username, role)


def make_challenge_token(username: str) -> str:
    return _make_token(username, "2fa")


def verify_challenge_token(token_b64: str) -> str | None:
    """Returns username or None."""
    result = _verify_token_raw(token_b64)
    if not result:
        return None
    username, kind, ts = result
    if kind != "2fa":
        return None
    if int(time.time()) - ts > CHALLENGE_MAX_AGE:
        return None
    return username


# ── Cookie helpers ─────────────────────────────────────────────────────────────

def get_token_from_request(handler) -> str | None:
    for part in handler.headers.get("Cookie", "").split(";"):
        name, _, val = part.strip().partition("=")
        if name.strip() == "wijn_auth":
            return val.strip()
    return None


def _cookie_flags() -> str:
    secure = "" if os.environ.get("DEV_MODE") else " Secure;"
    return f"HttpOnly;{secure} SameSite=Strict"

def set_auth_cookie(handler, token: str):
    handler.send_header(
        "Set-Cookie",
        f"wijn_auth={token}; {_cookie_flags()}; Max-Age={COOKIE_MAX_AGE}; Path=/"
    )


def clear_auth_cookie(handler):
    handler.send_header(
        "Set-Cookie",
        f"wijn_auth=; {_cookie_flags()}; Max-Age=0; Path=/"
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
