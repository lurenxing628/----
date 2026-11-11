import APSWorkbenchTransport from './shared/network/transport.js';
import { pendingStore, storageSlot } from './shared/session/pending-store.js';
import RunAdoptionAPI from './RunAdoptionAPI.js';
import WorkbenchTerms from './WorkbenchTerms.js';

const T = APSWorkbenchTransport, BASE = '/api/workbench/v1/scheduling', PENDING_KEY = 'aps_workbench_run_pending_v1', RECENT_KEY = 'aps_workbench_run_recent_v1';
const object = v => v !== null && typeof v === 'object' && !Array.isArray(v);
const text = v => typeof v === 'string';
const ref = v => text(v) && /^[a-f0-9]{48}$/.test(v), token = v => text(v) && /^[A-Za-z0-9_-]{32}$/.test(v);
const key = v => text(v) && /^run-[a-f0-9]{48}$/.test(v);
const contextRef = v => RunAdoptionAPI.contextRef(v);
const terminal = run => !!run && ['complete', 'partial', 'failed', 'interrupted'].includes(run.state);
function check(valid, message = '读到的排产数据不完整，请刷新重试。') { if (!valid) throw new Error(message); }
function hasKeys(v, required) {
  return object(v) && required.every(k => Object.prototype.hasOwnProperty.call(v, k));
}
function exactShape(v, required) {
  return hasKeys(v, required) && Object.keys(v).every(k => required.includes(k));
}
function previewResult(v, inputRef) {
  const d = v.data;
  check(d.input_ref === inputRef && text(d.data_context_ref) && d.data_context_ref.length > 0);
  return d;
}
function run(v, expectedRef) {
  check(object(v) && ref(v.run_ref) && (!expectedRef || v.run_ref === expectedRef));
  return v;
}
function accepted(v) {
  check(object(v) && text(v.data_context_ref) && v.data_context_ref.length > 0
    && v.ok === true && v.result === 'accepted' && ref(v.run_ref) && v.job_ref === v.run_ref && text(v.receipt_ref) && /^[a-f0-9]{32}$/.test(v.receipt_ref)
    && v.status_target === BASE + '/runs/' + v.run_ref);
  run(v.data, v.run_ref); return v;
}
function lookupResult(v, expectedRef) {
  const d = v.data;
  check(text(d.data_context_ref) && d.data_context_ref.length > 0
    && ['found', 'context_replaced', 'unresolved'].includes(d.resolution) && d.found === (d.resolution === 'found'));
  if (d.found) run(d.run, expectedRef); else check(d.run === null);
  return d;
}
const OUTCOMES = WorkbenchTerms.outcomes;
const messages = {
  input_already_used: '这份检查结果已经开始过排产，请重新检查后再开始下一次。',
  run_worker_not_connected: '排产计算程序没有启动，暂时不能开始排产。请联系维护人员。',
  execution_ledger_unavailable: '报工记录还没准备好，请联系维护人员升级数据库。',
  snapshot_stale: '资料已更新或排产检查已过期，请重新做排产检查。刚才的选择已保留。',
  stale_write: '本页数据已过期，请重新做排产检查。',
  constraint_conflict: '排产检查发现缺资料，请补齐后再开始排产。', invalid_input: '排产条件不完整，请重新做排产检查。',
  no_eligible_tasks: '当前范围没有可排工序。请调整批次、齐套条件或补齐工序资料后重新检查。',
  entity_not_found: '暂未查到这次排产记录，请点「查询结果」再次核对。',
  run_result_inconsistent: '这次排产的记录和保存结果不一致。请不要重做，联系维护人员。',
  storage_failure: OUTCOMES.pending('排产'), scheduling_busy: '已有排产正在计算，请稍后再点「查询结果」。',
  candidate_artifact_invalid: '候选方案记录不完整，请联系维护人员。',
  candidate_capacity_exceeded: '候选方案数量超过读取上限。',
  candidate_computation_failed: '本次候选计算失败。请联系维护人员，再重新做排产检查。',
  run_interrupted: '这次排产已中断，没有自动重跑。',
  request_lifecycle_stopping: '程序正在停止或维护，这次排产没有开始。重新启动后请重新做排产检查。'
};
function message(error) { return messages[error && error.code] || OUTCOMES.unknown('排产'); }
// 已结束的排产失败是确定结果：不认识的失败原因照后端原话显示，不能说成“可能已经生效”。
function failure(error) {
  return (error && text(error.message) && error.message) || messages[error && error.code] || messages.candidate_computation_failed;
}
function previewMessage(error) {
  return error && messages[error.code] && !['storage_failure', 'entity_not_found', 'run_result_inconsistent'].includes(error.code)
    ? messages[error.code] : '排产条件没有读出来，请重新检查。';
}
function validIntent(v) { return exactShape(v, ['schema_version', 'input_ref', 'request_key', 'run_ref', 'data_context_ref']) && v.schema_version === 2 && contextRef(v.data_context_ref)
  && token(v.input_ref) && key(v.request_key) && (v.run_ref === null || ref(v.run_ref)); }
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
      if (error && error.conflict === true) throw new Error('上次排产还没确认结果，不能重做。请先点「查询结果」。');
      throw error;
    }
  },
  // runRef 来自已校验的受理回执或排产记录。
  attach(intent, runRef) {
    check(!intent.run_ref || intent.run_ref === runRef, '上次操作记录已变化，没有覆盖其他排产记录。');
    const next = { ...intent, run_ref: runRef };
    const slot = sessionSlot(), prev = { ...slot };
    if (!slot.requestKey || slot.requestKey === intent.request_key) {
      slot.requestKey = next.request_key;
      slot.intent = next;
    }
    try {
      return save(next, intent);
    } catch (error) {
      if (error && error.conflict === true) {
        Object.assign(slot, prev);
        throw new Error('上次操作记录已变化，没有覆盖其他排产记录。');
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
      if (error && error.conflict === true) Object.assign(slot, prev);
      throw error;
    }
  },
  reject(intent) {
    const slot = sessionSlot(), prev = { ...slot };
    resetSlot(slot);
    try {
      save(null, intent);
    } catch (error) {
      if (error && error.conflict === true) Object.assign(slot, prev);
      throw error;
    }
  }
};
// 排产检查核对、受理回执和读取都按 30 秒等待；受理失败的结果编号指向排产请求查询。
async function preview(inputRef, signal) {
  check(token(inputRef));
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
  check(ref(runRef));
  const res = run((await T.read(BASE + '/runs/' + runRef, {}, { signal, timeout: 30000 })).data, runRef);
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
const RunJobAPI = { preview, accept, get, lookup, pending: runPending, PENDING_KEY, RECENT_KEY, token, ref, terminal, run, accepted, message, failure, previewMessage, pollDelay };
export { RunJobAPI, preview, accept, get, lookup, runPending as pending, PENDING_KEY, RECENT_KEY, token, ref, terminal, run, accepted, message, failure, previewMessage, pollDelay };
export default RunJobAPI;
