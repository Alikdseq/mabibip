(function () {
  function wsBase() {
    var el = document.querySelector("[data-channels-ws-base]");
    if (!el) return "";
    return el.getAttribute("data-channels-ws-base") || "";
  }

  function connectHelpFeed() {
    var base = wsBase();
    if (!base || !window.WebSocket) return;
    var url = base.replace(/^http/, "ws") + "/ws/help/feed/";
    var sock = new WebSocket(url);
    sock.onmessage = function (ev) {
      try {
        var data = JSON.parse(ev.data);
        if (data.event === "help_new" || data.event === "help_resolved") {
          window.location.reload();
        }
      } catch (e) {}
    };
  }

  var modalEl = document.getElementById("helpCallModal");
  var modal = modalEl && window.bootstrap ? new bootstrap.Modal(modalEl) : null;
  var form = document.getElementById("help-resolve-form");
  var authorEl = document.getElementById("help-modal-author");
  var messageEl = document.getElementById("help-modal-message");

  document.querySelectorAll(".help-feed-card").forEach(function (btn) {
    btn.addEventListener("click", function () {
      if (!modal) return;
      authorEl.textContent = btn.getAttribute("data-help-author") || "";
      messageEl.textContent = btn.getAttribute("data-help-message") || "";
      form.action = btn.getAttribute("data-resolve-url") || "";
      modal.show();
    });
  });

  if (form) {
    form.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var fd = new FormData(form);
      fetch(form.action, {
        method: "POST",
        body: fd,
        headers: { "X-Requested-With": "XMLHttpRequest" },
        credentials: "same-origin",
      })
        .then(function (r) {
          return r.json();
        })
        .then(function (data) {
          if (data.ok && data.phone) {
            window.location.href = "tel:" + data.phone;
            if (modal) modal.hide();
            setTimeout(function () {
              window.location.reload();
            }, 500);
          }
        })
        .catch(function () {
          form.submit();
        });
    });
  }

  connectHelpFeed();
})();
