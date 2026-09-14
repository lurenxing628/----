(function () {
  'use strict';
  const fileKinds = ['material', 'op_type', 'machine', 'operator', 'supplier'];
  function fileAdapter(kind) {
    const adapter = window.APSResourceAPI.create(kind + '_files');
    adapter.command = (commandKind, action, ref, body, signal) => {
      if (![kind + '_import', kind + '_bulk'].includes(commandKind) || action !== 'confirm'
          || !body || !body.input || body.input.preview_ref !== ref)
        throw window.APSResourceContract.failure('确认操作与当前预检结果不一致。');
      return adapter.execute(commandKind === kind + '_import' ? 'imports/' + kind + '/confirm' : 'entities/' + kind + '/bulk-confirm', body, signal);
    };
    return adapter;
  }
  function recovery(adapters) {
    const pending = [{ type: 'base', adapter: adapters.base }, ...fileKinds.map(kind => ({ type: 'file', kind, adapter: adapters.files[kind] })),
      { type: 'catalog', adapter: adapters.catalog }, { type: 'calendar', adapter: adapters.calendar }, { type: 'process', adapter: adapters.process }]
      .map(item => ({ ...item, intent: typeof item.adapter.readPending === 'function' && item.adapter.readPending() })).find(item => item.intent);
    if (!pending) return null;
    const intent = pending.intent, kind = pending.kind || intent.kind;
    const node = pending.type === 'process' ? 'process' : pending.type === 'calendar' ? 'calendar' : kind === 'op_type'
      ? intent.category === 'external' ? 'op_ext' : 'op_int' : fileKinds.includes(kind) ? kind : 'material';
    const auxiliary = pending.type === 'file' ? { type: intent.kind === kind + '_bulk' ? 'bulk' : 'import', kind,
      request: { refs: [], scope: intent.category ? { category: intent.category } : {}, recovery: true } }
      : pending.type === 'catalog' ? { type: 'catalog', kind, request: { recovery: true } } : null;
    return { node, auxiliary };
  }
  function ResourceLive({ onNavigate, initialContext }) {
    const [auxiliary, setAuxiliary] = React.useState(null), [revision, setRevision] = React.useState(0);
    const [hostError, setHostError] = React.useState(null);
    const adapters = React.useMemo(() => {
      const base = window.APSResourceAPI.create(), calendar = window.APSResourceAPI.create('calendar');
      const files = Object.fromEntries(fileKinds.map(kind => [kind, fileAdapter(kind)])), catalog = window.APSResourceAPI.create('catalog');
      calendar.command = (kind, action, ref, body, signal) => {
        if (kind !== 'calendar' || !['upsert', 'delete', 'confirm'].includes(action)) throw window.APSResourceContract.failure('工作日历操作不正确。');
        return calendar.execute('calendar/' + (action === 'confirm' ? 'range/confirm' : action), body, signal);
      };
      const open = (type, kind, request) => { setHostError(null); setAuxiliary({ type, kind, request }); return { state: 'opened' }; };
      base.supports = (name, kind) => name === 'openCatalog' ? ['machine_group', 'shift_profile'].includes(kind)
        : ['openImport', 'openExport', 'openBulk'].includes(name) && fileKinds.includes(kind);
      base.openImport = (kind, request) => open('import', kind, request);
      base.openExport = (kind, request) => open('export', kind, request);
      base.openBulk = (kind, request) => open('bulk', kind, request);
      base.openCatalog = (kind, request) => open('catalog', kind, request);
      return { base, calendar, files, catalog, process: window.APSProcessAPI.create(base) };
    }, []);
    const [boot] = React.useState(() => {
      const target = window.ResourceWorkspace.navigation(initialContext);
      try { return { target, recovery: recovery(adapters) }; }
      catch (error) { return { target, error }; }
    });
    const [deferred, setDeferred] = React.useState(() => !!boot.target.context && !!(boot.recovery || boot.error));
    const [initialNode, setInitialNode] = React.useState(() => boot.recovery ? boot.recovery.node : boot.target.node || 'material');
    const [navigationReady, setNavigationReady] = React.useState(false), [navigationKey, setNavigationKey] = React.useState(0);
    React.useEffect(() => {
      if (auxiliary) return;
      try {
        const pending = recovery(adapters);
        if (pending) { setInitialNode(pending.node); if (pending.auxiliary) setAuxiliary(pending.auxiliary); }
      } catch (error) { setHostError(error); }
    }, [adapters, auxiliary]);
    function continueNavigation() {
      try {
        const pending = recovery(adapters);
        if (pending) {
          setInitialNode(pending.node); if (!auxiliary && pending.auxiliary) setAuxiliary(pending.auxiliary);
          throw window.APSResourceContract.failure('上次操作的结果还没确认，请先处理并关闭。');
        }
        if (auxiliary || !navigationReady) throw window.APSResourceContract.failure('请先关闭上次结果或处理未保存的草稿，再继续跳转。');
        setHostError(null); setDeferred(false); setInitialNode(boot.target.node); setNavigationKey(value => value + 1);
      } catch (error) { setHostError(error); }
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
      <window.ResourceControls.ErrorBox error={hostError || boot.target.error || boot.error} />
      {deferred && <div role="status" className="match-note" style={{ display: 'block', margin: 12 }}><p>上次操作还没处理完，暂时没有跳转到指定记录。刚才的提交没有被覆盖。</p>
        <window.ResourceControls.Button icon="arrow-right" onClick={continueNavigation}>继续跳转</window.ResourceControls.Button></div>}
      <ResourceWorkspace key={initialNode + ':' + navigationKey} adapter={adapters.base} onNavigate={onNavigate} initialNode={initialNode} externalRevision={revision}
        rememberEnabled={!auxiliary && !deferred && !hostError && !boot.error && !boot.target.error}
        initialContext={deferred || boot.error ? undefined : boot.target.context} onNavigationReady={setNavigationReady}
        renderPart={({ onRefresh, initialContext, rememberEnabled }) => <window.ProcessWorkspace adapter={adapters.process} onCommitted={onRefresh} initialContext={initialContext} rememberEnabled={rememberEnabled} onNavigationReady={setNavigationReady} />}
        renderCalendar={({ onCommitted, initialContext, rememberEnabled }) => <window.ResourceCalendar adapter={adapters.calendar} onCommitted={onCommitted} initialContext={initialContext} rememberEnabled={rememberEnabled} onNavigationReady={setNavigationReady} />} />
      {auxiliary && (auxiliary.type === 'catalog' ? <window.ResourceCatalog kind={auxiliary.kind} adapter={adapters.catalog} onClose={close} onCommitted={committed} /> :
        auxiliary.kind === 'material' ? <window.ResourceMaterialActions mode={auxiliary.type} request={auxiliary.request} adapter={adapters.files.material} onClose={close} onCommitted={committed} /> :
          <window.ResourceFileActions kind={auxiliary.kind} mode={auxiliary.type} request={auxiliary.request} adapter={adapters.files[auxiliary.kind]} onClose={close} onCommitted={committed} />)}
    </>;
  }
  window.ResourceLive = ResourceLive;
})();
