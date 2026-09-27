"""Spijsadvies voor één wijn als doorlopend gesprek: de client stuurt de hele
historie mee (voorkeuren en eerdere voorstellen), zodat de gebruiker kan
blijven bijsturen tot er een passend gerecht is."""
import json
import re

from lib.helpers import get_anthropic_client, message_text, MODEL_SMART, SMART_OPTS

MAX_TURNS = 12


def _system_prompt(wine: dict) -> str:
    facts = {
        "naam": wine.get("name"), "producent": wine.get("producer"), "soort": wine.get("type"),
        "druif": wine.get("grape"), "land": wine.get("country"), "regio": wine.get("region"),
        "oogstjaar": wine.get("year"), "alcohol": wine.get("alcohol"), "vivino_score": wine.get("vivino"),
        "notitie": (wine.get("note") or "")[:200] or None,
        "al_bewaarde_gerechten": [p.get("dish") for p in (wine.get("pairings") or [])] or None,
    }
    facts = {k: v for k, v in facts.items() if v not in (None, "", 0, [])}
    return (
        "Je bent een sommelier die gerechten adviseert bij één specifieke wijn uit de kelder van de "
        "gebruiker. De gebruiker geeft voorkeuren en stuurt bij; jij bouwt voort op het gesprek en herhaalt "
        "geen gerechten die al voorgesteld of bewaard zijn, tenzij daar expliciet om wordt gevraagd.\n\n"
        f"De wijn: {json.dumps(facts, ensure_ascii=False)}\n\n"
        "Regels:\n"
        "- Geef precies 3 concrete gerechten (geen categorieën), passend bij de stijl en structuur van deze "
        "wijn én bij de voorkeuren. Nederlandse namen, met eventueel de oorspronkelijke naam erbij.\n"
        "- waarom: één zin, max 140 tekens, wat in het gerecht de wijn laat schitteren (zuur, vet, umami, "
        "kruiden, textuur). Geen algemeenheden.\n"
        "- intro: één korte zin die reageert op de voorkeur of bijsturing van de gebruiker.\n"
        "- vraag: optioneel één korte vervolgvraag om beter te kunnen adviseren, anders null.\n"
        "Antwoord in het Nederlands en geef UITSLUITEND dit JSON-object terug:\n"
        '{"intro": "...", "gerechten": [{"gerecht": "...", "waarom": "..."}, {"gerecht": "...", "waarom": "..."}, '
        '{"gerecht": "...", "waarom": "..."}], "vraag": null}'
    )


def advise_pairing(wine: dict, messages: list) -> dict:
    turns = []
    for m in messages[-MAX_TURNS:]:
        role = "assistant" if m.get("role") == "assistant" else "user"
        content = str(m.get("content") or "").strip()
        if content:
            turns.append({"role": role, "content": content[:2000]})
    if not turns or turns[-1]["role"] != "user":
        raise ValueError("Geef eerst een voorkeur of vraag op.")

    client = get_anthropic_client()
    resp = client.messages.create(
        model=MODEL_SMART, **SMART_OPTS,
        system=_system_prompt(wine),
        messages=turns,
    )
    text = message_text(resp)
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise ValueError("Geen advies herkend in het antwoord.")
    data = json.loads(m.group())
    dishes = [
        {"dish": str(d.get("gerecht") or "").strip()[:120], "why": str(d.get("waarom") or "").strip()[:300]}
        for d in (data.get("gerechten") or []) if d.get("gerecht")
    ][:3]
    if not dishes:
        raise ValueError("Geen gerechten in het antwoord.")
    return {
        "intro": str(data.get("intro") or "").strip()[:300],
        "dishes": dishes,
        "question": (str(data.get("vraag")).strip()[:200] if data.get("vraag") else None),
        "raw": m.group(),
    }
