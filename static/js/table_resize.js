/* APS table column resize + persistence (Win7/Chrome109 friendly) */
(function () {
  "use strict";

  var LS_COL_PREFIX = "aps_table_colwidth:v1:";
  var LS_DENSITY_KEY = "aps_table_density:v1";

  var DENSITY_ORDER = ["compact", "normal", "loose"];
  var DENSITY_LABEL = {
    compact: "紧凑",
    normal: "标准",
    loose: "宽松"
  };

  var DEFAULT_MIN_W = 60;
  var DEFAULT_MAX_W = 1600;
  var AUTOFIT_MAX_ROWS = 60;
  var AUTOFIT_EXTRA_PX = 20;

  function safeJsonParse(s) {
    try {
      return JSON.parse(s);
    } catch (_e) {
      return null;
    }
  }

  function lsGet(key) {
    try {
      return localStorage.getItem(key);
    } catch (_e) {
      return null;
    }
  }

  function lsSet(key, val) {
    try {
      localStorage.setItem(key, val);
      return true;
    } catch (_e) {
      return false;
    }
  }

  function lsRemove(key) {
    try {
      localStorage.removeItem(key);
      return true;
    } catch (_e) {
      return false;
    }
  }

  function clamp(n, lo, hi) {
    if (n < lo) return lo;
    if (n > hi) return hi;
    return n;
  }

  function normalizeDensity(v) {
    v = String(v || "").trim();
    for (var i = 0; i < DENSITY_ORDER.length; i++) {
      if (DENSITY_ORDER[i] === v) {
        return v;
      }
    }
    return "normal";
  }

  function getDensity() {
    var cur = "";
    try {
      cur = document.documentElement.getAttribute("data-table-density") || "";
    } catch (_e0) {}
    cur = normalizeDensity(cur);
    if (cur !== "normal") {
      return cur;
    }
    // normal might also mean "unset"; fall back to storage if present
    var saved = lsGet(LS_DENSITY_KEY) || "";
    saved = normalizeDensity(saved);
    return saved || "normal";
  }

  function applyDensity(d, persist) {
    d = normalizeDensity(d);
    try {
      document.documentElement.setAttribute("data-table-density", d);
    } catch (_e0) {}
    if (persist) {
      lsSet(LS_DENSITY_KEY, d);
    }
    return d;
  }

  function updateDensityButton(d) {
    var btn = document.getElementById("apsTableDensityToggle");
    if (!btn) return;
    var label = DENSITY_LABEL[d] || "标准";
    btn.textContent = "密度：" + label;
    btn.setAttribute("data-density", d);
    btn.title = "切换表格密度（行高）";
    btn.setAttribute("aria-label", "切换表格密度（当前：" + label + "）");
  }

  function nextDensity(d) {
    d = normalizeDensity(d);
    for (var i = 0; i < DENSITY_ORDER.length; i++) {
      if (DENSITY_ORDER[i] === d) {
        return DENSITY_ORDER[(i + 1) % DENSITY_ORDER.length];
      }
    }
    return "normal";
  }

  function initDensity() {
    var d = getDensity();
    d = applyDensity(d, false);
    updateDensityButton(d);

    var btn = document.getElementById("apsTableDensityToggle");
    if (!btn || btn.__aps_density_bound) return;
    btn.__aps_density_bound = true;
    btn.addEventListener("click", function () {
      var cur = getDensity();
      var nxt = nextDensity(cur);
      var applied = applyDensity(nxt, true);
      updateDensityButton(applied);
      if (window.APS_Toast) {
        try {
          window.APS_Toast("表格密度已切换为：" + (DENSITY_LABEL[applied] || applied), "info", 1600);
        } catch (_e0) {}
      }
    });
  }

  function normalizeColSpan(v) {
    var n = parseInt(v, 10);
    if (!isFinite(n) || n < 1) {
      return 1;
    }
    return n;
  }

  function getHeaderRow(table) {
    if (!table) return null;
    var thead = table.tHead || table.querySelector("thead");
    if (!thead) return null;
    var tr = thead.querySelector("tr");
    return tr || null;
  }

  function getHeaderCells(headerRow) {
    if (!headerRow || !headerRow.children) return [];
    return Array.prototype.slice.call(headerRow.children);
  }

  function getLogicalColCount(cells) {
    var n = 0;
    for (var i = 0; i < cells.length; i++) {
      var cell = cells[i];
      var span = normalizeColSpan(cell.getAttribute ? cell.getAttribute("colspan") : 1);
      n += span;
    }
    return n;
  }

  function normalizeHeaderText(s) {
    return String(s || "")
      .replace(/\s+/g, " ")
      .replace(/\u00a0/g, " ")
      .trim();
  }

  function buildHeaderSig(cells) {
    var parts = [];
    for (var i = 0; i < cells.length; i++) {
      var cell = cells[i];
      var span = normalizeColSpan(cell.getAttribute ? cell.getAttribute("colspan") : 1);
      var colKey = "";
      try {
        colKey = String(cell.getAttribute ? cell.getAttribute("data-col-key") : "") || "";
      } catch (_e0) {
        colKey = "";
      }
      var text = normalizeHeaderText(colKey || cell.textContent);
      parts.push(text + "(" + String(span) + ")");
    }
    return parts.join("|");
  }

  function sanitizeWidthArray(widths, logicalColCount, minWByCol) {
    if (!widths || !widths.length) return null;
    if (widths.length !== logicalColCount) return null;
    var out = [];
    for (var i = 0; i < widths.length; i++) {
      var w = parseInt(widths[i], 10);
      if (!isFinite(w) || w <= 0) {
        w = 120;
      }
      var minW = DEFAULT_MIN_W;
      if (minWByCol && minWByCol.length === logicalColCount) {
        var m = parseInt(minWByCol[i], 10);
        if (isFinite(m) && m > 0) {
          minW = m;
        }
      }
      out.push(clamp(w, minW, DEFAULT_MAX_W));
    }
    return out;
  }

  function computeMinWByCol(headerCells, logicalColCount) {
    var minWByCol = [];
    var logicalIdx = 0;
    for (var i = 0; i < headerCells.length; i++) {
      var cell = headerCells[i];
      var span = normalizeColSpan(cell.getAttribute ? cell.getAttribute("colspan") : 1);
      var minW = DEFAULT_MIN_W;
      if (span === 1) {
        minW = getMinW(cell);
      }
      for (var k = 0; k < span; k++) {
        minWByCol[logicalIdx + k] = minW;
      }
      logicalIdx += span;
      if (logicalIdx >= logicalColCount) {
        break;
      }
    }
    while (minWByCol.length < logicalColCount) {
      minWByCol.push(DEFAULT_MIN_W);
    }
    if (minWByCol.length > logicalColCount) {
      minWByCol = minWByCol.slice(0, logicalColCount);
    }
    return minWByCol;
  }

  function measureDefaultWidths(cells, logicalColCount) {
    var widths = [];
    for (var i = 0; i < cells.length; i++) {
      var cell = cells[i];
      var span = normalizeColSpan(cell.getAttribute ? cell.getAttribute("colspan") : 1);
      var w = 0;
      try {
        w = Math.round(cell.getBoundingClientRect().width);
      } catch (_e0) {
        w = cell.offsetWidth || 0;
      }
      if (!isFinite(w) || w <= 0) {
        w = 120;
      }
      var per = Math.max(1, Math.round(w / span));
      for (var k = 0; k < span; k++) {
        widths.push(per);
      }
    }
    while (widths.length < logicalColCount) {
      widths.push(120);
    }
    if (widths.length > logicalColCount) {
      widths = widths.slice(0, logicalColCount);
    }
    return widths;
  }

  function ensureColgroup(table, logicalColCount) {
    var colgroup = table.querySelector("colgroup");
    if (!colgroup) {
      colgroup = document.createElement("colgroup");
      if (table.firstChild) {
        table.insertBefore(colgroup, table.firstChild);
      } else {
        table.appendChild(colgroup);
      }
    }
    while (colgroup.children.length < logicalColCount) {
      colgroup.appendChild(document.createElement("col"));
    }
    while (colgroup.children.length > logicalColCount) {
      colgroup.removeChild(colgroup.lastChild);
    }
    return colgroup;
  }

  function applyColWidths(colgroup, widths) {
    var cols = colgroup.children;
    for (var i = 0; i < cols.length; i++) {
      var w = widths[i];
      if (!isFinite(w) || w <= 0) {
        w = 120;
      }
      cols[i].style.width = String(Math.round(w)) + "px";
    }
  }

  function readColWidths(colgroup) {
    var widths = [];
    var cols = colgroup.children;
    for (var i = 0; i < cols.length; i++) {
      var col = cols[i];
      var w = parseInt(col.style.width || "", 10);
      if (!isFinite(w) || w <= 0) {
        try {
          if (window.getComputedStyle) {
            var cs = window.getComputedStyle(col);
            var csw = parseInt((cs && cs.width) || "", 10);
            if (isFinite(csw) && csw > 0) {
              w = csw;
            }
          }
        } catch (_e0) {}
      }
      if (!isFinite(w) || w <= 0) {
        try {
          w = Math.round(col.getBoundingClientRect().width);
        } catch (_e1) {
          w = 120;
        }
      }
      if (!isFinite(w) || w <= 0) {
        w = 120;
      }
      widths.push(w);
    }
    return widths;
  }

  function getTableKey(table) {
    if (!table) return "";
    var k = String(table.getAttribute("data-table-key") || "").trim();
    if (k) return k;
    var id = String(table.id || "").trim();
    if (id) return id;
    return "";
  }

  function getPersistKeyForTable(table) {
    var k = getTableKey(table);
    if (!k) return "";
    return LS_COL_PREFIX + k;
  }

  function shouldAllowResizeCell(cell, logicalIdx, logicalColCount) {
    if (!cell || !cell.getAttribute) return false;

    var attr = String(cell.getAttribute("data-resize") || "").trim();
    if (attr === "0") return false;
    if (attr === "1") return true;

    var span = normalizeColSpan(cell.getAttribute("colspan"));
    if (span !== 1) {
      return false;
    }

    // auto-disable checkbox columns
    try {
      if (cell.querySelector && cell.querySelector('input[type="checkbox"]')) {
        return false;
      }
    } catch (_e0) {}

    // auto-disable action columns (can be overridden via data-resize="1")
    var t = normalizeHeaderText(cell.textContent);
    if (t && t.indexOf("操作") >= 0) {
      return false;
    }

    // last column often holds actions even without text; keep conservative
    if (logicalIdx === logicalColCount - 1 && (!t || t === "-")) {
      return false;
    }

    return true;
  }

  function getMinW(cell) {
    if (!cell || !cell.getAttribute) return DEFAULT_MIN_W;
    var v = parseInt(cell.getAttribute("data-min-w") || "", 10);
    if (isFinite(v) && v > 0) return v;
    return DEFAULT_MIN_W;
  }

  function findWrapperToInsertTools(table) {
    if (!table || !table.parentElement) return table;
    var p = table.parentElement;
    try {
      if (p.classList && p.classList.contains("overflow-x-auto")) {
        return p;
      }
    } catch (_e0) {}
    return table;
  }

  function insertTableToolsOnce(table) {
    if (!table || table.__aps_colresize_tools_inserted) return;
    table.__aps_colresize_tools_inserted = true;

    var key = getTableKey(table);
    if (!key) return;

    var holder = findWrapperToInsertTools(table);
    var parent = holder && holder.parentNode;
    if (!parent) return;

    var bar = document.createElement("div");
    bar.className = "aps-table-tools no-print";

    var left = document.createElement("div");
    left.className = "aps-table-tools-left";

    var hint = document.createElement("span");
    hint.className = "muted text-xs";
    hint.textContent = "提示：拖拽表头边缘可调整列宽，双击可自适应。";

    left.appendChild(hint);

    var actions = document.createElement("div");
    actions.className = "aps-table-tools-actions";

    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "btn btn-secondary btn-sm";
    btn.textContent = "重置列宽";
    btn.addEventListener("click", function () {
      try {
        resetTableWidths(table);
      } catch (_e0) {}
    });
    actions.appendChild(btn);

    bar.appendChild(left);
    bar.appendChild(actions);

    parent.insertBefore(bar, holder);
  }

  function resetTableWidths(table) {
    if (!table) return;
    var persistKey = getPersistKeyForTable(table);
    if (persistKey) {
      lsRemove(persistKey);
    }
    var colgroup = table.querySelector("colgroup");
    var defaults = table.__aps_colresize_default_widths;
    if (colgroup && defaults && defaults.length) {
      applyColWidths(colgroup, defaults);
    }
    if (window.APS_Toast) {
      try {
        window.APS_Toast("已重置列宽", "info", 1600);
      } catch (_e1) {}
    }
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

  function isRowVisible(row) {
    if (!row) return false;
    if (row.hidden) return false;
    if (row.style && row.style.display === "none") return false;
    try {
      if (row.getClientRects && row.getClientRects().length === 0) {
        return false;
      }
    } catch (_e0) {}
    return true;
  }

  function autoFitColumn(table, colIdx, headerCell, minW, maxW) {
    var target = 0;
    try {
      target = Math.max(target, headerCell ? headerCell.scrollWidth : 0);
    } catch (_e0) {}

    var tbody = table.tBodies && table.tBodies.length ? table.tBodies[0] : table.querySelector("tbody");
    if (tbody && tbody.rows && tbody.rows.length) {
      // collect visible rows up to AUTOFIT_MAX_ROWS (sampling if needed)
      var vis = [];
      for (var i = 0; i < tbody.rows.length; i++) {
        var r = tbody.rows[i];
        if (!isRowVisible(r)) continue;
        vis.push(r);
      }
      var step = 1;
      if (vis.length > AUTOFIT_MAX_ROWS) {
        step = Math.ceil(vis.length / AUTOFIT_MAX_ROWS);
      }
      for (var j = 0; j < vis.length; j += step) {
        var row = vis[j];
        var cell = getCellByLogicalIndex(row, colIdx);
        if (!cell) continue;
        try {
          target = Math.max(target, cell.scrollWidth);
        } catch (_e1) {}
      }
    }

    target = target + AUTOFIT_EXTRA_PX;
    target = clamp(target, minW, maxW);
    return target;
  }

  function persistTableWidths(table, sig) {
    var persistKey = getPersistKeyForTable(table);
    if (!persistKey) return;
    var colgroup = table.querySelector("colgroup");
    if (!colgroup) return;
    var widths = readColWidths(colgroup);
    var payload = {
      v: 1,
      sig: sig,
      widths: widths
    };
    lsSet(persistKey, JSON.stringify(payload));
  }

  var drag = null;
  function setDragActive(active) {
    try {
      document.body.classList.toggle("aps-col-resize-active", !!active);
    } catch (_e0) {}
  }

  function clearDrag() {
    if (!drag) return;
    if (drag.rafId) {
      try {
        cancelAnimationFrame(drag.rafId);
      } catch (_e0) {}
    }
    drag.rafId = 0;
    setDragActive(false);
    document.removeEventListener("mousemove", onDocMouseMove, true);
    document.removeEventListener("mouseup", onDocMouseUp, true);
    drag = null;
  }

  function onDocMouseMove(e) {
    if (!drag) return;
    drag.lastX = e.clientX;
    if (drag.rafId) return;
    drag.rafId = requestAnimationFrame(function () {
      if (!drag) return;
      drag.rafId = 0;
      var dx = drag.lastX - drag.startX;
      var w = clamp(drag.startW + dx, drag.minW, drag.maxW);
      drag.colEl.style.width = String(Math.round(w)) + "px";
    });
  }

  function applyDragWidthNow() {
    if (!drag) return;
    if (drag.rafId) {
      try {
        cancelAnimationFrame(drag.rafId);
      } catch (_e0) {}
      drag.rafId = 0;
    }
    var lastX = typeof drag.lastX === "number" ? drag.lastX : drag.startX;
    var dx = lastX - drag.startX;
    var w = clamp(drag.startW + dx, drag.minW, drag.maxW);
    drag.colEl.style.width = String(Math.round(w)) + "px";
  }

  function onDocMouseUp(e) {
    if (!drag) return;
    try {
      drag.lastX = e && typeof e.clientX === "number" ? e.clientX : drag.lastX;
    } catch (_e0) {}
    applyDragWidthNow();
    try {
      persistTableWidths(drag.table, drag.sig);
    } catch (_e1) {}
    clearDrag();
  }

  function flushDragAndClear() {
    if (!drag) return;
    applyDragWidthNow();
    try {
      persistTableWidths(drag.table, drag.sig);
    } catch (_e0) {}
    clearDrag();
  }

  function onWindowBlur() {
    flushDragAndClear();
  }

  function onVisibilityChange() {
    try {
      if (document.hidden) {
        flushDragAndClear();
      }
    } catch (_e0) {}
  }

  function onHandleMouseDown(e) {
    if (!e || e.button !== 0) return;
    if (!e.currentTarget) return;
    e.preventDefault();
    e.stopPropagation();

    var handle = e.currentTarget;
    var th = handle.parentNode;
    if (!th) return;
    var table = null;
    try {
      table = th.closest ? th.closest("table") : null;
    } catch (_e0) {}
    if (!table) return;

    var colgroup = table.querySelector("colgroup");
    if (!colgroup) return;

    var colIdx = parseInt(handle.getAttribute("data-col-idx") || "", 10);
    if (!isFinite(colIdx) || colIdx < 0 || colIdx >= colgroup.children.length) return;

    var colEl = colgroup.children[colIdx];
    var startW = parseInt(colEl.style.width || "", 10);
    if (!isFinite(startW) || startW <= 0) {
      try {
        startW = Math.round(th.getBoundingClientRect().width);
      } catch (_e1) {
        startW = th.offsetWidth || 120;
      }
    }

    drag = {
      table: table,
      sig: table.__aps_colresize_sig || "",
      colEl: colEl,
      startX: e.clientX,
      lastX: e.clientX,
      startW: startW,
      minW: getMinW(th),
      maxW: DEFAULT_MAX_W,
      rafId: 0
    };

    setDragActive(true);
    document.addEventListener("mousemove", onDocMouseMove, true);
    document.addEventListener("mouseup", onDocMouseUp, true);
  }

  function onHandleClick(e) {
    // prevent th click (sort) from firing
    if (!e) return;
    e.preventDefault();
    e.stopPropagation();
  }

  function onHandleDblClick(e) {
    if (!e || !e.currentTarget) return;
    e.preventDefault();
    e.stopPropagation();

    var handle = e.currentTarget;
    var th = handle.parentNode;
    if (!th) return;
    var table = null;
    try {
      table = th.closest ? th.closest("table") : null;
    } catch (_e0) {}
    if (!table) return;
    var colgroup = table.querySelector("colgroup");
    if (!colgroup) return;
    var colIdx = parseInt(handle.getAttribute("data-col-idx") || "", 10);
    if (!isFinite(colIdx) || colIdx < 0 || colIdx >= colgroup.children.length) return;

    var minW = getMinW(th);
    var w = autoFitColumn(table, colIdx, th, minW, DEFAULT_MAX_W);
    colgroup.children[colIdx].style.width = String(Math.round(w)) + "px";
    persistTableWidths(table, table.__aps_colresize_sig || "");
  }

  function installHandles(table, headerCells, logicalColCount) {
    var logicalIdx = 0;
    for (var i = 0; i < headerCells.length; i++) {
      var cell = headerCells[i];
      var span = normalizeColSpan(cell.getAttribute ? cell.getAttribute("colspan") : 1);
      if (shouldAllowResizeCell(cell, logicalIdx, logicalColCount)) {
        try {
          if (cell.classList) {
            cell.classList.add("aps-col-resize-cell");
          }
        } catch (_e0) {}
        // Ensure the resize handle has a positioned containing block
        try {
          if (window.getComputedStyle) {
            var pos = window.getComputedStyle(cell).position;
            if (!pos || pos === "static") {
              cell.style.position = "relative";
            }
          } else {
            cell.style.position = "relative";
          }
        } catch (_e1) {
          try {
            cell.style.position = "relative";
          } catch (_e2) {}
        }

        var handle = document.createElement("span");
        handle.className = "aps-col-resize-handle";
        handle.setAttribute("aria-hidden", "true");
        handle.setAttribute("data-col-idx", String(logicalIdx));
        handle.addEventListener("mousedown", onHandleMouseDown, true);
        handle.addEventListener("click", onHandleClick, true);
        handle.addEventListener("dblclick", onHandleDblClick, true);
        cell.appendChild(handle);
      }
      logicalIdx += span;
    }
  }

  function initOneTable(table) {
    var persistKey = getPersistKeyForTable(table);

    var headerRow = getHeaderRow(table);
    if (!headerRow) return;
    var headerCells = getHeaderCells(headerRow);
    if (!headerCells.length) return;

    var logicalColCount = getLogicalColCount(headerCells);
    if (!logicalColCount) return;

    if (table.__aps_colresize_inited) return;
    table.__aps_colresize_inited = true;

    var sig = buildHeaderSig(headerCells);
    table.__aps_colresize_sig = sig;

    var minWByCol = computeMinWByCol(headerCells, logicalColCount);

    // measure default widths before injecting handles / colgroup
    var defaultWidths = measureDefaultWidths(headerCells, logicalColCount);
    var defaultSan = sanitizeWidthArray(defaultWidths, logicalColCount, minWByCol);
    if (defaultSan) {
      defaultWidths = defaultSan;
    }
    table.__aps_colresize_default_widths = defaultWidths;

    // load persisted widths if sig matches
    var widthsToApply = defaultWidths;
    if (persistKey) {
      var saved = safeJsonParse(lsGet(persistKey) || "");
      if (saved && saved.v === 1 && saved.sig === sig && saved.widths) {
        var sanitized = sanitizeWidthArray(saved.widths, logicalColCount, minWByCol);
        if (sanitized) {
          widthsToApply = sanitized;
        }
      }
    } else {
      try {
        if (window.console && console.warn) {
          console.warn("[APS] table resize skipped persistence: missing table id/data-table-key", table);
        }
      } catch (_e0) {}
    }

    try {
      if (table && table.classList) {
        table.classList.add("table-layout-fixed");
      }
    } catch (_e2) {}

    var colgroup = ensureColgroup(table, logicalColCount);
    // enforce fixed layout for predictable resizing (even if template didn't set table-layout-fixed)
    table.style.tableLayout = "fixed";
    applyColWidths(colgroup, widthsToApply);

    insertTableToolsOnce(table);
    installHandles(table, headerCells, logicalColCount);
  }

  function initAll() {
    try {
      initDensity();
    } catch (_e0) {}

    try {
      if (!window.__aps_colresize_global_bound) {
        window.__aps_colresize_global_bound = 1;
        if (window.addEventListener) {
          window.addEventListener("blur", onWindowBlur, true);
        }
        if (document && document.addEventListener) {
          document.addEventListener("visibilitychange", onVisibilityChange, true);
        }
      }
    } catch (_e1) {}

    var tables = document.querySelectorAll('table[data-col-resize="1"]');
    for (var i = 0; i < tables.length; i++) {
      try {
        initOneTable(tables[i]);
      } catch (_e1) {}
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initAll);
  } else {
    initAll();
  }
})();

