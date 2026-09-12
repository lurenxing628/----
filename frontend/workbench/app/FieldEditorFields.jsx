(function () {
  'use strict';
  const C = window.FieldContract, { Button } = window.FieldControls;
  function FieldEditorFields({ task, record, legacy, action, adapter, draft, suggestions, disabled, first, change, error }) {
    const Field = window.ResourceControls.Field;
    const readonly = key => disabled || action === 'supplement' && record[key] !== null && record[key] !== '';
    const choices = (key, label, kind) => <window.ResourceControls.Choice adapter={adapter} field={{ key, label, kind }} value={draft[key]} disabled={readonly(key)} error={error}
      original={record ? { relationships: { [key]: record[key], [key.replace('_ref', '_label')]: record[key.replace('_ref', '_label')] } } : null} onChange={value => change(key, value)} />;
    const amount = value => value !== '' && Number.isFinite(Number(value)) ? Number(value) : null;
    const quantity = amount(draft.completed_quantity), effectiveHours = amount(draft.effective_processing_hours);
    const previousQuantity = record && record.completed_quantity !== null ? record.completed_quantity : 0;
    const cumulative = quantity === null || !Number.isSafeInteger(quantity) || quantity < 0 || task.execution.known_completed_quantity === null ? null
      : task.execution.known_completed_quantity - previousQuantity + quantity;
    const start = draft.actual_start ? Date.parse(draft.actual_start + 'Z') : NaN, end = draft.actual_end ? Date.parse(draft.actual_end + 'Z') : NaN;
    const span = Number.isFinite(start) && Number.isFinite(end) && end >= start ? (end - start) / 3600000 : null;
    const difference = span !== null && effectiveHours !== null ? span - effectiveHours : null;
    // Span and difference are checked against entered hours; keep up to three decimals instead of a one-decimal summary.
    const hours = value => window.WorkbenchFormat.hours(value, { digits: 3, trim: true });
    const timeHints = Object.keys(suggestions).length > 0;
    return <><div className="field-entry-grid">
      <section><h4>产出数量</h4><Field label="本次完成数量" path="completed_quantity" error={error}><input ref={first} type="number" min="0" step="1" aria-label="本次完成数量" value={draft.completed_quantity} disabled={readonly('completed_quantity')} onChange={event => change('completed_quantity', event.target.value)} /></Field>
        <div className="field-quantity-tools"><span>件</span><Button disabled={readonly('completed_quantity')} onClick={() => change('completed_quantity', '0')}>最小</Button>
          {action === 'create' && <Button disabled={disabled || task.execution.remaining_quantity === null} onClick={() => change('completed_quantity', String(task.execution.remaining_quantity))}>最大</Button>}</div>
        <p className="field-note">已知累计预览 <output aria-label="已知累计预览">{cumulative === null ? '未核对' : cumulative}</output> / 执行目标 {C.quantity(task.execution.target_quantity)} 件
          {task.execution.unknown_record_count > 0 && <small> · 原记录数量待补 {task.execution.unknown_record_count} 条</small>}</p></section>
      <section><h4>实际起止</h4>{timeHints && <p className="field-suggestion" role="status">以下时间为建议值，保存后将登记为实际记录。请核对；不确定时清空，保持未知。</p>}
        <div className="field-time-grid">{[['actual_start', '实际开工'], ['actual_end', '本次实际完工']].map(([key, label]) => <div key={key}>
          <Field label={label} path={key} error={error} hint={suggestions[key] ? '建议来源：' + suggestions[key] : undefined}><input type="datetime-local" step="1" aria-label={label} value={draft[key]} disabled={readonly(key)} onChange={event => change(key, event.target.value)} /></Field>
          <Button disabled={readonly(key) || !draft[key]} aria-label={'清空' + label} onClick={() => change(key, '')}>清空，记为未知</Button></div>)}</div></section>
      <section><h4>工时核对</h4><Field label="有效工时 (h)" path="effective_processing_hours" error={error}><input type="number" min="0" step="any" data-wb-step="0.1" aria-label="有效工时 (h)" value={draft.effective_processing_hours} disabled={readonly('effective_processing_hours')} onChange={event => change('effective_processing_hours', event.target.value)} /></Field>
        <p className="field-note">作业跨度 <output aria-label="作业跨度">{hours(span)}</output></p>
        <p className={'field-note' + (difference !== null && difference < 0 ? ' field-hours-warning' : '')}>工时差额 <output aria-label="工时差额">{hours(difference)}</output></p></section>
    </div>
    <details open={action !== 'create' || !!legacy}><summary>实际设备 / 人员 / 备注{record || legacy ? ' / 原因' : ''}</summary><div className="field-extra">
      {choices('actual_machine_ref', '实际设备', 'machine')}{choices('actual_operator_ref', '实际人员', 'operator')}
      <Field label="作业备注" path="remark" error={error}><textarea aria-label="作业备注" maxLength="2000" value={draft.remark} disabled={readonly('remark')} onChange={event => change('remark', event.target.value)} /></Field>
      {(record || legacy) && <Field label={action === 'supplement' || legacy ? '补齐原因' : '更正原因'} path="reason" error={error} required><textarea required aria-label="补齐或更正原因" maxLength="2000" value={draft.reason} disabled={disabled} onChange={event => change('reason', event.target.value)} /></Field>}
      <Field label="现场声明人" path="declared_operator" error={error}><input aria-label="现场声明人" maxLength="2000" value={draft.declared_operator} disabled={disabled} onChange={event => change('declared_operator', event.target.value)} /></Field>
    </div></details></>;
  }
  window.FieldEditorFields = FieldEditorFields;
})();
