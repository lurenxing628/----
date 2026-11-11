import React from './shared/runtime/react.js';
import CalibrationAdoptionAPI from './CalibrationAdoptionAPI.js';
import CalibrationAPI from './CalibrationAPI.js';
import APSWorkbenchTransport from './shared/network/transport.js';
import { pendingStore, exclusive } from './shared/session/pending-store.js';
import WorkbenchTerms from './WorkbenchTerms.js';

const A = CalibrationAdoptionAPI, C = CalibrationAPI, T = APSWorkbenchTransport, KEY = 'aps_calibration_adoption_pending_v1', EVENT = KEY + '_changed';

// 磁盘记录的唯一校验点：绑定按建议行规则、填写内容按采用表单规则、已采用的回执按回执与采用基线各核一次。
function validCommittedReceipt(r, value) {
  A.receipt(r, value);
  const d = r.data, s = value.baseline;
  return typeof r.replayed === 'boolean' && Array.isArray(r.warnings) && !r.warnings.length && d.method_version === s.method_version && d.sample_count === s.sample_count
    && A.equal(d.sample_refs, s.sample_refs) && A.equal(d.sample_revisions, s.sample_revisions) && d.effect_scope === 'future_template_use_only'
    && typeof d.generated_at === 'string' && d.generated_at.length > 0
    && d.old_unit_hours === s.old_unit_hours && d.new_unit_hours === s.suggested_unit_hours
    && d.template_revision_before === s.template_revision && d.template_revision_after === s.template_revision + (s.old_unit_hours === s.suggested_unit_hours ? 0 : 1)
    && typeof d.adopted_at === 'string' && d.adopted_at.length > 0
    && typeof d.application_operator === 'string' && d.application_operator.length > 0;
}

function valid(value) {
  try {
    return value && value.version === 1 && A.key(value.request_key) && ['pending', 'rejected', 'committed'].includes(value.phase)
      && A.equal(A.confirmation(A.input({ reason: value.input.reason, declared_operator: value.input.declared_operator })), value.input)
      && C.validBinding(value.baseline) && A.equal(A.binding(value.baseline), value.baseline)
      && (value.phase !== 'committed' || validCommittedReceipt(value.receipt, value));
  } catch (_) { return false; }
}

const { read, flush, save, subscribe } = pendingStore({
  key: KEY, event: EVENT, validate: valid,
  readError: '无法读取上次采用操作的记录，暂时不能开始新的采用。',
  corruptError: '上次采用的操作记录已损坏。请不要再操作，联系维护人员；不能换个编号重新提交。',
  invalidError: '上次采用的操作记录不完整。请不要再操作，联系维护人员；不能换个编号重新提交。',
  conflictError: '上次操作已变化，没有覆盖其他页面的采用记录。',
  writeError: '无法保存这次采用操作的记录，没有开始新的采用。'
});

// preview 是 A.preview 校验过的可采用预检，previous 只会是 null 或本存储读到的被拒记录。
function begin(preview, previous) {
  A.check(!previous || previous.phase === 'rejected' && previous.baseline.template_operation_ref === preview.suggestion.template_operation_ref, '上次操作的结果还没确认，不能开始新的采用。');
  return save({
    version: 1, request_key: T.requestKey('calibration'),
    phase: 'pending', baseline: A.binding(preview.suggestion), input: A.confirmation(preview.input)
  }, previous);
}

function storageMessage(e, current = e && e.saved) {
  if (current && current.phase === 'committed') return '已收到采用结果，但本机没能保存这次操作记录。';
  if (current && current.phase === 'rejected') return '本次采用未通过，但本机没能保存这次操作记录。';
  return e.message;
}

function useSession({ detail, stale }) {
  const [initial] = React.useState(() => { try { return { saved: read(), error: '' }; } catch (e) { return { saved: e.saved || null, error: storageMessage(e) }; } });
  const [saved, setSaved] = React.useState(initial.saved), [storageError, setStorageError] = React.useState(initial.error);
  const [draft, setDraft] = React.useState(initial.saved ? { reason: initial.saved.input.reason, declared_operator: initial.saved.input.declared_operator } : { reason: '', declared_operator: '' });
  const [open, setOpen] = React.useState(false), [preview, setPreview] = React.useState(null), [consent, setConsent] = React.useState(false);
  const [busy, setBusy] = React.useState(false), [error, setError] = React.useState(''), [notice, setNotice] = React.useState('');
  const [revision, refresh] = React.useReducer(v => v + 1, 0);
  const mounted = React.useRef(false), lock = React.useRef(false), request = React.useRef(null), active = React.useRef(saved), source = React.useRef(null);
  active.current = saved; source.current = { detail, stale, preview, consent, draft, storageError };
  const identity = detail ? JSON.stringify(A.binding(detail.suggestion)) : '';
  React.useEffect(() => { mounted.current = true; return () => { mounted.current = false; if (request.current) request.current.abort(); }; }, []);
  React.useEffect(() => { source.current = { ...source.current, preview: null, consent: false }; setPreview(null); setConsent(false); if (request.current) request.current.abort(); }, [identity, stale]);
  function sync(event, load = read) {
    try {
      const value = event && event.type === EVENT ? event.detail : load();
      if (value !== active.current && !A.equal(value, active.current)) {
        const switched = !active.current || !value || value.request_key !== active.current.request_key;
        const nextDraft = value ? { reason: value.input.reason, declared_operator: value.input.declared_operator } : { reason: '', declared_operator: '' };
        active.current = value;
        source.current = { ...source.current, preview: null, consent: false, draft: nextDraft, storageError: '' };
        if (!mounted.current) return;
        setSaved(value); setPreview(null); setConsent(false);
        setDraft(nextDraft);
        if (switched || value.phase === 'committed') { setError(''); setNotice(''); }
      } else {
        source.current = { ...source.current, storageError: '' };
      }
      if (mounted.current) setStorageError('');
    } catch (e) {
      const changed = e.saved !== undefined && !A.equal(e.saved, active.current);
      const nextDraft = changed ? (e.saved ? { reason: e.saved.input.reason, declared_operator: e.saved.input.declared_operator } : { reason: '', declared_operator: '' }) : source.current.draft;
      if (changed) active.current = e.saved;
      const msg = storageMessage(e, e.saved !== undefined ? e.saved : active.current);
      source.current = { ...source.current, ...(changed ? { preview: null, consent: false, draft: nextDraft } : {}), storageError: msg };
      if (!mounted.current) return;
      if (changed) { setSaved(e.saved); setDraft(nextDraft); }
      setStorageError(msg);
    }
  }
  React.useEffect(() => subscribe(sync), []);
  // 采用结论写回本机记录；调用方持有跨页锁。
  function accept(value, original) {
    if (!A.equal(active.current, original)) { if (mounted.current) sync(); return; }
    const committed = { ...original, phase: 'committed', receipt: value };
    try { save(committed, original); active.current = committed; if (!mounted.current) return; }
    catch (e) {
      if (!mounted.current) return;
      if (!A.equal(active.current, committed)) { sync(); setStorageError(e.message); return; }
      setStorageError(storageMessage(e, active.current));
    }
  }
  React.useEffect(() => {
    if (!saved || saved.phase !== 'pending' || storageError || lock.current) return undefined;
    let disposed = false; const controller = new AbortController(); setBusy(true);
    A.lookup(saved, controller.signal).then(async value => {
      if (disposed || !A.equal(active.current, saved)) return;
      if (value) await exclusive(KEY, { wait: true }, () => accept(value, saved));
      else setNotice('上次采用结果尚未确认，请稍后再次查询。');
    }).catch(e => { if (!disposed && A.equal(active.current, saved)) setError('上次操作的结果还没确认。' + e.message); }).finally(() => { if (!disposed) setBusy(false); });
    return () => { disposed = true; controller.abort(); if (!lock.current) setBusy(false); };
  }, [saved, revision, storageError]);
  function change(value) { source.current = { ...source.current, draft: value, preview: null, consent: false }; setDraft(value); setPreview(null); setConsent(false); setError(''); }
  async function inspect() {
    if (lock.current || stale || storageError || !detail || saved && saved.phase !== 'rejected') return;
    if (saved && saved.baseline.template_operation_ref !== detail.suggestion.template_operation_ref) { setError('上次操作属于另一个模板。请先点「放弃上次采用记录」处理完上次操作。'); return; }
    let values; try { values = A.input(draft); } catch (e) { setError(e.message); return; }
    lock.current = true; setBusy(true); setPreview(null); setConsent(false); setError(''); setNotice('');
    const controller = new AbortController(); request.current = controller;
    try {
      const value = await A.preview(detail.suggestion, values, controller.signal);
      if (mounted.current && !controller.signal.aborted && !source.current.stale && A.equal(detail, source.current.detail) && A.equal(draft, source.current.draft)) setPreview(value);
    } catch (e) { if (mounted.current && !controller.signal.aborted) setError(e.message); }
    finally { lock.current = false; if (mounted.current) setBusy(false); }
  }
  async function submit() {
    if (lock.current || stale || storageError || !preview || !preview.validation.can_adopt || !consent || !detail || saved && saved.phase !== 'rejected'
      || !A.equal(A.binding(detail.suggestion), A.binding(preview.suggestion))) return;
    const initialActive = active.current;
    lock.current = true; setBusy(true); setError(''); setNotice('');
    try {
      // 采用记录、提交和结果写回在跨页互斥里串行，持锁跨过采用命令。
      const { acquired } = await exclusive(KEY, {}, async () => {
        const latest = source.current;
        if (!mounted.current || latest.stale || latest.storageError || !latest.detail || latest.preview !== preview || !latest.consent
          || !A.equal(active.current, initialActive)
          || active.current && (active.current.phase !== 'rejected' || active.current.baseline.template_operation_ref !== latest.detail.suggestion.template_operation_ref)
          || !A.equal(A.binding(latest.detail.suggestion), A.binding(preview.suggestion))) return;
        let original;
        try { original = begin(preview, active.current); } catch (e) { setStorageError(e.message); return; }
        active.current = original; source.current = { ...source.current, preview: null, consent: false }; setSaved(original); setPreview(null); setConsent(false);
        try { accept(await A.adopt(original, preview.write_context.write_token), original); }
        catch (e) {
          if (!A.equal(active.current, original)) { if (mounted.current) sync(); return; }
          if (T.rejected(e)) {
            const rejected = { ...original, phase: 'rejected' };
            try { save(rejected, original); active.current = rejected; if (!mounted.current) return; }
            catch (storageErr) {
              if (!mounted.current) return;
              if (!A.equal(active.current, rejected)) { sync(); setStorageError(storageErr.message); return; }
              setStorageError(storageMessage(storageErr, active.current));
            }
            if (mounted.current && A.equal(active.current, rejected)) setError(e.message + ' 本次没有采用；请点「刷新所选模板」后重新预检。');
          } else if (mounted.current) setError(WorkbenchTerms.outcomes.pending('采用'));
        }
      });
      if (!acquired && mounted.current) setError('另一个页面正在采用，请先在那边查询结果。');
    } catch (e) { if (mounted.current) setError(e.message); }
    finally { lock.current = false; if (mounted.current) { setBusy(false); refresh(); } }
  }
  async function finish() {
    try {
      A.check(saved && saved.phase !== 'pending', '结果还不确定，不能丢弃这次操作。');
      await exclusive(KEY, { wait: true }, () => save(null, saved));
      source.current = { ...source.current, preview: null, consent: false }; setOpen(false); setPreview(null); setConsent(false);
      setError(''); setNotice(''); setDraft({ reason: '', declared_operator: '' });
    }
    catch (e) { setStorageError(e.message); }
  }
  return {
    saved, draft, open, preview, consent, busy, error, notice, storageError, setOpen,
    setConsent: value => { source.current = { ...source.current, consent: value }; setConsent(value); },
    change, inspect, submit, finish, lookup: refresh,
    // 「刷新上次操作记录」在跨页互斥里把本页没写进去的记录写回再读。
    sync: () => exclusive(KEY, { wait: true }, () => sync(undefined, flush)).catch(e => setStorageError(e.message)),
    close: () => { if (request.current) request.current.abort(); source.current = { ...source.current, preview: null, consent: false }; setOpen(false); setPreview(null); setConsent(false); }
  };
}

const CalibrationAdoptionState = { KEY, read, save, begin, useSession };

export { CalibrationAdoptionState, KEY, read, save, begin, useSession };
export default CalibrationAdoptionState;
