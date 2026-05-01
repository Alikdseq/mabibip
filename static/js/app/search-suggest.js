export function initSearchSuggest(root, opts) {
  const input = root.querySelector(opts.inputSelector || 'input[type="search"]');
  const panel = root.querySelector(opts.panelSelector || '[data-suggest-panel]');
  if (!input || !panel) return;

  const suggestUrlEl = document.getElementById(opts.suggestUrlScriptId || 'suggest-url');
  const suggestUrl = suggestUrlEl ? JSON.parse(suggestUrlEl.textContent || '""') : '';
  if (!suggestUrl) return;

  const limits = opts.limits || {
    services: 8,
    sections: 6,
    masters: 4,
    stations: 4,
  };

  let open = false;
  let loading = false;
  let results = [];
  let ambiguous = '';
  let blurTimer = null;
  let debounce = null;

  const render = () => {
    panel.innerHTML = '';
    if (!open) {
      panel.classList.add('d-none');
      return;
    }
    panel.classList.remove('d-none');

    if (loading) {
      panel.innerHTML =
        '<div class="list-group-item small text-muted py-3">Подбираем варианты…</div>';
      return;
    }

    if (ambiguous) {
      const amb = document.createElement('div');
      amb.className = 'list-group-item small text-primary py-2';
      amb.textContent = ambiguous;
      panel.appendChild(amb);
    }

    if (!results.length && input.value.trim().length >= 1) {
      const empty = document.createElement('div');
      empty.className = 'list-group-item small text-muted py-2';
      empty.textContent = 'Ничего не нашли — попробуйте другую формулировку.';
      panel.appendChild(empty);
      return;
    }

    results.forEach((row) => {
      const a = document.createElement('a');
      a.className = 'list-group-item list-group-item-action py-2';
      a.href = row.url;
      a.innerHTML = `<span class="fw-medium">${escapeHtml(row.label || '')}</span>
        <span class="d-block small text-muted">${escapeHtml(row.hint || '')}</span>`;
      panel.appendChild(a);
    });
  };

  const escapeHtml = (s) =>
    String(s)
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');

  const fetchSuggestions = () => {
    const q = input.value.trim();
    if (q.length < 2) {
      results = [];
      ambiguous = '';
      loading = false;
      open = false;
      render();
      return;
    }
    open = true;
    render();
    clearTimeout(debounce);
    debounce = setTimeout(async () => {
      loading = true;
      render();
      try {
        const r = await fetch(
          `${suggestUrl}?q=${encodeURIComponent(q)}` +
            `&limit_services=${limits.services}` +
            `&limit_sections=${limits.sections}` +
            `&limit_masters=${limits.masters}` +
            `&limit_stations=${limits.stations}`
        );
        if (!r.ok) throw new Error(String(r.status));
        const data = await r.json();
        results = (data.results || []).slice(0, opts.maxRows || 20);
        ambiguous = data.ambiguous_hint || '';
      } catch {
        results = [];
        ambiguous = '';
      } finally {
        loading = false;
        render();
      }
    }, opts.debounceMs || 320);
  };

  input.addEventListener('input', fetchSuggestions);
  input.addEventListener('focus', () => {
    clearTimeout(blurTimer);
    open = true;
    fetchSuggestions();
  });
  input.addEventListener('blur', () => {
    clearTimeout(blurTimer);
    blurTimer = setTimeout(() => {
      open = false;
      render();
    }, 220);
  });
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      open = false;
      render();
    }
  });

  // initial
  panel.classList.add('list-group', 'position-absolute', 'shadow', 'border-primary', 'border-opacity-25', 'w-100', 'mt-1', 'rounded-3', 'overflow-hidden');
  panel.style.maxHeight = panel.style.maxHeight || '360px';
  panel.style.overflowY = panel.style.overflowY || 'auto';
  panel.style.zIndex = panel.style.zIndex || '1070';
  panel.classList.add('d-none');
}

