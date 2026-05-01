(() => {
  document.addEventListener('htmx:configRequest', (event) => {
    const m = document.querySelector('meta[name=csrf-token]');
    const token = m?.getAttribute('content') || '';
    if (token) {
      event.detail.headers['X-CSRFToken'] = token;
    }
  });
})();

