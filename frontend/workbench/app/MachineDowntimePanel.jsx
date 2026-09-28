(function () {
  'use strict';
  const C = window.APSResourceContract, S = window.APSResourceSession;
  const { Button, Modal, Field, ErrorBox } = window.ResourceControls;
  const blank = () => ({ start_time: '', end_time: '', reason_code: 'maintenance', reason_detail: '' });
  function MachineDowntimePanel({ adapter, entity, source, onClose, onCommitted }) {
    const command = S.useCommand(adapter), [selection, setSelection] = React.useState(null);
    const [draft, setDraft] = React.useState(blank), [original, setOriginal] = React.useState(blank), [error, setError] = React.useState(null);
    const [confirmCancel, setConfirmCancel] = React.useState(false), [review, setReview] = React.useState(null), seen = React.useRef(null);
    const query = S.useQuery(signal => adapter.downtimes(entity.ref, signal), [adapter, entity.ref]);
    const data = query.result && query.result.data, done = command.phase === 'done', locked = command.locked || done;
    const dirty = JSON.stringify(draft) !== JSON.stringify(original), form = React.useId();
    const owner = window.WorkbenchGuards.useDirtyGuard({ dirty: !done && dirty, locked: command.locked, message: '停机资料尚未保存，离开会丢失本次填写。' });
    React.useEffect(() => {
      if (!done || seen.current === command.result.receipt_ref) return;
      const receipt = command.result, intent = command.intent;
      if (!intent || receipt.data.operation !== 'machine.' + intent.action || intent.ref !== entity.ref || receipt.data.entity_ref !== entity.ref) {
        setError(C.failure('保存结果与当前设备不一致，请查询结果后核对。')); return;
      }
      seen.current = receipt.receipt_ref; query.reload(); if (onCommitted) onCommitted(receipt);
    }, [done, command.result]);
    async function close(detail) {
      if (command.locked) return;
      if (detail && detail.guardConfirmed && detail.guardOwner === owner || await window.WorkbenchGuards.confirmLeave({ owner })) onClose();
    }
    function select(row) {
      const value = row ? Object.fromEntries(Object.keys(blank()).map(key => [key, row[key] || ''])) : blank();
      value.start_time = value.start_time.replace(' ', 'T'); value.end_time = value.end_time.replace(' ', 'T');
      setSelection(row); setDraft(value); setOriginal(value); setConfirmCancel(false); setError(null);
    }
    async function save(event) {
      event.preventDefault(); if (locked || !data || review) return;
      const action = confirmCancel ? 'cancel' : selection ? 'update' : 'create';
      const reason = C.blocked(data.write_context, 'machine', 'downtime_' + action, source);
      if (reason) { setError(C.failure(reason)); return; }
      if (!confirmCancel && (!draft.start_time || !draft.end_time || draft.end_time <= draft.start_time)) {
        setError(C.failure('请填写停机起止，结束必须晚于开始。')); return;
      }
      setError(null);
      await command.submit('machine', 'downtime_' + action, entity.ref, data.write_context,
        { ...(confirmCancel ? {} : draft), ...(selection ? { downtime_ref: selection.ref } : {}) });
    }
    async function reload() {
      try { const latest = await adapter.downtimes(entity.ref); setReview(latest); setError(null); }
      catch (e) { setError(e); }
    }
    return <Modal title={'停机计划 · ' + entity.business_code} icon="wrench" onClose={close} guardOwner={owner} locked={command.locked}
      footer={<><Button onClick={close} disabled={command.locked}>关闭</Button>{!done && <Button form={form} type="submit" className="btn primary" disabled={locked || !data || !!review}>
        {confirmCancel ? '确认取消这段停机' : '保存停机计划'}</Button>}</>}>
      <form id={form} className="modal-b form scroll" onSubmit={save}>
        <p>停机计划按起止时间限制排产。设备改为可用后，已有有效停机计划仍然生效；取消计划会保留原记录。</p>
        <ErrorBox error={query.error} />{query.loading && <p role="status">正在读取停机记录…</p>}
        <div className="wb-table-frame"><table className="tbl wb-table" aria-label="设备停机计划"><thead><tr><th>开始</th><th>结束</th><th>原因</th><th>状态</th><th>操作</th></tr></thead><tbody>
          {data && data.rows.map(row => <tr key={row.ref}><td>{window.WorkbenchFormat.dateTime(row.start_time)}</td><td>{window.WorkbenchFormat.dateTime(row.end_time)}</td>
            <td>{data.reasons[row.reason_code] || row.reason_code} {row.reason_detail}</td><td>{row.status === 'active' ? '有效' : row.status === 'cancelled' ? '已取消' : row.status}</td>
            <td><Button disabled={locked || dirty || row.status !== 'active'} onClick={() => select(row)}>维护</Button></td></tr>)}
        </tbody></table></div>
        {!done && <Button disabled={locked || dirty} onClick={() => select(null)}>新增停机</Button>}
        {!done && <><div className="fgrid">
          {['start_time', 'end_time'].map((key, index) => <Field key={key} label={index ? '停机结束' : '停机开始'}><input type="datetime-local" step="1" value={draft[key]} disabled={locked || confirmCancel}
            onChange={event => setDraft({ ...draft, [key]: event.target.value })} /></Field>)}
          <Field label="停机原因"><select value={draft.reason_code} disabled={locked || confirmCancel} onChange={event => setDraft({ ...draft, reason_code: event.target.value })}>
            {data && Object.entries(data.reasons).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></Field>
          <Field label="原因说明"><input value={draft.reason_detail} disabled={locked || confirmCancel} onChange={event => setDraft({ ...draft, reason_detail: event.target.value })} /></Field>
        </div>{selection && <Button disabled={locked} onClick={() => setConfirmCancel(!confirmCancel)}>{confirmCancel ? '返回编辑' : '取消这段停机'}</Button>}
          {confirmCancel && <p>确认后，该时段不再限制设备排产。已有排程不会自动重排。</p>}
          <Button onClick={reload} disabled={locked}>读取最新记录</Button></>}
        {review && <div role="status"><p>采用最新记录将放弃本次未保存的修改，请重新选择要维护的停机。</p><Button disabled={locked} onClick={() => { select(null); setReview(null); command.reset(); query.reload(); }}>采用最新记录并重新填写</Button></div>}
        <ErrorBox error={error} /><window.ResourceForms.Feedback command={command} />
        {done && <p role="status">{query.loading ? '正在刷新保存结果…' : query.error ? '保存结果已确认，列表尚未刷新；请关闭后重新查看。' : '已刷新停机记录。'}</p>}
      </form>
    </Modal>;
  }
  window.MachineDowntimePanel = MachineDowntimePanel;
})();
