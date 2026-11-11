import APSWorkbenchTransport from './shared/network/transport.js';
import { pendingStore, storageSlot, canonical, equal } from './shared/session/pending-store.js';

const T = APSWorkbenchTransport, BASE = '/api/workbench/v1/';
const PENDING_KEY = 'aps_workbench_candidate_adoption_pending_v1', EVENT = PENDING_KEY + '_changed';
const object = v => v !== null && typeof v === 'object' && !Array.isArray(v);
const text = v => typeof v === 'string', count = v => Number.isSafeInteger(v) && v >= 0;
const ref = v => text(v) && /^[a-f0-9]{48}$/.test(v), token = v => text(v) && /^[A-Za-z0-9_-]{32}$/.test(v);
const key = v => text(v) && /^adoption-[a-f0-9]{48}$/.test(v), replacedProofs = new WeakMap();
function check(valid, message = '读到的采用数据不完整，请刷新重试。') { if (!valid) throw new Error(message); }
function hasKeys(v, required) {
  return object(v) && required.every(k => Object.prototype.hasOwnProperty.call(v, k));
}
function exactShape(v, required) {
  return hasKeys(v, required) && Object.keys(v).every(k => required.includes(k));
}
function contextRef(v) {
  if (!text(v)) return false;
  try {
    const data = JSON.parse(v);
    return exactShape(data, ['database_scope', 'successful_restores']) && text(data.database_scope) && data.database_scope.length > 0
      && Array.isArray(data.successful_restores)
      && data.successful_restores.every((item, index, list) => text(item) && /^[a-f0-9]{32}$/.test(item) && (index === 0 || list[index - 1] < item));
  } catch (_) { return false; }
}
function summary(v) {
  return exactShape(v, ['candidate_ref', 'run_ref', 'baseline', 'task_count', 'scope_complete']) && ref(v.candidate_ref) && ref(v.run_ref)
    && exactShape(v.baseline, ['plan_ref', 'version']) && (v.baseline.plan_ref === null ? v.baseline.version === null : ref(v.baseline.plan_ref) && count(v.baseline.version) && v.baseline.version > 0)
    && count(v.task_count) && v.task_count > 0 && v.scope_complete === true;
}
// 采用范围的投影只取字段、不校验：本机记录在 validIntent 里核验。
const overviewFields = v => ({ candidate_ref: v.candidate_ref, run_ref: v.run_ref, baseline: v.baseline, task_count: v.task_count, scope_complete: v.scope_complete });
// candidateRef 已由 preview() 在拼路径前核过。
function previewResult(v, candidateRef) {
  const d = v.data;
  check(d.candidate_ref === candidateRef && text(d.data_context_ref) && d.data_context_ref.length > 0
    && (d.validation.can_adopt !== true || token(d.write_context.write_token)));
  return d;
}
function input(v) {
  check(exactShape(v, ['confirm', 'reason', 'declared_operator']) && v.confirm === true, '请勾选确认正式采用。');
  for (const [name, limit] of [['reason', 1000], ['declared_operator', 100]]) check(text(v[name]) && v[name].trim()
    && Array.from(v[name].trim()).length <= limit && !v[name].includes('\0'), '请填写采用原因（1 至 1000 字）和经办人（1 至 100 字）。');
  return { confirm: true, reason: v.reason.trim(), declared_operator: v.declared_operator.trim() };
}
function receipt(v, intent) {
  const d = v && v.data, p = d && d.official_plan, s = intent.preview;
  check(object(v) && v.ok === true && v.result === 'committed'
    && object(d) && d.candidate_ref === intent.candidate_ref && d.run_ref === s.run_ref && d.row_count === s.task_count
    && object(p) && ref(p.plan_ref) && p.source_run_ref === s.run_ref && p.baseline_ref === s.baseline.plan_ref);
  return v;
}
function lookupResult(v, intent) {
  check(object(v) && ['recorded', 'not_observed'].includes(v.state));
  if (v.state === 'not_observed') {
    check(['unresolved', 'context_replaced'].includes(v.resolution));
    if (v.resolution === 'unresolved') return null;
    const info = {
      resolution: 'context_replaced',
      message: '这条待确认采用记录来自旧数据库或恢复前的历史状态，当前数据源里没有这项候选采用操作。可安全结束本机待确认记录，再对当前候选执行采用。',
    };
    replacedProofs.set(info, canonical(intent)); return info;
  }
  return receipt(v.receipt, intent);
}
function validIntent(v) {
  if (!exactShape(v, ['schema_version', 'candidate_ref', 'request_key', 'input', 'preview', 'phase', 'data_context_ref']) || v.schema_version !== 2 || !ref(v.candidate_ref)
    || !contextRef(v.data_context_ref) || !key(v.request_key) || !summary(v.preview) || v.preview.candidate_ref !== v.candidate_ref || !['pending', 'rejected'].includes(v.phase)) return false;
  try { return equal(input(v.input), v.input); } catch (_) { return false; }
}
const READ_ERROR = '读不到上次采用的操作记录，不要重新采用。';
const { read: rawRead, flush: rawFlush, save, subscribe } = pendingStore({
  key: PENDING_KEY, event: EVENT, validate: validIntent,
  readError: READ_ERROR,
  corruptError: '本机存的采用操作记录已损坏，已拦下新采用。请不要再操作，联系维护人员。',
  invalidError: '本机存的采用操作记录不完整，已拦下新采用。请不要再操作，联系维护人员。',
  conflictError: '上次采用记录已变化，没有覆盖其他操作。',
  writeError: '存不下采用的操作记录，没有开始新的采用。请重新打开页面。'
});
const emptySlot = () => ({ requestKey: null, intent: null, result: null, replacedInfo: null });
const sessionSlot = storageSlot(() => window.localStorage, 'adoption', PENDING_KEY, emptySlot, (slot, prev) => {
  if (prev.requestKey) Object.assign(slot, prev);
});
function resetSlot(slot, intent = null, result = null, replacedInfo = null) {
  slot.requestKey = intent ? intent.request_key : null;
  slot.intent = intent;
  slot.result = result;
  slot.replacedInfo = replacedInfo;
}
function syncSlotFromDisk(saved) {
  const slot = sessionSlot();
  if (!saved) resetSlot(slot);
  else if (slot.requestKey !== saved.request_key || saved.phase === 'rejected') resetSlot(slot, saved);
  else slot.intent = saved;
  return saved;
}
function loadWithSlot(rawFn) {
  const slot = sessionSlot();
  try {
    return syncSlotFromDisk(rawFn());
  } catch (e) {
    if (e.saved !== undefined) {
      if (e.saved === null) {
        if (slot.intent) e.saved = slot.intent;
      } else {
        syncSlotFromDisk(e.saved);
      }
    } else if (e.message === READ_ERROR && slot.intent) {
      e.saved = slot.intent;
    }
    throw e;
  }
}
const read = () => loadWithSlot(rawRead), flush = () => loadWithSlot(rawFlush);
function clearPending(intent) {
  const slot = sessionSlot(), prev = { ...slot };
  resetSlot(slot);
  try {
    return save(null, intent);
  } catch (e) {
    if (!e || !e.conflict) Object.assign(slot, prev);
    throw e;
  }
}
// intent/previous 只来自本存储读到并校验过的记录，previous 还要与磁盘上的当前值相等才写得进去。
// value 是 previewResult 核过的可采用预检，values 是 input() 规整过的填写内容；各转换只检查业务状态，写前不再重验。
const adoptionPending = { read, flush, subscribe,
  session() { return { ...sessionSlot() }; },
  clearReplaced(intent) {
    const slot = sessionSlot();
    if (intent && slot.requestKey === intent.request_key) slot.replacedInfo = null;
  },
  begin(value, values, previous) {
    check(!previous || previous.phase === 'rejected' && previous.candidate_ref === value.candidate_ref, '上次采用还没确认结果，不能重新提交。');
    const next = save({ schema_version: 2, candidate_ref: value.candidate_ref, request_key: previous ? previous.request_key : T.requestKey('adoption'),
      input: values, preview: overviewFields(value), phase: 'pending', data_context_ref: value.data_context_ref }, previous);
    resetSlot(sessionSlot(), next);
    return next;
  },
  reject(intent, error) {
    check(T.rejected(error), '没有确认拒绝结果，已保留上次操作。');
    const rejected = { ...intent, phase: 'rejected' };
    const slot = sessionSlot(), prev = { ...slot };
    resetSlot(slot, rejected);
    try { return save(rejected, intent); }
    catch (e) {
      if (e && e.conflict) Object.assign(slot, prev);
      throw e;
    }
  },
  cancelRejected(intent) { check(intent.phase === 'rejected', '结果还没确认，不能丢弃上次操作。'); return clearPending(intent); },
  dismissReplaced(intent, info) {
    check(intent.phase === 'pending' && replacedProofs.get(info) === canonical(intent), '结果还没确认，不能丢弃上次操作。');
    return clearPending(intent);
  },
  finish(intent) { return clearPending(intent); }
};
const candidatePath = candidateRef => BASE + 'scheduling/candidates/' + candidateRef;
async function preview(candidateRef, signal) {
  check(ref(candidateRef));
  return previewResult(await T.preview(candidatePath(candidateRef) + '/adopt-preview', {}, { signal, timeout: 30000 }), candidateRef);
}
// intent 是 begin() 刚写入的待确认记录，writeToken 已由 previewResult 核过。
async function adopt(intent, writeToken) {
  const res = receipt(await T.command(candidatePath(intent.candidate_ref) + '/adopt', { write_token: writeToken, request_key: intent.request_key, input: intent.input },
    { timeout: 30000, expect: candidatePath(intent.candidate_ref) + '/adoption-commands/' + intent.request_key }), intent);
  const slot = sessionSlot();
  if (slot.requestKey === intent.request_key) resetSlot(slot, intent, res, null);
  return res;
}
async function lookup(intent, signal) {
  const res = lookupResult(await T.lookup(candidatePath(intent.candidate_ref) + '/adoption-commands/' + intent.request_key,
    { run_ref: intent.preview.run_ref, data_context_ref: intent.data_context_ref }, { signal, timeout: 30000 }), intent);
  if (!(signal && signal.aborted)) {
    const slot = sessionSlot();
    if (slot.requestKey === intent.request_key) {
      if (res && res.resolution === 'context_replaced') resetSlot(slot, intent, null, res);
      else if (res) resetSlot(slot, intent, res, null);
    }
  }
  return res;
}
const RunAdoptionAPI = { preview, adopt, lookup, receipt, input, pending: adoptionPending, ref, contextRef, PENDING_KEY, EVENT };
export { RunAdoptionAPI, preview, adopt, lookup, receipt, input, adoptionPending as pending, ref, contextRef, PENDING_KEY, EVENT };
export default RunAdoptionAPI;
