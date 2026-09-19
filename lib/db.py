import os
import psycopg2
import psycopg2.extras
import time


# ── Users table ────────────────────────────────────────────────────────────────

def ensure_users_schema():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id            SERIAL PRIMARY KEY,
                    username      TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role          TEXT NOT NULL DEFAULT 'readonly',
                    created_at    BIGINT DEFAULT 0,
                    totp_secret   TEXT
                )
            """)
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at BIGINT DEFAULT 0")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS totp_secret TEXT")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS owner_id INTEGER REFERENCES users(id)")
        conn.commit()


def get_user(username: str):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, username, password_hash, role, owner_id FROM users WHERE username=%s",
                (username,)
            )
            return cur.fetchone()


def list_users():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, username, role, totp_secret, owner_id FROM users ORDER BY id")
            rows = cur.fetchall()
    return [
        {"id": r["id"], "username": r["username"], "role": r["role"],
         "totpEnabled": bool(r.get("totp_secret")), "sharesOwnerId": r.get("owner_id")}
        for r in rows
    ]


def create_user(username: str, password_hash: str, role: str, owner_id: int = None):
    now = int(time.time())
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (username, password_hash, role, created_at, owner_id) VALUES (%s, %s, %s, %s, %s)",
                (username, password_hash, role, now, owner_id)
            )
        conn.commit()


def delete_user(username: str):
    """Verwijdert de gebruiker mét zijn/haar wijnen en kasten (owner_id-koppeling).
    Lezers die deze kelder deelden (users.owner_id) vallen terug op hun eigen,
    lege kelder i.p.v. mee te crashen op de foreign key."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE username=%s", (username,))
            row = cur.fetchone()
            if not row:
                return
            uid = row["id"]
            cur.execute("UPDATE users SET owner_id=NULL WHERE owner_id=%s", (uid,))
            cur.execute("DELETE FROM wines WHERE owner_id=%s", (uid,))
            cur.execute("DELETE FROM cabinets WHERE owner_id=%s", (uid,))
            cur.execute("DELETE FROM users WHERE id=%s", (uid,))
        conn.commit()


def update_password(username: str, password_hash: str):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET password_hash=%s WHERE username=%s",
                (password_hash, username)
            )
        conn.commit()


def count_users() -> int:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS c FROM users")
            return cur.fetchone()["c"]


def count_superadmins() -> int:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS c FROM users WHERE role='superadmin'")
            return cur.fetchone()["c"]


def get_totp_secret(username: str):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT totp_secret FROM users WHERE username=%s", (username,))
            row = cur.fetchone()
    return row["totp_secret"] if row else None


def set_totp_secret(username: str, secret):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET totp_secret=%s WHERE username=%s", (secret, username))
        conn.commit()


def get_wine_owner(wine_id) -> int | None:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT owner_id FROM wines WHERE id=%s", (wine_id,))
            row = cur.fetchone()
    return row["owner_id"] if row else None


def resolve_owner_id(username: str, role: str, requested_owner=None) -> int:
    """Eigen user-id, tenzij:
    - superadmin een andere owner opvraagt (alleen voor leesdoeleinden), of
    - de gebruiker een 'lezer' is die gekoppeld is aan iemand anders' kelder (owner_id op users)."""
    user = get_user(username)
    own_id = user["id"] if user else None
    if role == "superadmin" and requested_owner not in (None, ""):
        try:
            return int(requested_owner)
        except (TypeError, ValueError):
            return own_id
    if role == "readonly" and user and user.get("owner_id"):
        return user["owner_id"]
    return own_id


def get_db():
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    conn.cursor_factory = psycopg2.extras.RealDictCursor
    return conn


def ensure_wines_columns():
    """Idempotente kolom-toevoeging, los van ensure_schema() (die niet in productie draait)."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("ALTER TABLE wines ADD COLUMN IF NOT EXISTS proposed_at BIGINT DEFAULT 0")
            cur.execute("ALTER TABLE wines ADD COLUMN IF NOT EXISTS owner_id INTEGER REFERENCES users(id)")
            cur.execute("ALTER TABLE wines ADD COLUMN IF NOT EXISTS producer TEXT")
            cur.execute("ALTER TABLE wines ADD COLUMN IF NOT EXISTS alcohol REAL")
            cur.execute("ALTER TABLE wines ADD COLUMN IF NOT EXISTS vivino_wine_id INTEGER")
            cur.execute("ALTER TABLE wines ADD COLUMN IF NOT EXISTS vivino_vintage_id INTEGER")
            cur.execute("ALTER TABLE wines ADD COLUMN IF NOT EXISTS vivino_ratings_count INTEGER")
        conn.commit()


def ensure_cabinets_schema():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS cabinets (
                    id          SERIAL PRIMARY KEY,
                    owner_id    INTEGER REFERENCES users(id),
                    name        TEXT NOT NULL,
                    sort_order  INTEGER DEFAULT 0,
                    created_at  BIGINT DEFAULT 0
                )
            """)
        conn.commit()


def list_cabinets(owner_id: int) -> list:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, sort_order FROM cabinets WHERE owner_id=%s ORDER BY sort_order, id",
                (owner_id,)
            )
            rows = cur.fetchall()
    return [{"id": r["id"], "name": r["name"]} for r in rows]


def create_cabinets(owner_id: int, names: list) -> list:
    now = int(time.time())
    with get_db() as conn:
        with conn.cursor() as cur:
            for i, name in enumerate(names):
                cur.execute(
                    "INSERT INTO cabinets (owner_id, name, sort_order, created_at) VALUES (%s,%s,%s,%s)",
                    (owner_id, name, i, now)
                )
        conn.commit()
    return list_cabinets(owner_id)


def ensure_schema():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS wines (
                    id              SERIAL PRIMARY KEY,
                    name            TEXT,
                    type            TEXT,
                    grape           TEXT,
                    country         TEXT,
                    region          TEXT,
                    year            INTEGER,
                    quantity        INTEGER,
                    vivino          REAL,
                    purchaseprice   REAL,
                    purchasevalue   REAL,
                    currentprice    REAL,
                    currentvalue    REAL,
                    note            TEXT,
                    cabinet         TEXT,
                    score           INTEGER,
                    suppliername    TEXT,
                    suppliercontact TEXT,
                    supplieraddress TEXT,
                    supplierphone   TEXT,
                    supplieremail   TEXT,
                    suckling        REAL,
                    updatedat       BIGINT DEFAULT 0,
                    image_data      BYTEA,
                    thumb_data      BYTEA,
                    proposed_data   BYTEA,
                    proposed_at     BIGINT DEFAULT 0
                )
            """)
        conn.commit()


WINE_COLS = (
    "id,name,type,grape,country,region,year,quantity,vivino,"
    "purchaseprice,purchasevalue,currentprice,currentvalue,note,cabinet,"
    "score,suppliername,suppliercontact,supplieraddress,supplierphone,"
    "supplieremail,suckling,updatedat,producer,alcohol,"
    "vivino_wine_id,vivino_vintage_id,vivino_ratings_count"
)


def serialize_wine(row):
    r = dict(row)
    return {
        "id":              f"wine-{r['id']}",
        "rowNumber":       r["id"],
        "name":            r["name"],
        "type":            r["type"],
        "grape":           r["grape"],
        "country":         r["country"],
        "region":          r["region"],
        "year":            r["year"],
        "quantity":        r["quantity"],
        "vivino":          r["vivino"],
        "purchasePrice":   r["purchaseprice"],
        "purchaseValue":   r["purchasevalue"],
        "currentPrice":    r["currentprice"],
        "currentValue":    r["currentvalue"],
        "note":            r["note"],
        "cabinet":         r["cabinet"],
        "score":           r["score"],
        "supplierName":    r["suppliername"],
        "supplierContact": r["suppliercontact"],
        "supplierAddress": r["supplieraddress"],
        "supplierPhone":   r["supplierphone"],
        "supplierEmail":   r["supplieremail"],
        "suckling":        r["suckling"],
        "updatedAt":       r["updatedat"],
        "producer":        r.get("producer"),
        "alcohol":         r.get("alcohol"),
        "vivinoWineId":    r.get("vivino_wine_id"),
        "vivinoVintageId": r.get("vivino_vintage_id"),
        "vivinoRatingsCount": r.get("vivino_ratings_count"),
    }


def load_wines(owner_id: int):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT " + WINE_COLS + " "
                "FROM wines WHERE owner_id=%s AND name IS NOT NULL AND name != '' ORDER BY id",
                (owner_id,)
            )
            rows = cur.fetchall()
    return [serialize_wine(r) for r in rows]


def number_or_none(value, integer=False):
    if value is None or value == "":
        return None
    try:
        return int(value) if integer else float(value)
    except (ValueError, TypeError):
        return None


def add_wine(data: dict, owner_id: int) -> dict:
    qty = number_or_none(data.get("quantity"), integer=True) or 0
    pp  = number_or_none(data.get("purchasePrice")) or 0
    cp  = number_or_none(data.get("currentPrice")) or 0
    now = int(time.time())
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO wines (name,type,grape,country,region,year,quantity,
                    vivino,purchaseprice,purchasevalue,currentprice,currentvalue,
                    note,cabinet,score,suppliername,suppliercontact,supplieraddress,
                    supplierphone,supplieremail,suckling,updatedat,owner_id,producer,alcohol)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING id
            """, (
                data.get("name") or None,
                data.get("type") or None,
                data.get("grape") or None,
                data.get("country") or None,
                data.get("region") or None,
                number_or_none(data.get("year"), integer=True),
                qty,
                number_or_none(data.get("vivino")),
                pp or None,
                qty * pp if pp else None,
                cp or None,
                qty * cp if cp else None,
                data.get("note") or None,
                data.get("cabinet") or None,
                number_or_none(data.get("score"), integer=True),
                data.get("supplierName") or None,
                data.get("supplierContact") or None,
                data.get("supplierAddress") or None,
                data.get("supplierPhone") or None,
                data.get("supplierEmail") or None,
                number_or_none(data.get("suckling")),
                now,
                owner_id,
                data.get("producer") or None,
                number_or_none(data.get("alcohol")),
            ))
            wine_id = cur.fetchone()["id"]
        conn.commit()
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT " + WINE_COLS + " FROM wines WHERE id=%s", (wine_id,)
            )
            row = cur.fetchone()
    return serialize_wine(row)


def update_wine(data: dict, owner_id: int) -> dict:
    wine_id = int(data.get("rowNumber") or 0)
    if not wine_id:
        raise ValueError("Ongeldig wine ID")
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT " + WINE_COLS + " FROM wines WHERE id=%s AND owner_id=%s",
                (wine_id, owner_id)
            )
            existing = cur.fetchone()
    if not existing:
        raise ValueError(f"Wijn ID {wine_id} niet gevonden")
    ex = dict(existing)

    def _pick(key, db_key=None):
        db = db_key or key.lower()
        return (data[key] or None) if key in data else ex.get(db)

    qty = number_or_none(data.get("quantity"), integer=True) if "quantity" in data else (ex.get("quantity") or 0)
    qty = qty or 0
    pp  = number_or_none(data.get("purchasePrice")) if "purchasePrice" in data else ex.get("purchaseprice")
    cp  = number_or_none(data.get("currentPrice"))  if "currentPrice"  in data else ex.get("currentprice")
    quantity_only = set(data.keys()) <= {"rowNumber", "quantity"}
    now = ex.get("updatedat") if quantity_only else int(time.time())

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE wines SET
                    name=%s,type=%s,grape=%s,country=%s,region=%s,year=%s,quantity=%s,
                    vivino=%s,purchaseprice=%s,purchasevalue=%s,currentprice=%s,currentvalue=%s,
                    note=%s,cabinet=%s,score=%s,suppliername=%s,suppliercontact=%s,
                    supplieraddress=%s,supplierphone=%s,supplieremail=%s,suckling=%s,updatedat=%s,
                    producer=%s,alcohol=%s
                WHERE id=%s AND owner_id=%s
            """, (
                _pick("name"),
                _pick("type"),
                _pick("grape"),
                _pick("country"),
                _pick("region"),
                number_or_none(data.get("year"), integer=True) if "year" in data else ex.get("year"),
                qty,
                number_or_none(data.get("vivino")) if "vivino" in data else ex.get("vivino"),
                pp,
                (qty * pp) if (pp and qty) else None,
                cp,
                (qty * cp) if (cp and qty) else None,
                _pick("note"),
                _pick("cabinet"),
                number_or_none(data.get("score"), integer=True) if "score" in data else ex.get("score"),
                _pick("supplierName", "suppliername"),
                _pick("supplierContact", "suppliercontact"),
                _pick("supplierAddress", "supplieraddress"),
                _pick("supplierPhone", "supplierphone"),
                _pick("supplierEmail", "supplieremail"),
                number_or_none(data.get("suckling")) if "suckling" in data else ex.get("suckling"),
                now,
                _pick("producer"),
                number_or_none(data.get("alcohol")) if "alcohol" in data else ex.get("alcohol"),
                wine_id,
                owner_id,
            ))
        conn.commit()
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT " + WINE_COLS + " FROM wines WHERE id=%s", (wine_id,)
            )
            row = cur.fetchone()
    return serialize_wine(row)


def get_wine_row(wine_id: int, owner_id: int):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT " + WINE_COLS + " FROM wines WHERE id=%s AND owner_id=%s", (wine_id, owner_id))
            row = cur.fetchone()
    return serialize_wine(row) if row else None


def apply_vivino_match(wine_id: int, owner_id: int, c: dict) -> dict:
    """Schrijft een door de gebruiker bevestigde Vivino-kandidaat weg.
    Regio/land worden alleen ingevuld als ze bij ons nog leeg zijn."""
    rating = number_or_none(c.get("rating"))
    if rating is not None and not (0 < rating <= 5):
        raise ValueError("Ongeldige Vivino-score")
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE wines SET
                    vivino=COALESCE(%s, vivino),
                    producer=COALESCE(%s, producer),
                    alcohol=COALESCE(%s, alcohol),
                    region=COALESCE(NULLIF(region,''), %s),
                    country=COALESCE(NULLIF(country,''), %s),
                    vivino_wine_id=%s, vivino_vintage_id=%s, vivino_ratings_count=%s,
                    updatedat=%s
                WHERE id=%s AND owner_id=%s
            """, (
                rating,
                (c.get("winery") or "").strip() or None,
                number_or_none(c.get("alcohol")),
                (c.get("region") or "").strip() or None,
                (c.get("country") or "").strip() or None,
                number_or_none(c.get("wineId"), integer=True),
                number_or_none(c.get("vintageId"), integer=True),
                number_or_none(c.get("ratingsCount"), integer=True),
                int(time.time()),
                wine_id, owner_id,
            ))
            if cur.rowcount == 0:
                raise ValueError(f"Wijn ID {wine_id} niet gevonden")
        conn.commit()
    return get_wine_row(wine_id, owner_id)
