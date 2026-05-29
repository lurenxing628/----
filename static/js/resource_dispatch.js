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
    } catch (err) {
      if (window.console && typeof window.console.warn === "function") {
        window.console.warn("资源派工 JSON 配置解析失败", err);
      }
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

  function resourceInfo(row, prefix, emptyText) {
    const source = row || {};
    const display = (
      trim(source[prefix + "_display_label"]) ||
      trim(source[prefix + "_name"]) ||
      trim(source[prefix + "_label"]) ||
      trim(source[prefix + "_id"]) ||
      trim(emptyText)
    );
    const identity = (
      trim(source[prefix + "_identity_label"]) ||
      trim(source[prefix + "_label"]) ||
      display
    );
    return {
      display: display,
      identity: identity,
      hasIdentityDetail: !!(identity && display && identity !== display)
    };
  }

  function resourceDisplayHtml(row, prefix, emptyText) {
    const info = resourceInfo(row, prefix, emptyText);
    const title = escapeHtml(info.identity || info.display);
    const detail = info.hasIdentityDetail
      ? '<span class="aps-resource-display-sub">完整身份：' + escapeHtml(info.identity) + '</span>'
      : "";
    return (
      '<span class="aps-resource-display" title="' + title + '">' +
        '<span class="aps-resource-display-main">' + escapeHtml(info.display) + '</span>' +
        detail +
      '</span>'
    );
  }

  function resourceCell(row, prefix, className, emptyText) {
    const info = resourceInfo(row, prefix, emptyText);
    const safeTitle = escapeHtml(info.identity || info.display);
    const cls = className ? ' class="' + escapeHtml(className) + '"' : "";
    return (
      '<td' + cls + ' title="' + safeTitle + '" data-full-text="' + safeTitle + '">' +
        resourceDisplayHtml(row, prefix, emptyText) +
      '</td>'
    );
  }

  function namedResourceInfo(row, idKey, nameKey, emptyText, supplierKey) {
    const source = row || {};
    const resourceId = trim(source[idKey]);
    const resourceName = trim(source[nameKey]);
    const supplierName = supplierKey ? trim(source[supplierKey]) : "";
    if (resourceId || resourceName) {
      const display = resourceName || resourceId;
      const identity = resourceId && resourceName ? resourceId + " " + resourceName : display;
      return {
        display: display,
        identity: identity,
        id: resourceId,
        name: resourceName,
        supplier: supplierName,
        hasIdentityDetail: identity !== display
      };
    }
    if (supplierName) {
      const supplier = "外协供应商：" + supplierName;
      return { display: supplier, identity: supplier, id: "", name: "", supplier: supplierName, hasIdentityDetail: false };
    }
    const empty = trim(emptyText);
    return { display: empty, identity: empty, id: "", name: "", supplier: "", hasIdentityDetail: false };
  }

  function resourceInfoHtml(info) {
    const title = escapeHtml(info.identity || info.display);
    const detail = [];
    if (info.name && info.id) {
      detail.push('<span class="aps-resource-display-sub">编号：' + escapeHtml(info.id) + '</span>');
    }
    if (info.supplier && (info.id || info.name)) {
      detail.push('<span class="aps-resource-display-sub">供应商：' + escapeHtml(info.supplier) + '</span>');
    }
    return (
      '<span class="aps-resource-display" title="' + title + '">' +
        '<span class="aps-resource-display-main">' + escapeHtml(info.display) + '</span>' +
        detail.join("") +
      '</span>'
    );
  }

  function calendarOperationText(item) {
    const opCode = trim(item && item.op_code);
    if (opCode) return opCode;
    const seq = trim(item && item.seq);
    if (seq) return "工序" + seq;
    return "工序未维护";
  }

  function calendarPartText(item) {
    const partNo = trim(item && item.part_no);
    const partName = trim(item && item.part_name);
    return [partNo, partName].filter(Boolean).join(" ") || "未维护";
  }

  function calendarTaskField(label, value) {
    const textValue = trim(value) || "-";
    return (
      '<div class="aps-calendar-task-field">' +
        '<span class="aps-calendar-task-label">' + escapeHtml(label) + '</span>' +
        '<strong class="aps-calendar-task-value">' + escapeHtml(textValue) + '</strong>' +
      '</div>'
    );
  }

  function calendarTaskFieldHtml(label, html) {
    return (
      '<div class="aps-calendar-task-field aps-calendar-task-resource">' +
        '<span class="aps-calendar-task-label">' + escapeHtml(label) + '</span>' +
        '<strong class="aps-calendar-task-value">' + html + '</strong>' +
      '</div>'
    );
  }

  function calendarTaskHtml(item) {
    const task = item || {};
    const overdue = !!task.is_overdue;
    const taskClass = "aps-calendar-task" + (overdue ? " aps-calendar-task--overdue" : "");
    const title = trim(task.text) || [
      trim(task.time_label),
      trim(task.batch_id),
      calendarOperationText(task),
      calendarPartText(task)
    ].filter(Boolean).join(" ");
    const machineInfo = namedResourceInfo(task, "machine_id", "machine_name", "未维护计划设备", "supplier_name");
    const operatorInfo = namedResourceInfo(task, "operator_id", "operator_name", "未维护计划人员", "");
    const timeText = trim(task.time_label) || "时间未维护";
    return (
      '<div class="' + taskClass + '" title="' + escapeHtml(title) + '">' +
        '<div class="aps-calendar-task-time">' +
          '<span>' + escapeHtml(timeText) + '</span>' +
          (overdue ? badge("超期", "error") : "") +
        '</div>' +
        '<div class="aps-calendar-task-grid">' +
          calendarTaskField("批次", task.batch_id) +
          calendarTaskField("工序", calendarOperationText(task)) +
          calendarTaskFieldHtml("计划设备", resourceInfoHtml(machineInfo)) +
          calendarTaskFieldHtml("计划人员", resourceInfoHtml(operatorInfo)) +
          calendarTaskField("图号 / 物料", calendarPartText(task)) +
        '</div>' +
      '</div>'
    );
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
    const machine = resourceInfo(row, "latest_exception_affected_machine", "未填写影响设备").display;
    const operator = resourceInfo(row, "latest_exception_affected_operator", "未填写影响人员").display;
    return machine + "；" + operator;
  }

  function affectedResourceCell(row) {
    const reason = trim(row && row.latest_exception_reason_label);
    if (!reason || reason === "暂无异常") return fullTextCell("暂无异常", "aps-resource-cell");
    const machine = resourceInfo(row, "latest_exception_affected_machine", "未填写影响设备");
    const operator = resourceInfo(row, "latest_exception_affected_operator", "未填写影响人员");
    const display = machine.display + "；" + operator.display;
    const identities = [];
    if (machine.identity && machine.identity !== machine.display) identities.push(machine.identity);
    if (operator.identity && operator.identity !== operator.display) identities.push(operator.identity);
    const title = identities.length ? identities.join("；") : display;
    return (
      '<td class="aps-resource-cell" title="' + escapeHtml(title) + '" data-full-text="' + escapeHtml(title) + '">' +
        '<span class="aps-resource-display">' +
          '<span class="aps-resource-display-main">' + escapeHtml(display) + '</span>' +
          (identities.length ? '<span class="aps-resource-display-sub">完整身份：' + escapeHtml(identities.join("；")) + '</span>' : "") +
        '</span>' +
      '</td>'
    );
  }

  function affectedResourcePopupHtml(row) {
    const reason = trim(row && row.latest_exception_reason_label);
    if (!reason || reason === "暂无异常") return '<div>影响资源：暂无异常</div>';
    return (
      '<div>影响设备：' + resourceDisplayHtml(row, "latest_exception_affected_machine", "未填写影响设备") + '</div>' +
      '<div>影响人员：' + resourceDisplayHtml(row, "latest_exception_affected_operator", "未填写影响人员") + '</div>'
    );
  }

  const pageEl = $("rdPage");
  if (!pageEl) return;

  const state = {
    cfg: {
      filters: parseJson(pageEl.getAttribute("data-filters"), {}),
      dataUrl: trim(pageEl.getAttribute("data-url")),
      executionUrl: trim(pageEl.getAttribute("data-execution-url")),
      actualTemplateUrl: trim(pageEl.getAttribute("data-actual-template-url")),
      actualImportUrl: trim(pageEl.getAttribute("data-actual-import-url")),
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

  function renderExecutionActions(actions, task) {
    const row = task || {};
    const opId = trim(row.op_id);
    const fillAction = Array.isArray(actions)
      ? actions.find(function (item) { return trim(item && item.action) === "fill_actual"; })
      : null;
    const disabledReason = trim(fillAction && fillAction.disabled_reason);
    const disabledAttr = fillAction && fillAction.enabled ? "" : " disabled";
    const titleAttr = disabledReason ? ' title="' + escapeHtml(disabledReason) + '"' : "";
    const recordsDisabledAttr = opId ? "" : " disabled";
    const recordsTitleAttr = opId ? "" : ' title="缺少任务识别码，无法查看计划和实际"';
    return (
      '<button type="button" class="btn btn-primary btn-sm aps-execution-action" data-action="fill_actual" data-op-id="' +
        escapeHtml(row.op_id || "") + '" data-schedule-id="' + escapeHtml(row.schedule_id || "") +
        '" data-batch-id="' + escapeHtml(row.batch_id || "") +
        '" data-state-revision="' + escapeHtml(row.state_revision || "") +
        '" data-machine-id="' + escapeHtml(row.planned_machine_id || "") +
        '" data-operator-id="' + escapeHtml(row.planned_operator_id || "") + '"' + disabledAttr + titleAttr + '>填写实际情况</button> ' +
      '<button type="button" class="btn btn-secondary btn-sm aps-execution-events" data-op-id="' +
        escapeHtml(row.op_id || "") + '" data-loaded="0"' + recordsDisabledAttr + recordsTitleAttr + '>查看计划和实际</button>'
    );
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
  const EXECUTION_ACTION_LABELS = {
    fill_actual: "填写实际情况"
  };

  function renderExecutionExceptionDetails(task) {
    if (!trim(task && task.latest_exception_reason_label)) return "";
    const impact = trim(task.latest_exception_impact_minutes_label) || "暂时不知道影响多久";
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
        '<div><span>影响设备</span><strong>' + resourceDisplayHtml(task, "latest_exception_affected_machine", "未填写影响设备") + '</strong></div>' +
        '<div><span>影响人员</span><strong>' + resourceDisplayHtml(task, "latest_exception_affected_operator", "未填写影响人员") + '</strong></div>' +
        '<div><span>处理状态</span><strong>' + escapeHtml(handling) + '</strong></div>' +
        '<div><span>是否建议重排</span><strong>' + escapeHtml(suggest) + '</strong></div>' +
        '<div><span>情况说明</span><strong>' + escapeHtml(remark) + '</strong></div>' +
      '</div>'
    );
  }

  function executionReasonText(value) {
    return trim(value).replace(/[。；;,.，、\s]+$/g, "");
  }

  function normalizedUnavailableReasonTexts(reasons) {
    const seen = {};
    const lines = [];
    function addReason(value) {
      const item = executionReasonText(value);
      if (item && !seen[item]) {
        seen[item] = true;
        lines.push(item);
      }
    }
    if (Array.isArray(reasons)) {
      reasons.forEach(addReason);
      return lines;
    }
    if (!reasons || typeof reasons !== "object") return lines;
    if (Object.prototype.hasOwnProperty.call(reasons, "fill_actual")) {
      addReason(reasons.fill_actual);
    }
    return lines;
  }

  function statusUnavailableReasonSummary(lines) {
    if (!Array.isArray(lines) || !lines.length) return "";
    let status = "";
    const actions = [];
    for (let i = 0; i < lines.length; i++) {
      const match = /^当前状态是(.+)，不能(.+)$/.exec(lines[i]);
      if (!match) return "";
      if (!status) status = match[1];
      if (status !== match[1]) return "";
      actions.push(match[2]);
    }
    return status && actions.length ? ("当前状态是" + status + "，不能" + actions.join("、") + "。") : "";
  }

  function executionUnavailableReasonText(reasons) {
    const lines = normalizedUnavailableReasonTexts(reasons);
    if (!lines.length) return "";
    const summary = statusUnavailableReasonSummary(lines) || (lines.join("；") + "。");
    return escapeHtml(summary);
  }

  function renderExecutionCards(payload) {
    const wrap = $("rdExecutionCards");
    const notice = $("rdExecutionNotice");
    if (!wrap) return;
    const data = payload || {};
    const tasks = Array.isArray(data.tasks) ? data.tasks : [];
    const disabledReason = trim(data.disabled_reason);
    if (notice) {
      if (disabledReason) {
        notice.textContent = disabledReason;
      }
      show(notice, !!disabledReason);
    }
    if (!tasks.length) {
      wrap.innerHTML = '<div class="muted">当前查询范围内暂无现场记录任务卡。</div>';
      return;
    }
    const cards = [];
    for (let i = 0; i < tasks.length; i++) {
      const task = tasks[i] || {};
      const reasonText = executionUnavailableReasonText(task.unavailable_reasons);
      cards.push(
        '<section class="aps-execution-card" data-actual-start-time="' + escapeHtml(task.actual_start_time || "") +
          '" data-actual-end-time="' + escapeHtml(task.actual_end_time || "") + '">' +
          '<div class="aps-execution-card-head">' +
            '<div>' +
              '<div class="aps-execution-title">' + escapeHtml(task.op_name || "未命名工序") + '</div>' +
              '<div class="text-meta">批次：' + escapeHtml(task.batch_id || "-") + '</div>' +
            '</div>' +
            '<span class="badge badge-skip">' + escapeHtml(task.current_status_label || "待开工") + '</span>' +
          '</div>' +
          '<div class="aps-execution-facts">' +
            '<div><span>计划开始</span><strong>' + escapeHtml(task.planned_start_time || "-") + '</strong></div>' +
            '<div><span>实际开工</span><strong>' + escapeHtml(task.actual_start_time || "暂无开工记录") + '</strong></div>' +
            '<div><span>计划结束</span><strong>' + escapeHtml(task.planned_end_time || "-") + '</strong></div>' +
            '<div><span>实际完工</span><strong>' + escapeHtml(task.actual_end_time || "未填写实际完工") + '</strong></div>' +
            '<div><span>计划设备</span><strong>' + resourceDisplayHtml(task, "planned_machine", "-") + '</strong></div>' +
            '<div><span>实际设备</span><strong>' + resourceDisplayHtml(task, "actual_machine", "暂无") + '</strong></div>' +
            '<div><span>计划人员</span><strong>' + resourceDisplayHtml(task, "planned_operator", "-") + '</strong></div>' +
            '<div><span>实际人员</span><strong>' + resourceDisplayHtml(task, "actual_operator", "暂无") + '</strong></div>' +
          '</div>' +
          (task.actual_start_time ? '<div class="text-meta mt-1">已记录实际开工。</div>' : '') +
          (task.last_event_action_label ? '<div class="text-meta mt-1">最近记录：' + escapeHtml(task.last_event_action_label) + (task.last_event_remark ? '，' + escapeHtml(task.last_event_remark) : '') + '</div>' : '') +
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
    return input ? trim(input.value) : "";
  }

  function actionDataAttributes(source) {
    return [
      "data-action",
      "data-op-id",
      "data-schedule-id",
      "data-batch-id",
      "data-state-revision",
      "data-machine-id",
      "data-operator-id"
    ].map(function (name) {
      return name + '="' + escapeHtml(source.getAttribute(name) || "") + '"';
    }).join(" ");
  }

  function dateTimeTextFromInput(value) {
    const raw = trim(value);
    if (!raw) return "";
    return raw.replace("T", " ") + (raw.length === 16 ? ":00" : "");
  }

  function clearExecutionInlineForms(card) {
    const scope = card || document;
    scope.querySelectorAll(".aps-execution-inline-form").forEach(function (el) {
      if (el.parentNode) el.parentNode.removeChild(el);
    });
  }

  function clearExecutionRecords(card) {
    const scope = card || document;
    scope.querySelectorAll(".aps-execution-records").forEach(function (el) {
      if (el.parentNode) el.parentNode.removeChild(el);
    });
  }

  function renderActualInlineForm(button) {
    const card = button && button.closest ? button.closest(".aps-execution-card") : null;
    if (!card) return;
    clearExecutionInlineForms(card);
    const actions = button.closest(".aps-execution-actions");
    const recordedStart = trim(card.getAttribute("data-actual-start-time") || "");
    const recordedEnd = trim(card.getAttribute("data-actual-end-time") || "");
    // 已记录的实际开工/完工只读展示，不渲染成可编辑输入、也不进入提交内容——后端只追加、不覆盖，
    // 预填可编辑值会让“补完工/加暂停”被整单拒绝。仅未记录时才给出可填写的输入框。
    const startField = recordedStart
      ? '<div class="aps-execution-inline-readonly">实际开工时间<strong>' + escapeHtml(recordedStart) + '</strong><span class="text-meta">已记录，不可修改</span></div>'
      : '<label>实际开工时间<input type="datetime-local" class="aps-actual-start-time"></label>';
    const finishField = recordedEnd
      ? '<div class="aps-execution-inline-readonly">实际完工时间<strong>' + escapeHtml(recordedEnd) + '</strong><span class="text-meta">已记录，不可修改</span></div>'
      : '<label>实际完工时间<input type="datetime-local" class="aps-actual-finish-time"></label>';
    const finishQtyFields = recordedEnd
      ? ''
      : '<label>完成数量<input type="number" min="0" step="1" class="aps-actual-finish-qty" inputmode="numeric"></label>' +
        '<label>报废数量<input type="number" min="0" step="1" class="aps-actual-scrap-qty" inputmode="numeric"></label>';
    const form = document.createElement("div");
    form.className = "aps-execution-inline-form mt-2";
    form.setAttribute("role", "group");
    form.setAttribute("aria-label", "填写实际情况");
    form.innerHTML =
      '<div class="aps-execution-inline-title">填写实际情况</div>' +
      '<div class="aps-execution-inline-grid">' +
        startField +
        finishField +
        finishQtyFields +
        '<label>暂停开始时间<input type="datetime-local" class="aps-actual-pause-start"></label>' +
        '<label>暂停结束时间<input type="datetime-local" class="aps-actual-pause-end"></label>' +
        '<label>暂停时长分钟<input type="number" min="0" step="1" class="aps-actual-pause-duration" inputmode="numeric"></label>' +
        '<label>暂停原因<select class="aps-actual-pause-reason">' +
          executionOptionsHtml(EXECUTION_REASON_CODES, "请选择原因", "") +
        '</select></label>' +
        '<label class="aps-execution-inline-field-wide">暂停说明<textarea class="aps-actual-pause-remark" rows="2" placeholder="例如：设备需要检查"></textarea></label>' +
        '<div class="aps-execution-inline-title aps-execution-inline-field-wide">新增异常记录</div>' +
        '<label>异常时间<input type="datetime-local" class="aps-actual-exception-time"></label>' +
        '<label>异常原因<select class="aps-actual-exception-reason">' +
          executionOptionsHtml(EXECUTION_REASON_CODES, "请选择原因", "") +
        '</select></label>' +
        '<label>异常严重程度<select class="aps-actual-exception-severity">' +
          executionOptionsHtml(EXECUTION_SEVERITY_CODES, "请选择严重程度", "") +
        '</select></label>' +
        '<label class="aps-execution-inline-field-wide">异常说明<textarea class="aps-actual-exception-remark" rows="2" placeholder="例如：主轴异常，已通知维修"></textarea></label>' +
        '<label class="aps-execution-inline-field-wide">备注<textarea class="aps-actual-remark" rows="2" placeholder="可填写班次、补充说明等"></textarea></label>' +
      '</div>' +
      '<div class="aps-inline-form-actions mt-2">' +
        '<button type="button" class="btn btn-primary btn-sm aps-execution-inline-submit" ' + actionDataAttributes(button) + '>保存实际情况</button>' +
        '<button type="button" class="btn btn-secondary btn-sm aps-execution-inline-cancel">取消</button>' +
      '</div>';
    if (actions && actions.parentNode) {
      actions.parentNode.insertBefore(form, actions.nextSibling);
    } else {
      card.appendChild(form);
    }
    const first = form.querySelector("input, select, textarea");
    if (first && first.focus) first.focus();
  }

  function executionOptionsHtml(mapping, blankLabel, selectedValue) {
    const html = [];
    if (blankLabel) {
      html.push('<option value="">' + escapeHtml(blankLabel) + '</option>');
    }
    Object.keys(mapping).forEach(function (label) {
      const value = mapping[label];
      const selected = selectedValue === value ? " selected" : "";
      html.push('<option value="' + escapeHtml(value) + '"' + selected + '>' + escapeHtml(label) + '</option>');
    });
    return html.join("");
  }

  function inlineActionPayload(button, action) {
    if (action === "fill_actual") return inlineActualPayload(button);
    return {};
  }

  function inlineActualPayload(button) {
    const form = button && button.closest ? button.closest(".aps-execution-inline-form") : null;
    if (!form) return null;
    const payload = {
      actual_start_time: dateTimeTextFromInput(form.querySelector(".aps-actual-start-time") && form.querySelector(".aps-actual-start-time").value),
      actual_finish_time: dateTimeTextFromInput(form.querySelector(".aps-actual-finish-time") && form.querySelector(".aps-actual-finish-time").value),
      quantity_done: trim(form.querySelector(".aps-actual-finish-qty") && form.querySelector(".aps-actual-finish-qty").value),
      quantity_scrapped: trim(form.querySelector(".aps-actual-scrap-qty") && form.querySelector(".aps-actual-scrap-qty").value),
      pause_start_time: dateTimeTextFromInput(form.querySelector(".aps-actual-pause-start") && form.querySelector(".aps-actual-pause-start").value),
      pause_end_time: dateTimeTextFromInput(form.querySelector(".aps-actual-pause-end") && form.querySelector(".aps-actual-pause-end").value),
      pause_duration_minutes: trim(form.querySelector(".aps-actual-pause-duration") && form.querySelector(".aps-actual-pause-duration").value),
      pause_reason: trim(form.querySelector(".aps-actual-pause-reason") && form.querySelector(".aps-actual-pause-reason").value),
      pause_remark: trim(form.querySelector(".aps-actual-pause-remark") && form.querySelector(".aps-actual-pause-remark").value),
      exception_time: dateTimeTextFromInput(form.querySelector(".aps-actual-exception-time") && form.querySelector(".aps-actual-exception-time").value),
      exception_reason: trim(form.querySelector(".aps-actual-exception-reason") && form.querySelector(".aps-actual-exception-reason").value),
      exception_severity: trim(form.querySelector(".aps-actual-exception-severity") && form.querySelector(".aps-actual-exception-severity").value),
      exception_remark: trim(form.querySelector(".aps-actual-exception-remark") && form.querySelector(".aps-actual-exception-remark").value),
      remark: trim(form.querySelector(".aps-actual-remark") && form.querySelector(".aps-actual-remark").value)
    };
    const hasAny = Object.keys(payload).some(function (key) { return trim(payload[key]); });
    if (!hasAny) {
      executionNotice("请至少填写一项实际情况。");
      return null;
    }
    if (payload.actual_finish_time && !payload.quantity_done) {
      executionNotice("填写实际完工时，请填写完成数量。");
      const qty = form.querySelector(".aps-actual-finish-qty");
      if (qty && qty.focus) qty.focus();
      return null;
    }
    const hasPause = payload.pause_start_time || payload.pause_end_time || payload.pause_duration_minutes || payload.pause_reason || payload.pause_remark;
    if (hasPause && (!payload.pause_start_time || (!payload.pause_end_time && !payload.pause_duration_minutes) || !payload.pause_reason || !payload.pause_remark)) {
      executionNotice("新增暂停时间时，请填写暂停开始、暂停结束或时长、暂停原因和暂停说明。");
      return null;
    }
    const hasException = payload.exception_time || payload.exception_reason || payload.exception_severity || payload.exception_remark;
    if (hasException && (!payload.exception_time || !payload.exception_reason || !payload.exception_severity || !payload.exception_remark)) {
      executionNotice("新增异常记录时，请填写异常时间、异常原因、严重程度和异常说明。");
      return null;
    }
    return payload;
  }

  function executionPayload(button, action, createdBy, extraPayload) {
    const payload = executionIdentityPayload();
    const extra = extraPayload || {};
    payload.schedule_id = button.getAttribute("data-schedule-id") || "";
    payload.batch_id = button.getAttribute("data-batch-id") || "";
    payload.expected_state_revision = button.getAttribute("data-state-revision") || "";
    payload.created_by = createdBy;
    payload.feedback_person = createdBy;
    payload.idempotency_key = [
      "resource-dispatch",
      "actual",
      button.getAttribute("data-op-id") || "",
      String(Date.now())
    ].join("-");
    payload.remark = "";
    payload.actual_start_time = trim(extra.actual_start_time);
    payload.actual_finish_time = trim(extra.actual_finish_time);
    payload.quantity_done = trim(extra.quantity_done);
    payload.quantity_scrapped = trim(extra.quantity_scrapped);
    payload.pause_start_time = trim(extra.pause_start_time);
    payload.pause_end_time = trim(extra.pause_end_time);
    payload.pause_duration_minutes = trim(extra.pause_duration_minutes);
    payload.pause_reason = trim(extra.pause_reason);
    payload.pause_remark = trim(extra.pause_remark);
    payload.exception_time = trim(extra.exception_time);
    payload.exception_reason = trim(extra.exception_reason);
    payload.exception_severity = trim(extra.exception_severity);
    payload.exception_remark = trim(extra.exception_remark);
    payload.remark = trim(extra.remark);
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
    if (!EXECUTION_ACTION_LABELS[action]) return;
    const actionLabel = EXECUTION_ACTION_LABELS[action];
    const createdBy = executionCreatedBy();
    const extraPayload = inlineActionPayload(button, action);
    if (extraPayload === null) return;
    const payload = executionPayload(button, action, createdBy, extraPayload || {});
    if (payload === null) return;
    button.disabled = true;
    executionNotice("正在保存" + actionLabel + "，请稍候。");
    try {
      const resp = await fetch("/scheduler/resource-dispatch/execution/" + encodeURIComponent(opId) + "/actual", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify(payload)
      });
      const responsePayload = await resp.json();
      if (!resp.ok || !responsePayload || responsePayload.success !== true) {
        const errorMessage = responsePayload && responsePayload.error && responsePayload.error.message ? responsePayload.error.message : actionLabel + "保存失败，请刷新后重试。";
        throw new Error(errorMessage);
      }
      replaceExecutionTask(responsePayload.data && responsePayload.data.task_card);
      clearExecutionInlineForms();
      executionNotice(actionLabel + "已保存。");
    } catch (err) {
      button.disabled = false;
      executionNotice(err && err.message ? err.message : actionLabel + "保存失败，请刷新后重试。");
    }
  }

  function executionEventsUrl(opId) {
    const base = "/scheduler/resource-dispatch/execution/" + encodeURIComponent(opId) + "/events";
    return base + currentQueryString();
  }

  function renderExecutionRecords(button, data) {
    const card = button && button.closest ? button.closest(".aps-execution-card") : null;
    if (!card) return;
    clearExecutionRecords(card);
    const events = data && Array.isArray(data.events) ? data.events : [];
    const rows = [];
    if (!events.length) {
      rows.push('<div class="muted">暂无现场记录。</div>');
    } else {
      events.forEach(function (item) {
        rows.push(
          '<div class="aps-execution-record-item">' +
            '<div class="aps-execution-record-head">' +
              '<strong>' + escapeHtml(item.action_label || "现场记录") + '</strong>' +
              '<span>' + escapeHtml(item.event_time || "-") + '</span>' +
            '</div>' +
            '<div class="aps-execution-record-grid">' +
              '<div><span>反馈人</span><strong>' + escapeHtml(item.created_by || "未填写反馈人") + '</strong></div>' +
              '<div><span>原因</span><strong>' + escapeHtml(item.reason_label || "-") + '</strong></div>' +
              '<div class="aps-execution-record-wide"><span>说明</span><strong>' + escapeHtml(item.remark || "-") + '</strong></div>' +
            '</div>' +
          '</div>'
        );
      });
    }
    const panel = document.createElement("div");
    panel.className = "aps-execution-inline-form aps-execution-records mt-2";
    panel.innerHTML =
      '<div class="aps-execution-inline-title">查看计划和实际</div>' +
      rows.join("");
    const actions = button.closest(".aps-execution-actions");
    if (actions && actions.parentNode) {
      actions.parentNode.insertBefore(panel, actions.nextSibling);
    } else {
      card.appendChild(panel);
    }
    button.setAttribute("data-loaded", "1");
  }

  async function loadExecutionRecords(button) {
    if (!button || button.disabled) return;
    const card = button.closest ? button.closest(".aps-execution-card") : null;
    if (button.getAttribute("data-loaded") === "1") {
      clearExecutionRecords(card);
      button.setAttribute("data-loaded", "0");
      return;
    }
    const opId = trim(button.getAttribute("data-op-id"));
    if (!opId) {
      executionNotice("缺少任务识别码，无法查看计划和实际。");
      return;
    }
    button.disabled = true;
    executionNotice("正在加载计划和实际，请稍候。");
    try {
      const resp = await fetch(executionEventsUrl(opId), { headers: { Accept: "application/json" } });
      const payload = await resp.json();
      if (!resp.ok || !payload || payload.success !== true) {
        const message = payload && payload.error && payload.error.message ? payload.error.message : "计划和实际加载失败，请稍后重试。";
        throw new Error(message);
      }
      renderExecutionRecords(button, payload.data || {});
      executionNotice("");
    } catch (err) {
      executionNotice(err && err.message ? err.message : "计划和实际加载失败，请稍后重试。");
    } finally {
      button.disabled = false;
    }
  }

  function bindExecutionActionClicks() {
    const wrap = $("rdExecutionCards");
    if (!wrap) return;
    wrap.addEventListener("click", function (event) {
      const cancelTarget = event.target && event.target.closest ? event.target.closest(".aps-execution-inline-cancel") : null;
      if (cancelTarget && wrap.contains(cancelTarget)) {
        event.preventDefault();
        clearExecutionInlineForms(cancelTarget.closest(".aps-execution-card"));
        return;
      }
      const submitTarget = event.target && event.target.closest ? event.target.closest(".aps-execution-inline-submit") : null;
      if (submitTarget && wrap.contains(submitTarget)) {
        event.preventDefault();
        postExecutionAction(submitTarget);
        return;
      }
      const eventsTarget = event.target && event.target.closest ? event.target.closest(".aps-execution-events") : null;
      if (eventsTarget && wrap.contains(eventsTarget)) {
        event.preventDefault();
        loadExecutionRecords(eventsTarget);
        return;
      }
      const target = event.target && event.target.closest ? event.target.closest(".aps-execution-action") : null;
      if (!target || !wrap.contains(target)) return;
      event.preventDefault();
      const action = trim(target.getAttribute("data-action"));
      if (action === "fill_actual") {
        renderActualInlineForm(target);
        return;
      }
    });
  }

  function actualImportUrl() {
    const url = state.cfg.actualImportUrl || "";
    if (!url) return "";
    return url.indexOf("?") >= 0 ? url : url + currentQueryString();
  }

  function renderActualImportResult(data) {
    const wrap = $("rdActualImportPreviewWrap");
    if (!wrap) return;
    const payload = data || {};
    const summary = payload.summary || {};
    const rows = Array.isArray(payload.rows) ? payload.rows : [];
    if (!rows.length) {
      wrap.innerHTML = "";
      show(wrap, false);
      return;
    }
    const lines = [];
    lines.push(
      '<div class="aps-execution-inline-form">' +
        '<div class="aps-execution-inline-title">导入结果</div>' +
        '<div class="aps-execution-facts">' +
          '<div><span>匹配成功</span><strong>' + escapeHtml(summary.matched_rows || 0) + '</strong></div>' +
          '<div><span>可导入</span><strong>' + escapeHtml(summary.add_count || 0) + '</strong></div>' +
          '<div><span>空白行</span><strong>' + escapeHtml(summary.skip_count || 0) + '</strong></div>' +
          '<div><span>冲突</span><strong>' + escapeHtml(summary.conflict_count || 0) + '</strong></div>' +
          '<div><span>错误</span><strong>' + escapeHtml(summary.error_count || 0) + '</strong></div>' +
        '</div>' +
        '<div class="aps-table-scroll mt-2">' +
          '<table class="table-sticky table-layout-fixed aps-table-xwide">' +
            '<thead><tr><th>Sheet</th><th>行号</th><th>任务识别码</th><th>结果</th><th>说明</th><th>可导入</th><th>空白行</th></tr></thead><tbody>'
    );
    rows.forEach(function (row) {
      const status = trim(row.status);
      const variant = status === "ok" ? "new" : (status === "skip" ? "skip" : "error");
      lines.push(
        '<tr>' +
          '<td>' + escapeHtml(row.sheet || "") + '</td>' +
          '<td>' + escapeHtml(row.row_number || "") + '</td>' +
          '<td>' + escapeHtml(row.task_code || "") + '</td>' +
          '<td>' + badge(row.status_label || "待处理", variant) + '</td>' +
          fullTextCell(row.message || "", "aps-resource-cell") +
          '<td>' + escapeHtml(row.add_count || 0) + '</td>' +
          '<td>' + escapeHtml(row.skip_count || 0) + '</td>' +
        '</tr>'
      );
    });
    lines.push('</tbody></table></div></div>');
    wrap.innerHTML = lines.join("");
    show(wrap, true);
  }

  async function submitActualImport() {
    const fileInput = $("rdActualImportFile");
    const file = fileInput && fileInput.files && fileInput.files[0];
    if (!state.cfg.actualImportUrl) {
      executionNotice("当前查询没有可导入的实际情况。");
      return;
    }
    if (!file) {
      executionNotice("请先选择要导入的 Excel 文件。");
      return;
    }
    const btn = $("rdActualImportSubmit");
    const form = new FormData();
    form.append("file", file);
    if (btn) btn.disabled = true;
    renderActualImportResult(null);
    executionNotice("正在导入实际情况，请稍候。");
    try {
      const resp = await fetch(actualImportUrl(), {
        method: "POST",
        headers: { Accept: "application/json" },
        body: form
      });
      const payload = await resp.json();
      if (!resp.ok || !payload || payload.success !== true) {
        const details = payload && payload.error && payload.error.details ? payload.error.details : {};
        if (details && Array.isArray(details.rows)) {
          renderActualImportResult({ rows: details.rows, summary: details.summary || {} });
        }
        const message = payload && payload.error && payload.error.message ? payload.error.message : "导入实际情况失败，请修改 Excel 后重试。";
        throw new Error(message);
      }
      executionNotice((payload.data && payload.data.message) || "导入实际情况已完成。");
      if (fileInput) fileInput.value = "";
      loadExecutionData();
      loadData();
    } catch (err) {
      executionNotice(err && err.message ? err.message : "导入实际情况失败，请修改 Excel 后重试。");
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  function bindActualImportButtons() {
    const submitBtn = $("rdActualImportSubmit");
    const fileInput = $("rdActualImportFile");
    if (submitBtn) submitBtn.addEventListener("click", submitActualImport);
    if (fileInput) {
      fileInput.addEventListener("change", function () {
        renderActualImportResult(null);
        executionNotice("");
      });
    }
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
        const errorMessage = payload && payload.error && payload.error.message ? payload.error.message : "现场记录任务卡加载失败，请稍后重试。";
        throw new Error(errorMessage);
      }
      state.execution = payload.data || {};
      renderExecutionCards(state.execution);
    } catch (err) {
      state.execution = null;
      renderExecutionCards({ disabled_reason: err && err.message ? err.message : "现场记录任务卡加载失败，请稍后重试。", tasks: [] });
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
  bindActualImportButtons();
  loadData();
})();
