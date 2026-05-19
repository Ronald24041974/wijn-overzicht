# Wijnoverzicht – Componentengids

Een overzicht van alle herbruikbare UI-componenten in de app, met visuele beschrijving, CSS-klassen en gebruik.

---

## Knoppen

### Primaire actieknop (Opslaan)
```html
<button class="save-button">Opslaan</button>
```
- Achtergrond: `--c-brand` (#213f39)
- Tekst: wit, 900 gewicht, 0.9rem
- Breedte: 100% van container
- Hoogte: 52px
- Op mobiel: sticky aan onderkant viewport

### Secundaire knop
```html
<button class="secondary-action">Annuleren</button>
```
- Achtergrond: transparant
- Rand: `--c-border`
- Tekst: `--c-brand`

### Gevaar-knop (Verwijderen)
```html
<button class="danger-button">Verwijderen</button>
```
- Achtergrond: `--c-red-dark` (#7f1d1d)
- Tekst: wit

### Stapknop (+ / -)
```html
<button class="step-button" data-step="-1">−</button>
<button class="step-button" data-step="1">+</button>
```
- 44×44px raakgebied
- Achtergrond: `--c-brand`
- Tekst: wit, 1.5rem

---

## Badges & Labels

### Aantal-badge (normale voorraad)
```html
<span class="mob-qty-badge">3</span>
```
- Cirkel of pill, `--c-brand` achtergrond
- Wit, 900 gewicht

### Bestel-badge (0 op voorraad)
```html
<span class="mob-qty-badge mob-qty-order">Bestellen</span>
```
- Pill, `--c-order` (#c0392b) achtergrond
- Tekst: "Bestellen", 0.72rem

### Wijntype-badge (in detailweergave)
```html
<div class="bottle-type-badge">🍇 Wit</div>
```
- Pill met wit/doorzichtige achtergrond
- Klein, linksonder op de flesafbeelding

### Score-badge (mijn beoordeling)
```html
<div class="score-badge" style="--score-pct:70%">
  <span class="score-num">7</span>
  <span class="score-sub">/10</span>
  <span class="score-label">Mijn score</span>
</div>
```
- Cirkel met goudkleurige ring (conic gradient)
- 68px diameter

---

## Kaarten

### Wijnrij (mobiel)
```html
<button class="mob-wine-card" data-select="wine-1" style="--type-color:#a67c00">
  <!-- thumbnail -->
  <span class="mob-wine-card-text">
    <strong>Wijn naam</strong>
    <small>Land · Jaar 🍇 · €prijs/fles</small>
  </span>
  <span class="mob-wine-qty">
    <span class="mob-qty-badge">3</span>
  </span>
</button>
```
- Links: gekleurde accentbalk gebaseerd op `--type-color`
- Hoogte: 72px
- Actieve staat: `--c-brand-pale` achtergrond + `--c-brand` balk

### KPI-kaart (statistieken)
```html
<article class="kpi">
  <span>Flessen</span>
  <strong>42</strong>
</article>
```
- Wit oppervlak, `--shadow`
- Groot getal in `--c-brand`

### Voorraadbalk (in detail)
```html
<div class="stock-card">
  <button class="step-button" data-step="-1">−</button>
  <label>Aantal flessen <input id="quantity" /></label>
  <button class="step-button" data-step="1">+</button>
  <div class="stock-value">...</div>
</div>
```
- 3-koloms grid op desktop, gestapeld op mobiel
- `out-of-stock` klasse → rode rand + bestel-banner

---

## Formulierelementen

### Tekstveld
```html
<label class="form-field">
  Label
  <input name="fieldName" value="..." />
</label>
```

### Selectielijst
```html
<label class="form-field">
  Label
  <select name="fieldName">...</select>
</label>
```

### Sectie-uitklapper
```html
<button class="section-toggle open" data-toggle-section="wijngegevens">
  <span>Wijngegevens</span>
  <svg class="section-chevron">...</svg>
</button>
<div class="section-body">
  <!-- formuliervelden -->
</div>
```
- Klasse `open` = chevron wijst omlaag, sectie zichtbaar
- Zonder `open` = chevron wijst naar rechts, sectie verborgen

---

## Navigatie

### Mobiele header
- Vaste positie boven, 56px hoog
- `--c-brand` achtergrond, witte tekst
- Logo-merk (goud vierkant) + app-naam + FAB (+)

### Mobiele navigatiebalk (onder)
- Vaste positie onder, 64px + safe area
- 4 tabs: Lijst, Detail, Analyse, Scan
- Actieve tab: goudkleurige indicator + tekst

### Sectie-toggle (uitklapper)
- Volledige breedte
- Subtiele bovenrand als scheiding
- Uppercase, 0.72rem, `--c-muted`

---

## Beoordeling-widgets

### Vivino-rating
```html
<div class="rating" style="--r-pct:76%">
  3.8<span>Vivino</span>
</div>
```
- Ronde balk met percentage (conic gradient)
- Goud invul-kleur

### James Suckling-rating
Zelfde structuur, klasse `suckling-rating`.

---

## Kleuren per wijntype

| Type    | Kleur (CSS var)    | Hex      |
|---------|--------------------|----------|
| Rood    | `--c-wine-red`     | #8b1f35  |
| Wit     | `--c-wine-white`   | #a67c00  |
| Rosé    | `--c-wine-rose`    | #b5515d  |
| Overig  | `--c-wine-other`   | #5a6b66  |

---

## Typografische schaal

| Gebruik           | Grootte       | Gewicht |
|-------------------|---------------|---------|
| KPI-waarden       | 1.75rem (xl)  | 800     |
| Sectietitels      | 1.25rem (lg)  | 700     |
| Wijn-naam (detail)| 1.3rem        | 700     |
| Wijn-naam (lijst) | 0.88rem       | 700     |
| Subtekst lijst    | 0.76rem       | 400     |
| Badges/labels     | 0.68–0.72rem  | 700–900 |
| Sectie-toggle     | 0.72rem       | 700     |

---

## Breekpunten

| Naam    | Breedte    | Lay-out             |
|---------|------------|---------------------|
| Mobiel  | ≤ 767px    | Mobiele shell (tabs)|
| Desktop | ≥ 768px    | Zijbalk + werkruimte|
