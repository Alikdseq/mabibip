/**
 * Кнопка «показать / скрыть пароль» для полей ввода (Bootstrap input-group + bi icons).
 */
(function () {
  var WRAP_CLASS = "password-toggle-group";
  var BTN_CLASS = "password-toggle-btn";
  var BOUND = "data-password-toggle-bound";

  function createToggleButton(input) {
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "btn btn-outline-secondary " + BTN_CLASS;
    btn.setAttribute("aria-label", "Показать пароль");
    btn.setAttribute("aria-pressed", "false");
    btn.setAttribute("tabindex", "0");
    btn.innerHTML =
      '<i class="bi bi-eye password-toggle-icon" aria-hidden="true"></i>';

    btn.addEventListener("click", function () {
      var visible = input.type === "text";
      input.type = visible ? "password" : "text";
      var show = input.type === "text";
      btn.setAttribute("aria-pressed", show ? "true" : "false");
      btn.setAttribute("aria-label", show ? "Скрыть пароль" : "Показать пароль");
      var icon = btn.querySelector(".password-toggle-icon");
      if (icon) {
        icon.classList.toggle("bi-eye", !show);
        icon.classList.toggle("bi-eye-slash", show);
      }
    });

    return btn;
  }

  function wrapPasswordInput(input) {
    if (!input || input.getAttribute(BOUND) === "1") return;
    if (input.closest("." + WRAP_CLASS)) return;
    if (input.type !== "password") return;

    input.setAttribute(BOUND, "1");

    var group = document.createElement("div");
    group.className = "input-group " + WRAP_CLASS;

    var parent = input.parentNode;
    parent.insertBefore(group, input);
    group.appendChild(input);
    group.appendChild(createToggleButton(input));
  }

  function initPasswordToggles(root) {
    (root || document).querySelectorAll('input[type="password"]').forEach(wrapPasswordInput);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      initPasswordToggles(document);
    });
  } else {
    initPasswordToggles(document);
  }

  document.body.addEventListener("htmx:afterSwap", function (ev) {
    if (ev.detail && ev.detail.target) {
      initPasswordToggles(ev.detail.target);
    }
  });
})();
