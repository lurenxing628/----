import React from './shared/runtime/react.js';
import RunAdoptionAPI from './RunAdoptionAPI.js';
import RunAdoptionControls from './RunAdoptionControls.jsx';
import APSWorkbenchTransport from './shared/network/transport.js';
import { exclusive, equal } from './shared/session/pending-store.js';
import WorkbenchHandlerMemory from './WorkbenchHandlerMemory.js';
import WorkbenchTerms from './WorkbenchTerms.js';

const A = RunAdoptionAPI, U = RunAdoptionControls, T = APSWorkbenchTransport;
// A fresh draft starts with the last handler typed on this machine; it is a typing convenience, never an identity.
const empty = () => ({ reason: '', declared_operator: WorkbenchHandlerMemory.read().value });
function Session({ candidateRef, candidateDisplay, candidateCatalog, onNavigate }) {
  const [initial] = React.useState(() => {
    let saved = null, error = '';
    try { saved = A.pending.read(); }
    catch (e) { saved = e.saved || null; error = e.message; }
    const s = A.pending.session();
    const match = saved && s.requestKey === saved.request_key;
    return {
      intent: saved,
      error,
      result: match ? s.result : null,
      replacedInfo: match ? s.replacedInfo : null
    };
  });
  const [intent, setIntent] = React.useState(initial.intent), [storageError, setStorageError] = React.useState(initial.error);
  const [draft, setDraft] = React.useState(() => initial.intent ? initial.intent.input : empty()), [consent, setConsent] = React.useState(false);
  const [preview, setPreview] = React.useState(null), [result, setResult] = React.useState(initial.result), [open, setOpen] = React.useState(false);
  const [busy, setBusy] = React.useState(false), [checking, setChecking] = React.useState(false), [error, setError] = React.useState(''), [notice, setNotice] = React.useState('');
  const [replacedInfo, setReplacedInfo] = React.useState(initial.replacedInfo);
  const [revision, refresh] = React.useReducer(v => v + 1, 0);
  const alive = React.useRef(false), lock = React.useRef(false), previewRequest = React.useRef(null), active = React.useRef(intent), current = React.useRef(null);
  active.current = intent; current.current = { candidateRef, preview, consent, draft, storageError };
  React.useEffect(() => { alive.current = true; return () => { alive.current = false; if (previewRequest.current) previewRequest.current.abort(); }; }, []);
  function readStorage(event, load = A.pending.read) {
    try {
      const saved = event && event.type === A.EVENT ? event.detail : load();
      const s = A.pending.session();
      const match = saved && s.requestKey === saved.request_key;
      if (saved !== active.current && !equal(saved, active.current)) {
        const switched = !active.current || !saved || saved.request_key !== active.current.request_key;
        const nextDraft = saved ? saved.input : empty();
        active.current = saved;
        current.current = { ...current.current, preview: null, consent: false, draft: nextDraft, storageError: '' };
        if (!alive.current) return;
        setIntent(saved); setResult(match ? s.result : null); setPreview(null); setConsent(false); setReplacedInfo(match ? s.replacedInfo : null); setNotice('');
        setDraft(nextDraft); if (switched) setError('');
      } else {
        current.current = { ...current.current, storageError: '' };
        if (alive.current && match) { setResult(s.result); setReplacedInfo(s.replacedInfo); }
      }
      if (alive.current) setStorageError('');
    } catch (e) {
      const s = A.pending.session();
      const changed = e.saved !== undefined && !equal(e.saved, active.current);
      const nextDraft = changed ? (e.saved ? e.saved.input : empty()) : current.current.draft;
      if (changed) active.current = e.saved;
      const nowActive = active.current;
      const match = nowActive && s.requestKey === nowActive.request_key;
      current.current = { ...current.current, ...(changed ? { preview: null, consent: false, draft: nextDraft } : {}), storageError: e.message };
      if (!alive.current) return;
      if (changed) { setIntent(e.saved); setDraft(nextDraft); }
      setResult(match ? s.result : null);
      setReplacedInfo(match ? s.replacedInfo : null);
      setStorageError(e.message);
    }
  }
  function restoreSession(message) {
    const s = A.pending.session();
    if (s.intent) {
      active.current = s.intent;
      current.current = { ...current.current, draft: s.intent.input, storageError: message };
      if (alive.current) {
        setIntent(s.intent); setDraft(s.intent.input); setResult(s.result); setReplacedInfo(s.replacedInfo);
      }
    }
    if (alive.current) setStorageError(message);
  }
  React.useEffect(() => A.pending.subscribe(readStorage), []);
  function acceptResult(value, original) {
    if (!alive.current || !active.current || active.current.request_key !== original.request_key) return;
    setResult(value); setError(''); setNotice('');
  }
  React.useEffect(() => {
    if (!intent || intent.phase !== 'pending' || storageError || result || replacedInfo) return undefined;
    const s = A.pending.session();
    if (s.requestKey === intent.request_key) {
      if (s.result) { setResult(s.result); return undefined; }
      if (s.replacedInfo) { setReplacedInfo(s.replacedInfo); return undefined; }
    }
    let disposed = false; const controller = new AbortController();
    const current = () => !disposed && alive.current && active.current && active.current.request_key === intent.request_key;
    async function query() {
      if (lock.current) return;
      setChecking(true);
      try {
        const found = await A.lookup(intent, controller.signal);
        if (!current()) return;
        if (found && found.resolution === 'context_replaced') { setReplacedInfo(found); setError(''); setNotice(found.message); }
        else if (found) acceptResult(found, intent);
        else { setError(''); setNotice(WorkbenchTerms.outcomes.pending('采用')); }
      } catch (_) { if (current()) setError('查询采用结果失败，采用可能已经生效。请点「查询结果」重试，不要重新采用。'); }
      finally { if (!disposed) setChecking(false); }
    }
    query(); return () => { disposed = true; controller.abort(); setChecking(false); };
  }, [intent, revision, storageError, result, replacedInfo]);
  function retryLookup() {
    A.pending.clearReplaced(intent);
    setReplacedInfo(null);
    refresh();
  }
  async function inspect() {
    const target = active.current ? active.current.candidate_ref : candidateRef;
    if (lock.current || storageError || !A.ref(target) || active.current && active.current.phase === 'pending') return;
    lock.current = true; setBusy(true); setOpen(true); setPreview(null); setConsent(false); setError(''); setNotice('');
    const controller = new AbortController(); previewRequest.current = controller;
    try {
      const value = await A.preview(target, controller.signal);
      if (alive.current && !controller.signal.aborted) setPreview(value);
    } catch (e) { if (alive.current && !controller.signal.aborted) setError(e.message); }
    finally { lock.current = false; if (alive.current) setBusy(false); }
  }
  async function submit() {
    if (lock.current || storageError || !preview || !preview.validation.can_adopt || !consent || active.current && active.current.phase === 'pending') return;
    let values; try { values = A.input({ confirm: true, reason: draft.reason, declared_operator: draft.declared_operator }); }
    catch (e) { setError(e.message); return; }
    WorkbenchHandlerMemory.write(values.declared_operator);
    const initialActive = active.current;
    lock.current = true; setBusy(true); setError(''); setNotice('');
    try {
      // 采用记录、提交和拒绝写回在跨页互斥里串行，持锁跨过采用命令。
      const { acquired } = await exclusive(A.PENDING_KEY, {}, async () => {
        const latest = current.current;
        if (!alive.current || latest.storageError || latest.preview !== preview || !latest.consent || (active.current ? active.current.candidate_ref : latest.candidateRef) !== preview.candidate_ref
          || latest.draft.reason !== draft.reason || latest.draft.declared_operator !== draft.declared_operator
          || !equal(active.current, initialActive)
          || active.current && active.current.phase === 'pending') return;
        let original;
        try { original = A.pending.begin(preview, values, active.current); } catch (e) { setStorageError(e.message); return; }
        active.current = original; current.current = { ...current.current, preview: null, consent: false }; setIntent(original); setDraft(values); setPreview(null); setConsent(false);
        try { acceptResult(await A.adopt(original, preview.write_context.write_token), original); }
        catch (e) {
          if (!equal(active.current, original)) { if (alive.current) readStorage(); return; }
          if (T.rejected(e)) {
            // Only an authentic, definitive non-commit permits a new preview. Unknown responses keep the original key.
            const rejected = { ...original, phase: 'rejected' };
            try { A.pending.reject(original, e); active.current = rejected; }
            catch (storageErr) {
              if (!alive.current) return;
              if (!equal(active.current, rejected)) { readStorage(); setStorageError(storageErr.message); return; }
              setStorageError(storageErr.message);
            }
            if (alive.current && equal(active.current, rejected)) setError(e.message + ' 填写内容已保留，请重新预检并确认。');
          } else if (alive.current) setError(WorkbenchTerms.outcomes.pending('采用'));
        }
      });
      if (!acquired && alive.current) setError('另一个页面正在确认采用，请稍后刷新上次操作记录。');
    } catch (e) { if (alive.current) setError(e.message); }
    finally { lock.current = false; if (alive.current) { setBusy(false); refresh(); } }
  }
  // 「刷新上次操作记录」在跨页互斥里把本页没写进去的记录写回再读。
  async function reload() {
    try { await exclusive(A.PENDING_KEY, { wait: true }, () => readStorage(undefined, A.pending.flush)); }
    catch (e) { setStorageError(e.message); }
    refresh();
  }
  function close() {
    if (previewRequest.current) previewRequest.current.abort();
    current.current = { ...current.current, preview: null, consent: false };
    setOpen(false); setPreview(null); setConsent(false);
  }
  // 结束本机采用记录的三种方式都在跨页互斥里写入。
  async function finish() {
    try { await exclusive(A.PENDING_KEY, { wait: true }, () => A.pending.finish(intent)); setResult(null); setOpen(false); setNotice(WorkbenchTerms.outcomes.done('采用')); }
    catch (e) { restoreSession(e.message); }
  }
  async function cancelRejected() {
    try { await exclusive(A.PENDING_KEY, { wait: true }, () => A.pending.cancelRejected(intent)); setOpen(false); setNotice('已结束本次未采用，原正式计划未改变。'); }
    catch (e) { restoreSession(e.message); }
  }
  async function dismissReplaced() {
    try {
      await exclusive(A.PENDING_KEY, { wait: true }, () => A.pending.dismissReplaced(intent, replacedInfo)); setReplacedInfo(null); setOpen(false);
      setNotice('已结束本机的旧来源待确认记录，原数据库中的采用结果未作更改。');
    } catch (e) { restoreSession(e.message); }
  }
  const pending = intent && intent.phase === 'pending';
  const label = result ? '查看采用结果' : pending ? '查询采用结果' : intent ? '重新核对采用' : '采用前核对';
  const display = preview && preview.validation.can_adopt ? preview : intent ? intent.preview : { candidate_ref: candidateRef || '未指定' };
  const savedCandidate = candidateCatalog.find(candidate => candidate.candidate_ref === display.candidate_ref);
  const targetDisplay = candidateDisplay && candidateDisplay.candidate_ref === display.candidate_ref ? candidateDisplay : savedCandidate ? { candidate_ref: savedCandidate.candidate_ref, label: savedCandidate.label || '候选名称未填写' } : undefined;
  return <span className="plana run-adoption-action" data-run-adoption-action="true">
    <U.Button icon={pending ? 'refresh-cw' : 'check'} className="btn primary" disabled={!intent && (!A.ref(candidateRef) || !!storageError)} onClick={() => {
      if (intent) { setOpen(true); if (pending && !result) refresh(); }
      else inspect();
    }} aria-expanded={open} aria-label={!intent && targetDisplay ? '采用前核对 ' + targetDisplay.label : label} title={!intent && targetDisplay ? '采用前核对 ' + targetDisplay.label : undefined} busy={busy && !intent}>{label}</U.Button>
    {storageError && !open && <span className="ra-inline" role="alert">{storageError}<U.Button icon="refresh-cw" disabled={busy} onClick={reload}>刷新上次操作记录</U.Button></span>}
    {intent && !open && <span className="ra-inline">{result ? '采用结果已确认。' : pending ? '上次操作已保留，结果待确认。' : '上次没有采用，请重新预检。'}</span>}
    {open && <U.Dialog value={display} intent={intent} result={result} preview={preview} draft={draft} consent={consent} busy={busy || checking}
      candidateDisplay={targetDisplay} replacedInfo={replacedInfo}
      error={storageError || error} storageError={storageError} onReadStorage={reload}
      notice={[intent && intent.candidate_ref !== candidateRef ? '另一个候选方案还有没确认的采用操作，请先确认那条记录。' : '',
        notice || (intent && intent.phase === 'rejected' && !preview ? '上次采用被拒绝了，填写内容已保留。请重新预检并再次确认。' : '')].filter(Boolean).join(' ')}
      onChange={value => { current.current = { ...current.current, draft: value }; setDraft(value); }}
      onConsent={value => { current.current = { ...current.current, consent: value }; setConsent(value); }}
      onClose={close} onPreview={inspect} onConfirm={submit} onLookup={retryLookup} onFinish={finish} onCancelRejected={cancelRejected} onDismissReplaced={dismissReplaced} onNavigate={onNavigate} />}
  </span>;
}
const RunAdoptionAction = function RunAdoptionAction(props) { return <Session key={props.candidateRef || 'missing'} {...props} />; };
export { RunAdoptionAction };
export default RunAdoptionAction;
