import T from './shared/network/transport.js';
import { pendingStore, storageSlot } from './shared/session/pending-store.js';
import RunAdoptionAPI from './RunAdoptionAPI.js';
import { object, text, nonempty, ref48, token32, failure, checker } from './shared/contract/kit.js';

const BASE = '/api/workbench/v1/scheduling', PENDING_KEY = 'aps_workbench_run_pending_v1', RECENT_KEY = 'aps_workbench_run_recent_v1';
const key = v => text(v) && /^run-[a-f0-9]{48}$/.test(v);
const contextRef = v => RunAdoptionAPI.contextRef(v);
const terminal = run => !!run && ['complete', 'partial', 'failed', 'interrupted'].includes(run.state);
const INVALID = '读到的排产数据不完整，请刷新重试。';
// 受理回执与排产请求查询都在命令发出之后：核对不过时结果未知，本机待确认记录不能清。
const check = checker(INVALID), checkResult = checker(INVALID, { committed: 'unknown' });
function hasKeys(v, required) {
  return object(v) && required.every(k => Object.prototype.hasOwnProperty.call(v, k));
}
function exactShape(v, required) {
  return hasKeys(v, required) && Object.keys(v).every(k => required.includes(k));
}
function previewResult(v, inputRef) {
  const d = v.data;
  check(d.input_ref === inputRef && nonempty(d.data_context_ref));
  return d;
}
const runOk = (v, expectedRef) => object(v) && ref48(v.run_ref) && (!expectedRef || v.run_ref === expectedRef);
function accepted(v) {
  checkResult(object(v) && nonempty(v.data_context_ref)
    && v.ok === true && v.result === 'accepted' && ref48(v.run_ref) && v.job_ref === v.run_ref && text(v.receipt_ref) && /^[a-f0-9]{32}$/.test(v.receipt_ref)
    && v.status_target === BASE + '/runs/' + v.run_ref && runOk(v.data, v.run_ref));
  return v;
}
function lookupResult(v, expectedRef) {
  const d = v.data;
  checkResult(nonempty(d.data_context_ref)
    && ['found', 'context_replaced', 'unresolved'].includes(d.resolution) && d.found === (d.resolution === 'found')
    && (d.found ? runOk(d.run, expectedRef) : d.run === null));
  return d;
}
function validIntent(v) { return exactShape(v, ['schema_version', 'input_ref', 'request_key', 'run_ref', 'data_context_ref']) && v.schema_version === 2 && contextRef(v.data_context_ref)
  && token32(v.input_ref) && key(v.request_key) && (v.run_ref === null || ref48(v.run_ref)); }
const store = pendingStore({
  key: PENDING_KEY, validate: validIntent,
  readError: '读不到上次排产的操作记录，请重新打开页面，不要重做。',
  corruptError: '本机存的排产操作记录已损坏，已拦下新排产。请不要再操作，联系维护人员。',
  invalidError: '本机存的排产操作记录不完整，已拦下新排产。请不要再操作，联系维护人员。',
  conflictError: '上次操作记录已变化，没有删除其他记录。',
  writeError: '存不下这次排产的操作记录，没有开始排产。请重新打开页面。',
  removeError: '本机无法更新上次操作记录。请不要再操作，联系维护人员。'
});
const recentStore = pendingStore({
  key: RECENT_KEY,
  validate: value => exactShape(value, ['intent', 'resolution']) && validIntent(value.intent) && ['found', 'context_replaced'].includes(value.resolution),
  corruptError: '最近排产记录读不到，请到排产记录页查看。',
  invalidError: '最近排产记录不完整，请到排产记录页查看。'
});
const { read: rawRead, flush: rawFlush, save } = store;
const emptySlot = () => ({ requestKey: null, intent: null, run: null, resolution: 'unresolved', verified: false });
const sessionSlot = storageSlot(() => window.localStorage, 'run', PENDING_KEY, emptySlot, (slot, prev) => {
  if (prev.requestKey) Object.assign(slot, prev);
});
function resetSlot(slot, intent = null, runVal = null, resolution = 'unresolved', verified = false) {
  slot.requestKey = intent ? intent.request_key : null;
  slot.intent = intent;
  slot.run = runVal;
  slot.resolution = resolution;
  slot.verified = verified;
}
function syncSlotFromDisk(saved) {
  const slot = sessionSlot();
  if (!saved) {
    if (slot.resolution === 'unresolved') resetSlot(slot);
  } else if (slot.requestKey !== saved.request_key) resetSlot(slot, saved);
  else slot.intent = saved;
  return saved;
}
function recent() {
  const rec = recentStore.read();
  const slot = sessionSlot();
  if (slot.resolution !== 'unresolved' && (!rec || rec.intent.request_key !== slot.requestKey)) {
    resetSlot(slot);
  }
  return rec;
}
const read = () => syncSlotFromDisk(rawRead()), flush = () => syncSlotFromDisk(rawFlush());
// intent 都来自本存储读到并校验过的记录或 begin 刚写入的记录，转换只检查业务状态，不再重验记录格式。
const runPending = { read, flush, recent,
  subscribe(listener) {
    let lastEvent;
    const notify = event => {
      if (event && event === lastEvent) return;
      lastEvent = event;
      listener(event);
    };
    const offPending = store.subscribe(notify), offRecent = recentStore.subscribe(notify);
    return () => { offPending(); offRecent(); };
  },
  session() { return { ...sessionSlot() }; },
  // inputRef 与 dataContext 都取自 previewResult 核过的排产核对结果。
  begin(inputRef, dataContext) {
    try {
      const next = save({ schema_version: 2, input_ref: inputRef, request_key: T.requestKey('run'), run_ref: null, data_context_ref: dataContext }, null);
      resetSlot(sessionSlot(), next);
      return next;
    } catch (error) {
      if (error.conflict === true) throw failure('上次排产还没确认结果，不能重做。请先点「查询结果」。');
      throw error;
    }
  },
  // runRef 来自已校验的受理回执或排产记录：排产已受理，关联失败只说明本机记录没跟上，结果仍按未知处理。
  attach(intent, runRef) {
    checkResult(!intent.run_ref || intent.run_ref === runRef, '上次操作记录已变化，没有覆盖其他排产记录。');
    const next = { ...intent, run_ref: runRef };
    const slot = sessionSlot(), prev = { ...slot };
    if (!slot.requestKey || slot.requestKey === intent.request_key) {
      slot.requestKey = next.request_key;
      slot.intent = next;
    }
    try {
      return save(next, intent);
    } catch (error) {
      if (error.conflict === true) {
        Object.assign(slot, prev);
        throw failure('上次操作记录已变化，没有覆盖其他排产记录。', { committed: 'unknown' });
      }
      throw error;
    }
  },
  finish(intent, resolution) {
    const slot = sessionSlot(), prev = { ...slot };
    const runVal = slot.requestKey === intent.request_key ? slot.run : null;
    resetSlot(slot, intent, runVal, resolution, resolution === 'found' && !!runVal);
    try {
      save(null, intent, () => recentStore.write({ intent, resolution }));
    } catch (error) {
      if (error.conflict === true) Object.assign(slot, prev);
      throw error;
    }
  },
  reject(intent) {
    const slot = sessionSlot(), prev = { ...slot };
    resetSlot(slot);
    try {
      save(null, intent);
    } catch (error) {
      if (error.conflict === true) Object.assign(slot, prev);
      throw error;
    }
  }
};
// 排产检查核对、受理回执和读取都按 30 秒等待；受理失败的结果编号指向排产请求查询。
async function preview(inputRef, signal) {
  check(token32(inputRef));
  return previewResult(await T.preview(BASE + '/runs/preview', { input_ref: inputRef }, { signal, timeout: 30000 }), inputRef);
}
const isSlotTerminal = slot => slot.resolution === 'context_replaced' || Boolean(slot.run && terminal(slot.run));
// intent 是 begin 刚写入的记录，writeToken 已由 previewResult 核过。
async function accept(intent, writeToken) {
  const res = accepted(await T.command(BASE + '/runs', { input_ref: intent.input_ref, write_token: writeToken, request_key: intent.request_key },
    { timeout: 30000, expect: BASE + '/requests/' + intent.request_key }));
  const slot = sessionSlot();
  if (slot.requestKey === intent.request_key && isSlotTerminal(slot)) {
    if (slot.intent && !slot.intent.run_ref) slot.intent = { ...slot.intent, run_ref: res.run_ref };
  } else {
    resetSlot(slot, { ...intent, run_ref: res.run_ref }, res.data, 'found', true);
  }
  return res;
}
async function get(runRef, signal) {
  check(ref48(runRef));
  const res = (await T.read(BASE + '/runs/' + runRef, {}, { signal, timeout: 30000 })).data;
  check(runOk(res, runRef));
  const slot = sessionSlot();
  if (slot.intent && slot.intent.run_ref === runRef && (!isSlotTerminal(slot) || (slot.resolution !== 'context_replaced' && terminal(res)))) {
    slot.run = res;
    slot.resolution = 'found';
    slot.verified = true;
  }
  return res;
}
async function lookup(intent, signal) {
  const res = lookupResult(T.envelope(await T.lookup(BASE + '/requests/' + intent.request_key, { data_context_ref: intent.data_context_ref }, { signal, timeout: 30000 }), T.modes.lookup), intent.run_ref);
  if (!(signal && signal.aborted)) {
    const slot = sessionSlot();
    if (!slot.requestKey || slot.requestKey === intent.request_key || slot.resolution !== 'unresolved') {
      const sameTerminal = slot.requestKey === intent.request_key && isSlotTerminal(slot);
      const resTerminal = res.resolution === 'context_replaced' || Boolean(res.found && res.run && terminal(res.run));
      if (!sameTerminal || resTerminal) {
        const nextIntent = res.found && res.run && !intent.run_ref ? { ...intent, run_ref: res.run.run_ref } : intent;
        resetSlot(slot, nextIntent, res.found ? res.run : null, res.resolution, res.found);
      } else if (res.found && res.run && slot.intent && !slot.intent.run_ref) {
        slot.intent = { ...slot.intent, run_ref: res.run.run_ref };
      }
    }
  }
  return res;
}
const pollDelay = attempt => Math.min(30000, 2000 * Math.pow(2, Math.min(4, Math.max(0, attempt))));
const RunJobAPI = { preview, accept, get, lookup, pending: runPending, PENDING_KEY, RECENT_KEY, terminal, pollDelay };
export { RunJobAPI, preview, accept, get, lookup, runPending as pending, PENDING_KEY, RECENT_KEY, terminal, pollDelay };
export default RunJobAPI;
