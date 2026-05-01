export function wsBaseUrl() {
  const fromDom = typeof document !== 'undefined' ? String(document.body?.dataset?.wsBase || '').trim() : '';
  if (fromDom) {
    return fromDom.replace(/\/$/, '');
  }

  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = window.location.hostname;
  const port = window.location.port || '';

  // Local docker compose: HTTP on :8000, websockets on :8001.
  const wsPort = port === '8000' ? '8001' : port;
  return proto + '//' + host + (wsPort ? ':' + wsPort : '');
}

