(() => {
  const collapse = document.getElementById('stationChatCollapse');
  if (!collapse) return;

  collapse.addEventListener('shown.bs.collapse', () => {
    const slot = document.getElementById('station-chat-slot');
    if (!slot || slot.dataset.loaded === '1') return;
    slot.dataset.loaded = '1';
    const url = slot.getAttribute('data-load-url');
    if (!url) return;

    fetch(url, { credentials: 'same-origin', headers: { Accept: 'text/html' } })
      .then((r) => r.text())
      .then((html) => {
        slot.innerHTML = html;
        try {
          if (typeof window.pmInitStationDirectChat === 'function') {
            window.pmInitStationDirectChat();
          }
        } catch {}
      })
      .catch(() => {
        slot.innerHTML = '<p class="small text-danger mb-0">Не удалось загрузить чат. Обновите страницу.</p>';
      });
  });
})();

