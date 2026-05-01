import { wsBaseUrl } from './ws-base.js';

function getCookie(name) {
  const m = document.cookie.match('(^|;) ?' + name + '=([^;]*)(;|$)');
  return m ? decodeURIComponent(m[2]) : '';
}

function safeJsonParse(s) {
  try {
    return JSON.parse(s);
  } catch {
    return null;
  }
}

function ensureUi() {
  let root = document.getElementById('pm-calls-ui');
  if (root) return root;
  root = document.createElement('div');
  root.id = 'pm-calls-ui';
  root.innerHTML = `
    <div id="pm-call-overlay" class="position-fixed top-0 start-0 w-100 h-100 d-none" style="z-index: 1080; background: rgba(0,0,0,.35);">
      <div class="position-absolute top-50 start-50 translate-middle bg-white rounded shadow p-3" style="width: min(92vw, 420px);">
        <div class="d-flex align-items-center gap-2 mb-2">
          <img id="pm-call-avatar" src="" alt="" width="44" height="44" class="rounded-circle d-none" style="object-fit:cover;">
          <div class="min-w-0">
            <div id="pm-call-title" class="fw-semibold text-truncate">Звонок</div>
            <div id="pm-call-subtitle" class="small text-muted text-truncate"></div>
          </div>
        </div>

        <div id="pm-call-error" class="alert alert-danger py-2 px-3 small d-none" role="alert"></div>

        <div id="pm-call-actions-incoming" class="d-none">
          <button type="button" class="btn btn-success me-2" id="pm-call-accept">Принять</button>
          <button type="button" class="btn btn-outline-secondary" id="pm-call-decline">Отклонить</button>
        </div>

        <div id="pm-call-actions-outgoing" class="d-none">
          <button type="button" class="btn btn-outline-secondary" id="pm-call-cancel">Отменить</button>
        </div>

        <div id="pm-call-actions-active" class="d-none">
          <div class="d-flex align-items-center justify-content-between mb-2">
            <div class="small text-muted">Длительность: <span id="pm-call-timer">0:00</span></div>
            <button type="button" class="btn btn-outline-secondary btn-sm" id="pm-call-mute">Mute</button>
          </div>
          <button type="button" class="btn btn-danger w-100" id="pm-call-end">Завершить</button>
        </div>
      </div>
    </div>
  `;
  document.body.appendChild(root);
  return root;
}

function showOverlay({ title, subtitle, avatarUrl }) {
  ensureUi();
  const ov = document.getElementById('pm-call-overlay');
  const titleEl = document.getElementById('pm-call-title');
  const subEl = document.getElementById('pm-call-subtitle');
  const avatar = document.getElementById('pm-call-avatar');
  const err = document.getElementById('pm-call-error');
  if (err) err.classList.add('d-none');
  if (titleEl) titleEl.textContent = title || 'Звонок';
  if (subEl) subEl.textContent = subtitle || '';
  if (avatar) {
    if (avatarUrl) {
      avatar.src = avatarUrl;
      avatar.classList.remove('d-none');
    } else {
      avatar.classList.add('d-none');
      avatar.src = '';
    }
  }
  if (ov) ov.classList.remove('d-none');
}

function hideOverlay() {
  const ov = document.getElementById('pm-call-overlay');
  if (ov) ov.classList.add('d-none');
}

function setMode(mode) {
  const inc = document.getElementById('pm-call-actions-incoming');
  const out = document.getElementById('pm-call-actions-outgoing');
  const act = document.getElementById('pm-call-actions-active');
  if (inc) inc.classList.toggle('d-none', mode !== 'incoming');
  if (out) out.classList.toggle('d-none', mode !== 'outgoing');
  if (act) act.classList.toggle('d-none', mode !== 'active');
}

function showError(msg) {
  const err = document.getElementById('pm-call-error');
  if (!err) return;
  err.textContent = msg || 'Ошибка звонка';
  err.classList.remove('d-none');
}

function formatTimer(sec) {
  const s = Math.max(0, sec | 0);
  const mm = Math.floor(s / 60);
  const ss = String(s % 60).padStart(2, '0');
  return `${mm}:${ss}`;
}

async function postJson(url, body) {
  const r = await fetch(url, {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      'X-Requested-With': 'XMLHttpRequest',
      'X-CSRFToken': getCookie('csrftoken') || '',
    },
    body: JSON.stringify(body || {}),
  });
  const data = await r.json().catch(() => null);
  if (!r.ok) {
    throw new Error((data && data.error) || r.statusText || 'Ошибка');
  }
  return data;
}

let current = {
  callId: 0,
  roomName: '',
  token: '',
  livekitUrl: '',
  state: 'idle', // idle|outgoing|incoming|active
  room: null,
  localAudio: null,
  timerStart: 0,
  timerHandle: null,
  ringHandle: null,
};

function clearTimers() {
  if (current.timerHandle) window.clearInterval(current.timerHandle);
  current.timerHandle = null;
  if (current.ringHandle) window.clearTimeout(current.ringHandle);
  current.ringHandle = null;
}

async function ensureRoomLib() {
  // LiveKit JS SDK via ESM CDN (без сборки).
  return await import('https://unpkg.com/livekit-client/dist/livekit-client.esm.mjs');
}

async function connectLiveKit() {
  if (!current.livekitUrl || !current.token) throw new Error('LiveKit не настроен.');
  const lib = await ensureRoomLib();
  const Room = lib.Room;
  const RoomEvent = lib.RoomEvent;
  const createLocalAudioTrack = lib.createLocalAudioTrack;

  const room = new Room();
  current.room = room;

  room.on(RoomEvent.TrackSubscribed, (track) => {
    try {
      if (track?.kind !== 'audio') return;
      const el = track.attach();
      el.autoplay = true;
      el.playsInline = true;
      el.classList.add('d-none');
      document.body.appendChild(el);
    } catch {}
  });

  await room.connect(current.livekitUrl, current.token);
  const t = await createLocalAudioTrack();
  current.localAudio = t;
  await room.localParticipant.publishTrack(t);
}

async function disconnectLiveKit() {
  try {
    current.localAudio?.stop?.();
  } catch {}
  current.localAudio = null;
  try {
    current.room?.disconnect?.();
  } catch {}
  current.room = null;
}

function startActiveTimer() {
  current.timerStart = Date.now();
  const el = document.getElementById('pm-call-timer');
  if (el) el.textContent = '0:00';
  current.timerHandle = window.setInterval(() => {
    const sec = Math.floor((Date.now() - current.timerStart) / 1000);
    if (el) el.textContent = formatTimer(sec);
  }, 500);
}

async function endCall() {
  const id = current.callId;
  clearTimers();
  await disconnectLiveKit();
  current = { ...current, callId: 0, roomName: '', token: '', livekitUrl: '', state: 'idle' };
  hideOverlay();
  if (id) {
    try {
      await postJson('/api/calls/action/', { call_id: id, action: 'end' });
    } catch {}
  }
}

function bindUiHandlers() {
  ensureUi();
  const accept = document.getElementById('pm-call-accept');
  const decline = document.getElementById('pm-call-decline');
  const cancel = document.getElementById('pm-call-cancel');
  const end = document.getElementById('pm-call-end');
  const mute = document.getElementById('pm-call-mute');

  if (accept) {
    accept.onclick = async () => {
      try {
        await postJson('/api/calls/action/', { call_id: current.callId, action: 'accept' });
        // receiver: сразу подключаемся (токен уже в событии incoming)
        await connectLiveKit();
        setMode('active');
        current.state = 'active';
        startActiveTimer();
      } catch (e) {
        showError(e?.message || 'Не удалось принять звонок');
      }
    };
  }
  if (decline) {
    decline.onclick = async () => {
      try {
        await postJson('/api/calls/action/', { call_id: current.callId, action: 'decline' });
      } catch {}
      await endCall();
    };
  }
  if (cancel) cancel.onclick = () => endCall();
  if (end) end.onclick = () => endCall();
  if (mute) {
    mute.onclick = () => {
      try {
        if (!current.localAudio) return;
        const enabled = typeof current.localAudio.isEnabled === 'boolean' ? current.localAudio.isEnabled : true;
        const next = !enabled;
        current.localAudio.setEnabled(next);
        mute.textContent = next ? 'Mute' : 'Unmute';
      } catch {}
    };
  }
}

async function startOutgoingCall({ receiverUserId, contextKind, contextId, adId }) {
  bindUiHandlers();
  if (!receiverUserId) return;
  showOverlay({ title: 'Звоним…', subtitle: '', avatarUrl: '' });
  setMode('outgoing');

  try {
    const data = await postJson('/api/calls/initiate/', {
      receiver_user_id: receiverUserId,
      context_kind: contextKind || 'none',
      context_id: contextId || null,
      ad_id: adId || null,
    });
    if (!data?.ok) throw new Error('Не удалось инициировать звонок');
    current.callId = data.call_id || 0;
    current.roomName = data.room_name || '';
    current.token = data.token || '';
    current.livekitUrl = data.livekit_url || '';
    current.state = 'outgoing';

    // Таймаут звонка (если не приняли)
    const t = parseInt(data.ring_timeout_sec || '30', 10) || 30;
    current.ringHandle = window.setTimeout(() => {
      showError('Абонент не отвечает.');
    }, t * 1000);
  } catch (e) {
    showError(e?.message || 'Не удалось начать звонок');
    setMode('outgoing');
  }
}

function handleWsEvent(d) {
  if (!d || !d.type) return;

  if (d.type === 'call.incoming') {
    // Если уже есть активный звонок — игнорируем (сервер и так блокирует новые).
    if (current.state !== 'idle') return;
    bindUiHandlers();
    current.callId = parseInt(d.call_id || '0', 10) || 0;
    current.roomName = d.room_name || '';
    current.token = d.token || '';
    current.livekitUrl = d.livekit_url || '';
    current.state = 'incoming';
    showOverlay({
      title: 'Входящий звонок',
      subtitle: (d?.caller?.name || '').toString(),
      avatarUrl: (d?.caller?.avatar || '').toString(),
    });
    setMode('incoming');
    return;
  }

  if (d.type === 'call.accepted') {
    if (current.state !== 'outgoing') return;
    // Caller: подключаемся к комнате
    (async () => {
      try {
        await connectLiveKit();
        clearTimers();
        setMode('active');
        current.state = 'active';
        startActiveTimer();
      } catch (e) {
        showError(e?.message || 'Не удалось подключиться к звонку');
      }
    })();
    return;
  }

  if (d.type === 'call.declined' || d.type === 'call.ended' || d.type === 'call.timeout') {
    endCall();
    return;
  }
}

function attachCallButtons() {
  document.querySelectorAll('.js-pm-call').forEach((btn) => {
    if (btn.dataset.pmBound === '1') return;
    btn.dataset.pmBound = '1';
    btn.addEventListener('click', () => {
      const rid = parseInt(btn.dataset.receiverUserId || '0', 10) || 0;
      const ck = (btn.dataset.contextKind || '').toString();
      const cid = parseInt(btn.dataset.contextId || '0', 10) || 0;
      const adId = parseInt(btn.dataset.adId || '0', 10) || 0;
      startOutgoingCall({ receiverUserId: rid, contextKind: ck, contextId: cid, adId });
    });
  });
}

function initCallsWs() {
  const base = wsBaseUrl();
  let sock = null;
  let reconnectTimer = null;
  let wantReconnect = true;

  function connect() {
    try {
      sock = new WebSocket(base + '/ws/calls/');
      sock.onmessage = (ev) => handleWsEvent(safeJsonParse(ev.data));
      sock.onclose = () => {
        sock = null;
        if (!wantReconnect) return;
        if (reconnectTimer) return;
        reconnectTimer = window.setTimeout(() => {
          reconnectTimer = null;
          connect();
        }, 1800);
      };
      sock.onerror = () => {};
    } catch {}
  }

  connect();
  window.addEventListener('beforeunload', () => {
    wantReconnect = false;
    try {
      sock?.close();
    } catch {}
  });
}

(() => {
  // Включаем только когда сервер разрешил фичу (темплейт выставляет data-calls-enabled).
  const enabled = (document.body?.dataset?.callsEnabled || '0') === '1';
  if (!enabled) return;
  initCallsWs();
  attachCallButtons();
  // HTMX/динамические вставки: можно вызывать повторно.
  window.pmInitCallButtons = attachCallButtons;
})();

