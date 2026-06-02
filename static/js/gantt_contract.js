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

  function dedupeCriticalReason(message, reason) {
    var text = norm(message);
    var reasonText = norm(reason);
    if (!text || !reasonText) return text;
    var first = text.indexOf(reasonText);
    if (first < 0) return text;
    var next = text.indexOf(reasonText, first + reasonText.length);
    while (next >= 0) {
      text = text.slice(0, next) + text.slice(next + reasonText.length);
      next = text.indexOf(reasonText, first + reasonText.length);
    }
    return text.replace(/（\s*）/g, "").replace(/\s{2,}/g, " ").trim();
  }

  function publicCriticalPredecessorLabel(meta) {
    var label = norm(meta && (meta.from_label || meta.fromLabel));
    if (label) return label;
    var raw = norm(meta && meta.from);
    if (!raw) return "-";
    if (/^op_\d+$/i.test(raw)) return "未命名工序";
    return raw;
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
        from_label: norm(edge.from_label || edge.fromLabel),
        to_label: norm(edge.to_label || edge.toLabel),
        edge_type: norm(edge.edge_type) || "unknown",
        reason: norm(edge.reason) || "控制前驱",
        gap_minutes: edge.gap_minutes,
      };
      prevByTo.set(to, from);
      edgeMetaByTo.set(to, meta);
      edges.push(meta);
    }

    var available = src.available !== false;
    var reasonCode = norm(src.reason_code || src.reasonCode);
    var publicIds = available ? ids : [];
    var publicEdges = available ? edges : [];
    var renderIdSet = available ? idSet : new Set();
    var renderPrevByTo = available ? prevByTo : new Map();
    var renderEdgeMetaByTo = available ? edgeMetaByTo : new Map();

    return {
      __apsNormalizedCriticalChain: true,
      ids: publicIds,
      edges: publicEdges,
      makespan_end: norm(src.makespan_end) || null,
      available: available,
      reason: norm(src.reason),
      reason_code: reasonCode,
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
      reason_code: cc.reason_code,
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
    var prefix = "关键工序关系暂时看不了";
    var explicitReasonCode = critical && critical.reason_code;
    var reason = publicCriticalChainReason(cc.reason, cc.reason_code || explicitReasonCode);
    if (reason) {
      prefix += "（" + reason + "）";
    }
    return dedupeCriticalReason(
      prefix + "，当前只显示普通甘特任务和设备/人员安排，不显示关键工序关系线和高亮框。",
      reason
    );
  }

  function publicCriticalChainReason(reason, reasonCode) {
    var code = norm(reasonCode);
    if (code === "repo_exception") return "关键工序关系计算异常";
    if (code === "calc_exception") return "关键工序关系计算异常";
    if (code === "rows_exception") return "关键工序关系计算异常";
    if (code === "rows_load_exception") return "关键工序关系资料读取异常";
    if (code === "no_history") return "暂无排产历史";
    if (code === "unknown") return "状态未知";
    var text = norm(reason);
    if (!text) return "";
    if (text === "关键链计算异常") return "关键工序关系计算异常";
    if (text === "关键链数据读取异常") return "关键工序关系资料读取异常";
    var legacyUnavailable = ["关键", "链暂不可用"].join("");
    if (text === legacyUnavailable) return "关键工序关系暂时看不了";
    if (text === "repo_exception") return "关键工序关系计算异常";
    if (text === "calc_exception") return "关键工序关系计算异常";
    if (text === "rows_exception") return "关键工序关系计算异常";
    if (text === "rows_load_exception") return "关键工序关系资料读取异常";
    if (text === "no_history") return "暂无排产历史";
    if (text === "unknown") return "状态未知";
    if (/^[A-Za-z0-9_.:-]+$/.test(text)) return "状态异常";
    return text;
  }

  function getArrowModeLabel(depsMode, critical) {
    if (depsMode === "critical") {
      return getCriticalChainUnavailableMessage(critical)
        ? "关键工序关系线（当前停用）"
        : "关键工序关系线";
    }
    if (depsMode === "process") return "全部工艺关系线";
    return "无";
  }

  function getCriticalEdgeTypeLabel(edgeType) {
    var text = norm(edgeType);
    if (text === "process") return "要等上一道工序完成";
    if (text === "machine") return "同一设备前面还有任务";
    if (text === "operator") return "同一人员前面还有任务";
    return "前面任务会影响开工";
  }

  function publicCriticalEdgeReason(reason, edgeType) {
    var raw = norm(reason);
    var type = norm(edgeType);
    if (!raw || raw === "控制前驱") return getCriticalEdgeTypeLabel(type);
    if (raw === "工艺前驱" || raw === "process") return getCriticalEdgeTypeLabel("process");
    if (raw === "设备前驱" || raw === "machine") return getCriticalEdgeTypeLabel("machine");
    if (raw === "人员前驱" || raw === "operator") return getCriticalEdgeTypeLabel("operator");
    if (raw === "资源前驱（设备）") return getCriticalEdgeTypeLabel("machine");
    if (raw === "资源前驱（人员）") return getCriticalEdgeTypeLabel("operator");
    if (raw.indexOf("资源前驱") >= 0) return getCriticalEdgeTypeLabel(type);
    if (/^[A-Za-z0-9_.:-]+$/.test(raw)) return getCriticalEdgeTypeLabel(type);
    return raw;
  }

  function publicGapLabel(gapMinutes) {
    if (gapMinutes === null || typeof gapMinutes === "undefined" || gapMinutes === "") return "-";
    var num = Number(gapMinutes);
    if (isNaN(num)) return "等待时间暂无法识别";
    var text = Math.round(num) === num ? String(num) : String(Math.round(num * 100) / 100);
    if (num === 0) return "0 分钟（紧接前一道）";
    return text + " 分钟";
  }

  function publicSourceLabel(source) {
    var text = norm(source);
    if (!text) return "-";
    if (text === "internal") return "自制";
    if (text === "external") return "外协";
    if (/^[A-Za-z0-9_.:-]+$/.test(text)) return "未识别的加工方式";
    return text;
  }

  function publicPriorityLabel(priority) {
    var text = norm(priority);
    if (!text) return "-";
    if (text === "normal") return "普通";
    if (text === "urgent") return "急件";
    if (text === "critical") return "特急";
    if (text === "low") return "较低";
    if (/^[A-Za-z0-9_.:-]+$/.test(text)) return "未识别的优先级";
    return text;
  }

  function publicStatusLabel(status) {
    var text = norm(status);
    if (!text) return "-";
    if (text === "done" || text === "completed" || text === "finished") return "已完成";
    if (text === "in_progress" || text === "running") return "进行中";
    if (text === "blocked") return "阻塞";
    if (text === "pending" || text === "scheduled" || text === "not_started") return "未开始";
    if (/^[A-Za-z0-9_.:-]+$/.test(text)) return "未识别的状态";
    return text;
  }

  function _pad2(value) {
    var num = Number(value) || 0;
    return num < 10 ? ("0" + num) : String(num);
  }

  function _monthNumber(mon) {
    var text = norm(mon).toLowerCase();
    var names = {
      jan: 1, january: 1,
      feb: 2, february: 2,
      mar: 3, march: 3,
      apr: 4, april: 4,
      may: 5,
      jun: 6, june: 6,
      jul: 7, july: 7,
      aug: 8, august: 8,
      sep: 9, sept: 9, september: 9,
      oct: 10, october: 10,
      nov: 11, november: 11,
      dec: 12, december: 12,
    };
    return names[text] || 0;
  }

  function _formatDateParts(year, month, day, hour, minute) {
    return String(Number(year)) + "年" + String(Number(month)) + "月" + String(Number(day)) + "日 "
      + _pad2(hour) + ":" + _pad2(minute);
  }

  function formatChineseDateTime(value) {
    if (value === null || typeof value === "undefined" || value === "") return "-";
    if (value instanceof Date && !isNaN(value.getTime())) {
      return _formatDateParts(value.getFullYear(), value.getMonth() + 1, value.getDate(), value.getHours(), value.getMinutes());
    }
    var text = norm(value);
    if (!text) return "-";
    var iso = /^(\d{4})[-/](\d{1,2})[-/](\d{1,2})(?:[ T](\d{1,2}):(\d{1,2})(?::\d{1,2}(?:\.\d+)?)?)?/.exec(text);
    if (iso) {
      return _formatDateParts(iso[1], iso[2], iso[3], iso[4] || 0, iso[5] || 0);
    }
    var rfc = /^(?:[A-Za-z]{3},\s*)?(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{4})\s+(\d{1,2}):(\d{2})/.exec(text);
    if (rfc) {
      var month = _monthNumber(rfc[2]);
      if (month) return _formatDateParts(rfc[3], month, rfc[1], rfc[4], rfc[5]);
    }
    var parsed = new Date(text);
    if (!isNaN(parsed.getTime())) {
      return _formatDateParts(parsed.getFullYear(), parsed.getMonth() + 1, parsed.getDate(), parsed.getHours(), parsed.getMinutes());
    }
    return text;
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
      var reason = publicCriticalChainReason(cc.reason, cc.reason_code);
      return reason ? ("关键工序关系暂时看不了（" + reason + "）") : "关键工序关系暂时看不了";
    }
    return "可查看";
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
      if (badTimeSkipped > 0) {
        messages.push("已过滤 " + badTimeSkipped + " 条开始或结束时间写法不对的排程记录。当前区间没有可显示排程，请到系统管理里的排产历史查看这次排产的详细提醒。");
      } else {
        messages.push("当前区间的排程开始或结束时间写法不对，已全部过滤，请到系统管理里的排产历史查看这次排产的详细提醒。");
      }
    } else if (badTimeSkipped > 0) {
      messages.push("已过滤 " + badTimeSkipped + " 条开始或结束时间写法不对的排程记录。");
    }

    if (criticalChainUnavailable) {
      var criticalMessage = getCriticalChainUnavailableMessage(cc);
      if (!criticalMessage) {
        criticalMessage = "关键工序关系暂时看不了，当前只显示普通甘特任务和设备/人员安排，不显示关键工序关系线和外框高亮。";
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
      : "超期标记可能不完整，请刷新后重试，或到系统管理里的排产历史查看这次排产的详细提醒。";
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
      statusLabel: cc.available === false ? "暂时看不了" : (isCritical ? "是" : "否"),
      predecessorText: isCritical && meta ? publicCriticalPredecessorLabel(meta) : "-",
      edgeTypeText: isCritical && meta ? getCriticalEdgeTypeLabel(meta.edge_type) : "-",
      reasonText: cc.available === false
        ? (publicCriticalChainReason(cc.reason, cc.reason_code) || "-")
        : (isCritical && meta ? publicCriticalEdgeReason(meta.reason, meta.edge_type) : "-"),
      gapText: isCritical && meta && meta.gap_minutes !== null && typeof meta.gap_minutes !== "undefined"
        ? publicGapLabel(meta.gap_minutes)
        : "-",
    };
  }

  api.str = str; api.norm = norm;
  api.escapeHtml = escapeHtml;
  api.normalizeCriticalChain = normalizeCriticalChain;
  api.publicCriticalPredecessorLabel = publicCriticalPredecessorLabel;
  api.applyCriticalChainToState = applyCriticalChainToState;
  api.dedupeCriticalReason = dedupeCriticalReason;
  api.getCriticalChainUnavailableMessage = getCriticalChainUnavailableMessage;
  api.getArrowModeLabel = getArrowModeLabel;
  api.getCriticalEdgeTypeLabel = getCriticalEdgeTypeLabel;
  api.publicCriticalEdgeReason = publicCriticalEdgeReason;
  api.publicGapLabel = publicGapLabel;
  api.publicSourceLabel = publicSourceLabel;
  api.publicPriorityLabel = publicPriorityLabel;
  api.publicStatusLabel = publicStatusLabel;
  api.formatChineseDateTime = formatChineseDateTime;
  api.resolveDependencies = resolveDependencies;
  api.buildRenderTasks = buildRenderTasks;
  api.getCriticalStatusLabel = getCriticalStatusLabel;
  api.findDegradationEvent = findDegradationEvent;
  api.degradationCount = degradationCount;
  api.isCalendarLoadFailed = isCalendarLoadFailed;
  api.shouldUseFallbackCalendarDays = shouldUseFallbackCalendarDays;
  api.buildDegradationMessages = buildDegradationMessages;
  api.getOverdueWarningMessage = getOverdueWarningMessage;
  api.getCriticalTooltip = getCriticalTooltip; ns.contract = api;
})();
