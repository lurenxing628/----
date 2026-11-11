import React from './shared/runtime/react.js';
import TrialAPI from './TrialAPI.js';
import APSWorkbenchTransport from './shared/network/transport.js';
import { exclusive } from './shared/session/pending-store.js';
import { createCommandSession, useCommandSession } from './shared/session/command-session.js';
import { useQuery } from './shared/session/query.js';
import WorkbenchTerms from './WorkbenchTerms.js';

const A = TrialAPI, T = APSWorkbenchTransport;
const session = createCommandSession({
  key: A.PENDING_KEY,
  channel: 'trial',
  storage: () => window.localStorage,
  event: A.EVENT,
  initialState: () => ({ key: null, error: null, busy: false, note: '' })
});

function meta() {
  const slot = session.slot();
  if (!slot.meta) slot.meta = { busyCount: 0, rejected: false, pendingReceipt: null, callbacks: new Set() };
  return slot.meta;
}

// 读本机 key。本页登记过、还没写进磁盘的清除（读取错误带 saved）在跨页锁里写回，不再向服务端查询；flushed 表示这次只做了本机写回。
async function local() {
  try { return { key: A.pending(), flushed: false }; }
  catch (error) {
    if (!error || error.saved === undefined) throw error;
    return { key: (await exclusive(A.PENDING_KEY, { wait: true }, () => A.flush())).value, flushed: true };
  }
}

// 非复位同步入口：在途操作期间不重入；已结算且本机已清的业务拒绝保留提示，仅用户主动 restore() / clearError() 清空。
async function syncSession() {
  if (meta().busyCount > 0) return;
  try {
    const { key, flushed } = await local();
    if (meta().busyCount > 0) return;
    if (flushed || key !== null) {
      meta().rejected = false;
      session.setState(s => ({ ...s, key, error: null, note: '' }));
      return;
    }
    if (meta().rejected) {
      session.setState(s => s.key === null ? s : { ...s, key: null });
      return;
    }
    session.setState(s => ({ ...s, key: null, error: null, note: '' }));
  } catch (error) {
    if (meta().busyCount > 0) return;
    meta().rejected = false;
    session.setState(s => ({ ...s, key: error && error.saved === null ? null : s.key, error }));
  }
}

function useRead(load, deps, enabled = true) {
  const read = useQuery(load, deps, enabled);
  return { ...read, busy: read.loading };
}

// 服务端结论已定后只剩清除本机 key；删不掉时权威槽位记 key:null 与写错，发起实例保留 key 投影，不扣下已确认回执。
function releaseKey(key, done, note, isRejected, live, retainedKey) {
  try {
    A.clear(key);
    retainedKey.current = null;
    meta().rejected = isRejected;
    session.setState(s => ({ ...s, key: null, ...done }));
  } catch (error) {
    meta().rejected = false;
    if (error && error.conflict === true) {
      retainedKey.current = null;
      session.setState(s => s.key && s.key !== key ? s : { ...s, key: null, error, note: '' });
      return false;
    }
    if (live.current) retainedKey.current = key;
    session.setState(s => ({ ...s, key: null, error, note }));
  }
  return true;
}

function confirmReceipt(receipt, key, live, retainedKey, callback) {
  if (!releaseKey(key, { error: null, note: '' }, '', false, live, retainedKey)) return;
  if (live.current) { callback.current(receipt); return; }
  const m = meta();
  if (m.callbacks.size > 0) Array.from(m.callbacks).at(-1).current(receipt);
  else m.pendingReceipt = receipt;
}

function useCommands(onReceipt) {
  const state = useCommandSession(session), running = React.useRef(false), retainedKey = React.useRef(null);
  const live = React.useRef(true), callback = React.useRef(onReceipt); callback.current = onReceipt;
  if (state.key !== null || (!state.busy && !state.error)) retainedKey.current = null;
  const displayedKey = state.key !== null ? state.key : retainedKey.current;
  async function restore() {
    try {
      const { key } = await local();
      meta().rejected = false; retainedKey.current = null;
      session.setState(s => ({ ...s, key, error: null, note: '' }));
    } catch (error) {
      session.setState(s => ({ ...s, key: error && error.saved === null ? null : s.key, error }));
    }
  }
  function clearError() {
    if (!live.current || running.current || retainedKey.current) return;
    meta().rejected = false;
    session.setState(s => s.busy || s.key || (s.error && s.error.saved !== undefined) ? s : { ...s, error: null, note: '' });
  }
  React.useEffect(() => {
    live.current = true;
    const m = meta(); m.callbacks.add(callback);
    if (m.pendingReceipt !== null) { const r = m.pendingReceipt; m.pendingReceipt = null; callback.current(r); }
    syncSession();
    const unsubscribe = A.subscribe(syncSession);
    return () => { live.current = false; m.callbacks.delete(callback); unsubscribe(); };
  }, []);
  async function execute(intent, token) {
    if (running.current) return false;
    running.current = true; meta().busyCount++; meta().rejected = false;
    session.setState(s => ({ ...s, busy: true, error: null, note: '' }));
    try {
      const { acquired, value } = await exclusive(A.PENDING_KEY, {}, async () => {
        let key;
        try {
          key = A.reserve(); retainedKey.current = null; session.setState(s => ({ ...s, key }));
          confirmReceipt(await A.command(intent, token, key), key, live, retainedKey, callback); return true;
        } catch (error) {
          if (key && T.rejected(error))
            releaseKey(key, { error, note: '这次没有写入。填写内容已保留，请点「刷新」后重新确认。' }, '这次没有写入，但本机操作记录还没清掉。请点「查询结果」重试清理。', true, live, retainedKey);
          else session.setState(s => ({ ...s, error, ...(key ? { key, note: WorkbenchTerms.outcomes.pending('提交') } : {}) }));
          return false;
        }
      });
      if (!acquired) session.setState(s => ({ ...s, error: new Error('另一个页面正在提交试调，请稍后重试。') }));
      return acquired && value;
    } catch (error) { session.setState(s => ({ ...s, error })); return false; }
    finally { running.current = false; const m = meta(); m.busyCount -= 1; session.setState(s => ({ ...s, busy: m.busyCount > 0 })); }
  }
  async function lookup() {
    if (running.current) return;
    running.current = true; meta().busyCount++;
    session.setState(s => ({ ...s, busy: true, error: null }));
    try {
      const { key, flushed } = await local();
      retainedKey.current = null;
      if (flushed || !key) { meta().rejected = false; session.setState(s => ({ ...s, key, error: null, note: '' })); return; }
      const result = await A.lookup(key);
      await exclusive(A.PENDING_KEY, { wait: true }, () => {
        if (result.state === 'recorded') { confirmReceipt(result.receipt, key, live, retainedKey, callback); return; }
        const currentKey = A.pending();
        if (currentKey !== key) { meta().rejected = false; session.setState(s => ({ ...s, key: currentKey, error: null, note: '' })); return; }
        session.setState(s => ({ ...s, key, note: WorkbenchTerms.outcomes.pending('提交') }));
      });
    } catch (error) { session.setState(s => ({ ...s, key: error && error.saved === null ? null : s.key, error })); }
    finally { running.current = false; const m = meta(); m.busyCount -= 1; session.setState(s => ({ ...s, busy: m.busyCount > 0 })); }
  }
  return { ...state, key: displayedKey, execute, lookup, restore, clearError, blocked: state.busy || !!displayedKey || !!state.error };
}
const TrialSession = { useRead, useCommands };
export { TrialSession, useRead, useCommands };
export default TrialSession;
