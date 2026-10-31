(function () {
  'use strict';
  const A = window.SystemMaintenanceAPI, C = window.SystemMaintenanceControls, T = window.APSWorkbenchTransport;
  function useCommand(onChanged, revision) {
    const [initial] = React.useState(A.inspectPending), [intent, setIntent] = React.useState(initial.intent), [storageError, setStorageError] = React.useState(initial.storageError);
    const [result, setResult] = React.useState(initial.result || null), [error, setError] = React.useState(initial.error || null), [busy, setBusy] = React.useState(false);
    const [host, setHost] = React.useState(initial.result && initial.result.host ? initial.result.host : null), [hostError, setHostError] = React.useState(null), [hostBusy, setHostBusy] = React.useState(true);
    const startedHere = React.useRef(Boolean(initial.startedHere)), hostSequence = React.useRef(0);
    const [selection, setSelection] = React.useState(initial.selection || null);
    const current = React.useRef(initial.intent), found = React.useRef(initial.result || null), running = React.useRef(false), mounted = React.useRef(true), changed = React.useRef(onChanged);
    changed.current = onChanged;
    function settle(value, targetIntent, problem = null) {
      if (!current.current || current.current.request_key !== targetIntent.request_key) return false;
      if (!A.pending().settle(targetIntent, value, problem)) return false;
      found.current = value;
      if (mounted.current) { setResult(value); if (value && value.host) setHost(value.host); }
      return true;
    }
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
      // 查询在锁外，查询结论（或查询失败）写回本页记录在跨页互斥里做。
      let value, problem = null;
      try { value = await A.lookup(original); } catch (error) { problem = error; }
      try {
        await T.exclusive(A.PENDING_KEY, { wait: true }, () => {
          if (!problem) settle(value, original);
          else if (current.current && current.current.request_key === original.request_key && A.pending().settle(original, found.current, problem) && mounted.current) setError(problem);
        });
      } catch (error) { if (mounted.current) setError(error); }
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
        startedHere.current = Boolean(state.startedHere);
        setSelection(state.selection);
        if (!state.storageError && !current.current) {
          current.current = state.intent; setIntent(state.intent);
          found.current = state.result || null; setResult(state.result || null); setError(state.error || null);
          if (state.result && state.result.host) setHost(state.result.host);
        } else if (current.current && state.intent && state.intent.request_key === current.current.request_key && state.result) {
          found.current = state.result; setResult(state.result);
          if (state.error) setError(state.error);
          if (state.result.host) setHost(state.result.host);
        }
        if (state.intent && !(state.result && state.result.terminal)) lookup(); else inspectHost();
      }
      reload();
      window.addEventListener('online', reload); window.addEventListener('storage', reload);
      return () => { mounted.current = false; window.removeEventListener('online', reload); window.removeEventListener('storage', reload); };
    }, [revision]);
    async function execute(action, token, input, selected = null) {
      if (running.current || current.current || storageError || !host || hostError || host.state !== 'ready' || !host.operations_available) return;
      let original;
      running.current = true;
      try {
        // 维护操作的本机记录、提交和结果写回在跨页互斥里串行，持锁跨过维护命令。
        const { acquired } = await T.exclusive(A.PENDING_KEY, {}, async () => {
          try { original = A.pending().begin(action, selected); } catch (problem) { setStorageError(problem); return; }
          startedHere.current = action === 'restore';
          setSelection(selected);
          current.current = original; setIntent(original); settle(null, original); setError(null); setBusy(true);
          try { settle(await A.command(original, token, input), original); }
          catch (problem) {
            if (current.current && current.current.request_key === original.request_key) {
              if (T.rejected(problem)) {
                if (settle({ kind: 'rejected', terminal: true, intent: original }, original, problem)) {
                  if (mounted.current) setError(problem);
                  try {
                    A.pending().finish(original); current.current = null;
                    if (mounted.current) setIntent(null);
                  } catch (storageProblem) { if (mounted.current) setStorageError(storageProblem); }
                }
              } else if (A.pending().settle(original, null, problem) && mounted.current) {
                setError(problem);
              }
            }
          }
        });
        if (!acquired && mounted.current) setError(new Error('另一个页面正在处理维护操作，请稍后重试。'));
      } catch (problem) { if (mounted.current) setError(problem); }
      finally { if (original) await inspectHost(); running.current = false; if (mounted.current) setBusy(false); }
    }
    const restorePending = !!(intent && intent.action === 'restore' && !(result && result.terminal
      && (result.kind === 'rejected' || !startedHere.current)));
    const maintenanceRequired = restorePending || !!(host && host.state !== 'ready');
    const suspended = maintenanceRequired || !!hostError || !host;
    const readReason = maintenanceRequired ? host && host.state !== 'ready' ? window.SystemRestoreStatus.hostLabels[host.state] : '恢复请求结果待确认。'
      : hostError ? hostError.message : !host ? '正在查询维护状态。' : '';
    const lockedReason = storageError ? storageError.message : readReason || (intent ? intent.summary + '结果待确认，请查询结果。'
      : busy ? '正在执行维护操作。' : !host.operations_available ? '当前维护操作暂不可用，请重新查询状态。' : '');
    async function acknowledge() {
      if (suspended || running.current || !current.current || !found.current || !found.current.terminal) return;
      const original = current.current, completed = found.current;
      running.current = true;
      try { await T.exclusive(A.PENDING_KEY, { wait: true }, () => A.pending().finish(original, true)); }
      catch (problem) { setStorageError(problem); return; }
      finally { running.current = false; }
      current.current = null; found.current = null; startedHere.current = false;
      setIntent(null); setResult(null); setError(null); setStorageError(null);
      if (completed.kind !== 'rejected') changed.current(original, completed);
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
      {(visited.config || enabled && tab === 'config') && <div hidden={!enabled || tab !== 'config'}><window.SystemMaintenanceConfig revision={serial} command={command} active={enabled && tab === 'config'} tab={tab}
        theme={theme} onSetTheme={onSetTheme} pageSize={pageSize} onPageSize={onPageSize} compact={compact} onCompact={onCompact} /></div>}
    </div>;
  }
  window.SystemMaintenanceWorkspace = Workspace;
})();
