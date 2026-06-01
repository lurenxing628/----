(function () {
  const ns = window.__APS_RESOURCE_DISPATCH__;
  ns.execution = ns.execution || {};
  const $ = ns.$;
  const trim = ns.trim;
  const escapeHtml = ns.escapeHtml;
  const show = ns.show;
  const resourceDisplayHtml = ns.resourceDisplayHtml;

  function currentQueryString() {
    return ns.core.currentQueryString();
  }

  function executionAction(actions, actionName) {
    if (!Array.isArray(actions)) return null;
    return actions.find(function (item) {
      return trim(item && item.action) === actionName;
    }) || null;
  }

  function renderExecutionActions(actions, task) {
    const row = task || {};
    const opId = trim(row.op_id);
    const fillAction = executionAction(actions, "fill_actual");
    const viewAction = executionAction(actions, "view_records");
    let fillButton = "";
    if (fillAction) {
      const fillDisabledReason = trim(fillAction.disabled_reason);
      const fillDisabledAttr = fillAction.enabled === true ? "" : " disabled";
      const fillTitleAttr = fillDisabledReason ? ' title="' + escapeHtml(fillDisabledReason) + '"' : "";
      const fillLabel = trim(fillAction.label) || "填写实际情况";
      fillButton = (
        '<button type="button" class="btn btn-primary btn-sm aps-execution-action" data-action="fill_actual" data-op-id="' +
          escapeHtml(row.op_id || "") + '" data-schedule-id="' + escapeHtml(row.schedule_id || "") +
          '" data-batch-id="' + escapeHtml(row.batch_id || "") +
          '" data-state-revision="' + escapeHtml(row.state_revision || "") +
          '" data-machine-id="' + escapeHtml(row.planned_machine_id || "") +
          '" data-operator-id="' + escapeHtml(row.planned_operator_id || "") + '"' + fillDisabledAttr + fillTitleAttr + '>' + escapeHtml(fillLabel) + '</button> '
      );
    }
    let recordsDisabledReason = trim(viewAction && viewAction.disabled_reason);
    let recordsDisabledAttr = viewAction && viewAction.enabled === true ? "" : " disabled";
    if (!viewAction) {
      recordsDisabledReason = "当前任务暂不能查看现场记录。";
    }
    if (!opId && !recordsDisabledReason) {
      recordsDisabledReason = "缺少任务识别码，无法查看现场记录";
      recordsDisabledAttr = " disabled";
    }
    const recordsTitleAttr = recordsDisabledReason ? ' title="' + escapeHtml(recordsDisabledReason) + '"' : "";
    const recordsLabel = trim(viewAction && viewAction.label) || "查看现场记录";
    return (
      fillButton +
      '<button type="button" class="btn btn-secondary btn-sm aps-execution-events" data-op-id="' +
        escapeHtml(row.op_id || "") + '" data-loaded="0"' + recordsDisabledAttr + recordsTitleAttr + '>' + escapeHtml(recordsLabel) + '</button>'
    );
  }

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
      if (disabledReason) notice.textContent = disabledReason;
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
              '<div class="text-meta">图号 / 物料：' + escapeHtml(task.part_label || "未填写图号或物料") + '</div>' +
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
            '<div><span>开工偏差</span><strong>' + escapeHtml(task.actual_start_delta_label || "暂未记录现场实际") + '</strong></div>' +
            '<div><span>完工偏差</span><strong>' + escapeHtml(task.actual_end_delta_label || "暂未记录现场实际") + '</strong></div>' +
          '</div>' +
          '<div class="text-meta mt-1">计划和实际：' + escapeHtml(task.actual_delta_summary || "暂未记录现场实际") + '</div>' +
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

  function clearExecutionRecords(card) {
    const scope = card || document;
    scope.querySelectorAll(".aps-execution-records").forEach(function (el) {
      if (el.parentNode) el.parentNode.removeChild(el);
    });
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
              '<span>发生时间：' + escapeHtml(item.event_time || "-") + '</span>' +
            '</div>' +
            '<div class="aps-execution-record-grid">' +
              '<div><span>记录来源</span><strong>' + escapeHtml(item.record_source_label || "现场记录") + '</strong></div>' +
              '<div><span>记录时间</span><strong>' + escapeHtml(item.record_time_label || "暂未记录落库时间") + '</strong></div>' +
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
    panel.innerHTML = '<div class="aps-execution-inline-title">查看现场记录</div>' + rows.join("");
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
      ns.execution.executionNotice("缺少任务识别码，无法查看现场记录。");
      return;
    }
    button.disabled = true;
    ns.execution.executionNotice("正在加载现场记录，请稍候。");
    try {
      const resp = await fetch(executionEventsUrl(opId), { headers: { Accept: "application/json" } });
      const payload = await resp.json();
      if (!resp.ok || !payload || payload.success !== true) {
        const message = payload && payload.error && payload.error.message ? payload.error.message : "现场记录加载失败，请稍后重试。";
        throw new Error(message);
      }
      renderExecutionRecords(button, payload.data || {});
      ns.execution.executionNotice("");
    } catch (err) {
      ns.execution.executionNotice(err && err.message ? err.message : "现场记录加载失败，请稍后重试。");
    } finally {
      button.disabled = false;
    }
  }

  Object.assign(ns.execution, {
    loadExecutionRecords: loadExecutionRecords,
    renderExecutionCards: renderExecutionCards
  });
})();
