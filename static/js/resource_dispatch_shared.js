(function () {
  const ns = window.__APS_RESOURCE_DISPATCH__ = window.__APS_RESOURCE_DISPATCH__ || {};

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
  const state = pageEl ? {
    cfg: {
      filters: parseJson(pageEl.getAttribute("data-filters"), {}),
      dataUrl: trim(pageEl.getAttribute("data-url")),
      executionUrl: trim(pageEl.getAttribute("data-execution-url")),
      actualRecordUrlTemplate: trim(pageEl.getAttribute("data-actual-record-url-template")),
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
  } : null;

  ns.pageEl = pageEl;
  ns.state = state;
  ns.$ = $;
  ns.text = text;
  ns.trim = trim;
  ns.escapeHtml = escapeHtml;
  ns.show = show;
  ns.parseJson = parseJson;
  ns.badge = badge;
  ns.sourceLabel = sourceLabel;
  ns.lockStatusLabel = lockStatusLabel;
  ns.relationBadge = relationBadge;
  ns.codeCell = codeCell;
  ns.fullTextCell = fullTextCell;
  ns.resourceInfo = resourceInfo;
  ns.resourceDisplayHtml = resourceDisplayHtml;
  ns.resourceCell = resourceCell;
  ns.namedResourceInfo = namedResourceInfo;
  ns.resourceInfoHtml = resourceInfoHtml;
  ns.calendarOperationText = calendarOperationText;
  ns.calendarPartText = calendarPartText;
  ns.calendarTaskField = calendarTaskField;
  ns.calendarTaskFieldHtml = calendarTaskFieldHtml;
  ns.calendarTaskHtml = calendarTaskHtml;
  ns.renderFlags = renderFlags;
  ns.latestExceptionSummary = latestExceptionSummary;
  ns.affectedResourceSummary = affectedResourceSummary;
  ns.affectedResourceCell = affectedResourceCell;
  ns.affectedResourcePopupHtml = affectedResourcePopupHtml;
})();
