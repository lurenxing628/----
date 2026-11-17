import React from './shared/runtime/react.js';
import APSCalendarFile from './CalendarFileContract.js';
import APSRelationFile from './RelationFileContract.js';
import APSResourceAPI from './resource-api.js';
import ResourceWorkspace from './ResourceWorkspace.jsx';
import { ErrorBox, Button } from './ResourceControls.jsx';
import ProcessWorkspace from './ProcessWorkspace.jsx';
import ResourceCalendar from './ResourceCalendar.jsx';
import ResourceCatalog from './ResourceCatalog.jsx';
import CalendarFileActions from './CalendarFileActions.jsx';
import RelationFileActions from './RelationFileActions.jsx';
import ResourceMaterialActions from './ResourceMaterialActions.jsx';
import ResourceFileActions from './ResourceFileActions.jsx';
import { failure } from './shared/contract/kit.js';

const fileKinds = ['material', 'op_type', 'machine', 'operator', 'supplier'];
// 附属资料按它挂靠的那类基础资料开入口：在人员页维护可操作设备和个人日历。
const attachedTo = { operator: ['operator_machine', 'operator_calendar'] };
const hostOf = Object.fromEntries(Object.keys(attachedTo)
  .flatMap(kind => attachedTo[kind].map(family => [family, kind])));
// 只有导入导出、没有批量删除的文件家族，以及各自恢复后应该回到哪一页。
const importOnlyNode = { ...hostOf, work_calendar: 'calendar' };
const importOnlyKinds = Object.keys(importOnlyNode);
// 走日历文件对话框的家族：它们的导出范围是日期区间，不是列表的三档筛选。
const calendarFileKinds = ['work_calendar', 'operator_calendar'];
function familyLabel(family) {
  return calendarFileKinds.includes(family) ? APSCalendarFile.labels[family] : APSRelationFile.labels[family];
}
// 宿主给资源页的入口：按钮说要打开哪种维护向导，宿主挂出对应的对话框；回执与关闭再经 committed / close 交回发起方。
function hostEntries(open) {
  const openAttached = (mode, kind, request) => {
    // 一类基础资料可以挂多种附属资料，所以要打开哪一种由按钮自己说，主机不替它猜。
    if (!(attachedTo[kind] || []).includes(request && request.family))
      throw failure('这类基础资料没有这种可以用文件维护的附属资料。');
    return open(mode, request.family, request);
  };
  return {
    supports: (name, kind) => name === 'openCatalog' ? ['machine_group', 'shift_profile'].includes(kind)
      : ['openRelationImport', 'openRelationExport'].includes(name) ? !!(attachedTo[kind] || []).length
        : ['openImport', 'openExport', 'openBulk'].includes(name) && fileKinds.includes(kind),
    attachedFiles: kind => (attachedTo[kind] || []).map(family => ({ family, label: familyLabel(family) })),
    openImport: (kind, request) => open('import', kind, request),
    openExport: (kind, request) => open('export', kind, request),
    openBulk: (kind, request) => open('bulk', kind, request),
    openCatalog: (kind, request) => open('catalog', kind, request),
    openRelationImport: (kind, request) => openAttached('import', kind, request),
    openRelationExport: (kind, request) => openAttached('export', kind, request),
    openCalendarFile(mode, request) {
      if (!['import', 'export'].includes(mode)) throw failure('日历文件只支持导入和导出。');
      return open(mode, 'work_calendar', request);
    }
  };
}
function nodeFor(item, intent) {
  const kind = item.kind || (intent && intent.kind);
  return item.type === 'process' ? 'process' : item.type === 'calendar' ? 'calendar'
    : item.type === 'file_only' ? importOnlyNode[kind] : kind === 'op_type'
      ? intent && intent.category === 'external' ? 'op_ext' : 'op_int' : fileKinds.includes(kind) ? kind : 'material';
}
// 恢复时按这个顺序查各命名空间留下的待确认记录，查到的第一条就是要接着处理的。
const recoveryItems = [{ type: 'base', namespace: 'resources' },
  ...fileKinds.map(kind => ({ type: 'file', kind, namespace: kind + '_files' })),
  ...importOnlyKinds.map(kind => ({ type: 'file_only', kind, namespace: kind + '_files' })),
  { type: 'catalog', namespace: 'catalog' }, { type: 'calendar', namespace: 'calendar' }, { type: 'process', namespace: 'process' }];
function recovery() {
  let pending = null;
  for (const item of recoveryItems) {
    let intent;
    try { intent = APSResourceAPI.forNamespace(item.namespace).readPending(); }
    catch (error) { error.node = nodeFor(item, null); throw error; }
    if (intent) { pending = { ...item, intent }; break; }
  }
  if (!pending) return null;
  const intent = pending.intent, kind = pending.kind || intent.kind, node = nodeFor(pending, intent);
  const auxiliary = pending.type === 'file' ? { type: intent.kind === kind + '_bulk' ? 'bulk' : 'import', kind,
    request: { refs: [], scope: intent.category ? { category: intent.category } : {}, recovery: true } }
    : pending.type === 'file_only' ? { type: 'import', kind, request: { refs: [], scope: {}, recovery: true } }
      : pending.type === 'catalog' ? { type: 'catalog', kind, request: { recovery: true } } : null;
  return { node, auxiliary };
}
function ResourceLive({ onNavigate, initialContext }) {
  const [auxiliary, setAuxiliary] = React.useState(null), [revision, setRevision] = React.useState(0);
  const host = React.useMemo(() => hostEntries((type, kind, request) => { setHostError(null); setAuxiliary({ type, kind, request }); return { state: 'opened' }; }), []);
  const [boot] = React.useState(() => {
    const target = ResourceWorkspace.navigation(initialContext);
    try { return { target, recovery: recovery() }; }
    catch (error) { return { target, error }; }
  });
  const [hostError, setHostError] = React.useState(() => boot.error || null);
  const [deferred, setDeferred] = React.useState(() => !!boot.target.context && !!(boot.recovery || boot.error));
  const [initialNode, setInitialNode] = React.useState(() => boot.recovery ? boot.recovery.node : boot.error && boot.error.node ? boot.error.node : boot.target.node || 'material');
  const [navigationReady, setNavigationReady] = React.useState(false), [navigationKey, setNavigationKey] = React.useState(0);
  function retryRecovery() {
    if (auxiliary) return null;
    try {
      const pending = recovery();
      setHostError(null);
      if (pending) { setInitialNode(pending.node); if (pending.auxiliary) setAuxiliary(pending.auxiliary); }
      return pending;
    } catch (error) { if (error.node) setInitialNode(error.node); setHostError(error); return null; }
  }
  React.useEffect(() => { retryRecovery(); }, [auxiliary, navigationReady, revision]);
  function continueNavigation() {
    try {
      const pending = recovery();
      if (pending) {
        setInitialNode(pending.node); if (!auxiliary && pending.auxiliary) setAuxiliary(pending.auxiliary);
        throw failure('上次操作的结果还没确认，请先处理并关闭。');
      }
      if (auxiliary || !navigationReady) throw failure('请先关闭上次结果或处理未保存的草稿，再继续跳转。');
      setHostError(null); setDeferred(false); setInitialNode(boot.target.node); setNavigationKey(value => value + 1);
    } catch (error) { if (error.node) setInitialNode(error.node); setHostError(error); }
  }
  function committed(result) {
    if (auxiliary && auxiliary.type === 'catalog') setAuxiliary(null);
    if (auxiliary && typeof auxiliary.request.onCommitted === 'function') auxiliary.request.onCommitted(result);
    else setRevision(value => value + 1);
  }
  function close() {
    const current = auxiliary; setAuxiliary(null);
    if (!current) return;
    if (typeof current.request.onClosed === 'function') current.request.onClosed();
  }
  return <>
    <ErrorBox error={hostError || boot.target.error} />
    {deferred ? <div role="status" className="match-note is-block wb-resource-live-note"><p>上次操作还没处理完，暂时没有跳转到指定记录。刚才的提交没有被覆盖。</p>
      <Button icon="arrow-right" onClick={continueNavigation}>继续跳转</Button></div> : hostError ? <div role="status" className="match-note is-block wb-resource-live-note"><Button icon="refresh-cw" onClick={retryRecovery}>刷新上次操作记录</Button></div> : null}
    <ResourceWorkspace key={initialNode + ':' + navigationKey} host={host} onNavigate={onNavigate} initialNode={initialNode} externalRevision={revision}
      rememberEnabled={!auxiliary && !deferred && !hostError && !boot.target.error}
      initialContext={deferred || hostError ? undefined : boot.target.context} onNavigationReady={setNavigationReady}
      renderPart={({ onRefresh, initialContext, rememberEnabled }) => <ProcessWorkspace onCommitted={onRefresh} initialContext={initialContext} rememberEnabled={rememberEnabled} onNavigationReady={setNavigationReady} />}
      renderCalendar={({ onCommitted, externalRevision, initialContext, rememberEnabled, summaryState }) => <ResourceCalendar onCommitted={onCommitted} externalRevision={externalRevision} initialContext={initialContext} rememberEnabled={rememberEnabled} summaryState={summaryState} onNavigationReady={setNavigationReady}
        onOpenFile={(mode, context) => host.openCalendarFile(mode, { refs: [], scope: {}, ...context })} />} />
    {auxiliary && (auxiliary.type === 'catalog' ? <ResourceCatalog kind={auxiliary.kind} onClose={close} onCommitted={committed} /> :
      calendarFileKinds.includes(auxiliary.kind) ? <CalendarFileActions kind={auxiliary.kind} month={auxiliary.request.month} mode={auxiliary.type} request={auxiliary.request} onClose={close} onCommitted={committed} /> :
        importOnlyKinds.includes(auxiliary.kind) ? <RelationFileActions kind={auxiliary.kind} mode={auxiliary.type} request={auxiliary.request} onClose={close} onCommitted={committed} /> :
        auxiliary.kind === 'material' ? <ResourceMaterialActions mode={auxiliary.type} request={auxiliary.request} onClose={close} onCommitted={committed} /> :
          <ResourceFileActions kind={auxiliary.kind} mode={auxiliary.type} request={auxiliary.request} onClose={close} onCommitted={committed} />)}
  </>;
}

export { ResourceLive };
export default ResourceLive;
