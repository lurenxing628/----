(function () {
  var ns = window.__APS_GANTT__;
  if (!ns) return;
  if (!ns._inited) ns._inited = {};
  if (ns._inited.boot) return;
  ns._inited.boot = true;

  var $ = ns.$;
  var show = ns.show;
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

  function _reportMissingDeps(missing) {
    var msg = "甘特图脚本加载不完整，请刷新页面后重试。缺失：" + String((missing || []).join(", "));
    var errEl = document.getElementById("ganttError");
    if (errEl) {
      errEl.textContent = msg;
      if (errEl.classList) {
        errEl.classList.remove("is-hidden");
      }
      errEl.style.display = "block";
    }
    try {
      console.error(msg);
    } catch (_) {
      // ignore
    }
  }

  var missingDeps = [];
  if (typeof $ !== "function") missingDeps.push("$");
  if (typeof show !== "function") missingDeps.push("show");
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
  if (missingDeps.length > 0) {
    _reportMissingDeps(missingDeps);
    return;
  }

  function initCriticalChain(critical) {
    const cc = critical || {};
    state.critical = cc;

    const ids = Array.isArray(cc.ids) ? cc.ids : [];
    state.ccIdSet = new Set(ids.map((x) => norm(x)).filter((x) => !!x));

    const m = new Map();
    const metaMap = new Map();
    const edges = Array.isArray(cc.edges) ? cc.edges : [];
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
      resetOverdueMarkerState();
      applyOverdueMarkerState();
      if (host) host.innerHTML = "";
      return;
    }

    const dataUrl = norm(cfg && cfg.dataUrl ? cfg.dataUrl : "");
    if (!dataUrl) {
      if (errEl) {
        errEl.textContent = "甘特图配置缺失：未找到数据接口 URL（data-url；兼容 data-data-url）。";
      }
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
      applyOverdueMarkerState();
      show(errEl, true);
      return;
    }

    const data = payload.data || {};
    const tasks = Array.isArray(data.tasks) ? data.tasks : [];
    state.allTasks = tasks;
    state.overdueMarkersDegraded = data.overdue_markers_degraded === true;
    state.overdueMarkersPartial = data.overdue_markers_partial === true;
    state.overdueMarkersMessage = str(data.overdue_markers_message || "");
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

