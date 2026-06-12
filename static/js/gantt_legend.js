(function () {
  var ns = window.__APS_GANTT__;
  if (!ns) return;
  if (!ns._inited) ns._inited = {};
  if (ns._inited.legend) return;
  ns._inited.legend = true;

  var $ = ns.$;
  var norm = ns.norm;
  var state = ns.state;
  var _perfState = ns._perfState;
  var colorForBatch = ns.colorForBatch;
  var colorForPriority = ns.colorForPriority;
  var colorForSource = ns.colorForSource;
  var colorForStatusKey = ns.colorForStatusKey;
  var contractApi = ns.contract;
  var zoomApi = ns.zoom;

  if (typeof $ !== "function") return;
  if (typeof norm !== "function") return;
  if (!state || !_perfState || !contractApi || !zoomApi) return;
  if (typeof colorForBatch !== "function") return;
  if (typeof colorForPriority !== "function") return;
  if (typeof colorForSource !== "function") return;
  if (typeof colorForStatusKey !== "function") return;

  var getArrowModeLabel = contractApi.getArrowModeLabel;
  var getCriticalStatusLabel = contractApi.getCriticalStatusLabel;
  var shouldUseFallbackCalendarDays = contractApi.shouldUseFallbackCalendarDays;
  var formatChineseDateTime = contractApi.formatChineseDateTime;
  var getZoomSpec = zoomApi.getZoomSpec;
  var currentZoomLevel = zoomApi.currentZoomLevel;

  if (typeof getArrowModeLabel !== "function") return;
  if (typeof getCriticalStatusLabel !== "function") return;
  if (typeof shouldUseFallbackCalendarDays !== "function") return;
  if (typeof formatChineseDateTime !== "function") return;
  if (typeof getZoomSpec !== "function") return;
  if (typeof currentZoomLevel !== "function") return;

  function clear(node) {
    while (node.firstChild) node.removeChild(node.firstChild);
  }

  function row() {
    const d = document.createElement("div");
    d.className = "aps-legend-row";
    return d;
  }

  function title(text) {
    const s = document.createElement("span");
    s.className = "aps-legend-title";
    s.textContent = text;
    return s;
  }

  function item(label, chip) {
    const it = document.createElement("span");
    it.className = "aps-legend-item";
    const c = document.createElement("span");
    c.className = "aps-legend-chip";
    if (chip) {
      if (chip.background) c.style.background = String(chip.background);
      if (chip.borderColor) c.style.borderColor = String(chip.borderColor);
      if (chip.borderWidth) c.style.borderWidth = String(chip.borderWidth) + "px";
      if (chip.borderStyle) c.style.borderStyle = String(chip.borderStyle);
      if (chip.opacity) c.style.opacity = String(chip.opacity);
    }
    const tx = document.createElement("span");
    tx.textContent = label;
    it.appendChild(c);
    it.appendChild(tx);
    return it;
  }

  function summaryItem(label, value) {
    const it = document.createElement("span");
    it.className = "aps-legend-summary";
    const k = document.createElement("span");
    k.className = "aps-legend-summary-label";
    k.textContent = label;
    const v = document.createElement("span");
    v.className = "aps-legend-summary-value";
    v.textContent = value;
    it.appendChild(k);
    it.appendChild(v);
    return it;
  }

  function modeText() {
    if (state.ui.colorMode === "batch") return "按批次";
    if (state.ui.colorMode === "priority") return "按优先级";
    if (state.ui.colorMode === "source") return "按来源";
    return "按状态";
  }

  function arrowText() {
    return getArrowModeLabel(state.ui.depsMode, state.critical);
  }

  function sampleBatchIds(limit) {
    const out = [];
    const seen = new Set();
    const list = Array.isArray(state.filteredTasks) ? state.filteredTasks : [];
    for (let i = 0; i < list.length; i++) {
      const t = list[i] || {};
      const meta = t.meta || {};
      const bid = norm(meta.batch_id);
      if (!bid || seen.has(bid)) continue;
      seen.add(bid);
      out.push(bid);
      if (out.length >= limit) break;
    }
    return out;
  }

  function criticalVisibleCount() {
    if (state.critical && state.critical.available === false) return 0;
    const ids = state.ccIdSet;
    if (!ids || typeof ids.has !== "function") return 0;
    const list = Array.isArray(state.allTasks) ? state.allTasks : [];
    let count = 0;
    for (let i = 0; i < list.length; i += 1) {
      const tid = norm(list[i] && list[i].id);
      if (tid && ids.has(tid)) count += 1;
    }
    return count;
  }

  function calendarBackgroundDisabled() {
    const calendarPayload = {
      degradationEvents: state.degradationEvents,
      degradationCounters: state.degradationCounters,
      emptyReason: state.emptyReason,
    };
    const hasCalendarDays = Array.isArray(state.calendarDays) && state.calendarDays.length > 0;
    return !hasCalendarDays && !shouldUseFallbackCalendarDays(calendarPayload);
  }

  function updateLegend() {
    const el = $("ganttLegend");
    if (!el) return;

    const ccTotal = state.ccIdSet ? state.ccIdSet.size : 0;
    const ccVisible = criticalVisibleCount();
    const rawMakespanEnd = norm(state.critical && state.critical.makespan_end);
    const makespanEnd = rawMakespanEnd ? formatChineseDateTime(rawMakespanEnd) : "-";
    const ccStatusText = getCriticalStatusLabel(state.critical);
    const ccUnavailable = !!(state.critical && state.critical.available === false);
    const ccCacheText = ccUnavailable
      ? "不可用"
      : ((state.critical && state.critical.cache_hit === true) ? "已准备好" : "正在重新计算");
    const batchSamples = state.ui.colorMode === "batch" ? sampleBatchIds(3) : [];
    const calendarDisabled = calendarBackgroundDisabled();
    const zoomLevel = currentZoomLevel(state.ui);

    const digest = [
      state.filteredTasks.length,
      state.allTasks.length,
      zoomLevel,
      state.ui.colorMode || "batch",
      state.ui.depsMode || "critical",
      ccTotal,
      ccVisible,
      makespanEnd,
      ccStatusText,
      ccCacheText,
      calendarDisabled ? "calendar-off" : "calendar-on",
      batchSamples.join("|"),
    ].join("||");
    if (digest === _perfState.legendDigest) return;
    _perfState.legendDigest = digest;

    clear(el);

    const r1 = row();
    const zoomSpec = getZoomSpec(zoomLevel);
    const vmZh = zoomSpec.label || "日";
    r1.appendChild(summaryItem("显示", `${state.filteredTasks.length}/${state.allTasks.length}`));
    r1.appendChild(summaryItem("视图", vmZh));
    r1.appendChild(summaryItem("配色", modeText()));
    r1.appendChild(summaryItem("箭头", arrowText()));
    r1.appendChild(summaryItem("关键工序（全部/本页）", `${ccTotal}/${ccVisible}`));
    r1.appendChild(summaryItem("完工", makespanEnd));
    r1.appendChild(summaryItem("状态", ccStatusText));
    r1.appendChild(summaryItem("关键工序计算", ccCacheText));
    el.appendChild(r1);

    const r2 = row();
    r2.appendChild(title("配色"));
    if (state.ui.colorMode === "batch") {
      r2.appendChild(item("同批次同色", { background: "#94a3b8" }));
      for (let i = 0; i < batchSamples.length; i++) {
        const bid = batchSamples[i];
        r2.appendChild(item(bid, { background: colorForBatch(bid) }));
      }
    } else if (state.ui.colorMode === "priority") {
      r2.appendChild(item("普通", { background: colorForPriority("normal") }));
      r2.appendChild(item("急件", { background: colorForPriority("urgent") }));
      r2.appendChild(item("特急", { background: colorForPriority("critical") }));
    } else if (state.ui.colorMode === "source") {
      r2.appendChild(item("自制", { background: colorForSource("internal") }));
      r2.appendChild(item("外协", { background: colorForSource("external") }));
    } else {
      r2.appendChild(item("未开始", { background: colorForStatusKey("pending") }));
      r2.appendChild(item("进行中", { background: colorForStatusKey("in_progress") }));
      r2.appendChild(item("已完成", { background: colorForStatusKey("done") }));
    }
    el.appendChild(r2);

    const r3 = row();
    r3.appendChild(title("标记"));
    if (calendarDisabled) {
      r3.appendChild(item("假期/停工(停用)", { background: "#ffffff", borderColor: "#94a3b8", borderWidth: 1.5 }));
    } else {
      r3.appendChild(item("假期/停工(背景)", { background: "#fee2e2" }));
    }
    r3.appendChild(item("超期(红边)", { background: "#ffffff", borderColor: "#ef4444", borderWidth: 2.5 }));
    if (ccUnavailable) {
      r3.appendChild(item("关键工序(停用)", { background: "#ffffff", borderColor: "#94a3b8", borderWidth: 2.5 }));
    } else {
      r3.appendChild(item("关键工序(外框)", { background: "#ffffff", borderColor: "#38bdf8", borderWidth: 2.5 }));
    }
    r3.appendChild(item("外协(虚线)", { background: "#ffffff", borderColor: "#334155", borderWidth: 1.5, borderStyle: "dashed" }));
    // 执行状态样例（fusion-gantt-execution-visuals）：颜色与 aps_gantt.css 执行着色段
    // 的 --ui-* token 同源（updateLegend 调用时 getPropertyValue 取当时主题值；
    // 主题切换不主动刷图例是图例全部样例的既有行为，下次图例实际重建（digest 变化）时刷新）
    const uiColor = function (name, fallback) {
      const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
      return v || fallback;
    };
    r3.appendChild(item("已完工(绿罩)", { background: uiColor("--ui-success", "#16a34a"), opacity: 0.45 }));
    r3.appendChild(item("生产中(蓝边)", { background: "#ffffff", borderColor: uiColor("--ui-primary", "#2563eb"), borderWidth: 2 }));
    r3.appendChild(item("已暂停(琥珀边)", { background: "#ffffff", borderColor: uiColor("--ui-warning", "#d97706"), borderWidth: 2 }));
    r3.appendChild(item("异常中(红边)", { background: "#ffffff", borderColor: uiColor("--ui-danger", "#dc2626"), borderWidth: 2 }));
    r3.appendChild(item("非聚焦(变淡)", { background: "#94a3b8", opacity: 0.25 }));
    el.appendChild(r3);
  }

  ns.updateLegend = updateLegend;
})();
