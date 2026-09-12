(function () {
  'use strict';

  const labels = {
    actual_start: '实际开工',
    actual_end: '本次实际结束',
    completed_quantity: '本次完成数量',
    quantity_done: '旧登记数量',
    effective_processing_hours: '有效加工工时',
    remark: '备注',
    event_type: '事件类型',
    event_time: '事件时间',
    event_label: '事件名称',
    recorded_at: '登记时间',
    recorded_at_time_basis: '登记时间口径',
    source: '来源',
    local_operator: '登记人员',
    declared_operator: '声明人员',
    raw_values: '原存储字段',
    evidence: '来源证据',
    message: '说明',
    reason: '原因',
    event_time_basis: '事件时间口径',
    raw_event_time: '原存储事件时间',
    legacy_fact_ref: '旧事实编号',
    operation_ref: '工序编号',
    actual_machine_ref: '设备编号',
    actual_operator_ref: '人员编号',
    task_ref: '任务编号',
    receipt_ref: '回执编号',
    revision_ref: '修订编号',
    snapshot_ref: '范围快照',
    recorded_against_plan_ref: '原计划编号',
    recorded_against_task_ref: '原任务编号',
    report_ref: '报工编号',
    machine_label: '设备',
    operator_label: '人员',
    code: '原因代码',
    rule: '规则',
    rule_code: '规则代码',
    diagnostic_code: '诊断代码',
    request_key: '请求编号',
    fields: '字段',
    original_values: '原始值'
  };
  const diagnosticFields = new Set(['code', 'rule', 'rule_code', 'diagnostic_code', 'request_key']);
  const businessTextFields = new Set(['part_no', 'remark', 'message', 'reason', 'description', 'source', 'event_type', 'created_by', 'local_operator', 'declared_operator', 'quantity_done']);
  function referenceField(key, value) {
    if (diagnosticFields.has(key) || /(?:_ref|_refs|_snapshot)$/.test(key)) return true;
    const business = businessTextFields.has(key) || /(?:_code|_label|_name|_no|_quantity|_hours|_minutes)$/.test(key);
    return !business && typeof value === 'string' && /^[0-9a-f]{32,}$/i.test(value);
  }
  const noFeedback = summary => !!summary && summary.records === 0;
  function actualValue(value, empty, missing = '未知') {
    if (value === null || value === undefined) return empty ? /*#__PURE__*/React.createElement("span", {
      className: "rw-no-feedback-value",
      "aria-label": "\u6682\u65E0\u73B0\u573A\u6570\u636E"
    }, "\u2014") : missing;
    return String(value);
  }
  function StructuredFacts({
    value,
    field = ''
  }) {
    if (value === null || value === undefined) return '未知';
    if (typeof value === 'boolean') return value ? '是' : '否';
    if (typeof value !== 'object') return referenceField(field, value) ? /*#__PURE__*/React.createElement(window.WorkbenchReference, {
      value: value,
      label: labels[field] || '编号'
    }) : String(value);
    if (Array.isArray(value)) return value.length ? /*#__PURE__*/React.createElement("ul", {
      className: "rw-evidence-list"
    }, value.map((item, index) => /*#__PURE__*/React.createElement("li", {
      key: index
    }, StructuredFacts({
      value: item,
      field
    })))) : '无';
    const entries = Object.entries(value),
      refs = {},
      visible = [];
    entries.forEach(([key, item]) => {
      if (referenceField(key, item)) refs[labels[key] || key] = item;else visible.push([key, item]);
    });
    return /*#__PURE__*/React.createElement("div", {
      className: "rw-evidence-facts"
    }, /*#__PURE__*/React.createElement("dl", null, visible.map(([key, item]) => /*#__PURE__*/React.createElement(React.Fragment, {
      key: key
    }, /*#__PURE__*/React.createElement("dt", null, labels[key] || key), /*#__PURE__*/React.createElement("dd", null, StructuredFacts({
      value: item,
      field: key
    }))))), !!Object.keys(refs).length && /*#__PURE__*/React.createElement(window.WorkbenchReference, {
      entries: refs
    }));
  }
  function NoFeedback({
    summary
  }) {
    return noFeedback(summary) ? /*#__PURE__*/React.createElement("p", {
      className: "rw-no-feedback",
      role: "status"
    }, "\u5F53\u524D\u8303\u56F4\u6682\u65E0\u73B0\u573A\u6570\u636E\u3002\u5B9E\u9645\u503C\u4EE5\u201C\u2014\u201D\u8868\u793A\uFF1B\u8BA1\u5212\u503C\u4E0E\u5DF2\u77E5\u7684 0 \u4FDD\u7559\u3002\u6682\u65E0\u53CD\u9988\u4E0D\u7B49\u4E8E\u5C1A\u672A\u751F\u4EA7\u3002") : null;
  }
  function TableFrame({
    caption,
    children,
    className = '',
    actionColumn = -1,
    ...props
  }) {
    const frame = React.useRef(null);
    React.useLayoutEffect(() => {
      const table = frame.current.querySelector('table');
      if (!table) return;
      const heading = table.caption || table.createCaption();
      heading.className = 'wb-visually-hidden';
      heading.textContent = caption;
      table.querySelectorAll('thead th').forEach(cell => cell.setAttribute('scope', 'col'));
      table.querySelectorAll('tr').forEach(row => {
        Array.from(row.cells).forEach((cell, index) => {
          cell.classList.toggle('rw-fixed-action', index === actionColumn);
          cell.classList.toggle('rw-fixed-key', actionColumn >= 0 && index === 0);
        });
      });
    });
    return /*#__PURE__*/React.createElement("div", {
      ...props,
      ref: frame,
      className: 'rw-table-scroll wb-table-frame ' + className
    }, children);
  }
  window.ReportEvidence = {
    StructuredFacts,
    NoFeedback,
    noFeedback,
    actualValue,
    TableFrame
  };
})();
