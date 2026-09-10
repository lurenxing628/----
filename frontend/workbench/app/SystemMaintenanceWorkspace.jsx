(function () {
  'use strict';
  const A = window.SystemMaintenanceAPI, C = window.SystemMaintenanceControls;
  function useCommand(api, onChanged) {
    const [initial] = React.useState(A.inspectPending), [intent, setIntent] = React.useState(initial.intent), [storageError, setStorageError] = React.useState(initial.storageError);
    const [result, setResult] = React.useState(null), [error, setError] = React.useState(null), [busy, setBusy] = React.useState(false);
    const [host, setHost] = React.useState(null), [hostError, setHostError] = React.useState(null), [hostBusy, setHostBusy] = React.useState(true);
    const startedHere = React.useRef(false);
    const [selection, setSelection] = React.useState(null);
    const current = React.useRef(intent), found = React.useRef(null), running = React.useRef(false), mounted = React.useRef(true), changed = React.useRef(onChanged);
    changed.current = onChanged;
    function settle(value) { found.current = value; if (mounted.current) { setResult(value); if (value && value.host) setHost(value.host); } }
    async function inspectHost() {
      if (mounted.current) setHostBusy(true);
      try { const value = await api.host(); if (mounted.current) { setHost(value); setHostError(null); } return value; }
      catch (problem) { if (mounted.current) setHostError(problem); return null; }
      finally { if (mounted.current) setHostBusy(false); }
    }
    async function lookup() {
      const original = current.current; if (!original || running.current) return;
      running.current = true; setBusy(true); setError(null);
      try { settle(await api.lookup(original, found.current && found.current.kind === 'file_operation' ? found.current.operation.job_ref : null)); }
      catch (problem) { if (mounted.current) setError(problem); }
      finally { await inspectHost(); running.current = false; if (mounted.current) setBusy(false); }
    }
    React.useEffect(() => {
      mounted.current = true;
      function reload(event) {
        if (event && event.type === 'storage' && event.key !== A.PENDING_KEY && event.key !== null) return;
        if (running.current) return;
        const state = A.inspectPending(); setStorageError(state.storageError);
        if (current.current && (!state.intent || state.intent.request_key !== current.current.request_key)) {
          setStorageError(new Error('原请求的本机记录已变化，未释放待核实状态；请保留现场并核实原请求。'));
          lookup(); return;
        }
        if (!state.storageError && !current.current) {
          current.current = state.intent; setIntent(state.intent); settle(null); setError(null);
        }
        if (state.intent) lookup();
      }
      if (current.current) lookup(); else inspectHost();
      window.addEventListener('online', reload); window.addEventListener('storage', reload);
      return () => { mounted.current = false; window.removeEventListener('online', reload); window.removeEventListener('storage', reload); };
    }, [api]);
    async function execute(action, token, input, selected = null) {
      if (running.current || current.current || storageError || !host || hostError || host.state !== 'ready' || !host.operations_available) return;
      let original;
      try { original = A.pending().begin(action); } catch (problem) { setStorageError(problem); return; }
      startedHere.current = action === 'restore';
      setSelection(selected);
      current.current = original; setIntent(original); settle(null); setError(null); setBusy(true); running.current = true;
      try { settle(await api.command(original, token, input)); }
      catch (problem) {
        if (mounted.current) setError(problem);
        if (problem.rejected) settle({ kind: 'rejected', terminal: true });
      } finally { await inspectHost(); running.current = false; if (mounted.current) setBusy(false); }
    }
    const restorePending = !!(intent && intent.action === 'restore' && !(result && result.terminal
      && (result.kind === 'rejected' || !startedHere.current)));
    const suspended = !!storageError || !!hostError || !host || host.state !== 'ready' || restorePending;
    function acknowledge() {
      if (suspended || running.current || !current.current || !found.current || !found.current.terminal) return;
      try { A.pending().finish(current.current); } catch (problem) { setStorageError(problem); return; }
      const original = current.current, completed = found.current;
      current.current = null; setIntent(null); settle(null); setError(null); setStorageError(null); changed.current(original, completed);
    }
    return { intent, result, error, storageError, busy, host, hostError, hostBusy, suspended, inspectHost, selection,
      locked: suspended || !!intent || busy || !host.operations_available, execute, lookup, acknowledge };
  }
  // Keep this component mounted across tab/source changes: it owns the system-only original request.
  function Workspace({ tab, source = 'current', theme, onSetTheme, pageSize, onPageSize, compact, onCompact, revision = 0, onChanged, onReadSuspendedChange, recordContexts = {}, onRecordContext, api: supplied, children }) {
    const api = React.useMemo(() => supplied || A.create(), [supplied]);
    const [version, refresh] = React.useReducer(value => value + 1, 0);
    const command = useCommand(api, (intent, result) => { refresh(); if (onChanged) onChanged(intent, result); });
    const suspended = command.suspended;
    React.useLayoutEffect(() => { if (onReadSuspendedChange) onReadSuspendedChange(suspended); }, [suspended, onReadSuspendedChange]);
    const current = source === 'current', enabled = current && !suspended, serial = revision + ':' + version;
    const [visited, setVisited] = React.useState({});
    React.useEffect(() => { if (enabled && ['backups', 'logs', 'config'].includes(tab)) setVisited(value => ({ ...value, [tab]: true })); }, [enabled, tab]);
    return <div className="sm-maintenance-workspace plana" data-system-maintenance="v1" style={{ padding: 0, maxWidth: 'none', borderRadius: 0 }}>
      <C.Styles />
      {suspended && !(command.hostBusy && !command.intent && !command.hostError && !command.storageError && !command.host)
        ? <window.SystemRestorePanel command={command} api={api} theme={theme} onSetTheme={onSetTheme} /> : <C.Outcome command={command} />}
      {suspended && command.hostBusy && !command.intent && <p className="sm-note" role="status">正在核查软件维护状态，尚未读取数据库。</p>}
      {(!current || tab === 'overview') && !suspended && children}
      {['backups', 'logs'].map(kind => visited[kind] || enabled && tab === kind ? <div key={kind} hidden={!enabled || tab !== kind}>
        <window.SystemMaintenanceRecords api={api} kind={kind} pageSize={pageSize} onPageSize={onPageSize} revision={serial} command={command} active={enabled && tab === kind}
          initialContext={recordContexts[kind]} onReadContext={onRecordContext} />
      </div> : null)}
      {(visited.config || enabled && tab === 'config') && <div hidden={!enabled || tab !== 'config'}><window.SystemMaintenanceConfig api={api} revision={serial} command={command} active={enabled && tab === 'config'}
        theme={theme} onSetTheme={onSetTheme} pageSize={pageSize} onPageSize={onPageSize} compact={compact} onCompact={onCompact} /></div>}
    </div>;
  }
  window.SystemMaintenanceWorkspace = Workspace;
})();
