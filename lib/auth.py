import hmac, hashlib, time, os, base64


def _secret() -> str:
    return os.environ.get("AUTH_SECRET", "changeme-set-auth-secret")


def make_token() -> str:
    ts = str(int(time.time()))
    sig = hmac.new(_secret().encode(), ts.encode(), hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(f"{ts}.{sig}".encode()).decode()


def verify_token(token_b64: str) -> bool:
    try:
        raw = base64.urlsafe_b64decode(token_b64.encode() + b"==").decode()
        ts, sig = raw.split(".", 1)
        expected = hmac.new(_secret().encode(), ts.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return False
        return int(time.time()) - int(ts) < 30 * 24 * 3600
    except Exception:
        return False


def get_token_from_request(handler) -> str | None:
    for part in handler.headers.get("Cookie", "").split(";"):
        name, _, val = part.strip().partition("=")
        if name.strip() == "wijn_auth":
            return val.strip()
    return None


def check_auth(handler) -> bool:
    token = get_token_from_request(handler)
    if token and verify_token(token):
        return True
    body = b'{"message":"Niet ingelogd."}'
    handler.send_response(401)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    handler.wfile.write(body)
    return False


COOKIE_MAX_AGE = 30 * 24 * 3600


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
