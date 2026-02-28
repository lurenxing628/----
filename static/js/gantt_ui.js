(function () {
  var ns = window.__APS_GANTT__;
  if (!ns) return;
  if (!ns._inited) ns._inited = {};
  if (ns._inited.ui) return;
  ns._inited.ui = true;

  var $ = ns.$;
  var on = ns.on;
  var norm = ns.norm;
  var setSelectValueWithFallback = ns.setSelectValueWithFallback;
  var state = ns.state;
  var safeDecorateDynamic = ns.safeDecorateDynamic;
  var render = ns.render;

  if (typeof $ !== "function") return;
  if (typeof on !== "function") return;
  if (typeof norm !== "function") return;
  if (typeof setSelectValueWithFallback !== "function") return;
  if (!state) return;
  if (typeof safeDecorateDynamic !== "function") return;
  if (typeof render !== "function") return;

  function readUi() {
    const viewModeRaw = norm($("ganttViewMode") && $("ganttViewMode").value) || "Day";
    state.ui.viewMode = (viewModeRaw === "Week" || viewModeRaw === "Month") ? viewModeRaw : "Day";
    state.ui.colorMode = norm($("ganttColorMode") && $("ganttColorMode").value) || "batch";
    state.ui.filterBatch = norm($("ganttFilterBatch") && $("ganttFilterBatch").value);
    state.ui.filterResource = norm($("ganttFilterResource") && $("ganttFilterResource").value);
    state.ui.onlyOverdue = !!($("ganttOnlyOverdue") && $("ganttOnlyOverdue").checked);
    state.ui.onlyExternal = !!($("ganttOnlyExternal") && $("ganttOnlyExternal").checked);
    const depsModeRaw = norm($("ganttDepsMode") && $("ganttDepsMode").value) || "critical";
    state.ui.depsMode = (depsModeRaw === "none" || depsModeRaw === "process" || depsModeRaw === "critical")
      ? depsModeRaw
      : "critical";
    state.ui.highlightCC = !!($("ganttHighlightCC") && $("ganttHighlightCC").checked);
  }

  function parseBoolQuery(raw, fallback) {
    if (typeof raw !== "string") return !!fallback;
    const v = raw.trim().toLowerCase();
    if (v === "1" || v === "true" || v === "yes" || v === "on") return true;
    if (v === "0" || v === "false" || v === "no" || v === "off") return false;
    return !!fallback;
  }

  function applyUiFromUrl() {
    let params;
    try {
      params = new URL(window.location.href).searchParams;
    } catch (_) {
      return;
    }
    const vm = params.get("gantt_vm") || params.get("view_mode");
    if (vm) {
      const el = $("ganttViewMode");
      if (el && (vm === "Day" || vm === "Week" || vm === "Month")) el.value = vm;
    }
    const cm = params.get("gantt_color");
    if (cm) {
      const el = $("ganttColorMode");
      if (el) el.value = cm;
    }
    const fb = params.get("gantt_batch");
    if (fb !== null) {
      const el = $("ganttFilterBatch");
      if (el) setSelectValueWithFallback(el, fb, "批次");
    }
    const fr = params.get("gantt_resource");
    if (fr !== null) {
      const el = $("ganttFilterResource");
      if (el) setSelectValueWithFallback(el, fr, "资源");
    }
    const oo = params.get("gantt_overdue");
    if (oo !== null) {
      const el = $("ganttOnlyOverdue");
      if (el) el.checked = parseBoolQuery(oo, false);
    }
    const oe = params.get("gantt_external");
    if (oe !== null) {
      const el = $("ganttOnlyExternal");
      if (el) el.checked = parseBoolQuery(oe, false);
    }
    const deps = params.get("gantt_deps");
    if (deps) {
      const el = $("ganttDepsMode");
      if (el && (deps === "none" || deps === "process" || deps === "critical")) el.value = deps;
    }
    const hc = params.get("gantt_hcc");
    if (hc !== null) {
      const el = $("ganttHighlightCC");
      if (el) el.checked = parseBoolQuery(hc, true);
    }
  }

  function persistUiToUrl() {
    let url;
    try {
      url = new URL(window.location.href);
    } catch (_) {
      return;
    }
    const ui = state.ui || {};
    const setOrDelete = function (key, val, isDefault) {
      if (isDefault) url.searchParams.delete(key);
      else url.searchParams.set(key, String(val));
    };
    setOrDelete("gantt_vm", ui.viewMode || "Day", !ui.viewMode || ui.viewMode === "Day");
    setOrDelete("gantt_color", ui.colorMode || "batch", !ui.colorMode || ui.colorMode === "batch");
    setOrDelete("gantt_batch", ui.filterBatch || "", !ui.filterBatch);
    setOrDelete("gantt_resource", ui.filterResource || "", !ui.filterResource);
    setOrDelete("gantt_overdue", ui.onlyOverdue ? "1" : "0", !ui.onlyOverdue);
    setOrDelete("gantt_external", ui.onlyExternal ? "1" : "0", !ui.onlyExternal);
    setOrDelete("gantt_deps", ui.depsMode || "critical", !ui.depsMode || ui.depsMode === "critical");
    setOrDelete("gantt_hcc", ui.highlightCC ? "1" : "0", !!ui.highlightCC);
    try {
      window.history.replaceState(null, "", url.toString());
    } catch (_) {
      // ignore
    }
  }

  function bindUi() {
    // 防御：避免重复绑定事件
    if (bindUi._bound === true) return;
    bindUi._bound = true;

    const resetBtn = $("ganttResetView");
    if (resetBtn) {
      on(resetBtn, "click", function () {
        state.focusBatch = "";

        const vm = $("ganttViewMode");
        if (vm) vm.value = "Day";
        const cm = $("ganttColorMode");
        if (cm) cm.value = "batch";
        const fb = $("ganttFilterBatch");
        if (fb) fb.value = "";
        const fr = $("ganttFilterResource");
        if (fr) fr.value = "";

        const oo = $("ganttOnlyOverdue");
        if (oo) oo.checked = false;
        const oe = $("ganttOnlyExternal");
        if (oe) oe.checked = false;
        const dm = $("ganttDepsMode");
        if (dm) dm.value = "critical";
        const hc = $("ganttHighlightCC");
        if (hc) hc.checked = true;

        readUi();
        persistUiToUrl();
        render();
      });
    }

    let timerFull = 0;
    let timerDecor = 0;

    function scheduleFullRender() {
      if (timerFull) clearTimeout(timerFull);
      timerFull = setTimeout(function () {
        readUi();
        persistUiToUrl();
        render();
      }, 240);
    }

    function scheduleDecorate() {
      if (timerDecor) clearTimeout(timerDecor);
      timerDecor = setTimeout(function () {
        readUi();
        persistUiToUrl();
        safeDecorateDynamic({ updateLegend: true });
      }, 60);
    }

    // 纯视觉类：不重建 Gantt
    ["ganttColorMode", "ganttHighlightCC"].forEach((id) => {
      const el = $(id);
      if (el) on(el, "change", scheduleDecorate);
    });

    // 数据集合/依赖类：必须全量 render
    ["ganttViewMode", "ganttOnlyOverdue", "ganttOnlyExternal", "ganttDepsMode"].forEach((id) => {
      const el = $(id);
      if (el) on(el, "change", scheduleFullRender);
    });
    ["ganttFilterBatch", "ganttFilterResource"].forEach((id) => {
      const el = $(id);
      if (!el) return;
      on(el, "change", scheduleFullRender);
      // 兼容历史 input 控件（降级场景）
      on(el, "input", scheduleFullRender);
    });
  }

  ns.readUi = readUi;
  ns.applyUiFromUrl = applyUiFromUrl;
  ns.persistUiToUrl = persistUiToUrl;
  ns.bindUi = bindUi;
})();

