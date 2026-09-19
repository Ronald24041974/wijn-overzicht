"""Drinkvenster schatten met Claude. De uitkomst is altijd een *schatting*
(drink_confirmed=False) totdat de gebruiker die bevestigt of zelf aanpast."""
import json
import re
from datetime import date

from lib.helpers import get_anthropic_client, message_text, MODEL_SMART, SMART_OPTS


def estimate_drink_window(wine: dict) -> dict:
    year_now = date.today().year
    facts = {
        "naam": wine.get("name"),
        "producent": wine.get("producer"),
        "soort": wine.get("type"),
        "druif": wine.get("grape"),
        "land": wine.get("country"),
        "regio": wine.get("region"),
        "oogstjaar": wine.get("year"),
        "vivino_score": wine.get("vivino"),
        "alcohol": wine.get("alcohol"),
        "notitie": (wine.get("note") or "")[:200] or None,
    }
    facts = {k: v for k, v in facts.items() if v not in (None, "", 0)}

    prompt = (
        "Je bent een sommelier. Schat het drinkvenster (de jaren waarin deze wijn op zijn best gedronken "
        f"kan worden) voor de wijn hieronder. Het is nu {year_now}.\n\n"
        f"{json.dumps(facts, ensure_ascii=False)}\n\n"
        "Regels:\n"
        "- Baseer je op producent, appellatie/regio, druif, stijl en oogstjaar; houd rekening met het "
        "kwaliteitsniveau (topdomein vs. eenvoudige wijn) en het karakter van het oogstjaar als je dat kent.\n"
        "- Geef één aaneengesloten venster van hele jaren: van het eerste jaar waarin de wijn goed drinkt "
        "tot het laatste jaar waarin hij nog op niveau is. Het venster mag in het verleden liggen.\n"
        "- Zonder oogstjaar (non-vintage): neem aan dat de fles recent is gebotteld.\n"
        "- reden: één zin, maximaal 140 tekens, in het Nederlands, waarom dit venster (stijl, structuur, "
        "rijpingspotentieel). Geen herhaling van de jaartallen.\n"
        'Geef UITSLUITEND dit JSON-object terug: {"drink_from": 2024, "drink_to": 2032, "reden": "..."}'
    )
    client = get_anthropic_client()
    resp = client.messages.create(model=MODEL_SMART, **SMART_OPTS, messages=[{"role": "user", "content": prompt}])
    text = message_text(resp)
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise ValueError("Geen drinkvenster herkend in het antwoord.")
    data = json.loads(m.group())
    frm, to = int(data["drink_from"]), int(data["drink_to"])
    if not (1900 < frm < 2200 and 1900 < to < 2200) or to < frm:
        raise ValueError(f"Onbruikbaar drinkvenster: {frm}–{to}")
    return {"drinkFrom": frm, "drinkTo": to, "reason": str(data.get("reden") or "").strip()[:200]}
