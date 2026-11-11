import React from './shared/runtime/react.js';
import A from './SystemMaintenanceAPI.js';
import C from './SystemMaintenanceControls.jsx';
import T from './shared/network/transport.js';
import { exclusive } from './shared/session/pending-store.js';
import SystemRestoreStatus from './SystemRestoreStatus.js';
import SystemRestorePanel from './SystemRestorePanel.jsx';
import SystemMaintenanceRecords from './SystemMaintenanceRecords.jsx';
import SystemMaintenanceConfig from './SystemMaintenanceConfig.jsx';

function useCommand(onChanged, revision) {
  const [initial] = React.useState(A.inspectPending), [intent, setIntent] = React.useState(initial.intent), [storageError, setStorageError] = React.useState(initial.storageError);
  const [result, setResult] = React.useState(initial.result || null), [error, setError] = React.useState(initial.error || null), [busy, setBusy] = React.useState(false);
  const [host, setHost] = React.useState(initial.result && initial.result.host ? initial.result.host : null), [hostError, setHostError] = React.useState(null), [hostBusy, setHostBusy] = React.useState(true);
  const startedHere = React.useRef(Boolean(initial.startedHere)), hostSequence = React.useRef(0);
  const [selection, setSelection] = React.useState(initial.selection || null);
  const current = React.useRef(initial.intent), found = React.useRef(initial.result || null), running = React.useRef(false), mounted = React.useRef(true), changed = React.useRef(onChanged);
  changed.current = onChanged;
  const ctx = {
    current, found, startedHere, hostSequence, running, mounted, changed,
    setIntent, setStorageError, setResult, setError, setBusy, setHost, setHostError, setHostBusy, setSelection
  };
  const inspectHost = () => runInspectHost(ctx);
  const rereadStorage = () => runRereadStorage(ctx);
  async function lookup() {
    const original = current.current; if (!original || running.current) return;
    const snap = A.pending.session();
    if (found.current && found.current.terminal && (snap.storageError || snap.dismissPending || storageError)) return rereadStorage();
    if (found.current && found.current.kind === 'rejected') return inspectHost();
    return runLookupNetwork(ctx, original);
  }
  React.useEffect(() => {
    mounted.current = true;
    const reload = () => reloadCommandState(ctx, lookup, inspectHost);
    reload();
    const unsubscribe = A.pending.subscribe(reload); window.addEventListener('online', reload);
    return () => { mounted.current = false; window.removeEventListener('online', reload); unsubscribe(); };
  }, [revision]);
  const execute = (action, token, input, selected = null) => {
    if (running.current || current.current || storageError || !host || hostError || host.state !== 'ready' || !host.operations_available) return undefined;
    return runExecuteCommand(ctx, action, token, input, selected);
  };
  const restorePending = !!(intent && intent.action === 'restore' && !(result && result.terminal
    && (result.kind === 'rejected' || !startedHere.current)));
  const maintenanceRequired = restorePending || !!(host && host.state !== 'ready');
  const suspended = maintenanceRequired || !!hostError || !host;
  const readReason = maintenanceRequired ? host && host.state !== 'ready' ? SystemRestoreStatus.hostLabels[host.state] : '恢复请求结果待确认。'
    : hostError ? hostError.message : !host ? '正在查询维护状态。' : '';
  const lockedReason = storageError ? storageError.message : readReason || (intent ? intent.summary + '结果待确认，请查询结果。'
    : busy ? '正在执行维护操作。' : !host.operations_available ? '当前维护操作暂不可用，请重新查询状态。' : '');
  const acknowledge = () => runAcknowledge(ctx, suspended);
  return { intent, result, error, storageError, busy, host, hostError, hostBusy, suspended, readReason, maintenanceRequired, inspectHost, selection, lockedReason,
    locked: !!lockedReason, execute, lookup, acknowledge, rereadStorage };
}

function settleCommand(ctx, value, targetIntent, problem = null) {
  if (!ctx.current.current || ctx.current.current.request_key !== targetIntent.request_key) return false;
  if (!A.pending.settle(targetIntent, value, problem)) return false;
  ctx.found.current = value;
  if (ctx.mounted.current) { ctx.setResult(value); if (value && value.host) ctx.setHost(value.host); }
  return true;
}

function completeDismissal(ctx, original, completed) {
  ctx.current.current = null; ctx.found.current = null; ctx.startedHere.current = false;
  if (ctx.mounted.current) {
    ctx.setIntent(null); ctx.setResult(null); ctx.setError(null); ctx.setStorageError(null); ctx.setSelection(null);
  }
  if (completed && completed.kind !== 'rejected') ctx.changed.current(original, completed);
}

async function runInspectHost(ctx) {
  const sequence = ++ctx.hostSequence.current;
  if (ctx.mounted.current) ctx.setHostBusy(true);
  try {
    const value = await A.host();
    if (ctx.mounted.current && sequence === ctx.hostSequence.current) { ctx.setHost(value); ctx.setHostError(null); }
    return value;
  } catch (problem) {
    if (ctx.mounted.current && sequence === ctx.hostSequence.current) ctx.setHostError(problem);
    return null;
  } finally {
    if (ctx.mounted.current && sequence === ctx.hostSequence.current) ctx.setHostBusy(false);
  }
}

async function runLookupNetwork(ctx, original) {
  ctx.running.current = true; ctx.setBusy(true); ctx.setError(null);
  // 查询在锁外，查询结论（或查询失败）写回本页记录在跨页互斥里做。
  let value, problem = null;
  try { value = await A.lookup(original); } catch (error) { problem = error; }
  try {
    await exclusive(A.PENDING_KEY, { wait: true }, () => {
      if (!problem) settleCommand(ctx, value, original);
      else if (ctx.current.current && ctx.current.current.request_key === original.request_key
        && A.pending.settle(original, ctx.found.current, problem) && ctx.mounted.current) ctx.setError(problem);
    });
  } catch (error) { if (ctx.mounted.current) ctx.setError(error); }
  finally { await runInspectHost(ctx); ctx.running.current = false; if (ctx.mounted.current) ctx.setBusy(false); }
}

async function runRereadStorage(ctx) {
  if (ctx.running.current) return;
  const prev = A.pending.session();
  const original = ctx.current.current || prev.intent, completed = ctx.found.current || prev.result;
  const wasDismissing = Boolean(prev.dismissPending && original && completed && completed.terminal);
  ctx.running.current = true; if (ctx.mounted.current) ctx.setBusy(true);
  let lookupIntent = null;
  try {
    const { value: disk } = await exclusive(A.PENDING_KEY, { wait: true }, () => A.pending.flush());
    if (wasDismissing && !disk) {
      completeDismissal(ctx, original, completed);
    } else {
      const next = A.pending.session();
      ctx.current.current = next.intent; ctx.found.current = next.result; ctx.startedHere.current = next.startedHere;
      if (ctx.mounted.current) {
        ctx.setIntent(next.intent); ctx.setResult(next.result); ctx.setError(next.error);
        ctx.setStorageError(next.storageError); ctx.setSelection(next.selection);
        if (next.result && next.result.host) ctx.setHost(next.result.host);
      }
      if (next.intent && !(next.result && next.result.terminal)) lookupIntent = next.intent;
    }
  } catch (problem) {
    if (ctx.mounted.current) ctx.setStorageError(problem);
  } finally {
    if (!lookupIntent) {
      await runInspectHost(ctx);
      ctx.running.current = false;
      if (ctx.mounted.current) ctx.setBusy(false);
    }
  }
  if (lookupIntent) await runLookupNetwork(ctx, lookupIntent);
}

function reloadCommandState(ctx, lookup, inspectHost) {
  if (ctx.running.current) return;
  const state = A.inspectPending(); ctx.setStorageError(state.storageError);
  if (ctx.current.current && (!state.intent || state.intent.request_key !== ctx.current.current.request_key)) {
    const rejectedSame = Boolean(!state.intent && state.result && state.result.kind === 'rejected'
      && state.result.intent && state.result.intent.request_key === ctx.current.current.request_key);
    if (rejectedSame) {
      ctx.current.current = null; ctx.found.current = state.result;
      ctx.setIntent(null); ctx.setResult(state.result); ctx.setError(state.error || null);
      inspectHost(); return;
    }
    ctx.setStorageError(new Error('本机存的上次操作记录已变化，页面仍然停在等待确认的状态。请不要再操作，联系维护人员。'));
    lookup(); return;
  }
  ctx.startedHere.current = Boolean(state.startedHere);
  ctx.setSelection(state.selection);
  if (!state.storageError && !ctx.current.current) {
    ctx.current.current = state.intent; ctx.setIntent(state.intent);
    ctx.found.current = state.result || null; ctx.setResult(state.result || null); ctx.setError(state.error || null);
    if (state.result && state.result.host) ctx.setHost(state.result.host);
  } else if (ctx.current.current && state.intent && state.intent.request_key === ctx.current.current.request_key && state.result) {
    ctx.found.current = state.result; ctx.setResult(state.result);
    if (state.error) ctx.setError(state.error);
    if (state.result.host) ctx.setHost(state.result.host);
  }
  if (state.intent && !(state.result && state.result.terminal)) lookup(); else inspectHost();
}

async function runExecuteCommand(ctx, action, token, input, selected) {
  let original;
  ctx.running.current = true;
  try {
    // 维护操作的本机记录、提交和结果写回在跨页互斥里串行，持锁跨过维护命令。
    const { acquired } = await exclusive(A.PENDING_KEY, {}, async () => {
      try { original = A.pending.begin(action, selected); } catch (problem) { ctx.setStorageError(problem); return; }
      ctx.startedHere.current = action === 'restore';
      ctx.setSelection(selected);
      ctx.current.current = original; ctx.setIntent(original); settleCommand(ctx, null, original); ctx.setError(null); ctx.setBusy(true);
      try { settleCommand(ctx, await A.command(original, token, input), original); }
      catch (problem) {
        if (ctx.current.current && ctx.current.current.request_key === original.request_key) {
          if (T.rejected(problem)) {
            if (settleCommand(ctx, { kind: 'rejected', terminal: true, intent: original }, original, problem)) {
              if (ctx.mounted.current) ctx.setError(problem);
              try {
                A.pending.finish(original); ctx.current.current = null;
                if (ctx.mounted.current) ctx.setIntent(null);
              } catch (storageProblem) { if (ctx.mounted.current) ctx.setStorageError(storageProblem); }
            }
          } else if (A.pending.settle(original, null, problem) && ctx.mounted.current) {
            ctx.setError(problem);
          }
        }
      }
    });
    if (!acquired && ctx.mounted.current) ctx.setError(new Error('另一个页面正在处理维护操作，请稍后重试。'));
  } catch (problem) { if (ctx.mounted.current) ctx.setError(problem); }
  finally { if (original) await runInspectHost(ctx); ctx.running.current = false; if (ctx.mounted.current) ctx.setBusy(false); }
}

async function runAcknowledge(ctx, suspended) {
  if (suspended || ctx.running.current || !ctx.current.current || !ctx.found.current || !ctx.found.current.terminal) return;
  const original = ctx.current.current, completed = ctx.found.current;
  ctx.running.current = true;
  try { await exclusive(A.PENDING_KEY, { wait: true }, () => A.pending.finish(original, true)); }
  catch (problem) {
    if (problem && problem.conflict === true) completeDismissal(ctx, original, { kind: 'rejected' });
    else if (ctx.mounted.current) ctx.setStorageError(problem);
    return;
  }
  finally { ctx.running.current = false; }
  completeDismissal(ctx, original, completed);
}

// Keep this component mounted across tab changes: it owns the system-only original request.
// 系统管理只读本机数据，没有别的数据来源可切换。
function SystemMaintenanceWorkspace({ tab, theme, onSetTheme, pageSize, onPageSize, compact, onCompact, revision, onChanged, onReadSuspendedChange, recordContexts, onRecordContext, children }) {
  const [version, refresh] = React.useReducer(value => value + 1, 0);
  const command = useCommand((intent, result) => { refresh(); onChanged(intent, result); }, revision);
  const suspended = command.suspended;
  React.useLayoutEffect(() => { onReadSuspendedChange(suspended, command.readReason); }, [suspended, command.readReason, onReadSuspendedChange]);
  const enabled = !suspended, serial = revision + ':' + version;
  const [visited, setVisited] = React.useState({});
  React.useEffect(() => { if (enabled && ['backups', 'logs', 'config'].includes(tab)) setVisited(value => ({ ...value, [tab]: true })); }, [enabled, tab]);
  return <div className="sm-maintenance-workspace sm-maintenance-workspace-flush plana" data-system-maintenance="v1">

    {command.maintenanceRequired ? <SystemRestorePanel command={command} theme={theme} onSetTheme={onSetTheme} /> : <>
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
      <SystemMaintenanceRecords kind={kind} pageSize={pageSize} onPageSize={onPageSize} revision={serial} command={command} active={enabled && tab === kind}
        initialContext={recordContexts[kind]} onReadContext={onRecordContext} />
    </div> : null)}
    {(visited.config || enabled && tab === 'config') && <div hidden={!enabled || tab !== 'config'}><SystemMaintenanceConfig revision={serial} command={command} active={enabled && tab === 'config'} tab={tab}
      theme={theme} onSetTheme={onSetTheme} pageSize={pageSize} onPageSize={onPageSize} compact={compact} onCompact={onCompact} /></div>}
  </div>;
}

export { SystemMaintenanceWorkspace };
export default SystemMaintenanceWorkspace;
