/* ================================================
   STATE
   ================================================ */
const fallbackWines = Array.isArray(window.WINE_DATA) ? window.WINE_DATA : [];

let wines       = [];
let selectedId  = null;
let statusMsg   = 'Wijnoverzicht wordt geladen…';
let mobileView  = 'list';   // 'list' | 'detail' | 'analytics'
let filtersOpen = false;
let addOpen     = false;
let scanOpen    = false;
let addPrefill  = {};          // pre-ingevulde velden na lookup
let lookupStatus = '';         // '' | 'loading' | 'ok' | 'error'
let lookupError  = '';
let scanState   = {
  image: '',
  wineId: '',
  note: 'Maak een foto van het etiket en kies daarna de wijn.',
};
let filters = {
  search:  '',
  type:    'Alle',
  country: 'Alle',
  cabinet: 'Alle',
  sort:    'value-desc',
};
let supplierSearch = { wineId: null, status: '', results: [], error: '' };
let collapsedSections = {};
let imagePicker   = { wineId: null, open: false, status: '', images: [], source: '', proposed: null, error: '' };
let imageCacheBust = {};
let zoomedWineId  = null;
let uploadState   = { file: null, previewUrl: null, status: '', error: '' };
let labelScan     = { file: null, previewUrl: null, status: '', error: '', mode: '' };
let cabinetsOpen  = false;

const root = document.querySelector('#root');


/* ================================================
   HELPERS
   ================================================ */
function euro(v) {
  return new Intl.NumberFormat('nl-NL', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(Number(v) || 0);
}
function number(v) {
  return new Intl.NumberFormat('nl-NL').format(Number(v) || 0);
}
function num(v) {
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
}
function esc(v = '') {
  return String(v)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}
function wineTypeColor(type) {
  const map = { 'Rood': 'var(--c-wine-red)', 'Wit': 'var(--c-wine-white)', 'Rosé': 'var(--c-wine-rose)' };
  return map[type] || 'var(--c-wine-other)';
}
function wineImageUrl(wine) {
  const v = imageCacheBust[wine.name] || wine.updatedAt || '';
  const bust = v ? `&v=${v}` : '';
  return `/api/wine-image?name=${encodeURIComponent(wine.name || '')}${bust}`;
}
function wineThumbUrl(wine) {
  // Gebruik updatedAt uit de DB als primaire cache bust, imageCacheBust als fallback
  // (imageCacheBust wordt gezet bij handmatige upload/wijziging)
  const v = imageCacheBust[wine.name] || wine.updatedAt || '';
  const bust = v ? `&v=${v}` : '';
  return `/api/wine-thumb?name=${encodeURIComponent(wine.name || '')}${bust}`;
}
function isMobile() { return window.innerWidth < 768; }


/* ================================================
   DATA LAYER
   ================================================ */
function hydrateWine(w) {
  const qty   = num(w.quantity);
  const price = num(w.currentPrice);
  return { ...w, cabinet: w.cabinet || 'Niet ingedeeld', quantityNow: qty, valueNow: qty * price };
}

async function loadWines() {
  try {
    const r = await fetch('/api/wines');
    if (!r.ok) throw new Error('API niet beschikbaar');
    const data = await r.json();
    wines = data.wines.filter(w => w.name).map(hydrateWine);
    statusMsg = 'Live gekoppeld aan database.';
  } catch {
    wines = fallbackWines.filter(w => w.name).map(hydrateWine);
    statusMsg = 'Offline modus — start server.py om de database te bereiken.';
  }
  selectedId = selectedId ?? wines[0]?.id ?? null;
  render();
}

async function saveWine(patch) {
  try {
    statusMsg = 'Opslaan…';
    render();
    const r = await fetch('/api/wines', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(patch),
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.message || 'Opslaan mislukt');
    wines = data.wines.filter(w => w.name).map(hydrateWine);
    selectedId = data.wine?.id ?? selectedId;
    statusMsg = 'Opgeslagen.';
    render();
  } catch (e) {
    statusMsg = `Niet opgeslagen: ${e.message}`;
    render();
  }
}

async function addWine(formData) {
  try {
    statusMsg = 'Wijn toevoegen…';
    render();
    const r = await fetch('/api/wines', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(formData),
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.message || 'Toevoegen mislukt');
    wines = data.wines.filter(w => w.name).map(hydrateWine);
    selectedId = data.wine?.id ?? selectedId;

    const photoFile = labelScan.file;
    const photoMode = labelScan.mode;

    addOpen = false;
    addPrefill = {};
    lookupStatus = '';
    if (labelScan.previewUrl) URL.revokeObjectURL(labelScan.previewUrl);
    labelScan = { file: null, previewUrl: null, status: '', error: '', mode: '' };
    if (isMobile()) mobileView = 'detail';
    statusMsg = 'Wijn toegevoegd.';
    render();

    if (photoFile && photoMode === 'upload') {
      const wineName = data.wine?.name || formData.name;
      try {
        statusMsg = 'Foto vrijstaand maken…';
        render();
        const imgData = await uploadImageFile(wineName, photoFile);
        const bust = imgData.updatedAt || Date.now();
        imageCacheBust[wineName] = bust;
        wines = wines.map(w => w.name === wineName ? { ...w, updatedAt: bust } : w);
        statusMsg = 'Wijn toegevoegd.';
      } catch (imgErr) {
        statusMsg = `Wijn toegevoegd — foto mislukt: ${imgErr.message}`;
      }
      render();
    }
  } catch (e) {
    statusMsg = `Niet toegevoegd: ${e.message}`;
    render();
  }
}


/* ================================================
   DATA QUERIES
   ================================================ */
const SORT_OPTIONS = [
  ['value-desc',    'Waarde hoog→laag'],
  ['quantity-desc', 'Aantal hoog→laag'],
  ['rating-desc',   'Beoordeling hoog→laag'],
  ['year-asc',      'Jaar oud→nieuw'],
  ['name',          'Naam A→Z'],
];
const CABINETS = ['Niet ingedeeld', 'Wijnkast 1', 'Wijnkast 2', 'Wijnkast 3'];

function uniqueOpts(key) {
  return ['Alle', ...new Set(wines.map(w => w[key]).filter(Boolean).sort((a, b) => String(a).localeCompare(String(b), 'nl')))];
}

function filteredWines() {
  const term = filters.search.trim().toLowerCase();
  return wines
    .filter(w => {
      const hay = [w.name, w.type, w.grape, w.country, w.region, w.year, w.note].join(' ').toLowerCase();
      return (
        (!term || hay.includes(term)) &&
        (filters.type    === 'Alle' || w.type    === filters.type) &&
        (filters.country === 'Alle' || w.country === filters.country) &&
        (filters.cabinet === 'Alle' || w.cabinet === filters.cabinet)
      );
    })
    .sort((a, b) => {
      if (filters.sort === 'name')          return String(a.name).localeCompare(String(b.name), 'nl');
      if (filters.sort === 'quantity-desc') return b.quantityNow - a.quantityNow;
      if (filters.sort === 'rating-desc')  return num(b.vivino) - num(a.vivino);
      if (filters.sort === 'year-asc')     return num(a.year || 9999) - num(b.year || 9999);
      return b.valueNow - a.valueNow;
    });
}

function totals(src) {
  return {
    bottles:  src.reduce((s, w) => s + w.quantityNow, 0),
    value:    src.reduce((s, w) => s + w.valueNow, 0),
    avgPrice: src.reduce((s, w) => s + num(w.currentPrice), 0) / Math.max(src.length, 1),
    cabinets: new Set(src.map(w => w.cabinet).filter(c => c && c !== 'Niet ingedeeld')).size,
  };
}

function groupSum(src, key, fn) {
  const map = new Map();
  src.forEach(w => { const k = w[key] || 'Onbekend'; map.set(k, (map.get(k) || 0) + fn(w)); });
  return [...map.entries()].sort((a, b) => b[1] - a[1]);
}

function getSelected() {
  return wines.find(w => w.id === selectedId) ?? filteredWines()[0] ?? wines[0];
}

function activeFilterCount() {
  return (filters.search ? 1 : 0)
    + (filters.type    !== 'Alle' ? 1 : 0)
    + (filters.country !== 'Alle' ? 1 : 0)
    + (filters.cabinet !== 'Alle' ? 1 : 0);
}


/* ================================================
   RENDER ENTRY POINT
   ================================================ */
function render() {
  const visible  = filteredWines();
  const selected = getSelected();
  if (selected && selected.id !== selectedId) selectedId = selected.id;
  const summary  = totals(wines);

  root.innerHTML = isMobile()
    ? renderMobile(visible, selected, summary)
    : renderDesktop(visible, selected, summary);

  if (zoomedWineId) {
    const wine = wines.find(w => w.id === zoomedWineId);
    if (wine) {
      const overlay = document.createElement('div');
      overlay.id = 'zoom-overlay';
      overlay.innerHTML = `
        <div class="zoom-backdrop" id="zoom-backdrop"></div>
        <div class="zoom-box">
          <button class="zoom-close" id="zoom-close" title="Sluiten">${iconClose()}</button>
          <img src="${wineImageUrl(wine)}" alt="${esc(wine.name)}" class="zoom-img" />
          <p class="zoom-name">${esc(wine.name)}${wine.year ? ' · ' + esc(String(wine.year)) : ''}</p>
        </div>`;
      document.body.appendChild(overlay);
      overlay.querySelector('#zoom-backdrop').addEventListener('click', () => { zoomedWineId = null; overlay.remove(); });
      overlay.querySelector('#zoom-close').addEventListener('click', () => { zoomedWineId = null; overlay.remove(); });
    }
  }

  bindEvents();
}

let resizeTimer;
let _lastIsMobile = isMobile();
window.addEventListener('resize', () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => {
    const nowMobile = isMobile();
    if (nowMobile !== _lastIsMobile) {
      _lastIsMobile = nowMobile;
      render();
    }
  }, 120);
});


/* ================================================
   DESKTOP RENDER
   ================================================ */
function renderDesktop(visible, selected, summary) {
  return `
    <main class="app-shell">
      <aside class="sidebar">
        <button class="brand" id="logo-btn">
          <div class="brand-mark">${iconLogo(38)}</div>
          <div>
            <strong>Wijnoverzicht</strong>
            <span>Persoonlijk wijnarchief</span>
          </div>
        </button>

        <div class="sidebar-actions">
          <button class="primary-action" id="open-add">+ Nieuwe fles</button>
          <button class="secondary-action" id="open-scan">Fotoscan</button>
        </div>

        <label class="search">
          <span>Zoeken</span>
          <input id="search" value="${esc(filters.search)}" placeholder="Naam, druif, regio…" />
        </label>

        <div class="filter-block">
          ${selectCtrl('type',    'Soort',    uniqueOpts('type'),    filters.type)}
          ${selectCtrl('country', 'Land',     uniqueOpts('country'), filters.country)}
          ${selectCtrl('cabinet', 'Wijnkast', ['Alle', ...CABINETS], filters.cabinet)}
          ${selectCtrl('sort',    'Sortering', SORT_OPTIONS,         filters.sort)}
        </div>

        <div class="wine-list">
          ${visible.map(w => desktopWineRow(w, selected?.id)).join('')
            || '<p class="empty dark">Geen wijnen gevonden.</p>'}
        </div>

        <button class="sidebar-cabinets-btn${cabinetsOpen ? ' active' : ''}" id="toggle-cabinets">
          ${iconCabinets()} Wijnkasten
        </button>
      </aside>

      <section class="workspace">
        <header class="hero">
          <div>
            <p class="hero-meta">Persoonlijk wijnarchief</p>
            <h1>Wijnoverzicht</h1>
          </div>
          <div class="status-pill">${esc(statusMsg)}</div>
        </header>

        <section class="kpi-grid">
          ${kpiCard('Flessen',     number(summary.bottles))}
          ${kpiCard('Totale waarde', euro(summary.value))}
          ${kpiCard('Gem. prijs',  euro(summary.avgPrice))}
          ${kpiCard('Wijnkasten',  `${number(summary.cabinets)} / 3`)}
        </section>

        ${addOpen  ? addPanel()  : ''}
        ${scanOpen ? scanPanel() : ''}

        ${cabinetsOpen ? cabinetsPanel() : `
          <div class="dashboard-grid">
            ${selected ? editorPanel(selected) : ''}
            <section class="analytics-panel">
              <div class="panel-title">
                <div>
                  <p class="panel-title-meta">Analyse</p>
                  <h2>Voorraad & waarde</h2>
                </div>
                <span class="panel-title-right">${number(visible.length)} van ${number(wines.length)}</span>
              </div>
              ${analyticsCharts()}
            </section>
          </div>
        `}
      </section>
    </main>
  `;
}


/* ================================================
   MOBILE RENDER
   ================================================ */
function renderMobile(visible, selected, summary) {
  return `
    ${addOpen  ? mobileOverlay('Nieuwe fles toevoegen', 'close-add',  addPanel())  : ''}
    ${scanOpen ? mobileOverlay('Fotoscan',              'close-scan', scanPanel(), true) : ''}

    <div class="mobile-shell">
      ${mobileHeader()}

      <main class="mobile-content">
        ${mobileView === 'list'      ? mobListView(visible, selected)  : ''}
        ${mobileView === 'detail'    ? mobDetailView(selected)         : ''}
        ${mobileView === 'analytics' ? mobAnalyticsView(summary)       : ''}
        ${mobileView === 'cabinets'  ? cabinetsPanel()                 : ''}
      </main>

      ${mobileNav()}
    </div>
  `;
}

function mobileHeader() {
  return `
    <header class="mobile-header">
      <button class="mobile-brand" id="logo-btn">
        <div class="mobile-brand-mark">${iconLogo(32)}</div>
        <span class="mobile-brand-name">Wijnoverzicht</span>
      </button>
      <div class="mobile-header-actions">
        <button class="mobile-fab" id="open-add" title="Nieuwe fles toevoegen">+</button>
      </div>
    </header>
  `;
}

function mobileNav() {
  const tabs = [
    { id: 'list',      label: 'Lijst',   icon: iconList()     },
    { id: 'detail',    label: 'Detail',  icon: iconWine()     },
    { id: 'cabinets',  label: 'Kasten',  icon: iconCabinets() },
    { id: 'analytics', label: 'Analyse', icon: iconChart()    },
    { id: 'scan',      label: 'Scan',    icon: iconCamera(), isScan: true },
  ];
  return `
    <nav class="mobile-nav">
      ${tabs.map(t => `
        <button class="mobile-tab ${!t.isScan && mobileView === t.id ? 'active' : ''}"
                data-${t.isScan ? 'scan-nav' : 'nav'}="${t.id}">
          ${t.icon}
          <span>${t.label}</span>
          ${!t.isScan && mobileView === t.id ? '<span class="tab-dot"></span>' : ''}
        </button>
      `).join('')}
    </nav>
  `;
}

function mobileOverlay(title, closeId, content, hideClose = false) {
  return `
    <div class="mob-overlay">
      <header class="mob-overlay-header">
        <h2>${esc(title)}</h2>
        ${hideClose ? '' : `<button class="mob-overlay-close" id="${closeId}">✕</button>`}
      </header>
      <div class="mob-overlay-body">
        ${content}
      </div>
    </div>
  `;
}

/* --- Mobile list view --- */
function mobListView(visible, selected) {
  const fc = activeFilterCount();
  return `
    <div class="mob-list-search">
      <input id="search" value="${esc(filters.search)}" placeholder="Zoek wijn, druif, regio…" />
      <button class="mob-filter-btn ${filtersOpen ? 'active' : ''}" id="toggle-filters">
        Filter${fc > 0 ? `<span class="mob-filter-count">${fc}</span>` : ''}
      </button>
    </div>

    ${filtersOpen ? `
      <div class="mob-filter-panel">
        ${mobileSelectCtrl('type',    'Soort',    uniqueOpts('type'),    filters.type)}
        ${mobileSelectCtrl('country', 'Land',     uniqueOpts('country'), filters.country)}
        ${mobileSelectCtrl('cabinet', 'Wijnkast', ['Alle', ...CABINETS], filters.cabinet)}
        ${mobileSelectCtrl('sort',    'Sortering', SORT_OPTIONS,         filters.sort)}
      </div>
    ` : ''}

    <p class="mob-wine-count">${number(visible.length)} wijn${visible.length !== 1 ? 'en' : ''}</p>

    <div class="mob-wine-list">
      ${visible.map(w => mobWineCard(w, selected?.id)).join('')
        || '<p class="empty" style="padding:0 0 8px">Geen wijnen gevonden.</p>'}
    </div>
  `;
}

function mobWineCard(wine, activeId) {
  const color = wineTypeColor(wine.type);
  const out = wine.quantityNow === 0;
  return `
    <button class="mob-wine-card" data-select="${wine.id}" style="--type-color:${color}">
      ${listThumb(wine)}
      <span class="mob-wine-card-text">
        <strong>${esc(wine.name)}</strong>
        <small>${esc(wine.country || 'Onbekend')} · ${wine.year ? esc(String(wine.year)) : '—'} ${iconGrapeInline(wine.type)}${wine.currentPrice ? ' · ' + euro(num(wine.currentPrice)) + '/fles' : ''}${wine.cabinet && wine.cabinet !== 'Niet ingedeeld' ? ' · ' + esc(wine.cabinet) : ''}</small>
      </span>
      <span class="mob-wine-qty">
        ${out
          ? `<span class="mob-qty-badge mob-qty-order">Bestellen</span>`
          : `<span class="mob-qty-badge">${wine.quantityNow}</span>`}
      </span>
    </button>
  `;
}

/* --- Mobile detail view --- */
function mobDetailView(selected) {
  if (!selected) {
    return `
      <div class="mob-detail-empty">
        ${iconWine()}
        <p>Selecteer een wijn in de lijst.</p>
      </div>
    `;
  }
  return `<div class="mob-detail-view">${editorPanel(selected)}</div>`;
}

/* --- Mobile analytics view --- */
function mobAnalyticsView(summary) {
  return `
    <div class="mob-analytics-view">
      <div class="status-pill">${esc(statusMsg)}</div>

      <div class="kpi-grid" style="margin-top:14px">
        ${kpiCard('Flessen',      number(summary.bottles))}
        ${kpiCard('Totale waarde', euro(summary.value))}
        ${kpiCard('Gem. prijs',   euro(summary.avgPrice))}
        ${kpiCard('Wijnkasten',   `${number(summary.cabinets)} / 3`)}
      </div>

      <h2>Voorraad & waarde</h2>
      ${analyticsCharts()}
    </div>
  `;
}


/* ================================================
   SHARED COMPONENTS
   ================================================ */

/* Select controls */
function selectCtrl(id, label, options, selected) {
  return `
    <label class="field">
      ${esc(label)}
      <select id="${id}">
        ${options.map(o => {
          const val  = Array.isArray(o) ? o[0] : o;
          const text = Array.isArray(o) ? o[1] : o;
          return `<option value="${esc(val)}" ${val === selected ? 'selected' : ''}>${esc(text)}</option>`;
        }).join('')}
      </select>
    </label>
  `;
}

function mobileSelectCtrl(id, label, options, selected) {
  return `
    <label class="field">
      ${esc(label)}
      <select id="${id}">
        ${options.map(o => {
          const val  = Array.isArray(o) ? o[0] : o;
          const text = Array.isArray(o) ? o[1] : o;
          return `<option value="${esc(val)}" ${val === selected ? 'selected' : ''}>${esc(text)}</option>`;
        }).join('')}
      </select>
    </label>
  `;
}

/* Section collapse helpers */
function isSectionOpen(key, defaultOpen = true) {
  return key in collapsedSections ? !collapsedSections[key] : defaultOpen;
}
function sectionToggle(label, key, defaultOpen = true) {
  const open = isSectionOpen(key, defaultOpen);
  return `<button type="button" class="section-toggle ${open ? 'open' : ''}" data-toggle-section="${key}">
    <span>${label}</span>
    <svg class="section-chevron" width="13" height="13" viewBox="0 0 13 13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="2,4 6.5,9 11,4"/></svg>
  </button>`;
}

/* Desktop wine row */
function desktopWineRow(wine, activeId) {
  const color = wineTypeColor(wine.type);
  const out = wine.quantityNow === 0;
  return `
    <button class="wine-row ${wine.id === activeId ? 'active' : ''}"
            data-select="${wine.id}"
            style="--type-color:${color}">
      ${listThumb(wine)}
      <span>
        <strong>${esc(wine.name)}</strong>
        <small>${esc(wine.country || '—')} · ${wine.year ? esc(String(wine.year)) : '—'} ${iconGrapeInline(wine.type)}${wine.currentPrice ? ' · ' + euro(num(wine.currentPrice)) + '/fles' : ''}${wine.cabinet && wine.cabinet !== 'Niet ingedeeld' ? ' · ' + esc(wine.cabinet) : ''}</small>
      </span>
      ${out ? `<b class="qty-out">Bestellen</b>` : `<b>${wine.quantityNow}</b>`}
    </button>
  `;
}

/* KPI card */
function kpiCard(label, value) {
  return `
    <article class="kpi">
      <span>${esc(label)}</span>
      <strong>${esc(value)}</strong>
    </article>
  `;
}

/* Editor panel */
function editorPanel(wine) {
  const vivinoPct   = wine.vivino   ? `${Math.min(100, (num(wine.vivino) / 5) * 100)}%` : '0%';
  const sucklingPct = wine.suckling ? `${Math.min(100, num(wine.suckling))}%`            : '0%';
  const scorePct    = wine.score    ? `${(num(wine.score) / 10) * 100}%`                : '0%';
  const isOut       = wine.quantityNow === 0;
  const supActive   = supplierSearch.wineId === wine.id;

  return `
    <section class="editor-panel">
      <div class="panel-title">
        <div>
          <p class="panel-title-meta">${esc(wine.type || 'Wijn')} · ${esc(wine.country || '—')}</p>
          <h2>${esc(wine.name)}</h2>
        </div>
        <div class="ratings-group">
          ${wine.score ? `
            <div class="score-badge" style="--score-pct:${scorePct}">
              <span class="score-num">${num(wine.score)}</span>
              <span class="score-sub">/10</span>
              <span class="score-label">Mijn score</span>
            </div>
          ` : ''}
          <div class="ext-ratings">
            <div class="rating rating-sm" style="--r-pct:${vivinoPct}">
              ${wine.vivino ? Number(wine.vivino).toFixed(1) : '—'}<span>Vivino</span>
            </div>
            ${wine.suckling ? `
              <div class="rating rating-sm suckling-rating" style="--r-pct:${sucklingPct}">
                ${num(wine.suckling)}<span>James<br>Suckling</span>
              </div>` : ''}
          </div>
        </div>
      </div>

      <div class="bottle-img-wrap">
        <img class="bottle-img"
             src="${wineImageUrl(wine)}"
             alt="${esc(wine.name)}"
             loading="lazy"
             id="bottle-img-tap"
             onerror="this.style.display='none';this.closest('.bottle-img-wrap').classList.add('no-img')" />
        ${wine.type ? `<div class="bottle-type-badge">${iconGrapeInline(wine.type)} ${esc(wine.type)}</div>` : ''}
        <button class="step-button img-zoom-btn" id="open-zoom" title="Vergroot afbeelding">
          ${iconZoom()}
        </button>
        <div class="img-top-right-btns">
          <button class="step-button img-delete-btn" id="delete-img" title="Afbeelding verwijderen">${iconTrash()}</button>
          <button class="step-button img-picker-btn" id="open-img-picker"
                  title="${imagePicker.open && imagePicker.wineId === wine.id ? 'Sluiten' : 'Afbeelding wijzigen'}">
            ${imagePicker.open && imagePicker.wineId === wine.id ? iconClose() : iconPhoto()}
          </button>
        </div>
      </div>
      ${imagePicker.open && imagePicker.wineId === wine.id ? renderImagePicker(wine) : ''}

      <div class="stock-card ${isOut ? 'out-of-stock' : ''}">
        <button class="step-button" data-step="-1">−</button>
        <label>
          Aantal flessen
          <input id="quantity" inputmode="numeric" pattern="[0-9]*" value="${wine.quantityNow}" />
        </label>
        <button class="step-button" data-step="1">+</button>
        <div class="stock-value">
          <span>Totale waarde</span>
          <strong>${euro(wine.valueNow)}</strong>
          ${wine.currentPrice ? `<span class="stock-unit-price">${euro(num(wine.currentPrice))} / fles</span>` : ''}
        </div>
        ${isOut ? `
          <div class="order-banner">
            <span>Voorraad op — opnieuw bestellen?</span>
            <button class="order-btn ${supActive && supplierSearch.status === 'loading' ? 'loading' : ''}"
                    id="find-suppliers"
                    ${supActive && supplierSearch.status === 'loading' ? 'disabled' : ''}>
              ${supActive && supplierSearch.status === 'loading' ? iconSpinner() + ' Zoeken…' : '🛒&nbsp;Bestel online'}
            </button>
          </div>
        ` : ''}
      </div>

      ${isOut && supActive ? renderSupplierResults() : ''}

      <form id="edit-form" class="wine-form">
        <input type="hidden" name="rowNumber" value="${wine.rowNumber || ''}" />

        ${sectionToggle('Wijngegevens', 'wijngegevens', false)}
        <div class="section-body${isSectionOpen('wijngegevens', false) ? '' : ' section-collapsed'}">
          ${formField('Naam', 'name', wine.name, true)}
          <div class="form-row">
            ${formField('Soort', 'type', wine.type)}
            ${formField('Jaar',  'year', wine.year, false, 'numeric')}
          </div>
          ${selectFormField('Wijnkast', 'cabinet', CABINETS, wine.cabinet || 'Niet ingedeeld')}
          ${formField('Druifsoort', 'grape', wine.grape)}
          <div class="form-row">
            ${formField('Land',  'country', wine.country)}
            ${formField('Regio', 'region',  wine.region)}
          </div>
        </div>

        ${sectionToggle('Waardering & prijs', 'waardering', false)}
        <div class="section-body${isSectionOpen('waardering', false) ? '' : ' section-collapsed'}">
          <div class="form-row">
            ${formField('Vivino',         'vivino',    wine.vivino,    false, 'decimal')}
            ${formField('James Suckling', 'suckling',  wine.suckling,  false, 'numeric')}
          </div>
          <div class="form-row">
            <label class="form-field">
              Mijn score (1–10)
              <input type="number" name="score" min="1" max="10" step="1"
                     value="${esc(wine.score ?? '')}" inputmode="numeric" placeholder="—" />
            </label>
            ${formField('Prijs/fles', 'currentPrice', wine.currentPrice, false, 'decimal')}
          </div>
        </div>

        ${sectionToggle('Notitie', 'notitie', false)}
        <div class="section-body${isSectionOpen('notitie', false) ? '' : ' section-collapsed'}">
          <label class="form-field wide">
            Bron / opmerking
            <textarea name="note">${esc(wine.note || '')}</textarea>
          </label>
        </div>

        ${sectionToggle('Leverancier', 'leverancier', false)}
        <div class="section-body${isSectionOpen('leverancier', false) ? '' : ' section-collapsed'}">
          <div class="form-row">
            ${formField('Bedrijfsnaam',   'supplierName',    wine.supplierName    || '')}
            ${formField('Contactpersoon', 'supplierContact', wine.supplierContact || '')}
          </div>
          <div class="form-row">
            ${formField('Telefoonnummer', 'supplierPhone', wine.supplierPhone || '', false, 'tel')}
            ${formField('E-mailadres',    'supplierEmail', wine.supplierEmail || '', false, 'email')}
          </div>
          <label class="form-field wide">
            Adresgegevens
            <input name="supplierAddress" value="${esc(wine.supplierAddress || '')}" />
          </label>
        </div>

        <div class="form-actions-row">
          <button class="save-button" style="flex:1">Opslaan</button>
          <button type="button" class="danger-button" id="delete-wine" style="flex:1">Verwijder wijn</button>
        </div>
      </form>
    </section>
  `;
}

function cabinetsPanel() {
  const cabinetOrder = ['Wijnkast 1', 'Wijnkast 2', 'Wijnkast 3', 'Niet ingedeeld'];
  const groups = cabinetOrder
    .map(name => ({ name, wines: wines.filter(w => (w.cabinet || 'Niet ingedeeld') === name) }))
    .filter(g => g.wines.length > 0);

  return `
    <section class="cabinets-panel">
      <div class="cabinets-grid">
        ${groups.map(g => {
          const totalBottles = g.wines.reduce((s, w) => s + w.quantityNow, 0);
          const totalValue   = g.wines.reduce((s, w) => s + w.valueNow,   0);
          return `
            <div class="cabinet-card">
              <div class="cabinet-card-header">
                <h3>${esc(g.name)}</h3>
                <span class="cabinet-card-meta">${number(totalBottles)} fl &nbsp;·&nbsp; ${euro(totalValue)}</span>
              </div>
              <div class="cabinet-wine-list">
                ${g.wines.map(w => `
                  <button class="cabinet-wine-row" data-select="${w.id}">
                    <div class="cabinet-wine-thumb">
                      <img src="${wineThumbUrl(w)}" alt="" loading="lazy"
                           onerror="this.style.display='none'" />
                    </div>
                    <span class="cabinet-wine-info">
                      <strong>${esc(w.name)}</strong>
                      <small>${esc(w.type || '')}${w.year ? ' · ' + w.year : ''}</small>
                    </span>
                    <span class="cabinet-wine-qty${w.quantityNow === 0 ? ' out' : ''}">${w.quantityNow}</span>
                  </button>
                `).join('')}
              </div>
            </div>
          `;
        }).join('')}
      </div>
    </section>
  `;
}

function renderSupplierResults() {
  const s = supplierSearch;
  if (s.status === 'loading') return `
    <div class="supplier-results-section">
      <div class="supplier-loading">${iconSpinner()} Beste leveranciers zoeken…</div>
    </div>
  `;
  if (s.status === 'error') return `
    <div class="supplier-results-section">
      <p class="supplier-error">⚠ ${esc(s.error)}</p>
    </div>
  `;
  if (s.status === 'ok') {
    if (!s.results.length) return `
      <div class="supplier-results-section">
        <p class="empty">Geen leveranciers gevonden.</p>
      </div>
    `;
    return `
      <div class="supplier-results-section">
        <p class="supplier-disclaimer">Geschatte prijzen — controleer actuele prijs op de website.</p>
        <div class="supplier-list">
          ${s.results.map((r, i) => supplierResultCard(r, i === 0)).join('')}
        </div>
      </div>
    `;
  }
  return '';
}

function supplierResultCard(s, isBest) {
  return `
    <div class="supplier-result-card${isBest ? ' best' : ''}">
      ${isBest ? '<span class="src-badge">Beste keuze</span>' : ''}
      <div class="src-header">
        <span class="src-name">${esc(s.name)}</span>
        ${s.reviewScore ? `
          <span class="src-rating">★ ${Number(s.reviewScore).toFixed(1)}
            ${s.reviewPlatform ? `<em>${esc(s.reviewPlatform)}</em>` : ''}
          </span>
        ` : ''}
      </div>
      <div class="src-prices">
        <span>€${Number(s.pricePerBottle || 0).toFixed(2)} / fles</span>
        <span>Verzending: €${Number(s.shipping || 0).toFixed(2)}${s.freeShippingFrom ? ` (gratis v.a. €${s.freeShippingFrom})` : ''}</span>
      </div>
      <div class="src-total">
        <span>3 flessen totaal</span>
        <strong>€${Number(s.totalFor3 || 0).toFixed(2)}</strong>
      </div>
      ${s.notes ? `<p class="src-notes">${esc(s.notes)}</p>` : ''}
      ${s.url ? `<a href="${esc(s.url)}" target="_blank" rel="noopener noreferrer" class="src-link">Ga naar webshop →</a>` : ''}
    </div>
  `;
}

function renderImagePicker(wine) {
  const s = imagePicker;

  const loadingLabel = s.source === 'internet'
    ? `${iconSpinner()} Niets op Vivino — zoekt zelf op internet…`
    : `${iconSpinner()} Afbeeldingen zoeken op Vivino…`;

  const sourceNote = s.source === 'internet'
    ? '<span class="img-source-badge internet">🌐 Gevonden via internet</span>'
    : '<span class="img-source-badge vivino">Vivino</span>';

  return `
    <div class="img-picker-panel">
      ${s.status === 'choose' ? `
        <div class="img-picker-choice">
          <button class="save-button" id="choice-vivino" style="flex:1">Zoeken op Vivino</button>
          <button class="save-button" id="choice-upload" style="flex:1">Eigen foto</button>
        </div>
      ` : ''}
      ${s.status === 'loading' ? `
        <div class="img-picker-loading">${loadingLabel}</div>
      ` : ''}
      ${s.status === 'saving' ? `
        <div class="img-picker-loading">${iconSpinner()} Afbeelding opslaan…</div>
      ` : ''}
      ${s.status === 'error' ? `
        <p class="supplier-error">⚠ ${esc(s.error)}</p>
      ` : ''}
      ${s.status === 'upload' || s.status === 'ok' ? `
        ${s.status === 'ok' ? `
          ${s.source === 'internet' && s.proposed ? `
            <div class="img-proposed-wrap">
              <div class="img-picker-header-row">
                <p class="img-picker-hint">Op Vivino niets gevonden. We zochten zelf online en verwijderden de achtergrond:</p>
                ${sourceNote}
              </div>
              <div class="img-proposed-preview">
                <img src="${esc(s.proposed)}&v=${Date.now()}" alt="Voorstel" class="img-proposed-img"
                     onerror="this.closest('.img-proposed-preview').innerHTML='<p class=\\'supplier-error\\'>Afbeelding kon niet worden geladen.</p>'" />
              </div>
              <div class="img-proposed-actions">
                <button class="save-button" id="confirm-proposed" style="flex:1">Gebruik deze afbeelding</button>
                <button class="step-button" id="discard-proposed" style="width:auto;padding:0 14px" title="Annuleren">${iconClose()}</button>
              </div>
            </div>
          ` : s.images.length ? `
            <div class="img-picker-header-row">
              <p class="img-picker-hint">Klik op de juiste fles om deze te gebruiken.</p>
              ${sourceNote}
            </div>
            <div class="img-picker-grid">
              ${s.images.map(url => `
                <button class="img-picker-thumb" data-img-url="${esc(url)}">
                  <img src="${esc(url)}" alt="Kandidaat" loading="lazy"
                       onerror="this.closest('button').style.display='none'" />
                </button>
              `).join('')}
            </div>
          ` : `
            <p class="empty" style="padding:4px 0 10px">
              Geen afbeelding gevonden. Plak hieronder een eigen URL.
            </p>
          `}
          <div class="img-picker-custom">
            <label class="form-field">
              Of plak een eigen afbeelding-URL
              <div class="img-picker-url-row">
                <input id="custom-img-url" type="url" placeholder="https://…" />
                <button class="save-button" id="use-custom-url" style="width:auto;padding:0 16px;margin:0">Gebruik</button>
              </div>
            </label>
          </div>
        ` : ''}

        <div class="img-upload-section">
          <p class="img-picker-hint" style="margin-bottom:8px">Upload een eigen foto — de achtergrond wordt automatisch verwijderd:</p>
          <label class="img-upload-drop ${uploadState.previewUrl ? 'has-preview' : ''}">
            ${uploadState.previewUrl
              ? `<img src="${uploadState.previewUrl}" class="img-upload-preview" alt="Voorvertoning" />`
              : `<div class="img-upload-placeholder">${iconCamera()} Klik of sleep een foto hiernaartoe</div>`
            }
            <input id="upload-img-input" type="file" accept="image/*" class="img-upload-input" />
          </label>
          ${uploadState.previewUrl ? `
            <div class="img-proposed-actions" style="margin-top:8px">
              <button class="save-button" id="do-upload-img" style="flex:1" ${uploadState.status === 'uploading' ? 'disabled' : ''}>
                ${uploadState.status === 'uploading' ? iconSpinner() + ' Vrijstaand maken…' : 'Vrijstaand maken & opslaan'}
              </button>
              <button class="step-button" id="cancel-upload" style="width:auto;padding:0 14px" title="Annuleren">${iconClose()}</button>
            </div>
          ` : ''}
          ${uploadState.status === 'error' ? `<p class="supplier-error" style="margin-top:6px">⚠ ${esc(uploadState.error)}</p>` : ''}
        </div>
      ` : ''}
    </div>
  `;
}

async function triggerAutoImageCheck(wine) {
  imagePicker = { wineId: wine.id, open: true, status: 'loading', images: [], source: '', proposed: null, error: '' };
  render();
  try {
    const params = new URLSearchParams({
      name: wine.name,
      type: wine.type || '',
      year: wine.year ? String(wine.year) : '',
    });
    const r = await fetch(`/api/wine-images?${params}`);
    const data = await r.json();
    if (!r.ok) throw new Error(data.message || 'Zoeken mislukt');
    imagePicker = { ...imagePicker, status: 'ok', images: data.images || [], source: data.source || '', proposed: data.proposed || null };
  } catch (e) {
    imagePicker = { ...imagePicker, status: 'error', error: e.message };
  }
  render();
}

async function handleOpenImagePicker(wine) {
  if (imagePicker.open && imagePicker.wineId === wine.id) {
    imagePicker = { wineId: null, open: false, status: '', images: [], source: '', proposed: null, error: '' };
    render();
    return;
  }
  imagePicker = { wineId: wine.id, open: true, status: 'choose', images: [], source: '', proposed: null, error: '' };
  render();
}

async function handleSelectImage(wine, imageUrl) {
  imagePicker = { ...imagePicker, status: 'saving' };
  render();
  try {
    const r = await fetch('/api/set-image', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: wine.name, imageUrl }),
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.message || 'Opslaan mislukt');
    imageCacheBust[wine.name] = Date.now();
    imagePicker = { wineId: null, open: false, status: '', images: [], error: '' };
  } catch (e) {
    imagePicker = { ...imagePicker, status: 'error', error: e.message };
  }
  render();
}

async function handleConfirmProposed(wine) {
  imagePicker = { ...imagePicker, status: 'saving' };
  render();
  try {
    const r = await fetch('/api/confirm-proposed', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: wine.name }),
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.message || 'Opslaan mislukt');
    imageCacheBust[wine.name] = Date.now();
    imagePicker = { wineId: null, open: false, status: '', images: [], source: '', proposed: null, error: '' };
  } catch (e) {
    imagePicker = { ...imagePicker, status: 'error', error: e.message };
  }
  render();
}

async function handleDiscardProposed(wine) {
  await fetch('/api/discard-proposed', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: wine.name }),
  });
  imagePicker = { wineId: null, open: false, status: '', images: [], source: '', proposed: null, error: '' };
  render();
}

async function handleDeleteImage(wine) {
  if (!confirm(`Afbeelding van "${wine.name}" verwijderen?`)) return;
  try {
    await fetch(`/api/wine-image?name=${encodeURIComponent(wine.name)}`, { method: 'DELETE' });
    imageCacheBust[wine.name] = Date.now();
    render();
  } catch (e) { /* stil mislukken */ }
}

async function handleLabelScan() {
  if (!labelScan.file) return;
  labelScan = { ...labelScan, status: 'scanning', error: '' };
  render();
  try {
    const imageData = await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result.split(',')[1]);
      reader.onerror = reject;
      reader.readAsDataURL(labelScan.file);
    });
    const r = await fetch('/api/scan-wine-label', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ imageData }),
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.message || 'Herkenning mislukt');
    addPrefill = { ...data };
    lookupStatus = 'scan-ok';
    labelScan = { ...labelScan, status: 'done' };
  } catch (e) {
    labelScan = { ...labelScan, status: 'error', error: e.message };
  }
  render();
}

async function uploadImageFile(wineName, file) {
  const imageData = await new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result.split(',')[1]);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
  const r = await fetch('/api/upload-image', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: wineName, imageData }),
  });
  const data = await r.json();
  if (!r.ok) throw new Error(data.message || 'Uploaden mislukt');
  return data;
}

async function handleUploadImage(wine) {
  if (!uploadState.file) return;
  uploadState = { ...uploadState, status: 'uploading', error: '' };
  render();
  try {
    const data = await uploadImageFile(wine.name, uploadState.file);
    if (uploadState.previewUrl) URL.revokeObjectURL(uploadState.previewUrl);
    uploadState = { file: null, previewUrl: null, status: '', error: '' };
    const bust = data.updatedAt || Date.now();
    imageCacheBust[wine.name] = bust;
    wines = wines.map(w => w.name === wine.name ? { ...w, updatedAt: bust } : w);
    imagePicker = { wineId: null, open: false, status: '', images: [], source: '', proposed: null, error: '' };
  } catch (e) {
    uploadState = { ...uploadState, status: 'error', error: e.message };
  }
  render();
}

async function deleteWine(wine) {
  if (!confirm(`"${wine.name}" definitief verwijderen uit de kelder?`)) return;
  try {
    statusMsg = 'Verwijderen…';
    render();
    const r = await fetch(`/api/wines?rowNumber=${encodeURIComponent(wine.rowNumber)}`, { method: 'DELETE' });
    const data = await r.json();
    if (!r.ok) throw new Error(data.message || 'Verwijderen mislukt');
    wines = data.wines.filter(w => w.name).map(hydrateWine);
    selectedId = wines[0]?.id ?? null;
    if (isMobile()) mobileView = 'list';
    statusMsg = `"${wine.name}" verwijderd.`;
  } catch (e) {
    statusMsg = `Niet verwijderd: ${e.message}`;
  }
  render();
}

async function handleFindSuppliers(wine) {
  supplierSearch = { wineId: wine.id, status: 'loading', results: [], error: '' };
  render();
  try {
    const r = await fetch('/api/find-suppliers', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: wine.name, type: wine.type, grape: wine.grape,
        country: wine.country, region: wine.region, year: wine.year,
      }),
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.message || 'Zoeken mislukt');
    supplierSearch = { wineId: wine.id, status: 'ok', results: Array.isArray(data) ? data : [], error: '' };
  } catch (e) {
    supplierSearch = { wineId: wine.id, status: 'error', results: [], error: e.message };
  }
  render();
}

/* Lookup wine info from server (calls Claude API) */
async function handleLookup() {
  const nameInput = document.querySelector('#lookup-name');
  const name = nameInput?.value?.trim();
  if (!name) { nameInput?.focus(); return; }

  lookupStatus = 'loading';
  lookupError  = '';
  render();

  try {
    const r = await fetch('/api/lookup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.message || 'Opzoeken mislukt');
    addPrefill = { ...data, name };
    lookupStatus = 'ok';
  } catch (e) {
    lookupStatus = 'error';
    lookupError  = e.message;
  }
  render();
  // Zet focus terug op de naamveld na render
  document.querySelector('#lookup-name')?.focus();
}

/* Add wine panel */
function addPanel() {
  const p = addPrefill; // shorthand voor pre-ingevulde waarden

  const lookupFeedback =
    lookupStatus === 'loading'  ? `<span class="lookup-feedback loading">${iconSpinner()} Informatie ophalen…</span>` :
    lookupStatus === 'ok'       ? `<span class="lookup-feedback ok">✓ Automatisch ingevuld</span>` :
    lookupStatus === 'scan-ok'  ? `<span class="lookup-feedback ok">✓ Herkend via etiket + internet</span>` :
    lookupStatus === 'error'    ? `<span class="lookup-feedback err" title="${esc(lookupError)}">⚠ ${esc(lookupError)}</span>` : '';

  const scanBusy = labelScan.status === 'scanning';

  return `
    <section class="add-panel">
      <div class="panel-title">
        <div>
          <p class="panel-title-meta">Nieuwe invoer</p>
          <h2>Nieuwe fles toevoegen</h2>
        </div>
        <button class="ghost-button" id="close-add">Sluiten</button>
      </div>
      <form id="add-form" class="wine-form compact">

        <!-- ── Foto-scan sectie ───────────────────────────────────────────── -->
        <div class="label-scan-section">
          <p class="form-group-label" style="margin-bottom:8px">
            Stap 1 — Foto van het etiket (optioneel)
          </p>
          ${labelScan.mode === 'upload' ? `
            <div class="label-scan-upload-confirm">
              <img src="${labelScan.previewUrl}" alt="Etiket" />
              <span>Foto wordt vrijstaand gemaakt bij opslaan</span>
              <button type="button" class="step-button" id="clear-label-scan"
                      style="width:auto;padding:0 14px" title="Foto verwijderen">${iconClose()}</button>
            </div>
          ` : `
            <label class="label-scan-drop ${labelScan.previewUrl ? 'has-preview' : ''}" id="label-scan-drop">
              ${labelScan.previewUrl
                ? `<img src="${labelScan.previewUrl}" class="label-scan-preview" alt="Etiket" />`
                : `<div class="label-scan-placeholder">
                     ${iconCamera()}
                     <span>Maak of kies een foto van het etiket</span>
                   </div>`
              }
              <input id="label-scan-input" type="file" accept="image/*"
                     class="img-upload-input" />
            </label>
            ${labelScan.previewUrl ? `
              <div class="label-scan-actions">
                ${labelScan.mode === '' ? `
                  <button type="button" class="save-button" id="do-label-scan" style="flex:1">
                    ${iconCamera()} Herken wijn
                  </button>
                  <button type="button" class="ghost-button" id="do-label-use" style="flex:1">
                    Vul zelf de gegevens in
                  </button>
                ` : `
                  <button type="button" class="save-button" id="do-label-scan"
                          style="flex:1" ${scanBusy ? 'disabled' : ''}>
                    ${scanBusy
                      ? `${iconSpinner()} Etiket lezen en gegevens ophalen…`
                      : `${iconCamera()} Herken wijn & vul formulier in`}
                  </button>
                `}
                <button type="button" class="step-button" id="clear-label-scan"
                        style="width:auto;padding:0 14px" title="Foto verwijderen">${iconClose()}</button>
              </div>
              ${labelScan.status === 'error'
                ? `<p class="supplier-error" style="margin-top:6px">⚠ ${esc(labelScan.error)}</p>`
                : ''}
            ` : ''}
          `}
        </div>

        <p class="form-group-label" style="margin-top:4px">Stap 2 — Controleer en vul aan</p>

        <!-- Naam + Opzoeken -->
        <div class="lookup-row form-field wide">
          <div class="lookup-label-row">
            <span>Naam *</span>
            ${lookupFeedback}
          </div>
          <div class="lookup-input-wrap">
            <input id="lookup-name" name="name"
                   value="${esc(p.name || '')}"
                   required
                   placeholder="Bijv. Alphonse Mellot La Moussière 2022" />
            <button type="button" class="lookup-btn ${lookupStatus === 'loading' ? 'loading' : ''}"
                    id="do-lookup"
                    ${lookupStatus === 'loading' ? 'disabled' : ''}>
              ${lookupStatus === 'loading' ? iconSpinner() : 'Opzoeken'}
            </button>
          </div>
        </div>

        <div class="form-row">
          ${formField('Soort',  'type',     p.type     || 'Wit')}
          ${formField('Aantal', 'quantity', p.quantity || 1, true, 'numeric')}
          ${formField('Jaar',   'year',     p.year     || '', false, 'numeric')}
        </div>
        ${selectFormField('Wijnkast', 'cabinet', CABINETS, p.cabinet || 'Niet ingedeeld')}
        <div class="form-row">
          ${formField('Druifsoort', 'grape',   p.grape   || '')}
          ${formField('Land',       'country', p.country || '')}
          ${formField('Regio',      'region',  p.region  || '')}
        </div>
        <p class="form-group-label">Waardering & prijs</p>
        <div class="form-row">
          ${formField('Vivino beoordeling', 'vivino',        p.vivino        || '', false, 'decimal')}
          ${formField('Inkoop/fles',   'purchasePrice', p.purchasePrice || '', false, 'decimal')}
          ${formField('Prijs/fles',    'currentPrice',  p.currentPrice  || '', false, 'decimal')}
        </div>
        <div class="form-row">
          <label class="form-field">
            Mijn score (1–10)
            <input type="number" name="score" min="1" max="10" step="1"
                   value="${esc(p.score || '')}" inputmode="numeric" placeholder="—" />
          </label>
        </div>
        <label class="form-field wide">
          Bron / opmerking
          <textarea name="note">${esc(p.note || '')}</textarea>
        </label>

        <p class="form-group-label">Leverancier</p>
        <div class="form-row">
          ${formField('Bedrijfsnaam',   'supplierName',    p.supplierName    || '')}
          ${formField('Contactpersoon', 'supplierContact', p.supplierContact || '')}
        </div>
        <div class="form-row">
          ${formField('Telefoonnummer', 'supplierPhone', p.supplierPhone || '', false, 'tel')}
          ${formField('E-mailadres',    'supplierEmail', p.supplierEmail || '', false, 'email')}
        </div>
        <label class="form-field wide">
          Adresgegevens
          <input name="supplierAddress" value="${esc(p.supplierAddress || '')}" />
        </label>

        <button class="save-button">Opslaan</button>
      </form>
    </section>
  `;
}

/* Scan panel */
function scanPanel() {
  const wineId = scanState.wineId || selectedId || wines[0]?.id || '';
  return `
    <section class="scan-panel">
      <div class="panel-title">
        <div>
          <p class="panel-title-meta">Fotoscan</p>
          <h2>Voorraad bijwerken via foto</h2>
        </div>
        <button class="ghost-button" id="close-scan">Sluiten</button>
      </div>
      <div class="scan-grid">
        <label class="scan-drop">
          ${scanState.image
            ? `<img src="${scanState.image}" alt="Gescand etiket" />`
            : '<span>Maak of kies een foto van het etiket</span>'}
          <input id="scan-image" type="file" accept="image/*" />
        </label>
        <div class="scan-actions">
          <p>${esc(scanState.note)}</p>
          <label class="form-field">
            Gekoppelde wijn
            <select id="scan-wine">
              ${wines.map(w =>
                `<option value="${w.id}" ${w.id === wineId ? 'selected' : ''}>${esc(w.name)} · ${esc(w.cabinet || '—')}</option>`
              ).join('')}
            </select>
          </label>
          <div class="scan-buttons">
            <button class="save-button" data-scan-action="add"   style="background:var(--c-brand)">Fles gekocht (+1)</button>
            <button class="danger-button" data-scan-action="remove">Fles genuttigd (−1)</button>
          </div>
          <button class="ghost-button" id="scan-new">Nieuwe wijn met foto</button>
        </div>
      </div>
    </section>
  `;
}

/* Analytics charts */
function analyticsCharts() {
  return `
    <div class="chart-grid">
      ${barChart('Flessen per soort',   groupSum(wines, 'type',    w => w.quantityNow), false)}
      ${barChart('Flessen per wijnkast',groupSum(wines, 'cabinet', w => w.quantityNow), false)}
      ${barChart('Waarde per land',     groupSum(wines, 'country', w => w.valueNow).slice(0, 7), true)}
      ${donutChart(groupSum(wines, 'type', w => w.valueNow))}
    </div>
  `;
}

/* Form helpers */
function formField(label, name, value = '', required = false, inputMode = '') {
  const mode = inputMode ? ` inputmode="${inputMode}"` : '';
  return `
    <label class="form-field">
      ${esc(label)}
      <input name="${name}" value="${esc(value ?? '')}"${mode}${required ? ' required' : ''} />
    </label>
  `;
}

function selectFormField(label, name, options, selected) {
  return `
    <label class="form-field">
      ${esc(label)}
      <select name="${name}">
        ${options.map(o => `<option value="${esc(o)}" ${o === selected ? 'selected' : ''}>${esc(o)}</option>`).join('')}
      </select>
    </label>
  `;
}

/* Charts */
function barChart(title, rows, isValue) {
  const max = Math.max(...rows.map(r => r[1]), 1);
  return `
    <article class="chart-card">
      <h3>${esc(title)}</h3>
      <div class="bar-list">
        ${rows.map(([label, val]) => `
          <div class="bar-row">
            <span>${esc(label)}</span>
            <div><i style="width:${Math.max(3, (val / max) * 100)}%"></i></div>
            <b>${isValue ? euro(val) : `${number(val)} fl`}</b>
          </div>
        `).join('')}
      </div>
    </article>
  `;
}

function donutChart(rows) {
  const total  = rows.reduce((s, r) => s + r[1], 0) || 1;
  const colors = ['#7f1d1d','#d99f3d','#256f63','#4267ac','#9a4d8f','#d85f45'];
  let offset = 0;
  const gradient = rows.map(([, val], i) => {
    const start = offset;
    offset += (val / total) * 100;
    return `${colors[i % colors.length]} ${start}% ${offset}%`;
  }).join(', ');

  return `
    <article class="chart-card donut-card">
      <h3>Waardeverdeling per soort</h3>
      <div class="donut-wrap">
        <div class="donut" style="background:conic-gradient(${gradient})">
          <span>${euro(total)}</span>
        </div>
        <div class="legend">
          ${rows.map(([label, val], i) =>
            `<span><i style="background:${colors[i % colors.length]}"></i>${esc(label)} · ${euro(val)}</span>`
          ).join('')}
        </div>
      </div>
    </article>
  `;
}


/* ================================================
   ICONS (inline SVG)
   ================================================ */
function iconCabinets() {
  return `<svg width="22" height="22" viewBox="0 0 22 22" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
    <rect x="2" y="3" width="18" height="16" rx="1.5"/>
    <line x1="2" y1="9"  x2="20" y2="9"/>
    <line x1="2" y1="15" x2="20" y2="15"/>
  </svg>`;
}
function iconList() {
  return `<svg width="22" height="22" viewBox="0 0 22 22" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
    <line x1="3" y1="6"  x2="19" y2="6"/>
    <line x1="3" y1="11" x2="19" y2="11"/>
    <line x1="3" y1="16" x2="19" y2="16"/>
  </svg>`;
}
function iconWine() {
  return `<svg width="22" height="22" viewBox="0 0 22 22" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
    <path d="M7 3h8l1 5a5 5 0 01-10 0L7 3z"/>
    <line x1="11" y1="13" x2="11" y2="19"/>
    <line x1="7.5" y1="19" x2="14.5" y2="19"/>
  </svg>`;
}
function iconChart() {
  return `<svg width="22" height="22" viewBox="0 0 22 22" fill="currentColor">
    <rect x="2"  y="12" width="5" height="8" rx="1"/>
    <rect x="8.5" y="7"  width="5" height="13" rx="1"/>
    <rect x="15" y="3"  width="5" height="17" rx="1"/>
  </svg>`;
}
function iconSpinner() {
  return `<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
    <circle cx="8" cy="8" r="6" stroke-opacity=".25"/>
    <path d="M8 2a6 6 0 0 1 6 6" class="spin"/>
  </svg>`;
}
function iconCamera() {
  return `<svg width="22" height="22" viewBox="0 0 22 22" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
    <path d="M2 8a2 2 0 012-2h1.5L7 4h8l1.5 2H18a2 2 0 012 2v9a2 2 0 01-2 2H4a2 2 0 01-2-2V8z"/>
    <circle cx="11" cy="12" r="3"/>
  </svg>`;
}
function iconWineType(type) {
  const fill = wineTypeColor(type).replace('var(--c-wine-red)', '#8b1f35')
                                   .replace('var(--c-wine-white)', '#a67c00')
                                   .replace('var(--c-wine-rose)', '#b5515d')
                                   .replace('var(--c-wine-other)', '#5a6b66');
  return `<svg width="18" height="18" viewBox="0 0 18 18" fill="none" class="type-icon" aria-hidden="true">
    <path d="M4 2.5 L14 2.5 L12 9 Q11 12 9 12 Q7 12 6 9 Z" fill="${fill}"/>
    <rect x="8.2" y="12" width="1.6" height="3.5" rx="0.8" fill="${fill}"/>
    <rect x="5.5" y="15.5" width="7" height="1.2" rx="0.6" fill="${fill}"/>
  </svg>`;
}
function iconPhoto() {
  return `<svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
    <rect x="1" y="3" width="16" height="12" rx="2"/>
    <circle cx="6" cy="8" r="1.5"/>
    <path d="M1 13 l4-4 3 3 3-3.5 5 5.5"/>
  </svg>`;
}
function iconClose() {
  return `<svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
    <line x1="2" y1="2" x2="12" y2="12"/>
    <line x1="12" y1="2" x2="2" y2="12"/>
  </svg>`;
}
function iconTrash() {
  return `<svg width="15" height="15" viewBox="0 0 15 15" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
    <path d="M2 4h11M5 4V2.5a.5.5 0 01.5-.5h4a.5.5 0 01.5.5V4M6 7v4M9 7v4M3 4l1 8.5a.5.5 0 00.5.5h6a.5.5 0 00.5-.5L12 4"/>
  </svg>`;
}
function iconZoom() {
  return `<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
    <circle cx="6.5" cy="6.5" r="4.5"/>
    <line x1="10" y1="10" x2="14" y2="14"/>
    <line x1="4.5" y1="6.5" x2="8.5" y2="6.5"/>
    <line x1="6.5" y1="4.5" x2="6.5" y2="8.5"/>
  </svg>`;
}
function iconGrapeInline(type) {
  const colors = { 'Rood': '#c43050', 'Wit': '#d4b020', 'Rosé': '#d86070' };
  const fill = colors[type] || '#8aacac';
  return `<svg width="12" height="15" viewBox="0 0 12 15" fill="${fill}" style="display:inline-block;vertical-align:-3px;flex-shrink:0" aria-hidden="true">
    <path d="M6 1.5 Q8 1 7.5 3" stroke="${fill}" stroke-width="0.8" fill="none" stroke-linecap="round"/>
    <circle cx="2"  cy="5"  r="2"/>
    <circle cx="6"  cy="5"  r="2"/>
    <circle cx="10" cy="5"  r="2"/>
    <circle cx="4"  cy="9"  r="2"/>
    <circle cx="8"  cy="9"  r="2"/>
    <circle cx="6"  cy="13" r="2"/>
  </svg>`;
}
function iconBottle() {
  return `<svg width="16" height="26" viewBox="0 0 16 26" fill="currentColor" aria-hidden="true">
    <rect x="5.5" y="0" width="5" height="3" rx="1.5"/>
    <path d="M6.5 3 L9.5 3 L9.5 6.5 Q13 8 13 10.5 L13 22 Q13 23.2 11.8 23.2 L4.2 23.2 Q3 23.2 3 22 L3 10.5 Q3 8 6.5 6.5 Z"/>
    <rect x="4.5" y="14" width="7" height="5" rx="1" fill-opacity=".2"/>
  </svg>`;
}
function listThumb(wine) {
  return `
    <div class="list-thumb">
      <img class="list-thumb-img" src="${wineThumbUrl(wine)}" alt=""
           onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">
      <div class="list-thumb-fallback">${iconBottle()}</div>
    </div>
  `;
}
function iconLogo(size = 32) {
  return `<svg width="${size}" height="${size}" viewBox="0 0 32 32" fill="none">
    <path d="M15 22 C11 21.5 4 17 4 12 C4 7 8.5 3 9 2 L23 2 C23.5 3 28 7 28 12 C28 17 21 21.5 17 22 Z" fill="#213f39"/>
    <path d="M5.5 16.5 C4.5 19 11 22 15 22 L17 22 C21 22 27.5 19 26.5 16.5 Z" fill="#8b1f35"/>
    <line x1="16" y1="22" x2="16" y2="28" stroke="#213f39" stroke-width="2" stroke-linecap="round"/>
    <path d="M10 28.5 Q16 27 22 28.5" stroke="#213f39" stroke-width="2" stroke-linecap="round" fill="none"/>
  </svg>`;
}


/* ================================================
   EVENT BINDING
   ================================================ */
function bindEvents() {
  /* Logo → terug naar hoofdoverzicht */
  document.querySelector('#logo-btn')?.addEventListener('click', () => {
    selectedId  = null;
    addOpen     = false;
    scanOpen    = false;
    filtersOpen = false;
    if (isMobile()) mobileView = 'list';
    render();
  });

  /* Wijnkasten */
  document.querySelector('#toggle-cabinets')?.addEventListener('click', () => { cabinetsOpen = !cabinetsOpen; render(); });

  /* Add / scan panels */
  document.querySelector('#open-add')?.addEventListener('click', () => { addOpen = true; render(); });
  document.querySelector('#open-scan')?.addEventListener('click', () => { scanOpen = true; render(); });
  document.querySelector('#close-add')?.addEventListener('click', () => {
    addOpen = false; addPrefill = {}; lookupStatus = '';
    if (labelScan.previewUrl) URL.revokeObjectURL(labelScan.previewUrl);
    labelScan = { file: null, previewUrl: null, status: '', error: '', mode: '' };
    render();
  });
  document.querySelector('#close-scan')?.addEventListener('click', () => { scanOpen = false; render(); });

  /* Label-scan: foto → wijn herkennen */
  document.querySelector('#label-scan-input')?.addEventListener('change', e => {
    const file = e.target.files[0];
    if (!file) return;
    if (labelScan.previewUrl) URL.revokeObjectURL(labelScan.previewUrl);
    labelScan = { file, previewUrl: URL.createObjectURL(file), status: '', error: '' };
    lookupStatus = '';
    addPrefill = {};
    render();
  });
  document.querySelector('#do-label-scan')?.addEventListener('click', () => {
    if (labelScan.mode !== 'scan') labelScan = { ...labelScan, mode: 'scan' };
    handleLabelScan();
  });
  document.querySelector('#do-label-use')?.addEventListener('click', () => {
    labelScan = { ...labelScan, mode: 'upload', status: '', error: '' };
    render();
  });
  document.querySelector('#clear-label-scan')?.addEventListener('click', () => {
    if (labelScan.previewUrl) URL.revokeObjectURL(labelScan.previewUrl);
    labelScan = { file: null, previewUrl: null, status: '', error: '', mode: '' };
    render();
  });

  /* Wijn opzoeken */
  document.querySelector('#do-lookup')?.addEventListener('click', handleLookup);
  document.querySelector('#lookup-name')?.addEventListener('keydown', e => {
    if (e.key === 'Enter') { e.preventDefault(); handleLookup(); }
  });

  /* Mobile nav tabs */
  document.querySelectorAll('[data-nav]').forEach(btn => {
    btn.addEventListener('click', () => { mobileView = btn.dataset.nav; scanOpen = false; render(); });
  });
  document.querySelectorAll('[data-scan-nav]').forEach(btn => {
    btn.addEventListener('click', () => { scanOpen = true; render(); });
  });

  /* Filter toggle (mobile) */
  document.querySelector('#toggle-filters')?.addEventListener('click', () => { filtersOpen = !filtersOpen; render(); });

  /* Wine selection */
  document.querySelectorAll('[data-select]').forEach(btn => {
    btn.addEventListener('click', () => {
      const newId = btn.dataset.select;
      if (newId !== selectedId) {
        supplierSearch = { wineId: null, status: '', results: [], error: '' };
        imagePicker   = { wineId: null, open: false, status: '', images: [], source: '', proposed: null, error: '' };
        if (uploadState.previewUrl) URL.revokeObjectURL(uploadState.previewUrl);
        uploadState   = { file: null, previewUrl: null, status: '', error: '' };
      }
      selectedId = newId;
      cabinetsOpen = false;
      if (isMobile()) mobileView = 'detail';
      render();
    });
  });

  /* Bestel online */
  document.querySelector('#find-suppliers')?.addEventListener('click', () => {
    handleFindSuppliers(getSelected());
  });

  /* Afbeeldingskiezer */
  document.querySelector('#open-img-picker')?.addEventListener('click', () => {
    handleOpenImagePicker(getSelected());
  });
  document.querySelector('#choice-vivino')?.addEventListener('click', () => {
    triggerAutoImageCheck(getSelected());
  });
  document.querySelector('#choice-upload')?.addEventListener('click', () => {
    imagePicker = { ...imagePicker, status: 'upload' };
    render();
  });
  document.querySelector('#open-zoom')?.addEventListener('click', () => {
    const wine = getSelected();
    if (wine) { zoomedWineId = wine.id; render(); }
  });
  document.querySelector('#bottle-img-tap')?.addEventListener('click', () => {
    const wine = getSelected();
    if (wine) { zoomedWineId = wine.id; render(); }
  });
  document.querySelector('#delete-img')?.addEventListener('click', () => {
    handleDeleteImage(getSelected());
  });
  document.querySelectorAll('[data-img-url]').forEach(btn => {
    btn.addEventListener('click', () => handleSelectImage(getSelected(), btn.dataset.imgUrl));
  });
  document.querySelector('#confirm-proposed')?.addEventListener('click', () => {
    handleConfirmProposed(getSelected());
  });
  document.querySelector('#discard-proposed')?.addEventListener('click', () => {
    handleDiscardProposed(getSelected());
  });
  document.querySelector('#upload-img-input')?.addEventListener('change', e => {
    const file = e.target.files[0];
    if (!file) return;
    if (uploadState.previewUrl) URL.revokeObjectURL(uploadState.previewUrl);
    uploadState = { file, previewUrl: URL.createObjectURL(file), status: '', error: '' };
    render();
  });
  document.querySelector('#do-upload-img')?.addEventListener('click', async () => {
    const w = getSelected();
    await handleUploadImage(w);
    // Ververs de lijst zodat de nieuwe thumbnail direct zichtbaar is
    const formData = getFormData(document.querySelector('#edit-form'));
    if (formData && w.rowNumber) {
      await saveWine({ ...formData, quantity: document.querySelector('#quantity')?.value ?? w.quantityNow });
    }
  });
  document.querySelector('#cancel-upload')?.addEventListener('click', () => {
    if (uploadState.previewUrl) URL.revokeObjectURL(uploadState.previewUrl);
    uploadState = { file: null, previewUrl: null, status: '', error: '' };
    render();
  });
  document.querySelector('#use-custom-url')?.addEventListener('click', () => {
    const url = document.querySelector('#custom-img-url')?.value?.trim();
    if (url) handleSelectImage(getSelected(), url);
  });
  document.querySelector('#custom-img-url')?.addEventListener('keydown', e => {
    if (e.key === 'Enter') {
      e.preventDefault();
      const url = e.target.value.trim();
      if (url) handleSelectImage(getSelected(), url);
    }
  });

  /* Search */
  const searchInput = document.querySelector('#search');
  if (searchInput) {
    searchInput.addEventListener('input', e => {
      filters.search = e.target.value;
      render();
      document.querySelector('#search')?.focus();
    });
  }

  /* Filter dropdowns */
  ['type', 'country', 'cabinet', 'sort'].forEach(id => {
    document.querySelector(`#${id}`)?.addEventListener('change', e => { filters[id] = e.target.value; render(); });
  });

  /* Collapsible sections — toggle CSS only, no re-render (preserves unsaved form values) */
  document.querySelectorAll('[data-toggle-section]').forEach(btn => {
    btn.addEventListener('click', () => {
      const key = btn.dataset.toggleSection;
      const wasOpen = btn.classList.contains('open');
      collapsedSections[key] = wasOpen;
      btn.classList.toggle('open', !wasOpen);
      const body = btn.nextElementSibling;
      if (body?.classList.contains('section-body')) {
        body.classList.toggle('section-collapsed', wasOpen);
      }
    });
  });

  /* Quantity */
  document.querySelector('#quantity')?.addEventListener('change', e => {
    const w = getSelected();
    saveWine({ rowNumber: w.rowNumber, quantity: e.target.value });
  });
  document.querySelectorAll('[data-step]').forEach(btn => {
    btn.addEventListener('click', () => {
      const w = getSelected();
      saveWine({ rowNumber: w.rowNumber, quantity: Math.max(0, w.quantityNow + Number(btn.dataset.step)) });
    });
  });

  document.querySelector('#delete-wine')?.addEventListener('click', () => {
    deleteWine(getSelected());
  });

  /* Edit form */
  document.querySelector('#edit-form')?.addEventListener('submit', async e => {
    e.preventDefault();
    const w = getSelected();
    const formData = getFormData(e.currentTarget);
    const quantity = document.querySelector('#quantity')?.value ?? w.quantityNow;
    if (uploadState.file) {
      await handleUploadImage(w);
    }
    await saveWine({ ...formData, quantity });
  });

  /* Add form */
  document.querySelector('#add-form')?.addEventListener('submit', async e => {
    e.preventDefault();
    await addWine(getFormData(e.currentTarget));
  });

  /* Scan: image upload */
  document.querySelector('#scan-image')?.addEventListener('change', e => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.addEventListener('load', () => {
      scanState.image = reader.result;
      scanState.note  = 'Foto toegevoegd. Kies de wijn en werk de voorraad bij.';
      render();
    });
    reader.readAsDataURL(file);
  });

  document.querySelector('#scan-wine')?.addEventListener('change', e => { scanState.wineId = e.target.value; });

  document.querySelectorAll('[data-scan-action]').forEach(btn => {
    btn.addEventListener('click', () => {
      const wine  = wines.find(w => w.id === (scanState.wineId || selectedId)) || getSelected();
      const delta = btn.dataset.scanAction === 'add' ? 1 : -1;
      scanState.wineId = wine.id;
      selectedId       = wine.id;
      scanState.note   = delta > 0 ? 'Voorraad verhoogd (+1).' : 'Voorraad verlaagd (−1).';
      saveWine({ rowNumber: wine.rowNumber, quantity: Math.max(0, wine.quantityNow + delta) });
    });
  });

  document.querySelector('#scan-new')?.addEventListener('click', () => {
    scanOpen = false;
    addOpen  = true;
    render();
  });
}

function getFormData(form) {
  return Object.fromEntries(new FormData(form));
}


/* ================================================
   INIT
   ================================================ */
render();
loadWines();

// Versiecheck: herlaad de app als de server is herstart
// localStorage blijft bewaard na afsluiten PWA (sessionStorage niet)
// location.replace met ?nocache= parameter omzeilt iOS PWA-cache
(async () => {
  try {
    if (location.search.includes('nocache')) {
      history.replaceState(null, '', '/');
    }
    const r = await fetch('/api/version');
    const { version } = await r.json();
    const stored = localStorage.getItem('appVersion');
    if (stored && stored !== version && !location.search.includes('nocache')) {
      localStorage.setItem('appVersion', version);
      location.replace('/?nocache=' + version);
    } else {
      localStorage.setItem('appVersion', version);
    }
  } catch { /* geen verbinding, stil doorgaan */ }
})();
