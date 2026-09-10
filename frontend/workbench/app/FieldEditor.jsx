(function () {
  'use strict';
  const C = window.FieldContract, { Button, ErrorBox, Feedback } = window.FieldControls;
  function FieldEditor({ task, record, legacy, action, adapter, command, retained, onDraft, onClose, onDone }) {
    const [draft, setDraft] = React.useState(() => {
      if (retained) return { ...retained.draft };
      const value = C.draft(record);
      if (legacy) { value.actual_end = legacy.event_time.replace(' ', 'T'); value.completed_quantity = legacy.quantity_done === null ? '' : String(legacy.quantity_done); }
      return value;
    }), [error, setError] = React.useState(null);
    const currentBaseline = { task_ref: task.task_ref, plan_ref: task.plan_ref, report_ref: record ? record.report_ref : null,
      revision_ref: record ? record.revision_ref : null, legacy_ref: legacy ? legacy.legacy_fact_ref : null };
    const [baseline] = React.useState(() => retained ? retained.baseline : currentBaseline);
    const changed = JSON.stringify(baseline) !== JSON.stringify(currentBaseline);
    React.useLayoutEffect(() => { if (typeof onDraft === 'function') onDraft({ draft, baseline }); }, [draft, baseline, onDraft]);
    const form = React.useRef(null), first = React.useRef(null), title = legacy ? '补齐原始完工记录' : action === 'create' ? '本次报工' : action === 'supplement' ? '补齐本次报工' : '更正报工';
    const context = record ? record.write_context : task.execution.write_context;
    const disabled = command.locked || command.phase === 'done' || changed;
    const reason = changed ? '原记录或任务已变化，暂存内容未写入；请取消后重新核对。' : C.blocked(context, action);
    React.useEffect(() => { first.current.focus({ preventScroll: true }); }, []);
    function change(key, value) { setDraft(current => ({ ...current, [key]: value })); setError(null); }
    async function save(value) {
      if (disabled || reason) return;
      try {
        if (!form.current.reportValidity()) return;
        const input = C.input(value, record, action);
        if (legacy) {
          if (!value.reason.trim()) throw window.APSResourceContract.failure('请填写旧完工事实的补齐原因。');
          input.legacy_fact_ref = legacy.legacy_fact_ref; input.reason = value.reason.trim();
        }
        setError(null);
        await command.submit('execution', action, record ? record.report_ref : task.task_ref, context, input);
      } catch (error) { setError(error); }
    }
    const readonly = key => disabled || action === 'supplement' && record[key] !== null && record[key] !== '';
    const choices = (key, label, kind) => <window.ResourceControls.Choice adapter={adapter} field={{ key, label, kind }} value={draft[key]} disabled={readonly(key)}
      original={record ? { relationships: { [key]: record[key], [key.replace('_ref', '_label')]: record[key.replace('_ref', '_label')] } } : null} onChange={value => change(key, value)} />;
    const remaining = task.execution.remaining_quantity;
    const amount = value => value !== '' && Number.isFinite(Number(value)) ? Number(value) : null;
    const quantity = amount(draft.completed_quantity), effectiveHours = amount(draft.effective_processing_hours);
    const previousQuantity = record && record.completed_quantity !== null ? record.completed_quantity : 0;
    const cumulative = quantity === null || !Number.isSafeInteger(quantity) || quantity < 0 || task.execution.known_completed_quantity === null ? null
      : task.execution.known_completed_quantity - previousQuantity + quantity;
    const start = draft.actual_start ? Date.parse(draft.actual_start + 'Z') : NaN;
    const end = draft.actual_end ? Date.parse(draft.actual_end + 'Z') : NaN;
    const span = Number.isFinite(start) && Number.isFinite(end) && end >= start ? (end - start) / 3600000 : null;
    const difference = span !== null && effectiveHours !== null ? span - effectiveHours : null;
    const displayHours = value => value === null ? '未核对' : Math.round(value * 1000) / 1000 + ' h';
    return <form ref={form} className="field-editor" aria-label={title} onSubmit={event => { event.preventDefault(); save(draft); }}>
      <h3>{title}{record ? ' · ' + record.report_no : ''}</h3>
      <div className="field-entry-grid">
        <section><h4>产出数量</h4><label>本次完成数量<input ref={first} type="number" min="0" step="1" aria-label="本次完成数量" value={draft.completed_quantity} disabled={readonly('completed_quantity')} onChange={event => change('completed_quantity', event.target.value)} /></label>
          <div className="field-quantity-tools"><span>件</span><Button disabled={readonly('completed_quantity')} onClick={() => change('completed_quantity', '0')}>最小</Button>
            {action === 'create' && <Button disabled={disabled || remaining === null} onClick={() => change('completed_quantity', String(remaining))}>最大</Button>}</div>
          <p className="field-note">已知累计预览 <output aria-label="已知累计预览">{cumulative === null ? '未核对' : cumulative}</output> / 执行目标 {C.quantity(task.execution.target_quantity)} 件
            {task.execution.unknown_record_count > 0 && <small> · 原记录数量待补 {task.execution.unknown_record_count} 条</small>}</p></section>
        <section><h4>实际起止</h4><div className="field-time-grid">{[['actual_start', '实际开工'], ['actual_end', '本次实际完工']].map(([key, label]) => <label key={key}>{label}<input type="datetime-local" step="60" aria-label={label} value={draft[key]} disabled={readonly(key)} onChange={event => change(key, event.target.value)} /></label>)}</div></section>
        <section><h4>工时核对</h4><label>有效工时 (h)<input type="number" min="0" step="any" data-wb-step="0.1" aria-label="有效工时 (h)" value={draft.effective_processing_hours} disabled={readonly('effective_processing_hours')} onChange={event => change('effective_processing_hours', event.target.value)} /></label>
          <p className="field-note">作业跨度 <output aria-label="作业跨度">{displayHours(span)}</output></p>
          <p className="field-note" style={difference !== null && difference < 0 ? { color: 'var(--ui-danger-text)' } : undefined}>工时差额 <output aria-label="工时差额">{displayHours(difference)}</output></p></section>
      </div>
      <details open={action !== 'create' || !!legacy}><summary>实际设备 / 人员 / 备注{record || legacy ? ' / 原因' : ''}</summary><div className="field-extra">
        {choices('actual_machine_ref', '实际设备', 'machine')}{choices('actual_operator_ref', '实际人员', 'operator')}
        <label>作业备注<textarea aria-label="作业备注" maxLength="2000" value={draft.remark} disabled={readonly('remark')} onChange={event => change('remark', event.target.value)} /></label>
        {(record || legacy) && <label>{action === 'supplement' || legacy ? '补齐原因' : '更正原因'}<textarea required aria-label="补齐或更正原因" maxLength="2000" value={draft.reason} disabled={disabled} onChange={event => change('reason', event.target.value)} /></label>}
        <label>现场声明人<input aria-label="现场声明人" maxLength="2000" value={draft.declared_operator} disabled={disabled} onChange={event => change('declared_operator', event.target.value)} /></label>
      </div></details>
      <ErrorBox error={error} /><Feedback command={command} onDone={onDone} />{reason && <p role="status">{reason}</p>}
      <div className="field-footer"><Button onClick={onClose} disabled={command.locked}>取消</Button>
        {action === 'create' && !legacy && <Button icon="check-check" disabled={disabled || remaining === null || !!reason} onClick={() => { const value = { ...draft, completed_quantity: String(remaining) }; setDraft(value); save(value); }}>剩余全部完工</Button>}
        <Button type="submit" icon="check" className="btn primary" busy={disabled} reason={reason}>{action === 'correct' ? '保存更正' : '保存报工'}</Button></div>
    </form>;
  }
  window.FieldEditor = FieldEditor;
})();
