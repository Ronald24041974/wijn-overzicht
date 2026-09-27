"""Online zoeken naar webshops die een wijn aanbieden, gesorteerd op totaalprijs.
Sonnet 5 met web search vindt echte productpagina's; de totalen worden hier
zelf berekend zodat 'aantal flessen' in de app kan wisselen zonder nieuwe zoekopdracht."""
import json
import re
from urllib.parse import urlparse

from lib.helpers import get_anthropic_client, message_text, MODEL_SMART, SMART_OPTS

MAX_OFFERS = 5
MIN_OFFERS = 3


def _total(price: float, shipping: float, free_from, bottles: int) -> float:
    sub = price * bottles
    if free_from and sub >= free_from:
        return round(sub, 2)
    return round(sub + (shipping or 0), 2)


def find_offers(wine: dict, bottles: int = 3) -> list[dict]:
    facts = {
        "naam": wine.get("name"),
        "producent": wine.get("producer"),
        "soort": wine.get("type"),
        "druif": wine.get("grape"),
        "land": wine.get("country"),
        "regio": wine.get("region"),
        "oogstjaar": wine.get("year"),
    }
    facts = {k: v for k, v in facts.items() if v not in (None, "", 0)}

    prompt = (
        "Je zoekt voor een Nederlandse wijnliefhebber online webshops die precies deze wijn verkopen:\n"
        f"{json.dumps(facts, ensure_ascii=False)}\n\n"
        "Werkwijze:\n"
        "- Zoek op Nederlandse en Belgische wijnwebshops (bijv. via wine-searcher.com/nl, vivino.com, "
        "en direct bij shops zoals Grandcruwijnen, Wijnvoordeel, Gall & Gall, Wijnbeurs, Vinoblesse, "
        "Henri Bloem, Okhuysen, Bart's Wijnhuis, Wijnhandel Van Bilsen, Wijnkoperij De Gouden Ton). "
        "Gebruik maximaal 5 zoekopdrachten.\n"
        "- Neem alleen aanbiedingen op waarvan je een echte productpagina hebt gezien met een prijs. "
        "Verzin geen prijzen en geen URL's.\n"
        f"- Streef naar minimaal {MIN_OFFERS} verschillende webshops. Zoek eerst naar precies het gevraagde "
        "oogstjaar; vind je dat bij minder dan 3 shops, vul dan aan met andere oogstjaren van dezelfde wijn.\n"
        "- Geef per aanbieding de URL van de productpagina (niet de homepage), de prijs per fles in euro, "
        "de standaard verzendkosten in Nederland en vanaf welk bedrag verzending gratis is (0 als onbekend).\n"
        "- year: het oogstjaar dat de webshop op de productpagina noemt (null als het er niet staat). "
        "Neem dit letterlijk over, ook als het afwijkt van het gevraagde jaar.\n"
        "- reviewScore/reviewPlatform: alleen als je die op Trustpilot, Google of Kiyoh hebt gezien, anders null.\n"
        "- notes: één korte zin (max 80 tekens), bijv. levertijd of 'per doos van 6'.\n"
        f"Geef na het zoeken UITSLUITEND een JSON-array met maximaal {MAX_OFFERS} aanbiedingen, "
        "goedkoopste eerst:\n"
        '[{"shop": "Naam webshop", "url": "https://...", "pricePerBottle": 24.95, "shipping": 6.95, '
        '"freeShippingFrom": 75, "inStock": true, "year": 2019, '
        '"reviewScore": 4.6, "reviewPlatform": "Trustpilot", "notes": "..."}]'
    )
    client = get_anthropic_client()
    resp = client.messages.create(
        model=MODEL_SMART, **SMART_OPTS,
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 6}],
        messages=[{"role": "user", "content": prompt}],
    )
    text = message_text(resp)
    m = re.search(r"\[\s*\{.*\}\s*\]", text, re.DOTALL)
    if not m:
        return []
    try:
        raw = json.loads(m.group())
    except json.JSONDecodeError:
        return []

    wanted_year = None
    try:
        wanted_year = int(wine.get("year")) if wine.get("year") not in (None, "") else None
    except (TypeError, ValueError):
        wanted_year = None

    offers = []
    for o in raw if isinstance(raw, list) else []:
        if not isinstance(o, dict):
            continue
        url = str(o.get("url") or "").strip()
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            continue
        try:
            price = float(o.get("pricePerBottle"))
        except (TypeError, ValueError):
            continue
        if not (0 < price < 10000):
            continue
        shipping = float(o.get("shipping") or 0)
        free_from = float(o.get("freeShippingFrom") or 0) or None
        score = o.get("reviewScore")
        try:
            score = round(float(score), 1) if score is not None else None
        except (TypeError, ValueError):
            score = None
        # Jaargang zelf vergelijken; het model bleek een afwijkend jaar niet altijd te markeren
        try:
            offer_year = int(o.get("year")) if o.get("year") not in (None, "") else None
        except (TypeError, ValueError):
            offer_year = None
        if wanted_year is None or offer_year is None:
            vintage_match = None            # onbekend: laat de gebruiker het controleren
        else:
            vintage_match = offer_year == wanted_year
        offers.append({
            "shop": str(o.get("shop") or parsed.netloc.replace("www.", "")).strip()[:60],
            "host": parsed.netloc.replace("www.", ""),
            "url": url,
            "pricePerBottle": round(price, 2),
            "shipping": round(shipping, 2),
            "freeShippingFrom": free_from,
            "inStock": o.get("inStock") is not False,
            "year": offer_year,
            "vintageMatch": vintage_match,
            "wantedYear": wanted_year,
            "reviewScore": score if score and 0 < score <= 5 else None,
            "reviewPlatform": (str(o.get("reviewPlatform") or "").strip()[:30] or None),
            "notes": str(o.get("notes") or "").strip()[:120],
            "total": _total(price, shipping, free_from, bottles),
            "totalFor3": _total(price, shipping, free_from, 3),
        })
    # Zelfde shop + zelfde jaargang maar één keer (goedkoopste); andere jaargangen van dezelfde shop blijven aparte opties
    offers.sort(key=lambda x: x["total"])
    seen, unique = set(), []
    for o in offers:
        key = (o["host"], o["year"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(o)
    return unique[:MAX_OFFERS]
