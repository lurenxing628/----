/* APS common_toast.js — Toast API（Win7 + Chrome 109） */
(function () {
  "use strict";

  var ns = window.__APS_COMMON__;
  if (!ns) {
    return;
  }
  if (!ns._inited) {
    ns._inited = {};
  }
  if (ns._inited.toast) {
    return;
  }
  ns._inited.toast = true;

  /* --- 6.7 Toast API（纯前端提示） --- */
  window.APS_Toast = function (msg, type, duration) {
    type = type || "info";
    duration = duration || 3000;
    var container = document.getElementById("aps-toast-container");
    if (!container) {
      return;
    }
    var el = document.createElement("div");
    el.className = "aps-toast" + (type !== "info" ? " toast-" + type : "");
    el.textContent = msg;
    container.appendChild(el);
    while (container.children.length > 4) {
      container.removeChild(container.firstElementChild);
    }
    void el.offsetWidth;
    el.classList.add("show");
    setTimeout(function () {
      el.classList.remove("show");
      el.addEventListener("transitionend", function () {
        if (el.parentNode) {
          el.parentNode.removeChild(el);
        }
      }, { once: true });
      setTimeout(function () {
        if (el.parentNode) {
          el.parentNode.removeChild(el);
        }
      }, 500);
    }, duration);
  };
})();

