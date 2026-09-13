"""
Eenmalige migratie naar multi-tenant: voegt owner_id toe aan wines, maakt de
cabinets-tabel aan, koppelt bestaande wijnen aan het huidige (enige) account en
zet dat account op rol 'superadmin'.

Gebruik:
  python scripts/migrate_multitenant.py --dry-run     # alleen rapporteren
  python scripts/migrate_multitenant.py                # daadwerkelijk uitvoeren

Vereist: DATABASE_URL in de omgeving. Idempotent: bestaande owner_id's en
kasten worden nooit overschreven, alleen ontbrekende data wordt aangevuld.
"""
import os
import sys
import time
import argparse

import psycopg2
import psycopg2.extras


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        print("Fout: DATABASE_URL is niet ingesteld.")
        sys.exit(1)

    conn = psycopg2.connect(database_url)
    conn.cursor_factory = psycopg2.extras.RealDictCursor
    try:
        with conn.cursor() as cur:
            cur.execute("ALTER TABLE wines ADD COLUMN IF NOT EXISTS owner_id INTEGER REFERENCES users(id)")
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

        with conn.cursor() as cur:
            cur.execute("SELECT id, username, role FROM users ORDER BY id")
            users = cur.fetchall()
            cur.execute("SELECT count(*) c FROM wines WHERE owner_id IS NULL")
            unowned = cur.fetchone()["c"]

        print(f"Gebruikers: {len(users)}")
        for u in users:
            print(f"  - {u['id']} {u['username']} ({u['role']})")
        print(f"Wijnen zonder owner_id: {unowned}")

        if len(users) != 1:
            print("Afgebroken: script verwacht precies 1 bestaand account voor deze "
                  "eerste migratie. Pas het script aan als er al meerdere accounts zijn.")
            return

        target = users[0]

        if args.dry_run:
            print(f"Dry-run: zou {unowned} wijn(en) koppelen aan account {target['username']} "
                  f"(id={target['id']}), rol bijwerken naar 'superadmin' (was '{target['role']}'), "
                  "en ontbrekende kasten aanmaken.")
            return

        with conn.cursor() as cur:
            cur.execute("UPDATE wines SET owner_id=%s WHERE owner_id IS NULL", (target["id"],))
            if target["role"] != "superadmin":
                cur.execute("UPDATE users SET role='superadmin' WHERE id=%s", (target["id"],))
            cur.execute("SELECT count(*) c FROM cabinets WHERE owner_id=%s", (target["id"],))
            has_cabinets = cur.fetchone()["c"] > 0
            if not has_cabinets:
                now = int(time.time())
                for i, name in enumerate(["Wijnkast 1", "Wijnkast 2", "Wijnkast 3"]):
                    cur.execute(
                        "INSERT INTO cabinets (owner_id, name, sort_order, created_at) VALUES (%s,%s,%s,%s)",
                        (target["id"], name, i, now)
                    )
        conn.commit()
        print(f"Klaar: {unowned} wijn(en) gekoppeld aan {target['username']}, rol is nu 'superadmin'"
              + ("." if has_cabinets else ", 3 kasten aangemaakt."))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
