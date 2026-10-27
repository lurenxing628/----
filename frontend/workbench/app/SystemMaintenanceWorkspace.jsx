(function () {
  'use strict';
  const A = window.SystemMaintenanceAPI, C = window.SystemMaintenanceControls;
  function useCommand(onChanged, revision) {
    const [initial] = React.useState(A.inspectPending), [intent, setIntent] = React.useState(initial.intent), [storageError, setStorageError] = React.useState(initial.storageError);
    const [result, setResult] = React.useState(null), [error, setError] = React.useState(null), [busy, setBusy] = React.useState(false);
    const [host, setHost] = React.useState(null), [hostError, setHostError] = React.useState(null), [hostBusy, setHostBusy] = React.useState(true);
    const startedHere = React.useRef(false), hostSequence = React.useRef(0);
    const [selection, setSelection] = React.useState(null);
    const current = React.useRef(intent), found = React.useRef(null), running = React.useRef(false), mounted = React.useRef(true), changed = React.useRef(onChanged);
    changed.current = onChanged;
    function settle(value) { found.current = value; if (mounted.current) { setResult(value); if (value && value.host) setHost(value.host); } }
    async function inspectHost() {
      const sequence = ++hostSequence.current;
      if (mounted.current) setHostBusy(true);
      try { const value = await A.host(); if (mounted.current && sequence === hostSequence.current) { setHost(value); setHostError(null); } return value; }
      catch (problem) { if (mounted.current && sequence === hostSequence.current) setHostError(problem); return null; }
      finally { if (mounted.current && sequence === hostSequence.current) setHostBusy(false); }
    }
    async function lookup() {
      const original = current.current; if (!original || running.current) return;
      if (found.current && found.current.kind === 'rejected') return inspectHost();
      running.current = true; setBusy(true); setError(null);
      try { settle(await A.lookup(original)); }
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
          setStorageError(new Error('本机存的上次操作记录已变化，页面仍然停在等待确认的状态。请不要再操作，联系维护人员。'));
          lookup(); return;
        }
        if (!state.storageError && !current.current) {
          current.current = state.intent; setIntent(state.intent); settle(null); setError(null);
        }
        if (state.intent) lookup(); else inspectHost();
      }
      reload();
      window.addEventListener('online', reload); window.addEventListener('storage', reload);
      return () => { mounted.current = false; window.removeEventListener('online', reload); window.removeEventListener('storage', reload); };
    }, [revision]);
    async function execute(action, token, input, selected = null) {
      if (running.current || current.current || storageError || !host || hostError || host.state !== 'ready' || !host.operations_available) return;
      let original;
      try { original = A.pending().begin(action); } catch (problem) { setStorageError(problem); return; }
      startedHere.current = action === 'restore';
      setSelection(selected);
      current.current = original; setIntent(original); settle(null); setError(null); setBusy(true); running.current = true;
      try { settle(await A.command(original, token, input)); }
      catch (problem) {
        if (mounted.current) setError(problem);
        if (window.APSWorkbenchTransport.rejected(problem)) {
          settle({ kind: 'rejected', terminal: true, intent: original });
          try {
            A.pending().finish(original); current.current = null;
            if (mounted.current) setIntent(null);
          } catch (storageProblem) { if (mounted.current) setStorageError(storageProblem); }
        }
      } finally { await inspectHost(); running.current = false; if (mounted.current) setBusy(false); }
    }
    const restorePending = !!(intent && intent.action === 'restore' && !(result && result.terminal
      && (result.kind === 'rejected' || !startedHere.current)));
    const maintenanceRequired = restorePending || !!(host && host.state !== 'ready');
    const suspended = maintenanceRequired || !!hostError || !host;
    const readReason = maintenanceRequired ? host && host.state !== 'ready' ? window.SystemRestoreStatus.hostLabels[host.state] : '恢复请求结果待确认。'
      : hostError ? hostError.message : !host ? '正在查询维护状态。' : '';
    const lockedReason = storageError ? storageError.message : readReason || (intent ? intent.summary + '结果待确认，请查询结果。'
      : busy ? '正在执行维护操作。' : !host.operations_available ? '当前维护操作暂不可用，请重新查询状态。' : '');
    function acknowledge() {
      if (suspended || running.current || !current.current || !found.current || !found.current.terminal) return;
      try { A.pending().finish(current.current); } catch (problem) { setStorageError(problem); return; }
      const original = current.current, completed = found.current;
      current.current = null; setIntent(null); settle(null); setError(null); setStorageError(null); changed.current(original, completed);
    }
    return { intent, result, error, storageError, busy, host, hostError, hostBusy, suspended, readReason, maintenanceRequired, inspectHost, selection, lockedReason,
      locked: !!lockedReason, execute, lookup, acknowledge };
  }
  // Keep this component mounted across tab changes: it owns the system-only original request.
  // 系统管理只读本机数据，没有别的数据来源可切换。
  function Workspace({ tab, theme, onSetTheme, pageSize, onPageSize, compact, onCompact, revision, onChanged, onReadSuspendedChange, recordContexts, onRecordContext, children }) {
    const [version, refresh] = React.useReducer(value => value + 1, 0);
    const command = useCommand((intent, result) => { refresh(); onChanged(intent, result); }, revision);
    const suspended = command.suspended;
    React.useLayoutEffect(() => { onReadSuspendedChange(suspended, command.readReason); }, [suspended, command.readReason, onReadSuspendedChange]);
    const enabled = !suspended, serial = revision + ':' + version;
    const [visited, setVisited] = React.useState({});
    React.useEffect(() => { if (enabled && ['backups', 'logs', 'config'].includes(tab)) setVisited(value => ({ ...value, [tab]: true })); }, [enabled, tab]);
    return <div className="sm-maintenance-workspace sm-maintenance-workspace-flush plana" data-system-maintenance="v1">

      {command.maintenanceRequired ? <window.SystemRestorePanel command={command} theme={theme} onSetTheme={onSetTheme} /> : <>
        {command.hostError && <section className="sm-section sm-notice sm-tone-danger" role="alert" data-system-status-error>
          <h3>维护状态查询失败</h3><p>{command.hostError.message}</p>
          <div className="sm-actions"><C.Button icon="refresh-cw" busy={command.hostBusy} onClick={command.inspectHost}>重新查询</C.Button>
            <a href="/workbench?view=dashboard">返回工作台</a></div>
        </section>}
        {!command.hostError && command.host && !command.host.operations_available && <div className="sm-actions">
          <C.Button icon="refresh-cw" busy={command.hostBusy} onClick={command.inspectHost}>重新查询维护状态</C.Button>
        </div>}
        <C.Outcome command={command} />
      </>}
      {!command.maintenanceRequired && command.hostBusy && <p className="sm-note" role="status">正在查询维护状态…</p>}
      {tab === 'overview' && !suspended && children}
      {['backups', 'logs'].map(kind => visited[kind] || enabled && tab === kind ? <div key={kind} hidden={!enabled || tab !== kind}>
        <window.SystemMaintenanceRecords kind={kind} pageSize={pageSize} onPageSize={onPageSize} revision={serial} command={command} active={enabled && tab === kind}
          initialContext={recordContexts[kind]} onReadContext={onRecordContext} />
      </div> : null)}
      {(visited.config || enabled && tab === 'config') && <div hidden={!enabled || tab !== 'config'}><window.SystemMaintenanceConfig revision={serial} command={command} active={enabled && tab === 'config'}
        theme={theme} onSetTheme={onSetTheme} pageSize={pageSize} onPageSize={onPageSize} compact={compact} onCompact={onCompact} /></div>}
    </div>;
  }
  window.SystemMaintenanceWorkspace = Workspace;
})();
