(function () {
  var ns = window.__APS_GANTT__;
  if (!ns) return;
  if (!ns._inited) ns._inited = {};
  if (ns._inited.render) return;
  ns._inited.render = true;

  var $ = ns.$;
  var show = ns.show;
  var str = ns.str;
  var escapeHtml = ns.escapeHtml;
  var norm = ns.norm;
  var includesI = ns.includesI;
  var state = ns.state;
  var outlineApi = ns.outline;
  var contractApi = ns.contract;
  var zoomApi = ns.zoom;
  var adapterApi = ns.adapter;
  var popupApi = ns.popup;
  var decorationApi = ns.decorations;

  if (typeof $ !== "function") return;
  if (typeof show !== "function") return;
  if (typeof str !== "function") return;
  if (typeof escapeHtml !== "function") return;
  if (typeof norm !== "function") return;
  if (typeof includesI !== "function") return;
  if (!outlineApi || !contractApi || !zoomApi || !adapterApi || !popupApi || !decorationApi || !state) return;

  var installCriticalOutlineSyncAdapter = outlineApi.installCriticalOutlineSyncAdapter;
  var buildContractTasks = contractApi.buildRenderTasks;
  var getZoomSpec = zoomApi.getZoomSpec;
  var getGanttScale = zoomApi.getGanttScale;
  var validateZoomRange = zoomApi.validateZoomRange;
  var currentZoomLevel = zoomApi.currentZoomLevel;
  var createGantt = adapterApi.createGantt;
  var buildTaskPopupHtml = popupApi.buildTaskPopupHtml;
  var beginRenderPass = decorationApi.beginRenderPass;
  var buildTaskMapById = decorationApi.buildTaskMapById;
  var decorateStaticAfterRender = decorationApi.decorateStaticAfterRender;
  var resetDecorCache = decorationApi.resetCache;

  if (typeof installCriticalOutlineSyncAdapter !== "function") return;
  if (typeof buildContractTasks !== "function") return;
  if (typeof getZoomSpec !== "function") return;
  if (typeof getGanttScale !== "function") return;
  if (typeof validateZoomRange !== "function") return;
  if (typeof currentZoomLevel !== "function") return;
  if (typeof createGantt !== "function") return;
  if (typeof buildTaskPopupHtml !== "function") return;
  if (typeof beginRenderPass !== "function") return;
  if (typeof buildTaskMapById !== "function") return;
  if (typeof decorateStaticAfterRender !== "function") return;
  if (typeof resetDecorCache !== "function") return;
  if (typeof ns.updateLegend !== "function") return;
  if (typeof ns.safeDecorateDynamic !== "function") return;

  function updateLegend() {
    ns.updateLegend();
  }

  function safeDecorateDynamic(opts) {
    ns.safeDecorateDynamic(opts);
  }

  function applyFilters(all) {
    const cfg = state.cfg || {};
    const view = norm(cfg.view) || "machine";
    const list = Array.isArray(all) ? all : [];
    const out = [];
    for (let i = 0; i < list.length; i++) {
      const t = list[i] || {};
      const meta = t.meta || {};

      if (state.ui.onlyOverdue && meta.is_overdue !== true) continue;
      if (state.ui.onlyExternal && norm(meta.source) !== "external") continue;
      if (state.ui.filterBatch && !includesI(meta.batch_id, state.ui.filterBatch)) continue;

      if (state.ui.filterResource) {
        if (view === "machine") {
          if (!includesI(meta.machine_id, state.ui.filterResource) && !includesI(meta.machine, state.ui.filterResource)) continue;
        } else if (!includesI(meta.operator_id, state.ui.filterResource) && !includesI(meta.operator, state.ui.filterResource)) {
          continue;
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

  function countDependencies(tasks) {
    let count = 0;
    const list = Array.isArray(tasks) ? tasks : [];
    for (let i = 0; i < list.length; i++) {
      const deps = list[i] && list[i].dependencies;
      if (Array.isArray(deps)) count += deps.length;
      else if (typeof deps === "string" && deps.trim()) count += deps.split(",").filter(Boolean).length;
    }
    return count;
  }

  function parseLocalTaskDate(value) {
    if (value instanceof Date && !isNaN(value.getTime())) return value;
    const text = norm(value);
    if (!text) return null;
    const match = /^(\d{4})-(\d{1,2})-(\d{1,2})(?:[ T](\d{1,2}):(\d{1,2})(?::(\d{1,2})(?:\.\d+)?)?)?/.exec(text);
    if (match) {
      return new Date(
        Number(match[1]),
        Number(match[2]) - 1,
        Number(match[3]),
        Number(match[4] || 0),
        Number(match[5] || 0),
        Number(match[6] || 0),
        0
      );
    }
    const parsed = new Date(text);
    return isNaN(parsed.getTime()) ? null : parsed;
  }

  function localDateText(value) {
    if (!(value instanceof Date) || isNaN(value.getTime())) return "";
    const month = value.getMonth() + 1;
    const day = value.getDate();
    return [
      value.getFullYear(),
      month < 10 ? "0" + month : String(month),
      day < 10 ? "0" + day : String(day),
    ].join("-");
  }

  function localEndDateText(value) {
    if (!(value instanceof Date) || isNaN(value.getTime())) return "";
    if (value.getHours() === 0 && value.getMinutes() === 0 && value.getSeconds() === 0 && value.getMilliseconds() === 0) {
      return localDateText(new Date(value.getTime() - 1));
    }
    return localDateText(value);
  }

  function taskDateBounds(tasks) {
    const list = Array.isArray(tasks) ? tasks : [];
    let minDate = null;
    let maxDate = null;
    for (let i = 0; i < list.length; i++) {
      const start = parseLocalTaskDate(list[i] && list[i].start);
      const end = parseLocalTaskDate(list[i] && list[i].end);
      if (start && (!minDate || start < minDate)) minDate = start;
      if (end && (!maxDate || end > maxDate)) maxDate = end;
    }
    return {
      startDate: localDateText(minDate),
      endDate: localEndDateText(maxDate),
    };
  }

  function mergeDateBounds(primaryStart, primaryEnd, secondaryStart, secondaryEnd) {
    const starts = [parseLocalTaskDate(primaryStart), parseLocalTaskDate(secondaryStart)].filter(Boolean);
    const ends = [parseLocalTaskDate(primaryEnd), parseLocalTaskDate(secondaryEnd)].filter(Boolean);
    const start = starts.length ? starts.reduce((a, b) => (b < a ? b : a), starts[0]) : null;
    const end = ends.length ? ends.reduce((a, b) => (b > a ? b : a), ends[0]) : null;
    return {
      startDate: localDateText(start),
      endDate: localDateText(end),
    };
  }

  function setZoomWarning(message, visible) {
    const el = $("ganttZoomWarning");
    if (!el) return;
    el.textContent = message || "";
    show(el, !!visible);
  }

  function validateRenderZoom(tasks) {
    const cfg = state.cfg || {};
    const taskBounds = taskDateBounds(tasks);
    const rangeBounds = mergeDateBounds(
      cfg.startDate || cfg.weekStart || cfg.versionSpanStart || "",
      cfg.endDate || cfg.versionSpanEnd || cfg.weekStart || "",
      taskBounds.startDate,
      taskBounds.endDate
    );
    const result = validateZoomRange({
      zoomLevel: currentZoomLevel(state.ui),
      startDate: rangeBounds.startDate,
      endDate: rangeBounds.endDate,
      taskCount: Array.isArray(tasks) ? tasks.length : 0,
      dependencyCount: countDependencies(tasks),
      holidayMarkerCount: Array.isArray(state.calendarDays) ? state.calendarDays.length : 0,
    });
    if (result && result.message) setZoomWarning(result.message, true);
    else if (state.ui && state.ui.zoomWarningMessage) setZoomWarning(state.ui.zoomWarningMessage, true);
    else setZoomWarning("", false);
    return result;
  }

  function scrollToAnchor(gantt) {
    const cfg = state.cfg || {};
    try {
      const container = document.querySelector("#gantt .gantt-container");
      if (container && gantt && gantt.gantt_start) {
        const anchor = norm(cfg.startDate || cfg.weekStart || "");
        const target = new Date(anchor + " 00:00:00");
        const scale = getGanttScale(gantt);
        const diffMinutes = (target.getTime() - gantt.gantt_start.getTime()) / 60000.0;
        const px = (diffMinutes / scale.stepMinutes) * scale.columnWidth - scale.columnWidth;
        container.scrollLeft = Math.max(0, Math.floor(px));
      }
    } catch (_) {
      // 不阻断渲染
    }
  }

  function installPopupAutoFit(gantt) {
    if (window.__APS_GANTT_POPUP_FIT__ && typeof window.__APS_GANTT_POPUP_FIT__.install === "function") {
      window.__APS_GANTT_POPUP_FIT__.install(gantt);
    }
  }

  function emptyStateMessage() {
    const message = str(state.emptyMessage || "");
    if (message) return message;
    const reason = norm(state.emptyReason);
    const allTasks = Array.isArray(state.allTasks) ? state.allTasks : [];
    if (reason === "all_rows_filtered_by_invalid_time") {
      const counters = state.degradationCounters && typeof state.degradationCounters === "object" ? state.degradationCounters : {};
      const badTimeSkipped = Number(counters.bad_time_row_skipped || 0);
      if (badTimeSkipped > 0) {
        return "已过滤 " + badTimeSkipped + " 条开始或结束时间写法不对的排程记录。当前区间没有可显示排程，请到系统管理里的排产历史查看这次排产的详细提醒。";
      }
      return "当前区间的排程开始或结束时间写法不对，已全部过滤，请到系统管理里的排产历史查看这次排产的详细提醒。";
    }
    if (allTasks.length > 0) return "当前筛选条件下暂无可显示任务。";
    return "暂无排程数据（该周/该版本）。";
  }

  function render() {
    const emptyEl = $("ganttEmpty");
    const errEl = $("ganttError");
    show(errEl, false);

    state.filteredTasks = applyFilters(state.allTasks);
    if (!state.filteredTasks.length) {
      if (emptyEl) emptyEl.textContent = emptyStateMessage();
      show(emptyEl, true);
      const host = $("gantt");
      if (host) {
        host.innerHTML = "";
        host.classList.remove("aps-has-focus");
      }
      state.gantt = null;
      state.currentTasks = [];
      resetDecorCache();
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
    const zoomCheck = validateRenderZoom(tasks);
    if (zoomCheck && zoomCheck.ok === false) {
      state.gantt = null;
      resetDecorCache();
      updateLegend();
      return;
    }
    const zoomSpec = getZoomSpec(currentZoomLevel(state.ui));
    if (host.dataset) {
      host.dataset.ganttMode = state.ui && state.ui.mode ? state.ui.mode : "view";
      host.dataset.zoomLevel = zoomSpec.level || "day";
    }

    const gantt = createGantt({
      selector: "#gantt",
      tasks: tasks,
      mode: (state.ui && state.ui.mode) || host.dataset.ganttMode || "view",
      zoomLevel: zoomSpec.level,
      fallbackViewMode: state.ui && state.ui.viewMode ? state.ui.viewMode : "Day",
      onClick: function (task) {
        const meta = task && task.meta ? task.meta : {};
        const bid = norm(meta.batch_id);
        if (!bid) return;
        state.focusBatch = state.focusBatch === bid ? "" : bid;
        // 纯视觉交互：只做增量装饰（Win7 避免全量重建）
        safeDecorateDynamic({ updateLegend: false });
      },
      customPopupHtml: function (task) {
        return buildTaskPopupHtml(task, state.critical);
      },
    });

    state.gantt = gantt;
    installPopupAutoFit(gantt);
    installCriticalOutlineSyncAdapter(gantt);
    scrollToAnchor(gantt);
    // new Gantt()：全量渲染 + 静态装饰 + 动态装饰（一次）
    beginRenderPass();
    const byId = buildTaskMapById();
    decorateStaticAfterRender(byId);
    safeDecorateDynamic({ forceAll: true, byId: byId, updateLegend: true });
  }

  ns.applyFilters = applyFilters;
  ns.render = render;
})();
