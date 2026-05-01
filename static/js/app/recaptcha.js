function getForm(formId) {
  if (!formId) return null;
  return document.getElementById(formId);
}

function setToken(form, token) {
  const el = form.querySelector('input[name="recaptcha_token"]');
  if (el) el.value = token || '';
}

function ensureV3({ siteKey, formId, action }) {
  const form = getForm(formId);
  if (!form || !siteKey || !window.grecaptcha) return;
  const actionFromForm =
    form.dataset && form.dataset.recaptchaAction ? form.dataset.recaptchaAction : '';

  form.addEventListener('submit', (e) => {
    e.preventDefault();
    window.grecaptcha.ready(() => {
      const act = action || actionFromForm || 'submit';
      window.grecaptcha.execute(siteKey, { action: act }).then((token) => {
        setToken(form, token);
        form.submit();
      });
    });
  });
}

function ensureV2({ formId }) {
  const form = getForm(formId);
  if (!form) return;
  form.addEventListener('submit', () => {
    const resp = window.grecaptcha && window.grecaptcha.getResponse ? window.grecaptcha.getResponse() : '';
    setToken(form, resp);
  });
}

(() => {
  // Template injects one or more config nodes.
  document.querySelectorAll('[data-recaptcha-config="1"]').forEach((node) => {
    const version = (node.dataset.version || 'v3').toLowerCase();
    const formId = node.dataset.formId || '';
    if (version === 'v2') {
      ensureV2({ formId });
      return;
    }
    ensureV3({
      siteKey: node.dataset.siteKey || '',
      formId,
      // If data-action is empty, fall back to form's data-recaptcha-action.
      action: node.dataset.action || '',
    });
  });
})();

