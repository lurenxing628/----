/* APS common_theme.js — 主题切换（Win7 + Chrome 109） */
(function () {
  "use strict";

  var ns = window.__APS_COMMON__;
  if (!ns) {
    return;
  }
  if (!ns._inited) {
    ns._inited = {};
  }
  if (ns._inited.theme) {
    return;
  }
  ns._inited.theme = true;

  /* --- 1.5 主题切换（初始化已在 base head 内联脚本完成） --- */
  var themeToggleBtn = document.getElementById("apsThemeToggle");
  var themeLabel = document.getElementById("apsThemeLabel");
  if (themeToggleBtn) {
    var htmlEl = document.documentElement;
    var themeBusy = false;

    function normalizeTheme(raw) {
      var t = String(raw || "").trim().toLowerCase();
      return t === "dark" ? "dark" : "light";
    }

    function readThemeFromCookie() {
      try {
        var m = document.cookie.match(/(?:^|; )aps_theme=([^;]+)/);
        if (m && m[1]) {
          return decodeURIComponent(m[1]);
        }
      } catch (_e0) {}
      return "";
    }

    function readStoredTheme() {
      var t = "";
      try {
        t = localStorage.getItem("aps_theme") || "";
      } catch (_e1) {}
      if (!t) {
        t = readThemeFromCookie();
      }
      return normalizeTheme(t);
    }

    function syncThemeUI(theme) {
      var isDark = theme === "dark";
      if (themeLabel) {
        themeLabel.textContent = isDark ? "护眼开" : "护眼关";
      }
      themeToggleBtn.setAttribute("aria-pressed", isDark ? "true" : "false");
      themeToggleBtn.setAttribute("aria-checked", isDark ? "true" : "false");
      themeToggleBtn.setAttribute("data-theme-state", isDark ? "on" : "off");
    }

    function persistTheme(theme) {
      try {
        localStorage.setItem("aps_theme", theme);
      } catch (_e2) {}
      try {
        document.cookie = "aps_theme=" + encodeURIComponent(theme) + "; path=/; max-age=31536000; samesite=lax";
      } catch (_e3) {}
    }

    var switchingTimer = 0;
    var switchingRaf1 = 0;
    var switchingRaf2 = 0;

    function clearSwitching() {
      if (switchingTimer) {
        clearTimeout(switchingTimer);
        switchingTimer = 0;
      }
      if (switchingRaf1 && typeof cancelAnimationFrame === "function") {
        cancelAnimationFrame(switchingRaf1);
        switchingRaf1 = 0;
      }
      if (switchingRaf2 && typeof cancelAnimationFrame === "function") {
        cancelAnimationFrame(switchingRaf2);
        switchingRaf2 = 0;
      }
      try {
        htmlEl.classList.remove("aps-theme-switching");
      } catch (_e4) {}
      themeBusy = false;
    }

    function scheduleClearSwitching() {
      if (typeof requestAnimationFrame === "function") {
        switchingRaf1 = requestAnimationFrame(function () {
          switchingRaf1 = 0;
          switchingRaf2 = requestAnimationFrame(function () {
            switchingRaf2 = 0;
            clearSwitching();
          });
        });
      }
      switchingTimer = setTimeout(function () {
        switchingTimer = 0;
        clearSwitching();
      }, 220);
    }

    function applyThemeNow(theme) {
      var t = normalizeTheme(theme);
      var cur = normalizeTheme(htmlEl.getAttribute("data-theme") || "light");
      if (cur === t) {
        persistTheme(t);
        syncThemeUI(t);
        themeBusy = false;
        return;
      }
      try {
        htmlEl.classList.add("aps-theme-switching");
      } catch (_e5) {}
      try {
        htmlEl.setAttribute("data-theme", t);
      } catch (_e6) {}
      persistTheme(t);
      syncThemeUI(t);
      scheduleClearSwitching();
    }

    function scheduleApplyTheme(theme) {
      var t = normalizeTheme(theme);
      if (typeof requestAnimationFrame === "function") {
        requestAnimationFrame(function () {
          requestAnimationFrame(function () {
            applyThemeNow(t);
          });
        });
      } else {
        setTimeout(function () {
          applyThemeNow(t);
        }, 0);
      }
    }

    // 初始化：按钮状态以 html[data-theme] 为准（head 内联脚本已完成首屏主题设置）
    syncThemeUI(normalizeTheme(htmlEl.getAttribute("data-theme") || "light"));

    themeToggleBtn.addEventListener("click", function () {
      if (themeBusy) {
        return;
      }
      var current = normalizeTheme(htmlEl.getAttribute("data-theme") || "light");
      var next = current === "dark" ? "light" : "dark";
      themeBusy = true;

      // 先给用户即时反馈（按钮先动），再做昂贵的整页换肤
      syncThemeUI(next);
      scheduleApplyTheme(next);
    });

    // bfcache/回退恢复时：对齐存储主题与按钮 UI
    window.addEventListener("pageshow", function () {
      var stored = readStoredTheme();
      var current = normalizeTheme(htmlEl.getAttribute("data-theme") || "light");
      syncThemeUI(stored);
      if (stored === current) {
        return;
      }
      if (themeBusy) {
        return;
      }
      themeBusy = true;
      if (typeof requestAnimationFrame === "function") {
        requestAnimationFrame(function () {
          applyThemeNow(stored);
        });
      } else {
        setTimeout(function () {
          applyThemeNow(stored);
        }, 0);
      }
    });
  }
})();

