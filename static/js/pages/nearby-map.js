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

(() => {
  const points = readJsonScript('nearby-map-points') || [];
  const userLat = readJsonScript('nearby-user-lat');
  const userLng = readJsonScript('nearby-user-lng');
  const nearbyListUrl = readJsonScript('nearby-list-url') || '';
  const placesApiUrl = readJsonScript('map-places-api-url') || '';

  function goWithCoords(lat, lng) {
    const u = new URL(nearbyListUrl, window.location.origin);
    u.searchParams.set('lat', lat);
    u.searchParams.set('lng', lng);
    u.searchParams.set('radius_km', '10');
    window.location.href = u.pathname + u.search;
  }

  function readTypes() {
    const out = [];
    const sto = document.getElementById('pm-map-type-sto');
    const master = document.getElementById('pm-map-type-master');
    const shop = document.getElementById('pm-map-type-shop');
    if (sto && sto.checked) out.push('sto');
    if (master && master.checked) out.push('master');
    if (shop && shop.checked) out.push('autoshop');
    return out;
  }

  function readFilters() {
    const brandEl = document.getElementById('pm-map-brand');
    const sectionEl = document.getElementById('pm-map-section');
    return {
      brand: brandEl ? (brandEl.value || '').trim() : '',
      section: sectionEl ? (sectionEl.value || '').trim() : '',
      types: readTypes(),
    };
  }

  const btn = document.getElementById('btn-geo-locate');
  if (btn) {
    btn.addEventListener('click', () => {
      if (!navigator.geolocation) {
        alert('Геолокация не поддерживается браузером');
        return;
      }
      btn.disabled = true;
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          try {
            localStorage.setItem(
              'pm_last_geo',
              JSON.stringify({
                lat: pos.coords.latitude,
                lng: pos.coords.longitude,
                ts: Date.now(),
              })
            );
          } catch {}
          goWithCoords(pos.coords.latitude, pos.coords.longitude);
        },
        () => {
          btn.disabled = false;
          alert('Не удалось получить координаты. Проверьте разрешения и что сайт открыт по HTTPS или localhost.');
        },
        { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 }
      );
    });
  }

  if (userLat == null || userLng == null) return;
  if (!window.L) return;

  const map = window.L.map('nearby-map');
  window.L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  }).addTo(map);

  const userIcon = window.L.divIcon({
    className: 'nearby-user-marker',
    html: '<span style="display:block;width:14px;height:14px;border-radius:50%;background:#0d6efd;border:2px solid #fff;box-shadow:0 0 4px rgba(0,0,0,.4);"></span>',
    iconSize: [14, 14],
    iconAnchor: [7, 7],
  });

  window.L.marker([userLat, userLng], { icon: userIcon, zIndexOffset: 1000 }).addTo(map).bindPopup('Вы здесь');

  const bounds = window.L.latLngBounds([userLat, userLng], [userLat, userLng]);
  points.forEach((p) => bounds.extend([p.lat, p.lon]));
  if (points.length) map.fitBounds(bounds.pad(0.12));
  else map.setView([userLat, userLng], 12);

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

  let debounce = null;
  async function loadPlaces() {
    if (!placesApiUrl) return;
    const b = map.getBounds();
    const bbox = [
      b.getWest().toFixed(6),
      b.getSouth().toFixed(6),
      b.getEast().toFixed(6),
      b.getNorth().toFixed(6),
    ].join(',');
    const f = readFilters();
    const u = new URL(placesApiUrl, window.location.origin);
    u.searchParams.set('bbox', bbox);
    if (f.types && f.types.length) u.searchParams.set('types', f.types.join(','));
    if (f.brand) u.searchParams.set('brand', f.brand);
    if (f.section) u.searchParams.set('section', f.section);

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
      // молча: карта должна оставаться интерактивной даже при сетевых сбоях
    }
  }

  function scheduleLoad() {
    clearTimeout(debounce);
    debounce = setTimeout(loadPlaces, 280);
  }

  map.on('moveend', scheduleLoad);
  const brandEl = document.getElementById('pm-map-brand');
  const sectionEl = document.getElementById('pm-map-section');
  ['pm-map-type-sto', 'pm-map-type-master', 'pm-map-type-shop'].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('change', scheduleLoad);
  });
  if (brandEl) brandEl.addEventListener('change', scheduleLoad);
  if (sectionEl) sectionEl.addEventListener('change', scheduleLoad);

  // initial load
  loadPlaces();
})();

