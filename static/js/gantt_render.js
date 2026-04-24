(function () {
  var ns = window.__APS_GANTT__;
  if (!ns) return;
  if (!ns._inited) ns._inited = {};
  if (ns._inited.render) return;
  ns._inited.render = true;

  var $ = ns.$;
  var show = ns.show;
  var reportClientError = ns.reportClientError;
  var str = ns.str;
  var escapeHtml = ns.escapeHtml;
  var norm = ns.norm;
  var includesI = ns.includesI;
  var state = ns.state;
  var _perfState = ns._perfState;
  var colorForBatch = ns.colorForBatch;
  var colorForPriority = ns.colorForPriority;
  var colorForSource = ns.colorForSource;
  var statusKeyForTask = ns.statusKeyForTask;
  var colorForStatusKey = ns.colorForStatusKey;
  var getColor = ns.getColor;
  var outlineApi = ns.outline;
  var contractApi = ns.contract;

  if (typeof $ !== "function") return;
  if (typeof show !== "function") return;
  if (typeof reportClientError !== "function") return;
  if (typeof str !== "function") return;
  if (typeof escapeHtml !== "function") return;
  if (typeof norm !== "function") return;
  if (typeof includesI !== "function") return;
  if (!outlineApi) return;
  if (!contractApi) return;
  if (!state || !_perfState) return;

  var setCriticalOutlineEnabled = outlineApi.setCriticalOutlineEnabled;
  var installCriticalOutlineSyncAdapter = outlineApi.installCriticalOutlineSyncAdapter;
  var buildContractTasks = contractApi.buildRenderTasks;
  var getArrowModeLabel = contractApi.getArrowModeLabel;
  var getCriticalStatusLabel = contractApi.getCriticalStatusLabel;
  var getCriticalTooltip = contractApi.getCriticalTooltip;
  var shouldUseFallbackCalendarDays = contractApi.shouldUseFallbackCalendarDays;

  if (typeof setCriticalOutlineEnabled !== "function") return;
  if (typeof installCriticalOutlineSyncAdapter !== "function") return;
  if (typeof buildContractTasks !== "function") return;
  if (typeof getArrowModeLabel !== "function") return;
  if (typeof getCriticalStatusLabel !== "function") return;
  if (typeof getCriticalTooltip !== "function") return;
  if (typeof shouldUseFallbackCalendarDays !== "function") return;

  // ---- render/decorate cache (Win7 友好：减少不必要的全量重渲染) ----
  let _renderToken = 0; // 每次全量 render() + new Gantt() 递增
  const _decorCache = {
    renderToken: -1,
    colorMode: null,
    focusBatch: null,
    highlightCC: null,
  };

  function _resetDecorCache() {
    _decorCache.renderToken = -1;
    _decorCache.colorMode = null;
    _decorCache.focusBatch = null;
    _decorCache.highlightCC = null;
    _perfState.wrappersById = new Map();
    _perfState.decorateRenderedIds = [];
    _perfState.holidayDigest = "";
    _perfState.holidayLayerMounted = false;
    _perfState.lastHolidayHeight = 0;
    _perfState.legendDigest = "";
    _perfState.ccVisibleCount = 0;
  }

  function applyFilters(all) {
    const cfg = state.cfg || {};
    const view = norm(cfg.view) || "machine";
    const out = [];
    for (let i = 0; i < all.length; i++) {
      const t = all[i] || {};
      const meta = t.meta || {};

      if (state.ui.onlyOverdue && meta.is_overdue !== true) continue;
      if (state.ui.onlyExternal && norm(meta.source) !== "external") continue;

      if (state.ui.filterBatch && !includesI(meta.batch_id, state.ui.filterBatch)) continue;

      if (state.ui.filterResource) {
        if (view === "machine") {
          if (!includesI(meta.machine_id, state.ui.filterResource) && !includesI(meta.machine, state.ui.filterResource)) continue;
        } else {
          if (!includesI(meta.operator_id, state.ui.filterResource) && !includesI(meta.operator, state.ui.filterResource)) continue;
        }
      }

      out.push(t);
    }
    return out;
  }

  function buildRenderTasks() {
    const tasks = buildContractTasks(state.filteredTasks, state.ui.depsMode, state.critical);
    for (let i = 0; i < tasks.length; i++) {
      const t0 = state.filteredTasks[i] || {};
      const t = tasks[i] || {};
      const meta0 = t0.meta || {};
      t.meta = Object.assign({}, meta0);
      try {
        const rawName = str(t0.name || "");
        t.meta._raw_name = rawName;
        t.name = escapeHtml(rawName);
      } catch (_) {
        // ignore
      }
    }
    return tasks;
  }

  function updateLegend() {
    const el = $("ganttLegend");
    if (!el) return;

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

    // 关键链：后端为“全版本口径”；当前页面仅展示本窗口 tasks 的子集
    const ccTotal = state.ccIdSet ? state.ccIdSet.size : 0;
    const ccVisible = criticalVisibleCount();
    const makespanEnd = norm(state.critical && state.critical.makespan_end) || "-";
    const ccStatusText = getCriticalStatusLabel(state.critical);
    const ccUnavailable = !!(state.critical && state.critical.available === false);
    const ccCacheText = ccUnavailable
      ? "不可用"
      : ((state.critical && state.critical.cache_hit === true) ? "命中" : "未命中");
    const batchSamples = state.ui.colorMode === "batch" ? sampleBatchIds(3) : [];
    const calendarPayload = {
      degradationEvents: state.degradationEvents,
      degradationCounters: state.degradationCounters,
      emptyReason: state.emptyReason,
    };
    const hasCalendarDays = Array.isArray(state.calendarDays) && state.calendarDays.length > 0;
    const calendarBackgroundDisabled = !hasCalendarDays && !shouldUseFallbackCalendarDays(calendarPayload);

    // 图例在纯视觉交互时会高频触发；digest 未变化则跳过 DOM 重建
    const digest = [
      state.filteredTasks.length,
      state.allTasks.length,
      state.ui.viewMode || "Day",
      state.ui.colorMode || "batch",
      state.ui.depsMode || "critical",
      ccTotal,
      ccVisible,
      makespanEnd,
      ccStatusText,
      ccCacheText,
      calendarBackgroundDisabled ? "calendar-off" : "calendar-on",
      batchSamples.join("|"),
    ].join("||");
    if (digest === _perfState.legendDigest) return;
    _perfState.legendDigest = digest;

    clear(el);

    // Row 1: summary
    const r1 = row();
    const summary = document.createElement("span");
    const vmZh = {"Day": "日", "Week": "周", "Month": "月"}[state.ui.viewMode] || "日";
    summary.textContent = `显示 ${state.filteredTasks.length}/${state.allTasks.length}｜视图 ${vmZh}｜配色 ${modeText()}｜箭头 ${arrowText()}｜关键链（全版本/本窗口可见）${ccTotal}/${ccVisible}｜完工 ${makespanEnd}｜${ccStatusText}｜关键链缓存 ${ccCacheText}`;
    r1.appendChild(summary);
    el.appendChild(r1);

    // Row 2: color legend
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
      r2.appendChild(item("内制", { background: colorForSource("internal") }));
      r2.appendChild(item("外协", { background: colorForSource("external") }));
    } else {
      r2.appendChild(item("未开始", { background: colorForStatusKey("pending") }));
      r2.appendChild(item("进行中", { background: colorForStatusKey("in_progress") }));
      r2.appendChild(item("已完成", { background: colorForStatusKey("done") }));
    }
    el.appendChild(r2);

    // Row 3: markers
    const r3 = row();
    r3.appendChild(title("标记"));
    if (calendarBackgroundDisabled) {
      r3.appendChild(item("假期/停工(停用)", { background: "#ffffff", borderColor: "#94a3b8", borderWidth: 1.5 }));
    } else {
      r3.appendChild(item("假期/停工(背景)", { background: "#fee2e2" }));
    }
    r3.appendChild(item("超期(红边)", { background: "#ffffff", borderColor: "#ef4444", borderWidth: 2.5 }));
    if (ccUnavailable) {
      r3.appendChild(item("关键链(停用)", { background: "#ffffff", borderColor: "#94a3b8", borderWidth: 2.5 }));
    } else {
      r3.appendChild(item("关键链(外框)", { background: "#ffffff", borderColor: "#38bdf8", borderWidth: 2.5 }));
    }
    r3.appendChild(item("外协(虚线)", { background: "#ffffff", borderColor: "#334155", borderWidth: 1.5, borderStyle: "dashed" }));
    r3.appendChild(item("非聚焦(变淡)", { background: "#94a3b8", opacity: 0.25 }));
    el.appendChild(r3);
  }

  function initCalendarDays(days) {
    const list = Array.isArray(days) ? days : [];
    state.calendarDays = list;
  }

  // 关键链徽标（CC）已弃用：仅保留清理逻辑，避免旧 DOM 残留
  function upsertCriticalBadge(wrapper, enabled) {
    if (!wrapper) return;
    try {
      wrapper.querySelectorAll(".aps-cc-badge").forEach((n) => {
        try {
          n.remove();
        } catch (_) {
          // ignore
        }
      });
    } catch (err) {
      // ignore
    }

    // 徽标已弃用：不再插入
    return;
  }

  function _buildFallbackCalendarDays() {
    // 若后端未返回 calendar_days，则按“周末默认假期”做一个弱兜底（仅用于显示标注）
    const cfg = state.cfg || {};
    const s = norm(cfg.startDate || cfg.weekStart);
    const e0 = norm(cfg.endDate || "");
    if (!s) return [];

    const start = new Date(s + " 00:00:00");
    if (isNaN(start.getTime())) return [];

    // 若未提供 end_date，则默认用 7 天窗口（start + 6 天），保证“整周”都有假期兜底标注
    let end;
    if (e0) {
      end = new Date(e0 + " 00:00:00");
      if (isNaN(end.getTime())) return [];
    } else {
      end = new Date(start.getTime());
      end.setDate(end.getDate() + 6);
    }

    if (end.getTime() < start.getTime()) return [];

    const out = [];
    const cur = new Date(start.getTime());
    while (cur.getTime() <= end.getTime() + 1) {
      const dow = cur.getDay(); // 0=Sun ... 6=Sat
      const isHoliday = dow === 0 || dow === 6;
      const yyyy = cur.getFullYear();
      const mm = String(cur.getMonth() + 1).padStart(2, "0");
      const dd = String(cur.getDate()).padStart(2, "0");
      out.push({
        date: `${yyyy}-${mm}-${dd}`,
        day_type: isHoliday ? "weekend" : "workday",
        shift_hours: isHoliday ? 0 : 8,
        is_holiday: isHoliday,
        is_nonworking: isHoliday,
      });
      cur.setDate(cur.getDate() + 1);
    }
    return out;
  }

  function _buildHolidayDigest(days) {
    const list = Array.isArray(days) ? days : [];
    const buf = [];
    for (let i = 0; i < list.length; i++) {
      const d = list[i] || {};
      const dateStr = norm(d.date);
      if (!dateStr) continue;
      const isHoliday = d.is_holiday === true || (norm(d.day_type) && norm(d.day_type) !== "workday");
      const isNonworking = d.is_nonworking === true || Number(d.shift_hours || 0) <= 0;
      if (!isHoliday && !isNonworking) continue;
      buf.push(`${dateStr}|${isNonworking ? "1" : "0"}`);
    }
    return buf.join(",");
  }

  function _ensureHolidayLayer(svg) {
    try {
      const existing = svg.querySelector("g.aps-holiday-layer");
      if (existing) {
        _perfState.holidayLayerMounted = true;
        return existing;
      }
    } catch (_) {
      // ignore
    }
    const NS = "http://www.w3.org/2000/svg";
    const layer = document.createElementNS(NS, "g");
    layer.setAttribute("class", "aps-holiday-layer");

    // 优先插入到 grid 层末尾（保证：不盖住日期文字/条形，但能压住纯白背景）
    let mounted = false;
    try {
      const gridRow = svg.querySelector(".grid-row");
      if (gridRow) {
        let gridTop = gridRow;
        while (gridTop && gridTop.parentNode && gridTop.parentNode.tagName) {
          const tag = String(gridTop.parentNode.tagName || "").toLowerCase();
          if (tag === "svg") break;
          gridTop = gridTop.parentNode;
        }
        if (gridTop && gridTop !== svg && gridTop.parentNode === svg) {
          gridTop.appendChild(layer);
          mounted = true;
        }
      }
    } catch (_) {
      mounted = false;
    }
    if (!mounted) {
      // 兜底：插入到 bars 层之前（保证：背景在条形之下）
      let insertBefore = null;
      try {
        const firstBar = svg.querySelector(".bar-wrapper");
        if (firstBar) {
          let barTop = firstBar;
          while (barTop && barTop.parentNode && barTop.parentNode.tagName) {
            const tag = String(barTop.parentNode.tagName || "").toLowerCase();
            if (tag === "svg") break;
            barTop = barTop.parentNode;
          }
          if (barTop && barTop !== svg && barTop.parentNode === svg) {
            insertBefore = barTop;
          }
        }
      } catch (_) {
        insertBefore = null;
      }
      if (insertBefore) svg.insertBefore(layer, insertBefore);
      else svg.appendChild(layer);
    }
    _perfState.holidayLayerMounted = true;
    return layer;
  }

  function _computeHolidayHeight(svg) {
    let height = 0;
    try {
      const bb = svg.getBBox();
      height = bb && bb.height ? bb.height : 0;
    } catch (_) {
      height = 0;
    }
    if (!height) {
      const hAttr = Number(svg.getAttribute("height") || 0);
      if (hAttr) height = hAttr;
    }
    if (!height) {
      try {
        const vb = svg.viewBox && svg.viewBox.baseVal;
        if (vb && vb.height) height = vb.height;
      } catch (_) {
        // ignore
      }
    }
    if (!height) {
      const r = svg.getBoundingClientRect();
      if (r && r.height) height = r.height;
    }
    return height || 0;
  }

  function renderHolidayColumns() {
    const gantt = state.gantt;
    if (!gantt || !gantt.gantt_start || !gantt.options) return;

    const svg = document.querySelector("#gantt svg.gantt");
    if (!svg) return;

    const calendarPayload = {
      degradationEvents: state.degradationEvents,
      degradationCounters: state.degradationCounters,
      emptyReason: state.emptyReason,
    };
    const days = (Array.isArray(state.calendarDays) && state.calendarDays.length)
      ? state.calendarDays
      : (shouldUseFallbackCalendarDays(calendarPayload) ? _buildFallbackCalendarDays() : []);
    const digest = _buildHolidayDigest(days);
    const height = _computeHolidayHeight(svg);
    const sameDigest = digest === _perfState.holidayDigest;
    const sameHeight = Math.abs((_perfState.lastHolidayHeight || 0) - height) < 0.5;

    let layer = _ensureHolidayLayer(svg);
    if (!layer) return;
    if (!days.length) {
      try {
        layer.textContent = "";
      } catch (_) {
        // ignore
      }
      _perfState.holidayDigest = "";
      _perfState.lastHolidayHeight = height;
      return;
    }
    if (sameDigest && sameHeight) return;

    const step = Number(gantt.options.step) || 24;
    const col = Number(gantt.options.column_width) || 38;
    const start = gantt.gantt_start;
    const NS = "http://www.w3.org/2000/svg";
    const frag = document.createDocumentFragment();

    for (let i = 0; i < days.length; i++) {
      const d = days[i] || {};
      const dateStr = norm(d.date);
      if (!dateStr) continue;
      const isHoliday = d.is_holiday === true || (norm(d.day_type) && norm(d.day_type) !== "workday");
      const isNonworking = d.is_nonworking === true || Number(d.shift_hours || 0) <= 0;
      if (!isHoliday && !isNonworking) continue;

      const dt = new Date(dateStr + " 00:00:00");
      if (isNaN(dt.getTime())) continue;

      const diffHours = (dt.getTime() - start.getTime()) / 3600000.0;
      const x = (diffHours / step) * col;

      const rect = document.createElementNS(NS, "rect");
      rect.setAttribute("x", String(Math.floor(x)));
      rect.setAttribute("y", "0");
      rect.setAttribute("width", String(col));
      rect.setAttribute("height", String(height || 0));
      rect.setAttribute("class", isNonworking ? "aps-holiday-rect aps-nonworking" : "aps-holiday-rect");
      rect.setAttribute("data-date", dateStr);
      frag.appendChild(rect);
    }

    try {
      layer.textContent = "";
      layer.appendChild(frag);
    } catch (_) {
      // ignore
    }
    _perfState.holidayDigest = digest;
    _perfState.lastHolidayHeight = height;
  }

  function scrollToAnchor(gantt) {
    const cfg = state.cfg || {};
    try {
      const container = document.querySelector("#gantt .gantt-container");
      if (container && gantt && gantt.gantt_start) {
        const anchor = norm(cfg.startDate || cfg.weekStart || "");
        const target = new Date(anchor + " 00:00:00");
        const diffHours = (target.getTime() - gantt.gantt_start.getTime()) / 3600000.0;
        const px = (diffHours / gantt.options.step) * gantt.options.column_width - gantt.options.column_width;
        container.scrollLeft = Math.max(0, Math.floor(px));
      }
    } catch (_) {
      // 不阻断渲染
    }
  }

  function _buildTaskMapById() {
    const byId = new Map();
    const list = Array.isArray(state.currentTasks) ? state.currentTasks : [];
    for (let i = 0; i < list.length; i++) {
      const t = list[i] || {};
      byId.set(norm(t.id), t);
    }
    return byId;
  }

  function _applyGroupSeparators() {
    // 分组分隔（按 group_key）：给每个“新组”的首行加轻微底色，降低“混在一起”的心智负担
    const groupStartIdx = new Set();
    let prevGroup = null;
    for (let i = 0; i < state.currentTasks.length; i++) {
      const t = state.currentTasks[i] || {};
      const meta = t.meta || {};
      const gk = norm(meta.group_key);
      if (i === 0) {
        prevGroup = gk;
        continue;
      }
      if (gk !== prevGroup) {
        groupStartIdx.add(i);
        prevGroup = gk;
      }
    }
    try {
      const gridRows = document.querySelectorAll("#gantt .gantt .grid-row");
      gridRows.forEach((row, idx) => {
        const isGroupStart = groupStartIdx.has(idx);
        row.classList.toggle("aps-group-start", isGroupStart);
        // 统一移除历史内联 fill，避免主题切换时残留亮色注入
        row.removeAttribute("fill");
      });
    } catch (_) {
      // ignore
    }
  }

  function _roundBarsOnce() {
    // 圆角（SVG rect）
    try {
      document.querySelectorAll("#gantt .bar").forEach((rect) => {
        try {
          rect.setAttribute("rx", "4");
          rect.setAttribute("ry", "4");
        } catch (_) {
          // ignore
        }
      });
    } catch (_) {
      // ignore
    }
  }

  function _updateFocusClasses(wrapperList, byId) {
    const host = $("gantt");
    if (!host) return;
    const hasFocus = !!state.focusBatch;
    host.classList.toggle("aps-has-focus", hasFocus);

    // 无聚焦时只需清理旧 focus 标记
    if (!hasFocus) {
      for (let i = 0; i < wrapperList.length; i++) {
        wrapperList[i].el.classList.remove("aps-focus");
      }
      return;
    }

    for (let i = 0; i < wrapperList.length; i++) {
      const item = wrapperList[i];
      const t = byId.get(item.id);
      if (!t) continue;
      const meta = t.meta || {};
      const bid = norm(meta.batch_id);
      item.el.classList.toggle("aps-focus", !!(bid && bid === state.focusBatch));
    }
  }

  function decorateStaticAfterRender(byId) {
    // 说明：仅在 new Gantt() 后执行一次（避免纯视觉交互反复 getBBox()/重排）

    // 假期/停工标注（按全局工作日历）
    renderHolidayColumns();

    // 资源分组底色（grid-row fill）
    _applyGroupSeparators();

    // 外协虚线标识 + 清理旧 CC 徽标残留（已弃用）
    try {
      const wrappers = document.querySelectorAll("#gantt .bar-wrapper");
      wrappers.forEach((w) => {
        const tid = norm(w.getAttribute("data-id"));
        const t = byId.get(tid);
        if (!t) return;
        const meta = t.meta || {};
        const isExternal = norm(meta.source) === "external";
        w.classList.toggle("aps-external", isExternal);
      });
      // 旧版本残留：全局清理（避免逐 wrapper 扫描）
      document.querySelectorAll("#gantt .aps-cc-badge").forEach((n) => {
        try {
          n.remove();
        } catch (_) {
          // ignore
        }
      });
    } catch (_) {
      // ignore
    }

    _roundBarsOnce();
  }

  function decorateDynamic(opts) {
    const o = opts || {};
    const updateLegendFlag = o.updateLegend !== false;
    if (!state.gantt || !Array.isArray(state.currentTasks) || state.currentTasks.length === 0) {
      if (updateLegendFlag) updateLegend();
      return;
    }

    const ui = state.ui || {};
    const byId = o.byId || _buildTaskMapById();
    const forceAll = o.forceAll === true;
    const tokenChanged = _decorCache.renderToken !== _renderToken;
    let wrappersById = _perfState.wrappersById;
    let wrapperList = [];
    let needRebuildWrappers =
      forceAll ||
      tokenChanged ||
      !wrappersById ||
      wrappersById.size <= 0 ||
      wrappersById.size !== (state.currentTasks.length || 0);

    if (!needRebuildWrappers) {
      wrappersById.forEach((el, id) => {
        if (!el || !el.isConnected) {
          needRebuildWrappers = true;
          return;
        }
        wrapperList.push({ id: id, el: el });
      });
      if (wrapperList.length !== wrappersById.size) {
        needRebuildWrappers = true;
      }
    }

    if (needRebuildWrappers) {
      const wrappers = document.querySelectorAll("#gantt .bar-wrapper");
      if (!wrappers || wrappers.length === 0) {
        _perfState.wrappersById = new Map();
        if (updateLegendFlag) updateLegend();
        return;
      }
      wrappersById = new Map();
      wrapperList = [];
      wrappers.forEach((w) => {
        const tid = norm(w.getAttribute("data-id"));
        if (!tid) return;
        wrappersById.set(tid, w);
        wrapperList.push({ id: tid, el: w });
      });
      _perfState.wrappersById = wrappersById;
    }

    // 若 DOM 与数据不一致（例如渲染中途被打断），交给上层做降级
    const curCount = state.currentTasks.length || 0;
    const renderedCount = wrapperList.length || 0;
    if (curCount > 0 && renderedCount > 0 && renderedCount !== curCount) {
      throw new Error(`Gantt DOM mismatch: wrappers=${renderedCount}, tasks=${curCount}`);
    }
    const needColor = forceAll || tokenChanged || _decorCache.colorMode !== ui.colorMode;
    const needFocus = forceAll || tokenChanged || _decorCache.focusBatch !== state.focusBatch;
    const needCC = forceAll || tokenChanged || _decorCache.highlightCC !== ui.highlightCC;

    const renderedIds = [];

    for (let i = 0; i < wrapperList.length; i++) {
      const item = wrapperList[i];
      const tid = item.id;
      const w = item.el;
      const t = byId.get(tid);
      if (!t) continue;
      const meta = t.meta || {};

      if (needFocus) {
        // 兼容旧类：统一清理，后续改为容器级 + aps-focus
        w.classList.remove("aps-dim");
      }

      if (needColor) {
        const color = getColor(t, ui.colorMode);
        if (color) w.style.setProperty("--aps-bar-color", color);
      }

      if (needCC) {
        const isCC = !!(ui.highlightCC && state.ccIdSet && state.ccIdSet.has(tid));
        w.classList.toggle("aps-critical", isCC);
        setCriticalOutlineEnabled(w, isCC);
        upsertCriticalBadge(w, false);
        if (ui.highlightCC && isCC) renderedIds.push(tid);
      }
    }

    _perfState.decorateRenderedIds = needCC ? renderedIds : [];
    if (needCC && !ui.highlightCC) {
      // 高亮关闭时：确保 class 也被移除（上面 toggle 已处理大部分；此处做一次兜底）
      try {
        for (let i = 0; i < wrapperList.length; i++) {
          wrapperList[i].el.classList.remove("aps-critical");
        }
      } catch (_) {
        // ignore
      }
    }

    if (needFocus) {
      _updateFocusClasses(wrapperList, byId);
    }

    // 更新 cache（只要本次完成了增量装饰，就认为 DOM 与 ui 同步）
    _decorCache.renderToken = _renderToken;
    _decorCache.colorMode = ui.colorMode;
    _decorCache.focusBatch = state.focusBatch;
    _decorCache.highlightCC = ui.highlightCC;

    if (updateLegendFlag) updateLegend();
  }

  function safeDecorateDynamic(opts) {
    try {
      decorateDynamic(opts);
    } catch (err) {
      reportClientError("Gantt decorate failed", err);
      throw err;
    }
  }

  function _emptyStateMessage() {
    const reason = norm(state.emptyReason);
    const allTasks = Array.isArray(state.allTasks) ? state.allTasks : [];
    if (reason === "all_rows_filtered_by_invalid_time") {
      return "当前区间存在时间非法的排程数据，已全部过滤，请检查排产结果。";
    }
    if (allTasks.length > 0) {
      return "当前筛选条件下暂无可显示任务。";
    }
    return "暂无排程数据（该周/该版本）。";
  }

  function render() {
    const emptyEl = $("ganttEmpty");
    const errEl = $("ganttError");
    show(errEl, false);

    state.filteredTasks = applyFilters(state.allTasks);
    if (!state.filteredTasks.length) {
      if (emptyEl) {
        emptyEl.textContent = _emptyStateMessage();
      }
      show(emptyEl, true);
      const host = $("gantt");
      if (host) {
        host.innerHTML = "";
        host.classList.remove("aps-has-focus");
      }
      state.gantt = null;
      state.currentTasks = [];
      _resetDecorCache();
      updateLegend();
      return;
    }
    show(emptyEl, false);

    const host = $("gantt");
    if (!host) return;
    host.innerHTML = "";
    host.classList.remove("aps-has-focus");

    const tasks = buildRenderTasks();
    state.currentTasks = tasks;

    const gantt = new Gantt("#gantt", tasks, {
      view_mode: (state.ui && state.ui.viewMode) ? state.ui.viewMode : "Day",
      language: "zh",
      popup_trigger: "click",
      on_click: function (task) {
        const meta = task && task.meta ? task.meta : {};
        const bid = norm(meta.batch_id);
        if (!bid) return;
        state.focusBatch = state.focusBatch === bid ? "" : bid;
        // 纯视觉交互：只做增量装饰（Win7 避免全量重建）
        safeDecorateDynamic({ updateLegend: false });
      },
      custom_popup_html: function (task) {
        const meta = task && task.meta ? task.meta : {};
        const criticalInfo = getCriticalTooltip(task, state.critical);
        const sk = statusKeyForTask(task);
        const skZh =
          sk === "done" ? "已完成" : sk === "in_progress" ? "进行中" : sk === "blocked" ? "阻塞" : "未开始";

        // XSS 防御：所有动态字段必须 HTML 转义后再拼接
        const titleText = escapeHtml(str(meta._raw_name || (task && task.name ? task.name : "")));
        const startText = escapeHtml(str(task && task.start ? task.start : ""));
        const endText = escapeHtml(str(task && task.end ? task.end : ""));
        const batchText = escapeHtml(str(meta.batch_id || "-"));
        const pieceText = escapeHtml(str(meta.piece_id || "-"));
        const partText = escapeHtml(str(meta.part_no || "-"));
        const seqText = escapeHtml(str(meta.seq || "-"));
        const opTypeText = escapeHtml(str(meta.op_type_name || "-"));
        const machineText = escapeHtml(str(meta.machine || "-"));
        const operatorText = escapeHtml(str(meta.operator || "-"));
        const sourceText = escapeHtml(str(meta.source || "-"));
        const statusText = escapeHtml(str(skZh));
        const priorityText = escapeHtml(str(meta.priority || "-"));
        const dueText = escapeHtml(str(meta.due_date || "-"));
        const ccStatusText = escapeHtml(str(criticalInfo.statusLabel));
        const ccFromText = escapeHtml(str(criticalInfo.predecessorText));
        const ccTypeText = escapeHtml(str(criticalInfo.edgeTypeText));
        const ccReasonText = escapeHtml(str(criticalInfo.reasonText));
        const ccGapText = escapeHtml(str(criticalInfo.gapText));
        const ccUnavailableText = escapeHtml(str(criticalInfo.unavailableMessage));

        const lines = [
          `<div class="title">${titleText}</div>`,
          `<div class="subtitle">时间：${startText} ～ ${endText}</div>`,
          `<div class="subtitle">批次：${batchText}</div>`,
          `<div class="subtitle">件：${pieceText}</div>`,
          `<div class="subtitle">图号：${partText}</div>`,
          `<div class="subtitle">工序：${seqText}（${opTypeText}）</div>`,
          `<div class="subtitle">设备：${machineText}</div>`,
          `<div class="subtitle">人员：${operatorText}</div>`,
          `<div class="subtitle">来源：${sourceText}｜状态：${statusText}</div>`,
          `<div class="subtitle">优先级：${priorityText}｜交期：${dueText}</div>`,
          `<div class="subtitle">关键链：${ccStatusText}｜超期：${meta.is_overdue ? "是" : "否"}</div>`,
          `<div class="subtitle">关键链前驱：${ccFromText}｜类型：${ccTypeText}｜间隔(分)：${ccGapText}</div>`,
          `<div class="subtitle">关键链依据：${ccReasonText}</div>`,
        ];
        if (ccUnavailableText) {
          lines.push(`<div class="subtitle">关键链降级：${ccUnavailableText}</div>`);
        }
        return lines.join("") + `<div class="pointer"></div>`;
      },
    });

    state.gantt = gantt;
    installCriticalOutlineSyncAdapter(gantt);
    scrollToAnchor(gantt);
    // new Gantt()：全量渲染 + 静态装饰 + 动态装饰（一次）
    _renderToken += 1;
    _resetDecorCache();
    const byId = _buildTaskMapById();
    decorateStaticAfterRender(byId);
    safeDecorateDynamic({ forceAll: true, byId: byId, updateLegend: true });
  }

  ns.applyFilters = applyFilters;
  ns.initCalendarDays = initCalendarDays;
  ns.safeDecorateDynamic = safeDecorateDynamic;
  ns.render = render;
  ns.renderHolidayColumns = renderHolidayColumns;
  ns.updateLegend = updateLegend;
})();
