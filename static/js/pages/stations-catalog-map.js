function readJsonScript(id) {
  const el = document.getElementById(id);
  if (!el) return null;
  try {
    return JSON.parse(el.textContent || 'null');
  } catch {
    return null;
  }
}

function escapeHtml(s) {
  if (!s) return '';
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

function escapeAttr(s) {
  return String(s ?? '').replace(/"/g, '&quot;');
}

function getActiveTypes() {
  const sto = document.getElementById('pm-cat-map-type-sto');
  const master = document.getElementById('pm-cat-map-type-master');
  const shop = document.getElementById('pm-cat-map-type-shop');
  const out = [];
  if (sto && sto.checked) out.push('sto');
  if (master && master.checked) out.push('master');
  if (shop && shop.checked) out.push('autoshop');
  return out;
}

(() => {
  const apiUrl = readJsonScript('map-places-api-url') || '';
  const initialFilters = readJsonScript('catalog-map-filters') || {};
  const initialLatRaw = readJsonScript('catalog-user-lat');
  const initialLngRaw = readJsonScript('catalog-user-lng');
  const initialLat = initialLatRaw != null && String(initialLatRaw).trim() !== '' ? Number(initialLatRaw) : null;
  const initialLng = initialLngRaw != null && String(initialLngRaw).trim() !== '' ? Number(initialLngRaw) : null;
  if (!apiUrl || !window.L) return;

  const map = window.L.map('catalog-map');
  window.L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  }).addTo(map);

  const layer = window.L.layerGroup().addTo(map);

  const icons = {
    sto: window.L.divIcon({
      className: 'pm-map-icon pm-map-icon-sto',
      html: '<span style="display:block;width:18px;height:18px;border-radius:50%;background:#198754;border:2px solid #fff;box-shadow:0 0 6px rgba(0,0,0,.35);"></span>',
      iconSize: [18, 18],
      iconAnchor: [9, 9],
    }),
    master: window.L.divIcon({
      className: 'pm-map-icon pm-map-icon-master',
      html: '<span style="display:block;width:18px;height:18px;border-radius:50%;background:#0d6efd;border:2px solid #fff;box-shadow:0 0 6px rgba(0,0,0,.35);"></span>',
      iconSize: [18, 18],
      iconAnchor: [9, 9],
    }),
    autoshop: window.L.divIcon({
      className: 'pm-map-icon pm-map-icon-shop',
      html: '<span style="display:block;width:18px;height:18px;border-radius:50%;background:#fd7e14;border:2px solid #fff;box-shadow:0 0 6px rgba(0,0,0,.35);"></span>',
      iconSize: [18, 18],
      iconAnchor: [9, 9],
    }),
  };

  const userIcon = window.L.divIcon({
    className: 'nearby-user-marker',
    html: '<span style="display:block;width:14px;height:14px;border-radius:50%;background:#0d6efd;border:2px solid #fff;box-shadow:0 0 4px rgba(0,0,0,.4);"></span>',
    iconSize: [14, 14],
    iconAnchor: [7, 7],
  });

  function setInitialView() {
    if (initialLat != null && initialLng != null) {
      map.setView([initialLat, initialLng], 12);
      window.L.marker([initialLat, initialLng], { icon: userIcon, zIndexOffset: 1000 })
        .addTo(map)
        .bindPopup('Вы здесь');
      return;
    }
    // fallback: Vladikavkaz-ish
    map.setView([43.05, 44.68], 12);
  }

  setInitialView();

  let debounce = null;
  async function loadPlaces() {
    const b = map.getBounds();
    const bbox = [
      b.getWest().toFixed(6),
      b.getSouth().toFixed(6),
      b.getEast().toFixed(6),
      b.getNorth().toFixed(6),
    ].join(',');

    const u = new URL(apiUrl, window.location.origin);
    u.searchParams.set('bbox', bbox);

    const types = getActiveTypes();
    if (types.length) u.searchParams.set('types', types.join(','));

    // apply catalog filters we received from server
    if (initialFilters.brand) u.searchParams.set('brand', initialFilters.brand);
    if (initialFilters.section) u.searchParams.set('section', initialFilters.section);
    if (initialFilters.service) u.searchParams.set('service', initialFilters.service);
    if (initialFilters.cat && initialFilters.cat.length) {
      initialFilters.cat.forEach((x) => u.searchParams.append('cat', String(x)));
    }
    if (initialFilters.exec && initialFilters.exec.length) {
      initialFilters.exec.forEach((x) => u.searchParams.append('exec', String(x)));
    }

    try {
      const r = await fetch(u.pathname + u.search);
      if (!r.ok) throw new Error(String(r.status));
      const data = await r.json();
      const rows = data.results || [];
      layer.clearLayers();
      rows.forEach((p) => {
        const ic = icons[p.type] || null;
        const m = window.L.marker([p.lat, p.lng], ic ? { icon: ic } : undefined).addTo(layer);
        m.bindPopup(
          '<strong>' +
            escapeHtml(p.label) +
            '</strong><br>' +
            escapeHtml(p.hint || '') +
            '<br><a href="' +
            escapeAttr(p.url) +
            '">Открыть</a>'
        );
      });
    } catch {
      // best-effort
    }
  }

  function scheduleLoad() {
    clearTimeout(debounce);
    debounce = setTimeout(loadPlaces, 280);
  }

  map.on('moveend', scheduleLoad);
  ['pm-cat-map-type-sto', 'pm-cat-map-type-master', 'pm-cat-map-type-shop'].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('change', scheduleLoad);
  });

  loadPlaces();
})();

