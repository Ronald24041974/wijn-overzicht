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

- **Stack:** Vanilla JS PWA + Python serverless functies (Vercel) + Neon PostgreSQL
- **Repo:** `github.com/Ronald24041974/wijn-overzicht`
- **Productie:** `https://wijn-overzicht.vercel.app`
- **Vercel limiet:** max 12 functies in `api/`; gedeelde code in `lib/` via `vercel.json` → `includeFiles: "lib/**"`
- **Taal:** communiceer altijd in het Nederlands met de gebruiker

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

Vereist in `.env`: `DATABASE_URL`, `ANTHROPIC_API_KEY`

---

## Gebruikerspaneel

- Toegankelijk voor **alle** gebruikers (ook readonly) via header-knop
- Admins zien extra: gebruikerslijst, gebruiker toevoegen/verwijderen
- Alle gebruikers: wachtwoord wijzigen, 2FA instellen/uitschakelen
