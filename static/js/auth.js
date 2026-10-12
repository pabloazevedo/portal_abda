// ══════════════════════════════════════════════════════════════
// Portal — auth.js (login / forgot / reset)
// ══════════════════════════════════════════════════════════════

(function () {
  "use strict";

  // Toggle show/hide password
  document.querySelectorAll("[data-auth-toggle-password]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var targetId = btn.getAttribute("data-auth-toggle-password");
      var input = targetId ? document.getElementById(targetId) : null;
      if (!input) return;

      var showing = input.type === "text";
      input.type = showing ? "password" : "text";
      btn.setAttribute("aria-pressed", showing ? "false" : "true");

      var showLabel = btn.getAttribute("data-label-show") || btn.getAttribute("aria-label");
      var hideLabel = btn.getAttribute("data-label-hide") || showLabel;
      var nextLabel = showing ? showLabel : hideLabel;
      if (nextLabel) {
        btn.setAttribute("aria-label", nextLabel);
        btn.setAttribute("title", nextLabel);
      }

      var icon = btn.querySelector("i");
      if (icon) {
        icon.classList.toggle("bi-eye-fill", showing);
        icon.classList.toggle("bi-eye-slash-fill", !showing);
      }
    });
  });

  // Disable submit + aria-busy to prevent double-post
  document.querySelectorAll("form[data-auth-form]").forEach(function (form) {
    form.addEventListener("submit", function () {
      var btn = form.querySelector('[type="submit"]');
      if (!btn || btn.disabled) return;

      btn.disabled = true;
      btn.setAttribute("aria-busy", "true");
      form.classList.add("auth-form--submitting");

      var label = btn.querySelector("[data-auth-submit-label]");
      var busyLabel = btn.getAttribute("data-busy-label");
      if (label && busyLabel) {
        label.textContent = busyLabel;
      }
    });
  });
})();
