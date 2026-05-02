(function () {
  function $(id) {
    return document.getElementById(id);
  }

  function text(v) {
    return v === null || typeof v === "undefined" ? "" : String(v);
  }

  function trim(v) {
    return text(v).trim();
  }

  function escapeHtml(v) {
    const s = text(v);
    if (!s) return "";
    return s
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function show(el, visible) {
    if (!el) return;
    if (el.classList) {
      el.classList.toggle("is-hidden", !visible);
    }
    el.style.display = visible ? "" : "none";
  }

  function parseJson(value, fallback) {
    if (!value) return fallback;
    try {
      return JSON.parse(value);
    } catch (_err) {
      return fallback;
    }
  }

  function badge(label, variant) {
    return '<span class="badge badge-' + escapeHtml(variant || "unchanged") + '">' + escapeHtml(label) + '</span>';
  }

  function sourceLabel(value) {
    const v = trim(value);
    if (v === "internal") return "自制";
    if (v === "external") return "外协";
    return v || "-";
  }

  function relationBadge(label) {
    const v = trim(label);
    if (v === "跨班组") return badge(v, "update");
    if (v === "同班组") return badge(v, "new");
    if (v) return badge(v, "skip");
    return '<span class="muted">-</span>';
  }

  function renderFlags(row) {
    const items = [];
    if (trim(row && row.lock_status) === "locked") items.push(badge("已锁定", "update"));
    if (row && row.is_overdue) items.push(badge("超期", "error"));
    if (row && row.is_cross_day) items.push(badge("跨天", "skip"));
    return items.length ? items.join(" ") : '<span class="muted">-</span>';
  }

  const pageEl = $("rdPage");
  if (!pageEl) return;

  const state = {
    cfg: {
      filters: parseJson(pageEl.getAttribute("data-filters"), {}),
      dataUrl: trim(pageEl.getAttribute("data-url")),
      hasHistory: pageEl.getAttribute("data-has-history") === "1",
      canQuery: pageEl.getAttribute("data-can-query") === "1",
      exportUrl: trim(pageEl.getAttribute("data-export-url"))
    },
    data: null,
    gantt: null,
    activeTab: "detail"
  };

  function setButtonActive(button, active) {
    if (!button || !button.classList) return;
    button.classList.remove("btn-primary", "btn-secondary");
    button.classList.add(active ? "btn-primary" : "btn-secondary");
  }

  function bindFieldToggles() {
    const scopeTypeEl = $("rdScopeType");
    const periodPresetEl = $("rdPeriodPreset");
    const operatorField = $("rdOperatorField");
    const machineField = $("rdMachineField");
    const teamField = $("rdTeamField");
    const teamAxisField = $("rdTeamAxisField");
    const queryDateField = $("rdQueryDateField");
    const startField = $("rdStartField");
    const endField = $("rdEndField");

    function applyScopeType() {
      const value = trim(scopeTypeEl && scopeTypeEl.value) || "operator";
      show(operatorField, value === "operator");
      show(machineField, value === "machine");
      show(teamField, value === "team");
      show(teamAxisField, value === "team");
    }

    function applyPeriodPreset() {
      const value = trim(periodPresetEl && periodPresetEl.value) || "week";
      const isCustom = value === "custom";
      show(queryDateField, !isCustom);
      show(startField, isCustom);
      show(endField, isCustom);
    }

    if (scopeTypeEl) {
      scopeTypeEl.addEventListener("change", applyScopeType);
      applyScopeType();
    }
    if (periodPresetEl) {
      periodPresetEl.addEventListener("change", applyPeriodPreset);
      applyPeriodPreset();
    }
  }

  function renderSummary(summary) {
    const data = summary || {};
    $("rdSummaryTotalTasks").textContent = text(data.total_tasks || 0);
    $("rdSummaryTotalHours").textContent = text(data.total_hours || 0);
    $("rdSummaryOverdue").textContent = text(data.overdue_count || 0);
    $("rdSummaryCrossTeam").textContent = text(data.cross_team_count || 0);
    $("rdSummaryExternal").textContent = text(data.external_count || 0);
    $("rdSummaryCrossDay").textContent = text(data.cross_day_count || 0);
  }

  function buildDetailRowsHtml(rows, emptyText) {
    const list = Array.isArray(rows) ? rows : [];
    if (!list.length) {
      return '<tr><td colspan="10" class="muted">' + escapeHtml(emptyText || "暂无排班任务。") + '</td></tr>';
    }
    const html = [];
    for (let i = 0; i < list.length; i++) {
      const row = list[i] || {};
      html.push(
        '<tr>' +
          '<td>' + escapeHtml(row.start_time || "") + '</td>' +
          '<td>' + escapeHtml(row.end_time || "") + '</td>' +
          '<td>' + escapeHtml(row.batch_id || "") + '</td>' +
          '<td>' + escapeHtml(row.part_no || "") + '</td>' +
          '<td>' + escapeHtml(row.op_code || "") + '</td>' +
          '<td>' + escapeHtml(row.seq) + '</td>' +
          '<td>' + escapeHtml(row.counterpart_resource_label || "") + '</td>' +
          '<td>' + relationBadge(row.team_relation_label) + '</td>' +
          '<td>' + escapeHtml(sourceLabel(row.source)) + '</td>' +
          '<td>' + renderFlags(row) + '</td>' +
        '</tr>'
      );
    }
    return html.join("");
  }

  function renderDetailRows(rows) {
    const tbody = $("rdDetailBody");
    if (!tbody) return;
    tbody.innerHTML = buildDetailRowsHtml(rows, "暂无排班任务。");
  }

  function renderTeamTables(data) {
    const teamBlocks = $("rdTeamBlocks");
    const operatorBody = $("rdTeamOperatorBody");
    const machineBody = $("rdTeamMachineBody");
    const crossWrap = $("rdTeamCrossWrap");
    const crossBody = $("rdTeamCrossBody");
    const filters = (data && data.filters) || {};
    const isTeam = trim(filters.scope_type) === "team";
    show(teamBlocks, isTeam && state.activeTab === "detail");
    if (!isTeam) {
      if (operatorBody) operatorBody.innerHTML = buildDetailRowsHtml([], "暂无数据。");
      if (machineBody) machineBody.innerHTML = buildDetailRowsHtml([], "暂无数据。");
      if (crossBody) crossBody.innerHTML = buildDetailRowsHtml([], "暂无跨班组任务。");
      show(crossWrap, false);
      return;
    }
    if (operatorBody) operatorBody.innerHTML = buildDetailRowsHtml(data.operator_rows || [], "暂无班组人员任务。");
    if (machineBody) machineBody.innerHTML = buildDetailRowsHtml(data.machine_rows || [], "暂无班组设备任务。");
    if (crossBody) crossBody.innerHTML = buildDetailRowsHtml(data.cross_team_rows || [], "暂无跨班组任务。");
    show(crossWrap, Array.isArray(data.cross_team_rows) && data.cross_team_rows.length > 0);
  }

  function renderCalendar(headers, rows) {
    const wrap = $("rdCalendarWrap");
    if (!wrap) return;
    const headerList = Array.isArray(headers) ? headers : [];
    const rowList = Array.isArray(rows) ? rows : [];
    if (!headerList.length || !rowList.length) {
      wrap.innerHTML = '<div class="muted">暂无日历矩阵数据。</div>';
      return;
    }

    const html = [];
    html.push('<table class="table-sticky"><thead><tr><th class="w-180">查询对象</th>');
    for (let i = 0; i < headerList.length; i++) {
      const d = trim(headerList[i]);
      html.push('<th class="w-160">' + escapeHtml(d) + '</th>');
    }
    html.push('</tr></thead><tbody>');
    for (let r = 0; r < rowList.length; r++) {
      const row = rowList[r] || {};
      html.push('<tr>');
      html.push('<td>' + escapeHtml(row.scope_label || "") + '</td>');
      const cells = Array.isArray(row.cells) ? row.cells : [];
      for (let c = 0; c < cells.length; c++) {
        const cell = cells[c] || {};
        const items = Array.isArray(cell.items) ? cell.items : [];
        if (!items.length) {
          html.push('<td class="muted">-</td>');
          continue;
        }
        const lines = [];
        for (let j = 0; j < items.length; j++) {
          const item = items[j] || {};
          const cls = item.is_overdue ? ' style="color:#b91c1c;font-weight:600;"' : "";
          lines.push('<div' + cls + '>' + escapeHtml(item.text || "") + '</div>');
        }
        html.push('<td style="white-space:normal;min-width:140px;">' + lines.join("") + '</td>');
      }
      html.push('</tr>');
    }
    html.push('</tbody></table>');
    wrap.innerHTML = html.join("");
  }

  function ganttPopup(task) {
    const meta = (task && task.meta) || {};
    const lines = [
      '<div class="details-popup">',
      '<h5 style="margin:0 0 6px;">' + escapeHtml(meta.op_code || task.name || "任务") + '</h5>',
      '<div>批次：' + escapeHtml(meta.batch_id || "-") + '</div>',
      '<div>图号：' + escapeHtml(meta.part_no || "-") + '</div>',
      '<div>开始：' + escapeHtml(task.start || "") + '</div>',
      '<div>结束：' + escapeHtml(task.end || "") + '</div>',
      '<div>对应资源：' + escapeHtml(meta.counterpart_resource_label || "-") + '</div>',
      '<div>班组关系：' + escapeHtml(meta.team_relation_label || "-") + '</div>',
      '</div>'
    ];
    return lines.join("");
  }

  function renderGantt(tasks) {
    const wrap = $("rdGantt");
    if (!wrap) return;
    const list = Array.isArray(tasks) ? tasks : [];
    if (!list.length) {
      wrap.innerHTML = '<div class="muted">暂无甘特任务。</div>';
      state.gantt = null;
      return;
    }
    if (typeof window.Gantt !== "function") {
      wrap.innerHTML = '<div class="error">甘特图脚本未加载完成，请刷新页面后重试。</div>';
      state.gantt = null;
      return;
    }
    wrap.innerHTML = "";
    try {
      state.gantt = new window.Gantt("#rdGantt", list, {
        view_mode: trim($("rdGanttMode") && $("rdGanttMode").value) || "Day",
        language: "zh",
        popup_trigger: "click",
        custom_popup_html: ganttPopup
      });
    } catch (_err) {
      wrap.innerHTML = '<div class="error">甘特图渲染失败，请稍后重试。</div>';
      state.gantt = null;
    }
  }

  function activateTab(name) {
    state.activeTab = name;
    const detail = $("rdDetailPanel");
    const calendar = $("rdCalendarPanel");
    const gantt = $("rdGanttPanel");
    const ganttModeField = $("rdGanttModeField");
    const teamBlocks = $("rdTeamBlocks");
    const isTeam = !!(state.data && state.data.filters && state.data.filters.scope_type === "team");
    show(detail, name === "detail" && !isTeam);
    show(calendar, name === "calendar");
    show(gantt, name === "gantt");
    show(ganttModeField, name === "gantt");
    show(teamBlocks, name === "detail" && isTeam);
    setButtonActive($("rdTabDetail"), name === "detail");
    setButtonActive($("rdTabCalendar"), name === "calendar");
    setButtonActive($("rdTabGantt"), name === "gantt");
    if (name === "gantt" && state.data) {
      renderGantt(state.data.tasks || []);
    }
  }

  function bindTabs() {
    const detailBtn = $("rdTabDetail");
    const calendarBtn = $("rdTabCalendar");
    const ganttBtn = $("rdTabGantt");
    const ganttMode = $("rdGanttMode");
    if (detailBtn) detailBtn.addEventListener("click", function () { activateTab("detail"); });
    if (calendarBtn) calendarBtn.addEventListener("click", function () { activateTab("calendar"); });
    if (ganttBtn) ganttBtn.addEventListener("click", function () { activateTab("gantt"); });
    if (ganttMode) {
      ganttMode.addEventListener("change", function () {
        if (state.activeTab === "gantt" && state.data) {
          renderGantt(state.data.tasks || []);
        }
      });
    }
    activateTab("detail");
  }

  function setError(message) {
    const el = $("rdError");
    if (!el) return;
    el.textContent = trim(message);
    show(el, !!trim(message));
  }

  function setEmpty(message) {
    const el = $("rdEmpty");
    if (!el) return;
    el.textContent = trim(message);
    show(el, !!trim(message));
  }

  function setOverdueWarning(message) {
    const el = $("rdOverdueWarning");
    if (!el) return;
    const textMessage = trim(message);
    if (textMessage) {
      el.textContent = textMessage;
    }
    show(el, !!textMessage);
  }

  function setDegradationSummary(summary) {
    const card = $("rdDegradationSummary");
    const listEl = $("rdDegradationList");
    if (!card || !listEl) return;
    const events = (summary && Array.isArray(summary.degradation_events)) ? summary.degradation_events : [];
    if (!events.length) {
      listEl.innerHTML = "";
      show(card, false);
      return;
    }
    const items = [];
    for (let i = 0; i < events.length; i++) {
      const event = events[i] || {};
      const code = trim(event.code);
      const message = trim(event.message);
      const count = Number(event.count || 0);
      const parts = [];
      if (message) {
        parts.push(escapeHtml(message));
      } else if (code) {
        parts.push("有一条排班提示没有完整说明");
      }
      if (count > 1) {
        parts.push("×" + escapeHtml(count));
      }
      if (!parts.length) continue;
      items.push("<li>" + parts.join(" ") + "</li>");
    }
    listEl.innerHTML = items.join("");
    show(card, items.length > 0);
  }

  function currentQueryString() {
    const qs = trim(window.location.search || "");
    if (qs) return qs;
    const filters = state.cfg.filters || {};
    const params = new URLSearchParams();
    if (trim(filters.scope_type)) params.set("scope_type", trim(filters.scope_type));
    if (trim(filters.operator_id)) params.set("operator_id", trim(filters.operator_id));
    if (trim(filters.machine_id)) params.set("machine_id", trim(filters.machine_id));
    if (trim(filters.team_id)) params.set("team_id", trim(filters.team_id));
    if (trim(filters.team_axis)) params.set("team_axis", trim(filters.team_axis));
    if (trim(filters.period_preset)) params.set("period_preset", trim(filters.period_preset));
    if (trim(filters.query_date)) params.set("query_date", trim(filters.query_date));
    if (trim(filters.start_date)) params.set("start_date", trim(filters.start_date));
    if (trim(filters.end_date)) params.set("end_date", trim(filters.end_date));
    if (trim(filters.version)) params.set("version", trim(filters.version));
    const textQs = params.toString();
    return textQs ? ("?" + textQs) : "";
  }

  async function loadData() {
    if (!state.cfg.hasHistory || !state.cfg.canQuery || !state.cfg.dataUrl) return;
    renderDetailRows([]);
    renderCalendar([], []);
    setError("");
    setEmpty("");
    setOverdueWarning("");
    setDegradationSummary(null);
    try {
      const resp = await fetch(state.cfg.dataUrl + currentQueryString(), { headers: { Accept: "application/json" } });
      const payload = await resp.json();
      if (!resp.ok || !payload || payload.success !== true) {
        const errorMessage = payload && payload.error && payload.error.message ? payload.error.message : "资源排班数据加载失败，请稍后重试。";
        throw new Error(errorMessage);
      }
      state.data = payload.data || {};
      renderSummary(state.data.summary || {});
      renderDetailRows(state.data.detail_rows || []);
      renderTeamTables(state.data || {});
      renderCalendar(state.data.calendar_headers || [], state.data.calendar_rows || []);
      setDegradationSummary(state.data.summary || {});
      activateTab(state.activeTab || "detail");
      setEmpty(state.data.empty_message || "");
      const hasOverdueWarning = state.data.overdue_markers_degraded === true || state.data.overdue_markers_partial === true;
      const overdueWarningFallback = state.data.overdue_markers_partial
        ? "部分超期标记可能不完整，当前仍按已识别条目标记。"
        : "超期统计和标记可能不完整，请稍后重试或查看系统历史。";
      setOverdueWarning(
        hasOverdueWarning ? (state.data.overdue_markers_message || overdueWarningFallback) : ""
      );
      if (state.activeTab === "gantt") {
        renderGantt(state.data.tasks || []);
      }
    } catch (err) {
      setError(err && err.message ? err.message : "资源排班数据加载失败，请稍后重试。");
      renderDetailRows([]);
      state.data = null;
      renderTeamTables({});
      renderCalendar([], []);
      setOverdueWarning("");
      setDegradationSummary(null);
    }
  }

  bindFieldToggles();
  bindTabs();
  loadData();
})();
