(function () {
  function $(id) {
    return document.getElementById(id);
  }

  function on(el, evt, fn) {
    if (!el) return;
    el.addEventListener(evt, fn);
  }

  function show(el, visible) {
    if (!el) return;
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

  function includesI(hay, needle) {
    const h = norm(hay).toLowerCase();
    const n = norm(needle).toLowerCase();
    if (!n) return true;
    return h.indexOf(n) >= 0;
  }

  function hashToHue(s) {
    const x = norm(s);
    let h = 0;
    for (let i = 0; i < x.length; i++) {
      h = ((h * 31) + x.charCodeAt(i)) >>> 0;
    }
    return h % 360;
  }

  function colorForBatch(batchId) {
    const b = norm(batchId);
    if (!b) return "#94a3b8";
    const hue = hashToHue(b);
    return `hsl(${hue}, 70%, 52%)`;
  }

  function colorForPriority(priority) {
    const p = norm(priority) || "normal";
    if (p === "critical") return "#ef4444";
    if (p === "urgent") return "#f59e0b";
    return "#94a3b8";
  }

  function colorForSource(source) {
    const s = norm(source) || "internal";
    if (s === "external") return "#a855f7";
    return "#0ea5e9";
  }

  function parseLocalDateTime(s) {
    const x = norm(s);
    // 期望格式：YYYY-MM-DD HH:MM[:SS]
    const m = /^(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2})(?::(\d{2}))?/.exec(x);
    if (!m) return null;
    const yy = Number(m[1]);
    const mm = Number(m[2]) - 1;
    const dd = Number(m[3]);
    const hh = Number(m[4]);
    const mi = Number(m[5]);
    const ss = Number(m[6] || "0");
    const dt = new Date(yy, mm, dd, hh, mi, ss, 0);
    return isNaN(dt.getTime()) ? null : dt;
  }

  function statusKeyForTask(task) {
    const t = task || {};
    const meta = t.meta || {};
    const st = parseLocalDateTime(t.start);
    const et = parseLocalDateTime(t.end);
    const now = Date.now();
    if (st && et) {
      if (et.getTime() <= now) return "done";
      if (st.getTime() <= now && now < et.getTime()) return "in_progress";
      return "pending";
    }
    // fallback：用后端状态（若存在）
    const raw = norm(meta.status);
    if (raw === "done" || raw === "finished" || raw === "complete" || raw === "completed") return "done";
    if (raw === "in_progress" || raw === "running") return "in_progress";
    if (raw === "blocked") return "blocked";
    return "pending";
  }

  function colorForStatusKey(key) {
    const s = norm(key) || "pending";
    if (s === "done") return "#22c55e";
    if (s === "in_progress") return "#0ea5e9";
    if (s === "blocked") return "#ef4444";
    return "#94a3b8"; // pending
  }

  function getColor(task, mode) {
    const t = task || {};
    const meta = t.meta || {};
    const m = norm(mode) || "batch";
    if (m === "priority") return colorForPriority(meta.priority);
    if (m === "source") return colorForSource(meta.source);
    if (m === "status") return colorForStatusKey(statusKeyForTask(t));
    return colorForBatch(meta.batch_id);
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
    calendarDays: [],
    // 默认：按批次配色；高亮关键链；仅显示关键链箭头（避免全图箭头过密）
    ui: {
      colorMode: "batch",
      filterBatch: "",
      filterResource: "",
      onlyOverdue: false,
      onlyExternal: false,
      showProcessDeps: false,
      highlightCC: true,
      onlyCCDeps: true,
    },
  };

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
  }

  function readUi() {
    state.ui.colorMode = norm($("ganttColorMode") && $("ganttColorMode").value) || "batch";
    state.ui.filterBatch = norm($("ganttFilterBatch") && $("ganttFilterBatch").value);
    state.ui.filterResource = norm($("ganttFilterResource") && $("ganttFilterResource").value);
    state.ui.onlyOverdue = !!($("ganttOnlyOverdue") && $("ganttOnlyOverdue").checked);
    state.ui.onlyExternal = !!($("ganttOnlyExternal") && $("ganttOnlyExternal").checked);
    state.ui.showProcessDeps = !!($("ganttShowProcessDeps") && $("ganttShowProcessDeps").checked);
    state.ui.highlightCC = !!($("ganttHighlightCC") && $("ganttHighlightCC").checked);
    state.ui.onlyCCDeps = !!($("ganttOnlyCCDeps") && $("ganttOnlyCCDeps").checked);
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
    // 注意：Frappe Gantt 会依赖 dependencies 去找任务；因此必须保证依赖指向的 id 也在本次 tasks 里
    const visibleIds = new Set();
    for (let i = 0; i < state.filteredTasks.length; i++) {
      visibleIds.add(norm(state.filteredTasks[i] && state.filteredTasks[i].id));
    }

    const tasks = [];
    for (let i = 0; i < state.filteredTasks.length; i++) {
      const t0 = state.filteredTasks[i] || {};
      const t = Object.assign({}, t0);
      const meta0 = t0.meta || {};
      // XSS 防御：避免后续对 meta 做标记时污染原始数据对象
      t.meta = Object.assign({}, meta0);

      // XSS 防御：第三方 Gantt 组件内部可能用 innerHTML 渲染 task.name
      try {
        const rawName = str(t0.name || "");
        t.meta._raw_name = rawName;
        t.name = escapeHtml(rawName);
      } catch (_) {
        // ignore
      }

      let deps = "";
      if (state.ui.onlyCCDeps) {
        const pred = state.ccPrevByTo.get(norm(t.id));
        deps = pred && visibleIds.has(pred) ? pred : "";
      } else if (state.ui.showProcessDeps) {
        deps = norm(t.dependencies);
        if (deps) {
          deps = deps
            .split(",")
            .map((x) => norm(x))
            .filter((x) => x && visibleIds.has(x))
            .join(",");
        }
      } else {
        deps = "";
      }
      t.dependencies = deps;

      tasks.push(t);
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
      if (state.ui.onlyCCDeps) return "关键链箭头";
      if (state.ui.showProcessDeps) return "工艺依赖箭头";
      return "无";
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

    clear(el);

    // 关键链：后端为“全版本口径”；当前页面仅展示本窗口 tasks 的子集
    const ccTotal = state.ccIdSet ? state.ccIdSet.size : 0;
    let ccVisible = 0;
    try {
      const all = Array.isArray(state.allTasks) ? state.allTasks : [];
      for (let i = 0; i < all.length; i++) {
        const tid = norm(all[i] && all[i].id);
        if (tid && state.ccIdSet && state.ccIdSet.has(tid)) ccVisible += 1;
      }
    } catch (_) {
      ccVisible = 0;
    }
    const makespanEnd = norm(state.critical && state.critical.makespan_end) || "-";

    // Row 1: summary
    const r1 = row();
    const summary = document.createElement("span");
    summary.textContent = `显示 ${state.filteredTasks.length}/${state.allTasks.length}｜配色 ${modeText()}｜箭头 ${arrowText()}｜关键链（全版本/本窗口可见）${ccTotal}/${ccVisible}｜完工 ${makespanEnd}`;
    r1.appendChild(summary);
    el.appendChild(r1);

    // Row 2: color legend
    const r2 = row();
    r2.appendChild(title("配色"));
    if (state.ui.colorMode === "batch") {
      r2.appendChild(item("同批次同色", { background: "#94a3b8" }));
      const samples = sampleBatchIds(3);
      for (let i = 0; i < samples.length; i++) {
        const bid = samples[i];
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
    r3.appendChild(item("假期/停工(背景)", { background: "#fee2e2" }));
    r3.appendChild(item("超期(红边)", { background: "#ffffff", borderColor: "#ef4444", borderWidth: 2.5 }));
    r3.appendChild(item("关键链(外框)", { background: "#ffffff", borderColor: "#38bdf8", borderWidth: 2.5 }));
    r3.appendChild(item("外协(虚线)", { background: "#ffffff", borderColor: "#334155", borderWidth: 1.5, borderStyle: "dashed" }));
    r3.appendChild(item("非聚焦(变淡)", { background: "#94a3b8", opacity: 0.25 }));
    el.appendChild(r3);
  }

  function initCalendarDays(days) {
    const list = Array.isArray(days) ? days : [];
    state.calendarDays = list;
  }

  function upsertCriticalOutlines(wrapper, enabled) {
    if (!wrapper) return;
    try {
      wrapper.querySelectorAll(".aps-cc-outline-outer, .aps-cc-outline-inner").forEach((n) => {
        try {
          n.remove();
        } catch (_) {
          // ignore
        }
      });
    } catch (_) {
      // ignore
    }

    if (!enabled) return;

    const bar = wrapper.querySelector(".bar");
    if (!bar) return;

    // 关键链强调：把“双层边框”画在 bar 外侧，避免被超期红边遮挡
    const NS = "http://www.w3.org/2000/svg";
    let x = Number(bar.getAttribute("x") || 0);
    let y = Number(bar.getAttribute("y") || 0);
    let w = Number(bar.getAttribute("width") || 0);
    let h = Number(bar.getAttribute("height") || 0);
    if (!(w > 0 && h > 0)) return;

    // bar 圆角
    let rx0 = Number(bar.getAttribute("rx") || 4);
    let ry0 = Number(bar.getAttribute("ry") || rx0);
    if (!(rx0 >= 0)) rx0 = 4;
    if (!(ry0 >= 0)) ry0 = rx0;
    try {
      bar.setAttribute("rx", String(rx0));
      bar.setAttribute("ry", String(ry0));
    } catch (_) {
      // ignore
    }

    const outerPad = 2;
    const innerPad = 1;

    const outer = document.createElementNS(NS, "rect");
    outer.setAttribute("class", "aps-cc-outline-outer");
    outer.setAttribute("x", String(x - outerPad));
    outer.setAttribute("y", String(y - outerPad));
    outer.setAttribute("width", String(w + outerPad * 2));
    outer.setAttribute("height", String(h + outerPad * 2));
    outer.setAttribute("rx", String(rx0 + outerPad));
    outer.setAttribute("ry", String(ry0 + outerPad));
    outer.setAttribute("vector-effect", "non-scaling-stroke");
    outer.setAttribute("pointer-events", "none");

    const inner = document.createElementNS(NS, "rect");
    inner.setAttribute("class", "aps-cc-outline-inner");
    inner.setAttribute("x", String(x - innerPad));
    inner.setAttribute("y", String(y - innerPad));
    inner.setAttribute("width", String(w + innerPad * 2));
    inner.setAttribute("height", String(h + innerPad * 2));
    inner.setAttribute("rx", String(rx0 + innerPad));
    inner.setAttribute("ry", String(ry0 + innerPad));
    inner.setAttribute("vector-effect", "non-scaling-stroke");
    inner.setAttribute("pointer-events", "none");

    try {
      // 注意：Frappe Gantt 里 bar 往往不在 wrapper 的直接子级（可能在内部 g 分组里）。
      // 因此必须对 bar 的真实父节点执行 insertBefore，否则会触发 NotFoundError。
      const parent = (bar && bar.parentNode) ? bar.parentNode : wrapper;
      parent.insertBefore(outer, bar);
      parent.insertBefore(inner, bar);
    } catch (_) {
      // 兜底：尽量插入（即使顺序不完美也要可见）
      try {
        const parent = (bar && bar.parentNode) ? bar.parentNode : wrapper;
        parent.appendChild(outer);
        parent.appendChild(inner);
      } catch (_) {
        // ignore
      }
    }
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
    } catch (_) {
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

  function renderHolidayColumns() {
    const gantt = state.gantt;
    if (!gantt || !gantt.gantt_start || !gantt.options) return;

    const svg = document.querySelector("#gantt svg.gantt");
    if (!svg) return;

    // 清理旧层
    try {
      const old = svg.querySelector("g.aps-holiday-layer");
      if (old && old.parentNode) old.parentNode.removeChild(old);
    } catch (_) {
      // ignore
    }

    const days = (Array.isArray(state.calendarDays) && state.calendarDays.length) ? state.calendarDays : _buildFallbackCalendarDays();
    if (!days.length) return;

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

    // 计算高度（SVG user units）
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

    const step = Number(gantt.options.step) || 24;
    const col = Number(gantt.options.column_width) || 38;
    const start = gantt.gantt_start;

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
      layer.appendChild(rect);
    }
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
        if (groupStartIdx.has(idx)) row.setAttribute("fill", "#eef2ff");
        else row.removeAttribute("fill");
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

  function _clearAllCriticalOutlines() {
    try {
      document.querySelectorAll("#gantt .aps-cc-outline-outer, #gantt .aps-cc-outline-inner").forEach((n) => {
        try {
          n.remove();
        } catch (_) {
          // ignore
        }
      });
    } catch (_) {
      // ignore
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
    const wrappers = document.querySelectorAll("#gantt .bar-wrapper");
    if (!wrappers || wrappers.length === 0) {
      if (updateLegendFlag) updateLegend();
      return;
    }

    // 若 DOM 与数据不一致（例如渲染中途被打断），交给上层做降级
    const curCount = state.currentTasks.length || 0;
    if (curCount > 0 && wrappers.length > 0 && wrappers.length !== curCount) {
      throw new Error(`Gantt DOM mismatch: wrappers=${wrappers.length}, tasks=${curCount}`);
    }

    const forceAll = o.forceAll === true;
    const tokenChanged = _decorCache.renderToken !== _renderToken;
    const needColor = forceAll || tokenChanged || _decorCache.colorMode !== ui.colorMode;
    const needFocus = forceAll || tokenChanged || _decorCache.focusBatch !== state.focusBatch;
    const needCC = forceAll || tokenChanged || _decorCache.highlightCC !== ui.highlightCC;

    let ccWrappers = null;
    if (needCC) {
      _clearAllCriticalOutlines();
      ccWrappers = [];
    }

    wrappers.forEach((w) => {
      const tid = norm(w.getAttribute("data-id"));
      const t = byId.get(tid);
      if (!t) return;
      const meta = t.meta || {};

      if (needFocus) {
        const bid = norm(meta.batch_id);
        const dim = !!(state.focusBatch && bid && state.focusBatch !== bid);
        w.classList.toggle("aps-dim", dim);
      }

      if (needColor) {
        const color = getColor(t, ui.colorMode);
        if (color) w.style.setProperty("--aps-bar-color", color);
      }

      if (needCC) {
        const isCC = !!(ui.highlightCC && state.ccIdSet && state.ccIdSet.has(tid));
        w.classList.toggle("aps-critical", isCC);
        if (ui.highlightCC && isCC && ccWrappers) ccWrappers.push(w);
      }
    });

    if (needCC && ui.highlightCC && Array.isArray(ccWrappers) && ccWrappers.length > 0) {
      for (let i = 0; i < ccWrappers.length; i++) {
        const w = ccWrappers[i];
        // 关键链外框：仅对 CC wrapper 插入（避免对所有 wrapper 反复 querySelectorAll）
        upsertCriticalOutlines(w, true);
        // CC 徽标已弃用：这里仅做清理（防止旧 DOM 残留）
        upsertCriticalBadge(w, false);
      }
    }
    if (needCC && !ui.highlightCC) {
      // 高亮关闭时：确保 class 也被移除（上面 toggle 已处理大部分；此处做一次兜底）
      try {
        wrappers.forEach((w) => w.classList.remove("aps-critical"));
      } catch (_) {
        // ignore
      }
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
    } catch (_) {
      // 自动降级：确保正确性优先
      try {
        render();
      } catch (_2) {
        // ignore
      }
    }
  }

  function render() {
    const emptyEl = $("ganttEmpty");
    const errEl = $("ganttError");
    show(errEl, false);

    state.filteredTasks = applyFilters(state.allTasks);
    if (!state.filteredTasks.length) {
      show(emptyEl, true);
      const host = $("gantt");
      if (host) host.innerHTML = "";
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

    const tasks = buildRenderTasks();
    state.currentTasks = tasks;

    const gantt = new Gantt("#gantt", tasks, {
      view_mode: "Day",
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
        const isCC = !!(state.ccIdSet && state.ccIdSet.has(norm(task && task.id)));
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
          `<div class="subtitle">关键链：${isCC ? "是" : "否"}｜超期：${meta.is_overdue ? "是" : "否"}</div>`,
        ];
        return lines.join("") + `<div class="pointer"></div>`;
      },
    });

    state.gantt = gantt;
    scrollToAnchor(gantt);
    // new Gantt()：全量渲染 + 静态装饰 + 动态装饰（一次）
    _renderToken += 1;
    _resetDecorCache();
    const byId = _buildTaskMapById();
    decorateStaticAfterRender(byId);
    safeDecorateDynamic({ forceAll: true, byId: byId, updateLegend: true });
  }

  function bindUi() {
    // 防御：避免重复绑定事件
    if (bindUi._bound === true) return;
    bindUi._bound = true;

    const resetBtn = $("ganttResetView");
    if (resetBtn) {
      on(resetBtn, "click", function () {
        state.focusBatch = "";

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
        const sp = $("ganttShowProcessDeps");
        if (sp) sp.checked = false;
        const hc = $("ganttHighlightCC");
        if (hc) hc.checked = true;
        const oc = $("ganttOnlyCCDeps");
        if (oc) oc.checked = true;

        readUi();
        render();
      });
    }

    let timerFull = 0;
    let timerDecor = 0;

    function scheduleFullRender() {
      if (timerFull) clearTimeout(timerFull);
      timerFull = setTimeout(function () {
        readUi();
        render();
      }, 240);
    }

    function scheduleDecorate() {
      if (timerDecor) clearTimeout(timerDecor);
      timerDecor = setTimeout(function () {
        readUi();
        safeDecorateDynamic({ updateLegend: true });
      }, 60);
    }

    // 纯视觉类：不重建 Gantt
    ["ganttColorMode", "ganttHighlightCC"].forEach((id) => {
      const el = $(id);
      if (el) on(el, "change", scheduleDecorate);
    });

    // 数据集合/依赖类：必须全量 render
    ["ganttOnlyOverdue", "ganttOnlyExternal", "ganttShowProcessDeps", "ganttOnlyCCDeps"].forEach((id) => {
      const el = $(id);
      if (el) on(el, "change", scheduleFullRender);
    });
    ["ganttFilterBatch", "ganttFilterResource"].forEach((id) => {
      const el = $(id);
      if (el) on(el, "input", scheduleFullRender);
    });
  }

  function initCriticalChain(critical) {
    const cc = critical || {};
    state.critical = cc;

    const ids = Array.isArray(cc.ids) ? cc.ids : [];
    state.ccIdSet = new Set(ids.map((x) => norm(x)).filter((x) => !!x));

    const m = new Map();
    const edges = Array.isArray(cc.edges) ? cc.edges : [];
    for (let i = 0; i < edges.length; i++) {
      const e = edges[i] || {};
      const from = norm(e.from);
      const to = norm(e.to);
      if (from && to) m.set(to, from);
    }
    state.ccPrevByTo = m;
  }

  async function loadAndRender() {
    const cfg = (function () {
      // 优先：window 注入（兼容旧模板）
      try {
        const w = window.__APS_GANTT__;
        if (w && (w.dataUrl || w.view || w.weekStart)) return w;
      } catch (_) {
        // ignore
      }
      // 兜底：从 #gantt 的 data-* 读取（避免模板内联 JS 造成编辑器误报）
      const host = document.getElementById("gantt");
      const ds = host && host.dataset ? host.dataset : {};
      return {
        // 主用：data-url -> dataset.url（新模板）
        // 兼容：data-data-url -> dataset.dataUrl（旧模板）
        // 兼容：data-data-data-url -> dataset.dataDataUrl（历史误写，尽量不断）
        dataUrl: ds.url || ds.dataUrl || ds.dataDataUrl || "",
        view: ds.view || "",
        weekStart: ds.weekStart || "",
        startDate: ds.startDate || "",
        endDate: ds.endDate || "",
        offset: ds.offset || 0,
        version: ds.version || "",
      };
    })();
    state.cfg = cfg;

    const emptyEl = $("ganttEmpty");
    const errEl = $("ganttError");
    show(emptyEl, false);
    show(errEl, false);

    const dataUrl = norm(cfg && cfg.dataUrl ? cfg.dataUrl : "");
    if (!dataUrl) {
      if (errEl) {
        errEl.textContent = "甘特图配置缺失：未找到数据接口 URL（data-url；兼容 data-data-url）。";
      }
      show(errEl, true);
      return;
    }

    let url;
    try {
      url = new URL(dataUrl, window.location.origin);
    } catch (e) {
      if (errEl) {
        errEl.textContent = `甘特图配置错误：数据接口 URL 不合法（dataUrl=${str(dataUrl)}）。`;
      }
      show(errEl, true);
      return;
    }
    if (cfg.view) url.searchParams.set("view", cfg.view);
    if (cfg.weekStart) url.searchParams.set("week_start", cfg.weekStart);
    if (cfg.startDate) url.searchParams.set("start_date", cfg.startDate);
    if (cfg.endDate) url.searchParams.set("end_date", cfg.endDate);
    if (typeof cfg.offset !== "undefined") url.searchParams.set("offset", String(cfg.offset));
    if (cfg.version) url.searchParams.set("version", String(cfg.version));

    let payload;
    try {
      const resp = await fetch(url.toString(), { headers: { Accept: "application/json" } });
      payload = await resp.json();
      if (!payload || payload.success !== true) {
        const msg =
          payload && payload.error && payload.error.message ? payload.error.message : "甘特图数据获取失败。";
        throw new Error(msg);
      }
    } catch (e) {
      const msg = str(e && e.message ? e.message : e);
      if (errEl) errEl.textContent = msg;
      else {
        try {
          console.error("Gantt load failed:", e);
        } catch (_) {
          // ignore
        }
      }
      show(errEl, true);
      return;
    }

    const data = payload.data || {};
    const tasks = Array.isArray(data.tasks) ? data.tasks : [];
    state.allTasks = tasks;
    initCriticalChain(data.critical_chain || null);
    initCalendarDays(data.calendar_days || null);

    bindUi();
    readUi();
    render();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", loadAndRender);
  } else {
    loadAndRender();
  }
})();

