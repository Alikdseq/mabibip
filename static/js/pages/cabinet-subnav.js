import { wsBaseUrl } from '../app/ws-base.js';

function safeJsonParse(s) {
  try {
    return JSON.parse(s);
  } catch {
    return null;
  }
}

function updatePill(el, n) {
  if (!el) return;
  const v = parseInt(n, 10) || 0;
  if (v > 0) {
    el.textContent = String(v);
    el.classList.remove('d-none');
  } else {
    el.textContent = '0';
    el.classList.add('d-none');
  }
}

(() => {
  const el = document.getElementById('cabinet-chat-unread');
  if (!el) return;

  try {
    const sock = new WebSocket(wsBaseUrl() + '/ws/user-inbox/');
    sock.onmessage = (ev) => {
      const d = safeJsonParse(ev.data);
      if (d?.type === 'inbox' && typeof d.booking_unread === 'number') {
        updatePill(el, d.booking_unread);
      }
    };
    sock.onerror = () => {};
  } catch {}
})();

