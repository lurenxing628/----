/* APS common_table.js — bulk/search/sort（Win7 + Chrome 109） */
(function () {
  "use strict";

  var ns = window.__APS_COMMON__;
  if (!ns) {
    return;
  }
  if (!ns._inited) {
    ns._inited = {};
  }
  if (ns._inited.table) {
    return;
  }
  ns._inited.table = true;

  var requestIdle = ns.requestIdle;
  var debounce = ns.debounce;
  if (typeof requestIdle !== "function" || typeof debounce !== "function") {
    return;
  }

  var getLogicalCellIndex = ns.getLogicalCellIndex;
  var getCellByLogicalIndex = ns.getCellByLogicalIndex;

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
  ns.updateBulkCount = updateBulkCount;
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

  /* --- 6.6 表头点击排序（严格 opt-in） --- */
  if (typeof getLogicalCellIndex === "function" && typeof getCellByLogicalIndex === "function") {
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
  }
})();

