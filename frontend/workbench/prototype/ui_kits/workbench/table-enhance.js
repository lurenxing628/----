/* APS Workbench · table-enhance.js
 * Progressive enhancer for the plana-native plain-DOM tables (`.plana table.tbl`).
 * Adds click-to-sort, per-column filter, and column resize — matching the
 * React <Table> tools visually (shared `aps-*` classes). React-managed tables
 * carry data-aps-rtable and have their own logic, so they are never touched.
 *
 * plana-logic.js repaints its root via innerHTML, replacing table nodes; a
 * MutationObserver re-enhances any fresh `.tbl` (sort/filter state resets with
 * the repaint, which is expected).
 */
(function () {
  "use strict";

  var CSS_ID = "aps-table-tools-css";
  var SHARED_CSS = [
    ".aps-th{position:relative}",
    ".aps-th-inner{display:inline-flex;align-items:center;gap:6px;max-width:100%}",
    ".aps-th-sortable{cursor:pointer}",
    ".aps-th-label{overflow:hidden;text-overflow:ellipsis}",
    ".aps-sortglyph{display:inline-block;width:7px;height:13px;position:relative;color:currentColor;opacity:.3;transition:opacity .12s;flex:none}",
    ".aps-sortglyph::before,.aps-sortglyph::after{content:'';position:absolute;left:0;border-left:3.5px solid transparent;border-right:3.5px solid transparent}",
    ".aps-sortglyph::before{top:2px;border-bottom:4px solid currentColor}",
    ".aps-sortglyph::after{bottom:2px;border-top:4px solid currentColor}",
    ".aps-th:hover .aps-sortglyph{opacity:.55}",
    ".aps-sortglyph.asc,.aps-sortglyph.desc{opacity:1}",
    ".aps-sortglyph.asc::after{opacity:.2}",
    ".aps-sortglyph.desc::before{opacity:.2}",
    ".aps-filter-btn{display:inline-flex;align-items:center;justify-content:center;width:18px;height:18px;border:0;background:transparent;border-radius:4px;cursor:pointer;color:inherit;opacity:0;padding:0;flex:none;transition:opacity .12s,background-color .12s,color .12s}",
    ".aps-th:hover .aps-filter-btn{opacity:.55}",
    ".aps-filter-btn:hover{background:var(--ui-surface-muted);opacity:1}",
    ".aps-filter-btn.on{opacity:1;color:var(--ui-primary);background:var(--ui-primary-soft)}",
    ".aps-th-resize{position:absolute;top:0;right:0;height:100%;width:10px;cursor:col-resize;user-select:none;touch-action:none;z-index:4}",
    ".aps-th-resize::after{content:'';position:absolute;right:3px;top:22%;height:56%;width:2px;border-radius:2px;background:transparent;transition:background-color .12s}",
    ".aps-th-resize:hover::after,.aps-th-resize.dragging::after{background:var(--ui-primary)}",
    ".aps-filter-pop{position:fixed;z-index:9999;background:var(--ui-card-bg);border:1px solid var(--ui-border);border-radius:8px;box-shadow:var(--ui-shadow-md);padding:8px;width:240px;box-sizing:border-box}",
    ".aps-filter-pop input[type=checkbox]{width:15px;height:15px;flex:none;margin:0;padding:0;accent-color:var(--ui-primary);cursor:pointer}",
    ".aps-fp-list{max-height:220px;overflow:auto;margin-top:7px;display:flex;flex-direction:column;gap:1px;border-top:1px solid var(--ui-border);padding-top:6px}",
    ".aps-fp-opt{display:flex;align-items:center;gap:8px;padding:5px 6px;border-radius:5px;cursor:pointer;font-size:13px;color:var(--ui-text);user-select:none}",
    ".aps-fp-opt:hover{background:var(--ui-surface-muted)}",
    ".aps-fp-opt-label{flex:1 1 auto;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}",
    ".aps-fp-opt-count{flex:none;color:var(--ui-muted);font-size:11.5px;font-variant-numeric:tabular-nums}",
    ".aps-fp-all{font-weight:600;border-bottom:1px solid var(--ui-border);border-radius:0;margin-bottom:2px;padding-bottom:7px}",
    ".aps-fp-empty{padding:14px 6px;text-align:center;color:var(--ui-muted);font-size:12px}",
    ".aps-filter-pop input{width:100%;height:32px;padding:0 10px;border:1px solid var(--ui-border);border-radius:6px;background:var(--ui-card-bg);font-family:inherit;font-size:13px;color:var(--ui-text);box-sizing:border-box}",
    ".aps-filter-pop input:focus{outline:none;border-color:var(--ui-primary);box-shadow:var(--ui-focus-ring)}",
    ".aps-fp-foot{display:flex;justify-content:space-between;align-items:center;margin-top:7px}",
    ".aps-fp-clear{border:0;background:transparent;color:var(--ui-muted);font-size:12px;cursor:pointer;font-family:inherit;padding:2px 4px;border-radius:4px}",
    ".aps-fp-clear:hover{color:var(--ui-text);background:var(--ui-surface-muted)}",
    ".aps-fp-count{font-size:11.5px;color:var(--ui-muted);font-variant-numeric:tabular-nums}",
    /* plana th: defeat the scoped overflow:hidden + give a positioning context */
    ".plana table.tbl th.aps-th{overflow:visible;position:relative}",
  ].join("");

  function injectCSS() {
    if (document.getElementById(CSS_ID)) return;
    var el = document.createElement("style");
    el.id = CSS_ID;
    el.textContent = SHARED_CSS;
    document.head.appendChild(el);
  }

  var FUNNEL_SVG =
    '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 5h18l-7 8v5l-4 2v-7z"/></svg>';

  function cmpVals(a, b) {
    var sa = a == null ? "" : String(a);
    var sb = b == null ? "" : String(b);
    return sa.localeCompare(sb, "zh-Hans-CN", { numeric: true, sensitivity: "base" });
  }
  function cellText(tr, idx) {
    var c = tr.cells[idx];
    return c ? (c.textContent || "").trim() : "";
  }

  // ---- single shared filter popover ----
  var CURRENT_POP = null;
  function closePop() {
    if (CURRENT_POP && CURRENT_POP.parentNode) CURRENT_POP.parentNode.removeChild(CURRENT_POP);
    CURRENT_POP = null;
  }
  document.addEventListener("mousedown", function (e) {
    if (!CURRENT_POP) return;
    if (e.target.closest("[data-aps-fpop]") || e.target.closest("[data-aps-fbtn]")) return;
    closePop();
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") closePop();
  });
  window.addEventListener("scroll", closePop, true);

  function dataRowsOf(table) {
    return (table.__apsOrig || []).filter(function (tr) {
      return tr.parentNode && tr.parentNode.tagName === "TBODY" && tr.closest("table") === table;
    });
  }
  function visibleCount(table) {
    return dataRowsOf(table).filter(function (tr) {
      return tr.style.display !== "none";
    }).length;
  }
  function applyFilters(table) {
    var f = table.__apsFilters || {};
    var entries = Object.keys(f)
      .map(function (k) {
        return [parseInt(k, 10), f[k]];
      })
      .filter(function (e) {
        return Array.isArray(e[1]);
      });
    dataRowsOf(table).forEach(function (tr) {
      var ok = entries.every(function (e) {
        return e[1].indexOf(cellText(tr, e[0])) !== -1;
      });
      tr.style.display = ok ? "" : "none";
    });
  }
  function distinctForCol(table, idx) {
    var m = {};
    var order = [];
    (table.__apsOrig || []).forEach(function (tr) {
      var t = cellText(tr, idx);
      if (!Object.prototype.hasOwnProperty.call(m, t)) {
        m[t] = 0;
        order.push(t);
      }
      m[t] += 1;
    });
    order.sort(cmpVals);
    return order.map(function (v) {
      return { value: v, count: m[v] };
    });
  }
  function applyOrder(table) {
    var tbody = table.tBodies[0];
    if (!tbody) return;
    var s = table.__apsSort;
    var order = (table.__apsOrig || []).slice();
    if (s) {
      order.sort(function (a, b) {
        return cmpVals(cellText(a, s.idx), cellText(b, s.idx));
      });
      if (s.dir === "desc") order.reverse();
    }
    order.forEach(function (tr) {
      tbody.appendChild(tr);
    });
  }
  function doSort(table, idx, glyph) {
    var cur = table.__apsSort;
    var dir;
    if (!cur || cur.idx !== idx) dir = "asc";
    else if (cur.dir === "asc") dir = "desc";
    else dir = null;
    table.__apsSort = dir ? { idx: idx, dir: dir } : null;
    var glyphs = table.querySelectorAll(".aps-sortglyph");
    for (var i = 0; i < glyphs.length; i++) glyphs[i].classList.remove("asc", "desc");
    if (dir) glyph.classList.add(dir);
    applyOrder(table);
  }
  function openPop(table, idx, btn) {
    closePop();
    var options = distinctForCol(table, idx);
    var allValues = options.map(function (o) {
      return o.value;
    });
    var current = table.__apsFilters[idx];
    var checkedSet = {};
    (current || allValues).forEach(function (v) {
      checkedSet[v] = true;
    });
    function checkedCount() {
      return Object.keys(checkedSet).length;
    }

    var pop = document.createElement("div");
    pop.className = "aps-filter-pop";
    pop.setAttribute("data-aps-fpop", "1");

    var th = btn.closest("th");
    var lbl = th && th.querySelector(".aps-th-label");
    var title = lbl ? lbl.textContent.trim() : "本列";

    var search = document.createElement("input");
    search.type = "text";
    search.placeholder = "搜索 " + title + "…";
    var list = document.createElement("div");
    list.className = "aps-fp-list";
    var foot = document.createElement("div");
    foot.className = "aps-fp-foot";
    var count = document.createElement("span");
    count.className = "aps-fp-count";
    var clear = document.createElement("button");
    clear.type = "button";
    clear.className = "aps-fp-clear";
    clear.textContent = "清除";
    foot.appendChild(count);
    foot.appendChild(clear);
    pop.appendChild(search);
    pop.appendChild(list);
    pop.appendChild(foot);
    document.body.appendChild(pop);

    var r = btn.getBoundingClientRect();
    var w = 240;
    var left = r.left;
    if (left + w > window.innerWidth - 8) left = window.innerWidth - 8 - w;
    pop.style.left = Math.max(8, left) + "px";
    pop.style.top = r.bottom + 6 + "px";

    function labelOf(v) {
      return v === "" ? "(空白)" : v;
    }
    function commit() {
      if (checkedCount() >= allValues.length) {
        delete table.__apsFilters[idx];
        btn.classList.remove("on");
      } else {
        table.__apsFilters[idx] = Object.keys(checkedSet);
        btn.classList.add("on");
      }
      applyFilters(table);
      count.textContent = visibleCount(table) + " 行匹配";
    }
    function renderList() {
      var ql = search.value.trim().toLowerCase();
      var shown = ql
        ? options.filter(function (o) {
            return labelOf(o.value).toLowerCase().indexOf(ql) !== -1;
          })
        : options;
      var scroll = list.scrollTop;
      list.innerHTML = "";
      var shownChecked = shown.filter(function (o) {
        return checkedSet[o.value];
      }).length;
      var allOn = shown.length > 0 && shownChecked === shown.length;
      var someOn = shownChecked > 0 && shownChecked < shown.length;

      var allLab = document.createElement("label");
      allLab.className = "aps-fp-opt aps-fp-all";
      var allCk = document.createElement("input");
      allCk.type = "checkbox";
      allCk.checked = allOn;
      allCk.indeterminate = someOn;
      var allTxt = document.createElement("span");
      allTxt.className = "aps-fp-opt-label";
      allTxt.textContent = "(全选)";
      var allCnt = document.createElement("span");
      allCnt.className = "aps-fp-opt-count";
      allCnt.textContent = options.length;
      allLab.appendChild(allCk);
      allLab.appendChild(allTxt);
      allLab.appendChild(allCnt);
      allCk.addEventListener("change", function () {
        shown.forEach(function (o) {
          if (allOn) delete checkedSet[o.value];
          else checkedSet[o.value] = true;
        });
        commit();
        renderList();
      });
      list.appendChild(allLab);

      if (!shown.length) {
        var empty = document.createElement("div");
        empty.className = "aps-fp-empty";
        empty.textContent = "无匹配项";
        list.appendChild(empty);
      }
      shown.forEach(function (o) {
        var lab = document.createElement("label");
        lab.className = "aps-fp-opt";
        var ck = document.createElement("input");
        ck.type = "checkbox";
        ck.checked = !!checkedSet[o.value];
        ck.addEventListener("change", function () {
          if (ck.checked) checkedSet[o.value] = true;
          else delete checkedSet[o.value];
          commit();
          renderList();
        });
        var t = document.createElement("span");
        t.className = "aps-fp-opt-label";
        t.textContent = labelOf(o.value);
        t.title = labelOf(o.value);
        var c = document.createElement("span");
        c.className = "aps-fp-opt-count";
        c.textContent = o.count;
        lab.appendChild(ck);
        lab.appendChild(t);
        lab.appendChild(c);
        list.appendChild(lab);
      });
      list.scrollTop = scroll;
    }

    search.addEventListener("input", renderList);
    clear.addEventListener("click", function () {
      checkedSet = {};
      allValues.forEach(function (v) {
        checkedSet[v] = true;
      });
      commit();
      closePop();
    });
    renderList();
    count.textContent = visibleCount(table) + " 行匹配";
    CURRENT_POP = pop;
    setTimeout(function () {
      search.focus();
    }, 0);
  }
  function startResize(e, th, handle) {
    e.preventDefault();
    e.stopPropagation();
    var startX = e.clientX;
    var startW = th.getBoundingClientRect().width;
    handle.classList.add("dragging");
    function move(ev) {
      var w = Math.max(56, Math.round(startW + ev.clientX - startX));
      th.style.width = w + "px";
    }
    function up() {
      document.removeEventListener("mousemove", move);
      document.removeEventListener("mouseup", up);
      handle.classList.remove("dragging");
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    }
    document.addEventListener("mousemove", move);
    document.addEventListener("mouseup", up);
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
  }

  function enhanceTable(table) {
    if (table.__apsTx) return;
    table.__apsTx = true;
    var thead = table.tHead;
    var tbody = table.tBodies[0];
    if (!thead || !thead.rows[0] || !tbody) return;
    var ths = Array.prototype.slice.call(thead.rows[0].cells);
    var bodyRows = Array.prototype.slice.call(tbody.rows);
    var isDataRow = function (tr) {
      return tr.cells.length === ths.length && !tr.querySelector("td[colspan]");
    };
    table.__apsOrig = bodyRows.filter(isDataRow);
    table.__apsFilters = {};
    table.__apsSort = null;

    ths.forEach(function (th, idx) {
      if (th.classList.contains("cbx")) return;
      var colCells = table.__apsOrig.map(function (tr) {
        return tr.cells[idx];
      });
      var isAction = colCells.some(function (td) {
        return td && (td.classList.contains("actcol") || td.querySelector(".rowact, button"));
      });

      th.classList.add("aps-th");
      var inner = document.createElement("span");
      inner.className = "aps-th-inner";
      var label = document.createElement("span");
      label.className = "aps-th-label";
      while (th.firstChild) label.appendChild(th.firstChild);
      inner.appendChild(label);
      if (th.classList.contains("r")) inner.style.justifyContent = "flex-end";
      th.appendChild(inner);

      if (!isAction) {
        inner.classList.add("aps-th-sortable");
        var glyph = document.createElement("span");
        glyph.className = "aps-sortglyph";
        inner.appendChild(glyph);
        var fbtn = document.createElement("button");
        fbtn.type = "button";
        fbtn.className = "aps-filter-btn";
        fbtn.setAttribute("data-aps-fbtn", "1");
        fbtn.title = "筛选";
        fbtn.innerHTML = FUNNEL_SVG;
        inner.appendChild(fbtn);
        inner.addEventListener("click", function (e) {
          if (e.target.closest("[data-aps-fbtn]")) return;
          doSort(table, idx, glyph);
        });
        fbtn.addEventListener("click", function (e) {
          e.stopPropagation();
          openPop(table, idx, fbtn);
        });
      }

      var rh = document.createElement("span");
      rh.className = "aps-th-resize";
      rh.addEventListener("mousedown", function (e) {
        startResize(e, th, rh);
      });
      th.appendChild(rh);
    });
  }

  function scan() {
    var tables = document.querySelectorAll(".plana table.tbl");
    for (var i = 0; i < tables.length; i++) {
      var t = tables[i];
      if (t.hasAttribute("data-aps-rtable")) continue;
      try {
        enhanceTable(t);
      } catch (err) {
        /* never let one table break the page */
        // eslint-disable-next-line no-console
        console.warn("table-enhance: skip", err);
      }
    }
  }

  var scheduled = false;
  function schedule() {
    if (scheduled) return;
    scheduled = true;
    setTimeout(function () {
      scheduled = false;
      injectCSS();
      scan();
    }, 30);
  }

  function init() {
    injectCSS();
    scan();
    var obs = new MutationObserver(function (records) {
      for (var i = 0; i < records.length; i++) {
        if (records[i].addedNodes && records[i].addedNodes.length) {
          schedule();
          return;
        }
      }
    });
    obs.observe(document.body, { childList: true, subtree: true });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
