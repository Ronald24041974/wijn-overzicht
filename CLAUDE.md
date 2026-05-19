# Wijnoverzicht — werkinstructies voor Claude

## Deployment strategie (verplicht bij elke sessie)

Elke nieuwe feature of bugfix volgt dit vaste proces:

1. **Feature branch aanmaken**
   ```
   git checkout -b feature/<korte-naam>
   ```

2. **Code schrijven en committen op de feature branch**
   - Commits mogen tussentijds, logisch gegroepeerd
   - Nooit direct op `main` werken

3. **Lokaal testen — wacht op akkoord van de gebruiker**
   - Start de lokale dev-server: `npx vercel dev` (vanuit `/Users/ronaldvanrooijen/wijn-vercel/`)
   - Meld aan de gebruiker dat de feature klaar is om te testen op `http://localhost:3000`
   - **Wacht op expliciete goedkeuring** voordat verder gegaan wordt

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
   - Vercel deployt automatisch zodra `main` gepusht wordt
   - Bevestig de live deploy door de productie-URL te testen

## Projectoverzicht

- **Stack**: Vanilla JS PWA (geen framework) + Python serverless functies op Vercel + Neon PostgreSQL
- **Vercel limiet**: max 12 serverless functies in `api/`; gedeelde code staat in `lib/` (meegenomen via `vercel.json` → `includeFiles: "lib/**"`)
- **Auth**: HMAC-SHA256 tokens in HttpOnly Secure cookies (30 dagen); PBKDF2 wachtwoorden; optionele TOTP 2FA (RFC 6238, puur stdlib)
- **Taal**: communiceer altijd in het Nederlands met de gebruiker

## Lokale dev-server

```bash
cd /Users/ronaldvanrooijen/wijn-vercel
npx vercel dev
```

Vereist: `ANTHROPIC_API_KEY`, `DATABASE_URL`, `AUTH_SECRET` als environment variables (via `.env` of Vercel dashboard).
