(function () {
  'use strict';
  const C = window.APSResourceContract, S = window.APSResourceSession, { Button, Modal, ErrorBox } = window.ResourceControls;
  const scope = { query: '', page: 1, size: 20, sort: 'business_code', direction: 'asc' };
  function ProcessOpTypeCreate({ adapter, onClose, onCommitted }) {
    const command = S.useCommand(adapter), [initialized, setInitialized] = React.useState(false), [context, setContext] = React.useState(null);
    const [review, setReview] = React.useState(null), [busy, setBusy] = React.useState(false), [error, setError] = React.useState(null), [refresh, setRefresh] = React.useState({});
    const request = React.useRef(null), notified = React.useRef(null);
    React.useEffect(() => { if (command.reset()) setInitialized(true); }, []);
    React.useEffect(() => () => { if (request.current) request.current.abort(); }, []);
    const list = S.useQuery(async signal => C.query(await adapter.list('op_type', scope, signal), 'list'), [adapter], initialized);
    React.useEffect(() => { if (list.result && !context) setContext(list.result); }, [list.result]);
    async function reload() {
      if (busy || command.locked) return;
      const controller = new AbortController(); request.current = controller; setBusy(true); setError(null);
      try { const next = C.query(await adapter.list('op_type', scope, controller.signal), 'list'); if (!controller.signal.aborted) setReview(next); }
      catch (failure) { if (!controller.signal.aborted) setError(failure); }
      finally { if (!controller.signal.aborted) setBusy(false); if (request.current === controller) request.current = null; }
    }
    async function readSaved() {
      if (command.phase !== 'done' || request.current) return;
      const controller = new AbortController(); request.current = controller; setRefresh({ loading: true });
      try {
        if (!command.intent || command.intent.kind !== 'op_type' || command.intent.action !== 'create' || !['committed', 'unchanged'].includes(command.result.result)) throw C.failure('该资源回执不是当前工种的完整新建回执。');
        if (notified.current !== command.result.receipt_ref) { notified.current = command.result.receipt_ref; onCommitted(command.result); }
        const ref = C.resultRef(command.result);
        if (typeof ref !== 'string' || !ref) throw C.failure('新建回执缺少工种引用，尚未绑定工序。');
        const detail = C.query(await adapter.detail('op_type', ref, controller.signal), 'entity');
        if (detail.data.ref !== ref) throw C.failure('新建工种的详情与回执对象不一致。');
        await adapter.list('op_type', scope, controller.signal);
        if (!controller.signal.aborted) setRefresh({ done: true, detail });
      } catch (failure) { if (!controller.signal.aborted) setRefresh({ error: failure }); }
      finally { if (request.current === controller) request.current = null; }
    }
    React.useEffect(() => { if (initialized && command.phase === 'done') readSaved(); }, [initialized, command.phase, command.result && command.result.receipt_ref]);
    function close() { if (!command.locked && !busy && !refresh.loading && command.reset()) onClose(); }
    if (!context) return <Modal title="新增工种" icon="plus" onClose={close} locked={command.locked || busy} footer={<Button onClick={close} disabled={command.locked || busy}>取消</Button>}>
      <div className="modal-b"><ErrorBox error={list.error} />{list.loading && <p role="status">正在读取工种建档资料…</p>}{list.error && <Button icon="refresh-cw" onClick={list.reload}>重读建档资料</Button>}
        {!initialized && <><p>另一个资源请求尚未完成，请先核实。</p><window.ResourceForms.Feedback command={command} /></>}</div></Modal>;
    return <window.ResourceForms adapter={adapter} kind="op_type" action="create" writeContext={review ? null : context.data.create_context} source={context.meta.source} command={command}
      onClose={close} onReloadContext={reload} contextBusy={busy || refresh.loading} contextError={error} contextReview={review} onAcceptContext={() => { setContext(review); setReview(null); setError(null); }}
      refreshState={refresh} onRefresh={readSaved} />;
  }
  window.ProcessOpTypeCreate = ProcessOpTypeCreate;
})();
