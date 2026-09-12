(function () {
  'use strict';
  const labels = {
    actual_start: '实际开工', actual_end: '本次实际结束', completed_quantity: '本次完成数量', quantity_done: '旧登记数量',
    effective_processing_hours: '有效加工工时', remark: '备注', event_type: '事件类型', event_time: '事件时间',
    event_label: '事件名称', recorded_at: '登记时间', recorded_at_time_basis: '登记时间口径', source: '来源',
    local_operator: '登记人员', declared_operator: '声明人员', raw_values: '原存储字段', evidence: '来源证据',
    message: '说明', reason: '原因', event_time_basis: '事件时间口径', raw_event_time: '原存储事件时间',
    legacy_fact_ref: '旧事实编号', operation_ref: '工序编号', actual_machine_ref: '设备编号', actual_operator_ref: '人员编号',
    task_ref: '任务编号', receipt_ref: '回执编号', revision_ref: '修订编号', snapshot_ref: '范围快照',
    recorded_against_plan_ref: '原计划编号', recorded_against_task_ref: '原任务编号', report_ref: '报工编号',
    machine_label: '设备', operator_label: '人员', code: '原因代码', rule: '规则', rule_code: '规则代码',
    diagnostic_code: '诊断代码', request_key: '请求编号', fields: '字段', original_values: '原始值'
  };
  const diagnosticFields = new Set(['code', 'rule', 'rule_code', 'diagnostic_code', 'request_key']);
  const businessTextFields = new Set(['part_no', 'remark', 'message', 'reason', 'description', 'source', 'event_type',
    'created_by', 'local_operator', 'declared_operator', 'quantity_done']);
  function referenceField(key, value) {
    if (diagnosticFields.has(key) || /(?:_ref|_refs|_snapshot)$/.test(key)) return true;
    const business = businessTextFields.has(key) || /(?:_code|_label|_name|_no|_quantity|_hours|_minutes)$/.test(key);
    return !business && typeof value === 'string' && /^[0-9a-f]{32,}$/i.test(value);
  }
  const noFeedback = summary => !!summary && summary.records === 0;
  function actualValue(value, empty, missing = '未知') {
    if (value === null || value === undefined) return empty ? <span className="rw-no-feedback-value" aria-label="暂无现场数据">—</span> : missing;
    return String(value);
  }
  function StructuredFacts({ value, field = '' }) {
    if (value === null || value === undefined) return '未知';
    if (typeof value === 'boolean') return value ? '是' : '否';
    if (typeof value !== 'object') return referenceField(field, value) ? <window.WorkbenchReference value={value} label={labels[field] || '编号'} /> : String(value);
    if (Array.isArray(value)) return value.length ? <ul className="rw-evidence-list">{value.map((item, index) => <li key={index}>{StructuredFacts({ value: item, field })}</li>)}</ul> : '无';
    const entries = Object.entries(value), refs = {}, visible = [];
    entries.forEach(([key, item]) => {
      if (referenceField(key, item)) refs[labels[key] || key] = item;
      else visible.push([key, item]);
    });
    return <div className="rw-evidence-facts"><dl>{visible.map(([key, item]) => <React.Fragment key={key}>
      <dt>{labels[key] || key}</dt><dd>{StructuredFacts({ value: item, field: key })}</dd>
    </React.Fragment>)}</dl>{!!Object.keys(refs).length && <window.WorkbenchReference entries={refs} />}</div>;
  }
  function NoFeedback({ summary }) {
    return noFeedback(summary) ? <p className="rw-no-feedback" role="status">当前范围暂无现场数据。实际值以“—”表示；计划值与已知的 0 保留。暂无反馈不等于尚未生产。</p> : null;
  }
  function TableFrame({ caption, children, className = '', actionColumn = -1, ...props }) {
    const frame = React.useRef(null);
    React.useLayoutEffect(() => {
      const table = frame.current.querySelector('table');
      if (!table) return;
      const heading = table.caption || table.createCaption();
      heading.className = 'wb-visually-hidden'; heading.textContent = caption;
      table.querySelectorAll('thead th').forEach(cell => cell.setAttribute('scope', 'col'));
      table.querySelectorAll('tr').forEach(row => {
        Array.from(row.cells).forEach((cell, index) => {
          cell.classList.toggle('rw-fixed-action', index === actionColumn);
          cell.classList.toggle('rw-fixed-key', actionColumn >= 0 && index === 0);
        });
      });
    });
    return <div {...props} ref={frame} className={'rw-table-scroll wb-table-frame ' + className}>{children}</div>;
  }
  window.ReportEvidence = { StructuredFacts, NoFeedback, noFeedback, actualValue, TableFrame };
})();
