(function () {
  'use strict';
  const C = window.DashboardContract, P = window.DashboardPanels, { Button, Modal, ErrorBox } = window.ResourceControls;
  function draftFor(item) { return { target_status: item.handling.status, ...Object.fromEntries(C.fields.filter(k => k !== 'evidence_ref').map(k => [k, item.handling[k] || ''])), reason: '' }; }
  function inputFor(draft, reopen) {
    const normalized = text => text.trim() || null;
    if (reopen) { C.check(normalized(draft.reason), '请填写重开原因。'); return { reason: draft.reason.trim() }; }
    const input = { target_status: draft.target_status, ...Object.fromEntries(C.fields.filter(k => k !== 'evidence_ref').map(k => [k, normalized(draft[k])])) };
    if (input.completed_at && /^\d{4}-\d\d-\d\dT\d\d:\d\d$/.test(input.completed_at)) input.completed_at += ':00';
    C.check(input.remark, '请填写原因说明。');
    if (input.target_status !== 'new') C.check(input.owner && input.deadline && input.action, '请填写责任人、期限和处置行动。');
    if (input.target_status === 'closed') C.check(input.completed_at && input.completion_evidence && input.evidence_reference_text, '关闭前请填写完成时间、具体完成结果和可核对凭据。');
    return input;
  }
  function Receipt({ command, onFinish }) {
    const s = command.saved;
    return <><div className={'dy-note ' + (s.phase === 'confirmed' ? 'success' : 'warning')} role="status">
      {s.phase === 'confirmed' ? window.WorkbenchTerms.outcomes.done('处置', s.receipt.result === 'unchanged' ? '内容和原来一样，没有新增历史记录' : '处置和历史都已保存') : s.phase === 'rejected' ? '上次处置没有生效，填写内容已保留。改好后重新提交。' : window.WorkbenchTerms.outcomes.pending('处置')}</div>
      <p>{s.subject}</p><window.WorkbenchReference entries={{ '操作编号': s.request_key, '结果编号': s.phase === 'confirmed' ? s.receipt.receipt_ref : null }} />
      <P.Facts handling={s.phase === 'confirmed' ? s.receipt.data.handling : C.expected(s)} />
      {s.phase === 'pending' ? <Button reasonDisplay="inline" icon="refresh-cw" busy={command.busy} onClick={command.lookup}>查询结果</Button> : <Button reasonDisplay="inline" icon="check" onClick={onFinish}>完成</Button>}</>;
  }
  function Handling({ item, command, onClose, onFinish }) {
    const [draft, setDraft] = React.useState(() => item ? draftFor(item) : null), [error, setError] = React.useState(null);
    const saved = command.saved, reopen = item && item.handling.status === 'closed';
    const update = (k, v) => { setDraft(previous => ({ ...previous, [k]: v })); setError(null); };
    async function submit() { try { const input = inputFor(draft, reopen); await command.submit(item, reopen ? 'reopen' : 'transition', input); } catch (e) { setError(e); } }
    const action = reopen ? 'reopen' : 'transition', context = item && item.write_context;
    const disabledReason = !context || context.capabilities[action] !== true ? '这条记录现在不能处置，请刷新后重试。' : '';
    return <Modal title={saved ? '上次处置结果' : reopen ? '独立重开处置' : '登记条目处置'} icon={reopen ? 'refresh-cw' : 'square-pen'} locked={command.busy} onClose={onClose}
      footer={<><Button reasonDisplay="inline" onClick={onClose} disabled={command.busy}>{saved && saved.phase === 'pending' ? '关闭并保留这次操作' : '关闭'}</Button>
        {!saved && <Button reasonDisplay="inline" icon="check" className="btn primary" busy={command.busy} reason={disabledReason || (command.storageError ? '上次操作记录还没确认' : '')} onClick={submit}>{reopen ? '确认独立重开' : '提交处置'}</Button>}</>}>
      <div className="dy-dialog-body"><ErrorBox error={error || command.error || command.storageError} />{command.notice && <div className="dy-note">{command.notice}</div>}
        {saved ? <Receipt command={command} onFinish={onFinish} /> : item && <><h3>{item.subject}</h3><div className="dy-tools"><P.Risk risk={item.risk} /><P.Status handling={item.handling} /></div>
          {reopen ? <><div className="dy-note">重开后状态变为跟进中，本次填的完成内容会清除。原来的完成时间、结果和凭据都留在历史里。</div><label className="dy-form">重开原因<textarea aria-label="重开原因" value={draft.reason} maxLength={4000} onChange={e => update('reason', e.target.value)} /></label><P.Facts handling={item.handling} /></> : <form className="dy-form" onSubmit={e => { e.preventDefault(); submit(); }}>
            <label>目标处置状态<select aria-label="目标处置状态" value={draft.target_status} onChange={e => update('target_status', e.target.value)} disabled={command.busy}>{item.allowed_transitions.map(s => <option key={s} value={s}>{C.statuses[s]}</option>)}</select></label>
            <label>责任人<input aria-label="责任人" value={draft.owner} maxLength={200} onChange={e => update('owner', e.target.value)} disabled={command.busy} /></label>
            <label>责任期限<input aria-label="责任期限" type="date" value={draft.deadline} onChange={e => update('deadline', e.target.value)} disabled={command.busy} /></label>
            <label>完成时间<input aria-label="完成时间" type="datetime-local" step="1" value={draft.completed_at} onChange={e => update('completed_at', e.target.value)} disabled={command.busy} /></label>
            {['action', 'remark', 'completion_evidence', 'evidence_reference_text'].map(k => <label key={k} className="wide">{C.labels[k]}<textarea aria-label={C.labels[k]} value={draft[k]} maxLength={4000} onChange={e => update(k, e.target.value)} disabled={command.busy} /></label>)}
          </form>}
          <div className="dy-note">凭据这里只存文字说明，还没有当成附件核验。处置状态不会改动报工记录，关闭也不会删掉风险。</div></>}
      </div></Modal>;
  }
  window.DashboardHandling = Handling;
})();
