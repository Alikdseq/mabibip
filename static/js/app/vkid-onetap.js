/**
 * VK ID One Tap (Low-code): @vkid/sdk UMD + обмен кода на бэкенде /accounts/api/vkid/session/
 */
(function () {
  "use strict";

  function getCfgScript() {
    return document.querySelector('script[src*="vkid-onetap.js"][data-vk-app-id]');
  }

  function csrfToken() {
    var m = document.querySelector('meta[name="csrf-token"]');
    return m ? m.getAttribute("content") || "" : "";
  }

  function postSession(url, accessToken, process) {
    return fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken(),
        "X-Requested-With": "XMLHttpRequest",
      },
      body: JSON.stringify({ access_token: accessToken, process: process }),
    }).then(function (r) {
      return r
        .json()
        .catch(function () {
          return { ok: false, message: "Некорректный ответ сервера." };
        })
        .then(function (j) {
          return { okHttp: r.ok, j: j };
        });
    });
  }

  function showErr(msg) {
    if (window.console && console.error) console.error(msg);
    if (window.alert) window.alert(msg);
  }

  function init() {
    var s = getCfgScript();
    if (!s) return;
    var host = document.getElementById("vkid-onetap-host");
    if (!host) return;

    var appId = parseInt(s.getAttribute("data-vk-app-id") || "0", 10);
    var redirectUrl = (s.getAttribute("data-vk-redirect") || "").trim();
    var sessionUrl = (s.getAttribute("data-vk-session-url") || "").trim();
    var process = (s.getAttribute("data-vk-process") || "login").trim().toLowerCase();
    if (process !== "signup") process = "login";

    if (!redirectUrl) {
      showErr(
        "VK ID: пустой redirect_uri. Укажите SITE_BASE_URL или VK_ID_REDIRECT_URI в окружении (полный https-URL, как в кабинете VK)."
      );
      return;
    }
    var localhostHttp = /^http:\/\/(127\.0\.0\.1|localhost)(:\d+)?\//i.test(redirectUrl);
    if (!/^https:\/\//i.test(redirectUrl) && !localhostHttp) {
      showErr(
        "VK ID: redirect_uri должен быть https (как в кабинете VK). Проверьте прокси (X-Forwarded-Proto) или задайте VK_ID_REDIRECT_URI."
      );
      return;
    }
    if (!appId || !sessionUrl) return;

    var VKID = window.VKIDSDK || window.VKID;
    if (!VKID || !VKID.Config || !VKID.OneTap) return;

    try {
      var initCfg = {
        app: appId,
        redirectUrl: redirectUrl,
        responseMode: VKID.ConfigResponseMode.Callback,
        scope: "email",
      };
      if (VKID.ConfigSource && VKID.ConfigSource.LOWCODE) {
        initCfg.source = VKID.ConfigSource.LOWCODE;
      }
      VKID.Config.init(initCfg);
    } catch (e) {
      showErr("Не удалось инициализировать VK ID.");
      return;
    }

    var oneTap = new VKID.OneTap();
    oneTap
      .render({
        container: host,
        showAlternativeLogin: true,
      })
      .on(VKID.WidgetEvents.ERROR, function (err) {
        var msg = (err && (err.text || err.message)) || "Ошибка виджета VK.";
        showErr(msg);
      })
      .on(VKID.OneTapInternalEvents.LOGIN_SUCCESS, function (payload) {
        var code = payload && payload.code;
        var deviceId = payload && payload.device_id;
        if (!code || !deviceId) {
          showErr("VK: нет кода авторизации.");
          return;
        }
        VKID.Auth.exchangeCode(code, deviceId)
          .then(function (data) {
            var token = data && (data.access_token || data.accessToken);
            if (!token) {
              showErr("VK: не получен access_token.");
              return;
            }
            return postSession(sessionUrl, token, process).then(function (x) {
              if (x.j && x.j.ok && x.okHttp && x.j.redirect) {
                window.location.href = x.j.redirect;
                return;
              }
              showErr((x.j && x.j.message) || "Не удалось войти через VK.");
            });
          })
          .catch(function () {
            showErr("Не удалось обменять код VK.");
          });
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
