(function () {
  'use strict';

  const F = window.WorkbenchFormat,
    {
      Issues
    } = window.ResourceControls;
  const labels = {
    plan_ref: '正式计划编号',
    batch_ref: '批次编号',
    task_ref: '安排编号',
    operation_ref: '工序编号',
    downtime_ref: '停机编号',
    source_ref: '来源编号',
    evidence_ref: '附件编号',
    kind: '来源类型',
    evaluation: '交付评估',
    requirements: '物料需求',
    label: '名称',
    business_code: '业务编号',
    required_quantity: '需求量',
    available_quantity: '可用量',
    unit: '单位',
    ready_status: '齐套状态',
    due_date: '交期',
    planned_finish: '计划完工',
    delay_days: '预计超期天数',
    planned_start: '正式安排开始',
    planned_end: '正式安排结束',
    first_actual_start: '首次实际开始',
    confirmed_finish: '确认完工时间',
    finish_deviation_minutes: '完工偏差（分钟）',
    overlap_hours: '停机重叠（小时）',
    delay_after_reschedule_hours: '重排后超期（小时）',
    execution_state: '执行状态',
    data_quality: '记录完整性',
    hours: '工时依据',
    effective_processing_hours: '有效加工小时',
    quota_processing_hours: '定额加工小时',
    overrun: '是否超耗',
    downtimes: '停机依据',
    reason: '原因',
    start: '开始',
    end: '结束',
    overlap_start: '重叠开始',
    overlap_end: '重叠结束',
    data_gaps: '数据缺口',
    code: '检查规则',
    message: '说明',
    receipt: '物流登记',
    state: '状态',
    status: '状态',
    source: '来源',
    as_of: '数据截至',
    recorded_at: '记录时间',
    quantity: '数量',
    risk: '风险判断',
    active: '当前是否存在',
    subject: '涉及记录',
    note: '备注',
    processing_hours: '加工小时',
    available: '是否可用',
    basis: '计算依据',
    setup_or_elapsed_hours_included: '是否包括准备或停留时间'
  };
  const values = {
    yes: '已齐套',
    no: '未齐套',
    partial: '部分完成',
    unreported: '待报工',
    started: '已开工',
    complete: '完整',
    paused: '已暂停',
    exception: '异常',
    incomplete: '尚不完整',
    invalid: '待核对',
    legacy: '旧记录需核对',
    available: '已读取',
    unknown: '未知',
    missing: '缺少来源',
    unavailable: '无法读取',
    on_time: '预计准时',
    overdue: '预计超期',
    complete_report_processing_hours_vs_operation_unit_hours_times_target: '完整报工加工工时与单件定额乘以目标数量对照'
  };
  // Only diagnostics and opaque references fold into the reference summary. Business identifiers such as
  // business_code or kind stay visible: 4.7 hides technical ids, not the information a planner acts on.
  const diagnosticKeys = new Set(['code', 'rule', 'rule_code', 'diagnostic_code', 'request_key']);
  const businessKey = key => /(?:_code|_label|_name|_no|_quantity|_hours|_minutes|_days)$/.test(key) || ['kind', 'label', 'unit', 'reason', 'message', 'note', 'subject', 'source', 'basis', 'state', 'status'].includes(key);
  function referenceField(key, item) {
    if (diagnosticKeys.has(key) || /(?:_ref|_refs|_key|_snapshot)$/.test(key)) return true;
    return !businessKey(key) && typeof item === 'string' && /^[0-9a-f]{32,}$/i.test(item);
  }
  function display(value) {
    if (value === null || value === undefined || value === '') return '未知';
    if (typeof value === 'boolean') return value ? '是' : '否';
    if (typeof value === 'number') return F.number(value, {
      digits: Number.isInteger(value) ? 0 : 2
    });
    if (/^\d{4}-\d\d-\d\d[T ]\d\d:\d\d/.test(value)) return F.dateTime(value);
    return values[value] || String(value);
  }
  function Structure({
    value,
    title
  }) {
    if (Array.isArray(value)) return value.length ? /*#__PURE__*/React.createElement("ol", {
      className: "dy-source-list"
    }, value.map((item, index) => /*#__PURE__*/React.createElement("li", {
      key: index
    }, /*#__PURE__*/React.createElement(Structure, {
      value: item
    })))) : /*#__PURE__*/React.createElement("span", null, "\u65E0\u8BB0\u5F55");
    if (!value || typeof value !== 'object') return /[a-f0-9]{32,}/i.test(String(value)) ? /*#__PURE__*/React.createElement(window.WorkbenchReference, {
      value: value
    }) : /*#__PURE__*/React.createElement("span", null, display(value));
    const refs = {},
      fields = [];
    Object.entries(value).forEach(([key, item]) => {
      if (referenceField(key, item)) refs[labels[key] || key] = item;else fields.push([key, item]);
    });
    return /*#__PURE__*/React.createElement(React.Fragment, null, title && /*#__PURE__*/React.createElement("h4", null, title), /*#__PURE__*/React.createElement("dl", {
      className: "dy-source-facts"
    }, fields.map(([key, item]) => /*#__PURE__*/React.createElement("div", {
      key: key
    }, /*#__PURE__*/React.createElement("dt", null, labels[key] || key), /*#__PURE__*/React.createElement("dd", null, /*#__PURE__*/React.createElement(Structure, {
      value: item
    }))))), Object.keys(refs).length > 0 && /*#__PURE__*/React.createElement(window.WorkbenchReference, {
      entries: refs
    }));
  }
  function Evidence({
    source
  }) {
    const e = source.evaluation;
    const timeline = Object.fromEntries(['planned_start', 'planned_end', 'first_actual_start', 'confirmed_finish', 'finish_deviation_minutes', 'overlap_hours', 'delay_after_reschedule_hours'].filter(key => Object.prototype.hasOwnProperty.call(source, key)).map(key => [key, source[key]]));
    return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(window.WorkbenchReference, {
      entries: {
        '正式计划编号': source.plan_ref,
        '批次编号': source.batch_ref
      }
    }), source.kind === 'outsourcing_receipt' && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("h4", null, "\u7269\u6D41\u767B\u8BB0\u8BB0\u5F55"), source.receipt && window.OutsourcingControls ? /*#__PURE__*/React.createElement("div", {
      className: "outsourcing-live"
    }, /*#__PURE__*/React.createElement(window.OutsourcingStyles, null), /*#__PURE__*/React.createElement(window.OutsourcingControls.Facts, {
      facts: source.receipt
    })) : /*#__PURE__*/React.createElement("div", {
      className: "dy-note warning"
    }, "\u8FD9\u6761\u7269\u6D41\u767B\u8BB0\u73B0\u5728\u8BFB\u4E0D\u5230\uFF0C\u53D1\u51FA\u548C\u56DE\u5382\u65F6\u95F4\u90FD\u6309\u672A\u77E5\u5904\u7406\u3002")), source.requirements && /*#__PURE__*/React.createElement(Structure, {
      title: "\u7269\u6599\u9700\u6C42",
      value: source.requirements
    }), e && /*#__PURE__*/React.createElement(Structure, {
      title: "\u4EA4\u4ED8\u8BC4\u4F30",
      value: e
    }), source.execution_state && /*#__PURE__*/React.createElement("div", {
      className: "dy-note"
    }, "\u6267\u884C\u72B6\u6001\uFF1A", display(source.execution_state), " \xB7 ", display(source.data_quality)), Object.keys(timeline).length > 0 && /*#__PURE__*/React.createElement(Structure, {
      title: "\u5B89\u6392\u4E0E\u6267\u884C\u65F6\u95F4",
      value: timeline
    }), source.hours && /*#__PURE__*/React.createElement(Structure, {
      title: "\u52A0\u5DE5\u5DE5\u65F6\u4F9D\u636E",
      value: source.hours
    }), source.downtimes && /*#__PURE__*/React.createElement(Structure, {
      title: "\u505C\u673A\u65F6\u6BB5\u4F9D\u636E",
      value: source.downtimes
    }), source.data_gaps && /*#__PURE__*/React.createElement(Issues, {
      issues: source.data_gaps
    }), /*#__PURE__*/React.createElement("details", {
      className: "dy-evidence"
    }, /*#__PURE__*/React.createElement("summary", null, "\u5B8C\u6574\u6765\u6E90\u4F9D\u636E"), /*#__PURE__*/React.createElement(Structure, {
      value: source
    })));
  }
  window.DashboardEvidence = {
    Evidence,
    Structure,
    display
  };
})();
