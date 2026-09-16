(function () {
  'use strict';
  const C = window.FieldContract, { Button, ErrorBox, Feedback } = window.FieldControls;
  function FieldVoidEditor({ task, record, adapter, command, retained, onDraft, onClose, onDone }) {
    const [draft, setDraft] = React.useState(() => retained ? retained.draft : { reason: '', declared_operator: '' });
    const [baseline] = React.useState(() => retained ? retained.baseline : { report_ref: record.report_ref, revision_ref: record.revision_ref });
    const [preview, setPreview] = React.useState(null), [error, setError] = React.useState(null), [reading, setReading] = React.useState(false);
    const form = React.useRef(null), inputRef = React.useRef(null), request = React.useRef(null);
    const changed = baseline.report_ref !== record.report_ref || baseline.revision_ref !== record.revision_ref;
    const locked = command.locked || command.phase === 'done' || reading || changed;
    React.useLayoutEffect(() => { if (onDraft) onDraft({ draft, baseline, dirty: !!(draft.reason || draft.declared_operator) }); }, [draft, baseline, onDraft]);
    React.useEffect(() => { form.current.scrollIntoView({ block: 'start', inline: 'nearest' }); inputRef.current.focus({ preventScroll: true }); return () => { if (request.current) request.current.abort(); }; }, []);
    React.useEffect(() => {
      if (command.phase !== 'done' || !['committed', 'unchanged'].includes(command.result.result)) return undefined;
      const timer = setTimeout(() => onDone({ taskRef: task.task_ref, operationRef: task.operation_ref }), 0);
      return () => clearTimeout(timer);
    }, [command.phase, command.result, task.task_ref, task.operation_ref, onDone]);
    const input = () => ({ original_revision_ref: baseline.revision_ref, reason: draft.reason.trim(), declared_operator: draft.declared_operator.trim() });
    function change(key, value) { setDraft(current => ({ ...current, [key]: value })); setPreview(null); setError(null); }
    async function inspect() {
      if (locked || !form.current.reportValidity()) return;
      const controller = new AbortController(); request.current = controller; setReading(true); setError(null);
      try {
        const result = await adapter.previewVoid(record.report_ref, input(), controller.signal), value = result.data;
        if (!value || !value.target_report || value.target_report.report_ref !== record.report_ref || value.target_report.original_revision_ref !== baseline.revision_ref
          || !value.before || !value.after || !Array.isArray(value.downstream_impacts) || typeof value.can_confirm !== 'boolean' || !value.write_context)
          throw window.APSResourceContract.failure('撤销预检与原报工不一致，请刷新后重试。');
        setPreview(value);
      } catch (failure) { if (!controller.signal.aborted) setError(failure); }
      finally { if (!controller.signal.aborted) setReading(false); }
    }
    async function save() {
      if (locked || !preview || !preview.can_confirm || !form.current.reportValidity()) return;
      await command.submit('execution', 'report_void', record.report_ref, preview.write_context, input());
    }
    return <form ref={form} className="field-editor" aria-label="撤销这次报工" onSubmit={event => { event.preventDefault(); inspect(); }}>
      <div className="field-editor-heading"><h3>撤销这次报工 · {record.report_no}</h3></div>
      <p>本次数量 {C.display(record.completed_quantity)} 件 · 有效工时 {C.display(record.effective_processing_hours)} 小时。撤销后不再计入进度和工时，原记录及更正历史保留。</p>
      <div className="field-extra"><window.ResourceControls.Field label="撤销原因" path="reason" error={error} required>
        <textarea ref={inputRef} aria-label="撤销原因" required maxLength="2000" value={draft.reason} disabled={locked} onChange={event => change('reason', event.target.value)} />
      </window.ResourceControls.Field><window.ResourceControls.Field label="经办人" path="declared_operator" error={error}>
        <input aria-label="撤销经办人" maxLength="2000" value={draft.declared_operator} disabled={locked} onChange={event => change('declared_operator', event.target.value)} />
      </window.ResourceControls.Field></div>
      {preview && <section aria-label="撤销影响" className="field-note"><h4>撤销后</h4>
        <p>累计完成 {C.quantity(preview.before.known_completed_quantity)} → {C.quantity(preview.after.known_completed_quantity)} 件；剩余 {C.quantity(preview.after.remaining_quantity)} 件；状态 {C.states[preview.after.execution_state]}。</p>
        {preview.downstream_impacts.length > 0 && <><p role="alert">以下关联记录需要先处理，本次不能撤销：</p><ul>{preview.downstream_impacts.map((item, index) => <li key={index}>{item.operation_label}：{item.message}</li>)}</ul></>}
        {preview.state === 'voided' && <p>这条报工已经撤销，不会重复扣减。</p>}
      </section>}
      {changed && <p role="alert">原报工已变化，请取消后重新选择。</p>}
      <ErrorBox error={error} /><Feedback command={command} onDone={onDone} />
      <div className="field-footer"><Button onClick={onClose} disabled={command.locked || reading}>取消</Button>
        <Button type="submit" icon="search" busy={reading} disabled={locked}>查看撤销影响</Button>
        {preview && <Button icon="rotate-ccw" className="btn danger" disabled={locked || !preview.can_confirm} onClick={save}>确认撤销这次报工</Button>}
      </div>
    </form>;
  }
  window.FieldVoidEditor = FieldVoidEditor;
})();
