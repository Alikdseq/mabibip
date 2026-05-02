import { wsBaseUrl } from './ws-base.js';

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

function csrfToken() {
  return document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
}

function postForm(url) {
  const tok = csrfToken();
  if (!tok) return;
  const f = document.createElement('form');
  f.method = 'POST';
  f.action = url;
  const h = document.createElement('input');
  h.type = 'hidden';
  h.name = 'csrfmiddlewaretoken';
  h.value = tok;
  f.appendChild(h);
  document.body.appendChild(f);
  f.submit();
}

function pmInitHeaderInbox() {
  const el = document.getElementById('header-chat-unread');
  if (!el) return;

  let bookingUnread = parseInt(el.textContent || '0', 10) || 0;
  let stoDirectUnread = 0;
  let stoBookingPending = 0;
  let lastPendingSeen = null;

  const render = () => updatePill(el, bookingUnread + stoDirectUnread);
  render();

  const base = wsBaseUrl();
  let pollTimer = null;
  let inboxWsOk = false;
  let stoInboxWsOk = false;

  function clearInboxPoll() {
    if (pollTimer) {
      window.clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  async function pollInboxFromHttp() {
    try {
      const r = await fetch('/api/inbox/summary/', {
        credentials: 'same-origin',
        headers: { Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
      });
      if (!r.ok) return;
      const d = await r.json();
      if (typeof d.user_inbox_unread === 'number') bookingUnread = d.user_inbox_unread;
      if (typeof d.sto_direct_unread === 'number') stoDirectUnread = d.sto_direct_unread;
      if (typeof d.sto_booking_pending === 'number') {
        stoBookingPending = d.sto_booking_pending;
        const badge = document.getElementById('mobile-business-badge');
        updatePill(badge, stoBookingPending);
      }
      render();
    } catch {}
  }

  function scheduleInboxPollIfNeeded() {
    const isApprovedSto = (document.body?.dataset?.stoApproved || '0') === '1';
    const needPoll = !inboxWsOk || (isApprovedSto && !stoInboxWsOk);
    if (!needPoll) {
      clearInboxPoll();
      return;
    }
    if (pollTimer) return;
    pollInboxFromHttp();
    pollTimer = window.setInterval(pollInboxFromHttp, 12000);
  }

  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') pollInboxFromHttp();
  });

  const seenBuffer = new Set();
  let seenFlushTimer = null;

  function markSeenLater(id) {
    const n = parseInt(id, 10) || 0;
    if (!n) return;
    seenBuffer.add(n);
    if (seenFlushTimer) return;
    seenFlushTimer = window.setTimeout(() => {
      seenFlushTimer = null;
      const ids = Array.from(seenBuffer);
      seenBuffer.clear();
      if (!ids.length) return;
      try {
        fetch('/api/toast-events/seen/', {
          method: 'POST',
          credentials: 'same-origin',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken(),
          },
          body: JSON.stringify({ ids }),
        }).catch(() => {});
      } catch {}
    }, 800);
  }

  function markToastsSeenNow(ids) {
    const raw = []
      .concat(ids || [])
      .map((x) => parseInt(x, 10) || 0)
      .filter((x) => x > 0);
    if (!raw.length) return;
    try {
      fetch('/api/toast-events/seen/', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken(),
        },
        body: JSON.stringify({ ids: raw }),
      }).catch(() => {});
    } catch {}
  }

  const ownerNewBookingQueue = [];
  const ownerNewBookingSeenIds = new Set();
  let ownerNewBookingModalBusy = false;

  function enqueueOwnerNewBookingModal(ev) {
    if (!ev) return;
    const eventId = parseInt(ev.event_id || ev.eventId || 0, 10) || 0;
    if (!eventId || ownerNewBookingSeenIds.has(eventId)) return;
    const kind = (ev.kind || '').toString();
    const p = ev.payload || {};
    if (!ownerNewBookingQueue.some((x) => x.event_id === eventId)) {
      ownerNewBookingQueue.push({ event_id: eventId, kind, payload: p });
    }
    drainOwnerNewBookingModal();
  }

  function drainOwnerNewBookingModal() {
    if (ownerNewBookingModalBusy) return;
    if (!ownerNewBookingQueue.length) return;
    const modalEl = document.getElementById('pm-owner-new-booking-modal');
    const textEl = document.getElementById('pm-owner-new-booking-modal-text');
    const btnConfirm = document.getElementById('pm-owner-new-booking-modal-confirm');
    const btnOpen = document.getElementById('pm-owner-new-booking-modal-open');
    if (!modalEl || !window.bootstrap?.Modal || !textEl || !btnConfirm || !btnOpen) {
      return;
    }
    const next = ownerNewBookingQueue.shift();
    if (!next) return;
    const p = next.payload || {};
    const eventId = next.event_id;
    const s = (p.slot_summary || '').toString().trim();
    const st = (p.station_name || '').toString().trim();
    const phone = (p.client_phone || '').toString().trim();
    const lines = [
      st ? `СТО: ${st}` : '',
      s ? `Время: ${s}` : '',
      phone ? `Тел: ${phone}` : '',
    ].filter(Boolean);
    textEl.textContent = lines.length ? lines.join('\n') : `Заявка #${p.booking_id || ''}`;

    const confirmUrl = (p.confirm_url || '').toString();
    const openUrl = (p.open_url || '').toString();
    btnConfirm.onclick = () => {
      ownerNewBookingSeenIds.add(eventId);
      markToastsSeenNow([eventId]);
      try {
        window.bootstrap.Modal.getInstance(modalEl)?.hide();
      } catch {}
      if (confirmUrl) postForm(confirmUrl);
    };
    btnOpen.onclick = (e) => {
      e.preventDefault();
      ownerNewBookingSeenIds.add(eventId);
      markToastsSeenNow([eventId]);
      try {
        window.bootstrap.Modal.getInstance(modalEl)?.hide();
      } catch {}
      if (openUrl) window.location.assign(openUrl);
    };

    ownerNewBookingModalBusy = true;
    const modal = window.bootstrap.Modal.getOrCreateInstance(modalEl, { backdrop: true, keyboard: true });
    const onHidden = () => {
      modalEl.removeEventListener('hidden.bs.modal', onHidden);
      ownerNewBookingModalBusy = false;
      window.setTimeout(() => drainOwnerNewBookingModal(), 0);
    };
    modalEl.addEventListener('hidden.bs.modal', onHidden);
    modal.show();
  }

  function handleToastEvent(ev) {
    if (!ev) return;
    const eventId = ev.event_id || ev.eventId || 0;
    const kind = (ev.kind || '').toString();
    const p = ev.payload || {};

    // Owner: new booking — модалка; закрытие без действия не помечает событие (повтор при следующем входе).
    if (kind === 'owner_new_booking') {
      enqueueOwnerNewBookingModal({ event_id: eventId, kind, payload: p });
      return;
    }

    // Client: booking confirmed / canceled (so user doesn't miss)
    if (kind === 'client_booking_confirmed' || kind === 'client_booking_canceled') {
      const toastEl = document.getElementById('pm-client-booking-status-toast');
      const titleEl = document.getElementById('pm-client-booking-status-title');
      const textEl = document.getElementById('pm-client-booking-status-text');
      if (toastEl && window.bootstrap?.Toast) {
        const st = (p.station_name || '').toString().trim();
        const slot = (p.slot_summary || '').toString().trim();
        if (kind === 'client_booking_confirmed') {
          toastEl.classList.remove('text-bg-danger');
          toastEl.classList.add('text-bg-success');
          if (titleEl) titleEl.textContent = 'Запись подтверждена';
          if (textEl) textEl.textContent = `${st || 'СТО'} подтвердило запись${slot ? ` на ${slot}` : ''}.`;
        } else {
          toastEl.classList.remove('text-bg-success');
          toastEl.classList.add('text-bg-danger');
          if (titleEl) titleEl.textContent = 'Заявка отклонена';
          const reason = (p.reason || '').toString().trim();
          if (textEl) textEl.textContent = reason ? `Причина: ${reason}` : 'К сожалению, заявку отклонили.';
        }
        try {
          window.bootstrap.Toast.getOrCreateInstance(toastEl, { delay: 14000 }).show();
        } catch {}
        markSeenLater(eventId);
        return;
      }
    }

    // Client: reschedule prompt (persistent)
    if (kind === 'client_reschedule_prompt') {
      showClientReschedulePrompt({
        booking_id: p.booking_id,
        station_name: p.station_name,
        slot_summary: p.slot_summary,
        owner_message: p.owner_message,
      });
      markSeenLater(eventId);
      return;
    }

    // Owner: reschedule accepted/declined (persistent)
    if (kind === 'owner_reschedule_accepted' || kind === 'owner_reschedule_declined') {
      showOwnerRescheduleNotice({
        kind: kind === 'owner_reschedule_accepted' ? 'reschedule_accepted' : 'reschedule_declined',
        booking_id: p.booking_id,
        client_phone: p.client_phone,
        slot_summary: p.slot_summary,
        chat_url: p.chat_url,
      });
      markSeenLater(eventId);
      return;
    }
  }

  function showClientReschedulePrompt(d) {
    if (!d?.booking_id) return;
    const toastEl = document.getElementById('pm-reschedule-client-toast');
    const textEl = document.getElementById('pm-rs-client-text');
    const acc = document.getElementById('pm-rs-accept-btn');
    const dec = document.getElementById('pm-rs-decline-btn');
    if (!toastEl || !textEl || !acc || !dec || !window.bootstrap?.Toast) return;
    const st = (d.station_name || '').toString().trim();
    const slot = (d.slot_summary || '').toString().trim();
    const om = (d.owner_message || '').toString().trim();
    let body = st
      ? `«${st}» не может принять вас в запрошенное время и предлагает другое окно.`
      : 'Сервис предлагает другое время.';
    if (slot) body += `\n\nНовое окно: ${slot}.`;
    if (om) body += `\n\nКомментарий: ${om}`;
    body += '\n\nПодтвердите новое время или откажитесь (останется прежняя заявка).';
    textEl.textContent = body;
    const bid = String(d.booking_id);
    acc.onclick = () => postForm(`/cabinet/bookings/${encodeURIComponent(bid)}/reschedule/accept/`);
    dec.onclick = () => postForm(`/cabinet/bookings/${encodeURIComponent(bid)}/reschedule/decline/`);
    try {
      window.bootstrap.Toast.getOrCreateInstance(toastEl, { delay: 14000 }).show();
    } catch {}
  }

  function showOwnerRescheduleNotice(d) {
    const toastEl = document.getElementById('pm-sto-reschedule-toast');
    const titleEl = document.getElementById('pm-sto-rs-title');
    const textEl = document.getElementById('pm-sto-rs-text');
    const callEl = document.getElementById('pm-sto-rs-call');
    const chatEl = document.getElementById('pm-sto-rs-chat');
    if (!toastEl || !window.bootstrap?.Toast) return;
    const kind = (d.kind || '').toString();
    const phone = (d.client_phone || '').toString().trim();
    if (kind === 'reschedule_accepted') {
      if (titleEl) titleEl.textContent = 'Клиент согласился';
      if (textEl) {
        const sm = (d.slot_summary || '').toString().trim();
        textEl.textContent = sm ? `Запись #${d.booking_id} подтверждена на ${sm}.` : `Запись #${d.booking_id} подтверждена.`;
      }
      if (callEl) callEl.classList.add('d-none');
      if (chatEl) chatEl.classList.add('d-none');
    } else if (kind === 'reschedule_declined') {
      if (titleEl) titleEl.textContent = 'Клиент отказался от переноса';
      if (textEl) textEl.textContent = `По заявке #${d.booking_id} клиент оставил прежнее время. Можно позвонить или написать в чат.`;
      if (callEl) {
        if (phone) {
          callEl.href = 'tel:' + phone.replace(/\s+/g, '');
          callEl.classList.remove('d-none');
        } else {
          callEl.classList.add('d-none');
        }
      }
      if (chatEl) {
        const cu = (d.chat_url || '').toString().trim();
        if (cu) {
          chatEl.href = cu;
          chatEl.classList.remove('d-none');
        } else {
          chatEl.classList.add('d-none');
        }
      }
    } else {
      return;
    }
    try {
      window.bootstrap.Toast.getOrCreateInstance(toastEl, { delay: 12000 }).show();
    } catch {}
  }

  // booking unread for everyone (auth required server-side)
  try {
    const sock1 = new WebSocket(base + '/ws/user-inbox/');
    sock1.onopen = () => {
      inboxWsOk = true;
      scheduleInboxPollIfNeeded();
    };
    sock1.onclose = () => {
      inboxWsOk = false;
      scheduleInboxPollIfNeeded();
    };
    sock1.onmessage = (ev) => {
      const d = safeJsonParse(ev.data);
      if (d?.type === 'inbox' && typeof d.booking_unread === 'number') {
        bookingUnread = d.booking_unread;
        render();
      }
      if (d?.type === 'toast_events' && Array.isArray(d.events)) {
        d.events.forEach((e) => handleToastEvent({ event_id: e.event_id, kind: e.kind, payload: e.payload }));
      }
      if (d?.type === 'toast_event') {
        handleToastEvent(d);
      }
      if (d?.type === 'review_prompt' && d.booking_id) {
        const toastEl = document.getElementById('pm-review-toast');
        const textEl = document.getElementById('pm-review-toast-text');
        const linkEl = document.getElementById('pm-review-toast-link');
        if (toastEl && linkEl && window.bootstrap?.Toast) {
          const station = (d.station_name || '').toString().trim();
          if (textEl) {
            textEl.textContent = station
              ? `Оставьте отзыв о визите в «${station}» — это помогает другим водителям.`
              : 'Оставьте отзыв — это помогает другим водителям.';
          }
          linkEl.href = `/cabinet/reviews/${encodeURIComponent(String(d.booking_id))}/`;
          try {
            const t = window.bootstrap.Toast.getOrCreateInstance(toastEl, { delay: 8000 });
            t.show();
          } catch {}
        }
      }
      if (d?.type === 'reschedule_prompt' && d.booking_id) {
        showClientReschedulePrompt(d);
      }
    };
    sock1.onerror = () => {};
  } catch {}

  window.setTimeout(() => {
    if (!inboxWsOk) scheduleInboxPollIfNeeded();
  }, 3000);

  // direct unread only for approved sto owners; server can reject, it's ok.
  try {
    const isApprovedSto = (document.body?.dataset?.stoApproved || '0') === '1';
    if (isApprovedSto) {
      const sock2 = new WebSocket(base + '/ws/sto-owner/inbox/');
      sock2.onopen = () => {
        stoInboxWsOk = true;
        scheduleInboxPollIfNeeded();
      };
      sock2.onclose = () => {
        stoInboxWsOk = false;
        scheduleInboxPollIfNeeded();
      };
      sock2.onmessage = (ev) => {
        const d = safeJsonParse(ev.data);
        if (d?.type === 'toast_events' && Array.isArray(d.events)) {
          d.events.forEach((e) => handleToastEvent({ event_id: e.event_id, kind: e.kind, payload: e.payload }));
        }
        if (d?.type === 'toast_event') {
          handleToastEvent(d);
          return;
        }
        if (d?.type === 'sto_notice') {
          const toastEl = document.getElementById('pm-sto-reschedule-toast');
          const titleEl = document.getElementById('pm-sto-rs-title');
          const textEl = document.getElementById('pm-sto-rs-text');
          const callEl = document.getElementById('pm-sto-rs-call');
          const chatEl = document.getElementById('pm-sto-rs-chat');
          if (!toastEl || !window.bootstrap?.Toast) return;
          const kind = (d.kind || '').toString();
          const phone = (d.client_phone || '').toString().trim();
          if (kind === 'reschedule_accepted') {
            if (titleEl) titleEl.textContent = 'Клиент согласился';
            if (textEl) {
              const sm = (d.slot_summary || '').toString().trim();
              textEl.textContent = sm
                ? `Запись #${d.booking_id} подтверждена на ${sm}.`
                : `Запись #${d.booking_id} подтверждена на предложенное время.`;
            }
            if (callEl) callEl.classList.add('d-none');
            if (chatEl) chatEl.classList.add('d-none');
          } else if (kind === 'reschedule_declined') {
            if (titleEl) titleEl.textContent = 'Клиент отказался от переноса';
            if (textEl) {
              textEl.textContent = `По заявке #${d.booking_id} клиент оставил прежнее время. Можно позвонить или написать в чат.`;
            }
            if (callEl) {
              if (phone) {
                callEl.href = 'tel:' + phone.replace(/\s+/g, '');
                callEl.classList.remove('d-none');
              } else {
                callEl.classList.add('d-none');
              }
            }
            if (chatEl) {
              const cu = (d.chat_url || '').toString().trim();
              if (cu) {
                chatEl.href = cu;
                chatEl.classList.remove('d-none');
              } else {
                chatEl.classList.add('d-none');
              }
            }
          } else {
            return;
          }
          try {
            window.bootstrap.Toast.getOrCreateInstance(toastEl, { delay: 12000 }).show();
          } catch {}
          return;
        }
        if (d?.type !== 'inbox') return;
        if (typeof d.direct_unread === 'number') {
          stoDirectUnread = d.direct_unread;
          render();
        }
        if (typeof d.booking_pending === 'number') {
          stoBookingPending = d.booking_pending;
          const badge = document.getElementById('mobile-business-badge');
          updatePill(badge, stoBookingPending);

          // Toast on new pending bookings
          const toastEl = document.getElementById('pm-booking-toast');
          if (toastEl && window.bootstrap?.Toast) {
            if (lastPendingSeen === null) {
              lastPendingSeen = stoBookingPending;
            } else if (stoBookingPending > lastPendingSeen) {
              try {
                const t = window.bootstrap.Toast.getOrCreateInstance(toastEl, { delay: 5000 });
                t.show();
              } catch {}
              lastPendingSeen = stoBookingPending;
            } else {
              lastPendingSeen = stoBookingPending;
            }
          }
        }
      };
      sock2.onerror = () => {};
      window.setTimeout(() => {
        if (!stoInboxWsOk) scheduleInboxPollIfNeeded();
      }, 3500);
    } else {
      stoInboxWsOk = true;
    }
  } catch {}
}

function pmScheduleHeaderInbox() {
  const run = () => {
    pmInitHeaderInbox();
  };
  if (typeof window.requestIdleCallback === 'function') {
    window.requestIdleCallback(run, { timeout: 3000 });
  } else {
    window.addEventListener(
      'load',
      () => {
        window.setTimeout(run, 0);
      },
      { once: true },
    );
  }
}

pmScheduleHeaderInbox();
