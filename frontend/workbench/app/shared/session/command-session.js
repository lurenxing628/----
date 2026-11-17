import React from '../runtime/react.js';
import C from '../../resource-contract.js';
import T from '../network/transport.js';
import { storageSlot } from './pending-store.js';
import WorkbenchTerms from '../../WorkbenchTerms.js';
import { failure } from '../contract/kit.js';

// 同一 storage + channel + key 的底层命令结算会话：在组件卸载/重挂载之间保持在途与已结算终态，
// 并随底层 Storage 实例切换或 SecurityError 隔离槽位。从不把写令牌或猜测结论写入浏览器存储。
function createCommandSession({ key, channel, storage, event = null, initialState }) {
  const createSlot = () => ({ state: initialState(), dirty: false });
  const slotOf = storageSlot(storage, channel, key, createSlot, (slot, prev) => {
    if (prev.dirty) Object.assign(slot, prev);
  });
  const listeners = new Set();
  const emit = () => {
    const current = slotOf().state;
    for (const fn of listeners) fn(current);
  };
  function getState() {
    return slotOf().state;
  }
  function setState(updater) {
    const slot = slotOf();
    const next = typeof updater === 'function' ? updater(slot.state) : updater;
    if (Object.is(next, slot.state)) return slot.state;
    slot.state = next;
    slot.dirty = true;
    for (const fn of listeners) fn(next);
    return next;
  }
  function subscribe(listener) {
    if (!listeners.size && event) window.addEventListener(event, emit);
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
      if (!listeners.size && event) window.removeEventListener(event, emit);
    };
  }
  // 此刻是否有已挂载的组件在用这个会话；没有时下一次挂载等于重新打开页面。
  const observed = () => listeners.size > 0;
  return { slot: slotOf, getState, setState, subscribe, observed };
}

function useCommandSession(commandSession) {
  const [state, setLocal] = React.useState(() => commandSession.getState());
  React.useEffect(() => {
    setLocal(commandSession.getState());
    return commandSession.subscribe(setLocal);
  }, [commandSession]);
  return state;
}

const resourceSessions = new Map();

// api 是某个命名空间的单例（资源各命名空间、工艺、批次、现场），会话按它的待确认键共用。
function prepareResourceSession(api) {
  const key = api.pendingKey;
  let cs = resourceSessions.get(key);
  if (!cs) {
    cs = createCommandSession({
      key,
      channel: 'command',
      storage: () => window.sessionStorage,
      initialState: () => ({ phase: 'idle' })
    });
    resourceSessions.set(key, cs);
  }
  const slot = cs.slot();
  if (!slot.initialized) {
    slot.initialized = true;
    try {
      const intent = api.readPending();
      if (intent) { slot.state = { phase: 'pending', intent, restored: true }; slot.dirty = true; }
    } catch (error) {
      slot.state = { phase: 'pending', error };
      slot.dirty = true;
    }
    return cs;
  }
  // 同页内已有组件在用时以内存状态为准；所有组件都卸载后重新打开，按磁盘记录重新对齐。
  if (!slot.running && !cs.observed()) {
    try {
      const disk = api.readPending();
      if (disk) {
        if (!(slot.state.intent && disk.request_key === slot.state.intent.request_key)) {
          slot.state = { phase: 'pending', intent: disk, restored: true };
          slot.dirty = true;
        }
      } else if (slot.state.intent || (slot.state.phase === 'pending' && slot.state.error)) {
        slot.state = { phase: 'idle' };
        slot.dirty = true;
      }
    } catch (error) {
      slot.state = slot.state.intent || ['rejected', 'done'].includes(slot.state.phase)
        ? { ...slot.state, error }
        : { phase: 'pending', error };
      slot.dirty = true;
    }
  }
  return cs;
}

function useCommand(api) {
  const cs = prepareResourceSession(api);
  const state = useCommandSession(cs);
  React.useEffect(() => {
    const slot = cs.slot();
    if (slot.state.restored && slot.state.intent) { slot.state.restored = false; check(); }
  }, [cs]);
  const locked = ['sending', 'pending', 'checking'].includes(state.phase);
  React.useEffect(() => {
    if (!locked) return undefined;
    const warn = event => { event.preventDefault(); event.returnValue = ''; };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [locked]);
  async function check() {
    const slot = cs.slot();
    if (slot.running) return;
    let intent = slot.state.intent;
    if (!intent && slot.state.phase === 'pending') {
      try { intent = api.readPending(); }
      catch (error) { cs.setState({ phase: 'pending', error }); return; }
      if (!intent) { cs.setState({ phase: 'idle' }); return; }
    }
    if (!intent) return;
    slot.running = true; cs.setState(s => ({ ...s, intent, phase: 'checking', error: null }));
    try {
      const result = await api.lookup(intent.request_key, intent);
      const status = C.receipt(result);
      cs.setState({
        intent, result, phase: status === 'terminal' ? 'done' : 'pending',
        error: status === 'terminal' ? null : failure(result.message || WorkbenchTerms.outcomes.pending('操作'), { committed: 'unknown' })
      });
    } catch (error) { cs.setState({ intent, phase: 'pending', error }); }
    finally { cs.slot().running = false; }
  }
  async function submit(kind, action, ref, context, input, listCategory) {
    const slot = cs.slot();
    if (slot.running || ['sending', 'pending', 'checking', 'done'].includes(slot.state.phase)) return;
    let intent;
    try {
      intent = C.createIntent(kind, action, ref, input, listCategory);
      api.savePending(intent);
    } catch (error) { cs.setState({ phase: 'rejected', error }); return; }
    slot.running = true; cs.setState({ phase: 'sending', intent, error: null });
    try {
      const result = await api.command(kind, action, ref, { request_key: intent.request_key, write_token: context.write_token, input });
      cs.setState({ intent, result, phase: C.receipt(result) === 'terminal' ? 'done' : 'pending', error: null });
    } catch (error) {
      cs.setState({ intent, phase: T.rejected(error) ? 'rejected' : 'pending', error });
    } finally { cs.slot().running = false; }
    if (cs.getState().phase === 'rejected') {
      // 服务端已明确拒绝，没有回执可查；记录清不掉时保留拒绝态和意图，由 reset() 再清。
      try { api.clearPending(intent); }
      catch (error) { cs.setState(s => ({ ...s, error })); return; }
      cs.setState(s => ({ ...s, intent: null }));
    }
    if (cs.getState().phase === 'pending') await check();
  }
  function reset() {
    const slot = cs.slot();
    if (slot.running || ['sending', 'pending', 'checking'].includes(slot.state.phase)) return false;
    if (slot.state.intent) {
      try { api.clearPending(slot.state.intent); }
      catch (error) { cs.setState(s => ({ ...s, error })); return false; }
    }
    cs.setState({ phase: 'idle' });
    return true;
  }
  // 用户改了输入就清掉拒绝态。过期拒绝默认保留，等用户刷新资料；重新预检、换文件本身会产出新的写入依据，传 includeStale 一并清掉。
  function clearRejection({ includeStale = false } = {}) {
    const cur = cs.getState();
    if (cur.phase !== 'rejected' || !includeStale && C.stale(cur.error)) return false;
    return reset();
  }
  return { ...state, locked, stale: state.phase === 'rejected' && C.stale(state.error), submit, check, reset, clearRejection };
}

const APSResourceSession = { createCommandSession, useCommandSession, useCommand };
export { createCommandSession, useCommandSession, useCommand, APSResourceSession };
export default APSResourceSession;
