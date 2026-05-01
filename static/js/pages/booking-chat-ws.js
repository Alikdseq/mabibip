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

function appendBubble({ log, text, timeLabel, mine, mineLabel, otherLabel, msgId }) {
  clearPlaceholder(log);
  const row = document.createElement('div');
  row.className = 'mb-2' + (mine ? ' text-end' : '');
  if (msgId != null && String(msgId)) row.setAttribute('data-msg-id', String(msgId));
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

function markRead(roomId) {
  try {
    window
      .fetch('/api/chats/' + String(roomId) + '/read/', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'X-Requested-With': 'XMLHttpRequest',
          'X-CSRFToken': getCookie('csrftoken') || '',
        },
      })
      .catch(() => {});
  } catch {}
}

(() => {
  const root = document.getElementById('booking-chat-root');
  if (!root) return;

  const wsPath = root.dataset.wsPath || '';
  if (!wsPath) return;

  const mineLabel = root.dataset.mineLabel || 'Вы';
  const otherLabel = root.dataset.otherLabel || 'СТО';

  const log = document.getElementById('booking-chat-log');
  const form = document.getElementById('booking-chat-send-form');
  const alertEl = document.getElementById('booking-chat-send-alert');
  const submitBtn = document.getElementById('booking-chat-submit');
  const textarea = document.getElementById('booking-chat-textarea');
  const statusEl = document.getElementById('booking-chat-ws-status');
  if (!log || !form || !submitBtn || !textarea) return;

  const userPk = parseInt(log.getAttribute('data-user-pk') || '0', 10) || 0;
  const roomId = parseInt(log.getAttribute('data-room-id') || '0', 10) || 0;
  const seenMsgIds = new Set();
  log.querySelectorAll('[data-msg-id]').forEach((el) => {
    const id = el.getAttribute('data-msg-id');
    if (id) seenMsgIds.add(id);
  });

  log.scrollTop = log.scrollHeight;
  if (roomId) markRead(roomId);

  const wsUrl = wsBaseUrl() + wsPath;
  let sock = null;
  let reconnectTimer = null;
  let wantReconnect = true;
  let pingTimer = null;
  /** Не дублировать своё сообщение: оптимистично показываем сразу, эхо с сервера пропускаем. */
  let pendingOwnEcho = null;
  let messagePollTimer = null;

  function clearMessagePoll() {
    if (messagePollTimer) {
      window.clearInterval(messagePollTimer);
      messagePollTimer = null;
    }
  }

  function maxSeenMessageId() {
    let max = 0;
    seenMsgIds.forEach((id) => {
      const n = parseInt(String(id), 10) || 0;
      if (n > max) max = n;
    });
    return max;
  }

  async function pollNewMessagesHttp() {
    if (!roomId) return;
    try {
      const after = maxSeenMessageId();
      const r = await fetch(`/api/chats/${roomId}/messages/?after_id=${after}`, {
        credentials: 'same-origin',
        headers: { Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
      });
      if (!r.ok) return;
      const data = await r.json();
      const list = data.messages || [];
      for (const m of list) {
        const mid = m.id != null ? String(m.id) : '';
        if (mid && seenMsgIds.has(mid)) continue;
        if (mid) seenMsgIds.add(mid);
        const mine = parseInt(m.sender_id, 10) === userPk;
        const textBody = (m.text || '').trim() || (m.attachment_url ? 'Вложение' : '');
        if (!textBody) continue;
        if (mine && pendingOwnEcho && pendingOwnEcho.text === textBody) {
          pendingOwnEcho = null;
          continue;
        }
        appendBubble({
          log,
          msgId: m.id,
          text: textBody,
          timeLabel: 'сейчас',
          mine,
          mineLabel,
          otherLabel,
        });
        if (!mine && roomId) markRead(roomId);
      }
    } catch {}
  }

  function startMessagePoll() {
    if (!roomId || messagePollTimer) return;
    setConnStatus('fallback');
    pollNewMessagesHttp();
    messagePollTimer = window.setInterval(pollNewMessagesHttp, 5000);
  }

  function setConnStatus(kind) {
    if (!statusEl) return;
    if (kind === 'live') {
      statusEl.textContent = 'Чат онлайн — сообщения доставляются мгновенно.';
      statusEl.className = 'small text-success mb-2';
    } else if (kind === 'reconnecting') {
      statusEl.textContent = 'Нет связи, переподключаемся…';
      statusEl.className = 'small text-warning mb-2';
    } else if (kind === 'fallback') {
      statusEl.textContent =
        'Онлайн-режим недоступен (часто из‑за прокси). Сообщения обновляются автоматически; отправка через сервер.';
      statusEl.className = 'small text-warning mb-2';
    } else {
      statusEl.textContent = 'Подключение чата…';
      statusEl.className = 'small text-muted mb-2';
    }
  }

  function clearPingTimer() {
    if (pingTimer) {
      window.clearInterval(pingTimer);
      pingTimer = null;
    }
  }

  function startPingLoop() {
    clearPingTimer();
    pingTimer = window.setInterval(() => {
      try {
        if (sock && sock.readyState === 1) sock.send(JSON.stringify({ type: 'ping', t: Date.now() }));
      } catch {}
    }, 25000);
  }

  function attachSocketHandlers() {
    if (!sock) return;
    sock.onopen = () => {
      clearMessagePoll();
      setConnStatus('live');
      startPingLoop();
    };
    sock.onmessage = (ev) => {
      try {
        const d = JSON.parse(ev.data);
        if (d.type === 'pong') return;
        if (d.type !== 'message') return;
        if (!d.text) return;
        const mid = d.id != null ? String(d.id) : '';
        if (mid && seenMsgIds.has(mid)) return;
        if (mid) seenMsgIds.add(mid);
        const mine = parseInt(d.sender_id, 10) === userPk;
        if (mine && pendingOwnEcho && pendingOwnEcho.text === d.text) {
          pendingOwnEcho = null;
          return;
        }
        appendBubble({
          log,
          msgId: d.id,
          text: d.text,
          timeLabel: 'сейчас',
          mine,
          mineLabel,
          otherLabel,
        });
        if (!mine && roomId) markRead(roomId);
      } catch {}
    };
    sock.onerror = () => {};
    sock.onclose = () => {
      clearPingTimer();
      sock = null;
      if (!wantReconnect) return;
      setConnStatus('reconnecting');
      startMessagePoll();
      if (reconnectTimer) return;
      reconnectTimer = window.setTimeout(() => {
        reconnectTimer = null;
        connectWs();
      }, 1800);
    };
  }

  function connectWs() {
    setConnStatus(wantReconnect && sock === null && reconnectTimer ? 'reconnecting' : 'connecting');
    try {
      sock = new WebSocket(wsUrl);
      attachSocketHandlers();
    } catch {
      sock = null;
      if (wantReconnect && !reconnectTimer) {
        setConnStatus('reconnecting');
        reconnectTimer = window.setTimeout(() => {
          reconnectTimer = null;
          connectWs();
        }, 1800);
      }
    }
  }

  connectWs();

  window.setTimeout(() => {
    if (!sock || sock.readyState !== 1) startMessagePoll();
  }, 5000);

  window.addEventListener('beforeunload', () => {
    wantReconnect = false;
    clearPingTimer();
    clearMessagePoll();
    if (reconnectTimer) window.clearTimeout(reconnectTimer);
    try {
      sock?.close();
    } catch {}
  });

  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') pollNewMessagesHttp();
  });

  form.addEventListener('submit', async (ev) => {
    ev.preventDefault();
    hideErr(alertEl);
    const body = (textarea.value || '').toString().trim();
    if (!body) return;
    submitBtn.disabled = true;
    try {
      if (!sock || sock.readyState !== 1) {
        const r = await fetch(`/api/chats/${roomId}/messages/send/`, {
          method: 'POST',
          credentials: 'same-origin',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken') || '',
            'X-Requested-With': 'XMLHttpRequest',
            Accept: 'application/json',
          },
          body: JSON.stringify({ text: body }),
        });
        let data = {};
        try {
          data = await r.json();
        } catch {}
        if (!r.ok) {
          throw new Error(data.error || data.detail || 'Не удалось отправить');
        }
        const m = data.message;
        if (m?.id != null) seenMsgIds.add(String(m.id));
        appendBubble({
          log,
          msgId: m.id,
          text: body,
          timeLabel: 'сейчас',
          mine: true,
          mineLabel,
          otherLabel,
        });
        textarea.value = '';
        textarea.focus();
        return;
      }
      pendingOwnEcho = { text: body };
      appendBubble({ log, text: body, timeLabel: 'сейчас', mine: true, mineLabel, otherLabel });
      sock.send(JSON.stringify({ text: body }));
      textarea.value = '';
      textarea.focus();
      window.setTimeout(() => {
        if (pendingOwnEcho && pendingOwnEcho.text === body) pendingOwnEcho = null;
      }, 8000);
    } catch (e) {
      pendingOwnEcho = null;
      showErr(alertEl, e?.message || 'Не удалось отправить. Попробуйте ещё раз.');
    } finally {
      submitBtn.disabled = false;
    }
  });
})();

