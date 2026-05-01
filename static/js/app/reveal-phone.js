function getCsrfToken() {
  const el = document.querySelector('input[name="csrfmiddlewaretoken"]');
  return el ? el.value : '';
}

function lsGetJson(key) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function lsSetJson(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // ignore
  }
}

function lsRemove(key) {
  try {
    localStorage.removeItem(key);
  } catch {
    // ignore
  }
}

function fmtTimeLeft(ms) {
  const sec = Math.max(0, Math.floor(ms / 1000));
  const m = String(Math.floor(sec / 60)).padStart(2, '0');
  const s = String(sec % 60).padStart(2, '0');
  return `${m}:${s}`;
}

function ensureSafetyModal() {
  let modalEl = document.getElementById('pmSafetyRevealModal');
  if (modalEl) return modalEl;

  modalEl = document.createElement('div');
  modalEl.className = 'modal fade';
  modalEl.id = 'pmSafetyRevealModal';
  modalEl.tabIndex = -1;
  modalEl.setAttribute('aria-hidden', 'true');
  modalEl.innerHTML = `
    <div class="modal-dialog">
      <div class="modal-content">
        <div class="modal-header">
          <h2 class="modal-title h5">Безопасность</h2>
          <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Закрыть"></button>
        </div>
        <div class="modal-body">
          <p class="mb-2">
            Платформа «МаБибип» не проверяет объявления и не участвует в правоотношениях Покупателя и Продавца.
            Будьте внимательны и проверяйте продавца и товар самостоятельно.
          </p>
          <div class="form-check">
            <input class="form-check-input" type="checkbox" value="1" id="pmSafetyRevealAcknowledge" required>
            <label class="form-check-label" for="pmSafetyRevealAcknowledge">
              Я понимаю, что совершаю сделку напрямую с продавцом, платформа не отвечает за товар и оплату
            </label>
          </div>
          <div class="form-check mt-2">
            <input class="form-check-input" type="checkbox" value="1" id="pmSafetyRevealSeen">
            <label class="form-check-label" for="pmSafetyRevealSeen">Больше не показывать</label>
          </div>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Отмена</button>
          <button type="button" class="btn btn-primary" id="pmSafetyRevealConfirm">Показать номер</button>
        </div>
      </div>
    </div>
  `;
  document.body.appendChild(modalEl);
  return modalEl;
}

function ensureSafetyContactModal() {
  let modalEl = document.getElementById('pmSafetyContactModal');
  if (modalEl) return modalEl;

  modalEl = document.createElement('div');
  modalEl.className = 'modal fade';
  modalEl.id = 'pmSafetyContactModal';
  modalEl.tabIndex = -1;
  modalEl.setAttribute('aria-hidden', 'true');
  modalEl.innerHTML = `
    <div class="modal-dialog">
      <div class="modal-content">
        <div class="modal-header">
          <h2 class="modal-title h5">Безопасность</h2>
          <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Закрыть"></button>
        </div>
        <div class="modal-body">
          <p class="mb-2">Перед тем как звонить или писать, убедитесь, что объявление реальное. Не переводите предоплату незнакомым людям.</p>
          <div class="form-check">
            <input class="form-check-input" type="checkbox" value="1" id="pmSafetyContactSeen">
            <label class="form-check-label" for="pmSafetyContactSeen">Больше не показывать</label>
          </div>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Отмена</button>
          <button type="button" class="btn btn-primary" id="pmSafetyContactConfirm">Продолжить</button>
        </div>
      </div>
    </div>
  `;
  document.body.appendChild(modalEl);
  return modalEl;
}

function revealKey(adId) {
  return `ad_phone_reveal_${adId}`;
}

function applyRevealedUI(adId, payload) {
  const blocks = document.querySelectorAll(`[data-pm-reveal-ad-id="${adId}"]`);
  blocks.forEach((block) => {
    const btn = block.querySelector('.js-pm-reveal-phone');
    const phoneEl = block.querySelector('.js-pm-phone-display');
    const telA = block.querySelector('.js-pm-tel-href');
    const timerEl = block.querySelector('.js-pm-reveal-timer');
    const maskedEl = block.querySelector('.js-pm-phone-masked');

    if (maskedEl) maskedEl.classList.add('d-none');
    if (btn) btn.classList.add('d-none');
    if (phoneEl) {
      phoneEl.textContent = payload.phone_display || '';
      phoneEl.classList.remove('d-none');
      phoneEl.classList.add('pm-no-copy');
      phoneEl.setAttribute('aria-live', 'polite');
    }
    if (telA) {
      telA.href = payload.phone_e164 ? `tel:${payload.phone_e164}` : '#';
      telA.classList.remove('disabled');
      telA.removeAttribute('aria-disabled');
    }
    if (timerEl) timerEl.classList.remove('d-none');
  });
}

function applyMaskedUI(adId) {
  const blocks = document.querySelectorAll(`[data-pm-reveal-ad-id="${adId}"]`);
  blocks.forEach((block) => {
    const btn = block.querySelector('.js-pm-reveal-phone');
    const phoneEl = block.querySelector('.js-pm-phone-display');
    const telA = block.querySelector('.js-pm-tel-href');
    const timerEl = block.querySelector('.js-pm-reveal-timer');
    const maskedEl = block.querySelector('.js-pm-phone-masked');

    if (maskedEl) maskedEl.classList.remove('d-none');
    if (btn) btn.classList.remove('d-none');
    if (phoneEl) phoneEl.classList.add('d-none');
    if (telA) {
      telA.href = '#';
      telA.classList.add('disabled');
      telA.setAttribute('aria-disabled', 'true');
    }
    if (timerEl) timerEl.classList.add('d-none');
  });
}

async function fetchReveal(adId) {
  const resp = await fetch(`/api/ads/${adId}/reveal-phone/`, {
    method: 'GET',
    headers: {
      'X-CSRFToken': getCsrfToken(),
      'X-Requested-With': 'XMLHttpRequest',
    },
    credentials: 'same-origin',
  });
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    const msg = data && data.error ? data.error : 'Не удалось раскрыть телефон.';
    throw new Error(msg);
  }
  return data;
}

function initFromLocalStorage() {
  const blocks = document.querySelectorAll('[data-pm-reveal-ad-id]');
  blocks.forEach((block) => {
    const adId = block.getAttribute('data-pm-reveal-ad-id');
    if (!adId) return;
    const st = lsGetJson(revealKey(adId));
    if (!st || !st.untilMs || !st.phone_e164) return;
    if (Date.now() > st.untilMs) {
      lsRemove(revealKey(adId));
      applyMaskedUI(adId);
      return;
    }
    applyRevealedUI(adId, st);
  });
}

function startTimerLoop() {
  setInterval(() => {
    const blocks = document.querySelectorAll('[data-pm-reveal-ad-id]');
    blocks.forEach((block) => {
      const adId = block.getAttribute('data-pm-reveal-ad-id');
      if (!adId) return;
      const timerEl = block.querySelector('.js-pm-reveal-timer');
      if (!timerEl || timerEl.classList.contains('d-none')) return;
      const st = lsGetJson(revealKey(adId));
      if (!st || !st.untilMs) return;
      const left = st.untilMs - Date.now();
      if (left <= 0) {
        lsRemove(revealKey(adId));
        applyMaskedUI(adId);
        return;
      }
      timerEl.textContent = `Скрытие через ${fmtTimeLeft(left)}`;
    });
  }, 1000);
}

function isSafetySeen() {
  return lsGetJson('safety_warning_seen') === 1 || localStorage.getItem('safety_warning_seen') === '1';
}

function setSafetySeen() {
  try {
    localStorage.setItem('safety_warning_seen', '1');
  } catch {
    // ignore
  }
}

async function handleRevealClick(btn) {
  const adId = btn.getAttribute('data-ad-id');
  if (!adId) return;

  // Already revealed?
  const st = lsGetJson(revealKey(adId));
  if (st && st.untilMs && Date.now() < st.untilMs && st.phone_e164) {
    applyRevealedUI(adId, st);
    return;
  }

  const doReveal = async () => {
    btn.disabled = true;
    try {
      const data = await fetchReveal(adId);
      const untilMs = Date.now() + (data.revealed_for_sec || 300) * 1000;
      const stored = {
        phone_e164: data.phone_e164,
        phone_display: data.phone_display,
        untilMs,
      };
      lsSetJson(revealKey(adId), stored);
      applyRevealedUI(adId, stored);
    } catch (e) {
      alert(e && e.message ? e.message : 'Не удалось раскрыть телефон.');
    } finally {
      btn.disabled = false;
    }
  };

  if (isSafetySeen()) {
    await doReveal();
    return;
  }

  const modalEl = ensureSafetyModal();
  const ackCb = modalEl.querySelector('#pmSafetyRevealAcknowledge');
  const seenCb = modalEl.querySelector('#pmSafetyRevealSeen');
  const confirmBtn = modalEl.querySelector('#pmSafetyRevealConfirm');

  const bsModal = bootstrap.Modal.getOrCreateInstance(modalEl);
  const onConfirm = async () => {
    if (ackCb && !ackCb.checked) {
      alert('Подтвердите, что вы понимаете условия.');
      return;
    }
    confirmBtn.removeEventListener('click', onConfirm);
    bsModal.hide();
    if (seenCb && seenCb.checked) setSafetySeen();
    await doReveal();
  };

  confirmBtn.addEventListener('click', onConfirm);
  bsModal.show();
}

function bindClicks() {
  document.addEventListener('click', (e) => {
    const btn = e.target && e.target.closest ? e.target.closest('.js-pm-reveal-phone') : null;
    if (!btn) return;
    e.preventDefault();
    handleRevealClick(btn);
  });

  document.addEventListener('click', (e) => {
    const el = e.target && e.target.closest ? e.target.closest('.js-pm-safety-contact') : null;
    if (!el) return;
    if (isSafetySeen()) return;
    e.preventDefault();

    const modalEl = ensureSafetyContactModal();
    const seenCb = modalEl.querySelector('#pmSafetyContactSeen');
    const confirmBtn = modalEl.querySelector('#pmSafetyContactConfirm');
    const bsModal = bootstrap.Modal.getOrCreateInstance(modalEl);

    const onConfirm = () => {
      confirmBtn.removeEventListener('click', onConfirm);
      bsModal.hide();
      if (seenCb && seenCb.checked) setSafetySeen();

      // resume action
      if (el.tagName && el.tagName.toLowerCase() === 'a') {
        const href = el.getAttribute('href') || '#';
        if (href && href !== '#') window.location.href = href;
      } else {
        // button: re-trigger click after modal closes
        setTimeout(() => {
          el.click();
        }, 0);
      }
    };

    confirmBtn.addEventListener('click', onConfirm);
    bsModal.show();
  });
}

function preventCopyOnPhones() {
  document.addEventListener('copy', (e) => {
    const t = e.target;
    if (t && t.closest && t.closest('.pm-no-copy')) {
      e.preventDefault();
    }
  });
  document.addEventListener('contextmenu', (e) => {
    const t = e.target;
    if (t && t.closest && t.closest('.pm-no-copy')) {
      e.preventDefault();
    }
  });
}

initFromLocalStorage();
bindClicks();
startTimerLoop();
preventCopyOnPhones();

