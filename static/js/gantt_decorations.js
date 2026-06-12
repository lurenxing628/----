(function () {
  var ns = window.__APS_GANTT__;
  if (!ns) return;
  if (!ns._inited) ns._inited = {};
  if (ns._inited.decorations) return;
  ns._inited.decorations = true;

  var $ = ns.$;
  var reportClientError = ns.reportClientError;
  var norm = ns.norm;
  var state = ns.state;
  var _perfState = ns._perfState;
  var getColor = ns.getColor;
  var outlineApi = ns.outline;

  if (typeof $ !== "function") return;
  if (typeof reportClientError !== "function") return;
  if (typeof norm !== "function") return;
  if (typeof getColor !== "function") return;
  if (!outlineApi || !state || !_perfState) return;

  var setCriticalOutlineEnabled = outlineApi.setCriticalOutlineEnabled;
  if (typeof setCriticalOutlineEnabled !== "function") return;

  // ---- render/decorate cache (Win7 友好：减少不必要的全量重渲染) ----
  let _renderToken = 0; // 每次全量 render() + new Gantt() 递增
  const _decorCache = {
    renderToken: -1,
    colorMode: null,
    focusBatch: null,
    highlightCC: null,
  };

  function resetDecorCache() {
    _decorCache.renderToken = -1;
    _decorCache.colorMode = null;
    _decorCache.focusBatch = null;
    _decorCache.highlightCC = null;
    _perfState.wrappersById = new Map();
    _perfState.decorateRenderedIds = [];
    _perfState.holidayDigest = "";
    _perfState.holidayLayerMounted = false;
    _perfState.lastHolidayHeight = 0;
    _perfState.legendDigest = "";
    _perfState.ccVisibleCount = 0;
  }

  function beginRenderPass() {
    _renderToken += 1;
    resetDecorCache();
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
    } catch (err) {
      // ignore
    }

    // 徽标已弃用：不再插入
    return;
  }

  function buildTaskMapById() {
    const byId = new Map();
    const list = Array.isArray(state.currentTasks) ? state.currentTasks : [];
    for (let i = 0; i < list.length; i++) {
      const t = list[i] || {};
      byId.set(norm(t.id), t);
    }
    return byId;
  }

  function applyGroupSeparators() {
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
        const isGroupStart = groupStartIdx.has(idx);
        row.classList.toggle("aps-group-start", isGroupStart);
        // 统一移除历史内联 fill，避免主题切换时残留亮色注入
        row.removeAttribute("fill");
      });
    } catch (_) {
      // ignore
    }
  }

  function roundBarsOnce() {
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

  function updateFocusClasses(wrapperList, byId) {
    const host = $("gantt");
    if (!host) return;
    const hasFocus = !!state.focusBatch;
    host.classList.toggle("aps-has-focus", hasFocus);

    // 无聚焦时只需清理旧 focus 标记
    if (!hasFocus) {
      for (let i = 0; i < wrapperList.length; i++) {
        wrapperList[i].el.classList.remove("aps-focus");
      }
      return;
    }

    for (let i = 0; i < wrapperList.length; i++) {
      const item = wrapperList[i];
      const t = byId.get(item.id);
      if (!t) continue;
      const meta = t.meta || {};
      const bid = norm(meta.batch_id);
      item.el.classList.toggle("aps-focus", !!(bid && bid === state.focusBatch));
    }
  }

  function decorateStaticAfterRender(byId) {
    // 说明：仅在 new Gantt() 后执行一次（避免纯视觉交互反复 getBBox()/重排）

    // 假期/停工标注（按全局工作日历）
    ns.renderHolidayColumns();

    // 资源分组底色（grid-row fill）
    applyGroupSeparators();

    // 外协虚线标识 + 清理旧 CC 徽标残留（已弃用）
    try {
      const wrappers = document.querySelectorAll("#gantt .bar-wrapper");
      wrappers.forEach((w) => {
        const tid = norm(w.getAttribute("data-id"));
        const t = byId.get(tid);
        if (!t) return;
        const meta = t.meta || {};
        const isExternal = norm(meta.source) === "external";
        const isOverdue = meta.is_overdue === true || w.classList.contains("overdue");
        w.classList.toggle("overdue", isOverdue);
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

    roundBarsOnce();

    // 资源负荷条带（load_strip 加载在本文件之前；运行时判存防旧页面缺脚本）
    if (typeof ns.renderLoadStrip === "function") ns.renderLoadStrip();
  }

  function decorateDynamic(opts) {
    const o = opts || {};
    const updateLegendFlag = o.updateLegend !== false;
    if (!state.gantt || !Array.isArray(state.currentTasks) || state.currentTasks.length === 0) {
      if (updateLegendFlag) ns.updateLegend();
      return;
    }

    const ui = state.ui || {};
    const byId = o.byId || buildTaskMapById();
    const forceAll = o.forceAll === true;
    const tokenChanged = _decorCache.renderToken !== _renderToken;
    let wrappersById = _perfState.wrappersById;
    let wrapperList = [];
    let needRebuildWrappers =
      forceAll ||
      tokenChanged ||
      !wrappersById ||
      wrappersById.size <= 0 ||
      wrappersById.size !== (state.currentTasks.length || 0);

    if (!needRebuildWrappers) {
      wrappersById.forEach((el, id) => {
        if (!el || !el.isConnected) {
          needRebuildWrappers = true;
          return;
        }
        wrapperList.push({ id: id, el: el });
      });
      if (wrapperList.length !== wrappersById.size) {
        needRebuildWrappers = true;
      }
    }

    if (needRebuildWrappers) {
      const wrappers = document.querySelectorAll("#gantt .bar-wrapper");
      if (!wrappers || wrappers.length === 0) {
        _perfState.wrappersById = new Map();
        if (updateLegendFlag) ns.updateLegend();
        return;
      }
      wrappersById = new Map();
      wrapperList = [];
      wrappers.forEach((w) => {
        const tid = norm(w.getAttribute("data-id"));
        if (!tid) return;
        wrappersById.set(tid, w);
        wrapperList.push({ id: tid, el: w });
      });
      _perfState.wrappersById = wrappersById;
    }

    // 若 DOM 与数据不一致（例如渲染中途被打断），交给上层做降级
    const curCount = state.currentTasks.length || 0;
    const renderedCount = wrapperList.length || 0;
    if (curCount > 0 && renderedCount > 0 && renderedCount !== curCount) {
      throw new Error(`Gantt DOM mismatch: wrappers=${renderedCount}, tasks=${curCount}`);
    }
    const needColor = forceAll || tokenChanged || _decorCache.colorMode !== ui.colorMode;
    const needFocus = forceAll || tokenChanged || _decorCache.focusBatch !== state.focusBatch;
    const needCC = forceAll || tokenChanged || _decorCache.highlightCC !== ui.highlightCC;

    const renderedIds = [];

    for (let i = 0; i < wrapperList.length; i++) {
      const item = wrapperList[i];
      const tid = item.id;
      const w = item.el;
      const t = byId.get(tid);
      if (!t) continue;

      if (needFocus) {
        // 兼容旧类：统一清理，后续改为容器级 + aps-focus
        w.classList.remove("aps-dim");
      }

      if (needColor) {
        const color = getColor(t, ui.colorMode);
        if (color) w.style.setProperty("--aps-bar-color", color);
      }

      if (needCC) {
        const isCC = !!(ui.highlightCC && state.ccIdSet && state.ccIdSet.has(tid));
        w.classList.toggle("aps-critical", isCC);
        setCriticalOutlineEnabled(w, isCC);
        upsertCriticalBadge(w, false);
        if (ui.highlightCC && isCC) renderedIds.push(tid);
      }
    }

    _perfState.decorateRenderedIds = needCC ? renderedIds : [];
    if (needCC && !ui.highlightCC) {
      // 高亮关闭时：确保 class 也被移除（上面 toggle 已处理大部分；此处做一次兜底）
      try {
        for (let i = 0; i < wrapperList.length; i++) {
          wrapperList[i].el.classList.remove("aps-critical");
        }
      } catch (_) {
        // ignore
      }
    }

    if (needFocus) {
      updateFocusClasses(wrapperList, byId);
    }

    // 更新 cache（只要本次完成了增量装饰，就认为 DOM 与 ui 同步）
    _decorCache.renderToken = _renderToken;
    _decorCache.colorMode = ui.colorMode;
    _decorCache.focusBatch = state.focusBatch;
    _decorCache.highlightCC = ui.highlightCC;

    if (updateLegendFlag) ns.updateLegend();
  }

  function safeDecorateDynamic(opts) {
    try {
      decorateDynamic(opts);
    } catch (err) {
      reportClientError("甘特图装饰刷新失败", err);
      throw err;
    }
  }

  ns.safeDecorateDynamic = safeDecorateDynamic;
  ns.decorations = {
    beginRenderPass: beginRenderPass,
    buildTaskMapById: buildTaskMapById,
    decorateStaticAfterRender: decorateStaticAfterRender,
    resetCache: resetDecorCache,
  };
})();
