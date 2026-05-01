function readJsonScript(id) {
  const el = document.getElementById(id);
  if (!el) return null;
  try {
    return JSON.parse(el.textContent || 'null');
  } catch {
    return null;
  }
}

function norm(s) {
  return (s || '').toString().trim().toLowerCase();
}

function getSelectedBrandId() {
  const sel = document.querySelector('form#pm-ads-filters select[name="car_brand"]');
  if (!sel) return '';
  return (sel.value || '').trim();
}

function setModelValue(val) {
  const hidden = document.getElementById('pm-ads-car-model');
  const label = document.getElementById('pm-ads-car-model-label');
  if (hidden) hidden.value = val || '';
  if (label) label.value = val || '';
  const clearBtn = document.getElementById('pm-ads-clear-model');
  if (clearBtn) clearBtn.disabled = !(val || '').trim();
}

function submitFilters() {
  const f = document.getElementById('pm-ads-filters');
  if (f) f.submit();
}

function renderModelList(models) {
  const list = document.getElementById('pm-ads-model-list');
  const empty = document.getElementById('pm-ads-model-empty');
  if (!list || !empty) return;
  list.innerHTML = '';
  if (!models || !models.length) {
    empty.classList.remove('d-none');
    return;
  }
  empty.classList.add('d-none');
  for (const m of models) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'list-group-item list-group-item-action';
    btn.textContent = m;
    btn.addEventListener('click', () => {
      setModelValue(m);
      const modalEl = document.getElementById('pmCarModelModal');
      if (modalEl && window.bootstrap) {
        const inst = window.bootstrap.Modal.getInstance(modalEl) || new window.bootstrap.Modal(modalEl);
        inst.hide();
      }
      submitFilters();
    });
    list.appendChild(btn);
  }
}

function wireCarModelPopup() {
  const modelsByBrand = readJsonScript('pm-ads-car-models-by-brand') || {};

  const brandSel = document.querySelector('form#pm-ads-filters select[name="car_brand"]');
  const pickBtn = document.getElementById('pm-ads-pick-model-btn');
  const clearBtn = document.getElementById('pm-ads-clear-model');
  const search = document.getElementById('pm-ads-model-search');

  if (!brandSel || !pickBtn || !clearBtn) return;

  let currentModels = [];

  const refreshForBrand = (openModal) => {
    const brandId = getSelectedBrandId();
    currentModels = (brandId && modelsByBrand[brandId]) ? modelsByBrand[brandId] : [];
    pickBtn.disabled = !brandId;

    // если марку сбросили — сбрасываем модель
    if (!brandId) {
      if ((document.getElementById('pm-ads-car-model')?.value || '').trim()) {
        setModelValue('');
        submitFilters();
      }
      return;
    }

    // если бренд поменяли — показываем модалку, чтобы выбрать модель
    if (openModal) {
      renderModelList(currentModels);
      if (search) search.value = '';
      const modalEl = document.getElementById('pmCarModelModal');
      if (modalEl && window.bootstrap) {
        const inst = window.bootstrap.Modal.getOrCreateInstance(modalEl);
        inst.show();
      }
    }
  };

  brandSel.addEventListener('change', () => {
    // при смене марки модель сбрасываем (чтобы не было несоответствия)
    setModelValue('');
    refreshForBrand(true);
  });

  pickBtn.addEventListener('click', () => {
    refreshForBrand(false);
    renderModelList(currentModels);
  });

  clearBtn.addEventListener('click', () => {
    setModelValue('');
    submitFilters();
  });

  if (search) {
    search.addEventListener('input', () => {
      const q = norm(search.value);
      if (!q) {
        renderModelList(currentModels);
        return;
      }
      renderModelList(currentModels.filter((m) => norm(m).includes(q)));
    });
  }

  // initial state
  refreshForBrand(false);
}

document.addEventListener('DOMContentLoaded', () => {
  wireCarModelPopup();
});

