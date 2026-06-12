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
  var contract = ns.contract;
  var popup = ns.popup;

  function _showEarlyError(message) {
    var msg = String(message || "甘特图页面脚本加载不完整，请刷新页面后重试。");
    var errEl = document.getElementById("ganttError");
    var emptyEl = document.getElementById("ganttEmpty");
    var host = document.getElementById("gantt");
    if (errEl) {
      errEl.textContent = msg;
      if (errEl.classList) errEl.classList.remove("is-hidden");
      if (errEl.style) errEl.style.display = "block";
    }
    if (emptyEl) {
      if (emptyEl.classList) emptyEl.classList.add("is-hidden");
      if (emptyEl.style) emptyEl.style.display = "none";
    }
    if (host) host.innerHTML = "";
  }

  function _reportMissingDeps(missing) {
    var detail = String((missing || []).join(", "));
    var msg = "甘特图页面脚本加载不完整，请刷新页面后重试。";
    _showEarlyError(msg);
    if (typeof reportClientError === "function") {
      reportClientError(msg, detail ? new Error(detail) : undefined);
      return;
    }
    try { console.error(msg, detail); } catch (_) {}
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
  if (!contract || typeof contract.applyCriticalChainToState !== "function") {
    missingDeps.push("contract.applyCriticalChainToState");
  }
  if (!contract || typeof contract.getCriticalChainUnavailableMessage !== "function") {
    missingDeps.push("contract.getCriticalChainUnavailableMessage");
  }
  if (!contract || typeof contract.buildDegradationMessages !== "function") {
    missingDeps.push("contract.buildDegradationMessages");
  }
  if (!contract || typeof contract.getOverdueWarningMessage !== "function") {
    missingDeps.push("contract.getOverdueWarningMessage");
  }
  if (!contract || typeof contract.renderHelpList !== "function") {
    missingDeps.push("contract.renderHelpList");
  }
  if (!outline || typeof outline.setCriticalOutlineEnabled !== "function") {
    missingDeps.push("outline.setCriticalOutlineEnabled");
  }
  if (!outline || typeof outline.installCriticalOutlineSyncAdapter !== "function") {
    missingDeps.push("outline.installCriticalOutlineSyncAdapter");
  }
  if (!popup || typeof popup.buildTaskPopupHtml !== "function") {
    missingDeps.push("popup.buildTaskPopupHtml");
  }
  if (missingDeps.length > 0) {
    _reportMissingDeps(missingDeps);
    return;
  }

  function initCriticalChain(critical) {
    contract.applyCriticalChainToState(state, critical);
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

  function _buildDegradationMessages() {
    return contract.buildDegradationMessages(
      {
        degradationEvents: state.degradationEvents,
        degradationCounters: state.degradationCounters,
        emptyReason: state.emptyReason,
      },
      state.critical
    );
  }

  function applyCalendarDegradationState() {
    const warningEl = $("ganttDegradationWarning");
    const messages = _buildDegradationMessages();
    let message = messages.length > 0 ? messages.join(" ") : "";
    if (!message && state.degraded === true) {
      message = "这次排产有些提醒暂时没法直接说明，甘特图先按能识别的数据展示。请到系统管理里的排产历史查看详细提醒。";
    }
    const visible = !!message;

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
    const message = contract.getOverdueWarningMessage(
      {
        overdueMarkersDegraded: state.overdueMarkersDegraded,
        overdueMarkersPartial: state.overdueMarkersPartial,
        overdueMarkersMessage: state.overdueMarkersMessage,
      }
    );
    const visible = !!message;

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

  const DATA_FORMAT_ERROR = "甘特图数据格式不对，请刷新后重试或联系维护人员。";

  function _isObject(value) {
    return !!value && typeof value === "object" && !Array.isArray(value);
  }

  function _payloadErrorMessage(payload, fallback) {
    if (_isObject(payload) && _isObject(payload.error)) {
      const message = str(payload.error.message || "");
      if (message) return message;
    }
    return fallback;
  }

  async function _readJsonErrorBody(resp) {
    if (!resp || typeof resp.json !== "function") return null;
    try {
      return await resp.json();
    } catch (_) {
      return null;
    }
  }

  function _validatePayload(payload) {
    if (!_isObject(payload)) {
      throw new Error(DATA_FORMAT_ERROR);
    }
    if (payload.success !== true) {
      throw new Error(_payloadErrorMessage(payload, "甘特图数据获取失败。"));
    }
    if (!_isObject(payload.data) || !Array.isArray(payload.data.tasks)) {
      throw new Error(DATA_FORMAT_ERROR);
    }
    return payload.data;
  }

  function _showBlockingError(emptyEl, errEl, message) {
    const msg = str(message || "甘特图加载失败，请刷新后重试。");
    if (errEl) errEl.textContent = msg;
    else {
      try {
        console.error("Gantt load failed:", msg);
      } catch (_) {
        // ignore
      }
    }
    const host = $("gantt");
    if (host) {
      host.innerHTML = "";
      host.classList.remove("aps-has-focus");
    }
    state.gantt = null;
    state.allTasks = [];
    state.currentTasks = [];
    state.filteredTasks = [];
    resetOverdueMarkerState();
    resetCalendarDegradationState();
    applyCalendarDegradationState();
    applyOverdueMarkerState();
    show(emptyEl, false);
    show(errEl, true);
  }

  function _renderErrorMessage(error) {
    const rawMsg = str(error && error.message ? error.message : error);
    if (!rawMsg) return "甘特图显示异常，请刷新后重试。";
    if (rawMsg.indexOf("Gantt DOM mismatch") >= 0) {
      return "甘特图显示异常，请刷新后重试。";
    }
    if (rawMsg.indexOf("甘特图显示组件没有加载完成") >= 0) {
      return "甘特图显示组件没有加载完成，请刷新后重试。";
    }
    if (!/[\u4e00-\u9fff]/.test(rawMsg)) {
      return "甘特图显示异常，请刷新后重试。";
    }
    return rawMsg;
  }

  function _prepareVisibleState(data, emptyEl, errEl) {
    const tasks = data.tasks;
    state.degraded = data.degraded === true;
    state.degradationEvents = Array.isArray(data.degradation_events) ? data.degradation_events : [];
    state.degradationCounters = data.degradation_counters && typeof data.degradation_counters === "object"
      ? data.degradation_counters
      : {};
    state.emptyReason = str(data.empty_reason || "");
    state.emptyMessage = str(data.empty_message || "");
    state.versionTimeSpan = data.version_time_span || null;
    state.allTasks = tasks;
    if (ns.chainWalk) {
      // 索引每次数据加载后重建（allTasks 换代）；绑定幂等只生效一次
      ns.chainWalk.rebuildChainIndex();
      ns.chainWalk.bindChainWalk();
    }
    state.overdueMarkersDegraded = data.overdue_markers_degraded === true;
    state.overdueMarkersPartial = data.overdue_markers_partial === true;
    state.overdueMarkersMessage = str(data.overdue_markers_message || "");
    initCriticalChain(data.critical_chain || null);
    applyCalendarDegradationState();
    contract.renderHelpList($("ganttHelpList"), state.critical || null, {
      degradationEvents: state.degradationEvents,
      degradationCounters: state.degradationCounters,
      emptyReason: state.emptyReason,
    });
    initCalendarDays(data.calendar_days || null);
    refreshFilterSelectOptions();

    applyUiFromUrl();
    applyOverdueMarkerState();
    bindUi();
    readUi();
    persistUiToUrl();
    render();
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
        planRole: ds.planRole || "",
        scenarioId: ds.scenarioId || "",
        scenarioPreview: ds.scenarioPreview || "",
        scenarioLabel: ds.scenarioLabel || "",
        ganttMode: ds.ganttMode || "view",
        zoomLevel: ds.zoomLevel || "day",
        hasHistory: ds.hasHistory || "",
        versionSpanStart: ds.versionSpanStart || "",
        versionSpanEnd: ds.versionSpanEnd || "",
        rangeSource: ds.rangeSource || "",
        fetchTimeoutMs: ds.fetchTimeoutMs || ds.fetchTimeout || "",
      };
    })();
    state.cfg = cfg;
    state.ui.mode = norm(cfg.ganttMode || "view") || "view";
    state.ui.zoomLevel = norm(cfg.zoomLevel || "day") || "day";
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
          errEl.textContent = "甘特图配置不完整：未找到数据接口，请刷新页面后重试。";
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
        errEl.textContent = "甘特图页面打开不完整，暂时读不到排程数据，请刷新页面后重试。";
      }
      reportClientError("甘特图数据接口地址填写不对", e);
      resetCalendarDegradationState();
      applyCalendarDegradationState();
      resetOverdueMarkerState();
      applyOverdueMarkerState();
      show(errEl, true);
      return;
    }
    const usesVersionSpanRange = cfg.rangeSource === "version_span";
    const hasEffectiveRange = !!(cfg.startDate || cfg.endDate) && !usesVersionSpanRange;
    if (cfg.view) url.searchParams.set("view", cfg.view);
    if (hasEffectiveRange) {
      if (cfg.startDate) url.searchParams.set("start_date", cfg.startDate);
      if (cfg.endDate) url.searchParams.set("end_date", cfg.endDate);
    } else if (!usesVersionSpanRange) {
      if (cfg.weekStart) url.searchParams.set("week_start", cfg.weekStart);
      if (typeof cfg.offset !== "undefined") url.searchParams.set("offset", String(cfg.offset));
    }
    if (cfg.version) url.searchParams.set("version", String(cfg.version));
    if (cfg.planRole) url.searchParams.set("plan_role", String(cfg.planRole));
    if (cfg.scenarioId) url.searchParams.set("scenario_id", String(cfg.scenarioId));
    const fetchTimeoutMs = parsePositiveInt(cfg.fetchTimeoutMs, 12000);

    const reqId = (_perfState.activeRequestId || 0) + 1;
    _perfState.activeRequestId = reqId;
    const reqUrl = url.toString();
    let payload;
    let data;
    try {
      const resp = await _withFetchTimeout(reqUrl, fetchTimeoutMs);
      if (!resp || !resp.ok) {
        const errorPayload = await _readJsonErrorBody(resp);
        throw new Error(
          _payloadErrorMessage(errorPayload, `甘特图数据请求失败（HTTP ${resp ? resp.status : "0"}）`)
        );
      }
      payload = await resp.json();
      if (reqId !== _perfState.activeRequestId) {
        return;
      }
      data = _validatePayload(payload);
    } catch (e) {
      if (reqId !== _perfState.activeRequestId) {
        return;
      }
      const rawMsg = str(e && e.message ? e.message : e);
      const isAbortLike =
        !!(e && e.name === "AbortError") ||
        rawMsg.toLowerCase().indexOf("abort") >= 0;
      const timeoutSeconds = Math.max(1, Math.round(fetchTimeoutMs / 1000));
      const msg = isAbortLike
        ? `甘特图数据请求超过 ${timeoutSeconds} 秒，请稍后重试。`
        : rawMsg;
      _showBlockingError(emptyEl, errEl, msg);
      return;
    }

    try {
      _prepareVisibleState(data, emptyEl, errEl);
    } catch (e) {
      const msg = _renderErrorMessage(e);
      reportClientError("甘特图显示异常", e);
      _showBlockingError(emptyEl, errEl, msg);
    }
  }

  ns.loadAndRender = loadAndRender;

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", loadAndRender);
  } else {
    loadAndRender();
  }
})();
