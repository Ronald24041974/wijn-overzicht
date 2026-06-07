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
- **Taal:** communiceer altijd in het Nederlands met de gebruiker

---

## De twee apps & root-routing

Beide apps draaien uit **één repo / één Vercel-project** (`wijn-overzicht`) en delen dezelfde
`/api/*`-functies en database.

- **Oude app** — `index.html` + `src/app.js`, op het hoofddomein. Ongewijzigd.
- **Redesign** — `kelder.html`: fullscreen React-app (React 18 + Babel-in-browser, géén build-stap).
  Eigen login + 2FA (apart domein = eigen cookie-jar), data via `/api/wines`, flesfoto's via
  `/api/wine-thumb?id=` en `/api/wine-image?id=`. Branding heet overal **"Wijnoverzicht"**.

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

- Gebruikers: emailadres als username, rollen `admin` / `readonly`
- Wachtwoorden: PBKDF2-SHA256 (Python stdlib, 100.000 iteraties)
- Sessies: HMAC-SHA256 tokens in HttpOnly Secure cookie `wijn_auth` (30 dagen)
- 2FA: TOTP RFC 6238, puur Python stdlib — geen externe library
- Alle auth-logica in `lib/auth.py` en `api/auth.py`
- Wachtwoord reset via Python-script rechtstreeks op de database (geen UI nodig)

---

## Lokale dev-server

```bash
python3 dev_server.py   # poort 3000
```

`vercel dev` werkt niet voor Python functies. `dev_server.py` bootst de Vercel-routing na via Python class-swap en laadt `.env` automatisch in.

- Oude app: `http://localhost:3000/`
- Redesign: `http://localhost:3000/kelder.html` (op localhost draait de host-rewrite niet, dus altijd via het pad)

Vereist in `.env`: `DATABASE_URL`, `ANTHROPIC_API_KEY`

---

## Gebruikerspaneel

- Toegankelijk voor **alle** gebruikers (ook readonly) via header-knop
- Admins zien extra: gebruikerslijst, gebruiker toevoegen/verwijderen
- Alle gebruikers: wachtwoord wijzigen, 2FA instellen/uitschakelen
