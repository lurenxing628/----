(function () {
  var ns = window.__APS_GANTT__;
  if (!ns) throw new Error("甘特图命名空间未加载，无法初始化适配层。");
  if (!ns._inited) ns._inited = {};
  if (ns._inited.adapter) return;
  ns._inited.adapter = true;

  var zoom = ns.zoom;
  if (!zoom || typeof zoom.getZoomSpec !== "function" || typeof zoom.normalizeZoomLevel !== "function") {
    throw new Error("甘特图缩放合同未加载，无法初始化适配层。");
  }

  var MODES = {
    VIEW: "view",
    SIMULATE: "simulate",
  };

  function norm(value) {
    return String(value === null || typeof value === "undefined" ? "" : value).trim();
  }

  function normalizeMode(value) {
    var raw = norm(value || MODES.VIEW);
    if (raw === MODES.VIEW || raw === MODES.SIMULATE) return raw;
    throw new Error("不支持的甘特图模式：" + raw);
  }

  function readZoomSpec(input) {
    var rawLevel = input && (input.zoomLevel || (input.zoomSpec && input.zoomSpec.level));
    return zoom.getZoomSpec(zoom.normalizeZoomLevel(rawLevel || "day"));
  }

  function buildGanttOptions(input) {
    var opts = input || {};
    var mode = normalizeMode(opts.mode);
    var spec = readZoomSpec(opts);
    var isViewMode = mode === MODES.VIEW;
    var options = {
      view_mode: spec.frappeViewMode || opts.fallbackViewMode || "Day",
      step_minutes: spec.stepMinutes,
      step_ms: spec.stepMinutes * 60 * 1000,
      column_width: spec.columnWidthPx,
      readonly: isViewMode,
      readonly_dates: isViewMode,
      readonly_progress: true,
      language: "zh",
      popup_trigger: "click",
      on_click: opts.onClick,
      custom_popup_html: opts.customPopupHtml,
    };
    if (!isViewMode && typeof opts.onDraftChange === "function") {
      options.on_date_change = function (task, start, end) {
        opts.onDraftChange({ type: "date_change", task: task, start: start, end: end });
      };
    }
    return options;
  }

  function resolveCtor(input) {
    var ctor = input && input.GanttCtor ? input.GanttCtor : window.Gantt;
    if (typeof ctor !== "function") throw new Error("Frappe Gantt 未加载。");
    return ctor;
  }

  function createGantt(input) {
    var opts = input || {};
    var selector = opts.selector || "#gantt";
    if (!Array.isArray(opts.tasks)) throw new Error("甘特图任务列表必须是数组。");
    var ctor = resolveCtor(opts);
    return new ctor(selector, opts.tasks, buildGanttOptions(opts));
  }

  function createAdapter(input) {
    var config = Object.assign({}, input || {});
    config.mode = normalizeMode(config.mode);
    config.zoomLevel = zoom.normalizeZoomLevel(config.zoomLevel || "day");
    return {
      setMode: function (mode) {
        config.mode = normalizeMode(mode);
        return this;
      },
      setZoom: function (level) {
        config.zoomLevel = zoom.normalizeZoomLevel(level || config.zoomLevel || "day");
        return this;
      },
      onTaskClick: function (handler) {
        config.onClick = handler;
        return this;
      },
      onDraftChange: function (handler) {
        config.onDraftChange = handler;
        return this;
      },
      buildOptions: function (extra) {
        return buildGanttOptions(Object.assign({}, config, extra || {}));
      },
      createGantt: function (extra) {
        return createGantt(Object.assign({}, config, extra || {}));
      },
      destroy: function (gantt) {
        if (gantt && typeof gantt.hide_popup === "function") gantt.hide_popup();
      },
    };
  }

  ns.adapter = {
    MODES: MODES,
    normalizeMode: normalizeMode,
    buildGanttOptions: buildGanttOptions,
    createGantt: createGantt,
    createAdapter: createAdapter,
  };
})();
