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
    var btns = form.querySelectorAll("button[type='submit'], input[type='submit']");
    btns.forEach(function (b) {
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
        } catch (_e3) {
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
            } catch (_e4) {
              // ignore
            }
          });
        }, { root: null, rootMargin: "120px 0px", threshold: 0.01 });
      } catch (_e5) {
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
        } catch (_e6) {
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
