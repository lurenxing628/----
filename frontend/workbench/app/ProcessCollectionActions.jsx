(function () {
  'use strict';
  const C = window.APSResourceContract, P = window.APSProcessContract, A = window.APSProcessActions, S = window.APSResourceSession;
  const { Button, Modal, ErrorBox, Issues } = window.ResourceControls;
  function ProcessCollectionActions({ adapter, request, onClose, onCommitted, onOpen, disabled = false }) {
    const [original] = React.useState(() => ({ ...request, refs: request.refs && request.refs.slice(), scope: A.scope(request.scope) }));
    const [draft, setDraft] = React.useState({ business_code: '', label: '', route_raw: '', remark: '' });
    const [error, setError] = React.useState(null), [discard, setDiscard] = React.useState(false), [job, setJob] = React.useState(null);
    const [ack, setAck] = React.useState(false), [now, setNow] = React.useState(Date.now()), [opening, setOpening] = React.useState(false);
    const [context, setContext] = React.useState(original), [review, setReview] = React.useState(null), [reading, setReading] = React.useState(false);
    const command = S.useCommand(adapter), notified = React.useRef(null), controller = React.useRef(null);
    const create = original.mode === 'create', recovery = original.recovery === true;
    let saved = null, receiptError = null;
    if (command.phase === 'done') { try { saved = A.receipt(command.result, command.intent, !create && !recovery ? original.refs : undefined); } catch (failure) { receiptError = failure; } }
    const visible = receiptError ? { ...command, phase: 'pending', locked: true, error: receiptError } : command;
    const done = !!saved, dirty = !done && Object.values(draft).some(value => value !== ''), locked = visible.locked || opening || reading;
    const preview = S.useQuery(async signal => A.deletePreview(await adapter.bulkPreview(A.deleteBody(original), signal), original), [adapter, job], !!job);
    const result = preview.result, data = result && result.data;
    React.useEffect(() => () => { if (controller.current) controller.current.abort(); }, []);
    window.WorkbenchGuards.useDirtyGuard({ dirty, locked: visible.locked,
      message: create ? '新增零件的图号、名称或路线填写尚未保存。' : '上次操作的结果还没查到，先不要离开。' });
    React.useEffect(() => {
      if (!done || notified.current === command.result.receipt_ref) return;
      notified.current = command.result.receipt_ref;
      if (onCommitted) onCommitted(command.result);
    }, [done, command.result, onCommitted]);
    React.useEffect(() => {
      if (!data) return undefined;
      const timer = setTimeout(() => setNow(Date.now()), Math.max(0, Date.parse(data.expires_at) - Date.now() + 1));
      return () => clearTimeout(timer);
    }, [data]);
    function close(force = false) {
      if (locked) return;
      if (dirty && !force) { setDiscard(true); return; }
      if (command.reset()) onClose();
    }
    function preflight() {
      if (disabled || locked || done || recovery || !command.reset()) return;
      setError(null); setAck(false);
      try { if (typeof adapter.bulkPreview !== 'function') throw C.failure('dependency not wired: window.APSProcessAPI.bulkPreview'); A.deleteBody(original); setJob({}); setNow(Date.now()); }
      catch (failure) { setError(failure); }
    }
    async function readCurrent() {
      if (locked || done || controller.current) return;
      const abort = new AbortController(); controller.current = abort; setReading(true); setError(null);
      try {
        const scope = { ...original.scope, page: 1, size: original.page_size || 20 };
        const value = P.list(await adapter.list('part', scope, abort.signal), scope);
        if (!abort.signal.aborted) setReview({ ...context, create_context: value.data.create_context, source: value.meta.source });
      } catch (failure) { if (!abort.signal.aborted) setError(failure); }
      finally { if (controller.current === abort) { controller.current = null; if (!abort.signal.aborted) setReading(false); } }
    }
    async function openCreated() {
      if (!saved || locked || controller.current || typeof onOpen !== 'function') return;
      const abort = new AbortController(); controller.current = abort; setOpening(true); setError(null);
      try {
        P.detail(await adapter.detail('part', saved.entity_ref, abort.signal), saved.entity_ref);
        if (!abort.signal.aborted && command.reset()) onOpen(saved.entity_ref);
      } catch (failure) { if (!abort.signal.aborted) setError(failure); }
      finally { if (controller.current === abort) { controller.current = null; if (!abort.signal.aborted) setOpening(false); } }
    }
    let reason = create ? A.createReason(context.create_context, context.source) : A.blocked(result, original.source, 'process_bulk.confirm');
    if (!create && data && now >= Date.parse(data.expires_at)) reason = '预检已过期，请重新预检。';
    if (!create && !reason && !ack) reason = '请先核对并勾选完整删除范围。';
    if (review) reason = '请先核对新读取的资料。';
    if (command.phase === 'rejected') reason = create ? '本次未保存，请刷新资料后再试。' : '本次未删除，请重新预检。';
    function confirm() {
      if (disabled || locked || done || reason || recovery) return;
      setError(null);
      try {
        if (create) command.submit('process', 'create', null, context.create_context, A.createInput(draft));
        else command.submit('process_bulk', 'confirm', data.preview_ref, data.write_context, { preview_ref: data.preview_ref });
      } catch (failure) { setError(failure); }
    }
    return <div className={'plana rm-actions' + (data ? ' rm-wide' : '')}><window.ResourceMaterialPreview.Styles />
      <Modal title={create ? '新增零件' : original.refs && original.refs.length === 1 ? '删除零件' : '批量删除零件'} icon={create ? 'plus' : 'trash-2'} locked={locked} suspended={discard} onClose={() => close()}
        footer={<><Button disabled={locked} onClick={() => close()}>{done ? '完成' : '取消'}</Button>
          {!create && !recovery && !done && <Button icon="check" disabled={disabled || locked} busy={!!job && preview.loading} onClick={preflight}>{job ? '重新预检' : '检查删除范围'}</Button>}
          {!recovery && !done && (create || data) && <Button icon={create ? 'plus' : 'trash-2'} className={'btn ' + (create ? 'primary' : 'danger')} disabled={disabled || locked || preview.loading} reason={reason} onClick={confirm}>{create ? '保存零件' : '确认删除'}</Button>}
          {done && create && <Button icon="arrow-right" className="btn primary" busy={opening} disabled={disabled || locked} onClick={openCreated}>打开工艺详情</Button>}</>}>
        <div className="modal-b scroll rm-body">
          {create && !recovery && !done && <div className="fgrid">{[['business_code', '图号'], ['label', '零件名称'], ['route_raw', '路线文字（选填）'], ['remark', '备注（选填）']].map(([key, label]) => <label className={'field' + (['route_raw', 'remark'].includes(key) ? ' full' : '')} key={key}>{label}
            {['route_raw', 'remark'].includes(key) ? <textarea aria-label={label} rows={key === 'route_raw' ? 4 : 2} disabled={disabled || locked} value={draft[key]} onChange={event => setDraft({ ...draft, [key]: event.target.value })} /> : <input aria-label={label} required disabled={disabled || locked} value={draft[key]} onChange={event => setDraft({ ...draft, [key]: event.target.value })} />}</label>)}</div>}
          {create && !done && !recovery && <><p>新增后，请继续确认工艺。</p><Button icon="refresh-cw" disabled={disabled || locked} onClick={readCurrent}>刷新资料</Button></>}
          {review && <div role="status"><p>已读取最新资料，填写内容未改。请核对后继续保存。</p><Button disabled={locked} onClick={() => { if (command.reset()) { setContext(review); setReview(null); } }}>已核对，继续编辑</Button></div>}
          {!create && !recovery && <p>本次选中 {original.refs.length} 个零件，包含其他页的选择；已被批次使用的零件不能删除。有一项不能删，本次就一项也不删。</p>}
          {recovery && <p>正在查询上次操作结果，请稍候。</p>}
          {!!job && preview.loading && <p role="status">正在检查完整删除范围，尚未删除…</p>}
          <ErrorBox error={error} /><ErrorBox error={preview.error} /><Issues issues={result && result.warnings || []} />
          {data && <><window.ProcessActionPreview data={data} />{!done && <label className="rm-check"><input type="checkbox" checked={ack} disabled={disabled || locked} onChange={event => setAck(event.target.checked)} />已核对全部明细，确认删除这些零件。</label>}</>}
          <window.ResourceForms.Feedback command={visible} />
          {done && <p role="status">{create ? '零件已登记，工艺仍待确认。打开详情前会先刷新这条零件。' : '上次操作已确认删除 ' + saved.deleted_count + ' 个零件。'}</p>}
        </div></Modal>
      {discard && <Modal title="放弃新增零件的填写内容？" icon="square-pen" onClose={() => setDiscard(false)} footer={<><Button onClick={() => setDiscard(false)}>继续编辑</Button><Button className="btn danger" onClick={() => close(true)}>放弃填写并关闭</Button></>}><div className="modal-b">未保存的内容将被丢弃。</div></Modal>}
    </div>;
  }
  window.ProcessCollectionActions = ProcessCollectionActions;
})();
