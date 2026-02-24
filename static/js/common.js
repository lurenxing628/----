/* APS common.js — 公共交互（Win7 + Chrome 109） */
(function () {
  "use strict";

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

  markRequiredLabels(document);
  if ("MutationObserver" in window) {
    function bindRequiredObservers(observer, root) {
      var scope = root && root.querySelectorAll ? root : document;
      scope.querySelectorAll("form").forEach(function (form) {
        if (!form || !form.getAttribute) {
          return;
        }
        if (form.getAttribute("data-required-observed") === "1") {
          return;
        }
        form.setAttribute("data-required-observed", "1");
        try {
          observer.observe(form, {
            childList: true,
            subtree: true,
            attributes: true,
            attributeFilter: ["required"],
          });
        } catch (_e1) {
          // ignore
        }
      });
    }

    var requiredLabelObserver = new MutationObserver(function (mutations) {
      var refreshRoot = null;
      var needsRebind = false;
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
          continue;
        }
        if (m.type === "childList") {
          if ((m.addedNodes && m.addedNodes.length) || (m.removedNodes && m.removedNodes.length)) {
            refreshRoot = document;
          }
          if (m.addedNodes && m.addedNodes.length) {
            needsRebind = true;
          }
        }
      }
      if (needsRebind) {
        bindRequiredObservers(requiredLabelObserver, document);
      }
      if (refreshRoot) {
        scheduleRequiredLabelRefresh(refreshRoot);
      }
    });
    bindRequiredObservers(requiredLabelObserver, document);
    try {
      requiredLabelObserver.observe(document.body, {
        childList: true,
        subtree: true,
      });
    } catch (_e2) {
      // ignore
    }
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

  /* --- 2. 确认对话框 --- */
  document.querySelectorAll("form[data-confirm]").forEach(function (form) {
    form.addEventListener("submit", function (e) {
      if (!confirm(form.getAttribute("data-confirm") || "确定继续吗？")) {
        e.preventDefault();
      }
    });
  });
  document.addEventListener("click", function (e) {
    var target = e.target;
    if (!target || !target.closest) {
      return;
    }
    var trigger = target.closest("button[data-confirm], input[type='submit'][data-confirm], a[data-confirm]");
    if (!trigger) {
      return;
    }
    if (!confirm(trigger.getAttribute("data-confirm") || "确定继续吗？")) {
      e.preventDefault();
      e.stopPropagation();
    }
  });
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
  document.querySelectorAll("form").forEach(function (form) {
    var method = (form.method || "").toLowerCase();
    if (method !== "post") {
      return;
    }
    form.addEventListener("submit", function (e) {
      if (e.defaultPrevented) {
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
  });

  /* --- 4. 批量选择计数 --- */
  var updateBulkCount = function () {};
  var bulkChecks = document.querySelectorAll(".js-bulk-check, .js-batch-check");
  var countEl = document.getElementById("jsSelectedCount");
  if (bulkChecks.length > 0 && countEl) {
    updateBulkCount = function () {
      var cnt = 0;
      bulkChecks.forEach(function (c) {
        if (c.checked) {
          cnt += 1;
        }
      });
      countEl.textContent = String(cnt);
    };
    bulkChecks.forEach(function (c) {
      c.addEventListener("change", updateBulkCount);
    });
    updateBulkCount();
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
    function rebuildRowCache() {
      rowCache = [];
      tbody.querySelectorAll("tr").forEach(function (row) {
        rowCache.push({
          el: row,
          text: (row.textContent || "").toLowerCase(),
        });
      });
    }
    rebuildRowCache();

    var searchToken = 0;
    function applySearch() {
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
      if ((tbody.rows && tbody.rows.length) !== rowCache.length) {
        rebuildRowCache();
      }
    });
  });

  /* --- 6. 全选 / 取消全选 --- */
  document.querySelectorAll(".js-select-all").forEach(function (allCb) {
    var scope = allCb.closest("table") || allCb.closest("form") || document;
    allCb.addEventListener("change", function () {
      var targets = scope.querySelectorAll(".js-bulk-check, .js-batch-check");
      targets.forEach(function (cb) {
        cb.checked = allCb.checked;
      });
      updateBulkCount();
    });
  });
})();
