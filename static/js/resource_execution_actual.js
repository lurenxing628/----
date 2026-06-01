(function () {
  const ns = window.__APS_RESOURCE_DISPATCH__;
  ns.execution = ns.execution || {};
  const state = ns.state;
  const trim = ns.trim;
  const escapeHtml = ns.escapeHtml;

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

  function loadData() {
    return ns.core.loadData();
  }

  function executionNotice(message) {
    return ns.execution.executionNotice(message);
  }

  function clearExecutionInlineForms(card) {
    const scope = card || document;
    scope.querySelectorAll(".aps-execution-inline-form").forEach(function (el) {
      if (el.parentNode) el.parentNode.removeChild(el);
    });
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

  function renderActualInlineForm(button) {
    const card = button && button.closest ? button.closest(".aps-execution-card") : null;
    if (!card) return;
    clearExecutionInlineForms(card);
    const actions = button.closest(".aps-execution-actions");
    const recordedStart = trim(card.getAttribute("data-actual-start-time") || "");
    const recordedEnd = trim(card.getAttribute("data-actual-end-time") || "");
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
        startField + finishField + finishQtyFields +
        '<label>暂停开始时间<input type="datetime-local" class="aps-actual-pause-start"></label>' +
        '<label>暂停结束时间<input type="datetime-local" class="aps-actual-pause-end"></label>' +
        '<label>暂停时长分钟<input type="number" min="0" step="1" class="aps-actual-pause-duration" inputmode="numeric"></label>' +
        '<label>暂停原因<select class="aps-actual-pause-reason">' + executionOptionsHtml(EXECUTION_REASON_CODES, "请选择原因", "") + '</select></label>' +
        '<label class="aps-execution-inline-field-wide">暂停说明<textarea class="aps-actual-pause-remark" rows="2" placeholder="例如：设备需要检查"></textarea></label>' +
        '<div class="aps-execution-inline-title aps-execution-inline-field-wide">新增异常记录</div>' +
        '<label>异常时间<input type="datetime-local" class="aps-actual-exception-time"></label>' +
        '<label>异常原因<select class="aps-actual-exception-reason">' + executionOptionsHtml(EXECUTION_REASON_CODES, "请选择原因", "") + '</select></label>' +
        '<label>异常严重程度<select class="aps-actual-exception-severity">' + executionOptionsHtml(EXECUTION_SEVERITY_CODES, "请选择严重程度", "") + '</select></label>' +
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

  function dateTimeTextFromInput(value) {
    const raw = trim(value);
    if (!raw) return "";
    return raw.replace("T", " ") + (raw.length === 16 ? ":00" : "");
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

  function executionPayload(button, createdBy, extraPayload) {
    const payload = {};
    const extra = extraPayload || {};
    payload.schedule_id = button.getAttribute("data-schedule-id") || "";
    payload.batch_id = button.getAttribute("data-batch-id") || "";
    payload.expected_state_revision = button.getAttribute("data-state-revision") || "";
    payload.created_by = createdBy;
    payload.feedback_person = createdBy;
    payload.idempotency_key = ["resource-dispatch", "actual", button.getAttribute("data-op-id") || "", String(Date.now())].join("-");
    payload.remark = trim(extra.remark);
    Object.keys(extra).forEach(function (key) {
      if (key !== "remark") payload[key] = trim(extra[key]);
    });
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
    if (!replaced && taskCard) tasks.push(taskCard);
    state.execution.tasks = tasks;
    state.execution.disabled_reason = "";
    ns.execution.renderExecutionCards(state.execution);
  }

  async function postExecutionAction(button) {
    if (!button || button.disabled) return;
    const action = trim(button.getAttribute("data-action"));
    const opId = trim(button.getAttribute("data-op-id"));
    if (!EXECUTION_ACTION_LABELS[action]) return;
    const actionLabel = EXECUTION_ACTION_LABELS[action];
    const extraPayload = inlineActualPayload(button);
    if (extraPayload === null) return;
    const postUrl = ns.execution.actualRecordUrl(opId);
    if (!postUrl) {
      executionNotice("当前方案不能填写实际情况。");
      return;
    }
    button.disabled = true;
    executionNotice("正在保存" + actionLabel + "，请稍候。");
    try {
      const payload = executionPayload(button, ns.execution.executionCreatedBy(), extraPayload || {});
      const resp = await fetch(postUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify(payload)
      });
      const responsePayload = await resp.json();
      if (!resp.ok || !responsePayload || responsePayload.success !== true) {
        const message = responsePayload && responsePayload.error && responsePayload.error.message ? responsePayload.error.message : actionLabel + "保存失败，请刷新后重试。";
        throw new Error(message);
      }
      replaceExecutionTask(responsePayload.data && responsePayload.data.task_card);
      loadData();
      clearExecutionInlineForms();
      executionNotice(actionLabel + "已保存。");
    } catch (err) {
      button.disabled = false;
      executionNotice(err && err.message ? err.message : actionLabel + "保存失败，请刷新后重试。");
    }
  }

  Object.assign(ns.execution, {
    clearExecutionInlineForms: clearExecutionInlineForms,
    postExecutionAction: postExecutionAction,
    renderActualInlineForm: renderActualInlineForm
  });
})();
