/* 资源负荷热力条带（fusion-gantt-load-strip）：甘特图下方按「资源×自然日」
 * 的负荷格，Top 5 周内总负荷降序（承接老 roadmap item 11「最忙资源」），
 * 点击格弹出该资源当天任务清单 + 去派工/报表链接（href 来自后端 links，
 * 前端不手拼 URL）。
 *
 * 像素对齐：列 x 坐标与假期层同公式（(date - gantt_start) 分钟差 /
 * stepMinutes * columnWidth），列宽 getGanttScale(gantt).dayWidth；
 * 横向随 .gantt-container scroll 平移。对齐不达标止损线=同列宽日历对齐
 * （仍按 dayWidth 定列宽，不再强制与图区像素贴合）。
 *
 * 数据是渲染前注入（initResourceLoad）、渲染后挂层（renderLoadStrip——
 * decorateStaticAfterRender 末尾调用，与假期层同一单次时机）。
 * severity 由后端装饰层判定（阈值唯一字源在 Python），CSS 只消费
 * severity-* 类名（00-tokens.css 既定约定）。
 */
(function () {
  var ns = window.__APS_GANTT__;
  if (!ns) return;
  if (!ns._inited) ns._inited = {};
  if (ns._inited.loadStrip) return;
  ns._inited.loadStrip = true;

  var str = ns.str;
  var escapeHtml = ns.escapeHtml;
  var state = ns.state;
  if (typeof str !== "function" || typeof escapeHtml !== "function" || !state) return;

  var MAX_ROWS = 5; // 与后端 MAX_STRIP_ROWS 同义：Top 5 最忙资源
  var strip = { rows: null, bound: false, baseOffset: 0, scrollContainer: null };

  function norm(v) {
    return str(v || "").trim();
  }

  function initResourceLoad(rows) {
    strip.rows = Array.isArray(rows) ? rows : null;
  }

  function severityClass(row) {
    var sev = norm(row && row.severity);
    if (sev !== "normal" && sev !== "warning" && sev !== "danger") sev = "unknown";
    return "aps-load-cell-" + sev;
  }

  function cellTitle(row) {
    var hours = Number(row.hours || 0);
    if (row.ratio === null || typeof row.ratio === "undefined") {
      return row.date + "：已排 " + hours + " 小时，利用率暂时算不了";
    }
    return row.date + "：已排 " + hours + " 小时 / 容量 " + Number(row.capacity_hours || 0) + " 小时（" + Math.round(Number(row.ratio) * 100) + "%）";
  }

  function groupByResource(rows) {
    var order = [];
    var byId = {};
    for (var i = 0; i < rows.length; i++) {
      var row = rows[i] || {};
      var rid = norm(row.resource_id);
      if (!rid) continue;
      if (!byId[rid]) {
        byId[rid] = { id: rid, label: norm(row.resource_label) || rid, cells: [] };
        order.push(rid); // 后端已按周内总负荷降序输出，保序即保排名
      }
      byId[rid].cells.push(row);
    }
    var groups = [];
    for (var j = 0; j < order.length; j++) groups.push(byId[order[j]]);
    return groups;
  }

  function ganttGeometry() {
    var gantt = state.gantt;
    var zoom = ns.zoom;
    if (!gantt || !gantt.gantt_start || !gantt.options) return null;
    if (!zoom || typeof zoom.getGanttScale !== "function") return null;
    var scale = zoom.getGanttScale(gantt);
    return { start: gantt.gantt_start, stepMinutes: scale.stepMinutes, columnWidth: scale.columnWidth, dayWidth: scale.dayWidth };
  }

  function dayOffsetPx(geo, dateStr) {
    var dt = new Date(dateStr + " 00:00:00");
    if (isNaN(dt.getTime())) return null;
    var diffMinutes = (dt.getTime() - geo.start.getTime()) / 60000.0;
    return Math.floor((diffMinutes / geo.stepMinutes) * geo.columnWidth);
  }

  function buildPopupHtml(group, row) {
    var tasks = Array.isArray(state.allTasks) ? state.allTasks : [];
    var view = norm(state.cfg && state.cfg.view) || "machine";
    var idKey = view === "operator" ? "operator_id" : "machine_id";
    var dayStart = new Date(row.date + " 00:00:00");
    var dayEnd = new Date(dayStart.getTime() + 24 * 3600 * 1000);
    var items = [];
    for (var i = 0; i < tasks.length; i++) {
      var t = tasks[i] || {};
      var meta = t.meta || {};
      if (norm(meta[idKey]) !== group.id) continue;
      var st = new Date(String(t.start || "").replace("T", " "));
      var et = new Date(String(t.end || "").replace("T", " "));
      if (isNaN(st.getTime()) || isNaN(et.getTime())) continue;
      if (et <= dayStart || st >= dayEnd) continue;
      items.push(
        "<li>" + escapeHtml(norm(meta.batch_id)) + " " + escapeHtml(norm(meta.operation_label) || norm(t.name)) +
        "（" + escapeHtml(norm(meta.planned_time_label)) + "）</li>"
      );
    }
    var html = '<div class="aps-load-popup-title">' + escapeHtml(group.label) + " · " + escapeHtml(row.date) + "</div>";
    html += '<div class="aps-load-popup-meta">' + escapeHtml(cellTitle(row)) + "</div>";
    html += items.length
      ? '<ul class="aps-load-popup-tasks">' + items.join("") + "</ul>"
      : '<p class="aps-load-popup-empty">当天没有可显示的任务（可能被筛选条件过滤）。</p>';
    var links = Array.isArray(row.links) ? row.links : [];
    if (links.length) {
      var parts = [];
      for (var k = 0; k < links.length; k++) {
        var link = links[k] || {};
        if (link.disabled) {
          parts.push('<span class="aps-load-popup-link is-disabled" title="' + escapeHtml(norm(link.disabled_reason)) + '">' + escapeHtml(norm(link.label)) + "</span>");
        } else {
          parts.push('<a class="aps-load-popup-link" href="' + escapeHtml(norm(link.url)) + '">' + escapeHtml(norm(link.label)) + "</a>");
        }
      }
      html += '<div class="aps-load-popup-links">' + parts.join("") + "</div>";
    }
    return html;
  }

  function closePopup(host) {
    var popup = host.querySelector(".aps-load-popup");
    if (popup) popup.parentNode.removeChild(popup);
  }

  // scroll 监听单独于 click 委托：每次 full render 重建 .gantt-container（
  // gantt_render host.innerHTML="" 后 new Gantt），旧 listener 随节点销毁，
  // 必须对新容器重绑——按容器实例去重防同节点重复绑定
  function bindScrollSync(host) {
    var container = document.querySelector("#gantt .gantt-container");
    if (!container || typeof container.addEventListener !== "function") return null;
    if (strip.scrollContainer !== container) {
      strip.scrollContainer = container;
      container.addEventListener("scroll", function () {
        syncScroll(host, container);
      });
    }
    return container;
  }

  function bindStripEvents(host) {
    if (strip.bound) return;
    strip.bound = true;
    // 容器级委托：renderLoadStrip 重写 innerHTML 不丢绑定
    host.addEventListener("click", function (e) {
      var node = e && e.target;
      while (node && node !== host) {
        if (node.classList && node.classList.contains("aps-load-cell")) {
          var rid = node.getAttribute("data-resource");
          var dateStr = node.getAttribute("data-date");
          var rows = strip.rows || [];
          for (var i = 0; i < rows.length; i++) {
            if (norm(rows[i].resource_id) === rid && norm(rows[i].date) === dateStr) {
              closePopup(host);
              var popup = document.createElement("div");
              popup.className = "aps-load-popup";
              popup.innerHTML = buildPopupHtml({ id: rid, label: norm(rows[i].resource_label) || rid }, rows[i]);
              host.appendChild(popup);
              return;
            }
          }
          return;
        }
        if (node.classList && node.classList.contains("aps-load-popup")) return; // 弹层内点击（如链接）不关闭
        node = node.parentNode;
      }
      closePopup(host);
    });
  }

  // 渲染后实测「图区 SVG 左缘 vs 格子容器左缘」差值——条带左侧有资源名列，
  // 格子 x=0 必须平移到与甘特 day-0 列同一视口位置才算像素对齐
  function computeBaseOffset(host, container) {
    try {
      var svg = container.querySelector("svg");
      var cells = host.querySelector(".aps-load-strip-cells");
      if (!svg || !cells) return 0;
      if (typeof svg.getBoundingClientRect !== "function" || typeof cells.getBoundingClientRect !== "function") return 0;
      return Math.round(svg.getBoundingClientRect().left + container.scrollLeft - cells.getBoundingClientRect().left);
    } catch (_) {
      return 0; // 量不到（DOM shim/异常布局）：退化为止损线——同列宽不强制贴合
    }
  }

  // 只平移格子层，资源名列固定不动
  function syncScroll(host, container) {
    var wraps = host.querySelectorAll(".aps-load-strip-cells");
    for (var i = 0; i < wraps.length; i++) {
      wraps[i].style.transform = "translateX(" + (strip.baseOffset - container.scrollLeft) + "px)";
    }
  }

  // HTML 构建纯函数（导出供 JS contract 测试字符串断言——DOM shim 的
  // innerHTML 剥标签，渲染结果不可 querySelector，沿 buildTaskDetailHtml 模式）
  function buildLoadStripHtml(rows, geo) {
    if (!Array.isArray(rows) || rows.length === 0 || !geo) return "";
    var groups = groupByResource(rows);
    var shown = groups.slice(0, MAX_ROWS);
    var html = '<div class="aps-load-strip-head">资源负荷（按全局工作日历估算，未按单台设备/单人细分）</div>';
    html += '<div class="aps-load-strip-viewport">';
    for (var i = 0; i < shown.length; i++) {
      var group = shown[i];
      var cells = "";
      for (var j = 0; j < group.cells.length; j++) {
        var row = group.cells[j];
        var x = dayOffsetPx(geo, norm(row.date));
        if (x === null) continue;
        var label = row.ratio === null || typeof row.ratio === "undefined"
          ? "?"
          : Math.round(Number(row.ratio) * 100) + "%";
        cells +=
          '<button type="button" class="aps-load-cell ' + severityClass(row) + '"' +
          ' style="left:' + x + "px;width:" + Math.max(Math.floor(geo.dayWidth) - 2, 8) + 'px"' +
          ' data-resource="' + escapeHtml(group.id) + '" data-date="' + escapeHtml(norm(row.date)) + '"' +
          ' title="' + escapeHtml(cellTitle(row)) + '">' + escapeHtml(label) + "</button>";
      }
      html +=
        '<div class="aps-load-strip-row"><span class="aps-load-strip-label" title="' + escapeHtml(group.label) + '">' +
        escapeHtml(group.label) + '</span><span class="aps-load-strip-cells">' + cells + "</span></div>";
    }
    if (groups.length > shown.length) {
      html += '<div class="aps-load-strip-more">另有 ' + (groups.length - shown.length) + " 个资源有排程，可用筛选缩小范围查看。</div>";
    }
    html += "</div>";
    return html;
  }

  function renderLoadStrip() {
    var host = document.getElementById("ganttLoadStrip");
    if (!host) return;
    var html = buildLoadStripHtml(strip.rows, ganttGeometry());
    if (!html) {
      host.innerHTML = "";
      if (host.classList) host.classList.add("is-hidden");
      return;
    }
    host.innerHTML = html;
    if (host.classList) host.classList.remove("is-hidden");
    bindStripEvents(host);
    var container = bindScrollSync(host);
    if (container) {
      strip.baseOffset = computeBaseOffset(host, container);
      syncScroll(host, container);
    }
  }

  ns.initResourceLoad = initResourceLoad;
  ns.renderLoadStrip = renderLoadStrip;
  ns.buildLoadStripHtml = buildLoadStripHtml;
  ns.buildLoadPopupHtml = buildPopupHtml;
})();
