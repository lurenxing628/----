(function () {
  var ns = window.__APS_GANTT__ = window.__APS_GANTT__ || {};
  var api = ns.contract || {};
  if (api._inited) return;
  api._inited = true;

  function str(value) {
    return value === null || typeof value === "undefined" ? "" : String(value);
  }

  function norm(value) {
    return str(value).trim();
  }

  function escapeHtml(value) {
    var text = str(value);
    if (!text) return "";
    if (!/[&<>"']/.test(text)) return text;
    return text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function _normalizeVisibleIdSet(visibleIdSet) {
    if (visibleIdSet instanceof Set) return visibleIdSet;
    var out = new Set();
    var list = Array.isArray(visibleIdSet) ? visibleIdSet : [];
    for (var i = 0; i < list.length; i += 1) {
      var value = norm(list[i]);
      if (value) out.add(value);
    }
    return out;
  }

  function normalizeCriticalChain(raw) {
    var src = raw && raw.__apsNormalizedCriticalChain === true ? raw : (raw || {});
    var idsRaw = Array.isArray(src.ids) ? src.ids : [];
    var edgesRaw = Array.isArray(src.edges) ? src.edges : [];
    var ids = [];
    var idSet = new Set();
    var prevByTo = new Map();
    var edgeMetaByTo = new Map();
    var edges = [];

    for (var i = 0; i < idsRaw.length; i += 1) {
      var id = norm(idsRaw[i]);
      if (!id || idSet.has(id)) continue;
      idSet.add(id);
      ids.push(id);
    }

    for (var j = 0; j < edgesRaw.length; j += 1) {
      var edge = edgesRaw[j] || {};
      var from = norm(edge.from);
      var to = norm(edge.to);
      if (!from || !to) continue;
      var meta = {
        from: from,
        to: to,
        edge_type: norm(edge.edge_type) || "unknown",
        reason: norm(edge.reason) || "控制前驱",
        gap_minutes: edge.gap_minutes,
      };
      prevByTo.set(to, from);
      edgeMetaByTo.set(to, meta);
      edges.push(meta);
    }

    var available = src.available !== false;
    var renderIdSet = available ? idSet : new Set();
    var renderPrevByTo = available ? prevByTo : new Map();
    var renderEdgeMetaByTo = available ? edgeMetaByTo : new Map();

    return {
      __apsNormalizedCriticalChain: true,
      ids: ids,
      edges: edges,
      makespan_end: norm(src.makespan_end) || null,
      available: available,
      reason: norm(src.reason),
      cache_hit: src.cache_hit === true,
      idSet: renderIdSet,
      prevByTo: renderPrevByTo,
      edgeMetaByTo: renderEdgeMetaByTo,
    };
  }

  function applyCriticalChainToState(state, raw) {
    var cc = normalizeCriticalChain(raw);
    if (!state || typeof state !== "object") return cc;
    state.critical = {
      ids: cc.ids.slice(),
      edges: cc.edges.slice(),
      makespan_end: cc.makespan_end,
      available: cc.available,
      reason: cc.reason,
      cache_hit: cc.cache_hit,
    };
    state.ccIdSet = cc.idSet;
    state.ccPrevByTo = cc.prevByTo;
    state.ccEdgeMetaByTo = cc.edgeMetaByTo;
    return cc;
  }

  function getCriticalChainUnavailableMessage(critical) {
    var cc = normalizeCriticalChain(critical);
    if (cc.available !== false) return "";
    var prefix = "关键链暂不可用";
    var reason = publicCriticalChainReason(cc.reason);
    if (reason) {
      prefix += "（" + reason + "）";
    }
    return prefix + "，当前仅展示普通甘特任务与资源排程，不显示关键链控制前驱箭头与外框高亮。";
  }

  function publicCriticalChainReason(reason) {
    var text = norm(reason);
    if (!text) return "";
    if (text === "repo_exception") return "关键链计算异常";
    if (text === "unknown") return "状态未知";
    if (/^[A-Za-z0-9_.:-]+$/.test(text)) return "状态异常";
    return text;
  }

  function getArrowModeLabel(depsMode, critical) {
    if (depsMode === "critical") {
      return getCriticalChainUnavailableMessage(critical)
        ? "关键链控制前驱箭头（当前停用）"
        : "关键链控制前驱箭头";
    }
    if (depsMode === "process") return "完整工艺依赖箭头";
    return "无";
  }

  function getCriticalEdgeTypeLabel(edgeType) {
    var text = norm(edgeType);
    if (text === "process") return "工艺前驱";
    if (text === "machine") return "设备前驱";
    if (text === "operator") return "人员前驱";
    return "控制前驱";
  }

  function resolveDependencies(task, visibleIdSet, depsMode, critical) {
    var taskId = norm(task && task.id);
    var visible = _normalizeVisibleIdSet(visibleIdSet);
    var cc = normalizeCriticalChain(critical);

    if (depsMode === "critical") {
      if (cc.available === false) return "";
      var pred = cc.prevByTo.get(taskId);
      return pred && (!visible.size || visible.has(pred)) ? pred : "";
    }

    if (depsMode === "process") {
      var rawDeps = task && task.dependencies;
      var list = Array.isArray(rawDeps)
        ? rawDeps
        : (norm(rawDeps) ? norm(rawDeps).split(",") : []);
      var out = [];
      for (var i = 0; i < list.length; i += 1) {
        var dep = norm(list[i]);
        if (!dep) continue;
        if (visible.size > 0 && !visible.has(dep)) continue;
        out.push(dep);
      }
      return out.join(",");
    }

    return "";
  }

  function buildRenderTasks(taskList, depsMode, critical) {
    var list = Array.isArray(taskList) ? taskList : [];
    var visibleIds = new Set();
    var out = [];

    for (var i = 0; i < list.length; i += 1) {
      var id = norm(list[i] && list[i].id);
      if (id) visibleIds.add(id);
    }

    for (var j = 0; j < list.length; j += 1) {
      var task0 = list[j] || {};
      var task = Object.assign({}, task0);
      task.meta = Object.assign({}, task0.meta || {});
      task.meta._raw_name = str(task0.name || "");
      task.name = escapeHtml(task.meta._raw_name);
      task.dependencies = resolveDependencies(task0, visibleIds, depsMode, critical);
      out.push(task);
    }

    return out;
  }

  function getCriticalStatusLabel(critical) {
    var cc = normalizeCriticalChain(critical);
    if (cc.available === false) {
      var reason = publicCriticalChainReason(cc.reason);
      return reason ? ("关键链暂不可用（" + reason + "）") : "关键链暂不可用";
    }
    return "关键链可用";
  }

  function findDegradationEvent(events, code) {
    var target = norm(code);
    var list = Array.isArray(events) ? events : [];
    for (var i = 0; i < list.length; i += 1) {
      var event = list[i] || {};
      if (norm(event.code) === target) return event;
    }
    return null;
  }

  function degradationCount(counters, code) {
    var target = norm(code);
    var src = counters && typeof counters === "object" ? counters : {};
    return Number(src[target] || 0);
  }

  function isCalendarLoadFailed(payload) {
    var src = payload && typeof payload === "object" ? payload : {};
    var events = Array.isArray(src.degradationEvents) ? src.degradationEvents : (
      Array.isArray(src.degradation_events) ? src.degradation_events : []
    );
    var counters = src.degradationCounters && typeof src.degradationCounters === "object"
      ? src.degradationCounters
      : (src.degradation_counters && typeof src.degradation_counters === "object" ? src.degradation_counters : {});
    var emptyReason = norm(src.emptyReason || src.empty_reason);
    return degradationCount(counters, "calendar_load_failed") > 0
      || emptyReason === "calendar_load_failed"
      || !!findDegradationEvent(events, "calendar_load_failed");
  }

  function shouldUseFallbackCalendarDays(payload) {
    return !isCalendarLoadFailed(payload);
  }

  function buildDegradationMessages(payload, critical) {
    var src = payload && typeof payload === "object" ? payload : {};
    var events = Array.isArray(src.degradationEvents) ? src.degradationEvents : (
      Array.isArray(src.degradation_events) ? src.degradation_events : []
    );
    var counters = src.degradationCounters && typeof src.degradationCounters === "object"
      ? src.degradationCounters
      : (src.degradation_counters && typeof src.degradation_counters === "object" ? src.degradation_counters : {});
    var emptyReason = norm(src.emptyReason || src.empty_reason);
    var cc = critical || src.critical || src.critical_chain || null;

    var messages = [];
    var calendarEvent = findDegradationEvent(events, "calendar_load_failed");
    var calendarFailed = isCalendarLoadFailed(src);
    var badTimeSkipped = degradationCount(counters, "bad_time_row_skipped");
    var criticalChainUnavailable = degradationCount(counters, "critical_chain_unavailable") > 0
      || (normalizeCriticalChain(cc).available === false);
    var allFiltered = emptyReason === "all_rows_filtered_by_invalid_time";

    if (calendarFailed) {
      messages.push("工作日历加载失败，当前不显示假期/停工背景标注。");
    }

    if (allFiltered) {
      messages.push("当前区间存在时间非法的排程数据，已全部过滤，请检查排产结果。");
    } else if (badTimeSkipped > 0) {
      messages.push("已过滤 " + badTimeSkipped + " 条时间不合法的排程记录。");
    }

    if (criticalChainUnavailable) {
      var criticalMessage = getCriticalChainUnavailableMessage(cc);
      if (!criticalMessage) {
        criticalMessage = "关键链暂不可用，当前仅展示普通甘特任务与资源排程，不显示关键链控制前驱箭头与外框高亮。";
      }
      messages.push(criticalMessage);
    }

    return messages;
  }

  function getOverdueWarningMessage(payload) {
    var src = payload && typeof payload === "object" ? payload : {};
    var degraded = src.overdueMarkersDegraded === true || src.overdue_markers_degraded === true;
    var partial = (src.overdueMarkersPartial === true || src.overdue_markers_partial === true) && !degraded;
    if (!degraded && !partial) return "";
    var message = norm(src.overdueMarkersMessage || src.overdue_markers_message);
    if (message) return message;
    return partial
      ? "部分超期标记可能不完整，当前仍按已识别条目标记。"
      : "超期标记可能不完整，请稍后重试或查看系统历史。";
  }

  function getCriticalTooltip(task, critical) {
    var cc = normalizeCriticalChain(critical);
    var unavailableMessage = getCriticalChainUnavailableMessage(cc);
    var taskId = norm(task && task.id);
    var isCritical = cc.available !== false && cc.idSet.has(taskId);
    var meta = taskId ? cc.edgeMetaByTo.get(taskId) : null;

    return {
      available: cc.available !== false,
      unavailableMessage: unavailableMessage,
      isCritical: isCritical,
      statusLabel: cc.available === false ? "不可用" : (isCritical ? "是" : "否"),
      predecessorText: isCritical && meta ? meta.from : "-",
      edgeTypeText: isCritical && meta ? getCriticalEdgeTypeLabel(meta.edge_type) : "-",
      reasonText: cc.available === false
        ? unavailableMessage
        : (isCritical && meta ? (meta.reason || "控制前驱") : "-"),
      gapText: isCritical && meta && meta.gap_minutes !== null && typeof meta.gap_minutes !== "undefined"
        ? str(meta.gap_minutes)
        : "-",
    };
  }

  function getHelpItems(critical, payload) {
    var unavailableMessage = getCriticalChainUnavailableMessage(critical);
    var calendarFailed = isCalendarLoadFailed(payload || {});
    var items = [
      "颜色：默认按批次，同批次同色；可切换按优先级/来源/状态。",
      calendarFailed
        ? "假期/停工：工作日历加载失败，当前不显示假期/停工背景标注。"
        : "假期/停工：背景淡红色竖条标注（口径：全局工作日历；未配置时周末默认视为假期）。",
      "红边：该批次在该版本中被判定为超期。",
      unavailableMessage
        ? "关键链：当前不可用，不显示关键链任务外框高亮。"
        : "关键链：任务条外框高亮，表示该任务仍在当前版本关键链上。",
      "虚线边框：外协任务。",
      unavailableMessage
        ? "箭头：关键链控制前驱当前停用；可切换完整工艺依赖或关闭。"
        : "箭头：默认展示关键链控制前驱；可切换完整工艺依赖或关闭。",
      "聚焦：点击任务条可聚焦同批次任务，再次点击取消。",
      "筛选：支持批次/设备/人员筛选，并可叠加仅超期/仅外协。",
      "关键链口径：关键链按全版本排程计算（不随周窗口截断）；综合工艺前驱与资源前驱（设备/人员）选取控制前驱回溯得到。",
    ];
    if (unavailableMessage) {
      items.push("关键链降级：" + unavailableMessage);
    }
    return items;
  }

  function renderHelpList(target, critical, payload) {
    if (!target) return;
    while (target.firstChild) {
      target.removeChild(target.firstChild);
    }
    var items = getHelpItems(critical, payload);
    var useListItems = String(target.tagName || "").toLowerCase() === "ul";
    for (var i = 0; i < items.length; i += 1) {
      var node = document.createElement(useListItems ? "li" : "div");
      node.textContent = items[i];
      target.appendChild(node);
    }
  }

  api.str = str;
  api.norm = norm;
  api.escapeHtml = escapeHtml;
  api.normalizeCriticalChain = normalizeCriticalChain;
  api.applyCriticalChainToState = applyCriticalChainToState;
  api.getCriticalChainUnavailableMessage = getCriticalChainUnavailableMessage;
  api.getArrowModeLabel = getArrowModeLabel;
  api.getCriticalEdgeTypeLabel = getCriticalEdgeTypeLabel;
  api.resolveDependencies = resolveDependencies;
  api.buildRenderTasks = buildRenderTasks;
  api.getCriticalStatusLabel = getCriticalStatusLabel;
  api.findDegradationEvent = findDegradationEvent;
  api.degradationCount = degradationCount;
  api.isCalendarLoadFailed = isCalendarLoadFailed;
  api.shouldUseFallbackCalendarDays = shouldUseFallbackCalendarDays;
  api.buildDegradationMessages = buildDegradationMessages;
  api.getOverdueWarningMessage = getOverdueWarningMessage;
  api.getCriticalTooltip = getCriticalTooltip;
  api.getHelpItems = getHelpItems;
  api.renderHelpList = renderHelpList;
  ns.contract = api;
})();
