(() => {
  document.body.addEventListener('htmx:afterSwap', (evt) => {
    const target = evt?.detail?.target;
    if (!target || target.id !== 'bookingModalBody') return;
    const el = document.getElementById('bookingModal');
    if (!el || !window.bootstrap) return;
    window.bootstrap.Modal.getOrCreateInstance(el).show();
  });
})();

