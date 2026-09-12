(function () {
  'use strict';
  const C = window.DashboardContract, P = window.DashboardPanels, { Button, Modal, ErrorBox } = window.ResourceControls;
  function draftFor(item) { return { target_status: item.handling.status, ...Object.fromEntries(C.fields.filter(k => k !== 'evidence_ref').map(k => [k, item.handling[k] || ''])), reason: '' }; }
  function inputFor(draft, reopen) {
    const normalized = text => text.trim() || null;
    if (reopen) { C.check(normalized(draft.reason), '请填写独立重开原因。'); return { reason: draft.reason.trim() }; }
    const input = { target_status: draft.target_status, ...Object.fromEntries(C.fields.filter(k => k !== 'evidence_ref').map(k => [k, normalized(draft[k])])) };
    if (input.completed_at && /^\d{4}-\d\d-\d\dT\d\d:\d\d$/.test(input.completed_at)) input.completed_at += ':00';
    C.check(input.remark, '请填写原因和本次核实备注。');
    if (input.target_status !== 'new') C.check(input.owner && input.deadline && input.action, '请填写责任人、期限和处置行动。');
    if (input.target_status === 'closed') C.check(input.completed_at && input.completion_evidence && input.evidence_reference_text, '关闭须填写完成时间、具体结果和可核对凭据。');
    return input;
  }
  function Receipt({ command, onFinish }) {
    const s = command.saved;
    return <><div className={'dy-note ' + (s.phase === 'confirmed' ? 'success' : 'warning')} role="status">
      {s.phase === 'confirmed' ? '已确认：' + (s.receipt.result === 'unchanged' ? '无变化，未重复增加历史。' : '处置与历史已保存。') : s.phase === 'rejected' ? '本次明确未写入。' : '结果尚未确认，仅查询原请求。'}</div>
      <p>{s.subject}</p><window.WorkbenchReference entries={{ '原请求编号': s.request_key, '回执编号': s.phase === 'confirmed' ? s.receipt.receipt_ref : null }} />
      <P.Facts handling={s.phase === 'confirmed' ? s.receipt.data.handling : C.expected(s)} />
      {s.phase === 'pending' ? <Button reasonDisplay="inline" icon="refresh-cw" busy={command.busy} onClick={command.lookup}>查询原回执</Button> : <Button reasonDisplay="inline" icon="check" onClick={onFinish}>完成核实并刷新</Button>}</>;
  }
  function Handling({ item, command, onClose, onFinish }) {
    const [draft, setDraft] = React.useState(() => item ? draftFor(item) : null), [error, setError] = React.useState(null);
    const saved = command.saved, reopen = item && item.handling.status === 'closed';
    const update = (k, v) => { setDraft(previous => ({ ...previous, [k]: v })); setError(null); };
    async function submit() { try { const input = inputFor(draft, reopen); await command.submit(item, reopen ? 'reopen' : 'transition', input); } catch (e) { setError(e); } }
    const action = reopen ? 'reopen' : 'transition', context = item && item.write_context;
    const disabledReason = !context || context.capabilities[action] !== true ? '没有有效处置能力，请明确刷新条目。' : '';
    return <Modal title={saved ? '处置请求核实' : reopen ? '独立重开处置' : '登记条目处置'} icon={reopen ? 'refresh-cw' : 'square-pen'} locked={command.busy} onClose={onClose}
      footer={<><Button reasonDisplay="inline" onClick={onClose} disabled={command.busy}>{saved && saved.phase === 'pending' ? '关闭并保留请求' : '关闭窗口'}</Button>
        {!saved && <Button reasonDisplay="inline" icon="check" className="btn primary" busy={command.busy} reason={disabledReason || (command.storageError ? '恢复记录尚未核实' : '')} onClick={submit}>{reopen ? '确认独立重开' : '提交处置'}</Button>}</>}>
      <div className="dy-dialog-body"><ErrorBox error={error || command.error || command.storageError} />{command.notice && <div className="dy-note">{command.notice}</div>}
        {saved ? <Receipt command={command} onFinish={onFinish} /> : item && <><h3>{item.subject}</h3><div className="dy-tools"><P.Risk risk={item.risk} /><P.Status handling={item.handling} /></div>
          {reopen ? <><div className="dy-note">重开后转为跟进中，本轮完成字段清空；旧完成时间、结果和凭据保留在历史。</div><label className="dy-form">重开原因<textarea aria-label="重开原因" value={draft.reason} maxLength={4000} onChange={e => update('reason', e.target.value)} /></label><P.Facts handling={item.handling} /></> : <form className="dy-form" onSubmit={e => { e.preventDefault(); submit(); }}>
            <label>目标处置状态<select aria-label="目标处置状态" value={draft.target_status} onChange={e => update('target_status', e.target.value)} disabled={command.busy}>{item.allowed_transitions.map(s => <option key={s} value={s}>{C.statuses[s]}</option>)}</select></label>
            <label>责任人<input aria-label="责任人" value={draft.owner} maxLength={200} onChange={e => update('owner', e.target.value)} disabled={command.busy} /></label>
            <label>责任期限<input aria-label="责任期限" type="date" value={draft.deadline} onChange={e => update('deadline', e.target.value)} disabled={command.busy} /></label>
            <label>完成时间<input aria-label="完成时间" type="datetime-local" step="1" value={draft.completed_at} onChange={e => update('completed_at', e.target.value)} disabled={command.busy} /></label>
            {['action', 'remark', 'completion_evidence', 'evidence_reference_text'].map(k => <label key={k} className="wide">{C.labels[k]}<textarea aria-label={C.labels[k]} value={draft[k]} maxLength={4000} onChange={e => update(k, e.target.value)} disabled={command.busy} /></label>)}
          </form>}
          <div className="dy-note">凭据文字尚未核验为附件。处置状态不改报工事实，关闭不删除风险。</div></>}
      </div></Modal>;
  }
  window.DashboardHandling = Handling;
})();
