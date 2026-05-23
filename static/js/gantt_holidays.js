(function () {
  var ns = window.__APS_GANTT__;
  if (!ns) return;
  if (!ns._inited) ns._inited = {};
  if (ns._inited.holidays) return;
  ns._inited.holidays = true;

  var norm = ns.norm;
  var state = ns.state;
  var _perfState = ns._perfState;
  var contractApi = ns.contract;
  var zoomApi = ns.zoom;

  if (typeof norm !== "function") return;
  if (!state || !_perfState || !contractApi || !zoomApi) return;

  var shouldUseFallbackCalendarDays = contractApi.shouldUseFallbackCalendarDays;
  var getGanttScale = zoomApi.getGanttScale;

  if (typeof shouldUseFallbackCalendarDays !== "function") return;
  if (typeof getGanttScale !== "function") return;

  function initCalendarDays(days) {
    const list = Array.isArray(days) ? days : [];
    state.calendarDays = list;
  }

  function buildFallbackCalendarDays() {
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

  function buildHolidayDigest(days) {
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

  function ensureHolidayLayer(svg) {
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

  function computeHolidayHeight(svg) {
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
      : (shouldUseFallbackCalendarDays(calendarPayload) ? buildFallbackCalendarDays() : []);
    const digest = buildHolidayDigest(days);
    const height = computeHolidayHeight(svg);
    const sameDigest = digest === _perfState.holidayDigest;
    const sameHeight = Math.abs((_perfState.lastHolidayHeight || 0) - height) < 0.5;

    let layer = ensureHolidayLayer(svg);
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

    const scale = getGanttScale(gantt);
    const stepMinutes = scale.stepMinutes;
    const col = scale.columnWidth;
    const start = gantt.gantt_start;
    const NS = "http://www.w3.org/2000/svg";
    const rects = [];

    for (let i = 0; i < days.length; i++) {
      const d = days[i] || {};
      const dateStr = norm(d.date);
      if (!dateStr) continue;
      const isHoliday = d.is_holiday === true || (norm(d.day_type) && norm(d.day_type) !== "workday");
      const isNonworking = d.is_nonworking === true || Number(d.shift_hours || 0) <= 0;
      if (!isHoliday && !isNonworking) continue;

      const dt = new Date(dateStr + " 00:00:00");
      if (isNaN(dt.getTime())) continue;

      const diffMinutes = (dt.getTime() - start.getTime()) / 60000.0;
      const x = (diffMinutes / stepMinutes) * col;

      const rect = document.createElementNS(NS, "rect");
      rect.setAttribute("x", String(Math.floor(x)));
      rect.setAttribute("y", "0");
      rect.setAttribute("width", String(scale.dayWidth));
      rect.setAttribute("height", String(height || 0));
      rect.setAttribute("class", isNonworking ? "aps-holiday-rect aps-nonworking" : "aps-holiday-rect");
      rect.setAttribute("data-date", dateStr);
      rects.push(rect);
    }

    try {
      layer.textContent = "";
      for (let i = 0; i < rects.length; i++) {
        layer.appendChild(rects[i]);
      }
    } catch (_) {
      // ignore
    }
    _perfState.holidayDigest = digest;
    _perfState.lastHolidayHeight = height;
  }

  ns.initCalendarDays = initCalendarDays;
  ns.renderHolidayColumns = renderHolidayColumns;
})();
