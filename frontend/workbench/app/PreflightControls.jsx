(function () {
  'use strict';
  const { Button, ErrorBox } = window.ResourceControls;
  function Segment({ label, value, choices, onChange, disabled }) {
    const id = React.useId();
    return <div className="pf-segment" role="radiogroup" aria-label={label}>{choices.map(([key, text, unavailable]) => <label key={String(key)} className={value === key ? 'selected' : ''}>
      <input type="radio" name={id} checked={value === key} disabled={disabled || unavailable} onChange={() => onChange(key)} /><span>{text}</span>
    </label>)}</div>;
  }
  function Rules({ value, onChange, disabled }) {
    return <section aria-labelledby="pf-rules-title"><h3 id="pf-rules-title">本次排产规则</h3><div className="pf-rows">
      <div className="pf-rule"><strong>齐套检查</strong><Segment label="齐套检查" value={value.ready_check} choices={[[true, '开启'], [false, '关闭']]} disabled={disabled} onChange={ready_check => onChange({ ready_check })} /></div>
      <div className="pf-rule"><strong>缺资源工序</strong><Segment label="缺资源工序" value={value.missing_resource_policy} choices={[["auto_assign", '自动分配'], ['exclude', '暂不排']]} disabled={disabled} onChange={missing_resource_policy => onChange({ missing_resource_policy })} /></div>
      <div className="pf-rule"><span className="pf-fixed">已开工工序：保留记录（不可修改）</span></div>
      <div className="pf-rule pf-note">本次参数，不改全局配置。工时、工种、外协资料仍为必填项；已开工和已完工的工序不能解除保护。</div>
    </div></section>;
  }
  function Metrics({ counts }) {
    const items = [['selected_tasks', '范围内工序'], ['ready_tasks', '资料有效'], ['auto_assign_required', '自动分配待补'], ['skipped_tasks', '本次跳过'], ['blocked_tasks', '缺资料工序'], ['no_route_batches', '未生成工艺批次'], ['actual_fact_tasks', '已开工工序']];
    return <dl className="pf-metrics">{items.map(([key, label]) => <div key={key}><dt>{label}</dt><dd>{counts ? counts[key] : '未检查'}</dd></div>)}</dl>;
  }
  function Reasons({ data }) {
    const groups = new Map(), tasks = new Map(data.tasks.map(row => [row.operation_ref, row]));
    const batches = new Map(data.included_batches.concat(data.excluded_batches).map(row => [row.batch_ref, row.batch_id]));
    data.run_blocked_reasons.concat(data.warnings).forEach(item => {
      if (!groups.has(item.code)) groups.set(item.code, []);
      groups.get(item.code).push(item);
    });
    function summary(code, items) {
      const operations = new Set(items.map(item => item.operation_ref).filter(Boolean)).size;
      const messages = Array.from(new Set(items.map(item => item.message))).join('；');
      if (operations && code === 'operation_blocked') return operations + '道工序缺必填资料';
      if (operations && code === 'execution_review_required') return operations + '道工序已有执行记录待核对';
      if (code === 'route_not_generated') return new Set(items.map(item => item.batch_ref).filter(Boolean)).size + '批尚未生成工艺';
      return (operations ? operations + '道工序：' : '') + messages;
    }
    function objectLabel(item) {
      const task = tasks.get(item.operation_ref);
      if (task) return task.batch_id + ' · ' + task.sequence + ' ' + task.label + (task.piece_id ? ' · ' + task.piece_id : '');
      return item.batch_id || batches.get(item.batch_ref) || '批次与工序未读取';
    }
    return <div className="pf-alert"><div role="status">{Array.from(groups, ([code, items]) => <div key={code} data-reason-group={code}>{summary(code, items)}</div>)}</div>
      <details className="pf-reasons"><summary>原因明细 · {data.run_blocked_reasons.length + data.warnings.length} 项</summary>
        <div className="pf-reason-list">{Array.from(groups, ([code, items]) => <div key={code}>{items.map((item, index) => <div className="pf-reason-item" key={index}
          data-reason-code={item.code} data-operation-ref={item.operation_ref} data-batch-ref={item.batch_ref}>
          {objectLabel(item) && <strong>{objectLabel(item)}： </strong>}{item.message}<window.WorkbenchReference entries={{ '原因编号': item.code, '工序编号': item.operation_ref, '批次编号': item.batch_ref }} /></div>)}</div>)}</div>
      </details></div>;
  }
  function Styles() {
    return null;
  }
  window.PreflightControls = { Button, ErrorBox, Rules, Metrics, Reasons, Styles };
})();
