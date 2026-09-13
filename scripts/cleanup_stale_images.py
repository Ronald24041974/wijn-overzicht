"""
Ruimt verweesde 'proposed_data' op: afbeeldingsvoorstellen die nooit bevestigd
of afgewezen zijn en ouder zijn dan --max-age-days.

Gebruik:
  python scripts/cleanup_stale_images.py                  # opruimen, standaard 7 dagen
  python scripts/cleanup_stale_images.py --max-age-days 14
  python scripts/cleanup_stale_images.py --dry-run        # alleen rapporteren, niets wijzigen

Vereist: DATABASE_URL in de omgeving.
"""
import os
import sys
import time
import argparse

import psycopg2
import psycopg2.extras


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-age-days", type=int, default=7)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        print("Fout: DATABASE_URL is niet ingesteld.")
        sys.exit(1)

    cutoff = int(time.time()) - args.max_age_days * 86400

    conn = psycopg2.connect(database_url)
    conn.cursor_factory = psycopg2.extras.RealDictCursor
    try:
        with conn.cursor() as cur:
            cur.execute("ALTER TABLE wines ADD COLUMN IF NOT EXISTS proposed_at BIGINT DEFAULT 0")
        conn.commit()

        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, octet_length(proposed_data) AS bytes "
                "FROM wines WHERE proposed_data IS NOT NULL AND proposed_at > 0 AND proposed_at < %s",
                (cutoff,)
            )
            stale = cur.fetchall()

        total_bytes = sum(r["bytes"] or 0 for r in stale)
        print(f"Gevonden: {len(stale)} verweesd(e) voorstel(len), samen {total_bytes / 1024:.1f} KB "
              f"(ouder dan {args.max_age_days} dagen).")
        for r in stale:
            print(f"  - wine {r['id']} ({r['name']}): {(r['bytes'] or 0) / 1024:.1f} KB")

        if args.dry_run or not stale:
            print("Dry-run: niets aangepast." if args.dry_run else "Niets op te ruimen.")
            return

        with conn.cursor() as cur:
            cur.execute(
                "UPDATE wines SET proposed_data=NULL, proposed_at=0 "
                "WHERE proposed_data IS NOT NULL AND proposed_at > 0 AND proposed_at < %s",
                (cutoff,)
            )
        conn.commit()
        print(f"Opgeruimd: {len(stale)} rij(en), {total_bytes / 1024:.1f} KB vrijgemaakt.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
