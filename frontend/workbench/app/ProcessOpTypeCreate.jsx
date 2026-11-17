import React from './shared/runtime/react.js';
import C from './resource-contract.js';
import S from './shared/session/command-session.js';
import APSResourceAPI from './resource-api.js';
import { useQuery } from './shared/session/query.js';
import { Button, Modal, ErrorBox } from './ResourceControls.jsx';
import WorkbenchTerms from './WorkbenchTerms.js';
import ResourceForms, { Feedback } from './ResourceForms.jsx';
import { failure } from './shared/contract/kit.js';

const scope = { query: '', page: 1, size: 20, sort: 'business_code', direction: 'asc' };
// 在工艺页里新增工种：和资源页共用基础资料命名空间的待确认记录与命令会话。
function ProcessOpTypeCreate({ onClose, onCommitted }) {
  const api = APSResourceAPI.forNamespace('resources'), command = S.useCommand(api), [initialized, setInitialized] = React.useState(false), [context, setContext] = React.useState(null);
  const [review, setReview] = React.useState(null), [busy, setBusy] = React.useState(false), [error, setError] = React.useState(null), [refresh, setRefresh] = React.useState({});
  const request = React.useRef(null), notified = React.useRef(null);
  React.useEffect(() => { if (command.reset()) setInitialized(true); }, []);
  React.useEffect(() => () => { if (request.current) request.current.abort(); }, []);
  const list = useQuery(signal => api.list('op_type', scope, signal), [], { enabled: initialized });
  React.useEffect(() => { if (list.result && !context) setContext(list.result); }, [list.result]);
  async function reload() {
    if (busy || command.locked) return;
    const controller = new AbortController(); request.current = controller; setBusy(true); setError(null);
    try {
      const next = await api.list('op_type', scope, controller.signal);
      if (controller.signal.aborted || !command.reset()) return;
      // 刷新即采用：新读到的建档资料直接接进保存路径，复核区只展示当前资料。
      // 与 ResourceWorkspace.reloadContext 走同一条路，ResourceForms 不需要单独的“采用”步骤。
      setContext(next); setReview(next);
    }
    catch (failure) { if (!controller.signal.aborted) setError(failure); }
    finally { if (!controller.signal.aborted) setBusy(false); if (request.current === controller) request.current = null; }
  }
  async function readSaved() {
    if (command.phase !== 'done' || request.current) return;
    const controller = new AbortController(); request.current = controller; setRefresh({ loading: true });
    try {
      if (!command.intent || command.intent.kind !== 'op_type' || command.intent.action !== 'create' || !['committed', 'unchanged'].includes(command.result.result)) throw failure(WorkbenchTerms.outcomes.unknown('新增工种'), { committed: 'unknown' });
      if (notified.current !== command.result.receipt_ref) { notified.current = command.result.receipt_ref; onCommitted(command.result); }
      const ref = C.resultRef(command.result);
      if (typeof ref !== 'string' || !ref) throw failure('新增结果里没有工种编号，工序还没绑定。请刷新后核对。', { committed: 'unknown' });
      const detail = await api.detail('op_type', ref, controller.signal);
      if (!controller.signal.aborted) setRefresh({ done: true, detail });
    } catch (failure) { if (!controller.signal.aborted) setRefresh({ error: failure }); }
    finally { if (request.current === controller) request.current = null; }
  }
  React.useEffect(() => { if (initialized && command.phase === 'done') readSaved(); }, [initialized, command.phase, command.result && command.result.receipt_ref]);
  function close() { if (!command.locked && !busy && !refresh.loading && command.reset()) onClose(); }
  if (!context) return <Modal title="新增工种" icon="plus" onClose={close} locked={command.locked || busy} footer={<Button onClick={close} disabled={command.locked || busy}>取消</Button>}>
    <div className="modal-b"><ErrorBox error={list.error} />{list.loading && <p role="status">正在读取工种建档资料…</p>}{list.error && <Button icon="refresh-cw" onClick={list.reload}>{WorkbenchTerms.refresh_latest}</Button>}
      {!initialized && <><p>另一个操作还没处理完，请先查询上次结果。</p><Feedback command={command} /></>}</div></Modal>;
  return <ResourceForms kind="op_type" action="create" writeContext={context.data.create_context} source={context.meta.source} command={command}
    onClose={close} onReloadContext={reload} contextBusy={busy || refresh.loading} contextError={error} contextReview={review}
    refreshState={refresh} onRefresh={readSaved} />;
}

export { ProcessOpTypeCreate };
export default ProcessOpTypeCreate;
