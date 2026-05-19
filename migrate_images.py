"""
Migreert afbeeldingen vanuit ~/wijn/cache/images/ naar de Neon-database.
Gebruik: python3 migrate_images.py
"""
import os, re, sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "")
if not DATABASE_URL:
    print("Fout: DATABASE_URL niet ingesteld.")
    sys.exit(1)

CACHE_DIR = Path.home() / "wijn" / "cache" / "images"

def sanitize_filename(name: str) -> str:
    name = name.lower().strip()
    name = re.sub(r"[^\w\s-]", "", name)
    name = re.sub(r"[\s_-]+", "_", name)
    return name[:80]

conn = psycopg2.connect(DATABASE_URL)
conn.cursor_factory = psycopg2.extras.RealDictCursor

with conn.cursor() as cur:
    cur.execute("SELECT id, name FROM wines WHERE name IS NOT NULL")
    wines = cur.fetchall()

updated = 0
missing = 0

for wine in wines:
    name = wine["name"]
    wine_id = wine["id"]
    slug = sanitize_filename(name)

    img_path   = CACHE_DIR / f"{slug}.png"
    thumb_path = CACHE_DIR / f"{slug}_thumb.png"

    img_data   = img_path.read_bytes()   if img_path.exists()   else None
    thumb_data = thumb_path.read_bytes() if thumb_path.exists() else None

    if img_data or thumb_data:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE wines SET image_data=%s, thumb_data=%s WHERE id=%s",
                (img_data, thumb_data, wine_id)
            )
        updated += 1
        print(f"  ✓ {name}")
    else:
        missing += 1
        print(f"  - geen afbeelding: {name} (slug: {slug})")

conn.commit()
conn.close()
print(f"\nKlaar: {updated} afbeeldingen gemigreerd, {missing} zonder afbeelding.")
