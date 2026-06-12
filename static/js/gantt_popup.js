(function () {
  var ns = window.__APS_GANTT__;
  if (!ns) return;
  if (!ns._inited) ns._inited = {};
  if (ns._inited.popup) return;
  ns._inited.popup = true;

  var str = ns.str;
  var escapeHtml = ns.escapeHtml;
  var statusKeyForTask = ns.statusKeyForTask;
  var contractApi = ns.contract;

  if (typeof str !== "function") return;
  if (typeof escapeHtml !== "function") return;
  if (typeof statusKeyForTask !== "function") return;
  if (!contractApi) return;

  var getCriticalTooltip = contractApi.getCriticalTooltip;
  var publicSourceLabel = contractApi.publicSourceLabel;
  var publicPriorityLabel = contractApi.publicPriorityLabel;
  var publicStatusLabel = contractApi.publicStatusLabel;
  var formatChineseDateTime = contractApi.formatChineseDateTime;

  if (typeof getCriticalTooltip !== "function") return;
  if (typeof publicSourceLabel !== "function") return;
  if (typeof publicPriorityLabel !== "function") return;
  if (typeof publicStatusLabel !== "function") return;
  if (typeof formatChineseDateTime !== "function") return;

  function formatDurationMinutes(minutes) {
    const n = Number(minutes);
    if (!isFinite(n) || n <= 0) return "-";
    const h = Math.floor(n / 60);
    const m = Math.round(n % 60);
    if (h <= 0) return m + " 分钟";
    if (m <= 0) return h + " 小时";
    return h + " 小时 " + m + " 分钟";
  }

  function detailValue(value, fallback) {
    const text = str(value || "");
    return text ? text : (fallback || "-");
  }

  function detailRow(label, value) {
    return '<div class="aps-gantt-task-detail-row"><dt>' + escapeHtml(label) + '</dt><dd>' + escapeHtml(detailValue(value)) + '</dd></div>';
  }

  function detailLinkHtml(link) {
    const item = link && typeof link === "object" ? link : {};
    const label = detailValue(item.label, "查看详情");
    const disabled = item.disabled === true || !str(item.url || "");
    if (disabled) {
      const reason = detailValue(item.disabled_reason, "当前入口暂时不可用。");
      return '<span class="aps-gantt-task-detail-link is-disabled" aria-disabled="true" title="' + escapeHtml(reason) + '">' + escapeHtml(label) + '</span>';
    }
    return '<a class="aps-gantt-task-detail-link" href="' + escapeHtml(item.url) + '">' + escapeHtml(label) + '</a>';
  }

  function detailLinksHtml(links) {
    const list = Array.isArray(links) ? links : [];
    if (!list.length) return "";
    const items = [];
    for (let i = 0; i < list.length; i++) {
      items.push(detailLinkHtml(list[i]));
    }
    return '<div class="aps-gantt-task-detail-links" aria-label="下一步入口">' + items.join("") + '</div>';
  }

  function stripInternalTaskTokens(value) {
    return str(value || "").replace(/\bop_\d+\b/g, "").replace(/\s+/g, " ").trim();
  }

  function detailTitle(task, meta) {
    const preferred = [
      meta.detail_title,
      meta.task_label,
      meta.operation_label,
      meta.part_label,
    ];
    for (let i = 0; i < preferred.length; i++) {
      const text = stripInternalTaskTokens(preferred[i]);
      if (text) return text;
    }
    return stripInternalTaskTokens(meta._raw_name || (task && task.name ? task.name : "")) || "未命名任务";
  }

  function buildTaskDetailHtml(task, critical) {
    const meta = task && task.meta ? task.meta : {};
    const criticalInfo = getCriticalTooltip(task, critical);
    const title = detailTitle(task, meta);
    const plannedTime = detailValue(
      meta.planned_time_label,
      formatChineseDateTime(task && task.start ? task.start : "") + " ～ " + formatChineseDateTime(task && task.end ? task.end : "")
    );
    const statusText = detailValue(meta.execution_status_label, publicStatusLabel(meta.status));
    const overdueText = detailValue(meta.overdue_label, meta.is_overdue ? "已标记超期" : "未标记超期");
    const actualSummary = detailValue(meta.actual_summary_label, "暂未记录现场实际");
    const delayHint = detailValue(
      meta.delay_hint,
      meta.is_overdue ? "该批次已被标记为超期，建议查看超期清单或排产诊断。" : "当前未被标记为超期。"
    );
    const criticalText = criticalInfo.available === false
      ? detailValue(criticalInfo.unavailableMessage, "关键工序关系暂时看不了")
      : detailValue(criticalInfo.statusLabel, "-");

    const walkApi = (window.__APS_GANTT__ || {}).chainWalk;
    let walkHtml = "";
    if (walkApi && task && task.id) {
      const hasPrev = walkApi.hasPrev(task.id);
      const hasNext = walkApi.hasNext(task.id);
      const ccPos = walkApi.criticalPosition(task.id);
      const notice = str(walkApi.currentNotice ? walkApi.currentNotice() : "");
      const walkTitle = "按排程顺序沿工艺链移动（同批次同件）";
      walkHtml = [
        '<div class="aps-gantt-task-walk">',
        '<button type="button" data-walk="prev"' + (hasPrev ? "" : ' disabled title="已是本件第一道（按排程顺序）"') + (hasPrev ? ' title="' + escapeHtml(walkTitle) + '"' : "") + '>上一道</button>',
        '<button type="button" data-walk="next"' + (hasNext ? "" : ' disabled title="已是本件最后一道（按排程顺序）"') + (hasNext ? ' title="' + escapeHtml(walkTitle) + '"' : "") + '>下一道</button>',
        '<span class="aps-gantt-task-walk-cc">' + escapeHtml(ccPos ? ("关键链 " + ccPos.index + "/" + ccPos.total + "（←/→ 巡检）") : "不在关键链") + '</span>',
        '</div>',
        notice ? '<div class="aps-gantt-task-walk-notice">' + escapeHtml(notice) + '</div>' : "",
      ].join("");
    }
    return [
      '<div class="aps-gantt-task-detail-content">',
        '<div class="aps-gantt-task-detail-head">',
          '<div>',
            '<div class="aps-gantt-task-detail-kicker">任务详情</div>',
            '<h3>' + escapeHtml(title) + '</h3>',
          '</div>',
          '<span class="aps-gantt-task-detail-badge' + (meta.is_overdue ? ' is-overdue' : '') + '">' + escapeHtml(overdueText) + '</span>',
        '</div>',
        walkHtml,
        '<div class="aps-gantt-task-detail-summary">' + escapeHtml(actualSummary) + '</div>',
        '<dl class="aps-gantt-task-detail-grid">',
          detailRow("批次", meta.batch_id),
          detailRow("图号或物料", meta.part_label || meta.part_no || meta.part_name || meta.piece_id),
          detailRow("工序", meta.operation_label || ((meta.seq || "-") + "（" + detailValue(meta.op_type_name) + "）")),
          detailRow("资源", meta.resource_label || ("设备：" + detailValue(meta.machine) + "；人员：" + detailValue(meta.operator))),
          detailRow("优先级", publicPriorityLabel(meta.priority)),
          detailRow("加工方式", publicSourceLabel(meta.source)),
          detailRow("计划时间", plannedTime),
          detailRow("时长", formatDurationMinutes(meta.duration_minutes)),
          detailRow("现场状态", statusText),
          detailRow("实际开工", meta.actual_start_time_label),
          detailRow("实际完工", meta.actual_end_time_label),
          detailRow("交期", formatChineseDateTime(meta.due_date)),
          detailRow("关键工序", criticalText),
        '</dl>',
        '<div class="aps-gantt-task-detail-note">' + escapeHtml(delayHint) + '</div>',
        detailLinksHtml(meta.detail_links),
      '</div>',
    ].join("");
  }

  function renderTaskDetail(target, task, critical) {
    if (!target) return;
    target.innerHTML = buildTaskDetailHtml(task, critical);
  }

  function renderTaskDetailEmpty(target) {
    if (!target) return;
    target.innerHTML = '<div class="aps-gantt-task-detail-empty">点击甘特条查看任务详情</div>';
  }

  function buildTaskPopupHtml(task, critical) {
    const meta = task && task.meta ? task.meta : {};
    const criticalInfo = getCriticalTooltip(task, critical);
    const sk = statusKeyForTask(task);
    const skZh = sk === "done" ? "已完成" : sk === "in_progress" ? "进行中" : sk === "blocked" ? "阻塞" : "未开始";

    // XSS 防御：所有动态字段必须 HTML 转义后再拼接
    const titleText = escapeHtml(detailTitle(task, meta));
    const startText = escapeHtml(formatChineseDateTime(task && task.start ? task.start : ""));
    const endText = escapeHtml(formatChineseDateTime(task && task.end ? task.end : ""));
    const batchText = escapeHtml(str(meta.batch_id || "-"));
    const pieceText = escapeHtml(str(meta.piece_id || "-"));
    const partText = escapeHtml(str(meta.part_no || "-"));
    const seqText = escapeHtml(str(meta.seq || "-"));
    const opTypeText = escapeHtml(str(meta.op_type_name || "-"));
    const machineText = escapeHtml(str(meta.machine || "-"));
    const operatorText = escapeHtml(str(meta.operator || "-"));
    const sourceText = escapeHtml(publicSourceLabel(meta.source));
    const statusText = escapeHtml(str(skZh));
    const priorityText = escapeHtml(publicPriorityLabel(meta.priority));
    const dueText = escapeHtml(formatChineseDateTime(meta.due_date));
    const ccStatusText = escapeHtml(str(criticalInfo.statusLabel));
    const ccFromText = escapeHtml(str(criticalInfo.predecessorText));
    const ccReasonText = escapeHtml(str(criticalInfo.reasonText));
    const ccGapText = escapeHtml(str(criticalInfo.gapText));
    const ccUnavailableText = escapeHtml(str(criticalInfo.unavailableMessage));

    const lines = [
      `<div class="title">${titleText}</div>`,
      `<div class="subtitle">时间：${startText} ～ ${endText}</div>`,
      `<div class="subtitle">批次：${batchText}</div>`,
      `<div class="subtitle">件：${pieceText}</div>`,
      `<div class="subtitle">图号：${partText}</div>`,
      `<div class="subtitle">工序：${seqText}（${opTypeText}）</div>`,
      `<div class="subtitle">设备：${machineText}</div>`,
      `<div class="subtitle">人员：${operatorText}</div>`,
      `<div class="subtitle">加工方式：${sourceText}</div>`,
      `<div class="subtitle">状态：${statusText}</div>`,
      `<div class="subtitle">现场：${escapeHtml(str(meta.actual_summary_label || "暂未记录现场实际"))}</div>`,
      `<div class="subtitle">优先级：${priorityText}</div>`,
      `<div class="subtitle">交期：${dueText}</div>`,
      `<div class="subtitle">关键工序：${ccStatusText}</div>`,
      `<div class="subtitle">超期：${meta.is_overdue ? "是" : "否"}</div>`,
    ];
    if (criticalInfo.isCritical && ccFromText !== "-") {
      lines.push(`<div class="subtitle">前面影响它的工序：${ccFromText}</div>`);
    }
    if (criticalInfo.isCritical && ccReasonText !== "-") {
      lines.push(`<div class="subtitle">为什么影响总工期：${ccReasonText}</div>`);
    }
    if (criticalInfo.isCritical && ccGapText !== "-") {
      lines.push(`<div class="subtitle">中间等待：${ccGapText}</div>`);
    }
    if (ccUnavailableText) {
      lines.push(`<div class="subtitle">关键工序关系暂时看不了：${ccUnavailableText}</div>`);
    }
    return lines.join("") + `<div class="pointer"></div>`;
  }

  ns.popup = Object.assign({}, ns.popup || {}, {
    buildTaskPopupHtml: buildTaskPopupHtml,
    buildTaskDetailHtml: buildTaskDetailHtml,
    renderTaskDetail: renderTaskDetail,
    renderTaskDetailEmpty: renderTaskDetailEmpty,
  });
})();
