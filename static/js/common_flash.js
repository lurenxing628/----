/* APS common_flash.js — Flash 自动消失（Win7 + Chrome 109） */
(function () {
  "use strict";

  var ns = window.__APS_COMMON__;
  if (!ns) {
    return;
  }
  if (!ns._inited) {
    ns._inited = {};
  }
  if (ns._inited.flash) {
    return;
  }
  ns._inited.flash = true;

  var removeNodeWithFade = ns.removeNodeWithFade;
  if (typeof removeNodeWithFade !== "function") {
    return;
  }

  /* --- 1. Flash 消息：成功 4s 消失 + 关闭按钮 --- */
  document.querySelectorAll(".flash-card").forEach(function (el) {
    var cat = el.getAttribute("data-flash") || "";
    if (cat === "success") {
      removeNodeWithFade(el, 4000);
    }
    var btn = el.querySelector(".flash-close");
    if (btn) {
      btn.addEventListener("click", function () {
        removeNodeWithFade(el, 0);
      });
    }
  });
})();

