(function () {
  var ns = window.__APS_GANTT__;
  if (!ns) return;
  if (!ns._inited) ns._inited = {};
  if (ns._inited.boot) return;
  ns._inited.boot = true;

  var $ = ns.$;
  var show = ns.show;
  var reportClientError = ns.reportClientError;
  var str = ns.str;
  var norm = ns.norm;
  var parsePositiveInt = ns.parsePositiveInt;
  var state = ns.state;
  var _perfState = ns._perfState;

  var initCalendarDays = ns.initCalendarDays;
  var refreshFilterSelectOptions = ns.refreshFilterSelectOptions;
  var applyUiFromUrl = ns.applyUiFromUrl;
  var bindUi = ns.bindUi;
  var readUi = ns.readUi;
  var persistUiToUrl = ns.persistUiToUrl;
  var render = ns.render;
  var outline = ns.outline;

  function _reportMissingDeps(missing) {
    var msg = "甘特图脚本加载不完整，请刷新页面后重试。缺失：" + String((missing || []).join(", "));
    if (typeof reportClientError === "function") {
      reportClientError(msg);
      return;
    }
    try { console.error(msg); } catch (_) {}
  }

  var missingDeps = [];
  if (typeof $ !== "function") missingDeps.push("$");
  if (typeof show !== "function") missingDeps.push("show");
  if (typeof reportClientError !== "function") missingDeps.push("reportClientError");
  if (typeof str !== "function") missingDeps.push("str");
  if (typeof norm !== "function") missingDeps.push("norm");
  if (typeof parsePositiveInt !== "function") missingDeps.push("parsePositiveInt");
  if (!state) missingDeps.push("state");
  if (!_perfState) missingDeps.push("_perfState");
  if (typeof initCalendarDays !== "function") missingDeps.push("initCalendarDays");
  if (typeof refreshFilterSelectOptions !== "function") missingDeps.push("refreshFilterSelectOptions");
  if (typeof applyUiFromUrl !== "function") missingDeps.push("applyUiFromUrl");
  if (typeof bindUi !== "function") missingDeps.push("bindUi");
  if (typeof readUi !== "function") missingDeps.push("readUi");
  if (typeof persistUiToUrl !== "function") missingDeps.push("persistUiToUrl");
  if (typeof render !== "function") missingDeps.push("render");
  if (!outline || typeof outline.setCriticalOutlineEnabled !== "function") {
    missingDeps.push("outline.setCriticalOutlineEnabled");
  }
  if (!outline || typeof outline.installCriticalOutlineSyncAdapter !== "function") {
    missingDeps.push("outline.installCriticalOutlineSyncAdapter");
  }
  if (missingDeps.length > 0) {
    _reportMissingDeps(missingDeps);
    return;
  }

  function initCriticalChain(critical) {
    const raw = critical || {};
    const cc = {
      ids: Array.isArray(raw.ids) ? raw.ids : [],
      edges: Array.isArray(raw.edges) ? raw.edges : [],
      makespan_end: raw.makespan_end || null,
      available: raw.available !== false,
      reason: norm(raw.reason),
      cache_hit: raw.cache_hit === true,
    };
    state.critical = cc;

    const ids = cc.ids;
    state.ccIdSet = new Set(ids.map((x) => norm(x)).filter((x) => !!x));

    const m = new Map();
    const metaMap = new Map();
    const edges = cc.edges;
    for (let i = 0; i < edges.length; i++) {
      const e = edges[i] || {};
      const from = norm(e.from);
      const to = norm(e.to);
      if (from && to) {
        m.set(to, from);
        metaMap.set(to, {
          from: from,
          edge_type: norm(e.edge_type) || "unknown",
          reason: norm(e.reason) || "控制前驱",
          gap_minutes: e.gap_minutes,
        });
      }
    }
    state.ccPrevByTo = m;
    state.ccEdgeMetaByTo = metaMap;
    _perfState.ccVisibleCount = 0;
    const all = Array.isArray(state.allTasks) ? state.allTasks : [];
    for (let j = 0; j < all.length; j++) {
      const tid = norm(all[j] && all[j].id);
      if (tid && state.ccIdSet && state.ccIdSet.has(tid)) {
        _perfState.ccVisibleCount += 1;
      }
    }
  }

  function resetOverdueMarkerState() {
    state.overdueMarkersDegraded = false;
    state.overdueMarkersPartial = false;
    state.overdueMarkersMessage = "";
  }

  function resetCalendarDegradationState() {
    state.degraded = false;
    state.degradationEvents = [];
    state.degradationCounters = {};
    state.emptyReason = "";
  }

  function _findDegradationEvent(code) {
    const target = norm(code);
    const events = Array.isArray(state.degradationEvents) ? state.degradationEvents : [];
    for (let i = 0; i < events.length; i++) {
      const event = events[i] || {};
      if (norm(event.code) === target) {
        return event;
      }
    }
    return null;
  }

  function _degradationCount(code) {
    const target = norm(code);
    const counters = state.degradationCounters && typeof state.degradationCounters === "object"
      ? state.degradationCounters
      : {};
    return Number(counters[target] || 0);
  }

  function _buildDegradationMessages() {
    const messages = [];
    const emptyReason = str(state.emptyReason || "").trim();
    const calendarEvent = _findDegradationEvent("calendar_load_failed");
    const calendarFailed = _degradationCount("calendar_load_failed") > 0 || emptyReason === "calendar_load_failed";
    const badTimeSkipped = _degradationCount("bad_time_row_skipped");
    const criticalChainEvent = _findDegradationEvent("critical_chain_unavailable");
    const criticalChainUnavailable = _degradationCount("critical_chain_unavailable") > 0 || (state.critical && state.critical.available === false);
    const allFiltered = emptyReason === "all_rows_filtered_by_invalid_time";

    if (calendarFailed) {
      let calendarMessage = "工作日历加载失败，当前不显示假期/停工背景标注。";
      if (calendarEvent && str(calendarEvent.message || "").trim()) {
        const eventMessage = str(calendarEvent.message || "").trim();
        calendarMessage = eventMessage.indexOf("工作日历加载失败") >= 0
          ? "工作日历加载失败，当前不显示假期/停工背景标注。"
          : eventMessage;
      }
      messages.push(calendarMessage);
    }

    if (allFiltered) {
      messages.push("当前区间存在时间非法的排程数据，已全部过滤，请检查排产结果。");
    } else if (badTimeSkipped > 0) {
      messages.push("已过滤 " + badTimeSkipped + " 条时间不合法的排程记录。");
    }

    if (criticalChainUnavailable) {
      let criticalChainMessage = "关键链暂不可用，当前仅展示普通甘特任务与资源排程。";
      if (criticalChainEvent && str(criticalChainEvent.message || "").trim()) {
        criticalChainMessage = str(criticalChainEvent.message || "").trim();
      }
      messages.push(criticalChainMessage);
    }

    return messages;
  }

  function applyCalendarDegradationState() {
    const warningEl = $("ganttDegradationWarning");
    const messages = _buildDegradationMessages();
    const visible = messages.length > 0;
    const message = visible
      ? messages.join(" ")
      : "排程数据存在异常，可能影响甘特图展示，请检查数据。";

    if (warningEl) {
      warningEl.textContent = message;
      show(warningEl, visible);
    }
  }

  function applyOverdueMarkerState() {
    const warningEl = $("ganttOverdueWarning");
    const overdueToggle = $("ganttOnlyOverdue");
    const degraded = !!state.overdueMarkersDegraded;
    const partial = !!state.overdueMarkersPartial && !degraded;
    const visible = degraded || partial;
    const message =
      str(state.overdueMarkersMessage || "").trim() ||
      (partial ? "部分超期标记可能不完整，当前仍按已识别条目标记。" : "超期标记可能不完整，请稍后重试或查看系统历史。");

    if (warningEl) {
      warningEl.textContent = message;
      show(warningEl, visible);
    }

    if (!overdueToggle) return;
    overdueToggle.disabled = degraded;
    if (degraded) {
      overdueToggle.checked = false;
    }
    if (visible) {
      overdueToggle.title = message;
    } else {
      overdueToggle.title = "";
    }
  }

  function _withFetchTimeout(url, timeoutMs) {
    const timeout = Number(timeoutMs) > 0 ? Number(timeoutMs) : 12000;
    if (typeof AbortController === "undefined") {
      return fetch(url, { headers: { Accept: "application/json" } });
    }
    const controller = new AbortController();
    const timer = setTimeout(() => {
      try {
        controller.abort();
      } catch (_) {
        // ignore
      }
    }, timeout);
    return fetch(url, {
      headers: { Accept: "application/json" },
      signal: controller.signal,
    }).finally(() => {
      clearTimeout(timer);
    });
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
        hasHistory: ds.hasHistory || "",
        fetchTimeoutMs: ds.fetchTimeoutMs || ds.fetchTimeout || "",
      };
    })();
    state.cfg = cfg;
    const emptyEl = $("ganttEmpty");
    const errEl = $("ganttError");
    show(emptyEl, false);
    show(errEl, false);
    const hasHistory = String(cfg && cfg.hasHistory ? cfg.hasHistory : "") === "1";

    if (!hasHistory) {
      if (emptyEl) {
        emptyEl.textContent = "当前数据库暂无排程版本，请先在【排产调度】执行一次排产。";
      }
      show(emptyEl, true);
      const host = $("gantt");
      resetCalendarDegradationState();
      resetOverdueMarkerState();
      applyOverdueMarkerState();
      applyCalendarDegradationState();
      if (host) host.innerHTML = "";
      return;
    }

    const dataUrl = norm(cfg && cfg.dataUrl ? cfg.dataUrl : "");
    if (!dataUrl) {
      if (errEl) {
        errEl.textContent = "甘特图配置缺失：未找到数据接口 URL（data-url；兼容 data-data-url）。";
      }
      resetCalendarDegradationState();
      applyCalendarDegradationState();
      resetOverdueMarkerState();
      applyOverdueMarkerState();
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
      resetCalendarDegradationState();
      applyCalendarDegradationState();
      resetOverdueMarkerState();
      applyOverdueMarkerState();
      show(errEl, true);
      return;
    }
    const hasEffectiveRange = !!(cfg.startDate || cfg.endDate);
    if (cfg.view) url.searchParams.set("view", cfg.view);
    if (cfg.weekStart) url.searchParams.set("week_start", cfg.weekStart);
    if (cfg.startDate) url.searchParams.set("start_date", cfg.startDate);
    if (cfg.endDate) url.searchParams.set("end_date", cfg.endDate);
    // start/end 已是页面层计算后的有效区间；再叠加 offset 会导致区间二次偏移
    if (!hasEffectiveRange && typeof cfg.offset !== "undefined") url.searchParams.set("offset", String(cfg.offset));
    if (cfg.version) url.searchParams.set("version", String(cfg.version));
    const fetchTimeoutMs = parsePositiveInt(cfg.fetchTimeoutMs, 12000);

    const reqId = (_perfState.activeRequestId || 0) + 1;
    _perfState.activeRequestId = reqId;
    const reqUrl = url.toString();
    let payload;
    try {
      const resp = await _withFetchTimeout(reqUrl, fetchTimeoutMs);
      if (!resp || !resp.ok) {
        throw new Error(`甘特图数据请求失败（HTTP ${resp ? resp.status : "0"}）`);
      }
      payload = await resp.json();
      if (reqId !== _perfState.activeRequestId) {
        return;
      }
      if (!payload || payload.success !== true) {
        const msg =
          payload && payload.error && payload.error.message ? payload.error.message : "甘特图数据获取失败。";
        throw new Error(msg);
      }
    } catch (e) {
      if (reqId !== _perfState.activeRequestId) {
        return;
      }
      const rawMsg = str(e && e.message ? e.message : e);
      const isAbortLike =
        !!(e && e.name === "AbortError") ||
        rawMsg.toLowerCase().indexOf("abort") >= 0;
      const msg = isAbortLike
        ? `甘特图数据请求超时（>${fetchTimeoutMs}ms），请稍后重试。`
        : rawMsg;
      if (errEl) errEl.textContent = msg;
      else {
        try {
          console.error("Gantt load failed:", e);
        } catch (_) {
          // ignore
        }
      }
      resetOverdueMarkerState();
      resetCalendarDegradationState();
      applyCalendarDegradationState();
      applyOverdueMarkerState();
      show(errEl, true);
      return;
    }

    const data = payload.data || {};
    const tasks = Array.isArray(data.tasks) ? data.tasks : [];
    state.degraded = data.degraded === true;
    state.degradationEvents = Array.isArray(data.degradation_events) ? data.degradation_events : [];
    state.degradationCounters = data.degradation_counters && typeof data.degradation_counters === "object"
      ? data.degradation_counters
      : {};
    state.emptyReason = str(data.empty_reason || "");
    state.allTasks = tasks;
    state.overdueMarkersDegraded = data.overdue_markers_degraded === true;
    state.overdueMarkersPartial = data.overdue_markers_partial === true;
    state.overdueMarkersMessage = str(data.overdue_markers_message || "");
    applyCalendarDegradationState();
    initCriticalChain(data.critical_chain || null);
    initCalendarDays(data.calendar_days || null);
    refreshFilterSelectOptions();

    applyUiFromUrl();
    applyOverdueMarkerState();
    bindUi();
    readUi();
    persistUiToUrl();
    render();
  }

  ns.loadAndRender = loadAndRender;

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", loadAndRender);
  } else {
    loadAndRender();
  }
})();

