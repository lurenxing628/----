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

  function markRequiredLabels(root) {
    var scope = root && root.querySelectorAll ? root : document;
    scope.querySelectorAll(".form-field").forEach(function (field) {
      var label = field.querySelector("label");
      if (!label) {
        return;
      }
      var requiredControl = field.querySelector("input[required], select[required], textarea[required]");
      label.classList.toggle("required-label", !!requiredControl);
    });
  }

  var requiredLabelRefreshTimer = 0;
  function scheduleRequiredLabelRefresh(root) {
    if (requiredLabelRefreshTimer) {
      clearTimeout(requiredLabelRefreshTimer);
    }
    requiredLabelRefreshTimer = setTimeout(function () {
      requiredLabelRefreshTimer = 0;
      markRequiredLabels(root && root.querySelectorAll ? root : document);
    }, 80);
  }

  requestIdle(function () {
    markRequiredLabels(document);
  }, 1000);
  if ("MutationObserver" in window) {
    var requiredLabelObserver = new MutationObserver(function (mutations) {
      var refreshRoot = null;
      for (var i = 0; i < mutations.length; i++) {
        var m = mutations[i];
        if (!m) {
          continue;
        }
        if (m.type === "attributes") {
          var target = m.target;
          if (target && target.closest) {
            refreshRoot = target.closest(".form-field") || target.closest("form") || document;
          } else {
            refreshRoot = document;
          }
        }
      }
      if (refreshRoot) {
        scheduleRequiredLabelRefresh(refreshRoot);
      }
    });
    try {
      requiredLabelObserver.observe(document.body, {
        attributes: true,
        subtree: true,
        attributeFilter: ["required"],
      });
    } catch (_e2) {
      // ignore
    }
  }
  // 动态表单兜底：在交互时按表单维度刷新，避免大范围扫描
  document.addEventListener("focusin", function (e) {
    var target = e.target;
    var form = target && target.form ? target.form : (target && target.closest ? target.closest("form") : null);
    if (form) {
      scheduleRequiredLabelRefresh(form);
    }
  }, true);
  document.addEventListener("change", function (e) {
    var target = e.target;
    var form = target && target.form ? target.form : (target && target.closest ? target.closest("form") : null);
    if (form) {
      scheduleRequiredLabelRefresh(form);
    }
  }, true);

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

  /* --- 2. 确认对话框：提交路径统一判定 + 去重 --- */
  // 回归契约关键字（tests/regression_frontend_common_interactions.py）
  var FORM_CONFIRM_SELECTOR = "form[data-confirm]";
  var CONFIRM_TRIGGER_SELECTOR = "button[data-confirm], input[type='submit'][data-confirm], a[data-confirm], input[type='image'][data-confirm]";

  function getConfirmText(el) {
    if (!el || !el.getAttribute) {
      return "";
    }
    var msg = el.getAttribute("data-confirm") || "";
    return String(msg).trim();
  }

  function isSubmitControl(el) {
    if (!el || !el.tagName) {
      return false;
    }
    var tag = String(el.tagName).toUpperCase();
    if (tag === "BUTTON") {
      var btnType = (el.getAttribute("type") || "submit").toLowerCase();
      return btnType === "submit";
    }
    if (tag === "INPUT") {
      var inputType = (el.getAttribute("type") || "").toLowerCase();
      return inputType === "submit" || inputType === "image";
    }
    return false;
  }

  function trackSubmitter(trigger) {
    if (!trigger || !trigger.form) {
      return;
    }
    var form = trigger.form;
    try {
      form._apsLastSubmitter = trigger;
      if (form._apsLastSubmitterTimer) {
        clearTimeout(form._apsLastSubmitterTimer);
      }
      form._apsLastSubmitterTimer = setTimeout(function () {
        if (!form) {
          return;
        }
        form._apsLastSubmitter = null;
        form._apsLastSubmitterTimer = 0;
      }, 1500);
    } catch (_e) {
      // ignore
    }
  }

  document.addEventListener("click", function (e) {
    var target = e.target;
    if (!target || !target.closest) {
      return;
    }
    var trigger = target.closest(CONFIRM_TRIGGER_SELECTOR);
    if (!trigger) {
      return;
    }

    var tag = String(trigger.tagName || "").toUpperCase();
    if (tag === "A") {
      if (!confirm(getConfirmText(trigger) || "确定继续吗？")) {
        e.preventDefault();
        e.stopPropagation();
      }
      return;
    }

    // submit 按钮统一在 submit 阶段确认，避免 click + submit 双重弹窗
    if (isSubmitControl(trigger) && trigger.form) {
      trackSubmitter(trigger);
      return;
    }

    // 非提交按钮（如 data-confirm + onclick）仍在 click 阶段确认
    if (!confirm(getConfirmText(trigger) || "确定继续吗？")) {
      e.preventDefault();
      e.stopPropagation();
    }
  });

  // Enter 触发隐式提交时，尽量补齐 submitter 信息，保证优先读取按钮级 data-confirm
  document.addEventListener("keydown", function (e) {
    var key = e.key || e.code || "";
    if (key !== "Enter" && key !== "NumpadEnter") {
      return;
    }
    var target = e.target;
    if (!target || !target.form) {
      return;
    }
    var form = target.form;
    if (!form || form._apsLastSubmitter) {
      return;
    }
    var guessed = form.querySelector("button[type='submit'][data-confirm], input[type='submit'][data-confirm]");
    if (!guessed) {
      guessed = form.querySelector("button[type='submit'], input[type='submit']");
    }
    if (guessed) {
      trackSubmitter(guessed);
    }
  });

  document.addEventListener("submit", function (e) {
    var form = e.target;
    if (!form || !form.getAttribute) {
      return;
    }

    var submitter = e.submitter || form._apsLastSubmitter || null;
    if (submitter && submitter.form !== form) {
      submitter = null;
    }

    var msg = getConfirmText(submitter);
    if (!msg && form.matches && form.matches(FORM_CONFIRM_SELECTOR)) {
      msg = getConfirmText(form);
    }
    if (!msg) {
      msg = getConfirmText(form);
    }
    if (!msg) {
      if (form._apsLastSubmitterTimer) {
        clearTimeout(form._apsLastSubmitterTimer);
        form._apsLastSubmitterTimer = 0;
      }
      form._apsLastSubmitter = null;
      return;
    }

    // 去重：同一提交链路（click -> submit）只确认一次
    var token = "form";
    if (submitter && submitter.id) {
      token = "s#" + submitter.id;
    } else if (submitter && submitter.name) {
      token = "n#" + submitter.name + "::" + String(submitter.value || "");
    }
    if (form.dataset && form.dataset.apsConfirmPending === "1" && form.dataset.apsConfirmToken === token) {
      return;
    }

    if (!confirm(msg || "确定继续吗？")) {
      e.preventDefault();
      if (form.dataset) {
        form.dataset.apsConfirmPending = "";
        form.dataset.apsConfirmToken = "";
      }
      if (form._apsLastSubmitterTimer) {
        clearTimeout(form._apsLastSubmitterTimer);
        form._apsLastSubmitterTimer = 0;
      }
      form._apsLastSubmitter = null;
      return;
    }

    if (form.dataset) {
      form.dataset.apsConfirmPending = "1";
      form.dataset.apsConfirmToken = token;
      setTimeout(function () {
        if (!form || !form.dataset) {
          return;
        }
        form.dataset.apsConfirmPending = "";
        form.dataset.apsConfirmToken = "";
      }, 0);
    }
    if (form._apsLastSubmitterTimer) {
      clearTimeout(form._apsLastSubmitterTimer);
      form._apsLastSubmitterTimer = 0;
    }
    form._apsLastSubmitter = null;
  }, true);
  document.querySelectorAll("select[data-auto-submit='1']").forEach(function (sel) {
    sel.addEventListener("change", function () {
      var form = sel.form;
      if (form && typeof form.requestSubmit === "function") {
        form.requestSubmit();
      } else if (form) {
        var canContinue = true;
        try {
          if ("Event" in window) {
            var submitEvt = new Event("submit", { bubbles: true, cancelable: true });
            canContinue = form.dispatchEvent(submitEvt);
          }
        } catch (_e2) {
          canContinue = true;
        }
        if (canContinue) {
          form.submit();
        }
      }
    });
  });

  /* --- 3. 防双击 + Loading --- */
  document.addEventListener("submit", function (e) {
    if (e.defaultPrevented) {
      return;
    }
    var form = e.target;
    if (!form || !form.tagName || String(form.tagName).toUpperCase() !== "FORM") {
      return;
    }
    var method = (form.method || "").toLowerCase();
    if (method !== "post") {
      return;
    }
    if (form.dataset && form.dataset.submitted === "1") {
      e.preventDefault();
      return;
    }
    if (form.dataset) {
      form.dataset.submitted = "1";
    }
    var submitter = e.submitter || form._apsLastSubmitter || null;
    if (submitter && submitter.form !== form) {
      submitter = null;
    }
    var btns = form.querySelectorAll("button[type='submit'], input[type='submit']");
    btns.forEach(function (b) {
      if (submitter && b === submitter) {
        // 关键：不要禁用/改写 submitter，避免 Win7/Chrome109 丢失 name/value
        return;
      }
      b.disabled = true;
      if (b.tagName === "BUTTON") {
        b.dataset.originalText = b.textContent;
        b.classList.add("btn-loading");
        b.textContent = "处理中...";
      } else if (b.tagName === "INPUT") {
        b.dataset.originalValue = b.value;
        b.value = "处理中...";
      }
    });
  });

  /* --- 4. 批量选择计数 --- */
  var updateBulkCount = function (fromTarget) {
    var countEl = document.getElementById("jsSelectedCount");
    if (!countEl) {
      return;
    }
    var scope = document;
    if (fromTarget && fromTarget.closest) {
      scope = fromTarget.closest("table, form, .card") || document;
    }
    var checks = scope.querySelectorAll(".js-bulk-check, .js-batch-check");
    if (!checks || checks.length <= 0) {
      checks = document.querySelectorAll(".js-bulk-check, .js-batch-check");
    }
    var cnt = 0;
    checks.forEach(function (c) {
      if (c.checked) {
        cnt += 1;
      }
    });
    countEl.textContent = String(cnt);
  };
  if (document.querySelectorAll(".js-bulk-check, .js-batch-check").length > 0 && document.getElementById("jsSelectedCount")) {
    requestIdle(function () {
      updateBulkCount(null);
    }, 800);
  }

  /* --- 5. 表格前端搜索 --- */
  /* 用法：<input data-table-search="myTableId" placeholder="搜索..."> */
  document.querySelectorAll("[data-table-search]").forEach(function (input) {
    var table = document.getElementById(input.getAttribute("data-table-search"));
    if (!table) {
      return;
    }
    var tbody = table.querySelector("tbody");
    if (!tbody) {
      return;
    }

    var rowCache = [];
    var rowCacheBuilt = false;
    var rowCacheBuilding = false;
    function rebuildRowCache() {
      rowCacheBuilding = true;
      rowCache = [];
      tbody.querySelectorAll("tr").forEach(function (row) {
        rowCache.push({
          el: row,
          text: (row.textContent || "").toLowerCase(),
        });
      });
      rowCacheBuilt = true;
      rowCacheBuilding = false;
    }
    function ensureRowCacheBuilt() {
      if (rowCacheBuilt || rowCacheBuilding) {
        return;
      }
      rebuildRowCache();
    }
    requestIdle(function () {
      ensureRowCacheBuilt();
    }, 1200);

    var searchToken = 0;
    function applySearch() {
      ensureRowCacheBuilt();
      if ((tbody.rows && tbody.rows.length) !== rowCache.length) {
        rebuildRowCache();
      }
      var kw = (input.value || "").toLowerCase();
      var token = searchToken + 1;
      searchToken = token;
      var idx = 0;

      function flushBatch() {
        if (token !== searchToken) {
          return;
        }
        var end = Math.min(idx + 180, rowCache.length);
        for (; idx < end; idx++) {
          var it = rowCache[idx];
          var nextDisplay = !kw || it.text.indexOf(kw) >= 0 ? "" : "none";
          if (it.el.style.display !== nextDisplay) {
            it.el.style.display = nextDisplay;
          }
        }
        if (idx < rowCache.length) {
          if (typeof requestAnimationFrame === "function") {
            requestAnimationFrame(flushBatch);
          } else {
            setTimeout(flushBatch, 0);
          }
        }
      }
      flushBatch();
    }

    var onInput = debounce(applySearch, 120);
    input.addEventListener("input", onInput);
    input.addEventListener("search", applySearch);
    input.addEventListener("focus", function () {
      ensureRowCacheBuilt();
      if ((tbody.rows && tbody.rows.length) !== rowCache.length) {
        rebuildRowCache();
      }
    });
  });

  /* --- 6. 全选 / 取消全选 + 计数（统一委托） --- */
  document.addEventListener("change", function (e) {
    var target = e.target;
    if (!target || !target.matches) {
      return;
    }
    if (target.matches(".js-select-all")) {
      var scope = target.closest("table") || target.closest("form") || document;
      var targets = scope.querySelectorAll(".js-bulk-check, .js-batch-check");
      targets.forEach(function (cb) {
        cb.checked = target.checked;
      });
      updateBulkCount(target);
      return;
    }
    if (target.matches(".js-bulk-check, .js-batch-check")) {
      updateBulkCount(target);
    }
  });

  /* --- 6.5 表单草稿自动保存（仅 data-autosave=true） --- */
  document.querySelectorAll('form[data-autosave="true"]').forEach(function (form) {
    var autosaveKey = String(form.getAttribute("data-autosave-key") || "").trim();
    if (!autosaveKey) {
      return;
    }
    var key = "aps_draft:v1:" + autosaveKey;
    var submitMarkKey = "aps_draft_submit:v1:" + autosaveKey;
    var tabToken = getOrCreateTabToken();
    var clearOnSuccess = String(form.getAttribute("data-autosave-clear-on-success") || "1").trim() !== "0";
    function snapshotsEqual(a, b) {
      try {
        return JSON.stringify(a || {}) === JSON.stringify(b || {});
      } catch (_e5) {
        return false;
      }
    }

    function hasSuccessFlash() {
      return !!document.querySelector(".flash-card.flash-success, .alert.alert-success");
    }

    function hasErrorFlash() {
      return !!document.querySelector(".flash-card.flash-error, .alert.alert-error");
    }

    function hasWarningFlash() {
      return !!document.querySelector(".flash-card.flash-warning, .alert.alert-warning");
    }

    var submitMarkTs = 0;
    var submitMarkToken = "";
    try {
      var rawSubmitMark = String(sessionStorage.getItem(submitMarkKey) || "").trim();
      if (rawSubmitMark.indexOf("|") > 0) {
        var parts = rawSubmitMark.split("|");
        submitMarkTs = Number(parts[0] || 0);
        submitMarkToken = String(parts[1] || "");
      } else {
        submitMarkTs = Number(rawSubmitMark || 0);
        submitMarkToken = "";
      }
    } catch (_e6) {}

    var submitOwnedByCurrentTab = !submitMarkToken || submitMarkToken === tabToken;
    if (submitMarkTs > 0 && submitOwnedByCurrentTab) {
      var elapsed = Date.now() - submitMarkTs;
      var hasSuccess = hasSuccessFlash();
      var hasError = hasErrorFlash();
      var hasWarning = hasWarningFlash();
      var currentSnapshot = serializeForm(form);
      var draftSnapshot = null;
      try {
        draftSnapshot = JSON.parse(localStorage.getItem(key) || "null");
      } catch (_e7) {
        draftSnapshot = null;
      }
      var canClearDraft = clearOnSuccess
        && hasSuccess
        && !hasError
        && snapshotsEqual(draftSnapshot, currentSnapshot);
      if (canClearDraft) {
        try {
          localStorage.removeItem(key);
        } catch (_e8) {}
      }
      if (hasSuccess || hasError || hasWarning || elapsed > 10 * 60 * 1000) {
        try {
          sessionStorage.removeItem(submitMarkKey);
        } catch (_e9) {}
      }
    }

    var saveDraft = debounce(function () {
      try {
        localStorage.setItem(key, JSON.stringify(serializeForm(form)));
      } catch (_e10) {}
    }, 1000);

    form.addEventListener("input", saveDraft, true);
    form.addEventListener("change", saveDraft, true);
    form.addEventListener("submit", function () {
      try {
        localStorage.setItem(key, JSON.stringify(serializeForm(form)));
      } catch (_e11) {}
      try {
        sessionStorage.setItem(submitMarkKey, String(Date.now()) + "|" + tabToken);
      } catch (_e12) {}
    });

    var saved = null;
    try {
      saved = JSON.parse(localStorage.getItem(key) || "null");
    } catch (_e13) {
      saved = null;
    }
    if (saved && Object.keys(saved).length > 0) {
      var notice = document.createElement("div");
      notice.className = "flash-card flash-warning alert alert-warning";
      notice.innerHTML = '检测到未保存的草稿。'
        + ' <button type="button" class="btn btn-sm btn-secondary" data-draft-action="restore">恢复草稿</button>'
        + ' <button type="button" class="btn btn-sm btn-ghost" data-draft-action="clear">清除</button>';
      if (form.parentNode) {
        form.parentNode.insertBefore(notice, form);
      }
      var restoreBtn = notice.querySelector('[data-draft-action="restore"]');
      var clearBtn = notice.querySelector('[data-draft-action="clear"]');
      if (restoreBtn) {
        restoreBtn.addEventListener("click", function () {
          restoreForm(form, saved);
          try {
            localStorage.removeItem(key);
          } catch (_e14) {}
          try {
            sessionStorage.removeItem(submitMarkKey);
          } catch (_e15) {}
          if (notice.parentNode) {
            notice.parentNode.removeChild(notice);
          }
        });
      }
      if (clearBtn) {
        clearBtn.addEventListener("click", function () {
          try {
            localStorage.removeItem(key);
          } catch (_e16) {}
          try {
            sessionStorage.removeItem(submitMarkKey);
          } catch (_e17) {}
          if (notice.parentNode) {
            notice.parentNode.removeChild(notice);
          }
        });
      }
    }
  });

  /* --- 6.6 表头点击排序（严格 opt-in） --- */
  document.querySelectorAll('table[data-sort-enabled="1"] th[data-sort]').forEach(function (th) {
    th.style.cursor = "pointer";
    th.title = "点击排序";
    th.addEventListener("click", function () {
      var table = th.closest("table");
      if (!table || table.getAttribute("data-sort-enabled") !== "1") {
        return;
      }
      if (table.querySelector('select, textarea, input:not([type="checkbox"]):not([type="radio"]):not([type="hidden"])')) {
        return;
      }
      var tbody = table.querySelector("tbody");
      if (!tbody) {
        return;
      }
      if (tbody.rows.length > 300) {
        if (window.APS_Toast) {
          window.APS_Toast("当前页数据较多，请使用筛选或分页", "warning", 2500);
        }
        return;
      }
      var logicalColIdx = getLogicalCellIndex(th);
      var asc = th.getAttribute("data-sort-dir") !== "asc";
      th.parentNode.querySelectorAll("th[data-sort]").forEach(function (x) {
        x.removeAttribute("data-sort-dir");
      });
      th.setAttribute("data-sort-dir", asc ? "asc" : "desc");
      var rows = Array.prototype.slice.call(tbody.querySelectorAll("tr"));
      var type = th.getAttribute("data-sort");
      var decorated = rows.map(function (row) {
        var cell = getCellByLogicalIndex(row, logicalColIdx);
        var raw = String((cell && cell.textContent) || "").trim();
        var key = raw;
        var invalid = false;
        if (type === "number") {
          var num = parseFloat(raw);
          if (isFinite(num)) {
            key = num;
          } else {
            key = 0;
            invalid = true;
          }
        } else if (type === "date") {
          var ts = Date.parse(raw);
          if (isFinite(ts)) {
            key = ts;
          } else {
            key = 0;
            invalid = true;
          }
        }
        return { row: row, key: key, raw: raw, invalid: invalid };
      });
      decorated.sort(function (a, b) {
        // 空值/非法值统一置底，避免在升序下跑到最前（如空交期=1970 问题）。
        if (type !== "text" && a.invalid !== b.invalid) {
          return a.invalid ? 1 : -1;
        }
        if (type === "text") {
          return asc
            ? String(a.raw).localeCompare(String(b.raw), "zh")
            : String(b.raw).localeCompare(String(a.raw), "zh");
        }
        return asc ? (a.key - b.key) : (b.key - a.key);
      });
      var frag = document.createDocumentFragment();
      decorated.forEach(function (it) {
        frag.appendChild(it.row);
      });
      tbody.appendChild(frag);
    });
  });

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

  /* --- 7. 原生页面预取（白名单 GET） --- */
  if (NATIVE_PREFETCH_ENABLED && document.head) {
    var prefetched = {};
    function prefetchPath(pathname) {
      if (!pathname || prefetched[pathname]) {
        return;
      }
      prefetched[pathname] = true;
      requestIdle(function () {
        try {
          var link = document.createElement("link");
          link.rel = "prefetch";
          link.href = pathname;
          link.as = "document";
          document.head.appendChild(link);
        } catch (_e13) {
          // ignore prefetch failures
        }
      }, 1200);
    }

    var navObserver = null;
    if ("IntersectionObserver" in window) {
      try {
        navObserver = new IntersectionObserver(function (entries) {
          entries.forEach(function (entry) {
            if (!entry || !entry.isIntersecting) {
              return;
            }
            var a = entry.target;
            if (!a || !a.getAttribute) {
              return;
            }
            var p = normalizePrefetchUrl(a.getAttribute("href") || "");
            if (p) {
              prefetchPath(p);
            }
            try {
              navObserver.unobserve(a);
            } catch (_e14) {
              // ignore
            }
          });
        }, { root: null, rootMargin: "120px 0px", threshold: 0.01 });
      } catch (_e15) {
        navObserver = null;
      }
    }

    var prefetchLinks = document.querySelectorAll("header nav a[href], .sidebar .nav-item[href], .scheduler-subnav a[href]");
    var observed = 0;
    prefetchLinks.forEach(function (a) {
      if (observed >= 24) {
        return;
      }
      var p = normalizePrefetchUrl(a.getAttribute("href") || "");
      if (!p) {
        return;
      }
      if (p === window.location.pathname) {
        return;
      }
      observed += 1;
      if (navObserver) {
        try {
          navObserver.observe(a);
        } catch (_e16) {
          // ignore
        }
      } else {
        prefetchPath(p);
      }
    });
  }

  // 延迟执行的非关键初始化任务（缩短首帧阻塞）
  requestIdle(function () {
    scheduleRequiredLabelRefresh(document);
    updateBulkCount(null);
  });
})();
