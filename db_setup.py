"""
Eenmalig uitvoeren om:
1. Het PostgreSQL-schema aan te maken in Neon
2. Optioneel: bestaande wijnen migreren vanuit wijn.db (SQLite)

Gebruik:
  pip install psycopg2-binary python-dotenv
  python db_setup.py                   # alleen schema aanmaken
  python db_setup.py --migrate         # schema + data vanuit ../wijn/wijn.db
"""
import os
import sys
import argparse

# Laad .env als die aanwezig is
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DATABASE_URL = os.environ.get("DATABASE_URL", "")
if not DATABASE_URL:
    print("Fout: DATABASE_URL is niet ingesteld. Zet hem in .env of als omgevingsvariabele.")
    sys.exit(1)

import psycopg2
import psycopg2.extras


def create_schema(conn):
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
    print("Schema aangemaakt (of al aanwezig).")


def migrate_from_sqlite(conn, sqlite_path: str):
    import sqlite3
    if not os.path.exists(sqlite_path):
        print(f"SQLite-bestand niet gevonden: {sqlite_path}")
        return
    src = sqlite3.connect(sqlite_path)
    src.row_factory = sqlite3.Row
    rows = src.execute(
        "SELECT * FROM wines WHERE name IS NOT NULL AND name != '' ORDER BY id"
    ).fetchall()
    src.close()

    with conn.cursor() as cur:
        count = 0
        for r in rows:
            cur.execute("""
                INSERT INTO wines (name,type,grape,country,region,year,quantity,
                    vivino,purchaseprice,purchasevalue,currentprice,currentvalue,
                    note,cabinet,score,suppliername,suppliercontact,supplieraddress,
                    supplierphone,supplieremail,suckling,updatedat)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT DO NOTHING
            """, (
                r["name"], r["type"], r["grape"], r["country"], r["region"],
                r["year"], r["quantity"], r["vivino"],
                r["purchasePrice"], r["purchaseValue"],
                r["currentPrice"], r["currentValue"],
                r["note"], r["cabinet"], r["score"],
                r["supplierName"], r["supplierContact"], r["supplierAddress"],
                r["supplierPhone"], r["supplierEmail"],
                r["suckling"], r["updatedAt"] or 0,
            ))
            count += 1
    conn.commit()
    print(f"{count} wijnen gemigreerd vanuit {sqlite_path}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--migrate", action="store_true", help="Migreer data vanuit ../wijn/wijn.db")
    parser.add_argument("--sqlite", default=os.path.expanduser("~/wijn/wijn.db"), help="Pad naar SQLite-bestand")
    args = parser.parse_args()

    conn = psycopg2.connect(DATABASE_URL)
    try:
        create_schema(conn)
        if args.migrate:
            migrate_from_sqlite(conn, args.sqlite)
    finally:
        conn.close()
    print("Klaar.")
