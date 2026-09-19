"""Kandidaten zoeken op Vivino via de Algolia-zoekindex die vivino.com zelf gebruikt.

Eén request per wijn; de hit bevat winery, regio, type, alcohol en per jaargang
de score, dus vivino.com zelf hoeft niet aangeroepen te worden. Niets wordt
automatisch overgenomen — de gebruiker bevestigt altijd een kandidaat.
"""
import json
import random
import time
import urllib.request
from urllib.parse import urlencode

# Publieke search-only sleutel uit de client-JS van vivino.com (index WINES_prod).
ALGOLIA_APP_ID = "9TAKGWJUXL"
ALGOLIA_API_KEY = "60c11b2f1068885161d95ca068d3a6ae"
ALGOLIA_INDEX = "WINES_prod"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15"

TYPE_BY_ID = {1: "Rood", 2: "Wit", 3: "Mousserende", 4: "Rosé", 7: "Dessertwijn", 24: "Dessertwijn"}

COUNTRY_NL = {
    "fr": "Frankrijk", "it": "Italië", "es": "Spanje", "pt": "Portugal", "de": "Duitsland",
    "at": "Oostenrijk", "za": "Zuid-Afrika", "us": "Verenigde Staten", "ar": "Argentinië",
    "cl": "Chili", "au": "Australië", "nz": "Nieuw-Zeeland", "gr": "Griekenland",
    "hu": "Hongarije", "ch": "Zwitserland", "nl": "Nederland", "be": "België",
    "gb": "Verenigd Koninkrijk", "ca": "Canada", "uy": "Uruguay", "lb": "Libanon",
    "ge": "Georgië", "si": "Slovenië", "hr": "Kroatië", "ro": "Roemenië", "bg": "Bulgarije",
}


def _search(query: str, hits: int = 5) -> list:
    time.sleep(random.uniform(0.3, 0.8))
    body = json.dumps({"params": urlencode({"query": query, "hitsPerPage": hits})}).encode()
    req = urllib.request.Request(
        f"https://{ALGOLIA_APP_ID}-dsn.algolia.net/1/indexes/{ALGOLIA_INDEX}/query",
        data=body, method="POST",
        headers={
            "x-algolia-application-id": ALGOLIA_APP_ID,
            "x-algolia-api-key": ALGOLIA_API_KEY,
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
    )
    with urllib.request.urlopen(req, timeout=12) as r:
        return json.load(r).get("hits") or []


def _num(v):
    try:
        f = float(v)
        return f if f > 0 else None
    except (TypeError, ValueError):
        return None


def _candidate(hit: dict, year, wtype) -> dict:
    winery = hit.get("winery") or {}
    region = hit.get("region") or {}
    stats = hit.get("statistics") or {}
    image = hit.get("image") or {}
    variations = image.get("variations") or {}
    img = variations.get("bottle_medium") or image.get("location")
    if img and img.startswith("//"):
        img = "https:" + img

    wine_id = hit.get("id")
    winery_name = winery.get("name") or ""
    wine_name = hit.get("name") or ""
    full_name = f"{winery_name} {wine_name}".strip() if winery_name and not wine_name.startswith(winery_name) else wine_name

    vintage = None
    if year:
        for v in hit.get("vintages") or []:
            if str(v.get("year")) == str(year):
                vintage = v
                break
    vstats = (vintage or {}).get("statistics") or {}
    vintage_rating = _num(vstats.get("ratings_average")) if vstats.get("status") == "Normal" else None

    if vintage_rating:
        rating, count, source = vintage_rating, vstats.get("ratings_count") or 0, "jaargang"
    else:
        rating, count, source = _num(stats.get("ratings_average")), stats.get("ratings_count") or 0, "wijn"

    vtype = TYPE_BY_ID.get(hit.get("type_id"))
    country_code = (region.get("country") or "").lower()
    url = None
    if wine_id:
        seo = winery.get("seo_name")
        url = f"https://www.vivino.com/{seo}/w/{wine_id}" if seo else f"https://www.vivino.com/w/{wine_id}"
        if vintage:
            url += f"?year={year}"

    return {
        "wineId": wine_id,
        "vintageId": (vintage or {}).get("id"),
        "name": full_name,
        "winery": winery_name or None,
        "region": region.get("name") or None,
        "country": COUNTRY_NL.get(country_code) or (country_code.upper() or None),
        "type": vtype,
        "typeMatch": (vtype == wtype) if (vtype and wtype) else None,
        "yearMatch": bool(vintage) if year else None,
        "nonVintage": bool(hit.get("non_vintage")),
        "rating": round(rating, 1) if rating else None,
        "ratingsCount": int(count),
        "ratingSource": source,
        "alcohol": _num(hit.get("alcohol")),
        "imageUrl": img,
        "url": url,
    }


def find_candidates(name: str, year=None, wtype: str = None, limit: int = 3) -> list:
    hits = _search(name, hits=max(limit + 2, 5))
    cands = [_candidate(h, year, wtype) for h in hits if h.get("id")]
    # Algolia-volgorde is de relevantie; alleen kandidaten met kloppend jaar en type mogen voordringen.
    cands.sort(key=lambda c: (c["yearMatch"] is False, c["typeMatch"] is False))
    return cands[:limit]
