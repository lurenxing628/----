(function () {
  'use strict';
  const A = window.TrialAdoptionAPI, KEY = 'aps_workbench_trial_adoption_pending_v1', EVENT = KEY + '_changed';
  function valid(v) {
    try {
      return A.shape(v, ['schema_version', 'scenario_ref', 'request_key', 'input', 'preview', 'phase'], v.phase === 'committed' ? ['receipt'] : [])
        && v.schema_version === 1 && A.key(v.request_key)
        && A.shape(v.preview, ['scenario_ref', 'draft_ref', 'baseline', 'task_count', 'scope_complete', 'data_context_ref'])
        && A.overview(v.preview) && v.scenario_ref === v.preview.scenario_ref
        && A.equal(A.input(v.input), v.input) && ['pending', 'rejected', 'committed'].includes(v.phase) && (v.phase !== 'committed' || !!A.receipt(v.receipt, v));
    } catch (_) { return false; }
  }
  const { read, save } = window.APSWorkbenchTransport.pendingStore({
    key: KEY, event: EVENT, validate: valid,
    readError: '读不到上次采用操作的记录，不能开始新的采用。请重新打开页面。',
    corruptError: '上次采用操作的记录已损坏。请不要再操作，联系维护人员。',
    invalidError: '上次采用操作的记录不完整。请不要再操作，联系维护人员。',
    conflictError: '上次采用操作的记录已变化，没有覆盖其他页面的记录。',
    invalidWriteError: '读到的采用数据不完整或对不上，这次没有确认采用。请刷新重试。',
    writeError: '存不下这次采用操作的记录，这次没有提交。请点「查询结果」确认上次操作。'
  });
  function begin(preview, values, previous) {
    const scope = A.overview(preview), input = A.input(values);
    A.check(!previous || valid(previous) && previous.phase === 'rejected' && A.sameScope(previous.preview, scope) && A.equal(previous.input, input),
      '上次提交的试调方案、原因和经办人已绑定，改了内容不能沿用同一个操作编号。');
    const requestKey = previous ? previous.request_key : window.APSWorkbenchTransport.requestKey('trial-adoption');
    return save({ schema_version: 1, scenario_ref: scope.scenario_ref, request_key: requestKey, input, preview: scope, phase: 'pending' }, previous);
  }
  // A fresh draft starts from the handler this machine remembered, so the dirty guard compares against that prefill rather than an empty string.
  const remembered = () => window.WorkbenchHandlerMemory.read().value, empty = () => ({ reason: '', declared_operator: remembered() });
  function storageMessage(e, current = e && e.saved) {
    if (current && current.phase === 'committed') return '已收到采用结果，但本机没能保存这次操作记录。';
    if (current && current.phase === 'rejected') return '本次采用未通过，但本机没能保存这次操作记录。';
    return e.message;
  }
  function useSession({ scenarioRef, data, disabled, onAdopted }) {
    const [initial] = React.useState(() => { try { return { saved: read(), error: '' }; } catch (e) { return { saved: e.saved || null, error: storageMessage(e) }; } });
    const [saved, setSaved] = React.useState(initial.saved), [storageError, setStorageError] = React.useState(initial.error);
    const [draft, setDraft] = React.useState(() => initial.saved ? initial.saved.input : empty());
    const [open, setOpen] = React.useState(false), [preview, setPreview] = React.useState(null), [consent, setConsent] = React.useState(false);
    const [busy, setBusy] = React.useState(false), [checking, setChecking] = React.useState(false), [error, setError] = React.useState(''), [notice, setNotice] = React.useState('');
    window.WorkbenchGuards.useDirtyGuard({ dirty: open && !saved && (!!draft.reason || draft.declared_operator !== remembered()),
      message: '正式采用的原因或经办人还没提交。' });
    const [revision, refresh] = React.useReducer(v => v + 1, 0);
    const mounted = React.useRef(false), lock = React.useRef(false), request = React.useRef(null), active = React.useRef(saved), current = React.useRef(null);
    const callback = React.useRef(onAdopted), notified = React.useRef(null); callback.current = onAdopted; active.current = saved;
    let original = null, sourceError = '';
    try { original = A.source(scenarioRef, data); } catch (e) { sourceError = e.message; }
    current.current = { original, disabled, preview, consent, draft, storageError }; const identity = JSON.stringify(original);
    React.useEffect(() => { mounted.current = true; return () => { mounted.current = false; if (request.current) request.current.abort(); }; }, []);
    React.useEffect(() => { current.current = { ...current.current, preview: null, consent: false }; setPreview(null); setConsent(false); if (request.current) request.current.abort(); }, [identity, disabled]);
    function sync(event) {
      try {
        const value = event && event.type === EVENT ? event.detail : read();
        if (value !== active.current && !A.equal(value, active.current)) {
          const switched = !active.current || !value || value.request_key !== active.current.request_key;
          const nextDraft = value ? value.input : empty();
          active.current = value;
          current.current = { ...current.current, preview: null, consent: false, draft: nextDraft, storageError: '' };
          if (!mounted.current) return;
          setSaved(value); setPreview(null); setConsent(false); setDraft(nextDraft);
          if (switched || value.phase === 'committed') { setError(''); setNotice(''); }
        } else {
          current.current = { ...current.current, storageError: '' };
        }
        if (mounted.current) setStorageError('');
      } catch (e) {
        const changed = e.saved !== undefined && !A.equal(e.saved, active.current);
        const nextDraft = changed ? (e.saved ? e.saved.input : empty()) : current.current.draft;
        if (changed) active.current = e.saved;
        const msg = storageMessage(e, e.saved !== undefined ? e.saved : active.current);
        current.current = { ...current.current, ...(changed ? { preview: null, consent: false, draft: nextDraft } : {}), storageError: msg };
        if (!mounted.current) return;
        if (changed) { setSaved(e.saved); setDraft(nextDraft); }
        setStorageError(msg);
      }
    }
    React.useEffect(() => {
      const changed = e => { if (!e.key || e.key === KEY) sync(e); };
      window.addEventListener('storage', changed); window.addEventListener(EVENT, changed);
      return () => { window.removeEventListener('storage', changed); window.removeEventListener(EVENT, changed); };
    }, []);
    const result = saved && saved.phase === 'committed' ? saved.receipt : null;
    React.useEffect(() => {
      if (!result || notified.current === result.receipt_ref) return;
      notified.current = result.receipt_ref;
      const failed = () => { if (mounted.current) setNotice('采用已确认，但相关页面没有更新成功。请重新打开正式计划。'); };
      try { Promise.resolve(callback.current(result)).catch(failed); } catch (_) { failed(); }
    }, [result]);
    function accept(value, intent) {
      if (!A.equal(active.current, intent)) { if (mounted.current) sync(); return; }
      const committed = { ...intent, phase: 'committed', receipt: value };
      try { save(committed, intent); active.current = committed; }
      catch (e) {
        if (!mounted.current) return;
        if (!A.equal(active.current, committed)) { sync(); setStorageError(e.message); return; }
        setStorageError(storageMessage(e, active.current));
      }
      if (mounted.current && A.equal(active.current, committed)) { setError(''); setNotice(''); }
    }
    async function lookup(signal) {
      const intent = active.current;
      if (!intent || intent.phase === 'rejected' || lock.current || storageError) return;
      setChecking(true);
      try {
        const found = await A.lookup(intent, signal);
        if (!mounted.current || signal && signal.aborted) return;
        if (found.state === 'not_observed') {
          if (found.may_be_in_flight === false) {
            if (!A.equal(active.current, intent)) { sync(); return; }
            try { save(null, intent); } catch (e) {
              if (active.current !== null) sync();
              setStorageError(e.message);
            }
            if (active.current === null) {
              setError('');
              setNotice('上次采用记录的数据来源已失效，已结束本机待确认记录。请对当前试调方案重新预检。');
            }
          } else if (A.equal(active.current, intent)) { setError(''); setNotice(window.WorkbenchTerms.outcomes.pending('采用')); }
        } else accept(found, intent);
      } catch (e) { if (mounted.current && !(signal && signal.aborted) && A.equal(active.current, intent)) setError('上次采用的结果还没查到。' + e.message); }
      finally { if (mounted.current && !(signal && signal.aborted)) setChecking(false); }
    }
    React.useEffect(() => {
      if (!saved || saved.phase !== 'pending' || storageError || lock.current) return undefined;
      const controller = new AbortController(); lookup(controller.signal);
      return () => { controller.abort(); setChecking(false); };
    }, [saved, revision, storageError]);
    async function inspect() {
      if (lock.current || storageError || disabled || !original || saved && saved.phase !== 'rejected') return;
      if (saved && !A.sameScope(saved.preview, original)) { setError('上次采用操作属于另一个试调方案或范围，请先查询那条记录的结果。'); return; }
      lock.current = true; setBusy(true); setOpen(true); setPreview(null); setConsent(false); setError(''); setNotice('');
      const controller = new AbortController(); request.current = controller;
      try {
        const value = await A.preview(original, controller.signal);
        if (mounted.current && !controller.signal.aborted && !current.current.disabled && A.equal(original, current.current.original)) setPreview(value);
      } catch (e) { if (mounted.current && !controller.signal.aborted) setError(e.message); }
      finally { lock.current = false; if (mounted.current) setBusy(false); }
    }
    async function submit() {
      if (lock.current || storageError || disabled || !original || !preview || !preview.validation.can_adopt || !consent
        || !A.sameScope(original, A.overview(preview)) || saved && saved.phase !== 'rejected') return;
      let values; try { values = A.input({ confirm: true, reason: draft.reason, declared_operator: draft.declared_operator }); }
      catch (e) { setError(e.message); return; }
      window.WorkbenchHandlerMemory.write(values.declared_operator);
      const initialActive = active.current;
      lock.current = true; setBusy(true); setError(''); setNotice('');
      try {
        if (!navigator.locks || typeof navigator.locks.request !== 'function') { if (mounted.current) setError('当前浏览器不支持这项操作，请用 Chrome 打开。'); return; }
        await navigator.locks.request(KEY, { ifAvailable: true }, async acquired => {
          if (!acquired) { if (mounted.current) setError('另一个页面正在处理这次采用，请先在那个页面点「查询结果」。'); return; }
          const latest = current.current;
          if (!mounted.current || latest.disabled || latest.storageError || !latest.original || latest.preview !== preview || !latest.consent
            || !A.equal(active.current, initialActive) || active.current && active.current.phase !== 'rejected'
            || !A.equal(original, latest.original)
            || !A.equal(A.input({ confirm: true, reason: latest.draft.reason, declared_operator: latest.draft.declared_operator }), values)) return;
          const intent = begin(preview, values, active.current);
          active.current = intent; current.current = { ...current.current, preview: null, consent: false }; setSaved(intent); setDraft(intent.input); setPreview(null); setConsent(false);
          try { accept(await A.adopt(intent, preview.write_context.write_token), intent); }
          catch (e) {
            if (!A.equal(active.current, intent)) { if (mounted.current) sync(); return; }
            if (window.APSWorkbenchTransport.rejected(e)) {
              const rejected = { ...intent, phase: 'rejected' };
              try { save(rejected, intent); active.current = rejected; }
              catch (storageErr) {
                if (!mounted.current) return;
                if (!A.equal(active.current, rejected)) { sync(); setStorageError(storageErr.message); return; }
                setStorageError(storageMessage(storageErr, active.current));
              }
              if (mounted.current && A.equal(active.current, rejected)) setError(window.WorkbenchTerms.outcomes.rejected('采用', e.message));
            } else if (mounted.current) setError(window.WorkbenchTerms.outcomes.unknown('采用'));
          }
        });
      } catch (e) { if (mounted.current) setStorageError(e.message); }
      finally { lock.current = false; if (mounted.current) { setBusy(false); refresh(); } }
    }
    function finish() {
      try {
        A.check(saved && saved.phase !== 'pending', '结果还不确定，不能丢弃这次操作记录。'); save(null, saved);
        current.current = { ...current.current, preview: null, consent: false }; setOpen(false); setPreview(null); setConsent(false); setDraft(empty());
        setError(''); setNotice(saved.phase === 'committed' ? '这次采用结果已确认完成。' : '本次操作已结束，未采用。');
      } catch (e) { setStorageError(e.message); }
    }
    function close() { if (request.current) request.current.abort(); current.current = { ...current.current, preview: null, consent: false }; setOpen(false); setPreview(null); setConsent(false); if (!active.current) { setError(''); setDraft(empty()); } }
    return { saved, result, draft, open, preview, consent, busy: busy || checking, error, notice, storageError, sourceError, original, disabled,
      setOpen, setConsent: value => { current.current = { ...current.current, consent: value }; setConsent(value); },
      change: value => { if (!active.current) { current.current = { ...current.current, draft: value, consent: false }; setDraft(value); setConsent(false); } }, inspect, submit, lookup: () => lookup(), sync, close, finish };
  }
  window.TrialAdoptionState = { KEY, read, save, useSession };
})();
