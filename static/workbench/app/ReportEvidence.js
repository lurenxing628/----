(function () {
  'use strict';

  const labels = {
    actual_start: '实际开工',
    actual_end: '本次实际结束',
    completed_quantity: '本次完成数量',
    quantity_done: '登记数量',
    effective_processing_hours: '有效加工工时',
    remark: '备注',
    event_type: '记录类型',
    event_time: '记录时间',
    event_label: '记录名称',
    recorded_at: '登记时间',
    recorded_at_time_basis: '登记时间说明',
    source: '来源',
    local_operator: '记录人',
    declared_operator: '经办人',
    raw_values: '原存储内容',
    evidence: '来源记录',
    message: '说明',
    reason: '原因',
    event_time_basis: '记录时间说明',
    raw_event_time: '原存储记录时间',
    legacy_fact_ref: '历史记录编号',
    operation_ref: '工序编号',
    actual_machine_ref: '设备编号',
    actual_operator_ref: '人员编号',
    task_ref: '任务编号',
    receipt_ref: '结果编号',
    revision_ref: '版本编号',
    snapshot_ref: '数据版本编号',
    recorded_against_plan_ref: '原计划编号',
    recorded_against_task_ref: '原任务编号',
    report_ref: '报工编号',
    machine_label: '设备',
    operator_label: '人员',
    code: '原因代码',
    rule: '规则',
    rule_code: '规则代码',
    diagnostic_code: '诊断代码',
    request_key: '操作编号',
    fields: '相关项',
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
  // 历史现场记录（legacy_evidence）只展示登记过中文名的项，值里的英文代号换成说法，
  // 和后端 core/models/operation_execution_labels.py、report/review_records.py 同一套叫法；
  // 编号类和没登记的项折叠进「编号」区，正文不再出现英文键名。
  const legacyCodes = {
    event_type: {
      start: '开工',
      finish: '整道完工',
      pause: '暂停',
      resume: '恢复',
      exception: '异常'
    },
    reported_status: {
      not_started: '待开工',
      processing: '生产中',
      paused: '已暂停',
      exception: '异常中',
      completed: '已完工'
    },
    reason_code: {
      equipment: '设备问题',
      person: '人员问题',
      material: '物料问题',
      quality: '质量问题',
      process: '工艺问题',
      external: '外协问题',
      other: '其他'
    },
    severity: {
      low: '轻微',
      medium: '一般',
      high: '严重',
      critical: '紧急'
    },
    handling_status: {
      new: '刚上报',
      checking: '处理中',
      waiting: '等待条件',
      handled: '已处理'
    }
  };
  const legacyFields = [['event_type', '记录类型'], ['reported_status', '登记状态'], ['event_time', '记录时间'], ['quantity_done', '登记数量'], ['quantity_scrapped', '报废数量'], ['reason_code', '异常原因'], ['reason_detail', '原因说明'], ['severity', '严重程度'], ['impact_minutes', '影响时长'], ['handling_status', '处理状态'], ['suggest_reschedule', '是否建议重新排程'], ['remark', '备注'], ['created_by', '记录人'], ['created_at', '登记时间']];
  // 这几项没填也要列出来，让人一眼看到这条记录缺什么；其余项只在有值时显示。
  const legacyAlways = new Set(['event_type', 'event_time', 'quantity_done', 'created_at']);
  const legacyReferences = {
    legacy_fact_ref: '历史记录编号',
    operation_ref: '工序编号',
    recorded_against_task_ref: '原任务编号',
    recorded_against_plan_ref: '原计划编号',
    actual_machine_ref: '设备编号',
    actual_operator_ref: '人员编号'
  };
  // 时间来源的内部标记由「登记时间」旁的说明代替；工时在历史记录里恒为空，不单独显示。
  const legacyInternal = new Set(['created_at_time_basis', 'created_at_default_basis', 'unavailable_fields', 'effective_processing_hours']);
  const blank = value => value === null || value === undefined || value === '';
  function legacyTime(value) {
    try {
      return window.WorkbenchFormat.dateTime(String(value), {
        seconds: true
      });
    } catch (_) {
      return String(value) + '（原始格式，无法换算）';
    }
  }
  function legacyText(key, value) {
    if (blank(value)) return key === 'event_time' ? '未知' : '未填写';
    if (legacyCodes[key]) return legacyCodes[key][String(value).trim()] || (key === 'event_type' ? '执行事件' : '未识别');
    if (key === 'event_time') return legacyTime(value);
    if (key === 'created_at') return String(value) + '（历史系统导入的原始时间）';
    if (key === 'impact_minutes') return typeof value === 'number' ? window.WorkbenchFormat.number(value, {
      digits: 0
    }) + ' 分钟' : String(value);
    if (key === 'suggest_reschedule') {
      const flag = String(value).trim().toLowerCase();
      return ['1', 'yes', 'true'].includes(flag) ? '建议重新排程' : ['0', 'no', 'false'].includes(flag) ? '暂不建议重新排程' : '暂不清楚是否需要重新排程';
    }
    return typeof value === 'boolean' ? value ? '是' : '否' : String(value);
  }
  function LegacyRecord({
    value
  }) {
    if (value === null || typeof value !== 'object' || Array.isArray(value)) return /*#__PURE__*/React.createElement(StructuredFacts, {
      value: value
    });
    const refs = {},
      shown = legacyFields.filter(([key]) => legacyAlways.has(key) || !blank(value[key]));
    Object.entries(value).forEach(([key, item]) => {
      if (legacyInternal.has(key) || legacyFields.some(([field]) => field === key) || blank(item)) return;
      refs[legacyReferences[key] || '原始项 ' + key] = typeof item === 'object' ? JSON.stringify(item) : item;
    });
    const unavailable = Array.isArray(value.unavailable_fields) ? value.unavailable_fields : [];
    unavailable.forEach((item, index) => {
      refs['无法显示的项 ' + (index + 1)] = item && item.field ? item.field : String(item);
    });
    return /*#__PURE__*/React.createElement("div", {
      className: "rw-evidence-facts rw-legacy-record"
    }, /*#__PURE__*/React.createElement("dl", null, shown.map(([key, label]) => /*#__PURE__*/React.createElement(React.Fragment, {
      key: key
    }, /*#__PURE__*/React.createElement("dt", null, label), /*#__PURE__*/React.createElement("dd", null, legacyText(key, value[key]))))), !!unavailable.length && /*#__PURE__*/React.createElement("p", {
      className: "rw-muted"
    }, "\u6709 ", unavailable.length, " \u9879\u539F\u503C\u7684\u683C\u5F0F\u65E0\u6CD5\u663E\u793A\uFF0C\u539F\u503C\u5DF2\u4FDD\u7559\u3002"), !!Object.keys(refs).length && /*#__PURE__*/React.createElement(window.WorkbenchReference, {
      entries: refs
    }));
  }
  function NoFeedback({
    summary
  }) {
    return noFeedback(summary) ? /*#__PURE__*/React.createElement("p", {
      className: "rw-no-feedback",
      role: "status"
    }, "\u5F53\u524D\u8303\u56F4\u6682\u65E0\u62A5\u5DE5\u8BB0\u5F55\u3002") : null;
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
    LegacyRecord,
    NoFeedback,
    noFeedback,
    actualValue,
    TableFrame,
    legacyText
  };
})();
