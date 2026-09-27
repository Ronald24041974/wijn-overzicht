# Wijnoverzicht — werkinstructies voor Claude

## Deployment strategie (verplicht bij elke sessie)

Elke nieuwe feature of bugfix volgt dit vaste proces:

1. **Feature branch aanmaken**
   ```
   git checkout -b feature/<korte-naam>
   ```

2. **Code schrijven en committen op de feature branch**

3. **Lokaal testen — wacht op akkoord van de gebruiker**
   ```
   python3 dev_server.py
   ```
   Meld aan de gebruiker dat de feature klaar is om te testen op `http://localhost:3000`.
   **Wacht op expliciete goedkeuring** voordat verder gegaan wordt.

4. **Na akkoord: push feature branch naar remote**
   ```
   git push -u origin feature/<korte-naam>
   ```

5. **Merge naar main**
   ```
   git checkout main
   git merge --no-ff feature/<korte-naam>
   git push origin main
   ```

6. **Vercel deploy**
   Vercel deployt automatisch zodra `main` gepusht wordt.

---

## Projectoverzicht

- **Stack:** Vanilla JS PWA + Python serverless functies (Vercel) + Neon PostgreSQL + 1 Edge Middleware (Node)
- **Repo:** `github.com/Ronald24041974/wijn-overzicht`
- **Productie (2 apps, zelfde repo/project):**
  - `https://wijn-overzicht.vercel.app` → **oude/klassieke app** (`index.html` + `src/app.js`)
  - `https://wijn-overzicht-2.vercel.app` → **nieuwe Apple-redesign** (`kelder.html`), LIVE sinds 2026-06-07
- **Vercel limiet:** max 12 functies in `api/`; gedeelde code in `lib/` via `vercel.json` → `includeFiles: "lib/**"`
- **Vercel timeout:** `maxDuration: 60` voor alle Python-functies (`vercel.json`); web-search-aanroepen
  (drinkvenster 8–15 s, leverancierszoeker 20–40 s) passen niet in de standaard 10 s
- **Taal:** communiceer altijd in het Nederlands met de gebruiker

---

## De twee apps & root-routing

Beide apps draaien uit **één repo / één Vercel-project** (`wijn-overzicht`) en delen dezelfde
`/api/*`-functies en database. Sinds de multi-tenant-migratie (zie verderop) zijn **beide** apps
bijgewerkt: geen van beide is meer "bevroren" — wijzigingen aan rollen/kasten/gebruikersbeheer
moeten in principe in **beide** front-ends worden doorgevoerd.

- **Oude app** — `index.html` + `src/app.js`. Op het hoofddomein. Bevat het enige
  gebruikersbeheer-paneel (toevoegen/verwijderen, 2FA van anderen, "Bekijk kelder" als superadmin).
- **Redesign** — `kelder.html`: fullscreen React-app (React 18 + Babel-in-browser, géén build-stap).
  Eigen login + 2FA (apart domein = eigen cookie-jar), data via `/api/wines`, flesfoto's via
  `/api/wine-thumb?id=` en `/api/wine-image?id=`. Branding heet overal **"Wijnoverzicht"**.
  Heeft géén gebruikersbeheer-paneel — alleen een "Superadmin — kelder bekijken"-sectie in
  het Account-scherm om read-only een andere kelder te bekijken.

**Belangrijk — waarom Edge Middleware:** een `vercel.json`-rewrite `"/" → /kelder.html` werkt NIET,
want Vercel serveert statische bestanden (`index.html`) vóór `rewrites`. Daarom herschrijft
`middleware.ts` (Edge, dep `@vercel/edge` in `package.json`) — die vóór de filesystem draait — de
root `/` naar `/kelder.html` zodra de host `wijn-overzicht-2.vercel.app` is. Hoofddomein → oude app.
Wijzig je de host/routing, pas dan `middleware.ts` aan (niet `vercel.json`).

---

## Deploy-infra (let op)

- GitHub `main` → Vercel-project **`wijn-overzicht`** deployt automatisch. Build draait nu ook
  `npm install` (voor `@vercel/edge`) náást de Python-functies.
- `wijn-overzicht-2.vercel.app` is als **productie-domein** aan het project gekoppeld (anders
  `DEPLOYMENT_NOT_FOUND`, of een Vercel-SSO-loginmuur bij een los alias).
- ⚠️ De lokale `.vercel/project.json` wijst nog naar het **verwijderde** project `wijn-vercel`
  → `vercel`-CLI geeft "Project not found". Onschadelijk; eventueel `npx vercel link` naar
  `wijn-overzicht`.

> Edge Middleware en de host-rewrite kun je niet lokaal testen met `dev_server.py`
> (dat is alleen Python-routing). Verifieer die op de Vercel-deploy zelf.

---

## Authenticatie

- Gebruikers: emailadres als username, rollen `admin` / `readonly` / **`superadmin`**
- Wachtwoorden: PBKDF2-SHA256 (Python stdlib, 100.000 iteraties)
- Sessies: HMAC-SHA256 tokens in HttpOnly Secure cookie `wijn_auth` (30 dagen). **Let op:** de rol
  zit in het token zelf, niet in een live DB-lookup — na een rolwijziging (bv. admin → superadmin
  via een script) moet de gebruiker **uitloggen en opnieuw inloggen** om een vers token te krijgen.
- 2FA: TOTP RFC 6238, puur Python stdlib — geen externe library
- Alle auth-logica in `lib/auth.py` en `api/auth.py`
- Wachtwoord reset via Python-script rechtstreeks op de database (geen UI nodig)

### Rollen (na de multi-tenant-migratie, zie hieronder)

- **`superadmin`** — ziet/beheert alle gebruikers (`api/auth.py` gate: `require_superadmin`), kan
  read-only elke kelder inzien via `?owner=<user_id>` op `/api/wines` en `/api/cabinets`. Er moet
  altijd minstens 1 superadmin overblijven (`count_superadmins()` blokkeert de laatste).
- **`admin`** — volledig beheer over zíjn/haar **eigen** kelder (CRUD op eigen wijnen/kasten), geen
  toegang tot gebruikersbeheer of andermans data. `require_admin` accepteert `admin` én
  `superadmin`.
- **`readonly`** — alleen-lezen op een kelder. Standaard zijn eigen (mogelijk lege) kelder, tenzij
  `users.owner_id` gezet is (zie "Gedeelde leesaccounts").

---

## Multi-tenant: eigen kelder per gebruiker + wijnkasten

Sinds `feature/multi-tenant-cabinets` (gemerged) is dit **geen** single-tenant app meer — elke
gebruiker heeft een eigen, geïsoleerde kelder.

- **`wines.owner_id`** (FK → `users.id`) — elke wijn hoort bij precies één gebruiker. Alle
  wine-endpoints (`api/wines.py`, `api/wine_photo.py`, `api/proposed_*`, `api/image_input.py`,
  `api/wine_images.py`) resolven de effectieve `owner_id` via `lib/db.py: resolve_owner_id()` —
  **nooit** een client-aangeleverde owner vertrouwen, behalve voor superadmin's `?owner=` op
  leesroutes.
- **`cabinets`-tabel** (`id, owner_id, name, sort_order, created_at`) — vervangt de vroegere
  hardgecodeerde `"Wijnkast 1/2/3"` in beide front-ends. Nieuwe gebruikers (rol `admin`, niet
  `superadmin`) krijgen bij hun **eerste login** een onboarding-scherm om zelf het aantal en de
  namen van hun kasten te kiezen (`POST /api/cabinets`), zolang `list_cabinets(owner_id)` leeg is.
- **Gedeelde leesaccounts** — bij "Gebruiker toevoegen" (klassieke app, rol Lezer) kan de
  superadmin een checkbox "Deel mijn eigen kelder" aanvinken → zet `users.owner_id` op de
  aanmakende superadmin. `resolve_owner_id()` geeft dan de kelder van de **gekoppelde** gebruiker
  terug i.p.v. een eigen lege kelder. Alleen relevant voor rol `readonly`.
- **Cascade bij verwijderen** — `delete_user()` in `lib/db.py` ruimt bij het verwijderen van een
  gebruiker ook diens `wines`/`cabinets` op (anders `ForeignKeyViolation`), en zet `owner_id=NULL`
  bij lezers die die kelder deelden (zij vallen terug op hun eigen lege kelder). **Verwijderen van
  een gebruiker met eigen data is dus destructief** — de UI waarschuwt daarvoor in de confirm-dialog.
- **`scripts/migrate_multitenant.py`** — eenmalig migratiescript (al uitgevoerd tegen productie):
  koppelt bestaande eigenaarloze wijnen aan het enige bestaande account, zet dat account op
  `superadmin`, maakt 3 kasten aan ("Wijnkast 1/2/3") zodat de bestaande indeling niet verandert.
  Idempotent, maar gaat ervan uit dat er precies 1 gebruiker is — pas aan als dat niet meer zo is.

---

## Database-onderhoud (GitHub Actions)

- `.github/workflows/db-cleanup.yml` — wekelijkse cronjob (maandag ~03:17 UTC) + handmatig te
  starten (`workflow_dispatch`, met dry-run optie). Draait `scripts/cleanup_stale_images.py`:
  ruimt `proposed_data` (niet-bevestigde afbeeldingsvoorstellen) op die ouder zijn dan 7 dagen.
- Vereist GitHub **repository secret** `DATABASE_URL` (Settings → Secrets and variables →
  Actions) — niet hetzelfde als de Vercel env var, moet apart zijn ingesteld.
- Triggeren vanaf de CLI: `gh workflow run "Database opschonen" -f dry_run=true`.

---

## Claude API-aanroepen (modellen centraal)

Alle modelkeuzes staan in **`lib/helpers.py`** — nooit hardcoden in `api/*.py`:
- `MODEL_FAST = "claude-haiku-4-5"` — snelle tekst-taken zonder web search (`lookup.py`,
  `find_suppliers.py`).
- `MODEL_SMART = "claude-sonnet-5"` — etiket-scan (vision) en alles met web search
  (`scan_wine_label.py`, `fetch_suckling.py`, `wine_images.py`).
- `SMART_OPTS` — `max_tokens=8000`, `thinking={"type":"adaptive"}`, `effort="medium"`. Sonnet 5
  denkt standaard mee en die tokens tellen mee in `max_tokens`; met de oude limieten (200–600)
  werd de JSON afgekapt. Gebruik altijd `**SMART_OPTS` bij Sonnet-aanroepen.
- `message_text(resp)` — leest alle text-blocks; `resp.content[0].text` is fout (kan een
  thinking-block zijn).
- Web search: **`web_search_20250305`** blijven gebruiken. De nieuwere `web_search_20260209`
  (dynamic filtering) is getest en liep structureel tegen 90s+ timeouts — onbruikbaar op Vercel.
- SDK-pin `anthropic==1.7.0` (Python ≥ 3.10). Bij een model-update: alleen de constanten
  aanpassen en één rooktest draaien (zie `/claude-api migrate` voor breekpunten).

---

## Vivino-koppeling (handmatig, altijd met bevestiging)

Sinds `feature/vivino-matching` (live 2026-09-19). Ontwerpkeuzes van de gebruiker: **niets
automatisch, geen cron** — koppelen gebeurt alleen op een expliciete actie en per wijn bevestigd.

- **`lib/vivino.py`** — `find_candidates(name, year, type)` doet **één** POST naar de publieke
  Algolia-zoekindex van vivino.com (`WINES_prod`, search-only sleutel uit hun client-JS; geen
  login, vivino.com zelf wordt niet aangeroepen). Willekeurige pauze 0,3–0,8 s vóór elk request.
  Levert max. 3 kandidaten met `winery`, `region`, `country` (NL), `type`, `alcohol`,
  `yearMatch`/`typeMatch`, score op **jaargang-niveau** als die bestaat (`ratingSource`
  "jaargang"), anders wijnbreed. Kandidaten met kloppend jaar én type staan bovenaan.
- **API** — geen nieuwe Vercel-functie: `POST /api/lookup?action=vivino_search`
  (`{rowNumber}` → `{wine, candidates}`) en `POST /api/lookup?action=vivino_apply`
  (`{rowNumber, candidate}` → `{wine, wines}`). Beide `require_admin`, owner-check via
  `get_wine_row`.
- **DB** — kolommen `producer`, `alcohol`, `vivino_wine_id`, `vivino_vintage_id`,
  `vivino_ratings_count` (via `ensure_wines_columns()`). `apply_vivino_match()` overschrijft
  score/producent/alcohol met de gekozen kandidaat; `region`/`country` alleen als ze leeg waren.
  SELECT-kolommen staan centraal in `WINE_COLS`.
- **Redesign** — knop "Koppel met Vivino" op de detailpagina (`VivinoSheet`, één wijn) en
  Account → "Kelder verrijken → Vivino-matching starten" (zelfde sheet, loopt door alle wijnen
  zonder `vivinoWineId`, kies/overslaan per wijn; de front-end doet dat wijn-voor-wijn zodat het
  tempo natuurlijk blijft en Vercel's tijdslimiet niet geraakt wordt).
- **Klassieke app** — "★ Koppel met Vivino" boven het formulier met hetzelfde kandidatenpaneel;
  `producer` en `alcohol` zijn er bewerkbare velden.
- Vivino levert ook smaakstructuur/aroma's (`/api/wines/{id}/tastes`) — nog niet opgeslagen;
  kandidaat voor wijn-spijsadvies later.
- Voor experimenten in Claude Code is de `vivino` MCP-server lokaal geregistreerd
  (`claude mcp get vivino`; `~/.local/py311/bin/vivino-mcp`, vereist `mcp<2`).

---

## Drinkvenster (live 2026-09-27)

- **DB:** `drink_from`, `drink_to` (INTEGER), `drink_confirmed` (BOOLEAN), `drink_reason` (TEXT).
- **`lib/drinkwindow.py`** — `estimate_drink_window(wine)`: Sonnet 5 met web search (max 3
  zoekopdrachten) zoekt eerst een drinkvenster bij producent/recensenten (Vinous, Wine Advocate,
  Suckling, Decanter …), anders eigen inschatting. De bron staat in `drink_reason`.
- **API:** `POST /api/lookup?action=drink_window` `{rowNumber, force?}`. Slaat op als **schatting**
  (`drink_confirmed=false`). Een bevestigd venster wordt nooit overschreven → 409, tenzij `force`.
- **Bevestigingslogica in `update_wine()`:** handmatig gewijzigde jaren gelden als bevestigd; alleen
  échte wijzigingen tellen (de klassieke app stuurt bij elke save alle velden mee). Bij een
  handmatige wijziging vervalt `drink_reason`.
- **Redesign:** kaart "Drinkvenster" bovenaan de detailpagina (`DrinkWindowCard`) met oordeel in
  gewone taal (`drinkStatus()`), tijdlijn, label schatting/bevestigd, acties Bevestigen /
  Aanpassen / Opnieuw schatten. **Geen bulk-schatting** — per wijn, op verzoek (keuze gebruiker).
- **Klassieke app:** velden van/tot in het formulier, statusregel, knop "Schat drinkvenster".

---

## Spijsadvies (live 2026-09-27)

- **`lib/pairing.py`** — `advise_pairing(wine, messages)`: gesprek over één wijn; de client stuurt
  de hele historie mee (max 12 beurten). Systeemprompt bevat wijngegevens + al bewaarde gerechten.
  Antwoord: `intro`, 3 `dishes` (`dish`, `why`), optionele `question`, en `raw` (om als
  assistant-beurt terug te sturen).
- **API:** `POST /api/lookup?action=pairing` `{rowNumber, messages}`; `pairing_save`
  `{rowNumber, dish, why}`; `pairing_delete` `{rowNumber, pairingId}`.
- **DB:** JSONB-kolom `pairings` (`[{id, dish, why, savedAt}]`), in de redesign gemapt naar `w.spijs`.
- **Redesign:** sectie "Spijs" op de detailpagina (`PairingSection`) + `PairingSheet`: chips met
  voorkeuren in de inhoud, tekstveld onderaan, bijsturen, "Bewaren" per gerecht.
- Alleen in de redesign; de klassieke app heeft geen spijsadvies.

---

## Leverancierszoeker — goedkoopste webshop (live 2026-09-27)

- **`lib/suppliers.py`** — `find_offers(wine, bottles)`: Sonnet 5 met web search (max 6
  zoekopdrachten) zoekt echte productpagina's op NL/BE-webshops. Alleen aanbiedingen met geldige
  URL en prijs; streeft naar ≥ 3 verschillende shops en vult aan met andere jaargangen.
  **`vintageMatch` wordt server-side berekend** (jaar op productpagina vs. gevraagd jaar;
  `null` als onbekend) — het model markeerde afwijkende jaren niet betrouwbaar. Totalen
  (`total`, `totalFor3`) worden zelf berekend zodat het aantal flessen client-side kan wisselen.
  Ontdubbeling op (host, jaargang). Duurt 20–40 s.
- **API:** `POST /api/find-suppliers` `{rowNumber, bottles?}` (owner-check) of losse velden voor
  een nog niet opgeslagen wijn → `{wine, bottles, offers[]}`, goedkoopste eerst.
- **DB:** kolom `supplierurl` (`supplierUrl` in JSON) — link naar de productpagina van de vaste
  leverancier. Alleen via `update_wine()`, niet bij `add_wine()`.
- **Redesign:** `SupplierSheet` (zelfde opzet als `VivinoSheet`): keuze 1/3/6/12 flessen,
  "Bestellen bij <shop>" opent de productpagina in een nieuw venster, "Bewaren als leverancier"
  zet `supplierName` + `supplierUrl`. Bereikbaar via "Bestel" bij lege voorraad en de knop
  "Goedkoopste webshop" onder Leverancier; "Open webshop" als er een URL is. Badge "Goedkoopst"
  alleen bij kloppende jaargang; afwijkend jaar krijgt een amberkleurige badge.
- **Klassieke app:** "Bestel online" gebruikt dezelfde zoeker, met bestel-link en "Bewaren als
  leverancier" per aanbieding; veld "Webshop" in het formulier.
- **Direct in het winkelmandje leggen kan niet** (geen gemeenschappelijke shop-API); de
  productpagina openen is het maximaal haalbare.

---

## Redesign: mobiele valkuilen (`kelder.html`)

- **iOS-toetsenbord:** Safari scrolt de hele pagina omhoog zodra een invoerveld onderaan focus
  krijgt. Daardoor verdween de kop met sluitknop en werd het geparkeerde "Nieuwe fles"-formulier
  (`translateY(102%)`) zichtbaar. Oplossing (script direct na `#root`): app-hoogte volgt
  `window.visualViewport`, pagina blijft op scrollpositie 0, `html/body` hebben `overflow: hidden`,
  het gesloten formulier is `visibility: hidden`. **Gebruik nooit `scrollIntoView()`** in de
  sheets — dat scrolt het document mee; zet `scrollTop` op de eigen lijst.
- Fullscreen-sheets (`VivinoSheet`, `PairingSheet`, `SupplierSheet`) liggen op `zIndex: 90` in
  `WineApp` en hebben elk hun eigen state-variabele (`vivinoQueue`, `pairingWine`, `supplierWine`).
- Lokaal testen op de telefoon: `dev_server.py` bindt op `0.0.0.0`, dus
  `http://<LAN-IP>:3000/kelder.html` werkt (cookie is niet `Secure` in `DEV_MODE`).
- Overzicht: filterchips tonen alleen soorten die in de kelder voorkomen; de statistieken
  (Flessen/Waarde/Gem.) volgen het soortfilter én de zoekopdracht; Vivino-score met merkteken
  (`IcVivino`) naast de kastlocatie. Wijnkasten-scherm: alle kasten standaard ingeklapt.
- Syntax-check van alle Babel-blokken zonder browser: `@babel/parser` met de `jsx`-plugin over elk
  `<script type="text/babel">`-blok (zie eerdere sessies; `node` staat in `~/.local/node/bin`).

---

## Lokale dev-server

```bash
python3 dev_server.py   # poort 3000 — zie Python-versie-waarschuwing hieronder
```

`vercel dev` werkt niet voor Python functies. `dev_server.py` bootst de Vercel-routing na via Python class-swap en laadt `.env` automatisch in.

- Oude app: `http://localhost:3000/`
- Redesign: `http://localhost:3000/kelder.html` (op localhost draait de host-rewrite niet, dus altijd via het pad)

Vereist in `.env`: `DATABASE_URL`, `ANTHROPIC_API_KEY`. De lokale `.env` komt van
`vercel env pull` (waarden tussen aanhalingstekens) — `dev_server.py` stript die. De dev-server
stuurt `Cache-Control: no-store` voor statische bestanden; `index.html` laadt `styles.css`/`app.js`
met een `?v=`-versieparameter — **verhoog die bij CSS/JS-wijzigingen** in de klassieke app.

Let op: `dev_server.py` cachet Python-modules (`importlib.import_module`) — na wijzigingen in
`lib/` of `api/` de server **herstarten**. Draait er nog een oude server op poort 3000 (van een
eerdere sessie), dan houdt die oude code én oude SDK in het geheugen.

⚠️ **Python-versie:** de code gebruikt `X | None`-type-hints (3.10+-syntax), maar het systeem-
`python3` op deze Mac is 3.9.6 — `dev_server.py` crasht daarmee bij het importeren van `lib/db.py`.
Een standalone Python 3.11 staat al geïnstalleerd op `~/.local/py311/bin/python3.11` (via
`python-build-standalone`, geen root nodig). Gebruik die voor lokaal testen:
```bash
~/.local/py311/bin/python3.11 -m pip install -r requirements.txt   # eenmalig
~/.local/py311/bin/python3.11 dev_server.py 3000
```

---

## Tooling die lokaal is nagezet

Deze Mac had standaard geen `gh` of moderne Python — beide zijn los geïnstalleerd (geen sudo):
- `~/.local/bin/gh` — GitHub CLI, ingelogd via device-flow (`gh auth login`). Gebruikt voor
  `git push`/`pull` (SSH-remote, al werkend) en om workflows te triggeren (`gh workflow run`,
  `gh run view`, `gh secret list`).
- `~/.local/py311/bin/python3.11` — zie hierboven.
- Git-remote staat op SSH (`git@github.com:Ronald24041974/wijn-overzicht.git`), niet HTTPS.

---

## Gebruikerspaneel (klassieke app, `src/app.js`)

- Toegankelijk voor **alle** gebruikers (ook readonly) via header-knop
- **Superadmin** ziet extra: gebruikerslijst, gebruiker toevoegen/verwijderen (rol-keuze
  Lezer/Beheerder + "Deel mijn eigen kelder"-checkbox bij Lezer), "Bekijk kelder"-knop per
  gebruiker (schakelt naar `?owner=` read-only weergave, banner + "Terug naar eigen kelder")
- Gewone `admin`/`readonly` zien dit paneel **niet** — alleen eigen accountinstellingen
- Alle gebruikers: wachtwoord wijzigen, 2FA instellen/uitschakelen

---

## Vercel functie-limiet (12 in `api/`) — zit al aan het plafond

Na het toevoegen van `api/cabinets.py` zaten we op 13. `api/wine_thumb.py` en `api/wine_image.py`
zijn daarom samengevoegd tot **`api/wine_photo.py`** (`?variant=thumb|full` query-param,
`vercel.json`-rewrites `/api/wine-thumb`/`/api/wine-image` wijzen daar nu naartoe). We zitten nu
precies op **12 functies** — een nieuwe route toevoegen vereist eerst weer twee bestaande te
mergen, of een bestaande route uit te breiden met een actie/variant-param (zoals hier).
Voorbeelden van dat laatste: `api/auth.py?action=…`, `api/proposed_action.py?action=…`,
`api/lookup.py?action=vivino_search|vivino_apply|drink_window|pairing|pairing_save|pairing_delete`.
