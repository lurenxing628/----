/* 沿链巡检（fusion-chain-walk-navigation）：详情面板 上一道/下一道 工艺导航 +
 * 关键链 ←/→ 巡检 + selectTaskById 程序化选中统一入口。
 *
 * 生命周期两分：bindChainWalk（委托/keydown）只绑一次；rebuildChainIndex
 * （工艺链双向 Map + byId）每次数据加载后重建——「加载」重新 fetch 会换掉
 * allTasks，索引必须跟着换否则巡检指向旧数据。
 *
 * 工艺链索引建在 state.allTasks 的原始 dependencies 上（后端单前驱 id 串）——
 * 不读 currentTasks.dependencies：它被 buildRenderTasks 按 depsMode 重写
 * （critical 模式是关键链前驱、batch 模式空串）。
 *
 * 依赖一律运行时读取（函数体内取 ns.xxx，不在头部解构缓存）——本文件加载于
 * decorations 之后 render 之前，render 的导出（scrollToTaskStart）此时尚不存在。
 */
(function () {
  var ns = window.__APS_GANTT__;
  if (!ns) return;
  if (!ns._inited) ns._inited = {};
  if (ns._inited.chainWalk) return;
  ns._inited.chainWalk = true;

  var str = ns.str;
  var state = ns.state;
  if (typeof str !== "function" || !state) return;

  var walk = {
    currentId: "",
    byId: new Map(),
    prevById: new Map(),
    nextById: new Map(),
    bound: false,
    notice: "",
  };

  function norm(v) {
    return str(v || "").trim();
  }

  function rebuildChainIndex() {
    walk.byId = new Map();
    walk.prevById = new Map();
    walk.nextById = new Map();
    var tasks = Array.isArray(state.allTasks) ? state.allTasks : [];
    for (var i = 0; i < tasks.length; i++) {
      var t = tasks[i];
      var id = norm(t && t.id);
      if (!id) continue;
      walk.byId.set(id, t);
      var prev = norm(t.dependencies);
      if (prev) {
        walk.prevById.set(id, prev);
        walk.nextById.set(prev, id);
      }
    }
    // 数据换代后旧选中 id 可能已不存在——清掉防巡检指向幽灵任务
    if (walk.currentId && !walk.byId.has(walk.currentId)) walk.currentId = "";
    walk.notice = "";
  }

  function inCurrentView(id) {
    var list = Array.isArray(state.currentTasks) ? state.currentTasks : [];
    for (var i = 0; i < list.length; i++) {
      if (norm(list[i] && list[i].id) === id) return true;
    }
    return false;
  }

  function selectTaskById(id, opts) {
    var taskId = norm(id);
    var task = walk.byId.get(taskId);
    if (!task) return false;
    walk.currentId = taskId;
    var options = opts || {};
    walk.notice = options.notice || "";
    var visible = inCurrentView(taskId);
    if (!visible) {
      walk.notice = (walk.notice ? walk.notice + "；" : "") + "该工序不在当前筛选视图中，清除筛选后可在图上看到";
    }
    var popup = ns.popup;
    var target = document.getElementById("ganttTaskDetail");
    if (popup && typeof popup.renderTaskDetail === "function" && target) {
      popup.renderTaskDetail(target, task, state.critical);
    }
    // 视图外目标：详情照渲但聚焦装饰与滚动全部跳过（design「只提示、不装饰」——
    // focusBatch 会让可见条形整体变暗/高亮同批次，对不在图上的目标是误导）
    if (visible) {
      var bid = norm(task.meta && task.meta.batch_id);
      if (bid) {
        // 幂等赋值（非 toggle）：连续巡检同批次不闪烁；清聚焦走 ganttClearFocus 按钮
        state.focusBatch = bid;
        if (typeof ns.safeDecorateDynamic === "function") {
          ns.safeDecorateDynamic({ updateLegend: false });
        }
      }
      if (options.scroll !== false) {
        try {
          if (typeof ns.scrollToTaskStart === "function") ns.scrollToTaskStart(task);
        } catch (_) {
          // DOM shim/旧环境无滚动 API：定位失败不阻断巡检
        }
      }
    }
    return true;
  }

  function walkProcess(delta) {
    if (!walk.currentId) return false;
    var map = delta > 0 ? walk.nextById : walk.prevById;
    var targetId = map.get(walk.currentId);
    if (!targetId || !walk.byId.has(targetId)) return false;
    return selectTaskById(targetId, {});
  }

  function walkCritical(delta) {
    var critical = state.critical || {};
    if (critical.available === false) return false;
    var ids = Array.isArray(critical.ids) ? critical.ids : [];
    if (!ids.length || !walk.currentId) return false;
    var idx = ids.indexOf(walk.currentId);
    if (idx < 0) return false;
    // 范围外目标（关键链按整版回溯、tasks 按窗口截取）：跳过缺失 id 继续向同方向找
    var skipped = 0;
    for (var i = idx + delta; i >= 0 && i < ids.length; i += delta) {
      var candidate = norm(ids[i]);
      if (walk.byId.has(candidate)) {
        var notice = skipped > 0 ? "已跳过 " + skipped + " 道当前范围外的工序" : "";
        return selectTaskById(candidate, { notice: notice });
      }
      skipped++;
    }
    if (skipped > 0) {
      walk.notice = "关键链后续工序在当前日期范围/筛选之外";
      // 停在原地但提示要可见：重渲当前任务面板带提示
      selectTaskById(walk.currentId, { notice: walk.notice, scroll: false });
    }
    return false;
  }

  function criticalPosition(taskId) {
    var critical = state.critical || {};
    var ids = Array.isArray(critical.ids) ? critical.ids : [];
    var idx = ids.indexOf(norm(taskId));
    return idx < 0 ? null : { index: idx + 1, total: ids.length };
  }

  function isFormControl(node) {
    var tag = node && node.tagName ? String(node.tagName).toUpperCase() : "";
    return tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA";
  }

  function bindChainWalk() {
    if (walk.bound) return;
    walk.bound = true;
    var panel = document.getElementById("ganttTaskDetail");
    if (panel && typeof panel.addEventListener === "function") {
      // 容器级委托：面板 innerHTML 整体重写不丢绑定
      panel.addEventListener("click", function (e) {
        var node = e && e.target;
        while (node && node !== panel) {
          var dir = node.getAttribute && node.getAttribute("data-walk");
          if (dir === "prev") { walkProcess(-1); return; }
          if (dir === "next") { walkProcess(1); return; }
          node = node.parentNode;
        }
      });
    }
    if (document && typeof document.addEventListener === "function") {
      document.addEventListener("keydown", function (e) {
        if (!e || isFormControl(e.target)) return; // 输入框聚焦时方向键归输入框
        if (e.key === "ArrowRight") walkCritical(1);
        else if (e.key === "ArrowLeft") walkCritical(-1);
      });
    }
  }

  ns.chainWalk = {
    bindChainWalk: bindChainWalk,
    rebuildChainIndex: rebuildChainIndex,
    selectTaskById: selectTaskById,
    walkProcess: walkProcess,
    walkCritical: walkCritical,
    currentTaskId: function () { return walk.currentId; },
    currentNotice: function () { return walk.notice; },
    hasPrev: function (id) { return walk.prevById.has(norm(id)); },
    hasNext: function (id) { return walk.nextById.has(norm(id)); },
    criticalPosition: criticalPosition,
  };
})();
