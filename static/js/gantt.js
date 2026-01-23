(function () {
  function $(id) {
    return document.getElementById(id);
  }

  function show(el, visible) {
    if (!el) return;
    el.style.display = visible ? "block" : "none";
  }

  async function loadAndRender() {
    const cfg = window.__APS_GANTT__ || {};
    const url = new URL(cfg.dataUrl || "", window.location.origin);
    if (cfg.view) url.searchParams.set("view", cfg.view);
    if (cfg.weekStart) url.searchParams.set("week_start", cfg.weekStart);
    if (cfg.startDate) url.searchParams.set("start_date", cfg.startDate);
    if (cfg.endDate) url.searchParams.set("end_date", cfg.endDate);
    if (typeof cfg.offset !== "undefined") url.searchParams.set("offset", String(cfg.offset));
    if (cfg.version) url.searchParams.set("version", String(cfg.version));

    const emptyEl = $("ganttEmpty");
    const errEl = $("ganttError");
    show(emptyEl, false);
    show(errEl, false);

    let payload;
    try {
      const resp = await fetch(url.toString(), { headers: { "Accept": "application/json" } });
      payload = await resp.json();
      if (!payload || payload.success !== true) {
        const msg = (payload && payload.error && payload.error.message) ? payload.error.message : "甘特图数据获取失败。";
        throw new Error(msg);
      }
    } catch (e) {
      errEl.textContent = String(e && e.message ? e.message : e);
      show(errEl, true);
      return;
    }

    const data = payload.data || {};
    const tasks = Array.isArray(data.tasks) ? data.tasks : [];
    if (!tasks.length) {
      show(emptyEl, true);
      return;
    }

    // 渲染
    // 说明：Frappe Gantt 会自动在时间轴两侧留白（内部逻辑会加一个月），这里通过滚动把视口定位到本周附近。
    const gantt = new Gantt("#gantt", tasks, {
      view_mode: "Day",
      language: "zh",
      popup_trigger: "click",
      custom_popup_html: function (task) {
        const meta = task && task.meta ? task.meta : {};
        const lines = [
          `<div class="title">${task.name || ""}</div>`,
          `<div class="subtitle">时间：${task.start} ～ ${task.end}</div>`,
          `<div class="subtitle">批次：${meta.batch_id || "-"}</div>`,
          `<div class="subtitle">图号：${meta.part_no || "-"}</div>`,
          `<div class="subtitle">工序：${meta.seq || "-"}</div>`,
          `<div class="subtitle">设备：${meta.machine || "-"}</div>`,
          `<div class="subtitle">人员：${meta.operator || "-"}</div>`,
          `<div class="subtitle">优先级：${meta.priority || "-"}</div>`,
          `<div class="subtitle">交期：${meta.due_date || "-"}</div>`,
        ];
        return lines.join("") + `<div class="pointer"></div>`;
      }
    });

    try {
      const container = document.querySelector(".gantt-container");
      if (container && gantt && gantt.gantt_start) {
        const anchor = String(cfg.startDate || cfg.weekStart || "");
        const target = new Date(anchor + " 00:00:00");
        const diffHours = (target.getTime() - gantt.gantt_start.getTime()) / 3600000.0;
        const px = (diffHours / gantt.options.step) * gantt.options.column_width - gantt.options.column_width;
        container.scrollLeft = Math.max(0, Math.floor(px));
      }
    } catch (_) {
      // 不阻断渲染
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", loadAndRender);
  } else {
    loadAndRender();
  }
})();

