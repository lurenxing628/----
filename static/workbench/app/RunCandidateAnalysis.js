(function () {
  'use strict';

  const C = window.RunCandidateControls,
    M = window.RunCandidateModel;
  const labels = {
    overdue_count: window.WorkbenchTerms.overdue_count,
    total_tardiness_hours: window.WorkbenchTerms.total_tardiness_hours + '（小时）',
    changed_operation_count: '调整工序',
    machine_change_count: '换设备数'
  };
  function Value({
    metric
  }) {
    return /*#__PURE__*/React.createElement(React.Fragment, null, metric.value === null ? '未知' : M.number(metric.value), metric.value === null && /*#__PURE__*/React.createElement("small", null, "\u5DF2\u77E5\u5C0F\u8BA1 ", M.number(metric.known_subtotal), " \xB7 \u5F85\u786E\u8BA4 ", metric.unknown_count, " / ", metric.total_count), metric.reason && /*#__PURE__*/React.createElement("details", null, /*#__PURE__*/React.createElement("summary", null, "\u4F9D\u636E\u4E0D\u8DB3"), /*#__PURE__*/React.createElement("small", null, metric.reason.message)));
  }
  function Overview({
    data
  }) {
    return /*#__PURE__*/React.createElement("section", {
      "aria-label": "\u5B8C\u6574\u5019\u9009\u6BD4\u8F83\u6458\u8981",
      "data-candidate-analysis": data.candidate_ref
    }, /*#__PURE__*/React.createElement("div", {
      className: "rc-heading"
    }, /*#__PURE__*/React.createElement("h3", null, "\u6574\u4EFD\u5019\u9009\u4E0E\u6392\u4EA7\u65F6\u7684\u6B63\u5F0F\u8BA1\u5212"), /*#__PURE__*/React.createElement("span", {
      className: "rc-muted"
    }, data.batch_refs.length, " \u6279 \xB7 ", data.operations.operation_refs.length, " \u9053\u5DE5\u5E8F")), /*#__PURE__*/React.createElement("dl", {
      className: "rc-meta",
      "data-analysis-metrics": true
    }, Object.keys(labels).map(key => /*#__PURE__*/React.createElement("div", {
      key: key,
      "data-analysis-metric": key
    }, /*#__PURE__*/React.createElement("dt", null, labels[key]), /*#__PURE__*/React.createElement("dd", null, /*#__PURE__*/React.createElement(Value, {
      metric: data.metrics[key]
    }))))), /*#__PURE__*/React.createElement("div", {
      className: "rc-scope",
      "aria-label": "\u5019\u9009\u53D8\u5316\u4E0E\u53D6\u820D"
    }, Object.keys(data.delivery_deltas).map(key => /*#__PURE__*/React.createElement("span", {
      key: key
    }, labels[key], "\uFF1A", data.delivery_deltas[key] === null ? '对比基准或候选依据不足，变化未知' : M.signedChange(data.delivery_deltas[key]))), /*#__PURE__*/React.createElement("span", null, "\u8C03\u6574\u5DE5\u5E8F\uFF1A", data.metrics.changed_operation_count.value === null ? '完整数量待确认' : data.metrics.changed_operation_count.value + ' 道'), /*#__PURE__*/React.createElement("span", null, "\u6362\u8BBE\u5907\uFF1A", data.metrics.machine_change_count.value === null ? '完整数量待确认' : data.metrics.machine_change_count.value + ' 道'), /*#__PURE__*/React.createElement("span", null, "\u4EC5\u9648\u8FF0\u5DF2\u4FDD\u5B58\u5B89\u6392\u7684\u53D8\u5316\uFF0C\u672A\u8BC4\u4F30\u4F18\u5316\u6536\u76CA\u3001\u5B9E\u9645\u5DE5\u65F6\u6216\u6210\u672C\u3002")), !data.baseline.comparison_available && /*#__PURE__*/React.createElement("p", {
      className: "rc-notice"
    }, data.baseline.reason.message), /*#__PURE__*/React.createElement(C.Reasons, {
      rows: data.operations.issues.flatMap(row => row.reasons)
    }));
  }
  function Finish({
    row
  }) {
    return /*#__PURE__*/React.createElement(React.Fragment, null, row.planned_finish ? M.timeLabel(row.planned_finish) : '暂无数据', !row.planned_finish && row.partial_planned_finish && /*#__PURE__*/React.createElement("small", null, "\u5DF2\u5B89\u6392\u90E8\u5206\uFF1A", M.timeLabel(row.partial_planned_finish), "\uFF0C\u975E\u5168\u6279\u5B8C\u5DE5"));
  }
  function Batches({
    data,
    onBatch,
    onLast
  }) {
    const [page, setPage] = React.useState(1),
      pages = Math.max(1, Math.ceil(data.batches.length / 20)),
      current = Math.min(page, pages);
    return /*#__PURE__*/React.createElement("section", {
      "aria-label": "\u5019\u9009\u6279\u6B21\u4EA4\u4ED8\u5BF9\u7167"
    }, /*#__PURE__*/React.createElement("div", {
      className: "rc-heading"
    }, /*#__PURE__*/React.createElement("h3", null, "\u6279\u6B21\u4EA4\u4ED8\u5BF9\u7167"), /*#__PURE__*/React.createElement("span", {
      className: "rc-muted"
    }, "\u5B8C\u6574\u6392\u4EA7\u6279\u6B21 \xB7 \u5019\u9009\u51CF\u6392\u4EA7\u65F6\u7684\u6B63\u5F0F\u8BA1\u5212")), /*#__PURE__*/React.createElement("div", {
      className: "rc-table wb-table-frame",
      "data-sticky-head": true,
      "data-sticky-actions": true
    }, /*#__PURE__*/React.createElement("table", {
      className: "wb-table",
      "aria-label": "\u5019\u9009\u6279\u6B21\u4EA4\u4ED8\u5BF9\u7167"
    }, /*#__PURE__*/React.createElement("caption", {
      className: "wb-visually-hidden"
    }, "\u5019\u9009\u6279\u6B21\u4EA4\u4ED8\u5BF9\u7167"), /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, ['批次 / 零件', '交付截至日', '对比基准完工', '候选完工', '超期变化（小时）', '甘特定位'].map(label => /*#__PURE__*/React.createElement("th", {
      scope: "col",
      key: label
    }, label)))), /*#__PURE__*/React.createElement("tbody", null, data.batches.slice((current - 1) * 20, current * 20).map(row => /*#__PURE__*/React.createElement("tr", {
      key: row.batch_ref,
      "data-analysis-batch": row.batch_ref
    }, /*#__PURE__*/React.createElement("td", null, row.batch_id, /*#__PURE__*/React.createElement("small", null, row.part_label || '名称未填写')), /*#__PURE__*/React.createElement("td", null, row.after.due_date || '未记录'), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement(Finish, {
      row: row.before
    })), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement(Finish, {
      row: row.after
    })), /*#__PURE__*/React.createElement("td", null, row.delay_delta_hours === null ? '未知' : M.signedChange(row.delay_delta_hours)), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement(C.Button, {
      icon: "chart-gantt",
      disabled: !onBatch,
      "aria-label": '查看批次甘特 ' + row.batch_id,
      onClick: () => onBatch(row)
    }, "\u6279\u6B21\u7518\u7279"), (row.after.last_operations || []).map(task => /*#__PURE__*/React.createElement(C.Button, {
      key: task.row_ref,
      icon: "search",
      className: "mini",
      "aria-label": '定位末端工序 ' + row.batch_id + ' ' + task.sequence + (task.piece_id ? ' ' + task.piece_id : ''),
      onClick: () => onLast(task)
    }, M.number(task.sequence), " ", task.process_label || '工序未记录', task.piece_id && ' · ' + task.piece_id)))))))), /*#__PURE__*/React.createElement(C.Pager, {
      page: current,
      pages: pages,
      onPage: setPage,
      label: "\u6279\u6B21\u4EA4\u4ED8\u5BF9\u7167"
    }));
  }
  function History({
    data,
    onPlan
  }) {
    const [page, setPage] = React.useState(1),
      pages = Math.max(1, Math.ceil(data.items.length / 20)),
      current = Math.min(page, pages);
    return /*#__PURE__*/React.createElement("section", {
      "aria-label": "\u5019\u9009\u91C7\u7528\u8BB0\u5F55"
    }, /*#__PURE__*/React.createElement("h3", null, "\u91C7\u7528\u8BB0\u5F55 \xB7 ", data.total), !data.total ? /*#__PURE__*/React.createElement("p", {
      className: "rc-muted",
      role: "status"
    }, "\u8FD9\u4E2A\u5019\u9009\u65B9\u6848\u8FD8\u6CA1\u6709\u91C7\u7528\u8BB0\u5F55\u3002") : /*#__PURE__*/React.createElement("div", {
      className: "rc-table wb-table-frame",
      "data-sticky-head": true,
      "data-sticky-actions": true
    }, /*#__PURE__*/React.createElement("table", {
      className: "wb-table",
      "aria-label": "\u5019\u9009\u91C7\u7528\u8BB0\u5F55"
    }, /*#__PURE__*/React.createElement("caption", {
      className: "wb-visually-hidden"
    }, "\u5019\u9009\u91C7\u7528\u8BB0\u5F55"), /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, ['原正式计划', '采用时间', '经办人 / 记录人', '原因', '结果编号', '操作'].map(label => /*#__PURE__*/React.createElement("th", {
      scope: "col",
      key: label
    }, label)))), /*#__PURE__*/React.createElement("tbody", null, data.items.slice((current - 1) * 20, current * 20).map(row => /*#__PURE__*/React.createElement("tr", {
      key: row.receipt_ref,
      "data-adoption-receipt": row.receipt_ref
    }, /*#__PURE__*/React.createElement("td", null, row.official_plan.label, /*#__PURE__*/React.createElement("small", null, row.row_count, " \u9053\u5B89\u6392")), /*#__PURE__*/React.createElement("td", null, row.adoption ? M.timeLabel(row.adoption.adopted_at) : '暂无数据', /*#__PURE__*/React.createElement("small", null, "\u7ED3\u679C\u4FDD\u5B58\u65F6\u95F4\uFF1A", window.WorkbenchFormat.instant(row.committed_at_utc))), /*#__PURE__*/React.createElement("td", null, row.adoption ? /*#__PURE__*/React.createElement(React.Fragment, null, row.adoption.declared_operator, /*#__PURE__*/React.createElement("small", null, row.adoption.application_operator)) : '暂无数据'), /*#__PURE__*/React.createElement("td", null, row.adoption ? row.adoption.reason : '暂无数据'), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement(window.WorkbenchReference, {
      value: row.receipt_ref,
      label: "\u7ED3\u679C\u7F16\u53F7"
    }), /*#__PURE__*/React.createElement(C.Reasons, {
      rows: row.evidence_gaps
    })), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement(C.Button, {
      icon: "chart-gantt",
      disabled: !row.can_open || !onPlan,
      title: row.evidence_gaps.map(gap => gap.message).join(' '),
      "aria-label": '打开原采用计划 v' + row.official_plan.version,
      onClick: () => onPlan(row.official_plan)
    }, "\u6253\u5F00\u539F\u8BA1\u5212"))))))), /*#__PURE__*/React.createElement(C.Pager, {
      page: current,
      pages: pages,
      onPage: setPage,
      label: "\u5019\u9009\u91C7\u7528\u8BB0\u5F55"
    }));
  }
  window.RunCandidateAnalysis = {
    Overview,
    Batches,
    History
  };
})();
