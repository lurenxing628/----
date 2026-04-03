(function () {
  var ns = window.__APS_GANTT__ || {};
  window.__APS_GANTT__ = ns;
  if (!ns._inited) ns._inited = {};
  if (ns._inited.core) return;
  ns._inited.core = true;

  function $(id) {
    return document.getElementById(id);
  }

  function on(el, evt, fn) {
    if (!el) return;
    el.addEventListener(evt, fn);
  }

  function show(el, visible) {
    if (!el) return;
    if (el.classList) {
      el.classList.toggle("is-hidden", !visible);
    }
    el.style.display = visible ? "block" : "none";
  }

  function str(v) {
    return v === null || typeof v === "undefined" ? "" : String(v);
  }

  function escapeHtml(v) {
    const s = str(v);
    if (!s) return "";
    // Fast path: nothing to escape
    if (!/[&<>"']/.test(s)) return s;
    return s
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function norm(v) {
    return str(v).trim();
  }

  function parsePositiveInt(v, fallback) {
    var n = Number(v);
    if (!isFinite(n)) return fallback;
    n = Math.floor(n);
    if (n <= 0) return fallback;
    return n;
  }

  function includesI(hay, needle) {
    const h = norm(hay).toLowerCase();
    const n = norm(needle).toLowerCase();
    if (!n) return true;
    return h.indexOf(n) >= 0;
  }

  function hasSelectOption(el, value) {
    if (!el || !el.options) return false;
    const target = norm(value);
    for (let i = 0; i < el.options.length; i++) {
      if (norm(el.options[i].value) === target) return true;
    }
    return false;
  }

  function appendSelectOption(el, value, label) {
    if (!el) return;
    const opt = document.createElement("option");
    opt.value = norm(value);
    opt.textContent = norm(label) || norm(value);
    el.appendChild(opt);
  }

  function setSelectValueWithFallback(el, value, fallbackPrefix) {
    if (!el) return;
    const v = norm(value);
    if (!v) {
      el.value = "";
      return;
    }
    if (!hasSelectOption(el, v)) {
      const prefix = norm(fallbackPrefix) || "按值筛选";
      appendSelectOption(el, v, `${prefix}：${v}`);
    }
    el.value = v;
  }

  function replaceSelectOptions(el, options, defaultLabel) {
    if (!el) return;
    if (!el.options || el.options.length <= 0) {
      appendSelectOption(el, "", defaultLabel || "全部");
    } else {
      el.options[0].value = "";
      el.options[0].textContent = defaultLabel || "全部";
    }
    while (el.options.length > 1) {
      el.remove(1);
    }
    const list = Array.isArray(options) ? options : [];
    for (let i = 0; i < list.length; i++) {
      const item = list[i] || {};
      const value = norm(item.value);
      if (!value) continue;
      const label = norm(item.label) || value;
      appendSelectOption(el, value, label);
    }
  }

  function sortOptionItems(items) {
    const list = Array.isArray(items) ? items.slice() : [];
    list.sort((a, b) => {
      const la = norm(a && a.label).toLowerCase();
      const lb = norm(b && b.label).toLowerCase();
      if (la === lb) {
        return norm(a && a.value).toLowerCase().localeCompare(norm(b && b.value).toLowerCase());
      }
      return la.localeCompare(lb);
    });
    return list;
  }

  function addFilterOption(m, value, label) {
    if (!m) return;
    const v = norm(value);
    if (!v) return;
    if (!m.has(v)) {
      m.set(v, { value: v, label: norm(label) || v });
    }
  }

  function collectFilterOptions(tasks, view) {
    const batchMap = new Map();
    const resourceMap = new Map();
    const list = Array.isArray(tasks) ? tasks : [];
    const useView = norm(view) || "machine";

    for (let i = 0; i < list.length; i++) {
      const t = list[i] || {};
      const meta = t.meta || {};
      const batchId = norm(meta.batch_id);
      addFilterOption(batchMap, batchId, batchId);

      if (useView === "machine") {
        const machineId = norm(meta.machine_id);
        const machineName = norm(meta.machine);
        const value = machineId || machineName;
        const label = machineId && machineName && machineName !== machineId
          ? `${machineId} ${machineName}`
          : (machineName || machineId);
        addFilterOption(resourceMap, value, label);
      } else {
        const operatorId = norm(meta.operator_id);
        const operatorName = norm(meta.operator);
        const value = operatorId || operatorName;
        const label = operatorId && operatorName && operatorName !== operatorId
          ? `${operatorId} ${operatorName}`
          : (operatorName || operatorId);
        addFilterOption(resourceMap, value, label);
      }
    }

    return {
      batchOptions: sortOptionItems(Array.from(batchMap.values())),
      resourceOptions: sortOptionItems(Array.from(resourceMap.values())),
    };
  }

  function refreshFilterSelectOptions() {
    const cfg = state.cfg || {};
    const view = norm(cfg.view) || "machine";
    const batchEl = $("ganttFilterBatch");
    const resourceEl = $("ganttFilterResource");
    const selectedBatch = norm(batchEl && batchEl.value);
    const selectedResource = norm(resourceEl && resourceEl.value);

    const opts = collectFilterOptions(state.allTasks, view);
    replaceSelectOptions(batchEl, opts.batchOptions, "全部批次");
    replaceSelectOptions(resourceEl, opts.resourceOptions, view === "machine" ? "全部设备" : "全部人员");

    if (selectedBatch) {
      setSelectValueWithFallback(batchEl, selectedBatch, "批次");
    }
    if (selectedResource) {
      setSelectValueWithFallback(resourceEl, selectedResource, view === "machine" ? "设备" : "人员");
    }
  }

  const state = {
    cfg: null,
    allTasks: [],
    filteredTasks: [],
    currentTasks: [],
    gantt: null,
    focusBatch: "",
    critical: { ids: [], edges: [], makespan_end: null },
    ccIdSet: new Set(),
    ccPrevByTo: new Map(),
    ccEdgeMetaByTo: new Map(),
    calendarDays: [],
    overdueMarkersDegraded: false,
    overdueMarkersPartial: false,
    overdueMarkersMessage: "",
    // 默认：按批次配色；高亮关键链；仅显示关键链箭头（避免全图箭头过密）
    ui: {
      viewMode: "Day",
      colorMode: "batch",
      filterBatch: "",
      filterResource: "",
      onlyOverdue: false,
      onlyExternal: false,
      depsMode: "critical", // critical / process / none
      highlightCC: true,
    },
  };

  const _perfState = {
    holidayDigest: "",
    holidayLayerMounted: false,
    lastHolidayHeight: 0,
    wrappersById: new Map(),
    decorateRenderedIds: [],
    legendDigest: "",
    ccVisibleCount: 0,
    activeRequestId: 0,
    inFlightController: null,
    inFlightUrl: "",
  };

  ns.$ = $;
  ns.on = on;
  ns.show = show;
  ns.str = str;
  ns.escapeHtml = escapeHtml;
  ns.norm = norm;
  ns.parsePositiveInt = parsePositiveInt;
  ns.includesI = includesI;
  ns.hasSelectOption = hasSelectOption;
  ns.appendSelectOption = appendSelectOption;
  ns.setSelectValueWithFallback = setSelectValueWithFallback;
  ns.replaceSelectOptions = replaceSelectOptions;
  ns.sortOptionItems = sortOptionItems;
  ns.collectFilterOptions = collectFilterOptions;
  ns.refreshFilterSelectOptions = refreshFilterSelectOptions;
  ns.state = state;
  ns._perfState = _perfState;
})();

