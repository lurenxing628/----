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
  var formatChineseDateTime = contractApi.formatChineseDateTime;

  if (typeof getCriticalTooltip !== "function") return;
  if (typeof publicSourceLabel !== "function") return;
  if (typeof publicPriorityLabel !== "function") return;
  if (typeof formatChineseDateTime !== "function") return;

  function buildTaskPopupHtml(task, critical) {
    const meta = task && task.meta ? task.meta : {};
    const criticalInfo = getCriticalTooltip(task, critical);
    const sk = statusKeyForTask(task);
    const skZh = sk === "done" ? "已完成" : sk === "in_progress" ? "进行中" : sk === "blocked" ? "阻塞" : "未开始";

    // XSS 防御：所有动态字段必须 HTML 转义后再拼接
    const titleText = escapeHtml(str(meta._raw_name || (task && task.name ? task.name : "")));
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
      `<div class="subtitle">优先级：${priorityText}</div>`,
      `<div class="subtitle">交期：${dueText}</div>`,
      `<div class="subtitle">关键工序：${ccStatusText}</div>`,
      `<div class="subtitle">超期：${meta.is_overdue ? "是" : "否"}</div>`,
    ];
    if (criticalInfo.isCritical && ccFromText !== "-") {
      lines.push(`<div class="subtitle">前面影响它的工序编号：${ccFromText}</div>`);
    }
    if (criticalInfo.isCritical && ccReasonText !== "-") {
      lines.push(`<div class="subtitle">为什么影响总工期：${ccReasonText}</div>`);
    }
    if (criticalInfo.isCritical && ccGapText !== "-") {
      lines.push(`<div class="subtitle">中间等待：${ccGapText}</div>`);
    }
    if (ccUnavailableText) {
      lines.push(`<div class="subtitle">关键链暂不可用：${ccUnavailableText}</div>`);
    }
    return lines.join("") + `<div class="pointer"></div>`;
  }

  ns.popup = Object.assign({}, ns.popup || {}, {
    buildTaskPopupHtml: buildTaskPopupHtml,
  });
})();
