/**
 * Логирование клика «Позвонить» (tel:) для аналитики ERP. Не блокирует переход в набор номера.
 */
function csrfToken() {
  return document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
}

export function initClassifiedsCallTrack(root = document) {
  root.querySelectorAll('a.js-pm-track-ad-call[href^="tel:"]').forEach((a) => {
    a.addEventListener('click', () => {
      const id = a.getAttribute('data-ad-id');
      if (!id) return;
      const url = `/ads/${encodeURIComponent(id)}/call-click/`;
      try {
        fetch(url, {
          method: 'POST',
          credentials: 'same-origin',
          keepalive: true,
          headers: {
            'X-CSRFToken': csrfToken(),
            'X-Requested-With': 'XMLHttpRequest',
          },
        }).catch(() => {});
      } catch {}
    });
  });
}
