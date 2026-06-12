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
  var zoom = ns.zoom;
  var show = ns.show;

  if (typeof $ !== "function") return;
  if (typeof on !== "function") return;
  if (typeof norm !== "function") return;
  if (typeof setSelectValueWithFallback !== "function") return;
  if (!state) return;
  if (typeof safeDecorateDynamic !== "function") return;
  if (typeof render !== "function") return;
  if (!zoom || typeof zoom.normalizeZoomLevel !== "function" || typeof zoom.getZoomSpec !== "function") return;

  function setZoomWarning(message) {
    const el = $("ganttZoomWarning");
    if (!el) return;
    el.textContent = message || "";
    if (typeof show === "function") {
      show(el, !!message);
    }
  }

  function setUrlZoomWarning(message) {
    state.ui.zoomWarningMessage = message || "";
    setZoomWarning(state.ui.zoomWarningMessage);
  }

  function syncZoomCarriers(level) {
    const normalized = zoom.normalizeZoomLevel(level || "day");
    const hidden = $("ganttZoomFormValue");
    if (hidden) hidden.value = normalized;

    document.querySelectorAll("a").forEach(function (link) {
      let url;
      try {
        url = new URL(link.getAttribute("href") || "", window.location.origin);
      } catch (_) {
        return;
      }
      if (url.pathname !== "/scheduler/gantt") return;
      if (normalized === "day") {
        url.searchParams.delete("gantt_zoom");
      } else {
        url.searchParams.set("gantt_zoom", normalized);
      }
      link.setAttribute("href", url.pathname + url.search + url.hash);
    });
  }

  function syncGanttScopeCarriers() {
    const ui = state.ui || {};
    const batch = norm(ui.filterBatch || "");
    const resource = norm(ui.filterResource || "");
    const currentView = norm((state.cfg && state.cfg.view) || "");

    document.querySelectorAll("form.aps-gantt-range-form").forEach(function (form) {
      setHiddenField(form, "gantt_batch", batch);
      setHiddenField(form, "gantt_resource", resource);
    });

    document.querySelectorAll("a").forEach(function (link) {
      let url;
      try {
        url = new URL(link.getAttribute("href") || "", window.location.origin);
      } catch (_) {
        return;
      }
      if (url.pathname !== "/scheduler/gantt") return;
      const targetView = norm(url.searchParams.get("view") || currentView);
      if (batch) url.searchParams.set("gantt_batch", batch);
      else url.searchParams.delete("gantt_batch");
      if (resource && (!targetView || targetView === currentView)) {
        url.searchParams.set("gantt_resource", resource);
      } else {
        url.searchParams.delete("gantt_resource");
      }
      link.setAttribute("href", url.pathname + url.search + url.hash);
    });
  }

  function findHiddenField(form, name) {
    const inputs = form.querySelectorAll("input");
    for (let index = 0; index < inputs.length; index += 1) {
      if (inputs[index].getAttribute("name") === name) return inputs[index];
    }
    return null;
  }

  function setHiddenField(form, name, value) {
    let input = findHiddenField(form, name);
    if (!value) {
      if (input) input.remove();
      return;
    }
    if (!input) {
      input = document.createElement("input");
      input.setAttribute("type", "hidden");
      input.setAttribute("name", name);
      form.appendChild(input);
    }
    input.value = value;
  }

  function zoomControl() {
    return $("ganttZoomLevel") || $("ganttViewMode");
  }

  // ± 步进的档位序 = select option 顺序（与 gantt.html 9 档一致），
  // 不在 JS 里手抄第二份档位表
  function zoomLevelOrder(select) {
    const out = [];
    if (!select || !select.options) return out;
    for (let i = 0; i < select.options.length; i++) {
      out.push(String(select.options[i].value));
    }
    return out;
  }

  function refreshZoomStepperState() {
    const select = $("ganttZoomLevel");
    const minus = $("ganttZoomOut");
    const plus = $("ganttZoomIn");
    if (!select || !minus || !plus) return;
    const order = zoomLevelOrder(select);
    const idx = order.indexOf(String(select.value));
    minus.disabled = idx <= 0;
    plus.disabled = idx < 0 || idx >= order.length - 1;
  }

  function bindZoomSteppers() {
    const select = $("ganttZoomLevel");
    const minus = $("ganttZoomOut");
    const plus = $("ganttZoomIn");
    if (!select || !minus || !plus) return;
    function step(delta) {
      const order = zoomLevelOrder(select);
      const idx = order.indexOf(String(select.value));
      const next = idx + delta;
      if (idx < 0 || next < 0 || next >= order.length) return;
      select.value = order[next];
      refreshZoomStepperState();
      // 复用 select 的 change 通路（debounce 全量 render + URL 持久化）
      try {
        select.dispatchEvent(new Event("change", { bubbles: true }));
      } catch (_) {
        // 旧环境 Event 构造不可用：直接走与 change 等效的渲染调度
        setUrlZoomWarning("");
        readUi();
        persistUiToUrl();
        render();
      }
    }
    on(minus, "click", function () { step(-1); });
    on(plus, "click", function () { step(1); });
    on(select, "change", refreshZoomStepperState);
    refreshZoomStepperState();
  }

  function legacyViewModeToZoom(value) {
    return zoom.normalizeZoomLevel(value || "day");
  }

  function applyZoomToState(rawValue) {
    const level = zoom.normalizeZoomLevel(rawValue || (state.ui && state.ui.zoomLevel) || "day");
    const spec = zoom.getZoomSpec(level);
    state.ui.zoomLevel = level;
    state.ui.viewMode = spec.frappeViewMode || "Day";
    syncZoomCarriers(level);
    return level;
  }

  function readUi() {
    const zoomRaw = norm(zoomControl() && zoomControl().value) || "day";
    applyZoomToState(zoomRaw);
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
    const zoomParam = params.get("gantt_zoom");
    const legacyVm = params.get("gantt_vm") || params.get("view_mode");
    let level = "";
    if (zoomParam || legacyVm) {
      level = zoomParam ? zoom.normalizeZoomLevel(zoomParam) : legacyViewModeToZoom(legacyVm || "");
      const isKnown = !zoomParam || typeof zoom.isKnownZoomLevel !== "function" || zoom.isKnownZoomLevel(zoomParam);
      setUrlZoomWarning(isKnown ? "" : "链接里的时间粒度无法识别，已切回日视图。");
    } else {
      level = applyZoomToState((state.ui && state.ui.zoomLevel) || "day");
      setUrlZoomWarning("");
    }
    const zoomEl = zoomControl();
    if (zoomEl) zoomEl.value = level;
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
    const level = zoom.normalizeZoomLevel(ui.zoomLevel || ui.viewMode || "day");
    setOrDelete("gantt_zoom", level, level === "day");
    url.searchParams.delete("gantt_vm");
    url.searchParams.delete("view_mode");
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
    syncGanttScopeCarriers();
  }

  function bindUi() {
    // 防御：避免重复绑定事件
    if (bindUi._bound === true) return;
    bindUi._bound = true;

    const clearFocusBtn = $("ganttClearFocus");
    if (clearFocusBtn) {
      on(clearFocusBtn, "click", function () {
        // 仅清批次聚焦（fusion-chain-walk-navigation）：onClick 改幂等赋值后，
        // 这里是不重置缩放/筛选的唯一窄清聚焦入口
        state.focusBatch = "";
        if (typeof ns.safeDecorateDynamic === "function") ns.safeDecorateDynamic({ updateLegend: false });
      });
    }

    const resetBtn = $("ganttResetView");
    if (resetBtn) {
      on(resetBtn, "click", function () {
        state.focusBatch = "";

        const vm = zoomControl();
        if (vm) vm.value = "day";
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

        refreshZoomStepperState(); // 重置回 day 后 ± 端点 disabled 态同步
        setUrlZoomWarning("");
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
        setUrlZoomWarning("");
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
    ["ganttZoomLevel", "ganttViewMode", "ganttOnlyOverdue", "ganttOnlyExternal", "ganttDepsMode"].forEach((id) => {
      const el = $(id);
      if (el) on(el, "change", scheduleFullRender);
    });

    // zoom ± 步进：沿 ZOOM_SPECS 有序档位 ±1，写 select.value 后走同一 change 通路
    bindZoomSteppers();

    // 解码条批次 chips（点击即筛选）
    if (typeof ns.bindLegendChips === "function") ns.bindLegendChips();
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
