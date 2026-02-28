/* APS common.js — 公共交互（Win7 + Chrome 109） */
(function () {
  "use strict";

  var NATIVE_PREFETCH_ENABLED = true;
  // 允许通过 window.__APS_PREFETCH_ENABLED__ 动态覆盖：便于现场快速关停预取
  if (window && Object.prototype.hasOwnProperty.call(window, "__APS_PREFETCH_ENABLED__")) {
    var v = window.__APS_PREFETCH_ENABLED__;
    if (v === true || v === false) {
      NATIVE_PREFETCH_ENABLED = v === true;
    } else {
      var sv = String(v || "").trim().toLowerCase();
      if (sv === "1" || sv === "true" || sv === "yes" || sv === "on") {
        NATIVE_PREFETCH_ENABLED = true;
      } else if (sv === "0" || sv === "false" || sv === "no" || sv === "off") {
        NATIVE_PREFETCH_ENABLED = false;
      }
    }
  }
  var PREFETCH_IDLE_FALLBACK_MS = 900;
  var PREFETCH_WHITELIST_PATHS = {
    "/": 1,
    "/scheduler/": 1,
    "/scheduler/batches": 1,
    "/scheduler/config": 1,
    "/scheduler/gantt": 1,
    "/scheduler/analysis": 1,
    "/scheduler/week-plan": 1,
    "/scheduler/calendar": 1,
    "/equipment/": 1,
    "/personnel/": 1,
    "/process/": 1,
    "/material/materials": 1,
    "/reports/": 1,
    "/system/backup": 1,
    "/system/logs": 1,
    "/system/history": 1,
  };

  function requestIdle(cb, timeout) {
    if (typeof window.requestIdleCallback === "function") {
      return window.requestIdleCallback(cb, { timeout: timeout || 1200 });
    }
    return setTimeout(function () {
      cb({ didTimeout: true, timeRemaining: function () { return 0; } });
    }, typeof timeout === "number" ? timeout : PREFETCH_IDLE_FALLBACK_MS);
  }

  function isSameOriginHttpUrl(url) {
    if (!url || typeof url !== "string") {
      return false;
    }
    try {
      var u = new URL(url, window.location.href);
      if (u.origin !== window.location.origin) {
        return false;
      }
      if (u.protocol !== "http:" && u.protocol !== "https:") {
        return false;
      }
      return true;
    } catch (_e0) {
      return false;
    }
  }

  function isWhitelistedPrefetchPath(pathname) {
    if (!pathname) {
      return false;
    }
    return !!PREFETCH_WHITELIST_PATHS[pathname];
  }

  function normalizePrefetchUrl(rawHref) {
    if (!isSameOriginHttpUrl(rawHref)) {
      return "";
    }
    try {
      var u = new URL(rawHref, window.location.href);
      if (!isWhitelistedPrefetchPath(u.pathname)) {
        return "";
      }
      if (u.search) {
        return "";
      }
      if (u.hash) {
        u.hash = "";
      }
      return u.pathname;
    } catch (_e1) {
      return "";
    }
  }

  function debounce(fn, waitMs) {
    var timer = 0;
    return function () {
      var ctx = this;
      var args = arguments;
      if (timer) {
        clearTimeout(timer);
      }
      timer = setTimeout(function () {
        fn.apply(ctx, args);
      }, waitMs);
    };
  }

  function cssEscapeCompat(s) {
    try {
      if (window.CSS && typeof window.CSS.escape === "function") {
        return window.CSS.escape(String(s));
      }
    } catch (_e0) {}
    return String(s).replace(/[^a-zA-Z0-9_\\-]/g, "\\$&");
  }

  function serializeForm(form) {
    var data = {};
    if (!form) {
      return data;
    }
    var inputs = form.querySelectorAll("input, select, textarea");
    for (var i = 0; i < inputs.length; i++) {
      var el = inputs[i];
      if (!el || el.disabled) {
        continue;
      }
      var name = el.name;
      var type = String(el.type || "").toLowerCase();
      if (!name || type === "hidden" || type === "submit" || type === "button") {
        continue;
      }
      if (type === "checkbox") {
        data["__cb__" + name] = el.checked ? "1" : "0";
      } else if (type === "radio") {
        if (el.checked) {
          data[name] = el.value;
        }
      } else {
        data[name] = el.value;
      }
    }
    return data;
  }

  function restoreForm(form, saved) {
    if (!form || !saved) {
      return;
    }

    Object.keys(saved).forEach(function (k) {
      if (k.indexOf("__cb__") !== 0) {
        return;
      }
      var name = k.slice(6);
      var checked = String(saved[k]) === "1";
      var cbs = form.querySelectorAll('input[type="checkbox"][name="' + cssEscapeCompat(name) + '"]');
      cbs.forEach(function (cb) {
        cb.checked = checked;
        try {
          cb.dispatchEvent(new Event("change", { bubbles: true }));
        } catch (_e1) {}
      });
    });

    Object.keys(saved).forEach(function (name) {
      if (name.indexOf("__cb__") === 0) {
        return;
      }
      var val = saved[name];
      var els = form.querySelectorAll('[name="' + cssEscapeCompat(name) + '"]');
      els.forEach(function (el) {
        if (!el || el.disabled) {
          return;
        }
        var tag = String(el.tagName || "").toUpperCase();
        var type = String(el.type || "").toLowerCase();
        if (type === "radio") {
          el.checked = String(el.value) === String(val);
          try {
            el.dispatchEvent(new Event("change", { bubbles: true }));
          } catch (_e2) {}
          return;
        }
        if (tag === "SELECT") {
          el.value = String(val);
          try {
            el.dispatchEvent(new Event("change", { bubbles: true }));
          } catch (_e3) {}
          return;
        }
        if (tag === "TEXTAREA" || tag === "INPUT") {
          el.value = String(val);
          try {
            el.dispatchEvent(new Event("input", { bubbles: true }));
          } catch (_e4) {}
          try {
            el.dispatchEvent(new Event("change", { bubbles: true }));
          } catch (_e5) {}
        }
      });
    });
  }

  function normalizeColSpan(v) {
    var n = parseInt(v, 10);
    if (!isFinite(n) || n < 1) {
      return 1;
    }
    return n;
  }

  function getLogicalCellIndex(cell) {
    if (!cell || !cell.parentNode || !cell.parentNode.children) {
      return 0;
    }
    var siblings = cell.parentNode.children;
    var logical = 0;
    for (var i = 0; i < siblings.length; i++) {
      var c = siblings[i];
      if (c === cell) {
        return logical;
      }
      logical += normalizeColSpan(c.getAttribute ? c.getAttribute("colspan") : 1);
    }
    return logical;
  }

  function getCellByLogicalIndex(row, logicalIdx) {
    if (!row || !row.children || logicalIdx < 0) {
      return null;
    }
    var acc = 0;
    for (var i = 0; i < row.children.length; i++) {
      var c = row.children[i];
      var span = normalizeColSpan(c.getAttribute ? c.getAttribute("colspan") : 1);
      if (logicalIdx >= acc && logicalIdx < acc + span) {
        return c;
      }
      acc += span;
    }
    return null;
  }

  function getOrCreateTabToken() {
    var key = "aps_tab_token:v1";
    var token = "";
    try {
      token = String(sessionStorage.getItem(key) || "").trim();
    } catch (_e0) {}
    if (token) {
      return token;
    }
    token = String(Date.now()) + "-" + String(Math.random()).slice(2, 10);
    try {
      sessionStorage.setItem(key, token);
    } catch (_e1) {}
    return token;
  }

  function removeNodeWithFade(el, delayMs) {
    setTimeout(function () {
      el.style.opacity = "0";
      setTimeout(function () {
        if (el.parentNode) {
          el.parentNode.removeChild(el);
        }
      }, 420);
    }, delayMs || 0);
  }

  // 共享命名空间：各模块通过这里取工具函数/写回挂载点
  var ns = window.__APS_COMMON__;
  if (!ns) {
    ns = {};
    window.__APS_COMMON__ = ns;
  }
  if (!ns._inited) {
    ns._inited = {};
  }

  ns.NATIVE_PREFETCH_ENABLED = NATIVE_PREFETCH_ENABLED;
  ns.PREFETCH_WHITELIST_PATHS = PREFETCH_WHITELIST_PATHS;
  ns.requestIdle = requestIdle;
  ns.debounce = debounce;
  ns.cssEscapeCompat = cssEscapeCompat;
  ns.serializeForm = serializeForm;
  ns.restoreForm = restoreForm;
  ns.normalizeColSpan = normalizeColSpan;
  ns.getLogicalCellIndex = getLogicalCellIndex;
  ns.getCellByLogicalIndex = getCellByLogicalIndex;
  ns.getOrCreateTabToken = getOrCreateTabToken;
  ns.removeNodeWithFade = removeNodeWithFade;
  ns.normalizePrefetchUrl = normalizePrefetchUrl;

  // 模块挂载点（由各 common_*.js 写入）
  if (!("scheduleRequiredLabelRefresh" in ns)) {
    ns.scheduleRequiredLabelRefresh = null;
  }
  if (!("updateBulkCount" in ns)) {
    ns.updateBulkCount = null;
  }

  // 延迟执行的非关键初始化任务（缩短首帧阻塞）
  requestIdle(function () {
    var n = window.__APS_COMMON__ || {};
    if (typeof n.scheduleRequiredLabelRefresh === "function") {
      n.scheduleRequiredLabelRefresh(document);
    }
    if (typeof n.updateBulkCount === "function") {
      n.updateBulkCount(null);
    }
  });
})();

