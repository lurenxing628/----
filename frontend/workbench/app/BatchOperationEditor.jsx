(function () {
  'use strict';
  const B = window.APSBatchContract, C = window.APSResourceContract, S = window.APSResourceSession;
  const { Button, Modal, ErrorBox } = window.ResourceControls, { Field } = window.BatchControls;
  function BatchOperationEditor({ adapter, entity, operation, source, command, onCommitted, onClose, disabled }) {
    const internal = operation.source === 'internal', merged = operation.external_group && operation.external_group.merge_mode === 'merged';
    const keys = internal ? ['machine_ref', 'operator_ref', 'setup_hours', 'unit_hours'] : ['supplier_ref'].concat(merged ? [] : ['external_days']);
    const original = Object.fromEntries(keys.map(key => [key, operation[key] == null ? '' : String(operation[key])]));
    const [draft, setDraft] = React.useState(original), [error, setError] = React.useState(null), seen = React.useRef(null);
    const form = React.useId(), done = command.phase === 'done', locked = disabled || command.locked || done;
    const formElement = React.useRef(null), paths = keys.map(key => 'fields.' + key), currentError = error || command.error;
    const guardOwner = window.WorkbenchGuards.useDirtyGuard({ dirty: !done && keys.some(key => draft[key] !== original[key]), locked: command.locked,
      message: '批次工序补充资料尚未保存，离开会丢失本次填写。' });
    React.useEffect(() => { if (currentError) window.ResourceControls.focusFirstInvalid(formElement.current); }, [currentError]);
    async function close(detail) {
      if (command.locked) return;
      if (detail && detail.guardConfirmed === true && detail.guardOwner === guardOwner || await window.WorkbenchGuards.confirmLeave({ owner: guardOwner })) onClose();
    }
    const choices = S.useQuery(signal => adapter.choices(signal), [adapter]);
    const catalogs = choices.result && choices.result.data;
    const names = { machine_ref: '设备', operator_ref: '人员', supplier_ref: '供应商', setup_hours: '换型工时（小时）', unit_hours: '单件工时（小时）', external_days: '外协周期（天）' };
    const allowed = catalogs && draft.machine_ref ? catalogs.authorizations.filter(row => row.machine_ref === draft.machine_ref).map(row => row.operator_ref) : null;
    const mismatch = allowed && draft.operator_ref && !allowed.includes(draft.operator_ref);
    React.useEffect(() => {
      if (!done || seen.current === command.result.receipt_ref) return;
      try { B.receipt(command.result, 'operation_update', entity.ref); if (command.result.data.operation_ref !== operation.ref) throw C.failure('回执工序与当前工序不一致。'); seen.current = command.result.receipt_ref; onCommitted(command.result); }
      catch (error) { setError(error); }
    }, [done, command.result]);
    async function submit(event) {
      event.preventDefault(); if (locked || mismatch) return;
      try {
        const fields = {};
        for (const key of keys) {
          if (draft[key] === original[key]) continue;
          let value = draft[key] === '' ? null : draft[key];
          if (!key.endsWith('_ref') && value !== null) {
            if (!/^\d+(?:\.\d+)?$/.test(value) || !Number.isFinite(Number(value)) || Number(value) > Number.MAX_SAFE_INTEGER || key === 'external_days' && Number(value) <= 0)
              throw C.failure('请检查标记的工序字段。', [{ path: 'fields.' + key, message: names[key] + '必须为有效数字。' }]);
            value = Number(value);
          }
          fields[key] = value;
        }
        if (!Object.keys(fields).length) throw C.failure('没有需要保存的变更。');
        setError(null); await command.submit('batch', 'operation_update', entity.ref, entity.write_context, { operation_ref: operation.ref, fields });
      } catch (error) { setError(error); }
    }
    return <Modal title={'工序 ' + operation.sequence + ' · ' + operation.label} icon="wrench" guardOwner={guardOwner} locked={command.locked} onClose={close}
      footer={<><Button onClick={close} disabled={command.locked}>{done ? '关闭' : '取消'}</Button>{!done && <Button form={form} type="submit" icon="check" className="btn primary"
        disabled={locked || !catalogs || !!mismatch} reason={B.reason(entity.write_context, 'operation_update', source)}>保存工序</Button>}</>}>
      <form id={form} ref={formElement} className="modal-b form" onSubmit={submit} noValidate><div className="fgrid batch-fields">
        {keys.map(key => <Field key={key} label={names[key]} path={'fields.' + key} error={currentError}>{key.endsWith('_ref') ? <select value={draft[key]} disabled={locked || !catalogs} onChange={event => setDraft({ ...draft, [key]: event.target.value })}>
          <option value="">未选择</option>{catalogs && catalogs[key.slice(0, -4) + 's'].map(row => <option key={row.ref} value={row.ref} disabled={row.status !== 'active'}>{row.business_code} · {row.label}{row.status === 'active' ? '' : '（不可用）'}</option>)}</select>
          : <input value={draft[key]} type="text" inputMode="decimal" disabled={locked} onChange={event => setDraft({ ...draft, [key]: event.target.value })} />}</Field>)}
      </div>{merged && <p>合并外协组 {operation.external_group.business_code} · 整组周期 {window.WorkbenchFormat.number(operation.external_group.total_days)} 天（只读）</p>}
        {allowed && <p style={mismatch ? { color: 'var(--ui-danger-text)' } : undefined}>{mismatch ? '所选人员未获设备操作授权。' : '设备授权人员：'}{catalogs.operators.filter(row => allowed.includes(row.ref)).map(row => row.label).join('、') || '无'}</p>}
        <ErrorBox error={error} excludePaths={paths} /><ErrorBox error={choices.error} /><window.ResourceForms.Feedback command={command} excludePaths={error ? [] : paths} />
      </form>
    </Modal>;
  }
  window.BatchOperationEditor = BatchOperationEditor;
})();
