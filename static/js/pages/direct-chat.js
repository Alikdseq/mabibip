import { wsBaseUrl } from '../app/ws-base.js';

function escapeHtml(s) {
  const d = document.createElement('div');
  d.textContent = s ?? '';
  return d.innerHTML;
}

function getCookie(name) {
  const m = document.cookie.match('(^|;) ?' + name + '=([^;]*)(;|$)');
  return m ? decodeURIComponent(m[2]) : '';
}

function clearPlaceholder(log) {
  const ph = log.querySelector('p.text-muted.mb-0');
  if (ph && (ph.textContent || '').includes('Пока нет сообщений')) ph.remove();
}

function appendBubble({ log, id, text, timeLabel, mine, mineLabel, otherLabel }) {
  clearPlaceholder(log);
  const row = document.createElement('div');
  row.className = 'mb-2' + (mine ? ' text-end' : '');
  if (id) row.setAttribute('data-msg-id', id.toString());
  row.innerHTML =
    '<span class="badge ' +
    (mine ? 'text-bg-primary' : 'text-bg-secondary') +
    '">' +
    (mine ? escapeHtml(mineLabel) : escapeHtml(otherLabel)) +
    '</span> ' +
    '<span class="text-muted">' +
    escapeHtml(timeLabel) +
    '</span>' +
    '<div class="mt-1">' +
    escapeHtml(text).replace(/\n/g, '<br>') +
    '</div>';
  log.appendChild(row);
  log.scrollTop = log.scrollHeight;
}

function showErr(alertEl, msg) {
  if (!alertEl) return;
  alertEl.textContent = msg;
  alertEl.classList.remove('d-none');
}

function hideErr(alertEl) {
  if (!alertEl) return;
  alertEl.classList.add('d-none');
  alertEl.textContent = '';
}

function safeJsonParse(s) {
  try {
    return JSON.parse(s);
  } catch {
    return null;
  }
}

(() => {
  function initFromRoot(root) {
    const wsPath = root.dataset.wsPath || '';
    const mineLabel = root.dataset.mineLabel || 'Вы';
    const otherLabel = root.dataset.otherLabel || 'СТО';

    const log = document.getElementById('direct-chat-log');
    const form = document.getElementById('direct-chat-send-form');
    const alertEl = document.getElementById('direct-chat-send-alert');
    const submitBtn = document.getElementById('direct-chat-submit');
    const textarea = document.getElementById('direct-chat-textarea');
    if (!log || !form || !submitBtn || !textarea) return;

    const userPk = parseInt(log.getAttribute('data-user-pk') || '0', 10) || 0;
    log.scrollTop = log.scrollHeight;
    const seenIds = new Set();
    log.querySelectorAll('[data-msg-id]').forEach((el) => {
      const raw = el.getAttribute('data-msg-id') || '';
      if (raw) seenIds.add(raw);
    });

    // WS: входящие; исходящие сразу рисуем из ответа HTTP (без ожидания сокета).
    if (wsPath) {
      const wsUrl = wsBaseUrl() + wsPath;
      let sock = null;
      let reconnectTimer = null;
      let wantReconnect = true;

      function attachHandlers() {
        if (!sock) return;
        sock.onmessage = (ev) => {
          const d = safeJsonParse(ev.data);
          if (d?.type !== 'message' || !d.text) return;
          const id = (d.id ?? '').toString();
          if (id && seenIds.has(id)) return;
          if (id) seenIds.add(id);
          const mine = parseInt(d.sender_id, 10) === userPk;
          appendBubble({ log, id: d.id, text: d.text, timeLabel: 'сейчас', mine, mineLabel, otherLabel });
        };
        sock.onerror = () => {};
        sock.onclose = () => {
          sock = null;
          if (!wantReconnect) return;
          if (reconnectTimer) return;
          reconnectTimer = window.setTimeout(() => {
            reconnectTimer = null;
            connectWs();
          }, 1800);
        };
      }

      function connectWs() {
        try {
          sock = new WebSocket(wsUrl);
          attachHandlers();
        } catch {
          sock = null;
          if (wantReconnect && !reconnectTimer) {
            reconnectTimer = window.setTimeout(() => {
              reconnectTimer = null;
              connectWs();
            }, 1800);
          }
        }
      }

      connectWs();
      window.addEventListener('beforeunload', () => {
        wantReconnect = false;
        if (reconnectTimer) window.clearTimeout(reconnectTimer);
        try {
          sock?.close();
        } catch {}
      });
    }

    // HTTP send
    form.addEventListener('submit', (ev) => {
      if (!window.fetch) return;
      ev.preventDefault();
      hideErr(alertEl);

      const fd = new FormData(form);
      const body = (fd.get('text') || '').toString().trim();
      if (!body) return;
      submitBtn.disabled = true;

      fetch(form.action, {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          Accept: 'application/json',
          'X-Requested-With': 'XMLHttpRequest',
          'X-CSRFToken': fd.get('csrfmiddlewaretoken') || getCookie('csrftoken') || '',
        },
        body: fd,
      })
        .then((r) =>
          r.json().then((data) => {
            if (!r.ok) throw new Error((data && data.error) || r.statusText);
            return data;
          })
        )
        .then((data) => {
          if (!data.ok || !data.message) throw new Error('Некорректный ответ сервера');
          const m = data.message;
          const id = (m.id ?? '').toString();
          if (id && seenIds.has(id)) {
            textarea.value = '';
            textarea.focus();
            return;
          }
          if (id) seenIds.add(id);
          appendBubble({
            log,
            id: m.id,
            text: m.text,
            timeLabel: m.created_at_display || 'сейчас',
            mine: true,
            mineLabel,
            otherLabel,
          });
          textarea.value = '';
          textarea.focus();
        })
        .catch((e) => showErr(alertEl, e?.message || 'Не удалось отправить. Попробуйте ещё раз.'))
        .finally(() => {
          submitBtn.disabled = false;
        });
    });
  }

  const root = document.getElementById('direct-chat-root');
  if (!root) return;
  if (root.dataset.initialized === '1') return;
  root.dataset.initialized = '1';
  initFromRoot(root);

  // Support dynamically injected station chat panel (and any other HTMX/fetch inserts).
  window.pmInitStationDirectChat = function pmInitStationDirectChat() {
    const r = document.getElementById('direct-chat-root');
    if (!r) return;
    if (r.dataset.initialized === '1') return;
    r.dataset.initialized = '1';
    initFromRoot(r);
  };
})();

