(function () {
  var ns = window.__APS_GANTT__;
  if (!ns || !ns.contract) {
    return;
  }

  var api = ns.contract;
  if (api._helpReady) {
    return;
  }
  api._helpReady = true;

  function getHelpItems(critical, payload) {
    var unavailableMessage = api.getCriticalChainUnavailableMessage(critical);
    var calendarFailed = api.isCalendarLoadFailed(payload || {});
    var items = [
      "查看模式：这里只显示排产结果。可以点击任务条看详情、筛选、切换配色和缩放时间粒度；拖动或拉伸任务条不会修改计划。",
      "日期范围：按本地自然日计算，开始日从 00:00 开始，结束日整天都算在内。",
      "时间粒度：月/周/日适合看整体范围；12小时/6小时适合看班次附近；小时/15分钟/5分钟/1分钟适合看短工序的开始和结束时间。",
      "短工序：时间很短的工序会按真实时长显示，所以条形可能很窄；页面会保留方便点击的区域，点击后仍能看详情。",
      "范围保护：时间粒度越细，能看的日期范围越短；范围太大时，页面会提示先缩短日期范围或切回更粗的时间粒度，避免浏览器卡顿。",
      "颜色：默认按批次，同批次同色；可切换按优先级/来源/状态。",
      calendarFailed
        ? "假期/停工：工作日历加载失败，当前不显示假期/停工背景标注。"
        : "假期/停工：背景淡红色竖条标注（口径：全局工作日历；未配置时周末默认视为假期）。",
      "红边：该批次在该版本中被判定为超期。",
      unavailableMessage
        ? "关键工序：当前不可用，不显示关键工序外框高亮。"
        : "关键工序：这些工序会直接影响当前版本的最晚完工时间，系统用外框标出。",
      "虚线边框：外协任务。",
      unavailableMessage
        ? "工序关系线：关键工序关系当前停用；可切换为全部工艺关系线或关闭。"
        : "工序关系线：默认只显示关键工序之间的关系线；可切换为全部工艺关系线或关闭。",
      "聚焦：点击任务条可聚焦同批次任务，再次点击取消。",
      "筛选：支持批次/设备/人员筛选，并可叠加仅超期/仅外协。",
      "关键工序口径：按当前版本的全量排程计算，不随当前页面的日期窗口截断；会综合工艺前后关系、设备和人员占用关系来找最影响总工期的链路。",
    ];
    if (unavailableMessage) {
      items.push("关键链暂不可用：" + unavailableMessage);
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

  api.getHelpItems = getHelpItems;
  api.renderHelpList = renderHelpList;
})();
