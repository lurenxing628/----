(function () {
  'use strict';
  const { Button, ErrorBox } = window.ResourceControls;
  function Segment({ label, value, choices, onChange, disabled }) {
    const id = React.useId();
    return <div className="pf-segment" role="radiogroup" aria-label={label}>{choices.map(([key, text, unavailable]) => <label key={String(key)} className={value === key ? 'selected' : ''}>
      <input type="radio" name={id} checked={value === key} disabled={disabled || unavailable} onChange={() => onChange(key)} /><span>{text}</span>
    </label>)}</div>;
  }
  function MaterialRules({ value, onChange, disabled }) {
    const id = React.useId(), T = window.WorkbenchTerms, unavailable = disabled || !value.ready_check;
    return <fieldset className="pf-material-rules" disabled={unavailable}><legend>物料齐套规则</legend>
      <div className="pf-material-choices">{['strict', 'stage'].map(strategy => <label key={strategy} className={'pf-material-choice' + (value.material_strategy === strategy ? ' selected' : '')}>
        <input type="radio" name={id} checked={value.material_strategy === strategy} disabled={unavailable} aria-describedby={id + '-' + strategy}
          onChange={() => onChange({ material_strategy: strategy })} />
        <span><strong>{T.material_strategies[strategy]}</strong><small id={id + '-' + strategy}>{T.material_descriptions[strategy]}</small></span>
      </label>)}</div>
    </fieldset>;
  }
  // 不重排时段：没动过时不带这一项（按交付设置），检查后用本次生效的时段填显示值；改任一端就按本次单独填的发送，点「不设」发送 null。
  function HoldWindow({ value, effective, onChange, disabled }) {
    const C = window.PreflightContract, explicit = value.hold_window !== undefined;
    const shown = explicit ? value.hold_window : effective ? effective.hold_window : null, bounds = C.holdBounds(value.start_date, value.end_date) || {};
    let problem = '';
    if (explicit) { try { C.holdWindow(value.hold_window, value.start_date, value.end_date); } catch (error) { problem = error.message; } }
    const status = explicit ? value.hold_window === null ? '本次不设' : '本次单独填写' : effective ? effective.hold_window ? '（按交付设置）' : '（按交付设置：不设）' : '未填时按交付设置，检查后显示本次生效的时段';
    function edit(key, text) {
      // 按交付设置推算的时段可能超出这次的排产日期：只改一端时，带过来的另一端先截到日期范围内，免得没动过的一端报错。
      const base = { ...(shown || { start: '', end: '' }) };
      if (!explicit && shown && bounds.min && base.start < bounds.min) base.start = bounds.min;
      if (!explicit && shown && bounds.max && base.end > bounds.max) base.end = bounds.max;
      onChange({ hold_window: { ...base, [key]: text } });
    }
    return <><div className="pf-rule pf-hold" role="group" aria-label="不重排时段">
      <div className="pf-hold-head"><strong>不重排时段</strong><span className="pf-muted" data-hold-source={explicit ? 'explicit' : effective ? 'default' : 'unchecked'}>{status}</span></div>
      <div className="pf-hold-fields">{[['start', '开始'], ['end', '结束']].map(([key, label]) => <label key={key}>{label}
        <input type="datetime-local" aria-label={'不重排时段' + label} min={bounds.min} max={bounds.max} value={shown ? shown[key] : ''} disabled={disabled} aria-invalid={!!problem || undefined} onChange={event => edit(key, event.target.value)} /></label>)}
        <Button icon="x" disabled={disabled || explicit && value.hold_window === null} onClick={() => onChange({ hold_window: null })}>不设</Button>
        {explicit && <Button icon="rotate-ccw" disabled={disabled} onClick={() => onChange({ hold_window: undefined })}>按交付设置</Button>}</div></div>
      <div className="pf-rule pf-note">甘特图上落在这段时间里的工序保持原安排不动，同批次排在前面的工序也一起不动；其余照常重排。</div>
      {problem && <div className="pf-rule pf-note pf-hold-error" role="alert">{problem}</div>}</>;
  }
  const minuteText = value => window.WorkbenchFormat.dateTime(value);
  function HeldRows({ rows, label }) {
    const [page, setPage] = React.useState(1), pages = Math.max(1, Math.ceil(rows.length / 100));
    return <div className="pf-held-group"><strong>{label} · {rows.length} 道</strong><ul>{rows.slice((page - 1) * 100, page * 100).map(row => <li key={row.operation_ref} data-held-basis={row.held.basis}>
      {row.batch_id} · {row.sequence} {row.label}{row.piece_id ? ' · ' + row.piece_id : ''} · 原安排 {minuteText(row.held.start)} 至 {minuteText(row.held.end)}</li>)}</ul>
      {pages > 1 && <window.WorkbenchListControls.Pager page={page} pages={pages} total={rows.length} size={100} unit="道" label={label} onPage={setPage} />}</div>;
  }
  // 检查结果里的“本次不重排”一行；明细列出因不重排时段保持原安排的工序。
  function HoldSummary({ data }) {
    const span = data.effective_config.hold_window, kept = data.tasks.filter(row => row.held);
    const text = span ? '本次不重排：' + window.WorkbenchTerms.hold_window(span) + '，共 ' + data.counts.hold_window_tasks + ' 道工序保持原安排' : '本次不设不重排时段';
    const source = data.effective_config.hold_window_source === 'default' ? '（按交付设置）' : '';
    if (!kept.length) return <p className="pf-hold-summary" data-hold-summary role="status">{text}{source}</p>;
    return <details className="pf-detail pf-hold-summary" data-hold-summary><summary>{text}{source} · 查看明细</summary>
      <HeldRows rows={kept} label="不重排时段内保持原安排" /></details>;
  }
  function Rules({ value, effective, onChange, disabled, onInspectMaterials, splitExpanded, materialPanel }) {
    return <section aria-labelledby="pf-rules-title"><h3 id="pf-rules-title">本次排产规则</h3><div className="pf-rows">
      <div className="pf-rule"><strong>齐套检查</strong><Segment label="齐套检查" value={value.ready_check} choices={[[true, '开启'], [false, '关闭']]} disabled={disabled} onChange={ready_check => onChange({ ready_check, ...(ready_check ? {} : { material_strategy: 'strict' }) })} /></div>
      <MaterialRules value={value} onChange={onChange} disabled={disabled} />
      {!value.ready_check && <p className="pf-material-disabled">已关闭齐套检查，本次排产不按到料条件限制。</p>}
      <div className="pf-split-action"><div><strong>物料只够做一部分？</strong><p>先检查可做数量，确认后拆成两批。</p></div>
        <Button icon={splitExpanded ? 'chevron-up' : 'search'} disabled={disabled || !value.ready_check || !onInspectMaterials} aria-expanded={!!splitExpanded} aria-controls={splitExpanded ? 'pf-material-split' : undefined}
          onClick={onInspectMaterials}>{splitExpanded ? '收起数量检查' : '检查物料可做数量'}</Button></div>
      {materialPanel}
      <div className="pf-rule"><strong>缺资源工序</strong><Segment label="缺资源工序" value={value.missing_resource_policy} choices={[["auto_assign", '自动分配'], ['exclude', '暂不排']]} disabled={disabled} onChange={missing_resource_policy => onChange({ missing_resource_policy })} /></div>
      <HoldWindow value={value} effective={effective} onChange={onChange} disabled={disabled} />
      <div className="pf-rule"><span className="pf-fixed">已开工工序：保留记录（不可修改）</span></div>
      <div className="pf-rule pf-note">规则仅用于本次排产。</div>
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
      if (operations && code === 'operation_blocked') return operations + ' 道工序缺必填资料';
      if (operations && code === 'execution_review_required') return operations + ' 道工序已有执行记录待核对';
      if (code === 'route_not_generated') return new Set(items.map(item => item.batch_ref).filter(Boolean)).size + ' 批尚未生成工艺';
      return (operations ? operations + ' 道工序：' : '') + messages;
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
  window.PreflightControls = { Button, ErrorBox, Rules, Metrics, Reasons, HoldSummary };
})();
