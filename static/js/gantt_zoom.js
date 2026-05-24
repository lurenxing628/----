(function () {
  var ns = window.__APS_GANTT__;
  if (!ns) return;
  if (!ns._inited) ns._inited = {};
  if (ns._inited.zoom) return;
  ns._inited.zoom = true;

  var DAY_MINUTES = 1440;
  var DEFAULT_ZOOM = "day";
  var HARD_COLUMN_LIMIT = 1500;
  var SOFT_NODE_LIMIT = 12000;
  var HARD_NODE_LIMIT = 18000;
  var GANTT_ROW_PITCH_PX = 38;
  var GANTT_BASE_HEIGHT_PX = 168;
  var SOFT_TASK_LIMIT = 800;
  var HARD_TASK_LIMIT = 1200;
  var SOFT_HEIGHT_LIMIT_PX = 30000;
  var HARD_HEIGHT_LIMIT_PX = 45000;

  var ZOOM_SPECS = {
    month: {
      level: "month",
      label: "月",
      frappeViewMode: "Month",
      stepMinutes: 43200,
      columnWidthPx: 120,
      maxRangeDays: null,
      minHitboxPx: 12,
    },
    week: {
      level: "week",
      label: "周",
      frappeViewMode: "Week",
      stepMinutes: 10080,
      columnWidthPx: 140,
      maxRangeDays: null,
      minHitboxPx: 12,
    },
    day: {
      level: "day",
      label: "日",
      frappeViewMode: "Day",
      stepMinutes: 1440,
      columnWidthPx: 38,
      maxRangeDays: 62,
      minHitboxPx: 12,
    },
    "half-day": {
      level: "half-day",
      label: "12小时",
      frappeViewMode: "Half Day",
      stepMinutes: 720,
      columnWidthPx: 56,
      maxRangeDays: 31,
      minHitboxPx: 12,
    },
    "quarter-day": {
      level: "quarter-day",
      label: "6小时",
      frappeViewMode: "Quarter Day",
      stepMinutes: 360,
      columnWidthPx: 56,
      maxRangeDays: 21,
      minHitboxPx: 12,
    },
    hour: {
      level: "hour",
      label: "小时",
      frappeViewMode: "Hour",
      stepMinutes: 60,
      columnWidthPx: 48,
      maxRangeDays: 14,
      minHitboxPx: 12,
    },
    "fifteen-minute": {
      level: "fifteen-minute",
      label: "15分钟",
      frappeViewMode: "Fifteen Minute",
      stepMinutes: 15,
      columnWidthPx: 32,
      maxRangeDays: 7,
      minHitboxPx: 12,
    },
    "five-minute": {
      level: "five-minute",
      label: "5分钟",
      frappeViewMode: "Five Minute",
      stepMinutes: 5,
      columnWidthPx: 24,
      maxRangeDays: 3,
      minHitboxPx: 12,
    },
    "one-minute": {
      level: "one-minute",
      label: "1分钟",
      frappeViewMode: "One Minute",
      stepMinutes: 1,
      columnWidthPx: 18,
      maxRangeDays: 1,
      minHitboxPx: 12,
    },
  };

  var LEGACY_VIEW_MODE_TO_ZOOM = {
    Day: "day",
    Week: "week",
    Month: "month",
    "Half Day": "half-day",
    "Quarter Day": "quarter-day",
    Hour: "hour",
    "Fifteen Minute": "fifteen-minute",
    "Five Minute": "five-minute",
    "One Minute": "one-minute",
  };

  function norm(value) {
    return String(value === null || typeof value === "undefined" ? "" : value).trim();
  }

  function normalizeZoomLevel(value) {
    var raw = norm(value);
    if (!raw) return DEFAULT_ZOOM;
    if (ZOOM_SPECS[raw]) return raw;
    if (LEGACY_VIEW_MODE_TO_ZOOM[raw]) return LEGACY_VIEW_MODE_TO_ZOOM[raw];
    var lower = raw.toLowerCase().replace(/_/g, "-").replace(/\s+/g, "-");
    if (ZOOM_SPECS[lower]) return lower;
    if (lower === "halfday") return "half-day";
    if (lower === "quarterday") return "quarter-day";
    if (lower === "15-minute" || lower === "15m" || lower === "fifteenminute") return "fifteen-minute";
    if (lower === "5-minute" || lower === "5m" || lower === "fiveminute") return "five-minute";
    if (lower === "1-minute" || lower === "1m" || lower === "oneminute") return "one-minute";
    return DEFAULT_ZOOM;
  }

  function isKnownZoomLevel(value) {
    var raw = norm(value);
    if (!raw) return true;
    if (ZOOM_SPECS[raw]) return true;
    if (LEGACY_VIEW_MODE_TO_ZOOM[raw]) return true;
    var lower = raw.toLowerCase().replace(/_/g, "-").replace(/\s+/g, "-");
    if (ZOOM_SPECS[lower]) return true;
    return lower === "halfday"
      || lower === "quarterday"
      || lower === "15-minute"
      || lower === "15m"
      || lower === "fifteenminute"
      || lower === "5-minute"
      || lower === "5m"
      || lower === "fiveminute"
      || lower === "1-minute"
      || lower === "1m"
      || lower === "oneminute";
  }

  function getZoomSpec(value) {
    return ZOOM_SPECS[normalizeZoomLevel(value)] || ZOOM_SPECS[DEFAULT_ZOOM];
  }

  function currentZoomLevel(ui) {
    var source = ui || {};
    var rawZoom = norm(source.zoomLevel || "");
    var rawViewMode = norm(source.viewMode || "");
    if (rawViewMode && rawViewMode !== "Day" && (!rawZoom || rawZoom === DEFAULT_ZOOM)) {
      return rawViewMode;
    }
    return rawZoom || rawViewMode || DEFAULT_ZOOM;
  }

  function getGanttScale(gantt) {
    var options = gantt && gantt.options ? gantt.options : {};
    var stepMinutes = Number(options.step_minutes || 0);
    if (!stepMinutes) stepMinutes = Number(options.step || 24) * 60;
    var columnWidth = Number(options.column_width || 38);
    var stepMs = Number(options.step_ms || 0);
    if (!stepMs) stepMs = stepMinutes * 60 * 1000;
    return {
      stepMinutes: stepMinutes,
      stepMs: stepMs,
      columnWidth: columnWidth,
      dayWidth: DAY_MINUTES / stepMinutes * columnWidth,
    };
  }

  function parseLocalDate(value, endOfDay) {
    var text = norm(value);
    if (!text) return null;
    var match = /^(\d{4})-(\d{1,2})-(\d{1,2})$/.exec(text);
    if (match) {
      return new Date(
        Number(match[1]),
        Number(match[2]) - 1,
        Number(match[3]),
        endOfDay ? 23 : 0,
        endOfDay ? 59 : 0,
        endOfDay ? 59 : 0,
        endOfDay ? 999 : 0
      );
    }
    var parsed = new Date(text);
    if (isNaN(parsed.getTime())) return null;
    return parsed;
  }

  function estimateGanttCost(columns, taskCount, dependencyCount, holidayMarkerCount) {
    return columns * 3 + taskCount * 8 + dependencyCount * 2 + holidayMarkerCount;
  }

  function estimateGanttHeight(taskCount) {
    var count = Number(taskCount || 0);
    if (!isFinite(count) || count < 0) count = 0;
    return GANTT_BASE_HEIGHT_PX + count * GANTT_ROW_PITCH_PX;
  }

  function baseZoomResult(ok, level, reason, columns, taskCount, estimatedNodes, estimatedHeight, message) {
    return {
      ok: ok,
      level: level,
      reason: reason,
      columns: columns,
      taskCount: taskCount,
      estimatedNodes: estimatedNodes,
      estimatedHeight: estimatedHeight,
      message: message || "",
    };
  }

  function validateZoomRange(args) {
    var spec = getZoomSpec(args && args.zoomLevel);
    var start = parseLocalDate(args && args.startDate, false);
    var end = parseLocalDate(args && args.endDate, true);
    var taskCount = Number(args && args.taskCount ? args.taskCount : 0);
    var dependencyCount = Number(args && args.dependencyCount ? args.dependencyCount : 0);
    var holidayMarkerCount = Number(args && args.holidayMarkerCount ? args.holidayMarkerCount : 0);
    if (!isFinite(taskCount) || taskCount < 0) taskCount = 0;
    if (!isFinite(dependencyCount) || dependencyCount < 0) dependencyCount = 0;
    if (!isFinite(holidayMarkerCount) || holidayMarkerCount < 0) holidayMarkerCount = 0;
    var rangeMinutes = start && end && end >= start ? (end.getTime() - start.getTime() + 1) / 60000 : 0;
    var rangeDays = rangeMinutes ? rangeMinutes / DAY_MINUTES : 0;
    var columns = rangeMinutes ? Math.ceil(rangeMinutes / spec.stepMinutes) : 0;
    var estimatedNodes = estimateGanttCost(columns, taskCount, dependencyCount, holidayMarkerCount);
    var estimatedHeight = estimateGanttHeight(taskCount);

    if (spec.maxRangeDays !== null && rangeDays > spec.maxRangeDays) {
      return baseZoomResult(false, "hard", "range", columns, taskCount, estimatedNodes, estimatedHeight, "当前日期范围太宽，请缩小日期范围，或切换到更粗的时间粒度。");
    }
    if (columns > HARD_COLUMN_LIMIT) {
      return baseZoomResult(false, "hard", "columns", columns, taskCount, estimatedNodes, estimatedHeight, "当前时间格太多，请缩小日期范围，或切换到更粗的时间粒度。");
    }
    if (taskCount > HARD_TASK_LIMIT || estimatedHeight > HARD_HEIGHT_LIMIT_PX) {
      return baseZoomResult(
        false,
        "hard",
        taskCount > HARD_TASK_LIMIT ? "tasks" : "height",
        columns,
        taskCount,
        estimatedNodes,
        estimatedHeight,
        "当前任务太多，直接打开甘特图可能会把页面卡住。请先筛选设备、人员或批次，或者缩短日期范围后再查看。"
      );
    }
    if (estimatedNodes > HARD_NODE_LIMIT) {
      return baseZoomResult(false, "hard", "nodes", columns, taskCount, estimatedNodes, estimatedHeight, "当前任务和连线太多，直接打开甘特图可能会把页面卡住。请先筛选设备、人员或批次，或者切换到更粗的时间粒度。");
    }
    if (taskCount > SOFT_TASK_LIMIT || estimatedHeight > SOFT_HEIGHT_LIMIT_PX) {
      return baseZoomResult(
        true,
        "soft",
        taskCount > SOFT_TASK_LIMIT ? "tasks" : "height",
        columns,
        taskCount,
        estimatedNodes,
        estimatedHeight,
        "当前任务较多，页面可能会变慢。建议先筛选设备、人员或批次。"
      );
    }
    if (estimatedNodes > SOFT_NODE_LIMIT) {
      return baseZoomResult(true, "soft", "nodes", columns, taskCount, estimatedNodes, estimatedHeight, "当前任务和连线较多，页面可能会变慢。建议先筛选设备、人员或批次。");
    }
    return baseZoomResult(true, "ok", "", columns, taskCount, estimatedNodes, estimatedHeight, "");
  }

  ns.zoom = {
    DEFAULT_ZOOM: DEFAULT_ZOOM,
    ZOOM_SPECS: ZOOM_SPECS,
    HARD_COLUMN_LIMIT: HARD_COLUMN_LIMIT,
    SOFT_NODE_LIMIT: SOFT_NODE_LIMIT,
    HARD_NODE_LIMIT: HARD_NODE_LIMIT,
    GANTT_ROW_PITCH_PX: GANTT_ROW_PITCH_PX,
    GANTT_BASE_HEIGHT_PX: GANTT_BASE_HEIGHT_PX,
    SOFT_TASK_LIMIT: SOFT_TASK_LIMIT,
    HARD_TASK_LIMIT: HARD_TASK_LIMIT,
    SOFT_HEIGHT_LIMIT_PX: SOFT_HEIGHT_LIMIT_PX,
    HARD_HEIGHT_LIMIT_PX: HARD_HEIGHT_LIMIT_PX,
    normalizeZoomLevel: normalizeZoomLevel,
    currentZoomLevel: currentZoomLevel,
    isKnownZoomLevel: isKnownZoomLevel,
    getZoomSpec: getZoomSpec,
    getGanttScale: getGanttScale,
    validateZoomRange: validateZoomRange,
    estimateGanttCost: estimateGanttCost,
    estimateGanttHeight: estimateGanttHeight,
  };
})();
