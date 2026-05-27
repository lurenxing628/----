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

  function sourceLabel(value, publicLabel) {
    const label = trim(publicLabel); if (label) return label;
    const v = trim(value);
    if (v === "internal" || v === "external") return v === "internal" ? "自制" : "外协";
    return v ? "来源未识别" : "来源未维护";
  }

  function lockStatusLabel(value, publicLabel) {
    const label = trim(publicLabel); if (label) return label;
    const v = trim(value);
    if (v === "locked" || v === "unlocked" || !v) return v === "locked" ? "已锁定" : "未锁定";
    return "锁定状态未识别";
  }

  function relationBadge(label) {
    const v = trim(label);
    if (v === "跨班组") return badge(v, "update");
    if (v === "同班组") return badge(v, "new");
    if (v) return badge(v, "skip");
    return '<span class="muted">-</span>';
  }

  function codeCell(value) {
    const v = text(value);
    return '<span class="aps-col-code" title="' + escapeHtml(v) + '">' + escapeHtml(v) + '</span>';
  }

  function fullTextCell(value, className) {
    const v = text(value);
    const classAttr = className ? ' class="' + escapeHtml(className) + '"' : "";
    const safe = escapeHtml(v);
    return '<td' + classAttr + ' title="' + safe + '" data-full-text="' + safe + '">' + safe + '</td>';
  }

  function renderFlags(row) {
    const items = [];
    const lockLabel = lockStatusLabel(row && row.lock_status, row && row.lock_status_label);
    if (lockLabel === "已锁定") items.push(badge(lockLabel, "update"));
    else if (lockLabel === "锁定状态未识别") items.push(badge(lockLabel, "skip"));
    if (row && row.is_overdue) items.push(badge("超期", "error"));
    if (row && row.is_cross_day) items.push(badge("跨天", "skip"));
    return items.length ? items.join(" ") : '<span class="muted">-</span>';
  }

  function latestExceptionSummary(row) {
    const reason = trim(row && row.latest_exception_reason_label);
    if (!reason || reason === "暂无异常") return "暂无异常";
    const parts = [reason];
    const severity = trim(row && row.latest_exception_severity_label);
    const impact = trim(row && row.latest_exception_impact_minutes_label);
    const handling = trim(row && row.latest_exception_handling_status_label);
    const suggest = trim(row && row.latest_exception_suggest_reschedule_label);
    const remark = trim(row && row.latest_exception_remark);
    if (severity) parts.push(severity);
    if (impact) parts.push(impact);
    if (handling) parts.push(handling);
    if (suggest) parts.push(suggest);
    if (remark) parts.push(remark);
    return parts.join("；");
  }

  function affectedResourceSummary(row) {
    const reason = trim(row && row.latest_exception_reason_label);
    if (!reason || reason === "暂无异常") return "暂无异常";
    const machine = trim(row && row.latest_exception_affected_machine_label) || "未填写影响设备";
    const operator = trim(row && row.latest_exception_affected_operator_label) || "未填写影响人员";
    return machine + "；" + operator;
  }

  const pageEl = $("rdPage");
  if (!pageEl) return;

  const state = {
    cfg: {
      filters: parseJson(pageEl.getAttribute("data-filters"), {}),
      dataUrl: trim(pageEl.getAttribute("data-url")),
      executionUrl: trim(pageEl.getAttribute("data-execution-url")),
      hasHistory: pageEl.getAttribute("data-has-history") === "1",
      canQuery: pageEl.getAttribute("data-can-query") === "1",
      exportUrl: trim(pageEl.getAttribute("data-export-url"))
    },
    data: null,
    execution: null,
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
          fullTextCell(row.current_resource_label || "", "aps-resource-cell") +
          fullTextCell(row.counterpart_resource_label || "", "aps-resource-cell") +
          '<td>' + relationBadge(row.team_relation_label) + '</td>' +
          '<td>' + escapeHtml(sourceLabel(row.source, row.source_label)) + '</td>' +
          '<td>' + renderFlags(row) + '</td>' +
          '<td>' + escapeHtml(row.execution_status_label || "待开工") + '</td>' +
          fullTextCell(latestExceptionSummary(row), "aps-resource-cell") +
          fullTextCell(affectedResourceSummary(row), "aps-resource-cell") +
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

  function renderExecutionActions(actions, task) {
    const list = Array.isArray(actions) ? actions : [];
    if (!list.length) return '<span class="muted">暂无可用操作</span>';
    const html = [];
    const row = task || {};
    for (let i = 0; i < list.length; i++) {
      const action = list[i] || {};
      const disabledReason = trim(action.disabled_reason);
      const disabledAttr = action.enabled ? "" : " disabled";
      const titleAttr = disabledReason ? ' title="' + escapeHtml(disabledReason) + '"' : "";
      html.push(
        '<button type="button" class="btn btn-secondary btn-sm aps-execution-action" data-action="' +
          escapeHtml(action.action || "") + '" data-op-id="' + escapeHtml(row.op_id || "") +
          '" data-schedule-id="' + escapeHtml(row.schedule_id || "") +
          '" data-batch-id="' + escapeHtml(row.batch_id || "") +
          '" data-state-revision="' + escapeHtml(row.state_revision || "") +
          '" data-machine-id="' + escapeHtml(row.planned_machine_id || "") +
          '" data-operator-id="' + escapeHtml(row.planned_operator_id || "") + '"' + disabledAttr + titleAttr + '>' +
          escapeHtml(action.label || "操作") +
        '</button>'
      );
    }
    return html.join(" ");
  }

  const EXECUTION_REASON_CODES = {
    "设备问题": "equipment",
    "人员问题": "person",
    "物料问题": "material",
    "质量问题": "quality",
    "工艺问题": "process",
    "外协问题": "external",
    "其他": "other"
  };
  const EXECUTION_SEVERITY_CODES = {
    "轻微": "low",
    "一般": "medium",
    "严重": "high",
    "紧急": "critical"
  };
  const EXECUTION_HANDLING_CODES = {
    "刚上报": "new",
    "处理中": "checking",
    "等待条件": "waiting",
    "已处理": "handled"
  };

  function executionCodeFromChinese(input, mapping) {
    const text = trim(input);
    return mapping[text] || "";
  }

  function executionPrompt(message, defaultValue) {
    if (!window.prompt) return "";
    const value = window.prompt(message, defaultValue || "");
    return value === null ? null : trim(value);
  }

  function executionPromptReason() {
    const value = executionPrompt("请选择原因：设备问题、人员问题、物料问题、质量问题、工艺问题、外协问题、其他", "");
    if (value === null) return null;
    const code = executionCodeFromChinese(value, EXECUTION_REASON_CODES);
    if (!code) {
      executionNotice("请选择有效原因，例如设备问题、人员问题、物料问题。");
      return null;
    }
    return code;
  }

  function executionPromptSeverity() {
    const value = executionPrompt("请选择严重程度：轻微、一般、严重、紧急", "一般");
    if (value === null) return null;
    const code = executionCodeFromChinese(value, EXECUTION_SEVERITY_CODES);
    if (!code) {
      executionNotice("请选择有效严重程度，例如一般、严重。");
      return null;
    }
    return code;
  }

  function executionPromptStartResource(button) {
    const plannedMachine = button.getAttribute("data-machine-id") || "";
    const plannedOperator = button.getAttribute("data-operator-id") || "";
    const machine = executionPrompt("请确认实际设备编号（需与当前计划设备一致）", plannedMachine);
    if (machine === null) return null;
    if (!trim(machine)) {
      executionNotice("请填写实际设备编号。");
      return null;
    }
    const operator = executionPrompt("请填写实际人员工号（默认当前计划人员）", plannedOperator);
    if (operator === null) return null;
    if (!trim(operator)) {
      executionNotice("请填写实际人员工号。");
      return null;
    }
    return { machine_id: trim(machine), operator_id: trim(operator) };
  }

  function renderExecutionExceptionDetails(task) {
    if (!trim(task && task.latest_exception_reason_label)) return "";
    const impact = trim(task.latest_exception_impact_minutes_label) || "暂时不知道影响多久";
    const machine = trim(task.latest_exception_affected_machine_label) || "未填写影响设备";
    const operator = trim(task.latest_exception_affected_operator_label) || "未填写影响人员";
    const handling = trim(task.latest_exception_handling_status_label) || "刚上报";
    const suggest = trim(task.latest_exception_suggest_reschedule_label) || "暂不建议重新排程";
    const remark = trim(task.latest_exception_remark) || "未填写情况说明";
    const criticalNotice = trim(task.latest_exception_severity_label) === "紧急"
      ? '<div class="flash-card flash-warning mt-2">紧急异常，请计划员尽快处理。</div>'
      : "";
    return (
      '<div class="text-meta mt-2">最近异常</div>' +
      criticalNotice +
      '<div class="aps-execution-facts aps-execution-exception-facts">' +
        '<div><span>异常原因</span><strong>' + escapeHtml(task.latest_exception_reason_label || "暂无异常") + '</strong></div>' +
        '<div><span>严重程度</span><strong>' + escapeHtml(task.latest_exception_severity_label || "未填写严重程度") + '</strong></div>' +
        '<div><span>预计影响时间</span><strong>' + escapeHtml(impact) + '</strong></div>' +
        '<div><span>影响设备</span><strong>' + escapeHtml(machine) + '</strong></div>' +
        '<div><span>影响人员</span><strong>' + escapeHtml(operator) + '</strong></div>' +
        '<div><span>处理状态</span><strong>' + escapeHtml(handling) + '</strong></div>' +
        '<div><span>是否建议重排</span><strong>' + escapeHtml(suggest) + '</strong></div>' +
        '<div><span>情况说明</span><strong>' + escapeHtml(remark) + '</strong></div>' +
      '</div>'
    );
  }

  function executionUnavailableReasonText(reasons) {
    if (Array.isArray(reasons)) {
      return reasons.length ? reasons.map(escapeHtml).join("；") : "";
    }
    if (!reasons || typeof reasons !== "object") return "";
    const seen = {};
    const lines = [];
    Object.keys(reasons).forEach(function (key) {
      const item = trim(reasons[key]);
      if (item && !seen[item]) {
        seen[item] = true;
        lines.push(escapeHtml(item));
      }
    });
    return lines.join("；");
  }

  function renderExecutionCards(payload) {
    const wrap = $("rdExecutionCards");
    const notice = $("rdExecutionNotice");
    if (!wrap) return;
    const data = payload || {};
    const tasks = Array.isArray(data.tasks) ? data.tasks : [];
    const disabledReason = trim(data.disabled_reason);
    if (notice) {
      notice.textContent = disabledReason;
      show(notice, !!disabledReason);
    }
    if (!tasks.length) {
      wrap.innerHTML = '<div class="muted">当前查询范围内暂无现场反馈任务卡。</div>';
      return;
    }
    const cards = [];
    for (let i = 0; i < tasks.length; i++) {
      const task = tasks[i] || {};
      const reasonText = executionUnavailableReasonText(task.unavailable_reasons);
      cards.push(
        '<section class="aps-execution-card">' +
          '<div class="aps-execution-card-head">' +
            '<div>' +
              '<div class="aps-execution-title">' + escapeHtml(task.op_name || "未命名工序") + '</div>' +
              '<div class="text-meta">批次：' + escapeHtml(task.batch_id || "-") + '</div>' +
            '</div>' +
            '<span class="badge badge-skip">' + escapeHtml(task.current_status_label || "待开工") + '</span>' +
          '</div>' +
          '<div class="aps-execution-facts">' +
            '<div><span>计划开始</span><strong>' + escapeHtml(task.planned_start_time || "-") + '</strong></div>' +
            '<div><span>实际开始</span><strong>' + escapeHtml(task.actual_start_time || "暂无") + '</strong></div>' +
            '<div><span>计划结束</span><strong>' + escapeHtml(task.planned_end_time || "-") + '</strong></div>' +
            '<div><span>实际结束</span><strong>' + escapeHtml(task.actual_end_time || "暂无") + '</strong></div>' +
            '<div><span>计划设备</span><strong>' + escapeHtml(task.planned_machine_label || "-") + '</strong></div>' +
            '<div><span>实际设备</span><strong>' + escapeHtml(task.actual_machine_label || "暂无") + '</strong></div>' +
            '<div><span>计划人员</span><strong>' + escapeHtml(task.planned_operator_label || "-") + '</strong></div>' +
            '<div><span>实际人员</span><strong>' + escapeHtml(task.actual_operator_label || "暂无") + '</strong></div>' +
          '</div>' +
          (task.last_event_action_label ? '<div class="text-meta mt-1">最近反馈：' + escapeHtml(task.last_event_action_label) + (task.last_event_remark ? '，' + escapeHtml(task.last_event_remark) : '') + '</div>' : '') +
          renderExecutionExceptionDetails(task) +
          (reasonText ? '<div class="text-meta mt-1">' + reasonText + '</div>' : '') +
          '<div class="aps-execution-actions mt-2">' + renderExecutionActions(task.available_actions, task) + '</div>' +
        '</section>'
      );
    }
    wrap.innerHTML = cards.join("");
  }

  function executionNotice(message) {
    const notice = $("rdExecutionNotice");
    if (!notice) return;
    notice.textContent = trim(message);
    show(notice, !!trim(message));
  }

  function localDateTimeText(date) {
    const d = date || new Date();
    function pad(v) {
      return String(v).padStart(2, "0");
    }
    return (
      d.getFullYear() + "-" +
      pad(d.getMonth() + 1) + "-" +
      pad(d.getDate()) + " " +
      pad(d.getHours()) + ":" +
      pad(d.getMinutes()) + ":" +
      pad(d.getSeconds())
    );
  }

  function executionActionPath(action) {
    if (action === "report_exception") return "report-exception";
    return action;
  }

  function executionIdentityPayload() {
    const identity = (state.execution && state.execution.plan_identity) || {};
    const filters = state.cfg.filters || {};
    return {
      version: identity.version || filters.version || "",
      requested_plan_role: identity.requested_plan_role || filters.plan_role || "adopted",
      effective_plan_role: identity.effective_plan_role || "adopted",
      source_table: identity.source_table || "schedule",
      scenario_id: identity.scenario_id || null
    };
  }

  function executionCreatedBy() {
    const input = $("rdExecutionCreatedBy");
    const createdBy = input ? trim(input.value) : "";
    if (!createdBy) {
      executionNotice("请先填写反馈人。");
      if (input && input.focus) input.focus();
      return null;
    }
    return createdBy;
  }

  function executionPayload(button, action, createdBy) {
    const payload = executionIdentityPayload();
    payload.schedule_id = button.getAttribute("data-schedule-id") || "";
    payload.batch_id = button.getAttribute("data-batch-id") || "";
    payload.expected_state_revision = button.getAttribute("data-state-revision") || "";
    payload.event_time = localDateTimeText(new Date());
    payload.created_by = createdBy;
    payload.idempotency_key = [
      "resource-dispatch",
      action,
      button.getAttribute("data-op-id") || "",
      String(Date.now())
    ].join("-");
    payload.remark = "";
    if (action === "start") {
      const actualResource = executionPromptStartResource(button);
      if (actualResource === null) return null;
      payload.machine_id = actualResource.machine_id;
      payload.operator_id = actualResource.operator_id;
    } else if (action === "pause") {
      const reason = executionPromptReason();
      if (reason === null) return null;
      const detail = executionPrompt("请填写情况说明", "");
      if (detail === null) return null;
      payload.reason_code = reason;
      payload.remark = detail;
    } else if (action === "resume") {
      const detail = executionPrompt("请填写情况说明（可留空）", "");
      if (detail === null) return null;
      payload.remark = detail;
    } else if (action === "finish") {
      const qty = window.prompt ? window.prompt("请填写完成数量", "") : "";
      if (qty === null) return null;
      payload.quantity_done = qty;
      payload.quantity_scrapped = "";
    } else if (action === "report_exception") {
      const reason = executionPromptReason();
      if (reason === null) return null;
      const severity = executionPromptSeverity();
      if (severity === null) return null;
      const impact = executionPrompt("预计影响多少分钟？不确定可留空", "");
      if (impact === null) return null;
      const handling = executionPrompt("请选择处理状态：刚上报、处理中、等待条件、已处理", "刚上报");
      if (handling === null) return null;
      const handlingCode = executionCodeFromChinese(handling || "刚上报", EXECUTION_HANDLING_CODES);
      if (!handlingCode) {
        executionNotice("请选择有效处理状态，例如刚上报、处理中。");
        return null;
      }
      const affectedMachine = executionPrompt("请填写影响设备编号（可留空）", "");
      if (affectedMachine === null) return null;
      const affectedOperator = executionPrompt("请填写影响人员工号（可留空）", "");
      if (affectedOperator === null) return null;
      const suggest = executionPrompt("是否建议重新排程？请输入 是 或 否", "否");
      if (suggest === null) return null;
      const detail = executionPrompt("请填写情况说明", "");
      if (detail === null) return null;
      payload.reason_code = reason;
      payload.severity = severity;
      payload.impact_minutes = impact;
      payload.affected_machine_id = affectedMachine;
      payload.affected_operator_id = affectedOperator;
      payload.handling_status = handlingCode;
      payload.suggest_reschedule = trim(suggest) === "是";
      payload.remark = detail;
    }
    return payload;
  }

  function replaceExecutionTask(taskCard) {
    if (!state.execution) state.execution = { tasks: [] };
    const tasks = Array.isArray(state.execution.tasks) ? state.execution.tasks.slice() : [];
    const opId = String((taskCard && taskCard.op_id) || "");
    let replaced = false;
    for (let i = 0; i < tasks.length; i++) {
      if (String((tasks[i] && tasks[i].op_id) || "") === opId) {
        tasks[i] = taskCard;
        replaced = true;
        break;
      }
    }
    if (!replaced && taskCard) {
      tasks.push(taskCard);
    }
    state.execution.tasks = tasks;
    state.execution.disabled_reason = "";
    renderExecutionCards(state.execution);
  }

  async function postExecutionAction(button) {
    if (!button || button.disabled) return;
    const action = trim(button.getAttribute("data-action"));
    const opId = trim(button.getAttribute("data-op-id"));
    const actionLabels = {
      start: "开工",
      pause: "暂停",
      resume: "继续生产",
      finish: "完工",
      report_exception: "报异常"
    };
    if (!actionLabels[action]) return;
    const actionLabel = actionLabels[action];
    const createdBy = executionCreatedBy();
    if (createdBy === null) return;
    if (window.confirm && !window.confirm("确认提交" + actionLabel + "反馈吗？")) return;
    const payload = executionPayload(button, action, createdBy);
    if (payload === null) return;
    button.disabled = true;
    executionNotice("正在提交" + actionLabel + "反馈，请稍候。");
    try {
      const resp = await fetch("/scheduler/resource-dispatch/execution/" + encodeURIComponent(opId) + "/" + executionActionPath(action), {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify(payload)
      });
      const responsePayload = await resp.json();
      if (!resp.ok || !responsePayload || responsePayload.success !== true) {
        const errorMessage = responsePayload && responsePayload.error && responsePayload.error.message ? responsePayload.error.message : actionLabel + "反馈提交失败，请刷新后重试。";
        throw new Error(errorMessage);
      }
      replaceExecutionTask(responsePayload.data && responsePayload.data.task_card);
      executionNotice(actionLabel + "反馈已提交。");
    } catch (err) {
      button.disabled = false;
      executionNotice(err && err.message ? err.message : actionLabel + "反馈提交失败，请刷新后重试。");
    }
  }

  function bindExecutionActionClicks() {
    const wrap = $("rdExecutionCards");
    if (!wrap) return;
    wrap.addEventListener("click", function (event) {
      const target = event.target && event.target.closest ? event.target.closest(".aps-execution-action") : null;
      if (!target || !wrap.contains(target)) return;
      event.preventDefault();
      postExecutionAction(target);
    });
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
    html.push('<table id="rdCalendarTable" class="table-sticky table-layout-fixed aps-table-xwide" data-col-resize="1" data-table-key="v1_resourceDispatchCalendar"><thead><tr><th class="w-200" data-col-key="scope" data-default-w="200" data-min-w="160">查询对象</th>');
    for (let i = 0; i < headerList.length; i++) {
      const d = trim(headerList[i]);
      html.push('<th class="w-180" data-col-key="day_' + escapeHtml(String(i)) + '" data-default-w="180" data-min-w="150">' + escapeHtml(d) + '</th>');
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
    if (typeof window.APS_InitResizableTables === "function") {
      try {
        window.APS_InitResizableTables(wrap);
      } catch (_err) {}
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
      '<div>对应资源：' + escapeHtml(meta.counterpart_resource_label || "-") + '</div>',
      '<div>班组关系：' + escapeHtml(meta.team_relation_label || "-") + '</div>',
      '<div>现场状态：' + escapeHtml(meta.execution_status_label || "待开工") + '</div>',
      '<div>最近异常：' + escapeHtml(latestExceptionSummary(meta)) + '</div>',
      '<div>影响资源：' + escapeHtml(affectedResourceSummary(meta)) + '</div>',
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
    } catch (_err) {
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
    if (trim(filters.scenario_id)) params.set("scenario_id", trim(filters.scenario_id));
    const textQs = params.toString();
    return textQs ? ("?" + textQs) : "";
  }

  function dataRequestUrl() {
    const url = state.cfg.dataUrl || "";
    if (!url) return "";
    return url.indexOf("?") >= 0 ? url : url + currentQueryString();
  }

  function executionRequestUrl() {
    const url = state.cfg.executionUrl || "";
    if (!url) return "";
    return url.indexOf("?") >= 0 ? url : url + currentQueryString();
  }

  async function loadExecutionData() {
    if (!state.cfg.hasHistory || !state.cfg.canQuery || !state.cfg.executionUrl) {
      renderExecutionCards(null);
      return;
    }
    try {
      const resp = await fetch(executionRequestUrl(), { headers: { Accept: "application/json" } });
      const payload = await resp.json();
      if (!resp.ok || !payload || payload.success !== true) {
        const errorMessage = payload && payload.error && payload.error.message ? payload.error.message : "现场反馈任务卡加载失败，请稍后重试。";
        throw new Error(errorMessage);
      }
      state.execution = payload.data || {};
      renderExecutionCards(state.execution);
    } catch (err) {
      state.execution = null;
      renderExecutionCards({ disabled_reason: err && err.message ? err.message : "现场反馈任务卡加载失败，请稍后重试。", tasks: [] });
    }
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

  bindFieldToggles();
  bindTabs();
  bindExecutionActionClicks();
  loadData();
})();
