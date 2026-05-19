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
                    created_at    BIGINT DEFAULT 0
                )
            """)
        conn.commit()


def get_user(username: str):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, username, password_hash, role FROM users WHERE username=%s",
                (username,)
            )
            return cur.fetchone()


def list_users():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, username, role FROM users ORDER BY id")
            rows = cur.fetchall()
    return [{"id": r["id"], "username": r["username"], "role": r["role"]} for r in rows]


def create_user(username: str, password_hash: str, role: str):
    now = int(time.time())
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (username, password_hash, role, created_at) VALUES (%s, %s, %s, %s)",
                (username, password_hash, role, now)
            )
        conn.commit()


def delete_user(username: str):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM users WHERE username=%s", (username,))
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


def count_admins() -> int:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS c FROM users WHERE role='admin'")
            return cur.fetchone()["c"]


def get_db():
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    conn.cursor_factory = psycopg2.extras.RealDictCursor
    return conn


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
                    proposed_data   BYTEA
                )
            """)
        conn.commit()


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
    }


def load_wines():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id,name,type,grape,country,region,year,quantity,vivino,"
                "purchaseprice,purchasevalue,currentprice,currentvalue,note,cabinet,"
                "score,suppliername,suppliercontact,supplieraddress,supplierphone,"
                "supplieremail,suckling,updatedat "
                "FROM wines WHERE name IS NOT NULL AND name != '' ORDER BY id"
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


def add_wine(data: dict) -> dict:
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
                    supplierphone,supplieremail,suckling,updatedat)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
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
            ))
            wine_id = cur.fetchone()["id"]
        conn.commit()
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id,name,type,grape,country,region,year,quantity,vivino,"
                "purchaseprice,purchasevalue,currentprice,currentvalue,note,cabinet,"
                "score,suppliername,suppliercontact,supplieraddress,supplierphone,"
                "supplieremail,suckling,updatedat FROM wines WHERE id=%s", (wine_id,)
            )
            row = cur.fetchone()
    return serialize_wine(row)


def update_wine(data: dict) -> dict:
    wine_id = int(data.get("rowNumber") or 0)
    if not wine_id:
        raise ValueError("Ongeldig wine ID")
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id,name,type,grape,country,region,year,quantity,vivino,"
                "purchaseprice,purchasevalue,currentprice,currentvalue,note,cabinet,"
                "score,suppliername,suppliercontact,supplieraddress,supplierphone,"
                "supplieremail,suckling,updatedat FROM wines WHERE id=%s", (wine_id,)
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
    now = int(time.time())

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE wines SET
                    name=%s,type=%s,grape=%s,country=%s,region=%s,year=%s,quantity=%s,
                    vivino=%s,purchaseprice=%s,purchasevalue=%s,currentprice=%s,currentvalue=%s,
                    note=%s,cabinet=%s,score=%s,suppliername=%s,suppliercontact=%s,
                    supplieraddress=%s,supplierphone=%s,supplieremail=%s,suckling=%s,updatedat=%s
                WHERE id=%s
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
                wine_id,
            ))
        conn.commit()
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id,name,type,grape,country,region,year,quantity,vivino,"
                "purchaseprice,purchasevalue,currentprice,currentvalue,note,cabinet,"
                "score,suppliername,suppliercontact,supplieraddress,supplierphone,"
                "supplieremail,suckling,updatedat FROM wines WHERE id=%s", (wine_id,)
            )
            row = cur.fetchone()
    return serialize_wine(row)
