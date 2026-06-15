(function () {
  const ns = window.__APS_RESOURCE_DISPATCH__;
  const state = ns.state;
  const $ = ns.$;
  const text = ns.text;
  const trim = ns.trim;
  const escapeHtml = ns.escapeHtml;
  const show = ns.show;
  const badge = ns.badge;
  const sourceLabel = ns.sourceLabel;
  const relationBadge = ns.relationBadge;
  const codeCell = ns.codeCell;
  const fullTextCell = ns.fullTextCell;
  const resourceDisplayHtml = ns.resourceDisplayHtml;
  const resourceCell = ns.resourceCell;
  const calendarTaskHtml = ns.calendarTaskHtml;
  const renderFlags = ns.renderFlags;
  const latestExceptionSummary = ns.latestExceptionSummary;
  const affectedResourceCell = ns.affectedResourceCell;
  const affectedResourcePopupHtml = ns.affectedResourcePopupHtml;

  function loadExecutionData() {
    return ns.execution.loadExecutionData();
  }

  function renderExecutionCards(payload) {
    return ns.execution.renderExecutionCards(payload);
  }

  function setButtonActive(button, active) {
    if (!button || !button.classList) return;
    button.classList.remove("btn-primary", "btn-secondary");
    button.classList.add(active ? "btn-primary" : "btn-secondary");
  }

  function bindFieldToggles() {
    const queryForm = document.querySelector(".aps-resource-query-grid");
    const scopeTypeEl = $("rdScopeType");
    const periodPresetEl = $("rdPeriodPreset");
    const teamAxisField = $("rdTeamAxisField");
    const queryDateField = $("rdQueryDateField");
    const startField = $("rdStartField");
    const endField = $("rdEndField");

    function applyScopeType() {
      const value = trim(scopeTypeEl && scopeTypeEl.value) || "operator";
      const labelEl = $("rdScopeTargetLabel");
      const targetMap = {
        operator: "人员",
        machine: "设备",
        team: "班组"
      };
      if (labelEl) labelEl.textContent = targetMap[value] || "人员";

      document.querySelectorAll("[data-scope-target]").forEach(function (el) {
        const active = trim(el.getAttribute("data-scope-target")) === value;
        show(el, active);
        el.disabled = !active;
      });

      const teamAxisSelect = teamAxisField ? teamAxisField.querySelector("select") : null;
      if (teamAxisField && teamAxisField.classList) {
        teamAxisField.classList.toggle("is-disabled", value !== "team");
        teamAxisField.hidden = value !== "team";
      }
      if (queryForm && queryForm.classList) {
        queryForm.classList.toggle("has-team-axis", value === "team");
      }
      if (teamAxisSelect) {
        teamAxisSelect.disabled = value !== "team";
      }
    }

    function applyPeriodPreset() {
      const value = trim(periodPresetEl && periodPresetEl.value) || "week";
      const isCustom = value === "custom";
      show(queryDateField, !isCustom);
      show(startField, isCustom);
      show(endField, isCustom);
      if (queryForm && queryForm.classList) {
        queryForm.classList.toggle("has-custom-period", isCustom);
      }
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
      return '<tr><td colspan="14" class="muted">' + escapeHtml(emptyText || "暂无排班任务。") + '</td></tr>';
    }
    const html = [];
    for (let i = 0; i < list.length; i++) {
      const row = list[i] || {};
      html.push(
        '<tr>' +
          '<td>' + escapeHtml(row.start_time || "") + '</td>' +
          '<td>' + escapeHtml(row.end_time || "") + '</td>' +
          '<td>' + codeCell(row.batch_id || "") + '</td>' +
          '<td>' + codeCell(row.part_no || "") + '</td>' +
          '<td>' + codeCell(row.op_code || "") + '</td>' +
          '<td>' + escapeHtml(row.seq) + '</td>' +
          resourceCell(row, "current_resource", "aps-resource-cell", "") +
          resourceCell(row, "counterpart_resource", "aps-resource-cell", "") +
          '<td>' + relationBadge(row.team_relation_label) + '</td>' +
          '<td>' + escapeHtml(sourceLabel(row.source, row.source_label)) + '</td>' +
          '<td>' + renderFlags(row) + '</td>' +
          '<td>' + escapeHtml(row.execution_status_label || "待开工") + '</td>' +
          fullTextCell(latestExceptionSummary(row), "aps-resource-cell") +
          affectedResourceCell(row) +
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
    html.push('<table id="rdCalendarTable" class="table-sticky table-sticky-col table-layout-fixed aps-table-xwide aps-resource-calendar-table" data-col-resize="1" data-table-key="v1_resourceDispatchCalendar"><thead><tr><th class="w-200 aps-calendar-scope-head" data-col-key="scope" data-default-w="200" data-min-w="160">查询对象</th>');
    for (let i = 0; i < headerList.length; i++) {
      const d = trim(headerList[i]);
      html.push('<th class="w-180" data-col-key="day_' + escapeHtml(String(i)) + '" data-default-w="180" data-min-w="150">' + escapeHtml(d) + '</th>');
    }
    html.push('</tr></thead><tbody>');
    for (let r = 0; r < rowList.length; r++) {
      const row = rowList[r] || {};
      html.push('<tr>');
      html.push(resourceCell(row, "current_resource", "aps-resource-cell aps-calendar-scope-cell", row.scope_label || ""));
      const cells = Array.isArray(row.cells) ? row.cells : [];
      for (let c = 0; c < cells.length; c++) {
        const cell = cells[c] || {};
        const items = Array.isArray(cell.items) ? cell.items : [];
        if (!items.length) {
          html.push('<td class="muted aps-calendar-empty-cell">-</td>');
          continue;
        }
        const lines = [];
        for (let j = 0; j < items.length; j++) {
          lines.push(calendarTaskHtml(items[j] || {}));
        }
        html.push('<td class="aps-calendar-cell">' + lines.join("") + '</td>');
      }
      html.push('</tr>');
    }
    html.push('</tbody></table>');
    wrap.innerHTML = html.join("");
    if (typeof window.APS_InitResizableTables === "function") {
      try {
        window.APS_InitResizableTables(wrap);
      } catch (err) {
        if (window.console && typeof window.console.warn === "function") {
          window.console.warn("资源派工日历表格列宽初始化失败", err);
        }
      }
    }
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
      '<div>对应资源：' + resourceDisplayHtml(meta, "counterpart_resource", "-") + '</div>',
      '<div>班组关系：' + escapeHtml(meta.team_relation_label || "-") + '</div>',
      '<div>现场状态：' + escapeHtml(meta.execution_status_label || "待开工") + '</div>',
      '<div>最近异常：' + escapeHtml(latestExceptionSummary(meta)) + '</div>',
      affectedResourcePopupHtml(meta),
      '</div>'
    ];
    return lines.join("");
  }

  function installResourceGanttPopupAutoFit(gantt) {
    if (window.__APS_GANTT_POPUP_FIT__ && typeof window.__APS_GANTT_POPUP_FIT__.install === "function") {
      window.__APS_GANTT_POPUP_FIT__.install(gantt);
    }
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
      installResourceGanttPopupAutoFit(state.gantt);
    } catch (err) {
      if (window.console && typeof window.console.warn === "function") {
        window.console.warn("资源派工甘特图渲染失败", err);
      }
      wrap.innerHTML = '<div class="error">甘特图渲染失败，请稍后重试。</div>';
      state.gantt = null;
    }
  }

  function activateTab(name) {
    state.activeTab = name;
    const detail = $("rdDetailPanel");
    const execution = $("rdExecutionPanel");
    const calendar = $("rdCalendarPanel");
    const gantt = $("rdGanttPanel");
    const ganttModeField = $("rdGanttModeField");
    const teamBlocks = $("rdTeamBlocks");
    const isTeam = !!(state.data && state.data.filters && state.data.filters.scope_type === "team");
    show(detail, name === "detail" && !isTeam);
    show(execution, name === "execution");
    show(calendar, name === "calendar");
    show(gantt, name === "gantt");
    show(ganttModeField, name === "gantt");
    show(teamBlocks, name === "detail" && isTeam);
    setButtonActive($("rdTabDetail"), name === "detail");
    setButtonActive($("rdTabExecution"), name === "execution");
    setButtonActive($("rdTabCalendar"), name === "calendar");
    setButtonActive($("rdTabGantt"), name === "gantt");
    if (name === "gantt" && state.data) {
      renderGantt(state.data.tasks || []);
    }
  }

  function bindTabs() {
    const detailBtn = $("rdTabDetail");
    const executionBtn = $("rdTabExecution");
    const calendarBtn = $("rdTabCalendar");
    const ganttBtn = $("rdTabGantt");
    const ganttMode = $("rdGanttMode");
    if (detailBtn) detailBtn.addEventListener("click", function () { activateTab("detail"); });
    if (executionBtn) executionBtn.addEventListener("click", function () { activateTab("execution"); });
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
    if (trim(filters.plan_role)) params.set("plan_role", trim(filters.plan_role));
    if (trim(filters.plan_context_token)) params.set("plan_context_token", trim(filters.plan_context_token));
    const textQs = params.toString();
    return textQs ? ("?" + textQs) : "";
  }

  function dataRequestUrl() {
    const url = state.cfg.dataUrl || "";
    if (!url) return "";
    return url.indexOf("?") >= 0 ? url : url + currentQueryString();
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
      const resp = await fetch(dataRequestUrl(), { headers: { Accept: "application/json" } });
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
        : "超期统计和标记可能不完整，请刷新后重试，或到系统管理里的排产历史查看这次排产的详细提醒。";
      setOverdueWarning(
        hasOverdueWarning ? (state.data.overdue_markers_message || overdueWarningFallback) : ""
      );
      if (state.activeTab === "gantt") {
        renderGantt(state.data.tasks || []);
      }
      loadExecutionData();
    } catch (err) {
      setError(err && err.message ? err.message : "资源排班数据加载失败，请稍后重试。");
      renderDetailRows([]);
      state.data = null;
      renderTeamTables({});
      renderCalendar([], []);
      setOverdueWarning("");
      setDegradationSummary(null);
      renderExecutionCards(null);
    }
  }

  ns.core = {
    bindFieldToggles: bindFieldToggles,
    bindTabs: bindTabs,
    currentQueryString: currentQueryString,
    loadData: loadData
  };
})();
