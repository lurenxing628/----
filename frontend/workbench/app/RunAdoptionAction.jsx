(function () {
  'use strict';
  const A = window.RunAdoptionAPI, U = window.RunAdoptionControls;
  // A fresh draft starts with the last handler typed on this machine; it is a typing convenience, never an identity.
  const empty = () => ({ reason: '', declared_operator: window.WorkbenchHandlerMemory.read().value });
  function Session({ candidateRef, candidateDisplay, candidateCatalog = [], onNavigate, adapter }) {
    const api = React.useMemo(() => adapter || A.create(), [adapter]);
    const [initial] = React.useState(() => { try { return { intent: A.pending().read(), error: '' }; } catch (e) { return { intent: null, error: e.message }; } });
    const [intent, setIntent] = React.useState(initial.intent), [storageError, setStorageError] = React.useState(initial.error);
    const [draft, setDraft] = React.useState(() => initial.intent ? initial.intent.input : empty()), [consent, setConsent] = React.useState(false);
    const [preview, setPreview] = React.useState(null), [result, setResult] = React.useState(null), [open, setOpen] = React.useState(false);
    const [busy, setBusy] = React.useState(false), [checking, setChecking] = React.useState(false), [error, setError] = React.useState(''), [notice, setNotice] = React.useState('');
    const [replacedInfo, setReplacedInfo] = React.useState(null);
    const [revision, refresh] = React.useReducer(v => v + 1, 0);
    const alive = React.useRef(false), lock = React.useRef(false), previewRequest = React.useRef(null), active = React.useRef(intent);
    active.current = intent;
    React.useEffect(() => { alive.current = true; return () => { alive.current = false; if (previewRequest.current) previewRequest.current.abort(); }; }, []);
    function readStorage(event) {
      try {
        const saved = event && event.type === A.EVENT ? event.detail : A.pending().read();
        if (saved !== active.current && JSON.stringify(saved) !== JSON.stringify(active.current)) {
          active.current = saved; setIntent(saved); setResult(null); setPreview(null); setConsent(false); setReplacedInfo(null); setNotice('');
          setDraft(saved ? saved.input : empty()); if (!saved) setError('');
        }
        setStorageError('');
      } catch (e) { setStorageError(e.message); }
    }
    React.useEffect(() => {
      const changed = e => { if (!e.key || e.key === A.PENDING_KEY) readStorage(e); };
      window.addEventListener('storage', changed); window.addEventListener(A.EVENT, changed);
      return () => { window.removeEventListener('storage', changed); window.removeEventListener(A.EVENT, changed); };
    }, []);
    function acceptResult(value, original) {
      const receipt = A.receipt(value, original);
      if (!alive.current || !active.current || active.current.request_key !== original.request_key) return;
      setResult(receipt); setError(''); setNotice('');
    }
    React.useEffect(() => {
      setReplacedInfo(null);
      if (!intent || intent.phase !== 'pending' || storageError || result) return undefined;
      let disposed = false; const controller = new AbortController();
      async function query() {
        if (lock.current) return;
        setChecking(true);
        try {
          const found = A.lookup(await api.lookup(intent, controller.signal), intent);
          if (disposed) return;
          if (found && found.resolution === 'context_replaced') { setReplacedInfo(found); setError(''); setNotice(found.message); }
          else if (found) acceptResult(found, intent);
          else { setError(''); setNotice(window.WorkbenchTerms.outcomes.pending('采用')); }
        } catch (_) { if (!disposed) setError('查询采用结果失败，采用可能已经生效。请点「查询结果」重试，不要重新采用。'); }
        finally { if (!disposed) setChecking(false); }
      }
      query(); return () => { disposed = true; controller.abort(); setChecking(false); };
    }, [api, intent, revision, storageError, result]);
    async function inspect() {
      const target = active.current ? active.current.candidate_ref : candidateRef;
      if (lock.current || storageError || !A.ref(target) || active.current && active.current.phase === 'pending') return;
      lock.current = true; setBusy(true); setOpen(true); setPreview(null); setConsent(false); setError(''); setNotice('');
      const controller = new AbortController(); previewRequest.current = controller;
      try {
        const value = A.preview(await api.preview(target, controller.signal), target);
        if (alive.current && !controller.signal.aborted) setPreview(value);
      } catch (e) { if (alive.current && !controller.signal.aborted) setError(e.message); }
      finally { lock.current = false; if (alive.current) setBusy(false); }
    }
    async function submit() {
      if (lock.current || storageError || !preview || !preview.validation.can_adopt || !consent || active.current && active.current.phase === 'pending') return;
      let values; try { values = A.input({ confirm: true, reason: draft.reason, declared_operator: draft.declared_operator }); }
      catch (e) { setError(e.message); return; }
      window.WorkbenchHandlerMemory.write(values.declared_operator);
      lock.current = true; setBusy(true); setError(''); setNotice('');
      try {
        if (!navigator.locks || typeof navigator.locks.request !== 'function') { if (alive.current) setError('当前浏览器不支持，请用 Chrome 打开。'); return; }
        await navigator.locks.request(A.PENDING_KEY, { ifAvailable: true }, async acquired => {
          if (!acquired) { if (alive.current) setError('另一个页面正在确认采用，请稍后刷新上次操作记录。'); return; }
          if (!alive.current) return;
          const original = A.pending().begin(preview, values, active.current);
          active.current = original; setIntent(original); setDraft(values); setPreview(null); setConsent(false);
          try { acceptResult(await api.adopt(original, preview.write_context.write_token), original); }
          catch (e) {
            if (A.isRejected(e)) {
              // Only an authentic, definitive non-commit permits a new preview. Unknown responses keep the original key.
              const rejected = A.pending().reject(original, e);
              if (alive.current) { active.current = rejected; setIntent(rejected); setError(e.message + ' 填写内容已保留，请重新预检并确认。'); }
            } else if (alive.current) setError(window.WorkbenchTerms.outcomes.pending('采用'));
          }
        });
      } catch (e) { if (alive.current) setStorageError(e.message); }
      finally { lock.current = false; if (alive.current) { setBusy(false); refresh(); } }
    }
    function close() {
      if (previewRequest.current) previewRequest.current.abort();
      setOpen(false); setPreview(null); setConsent(false);
    }
    function finish() {
      try { A.pending().finish(intent, result); setResult(null); setOpen(false); setNotice(window.WorkbenchTerms.outcomes.done('采用')); }
      catch (e) { setStorageError(e.message); }
    }
    function cancelRejected() {
      try { A.pending().cancelRejected(intent); setOpen(false); setNotice('已结束本次未采用，原正式计划未改变。'); }
      catch (e) { setStorageError(e.message); }
    }
    function dismissReplaced() {
      try {
        A.pending().dismissReplaced(intent, replacedInfo); setReplacedInfo(null); setOpen(false);
        setNotice('已结束本机的旧来源待确认记录，原数据库中的采用结果未作更改。');
      } catch (e) { setStorageError(e.message); }
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
      {storageError && !open && <span className="ra-inline" role="alert">{storageError}<U.Button icon="refresh-cw" disabled={busy} onClick={() => { readStorage(); refresh(); }}>刷新上次操作记录</U.Button></span>}
      {intent && !open && <span className="ra-inline">{result ? '采用结果已确认。' : pending ? '上次操作已保留，结果待确认。' : '上次没有采用，请重新预检。'}</span>}
      {open && <U.Dialog value={display} intent={intent} result={result} preview={preview} draft={draft} consent={consent} busy={busy || checking}
        candidateDisplay={targetDisplay} replacedInfo={replacedInfo}
        error={storageError || error} storageError={storageError} onReadStorage={() => { readStorage(); refresh(); }}
        notice={[intent && intent.candidate_ref !== candidateRef ? '另一个候选方案还有没确认的采用操作，请先确认那条记录。' : '',
          notice || (intent && intent.phase === 'rejected' && !preview ? '上次采用被拒绝了，填写内容已保留。请重新预检并再次确认。' : '')].filter(Boolean).join(' ')}
        onChange={setDraft} onConsent={setConsent} onClose={close} onPreview={inspect} onConfirm={submit} onLookup={refresh} onFinish={finish} onCancelRejected={cancelRejected} onDismissReplaced={dismissReplaced} onNavigate={onNavigate} />}
    </span>;
  }
  window.RunAdoptionAction = function RunAdoptionAction(props) { return <Session key={props.candidateRef || 'missing'} {...props} />; };
})();
