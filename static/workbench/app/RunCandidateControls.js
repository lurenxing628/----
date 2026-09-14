(function () {
  'use strict';

  const {
    Button,
    Icon
  } = window.ResourceControls;
  function ErrorBox({
    error
  }) {
    return error ? /*#__PURE__*/React.createElement("div", {
      className: "rc-notice rc-error",
      role: "alert"
    }, error.message || '候选方案读取失败，没有显示替代结果。请刷新后重试。') : null;
  }
  function Reasons({
    rows = []
  }) {
    const groups = new Map();
    rows.forEach(r => {
      const key = [r.field, r.code, r.message].join('\n');
      if (!groups.has(key)) groups.set(key, {
        ...r,
        count: 0
      });
      groups.get(key).count++;
    });
    const [page, setPage] = React.useState(1),
      values = Array.from(groups.values()),
      pages = Math.max(1, Math.ceil(values.length / 20)),
      current = Math.min(page, pages);
    if (!values.length) return null;
    return /*#__PURE__*/React.createElement("details", {
      className: "rc-reasons"
    }, /*#__PURE__*/React.createElement("summary", null, "\u539F\u56E0\u4E0E\u6570\u636E\u7F3A\u9879 \xB7 ", rows.length, " \u9879"), values.slice((current - 1) * 20, current * 20).map((r, i) => /*#__PURE__*/React.createElement("div", {
      key: i
    }, r.message, r.count > 1 && '（' + r.count + ' 项）', r.field && /*#__PURE__*/React.createElement(window.WorkbenchReference, {
      entries: {
        '数据项': r.field,
        '原因码': r.code
      }
    }))), pages > 1 && /*#__PURE__*/React.createElement(Pager, {
      page: current,
      pages: pages,
      onPage: setPage,
      label: "\u539F\u56E0"
    }));
  }
  function Pager({
    page,
    pages,
    onPage,
    disabled,
    label
  }) {
    return /*#__PURE__*/React.createElement(window.WorkbenchListControls.Pager, {
      page: page,
      pages: pages,
      onPage: onPage,
      disabled: disabled,
      label: label
    });
  }
  function Metric({
    metric,
    suffix = '',
    kind
  }) {
    return metric.value === null ? /*#__PURE__*/React.createElement("details", {
      className: "rc-metric rc-muted"
    }, /*#__PURE__*/React.createElement("summary", {
      title: metric.reason.message
    }, "\u672A\u77E5"), /*#__PURE__*/React.createElement("small", null, metric.reason.message)) : /*#__PURE__*/React.createElement("span", null, ['machine_util_avg', 'operator_util_avg'].includes(kind) ? window.RunCandidateModel.percent(metric.value) : window.RunCandidateModel.number(metric.value), suffix);
  }
  function Status({
    candidate
  }) {
    return /*#__PURE__*/React.createElement("span", {
      className: 'pill ' + (candidate.status === 'completed' && candidate.completeness === 'complete' ? 'ok' : 'warn'),
      "data-candidate-status": candidate.status
    }, /*#__PURE__*/React.createElement("span", {
      className: "dot"
    }), {
      completed: '已完成',
      partial: '部分完成',
      failed: '失败',
      skipped: '已跳过'
    }[candidate.status], candidate.completeness === 'unknown' && ' · 完整性未知');
  }
  function Catalog({
    result,
    selectedRef,
    busy,
    query,
    onQuery,
    onSelect
  }) {
    const d = result && result.data;
    const [open, setOpen] = React.useState(!selectedRef),
      panel = React.useRef(null);
    React.useEffect(() => {
      if (selectedRef && panel.current && panel.current.contains(document.activeElement)) panel.current.querySelector(':scope > summary').focus({
        preventScroll: true
      });
      setOpen(!selectedRef);
    }, [selectedRef]);
    return /*#__PURE__*/React.createElement("details", {
      className: "rc-catalog",
      ref: panel,
      open: open,
      onToggle: e => setOpen(e.currentTarget.open)
    }, /*#__PURE__*/React.createElement("summary", null, "\u5019\u9009\u6BD4\u8F83", d && ' · ' + d.candidate_count + ' 项', selectedRef && !open ? ' · 展开查看其他候选' : ''), /*#__PURE__*/React.createElement("section", {
      "aria-label": "\u5019\u9009\u6BD4\u8F83"
    }, /*#__PURE__*/React.createElement("div", {
      className: "rc-heading"
    }, /*#__PURE__*/React.createElement("h3", null, "\u5019\u9009\u6BD4\u8F83", d && ' · ' + d.candidate_count + ' 项'), /*#__PURE__*/React.createElement("div", {
      className: "rc-tools"
    }, /*#__PURE__*/React.createElement("label", null, "\u72B6\u6001 ", /*#__PURE__*/React.createElement("select", {
      "aria-label": "\u5019\u9009\u72B6\u6001",
      value: query.status || 'all',
      disabled: busy,
      onChange: e => onQuery({
        status: e.target.value
      })
    }, [['all', '全部'], ['completed', '已完成'], ['partial', '部分完成'], ['failed', '失败'], ['skipped', '已跳过']].map(([v, t]) => /*#__PURE__*/React.createElement("option", {
      key: v,
      value: v
    }, t)))), /*#__PURE__*/React.createElement("label", null, "\u6392\u5E8F ", /*#__PURE__*/React.createElement("select", {
      "aria-label": "\u5019\u9009\u6392\u5E8F",
      value: query.sort || 'sequence',
      disabled: busy,
      onChange: e => onQuery({
        sort: e.target.value
      })
    }, /*#__PURE__*/React.createElement("option", {
      value: "sequence"
    }, "\u751F\u6210\u987A\u5E8F"), /*#__PURE__*/React.createElement("option", {
      value: "label"
    }, "\u540D\u79F0"), /*#__PURE__*/React.createElement("option", {
      value: "task_count"
    }, "\u5B89\u6392\u6570"))))), d && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      className: "rc-table wb-table-frame",
      "data-sticky-head": true,
      "data-sticky-actions": true
    }, /*#__PURE__*/React.createElement("table", {
      className: "wb-table",
      "aria-label": "\u5019\u9009\u6BD4\u8F83"
    }, /*#__PURE__*/React.createElement("caption", {
      className: "wb-visually-hidden"
    }, "\u5019\u9009\u6BD4\u8F83"), /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", {
      scope: "col",
      className: "wb-col-key"
    }, window.WorkbenchTerms.candidate), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u72B6\u6001"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u5B89\u6392"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, window.WorkbenchTerms.overdue_count), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, window.WorkbenchTerms.total_tardiness_hours, "\uFF08\u5C0F\u65F6\uFF09"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u65F6\u957F\uFF08\u5C0F\u65F6\uFF09"), /*#__PURE__*/React.createElement("th", {
      scope: "col",
      className: "wb-col-actions"
    }, "\u64CD\u4F5C"))), /*#__PURE__*/React.createElement("tbody", null, d.candidates.map((c, index) => /*#__PURE__*/React.createElement("tr", {
      key: c.candidate_ref,
      "data-candidate-ref": c.candidate_ref,
      "aria-selected": c.candidate_ref === selectedRef
    }, /*#__PURE__*/React.createElement("td", {
      className: "wb-col-key"
    }, /*#__PURE__*/React.createElement("div", {
      className: "rc-name"
    }, /*#__PURE__*/React.createElement("span", null, c.label || '生成时名称未填写'), /*#__PURE__*/React.createElement(window.WorkbenchReference, {
      value: c.candidate_ref
    }))), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement(Status, {
      candidate: c
    })), /*#__PURE__*/React.createElement("td", null, c.task_count), ['overdue_count', 'total_tardiness_hours', 'makespan_hours'].map(k => /*#__PURE__*/React.createElement("td", {
      key: k
    }, /*#__PURE__*/React.createElement(Metric, {
      metric: c.metrics[k]
    }))), /*#__PURE__*/React.createElement("td", {
      className: "wb-col-actions"
    }, /*#__PURE__*/React.createElement(Button, {
      icon: "search",
      className: "mini",
      "aria-label": '查看候选 ' + (c.label || '第 ' + ((d.page.number - 1) * d.page.size + index + 1) + ' 项'),
      disabled: busy || d.capabilities.view !== true || c.capabilities.view !== true,
      onClick: () => onSelect(c)
    }, "\u67E5\u770B"))))))), !d.candidates.length && /*#__PURE__*/React.createElement("p", {
      className: "rc-muted"
    }, "\u8FD9\u6B21\u6392\u4EA7\u5728\u5F53\u524D\u7B5B\u9009\u4E0B\u6CA1\u6709\u5019\u9009\u65B9\u6848\u3002"), !d.catalog_complete && /*#__PURE__*/React.createElement("p", {
      className: "rc-notice"
    }, "\u8FD9\u6B21\u6392\u4EA7\u8FD8\u6CA1\u7ED3\u675F\uFF0C\u5019\u9009\u65B9\u6848\u5217\u8868\u8FD8\u4E0D\u5B8C\u6574\u3002"), /*#__PURE__*/React.createElement("div", {
      className: "rc-heading"
    }, /*#__PURE__*/React.createElement("span", {
      className: "rc-muted"
    }, "\u4EA4\u4ED8\u6307\u6807\u4EC5\u8986\u76D6\u5B8C\u6210\u6279\u6B21\uFF1B\u8D44\u6E90\u6307\u6807\u4EC5\u8986\u76D6\u5DF2\u6392\u7ED3\u679C\uFF0C\u7F3A\u9879\u4E0D\u6309\u96F6\u8BA1\u7B97\u3002"), /*#__PURE__*/React.createElement(Pager, {
      page: d.page.number,
      pages: Math.max(1, Math.ceil(d.page.total / d.page.size)),
      disabled: busy,
      label: "\u5019\u9009",
      onPage: page => onQuery({
        page
      }, true)
    })))));
  }
  function Generation({
    data,
    analysis
  }) {
    const g = data.generation,
      input = g.input,
      M = window.RunCandidateModel;
    return /*#__PURE__*/React.createElement("section", {
      "aria-label": "\u751F\u6210\u65F6\u8303\u56F4"
    }, /*#__PURE__*/React.createElement("div", {
      className: "rc-heading"
    }, /*#__PURE__*/React.createElement("div", {
      className: "rc-tools"
    }, /*#__PURE__*/React.createElement("h3", null, "\u5F53\u524D\uFF1A", data.candidate.label || '名称未填写'), /*#__PURE__*/React.createElement(Status, {
      candidate: data.candidate
    }), /*#__PURE__*/React.createElement("span", {
      className: "rc-pending"
    }, "\u751F\u6210\u65F6\u8FD8\u6CA1\u6210\u4E3A\u6B63\u5F0F\u8BA1\u5212")), /*#__PURE__*/React.createElement("span", null, "\u751F\u6210\u65E5\u671F\uFF1A", input.start_date || '未记录', " \u81F3 ", input.end_date || '未记录')), /*#__PURE__*/React.createElement("div", {
      className: "rc-source-summary"
    }, /*#__PURE__*/React.createElement("details", {
      className: "rc-reasons rc-generation wb-ref"
    }, /*#__PURE__*/React.createElement("summary", null, "\u751F\u6210\u8D44\u6599\u4E0E\u8BB0\u5F55\u7F16\u53F7"), /*#__PURE__*/React.createElement("dl", {
      className: "rc-meta"
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u63D0\u4EA4 / \u7ED3\u675F\u65F6\u95F4"), /*#__PURE__*/React.createElement("dd", null, M.timeLabel(g.accepted_at), /*#__PURE__*/React.createElement("small", null, M.timeLabel(g.finished_at)))), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u9F50\u5957\u68C0\u67E5 / \u7F3A\u8D44\u6E90"), /*#__PURE__*/React.createElement("dd", null, input.ready_check === null ? '未记录' : input.ready_check ? '开启' : '关闭', " / ", {
      auto_assign: '自动分配',
      exclude: '暂不排'
    }[input.missing_resource_policy] || '未记录')), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u5DF2\u6709\u6267\u884C / \u5F53\u65F6\u7684\u6B63\u5F0F\u8BA1\u5212"), /*#__PURE__*/React.createElement("dd", null, input.completed_policy === 'preserve_actuals' ? '保留已有开工和完工记录' : '执行规则未记录', /*#__PURE__*/React.createElement("small", null, g.baseline.captured_task_count === null ? '正式计划安排数未知' : '已保留 ' + g.baseline.captured_task_count + ' 道正式计划安排')))), /*#__PURE__*/React.createElement("div", {
      className: "rc-muted"
    }, "\u540D\u79F0\u3001\u8D44\u6E90\u3001\u4EA4\u671F\u548C\u6267\u884C\u72B6\u6001\u6765\u81EA\u751F\u6210\u65F6\u4FDD\u5B58\u7684\u8D44\u6599\uFF0C\u672A\u8BFB\u53D6\u540E\u6765\u7684\u4FEE\u6539\u3002", analysis ? analysis.baseline.reason && analysis.baseline.reason.message : g.baseline.reason.message), /*#__PURE__*/React.createElement("div", {
      className: "rc-muted"
    }, analysis ? '排产时选批：' + analysis.batches.map(row => row.batch_id).join(' / ') : '原始选批清单尚未核对，不能用可见安排反推生成时的完整选批范围。'), /*#__PURE__*/React.createElement("div", null, "\u6392\u4EA7\u8BB0\u5F55\u7F16\u53F7\uFF1A", /*#__PURE__*/React.createElement("code", null, g.run_ref)), /*#__PURE__*/React.createElement("div", null, "\u5019\u9009\u8BB0\u5F55\u7F16\u53F7\uFF1A", /*#__PURE__*/React.createElement("code", null, data.candidate.candidate_ref)), /*#__PURE__*/React.createElement("dl", {
      className: "rc-meta"
    }, window.RunCandidateAPI.metricKeys.map(k => /*#__PURE__*/React.createElement("div", {
      key: k
    }, /*#__PURE__*/React.createElement("dt", null, M.metricLabels[k]), /*#__PURE__*/React.createElement("dd", null, /*#__PURE__*/React.createElement(Metric, {
      metric: data.candidate.metrics[k],
      kind: k
    })))), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u5B9E\u9645\u5DE5\u65F6 / \u6210\u672C"), /*#__PURE__*/React.createElement("dd", null, "\u6682\u65E0\u6570\u636E", /*#__PURE__*/React.createElement("small", null, "\u7CFB\u7EDF\u8FD8\u6CA1\u6709\u5B9E\u9645\u5DE5\u65F6\u548C\u6210\u672C\u8BB0\u5F55\u3002"))))), /*#__PURE__*/React.createElement("span", {
      className: "rc-muted"
    }, analysis ? '完整排产范围 ' + analysis.batch_refs.length + ' 批' : '完整排产范围待核对'), /*#__PURE__*/React.createElement(Reasons, {
      rows: [...data.data_gaps, ...data.candidate.data_gaps, ...g.data_gaps, ...data.blocked_reasons, ...data.candidate.blocked_reasons]
    })));
  }
  function Detail({
    task,
    onClose
  }) {
    const M = window.RunCandidateModel;
    return /*#__PURE__*/React.createElement("aside", {
      className: "rc-detail",
      "aria-label": "\u5019\u9009\u5DE5\u5E8F\u8BE6\u60C5"
    }, /*#__PURE__*/React.createElement("div", {
      className: "rc-heading"
    }, /*#__PURE__*/React.createElement("h3", null, "\u5DE5\u5E8F\u8BE6\u60C5"), task && /*#__PURE__*/React.createElement(Button, {
      icon: "x",
      "aria-label": "\u5173\u95ED\u5DE5\u5E8F\u8BE6\u60C5",
      onClick: onClose
    })), !task ? /*#__PURE__*/React.createElement("p", {
      className: "rc-muted"
    }, "\u5C1A\u672A\u9009\u62E9\u5DE5\u5E8F") : /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("strong", null, task.batch_label || '批次名称未填写', " \xB7 ", task.process_label || '工序名称未填写'), /*#__PURE__*/React.createElement("dl", null, [['零件', task.part_label], ['工序顺序', M.number(task.sequence)], ['分件', task.piece_id === null ? task.data_gaps.some(g => g.field === 'piece_id') ? '分件未记录' : '共同工序' : task.piece_id], ['本工序目标量', M.number(task.quantity)], ['生成时整批量', M.number(task.batch_quantity)], ['交期', task.due_date], ['开始', task.start && M.timeLabel(task.start)], ['结束', task.end && M.timeLabel(task.end)], ['设备', task.machine && task.machine.label], ['人员', task.operator && task.operator.label], ['外协商', task.supplier && task.supplier.label], ['来源', task.source === 'internal' ? '内部' : task.source === 'external' ? '外协' : null], ['生成时锁定', typeof task.locked === 'boolean' ? task.locked ? '是' : '否' : null], ['安排状态', task.reason ? task.reason.message : '已保存候选安排']].map(([k, v]) => /*#__PURE__*/React.createElement("div", {
      key: k
    }, /*#__PURE__*/React.createElement("dt", null, k), /*#__PURE__*/React.createElement("dd", null, v == null ? '未记录' : v)))), /*#__PURE__*/React.createElement(window.WorkbenchReference, {
      entries: {
        '安排编号': task.row_ref,
        '工序编号': task.operation_ref,
        '批次编号': task.batch_ref
      }
    }), /*#__PURE__*/React.createElement("h4", null, "\u751F\u6210\u65F6\u7684\u5F00\u5DE5\u548C\u5B8C\u5DE5\u8BB0\u5F55"), task.execution_at_generation ? /*#__PURE__*/React.createElement("dl", null, Object.entries(task.execution_at_generation).map(([k, v]) => /*#__PURE__*/React.createElement("div", {
      key: k
    }, /*#__PURE__*/React.createElement("dt", null, M.executionLabels[k]), /*#__PURE__*/React.createElement("dd", null, v === null ? '未知' : M.executionValue(v))))) : /*#__PURE__*/React.createElement("p", {
      className: "rc-muted"
    }, "\u672A\u4FDD\u7559\u751F\u6210\u65F6\u7684\u5F00\u5DE5\u548C\u5B8C\u5DE5\u8BB0\u5F55\uFF0C\u4E0D\u80FD\u63A8\u65AD\u4E3A\u672A\u5F00\u5DE5\u3002"), /*#__PURE__*/React.createElement("p", {
      className: "rc-muted"
    }, "\u5B9E\u9645\u5DE5\u65F6\u548C\u6210\u672C\uFF1A\u6682\u65E0\u6570\u636E\u3002\u7CFB\u7EDF\u8FD8\u6CA1\u6709\u8FD9\u4E9B\u8BB0\u5F55\uFF0C\u5B89\u6392\u65F6\u957F\u4E0D\u7B49\u4E8E\u5B9E\u9645\u5DE5\u65F6\u3002"), /*#__PURE__*/React.createElement(Reasons, {
      rows: task.data_gaps
    })));
  }
  function Styles() {
    return null;
  }
  function Delivery({
    data,
    onLast
  }) {
    const M = window.RunCandidateModel;
    const [page, setPage] = React.useState(1),
      summary = data.summary;
    const pages = Math.max(1, Math.ceil(data.items.length / 20)),
      current = Math.min(page, pages);
    const reasons = {
      operations_unscheduled: '尚有工序未安排',
      operations_missing: '排产时工序未记录',
      schedule_time_invalid: '安排时间无效',
      saved_plan_incomplete: '候选结果不完整',
      due_date_missing: '交期未记录',
      due_date_invalid: '交期无效',
      due_date_unspecified: '未指定交期',
      part_label_missing: '零件名称未填写'
    };
    return /*#__PURE__*/React.createElement("section", {
      "aria-label": "\u5019\u9009\u9010\u6279\u4EA4\u4ED8\u98CE\u9669"
    }, /*#__PURE__*/React.createElement("h3", null, "\u9010\u6279\u4EA4\u4ED8\u98CE\u9669"), /*#__PURE__*/React.createElement("dl", {
      className: "rc-meta"
    }, [[summary.overdue_count, '已确认预计超期'], [summary.total_tardiness_hours, '完整范围超期（小时）'], [summary.unknown_count, '交付待确认'], [summary.batch_count, '关联批次']].map(([value, label]) => /*#__PURE__*/React.createElement("div", {
      key: label
    }, /*#__PURE__*/React.createElement("dt", null, label), /*#__PURE__*/React.createElement("dd", null, M.number(value))))), /*#__PURE__*/React.createElement("p", {
      className: "rc-muted"
    }, "\u4F9D\u636E\uFF1A\u6392\u4EA7\u65F6\u7684\u8D44\u6599\u548C\u540C\u6279\u5B8C\u6574\u5019\u9009\u5B89\u6392\u3002\u4E0D\u662F\u5B9E\u9645\u5B8C\u5DE5\u6216\u53D1\u8D27\uFF1B\u6CA1\u6709\u6838\u5BF9\u7B49\u5F85\u3001\u505C\u673A\u6216\u7F3A\u6599\u7684\u539F\u56E0\u3002"), data.issues.map((issue, index) => /*#__PURE__*/React.createElement("p", {
      className: "rc-notice",
      key: index
    }, issue.message)), /*#__PURE__*/React.createElement("div", {
      className: "rc-table wb-table-frame",
      "data-sticky-head": true,
      "data-sticky-actions": true
    }, /*#__PURE__*/React.createElement("table", {
      className: "wb-table",
      "aria-label": "\u5019\u9009\u4EA4\u4ED8\u98CE\u9669\u5217\u8868"
    }, /*#__PURE__*/React.createElement("caption", {
      className: "wb-visually-hidden"
    }, "\u5019\u9009\u4EA4\u4ED8\u98CE\u9669\u5217\u8868"), /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, ['批次 / 零件', '批量 / 工序覆盖', '交付截至日', '全批计划完工', '预计交付', '末端工序 / 依据'].map(label => /*#__PURE__*/React.createElement("th", {
      scope: "col",
      key: label
    }, label)))), /*#__PURE__*/React.createElement("tbody", null, data.items.slice((current - 1) * 20, current * 20).map(row => /*#__PURE__*/React.createElement("tr", {
      key: row.batch_ref
    }, /*#__PURE__*/React.createElement("td", null, row.batch_id, /*#__PURE__*/React.createElement("small", null, row.part_no || '图号未记录', " \xB7 ", row.part_label || '名称未填写')), /*#__PURE__*/React.createElement("td", null, M.number(row.quantity), " \u4EF6", /*#__PURE__*/React.createElement("small", null, row.scheduled_operation_count, " / ", row.operation_count, " \u9053")), /*#__PURE__*/React.createElement("td", null, row.due_date || '未记录'), /*#__PURE__*/React.createElement("td", null, row.planned_finish ? M.timeLabel(row.planned_finish) : '暂无数据', row.partial_planned_finish && /*#__PURE__*/React.createElement("small", null, "\u5DF2\u5B89\u6392\u90E8\u5206\uFF1A", M.timeLabel(row.partial_planned_finish), "\uFF0C\u975E\u5168\u6279\u5B8C\u5DE5")), /*#__PURE__*/React.createElement("td", null, {
      overdue: '预计超期',
      on_time: '预计按期',
      unknown: '暂无数据'
    }[row.risk], /*#__PURE__*/React.createElement("small", null, M.number(row.delay_hours), " \u5C0F\u65F6")), /*#__PURE__*/React.createElement("td", null, row.last_operations.map(task => /*#__PURE__*/React.createElement(Button, {
      key: task.row_ref,
      icon: "search",
      className: "mini",
      onClick: () => onLast(task),
      "aria-label": '定位末端工序 ' + row.batch_id + ' ' + task.sequence + (task.piece_id ? ' ' + task.piece_id : '')
    }, M.number(task.sequence), " ", task.process_label || '工序未记录', task.piece_id && ' · ' + task.piece_id)), row.issues.map((code, index) => /*#__PURE__*/React.createElement("small", {
      key: index
    }, reasons[code] || '排产时依据不完整，交付结论待确认'))))), !data.items.length && /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("td", {
      colSpan: 6
    }, data.items_complete ? '当前读取范围没有批次。' : '交付依据未完整记录，不能认定为零风险。'))))), /*#__PURE__*/React.createElement(Pager, {
      page: current,
      pages: pages,
      onPage: setPage,
      label: "\u5019\u9009\u4EA4\u4ED8\u98CE\u9669"
    }));
  }
  window.RunCandidateControls = {
    Button,
    Icon,
    ErrorBox,
    Reasons,
    Pager,
    Metric,
    Status,
    Catalog,
    Generation,
    Detail,
    Delivery,
    Styles
  };
})();
