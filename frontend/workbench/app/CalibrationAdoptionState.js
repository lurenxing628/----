(function () {
  'use strict';
  const A = window.CalibrationAdoptionAPI, KEY = 'aps_calibration_adoption_pending_v1', EVENT = KEY + '_changed';
  function valid(value) {
    try {
      return value && value.version === 1 && A.key(value.request_key) && ['pending', 'rejected', 'committed'].includes(value.phase)
        && A.equal(A.input(value.input, true), value.input) && A.equal(A.binding(value.baseline), value.baseline)
        && (value.phase !== 'committed' || !!A.receipt(value.receipt, value));
    } catch (_) { return false; }
  }
  function read() {
    let raw; try { raw = localStorage.getItem(KEY); } catch (_) { throw new Error('无法读取原采纳请求，暂不能开始新采用。'); }
    if (raw === null) return null;
    let value; try { value = JSON.parse(raw); } catch (_) { throw new Error('原采纳恢复记录损坏，请保留现场，不能换请求重提。'); }
    A.check(valid(value), '原采纳恢复记录不完整，请保留现场，不能换请求重提。'); return value;
  }
  function save(value, previous) {
    A.check(A.equal(read(), previous), '原请求已变化，未覆盖其他页面的采纳记录。');
    A.check(value === null || valid(value));
    try { if (value === null) localStorage.removeItem(KEY); else localStorage.setItem(KEY, JSON.stringify(value)); }
    catch (_) { throw new Error('无法持久保存原采纳请求，未开始新的采用。'); }
    A.check(A.equal(read(), value), '原请求未完整保存，不能开始新的采用。');
    window.dispatchEvent(new Event(EVENT)); return value;
  }
  function begin(preview, previous) {
    A.check(!previous || previous.phase === 'rejected', '原请求结果尚未核实，不能开始新的采用。');
    return save({ version: 1, request_key: 'calibration-' + Array.from(crypto.getRandomValues(new Uint8Array(24)), n => n.toString(16).padStart(2, '0')).join(''),
      phase: 'pending', baseline: A.binding(preview.suggestion), input: A.input({ ...preview.input, confirm: true }, true) }, previous);
  }
  function useSession({ detail, stale, adapter }) {
    const api = React.useMemo(() => adapter || A.create(), [adapter]);
    const [initial] = React.useState(() => { try { return { saved: read(), error: '' }; } catch (e) { return { saved: null, error: e.message }; } });
    const [saved, setSaved] = React.useState(initial.saved), [storageError, setStorageError] = React.useState(initial.error);
    const [draft, setDraft] = React.useState(initial.saved ? { reason: initial.saved.input.reason, declared_operator: initial.saved.input.declared_operator } : { reason: '', declared_operator: '' });
    const [open, setOpen] = React.useState(false), [preview, setPreview] = React.useState(null), [consent, setConsent] = React.useState(false);
    const [busy, setBusy] = React.useState(false), [error, setError] = React.useState(''), [notice, setNotice] = React.useState('');
    const [revision, refresh] = React.useReducer(v => v + 1, 0);
    const mounted = React.useRef(false), lock = React.useRef(false), request = React.useRef(null), active = React.useRef(saved), source = React.useRef(detail);
    active.current = saved; source.current = detail;
    const identity = detail ? JSON.stringify(A.binding(detail.suggestion)) : '';
    React.useEffect(() => { mounted.current = true; return () => { mounted.current = false; if (request.current) request.current.abort(); }; }, []);
    React.useEffect(() => { setPreview(null); setConsent(false); if (request.current) request.current.abort(); }, [identity, stale]);
    function sync() {
      try { const value = read(); active.current = value; setSaved(value); setStorageError(''); }
      catch (e) { setStorageError(e.message); }
    }
    React.useEffect(() => {
      const changed = e => { if (!e.key || e.key === KEY) sync(); };
      window.addEventListener('storage', changed); window.addEventListener(EVENT, changed);
      return () => { window.removeEventListener('storage', changed); window.removeEventListener(EVENT, changed); };
    }, []);
    function accept(value, original) {
      A.receipt(value, original);
      const committed = { ...original, phase: 'committed', receipt: value };
      save(committed, original);
      if (mounted.current) { setSaved(committed); setError(''); setNotice(''); }
    }
    React.useEffect(() => {
      if (!saved || saved.phase !== 'pending' || storageError || lock.current) return undefined;
      let disposed = false; const controller = new AbortController(); setBusy(true);
      api.lookup(saved, controller.signal).then(value => {
        if (disposed) return;
        if (value) accept(value, saved);
        else setNotice('尚未查到原回执，请稍后查询；原请求仍可能完成，不会换 key 或自动重新提交。');
      }).catch(e => { if (!disposed) setError('原请求结果尚未核实。' + e.message); }).finally(() => { if (!disposed) setBusy(false); });
      return () => { disposed = true; controller.abort(); };
    }, [saved, api, revision, storageError]);
    function change(value) { setDraft(value); setPreview(null); setConsent(false); setError(''); }
    async function inspect() {
      if (lock.current || stale || storageError || !detail || saved && saved.phase !== 'rejected') return;
      if (saved && saved.baseline.template_operation_ref !== detail.suggestion.template_operation_ref) { setError('原请求属于另一模板，请先结束已明确拒绝的原请求。'); return; }
      let values; try { values = A.input(draft); } catch (e) { setError(e.message); return; }
      lock.current = true; setBusy(true); setPreview(null); setConsent(false); setError(''); setNotice('');
      const controller = new AbortController(); request.current = controller;
      try { const value = await api.preview(detail.suggestion, values, controller.signal);
        if (mounted.current && !controller.signal.aborted && A.equal(detail, source.current)) setPreview(value);
      } catch (e) { if (mounted.current && !controller.signal.aborted) setError(e.message); }
      finally { lock.current = false; if (mounted.current) setBusy(false); }
    }
    async function submit() {
      if (lock.current || stale || storageError || !preview || !preview.validation.can_adopt || !consent || !detail
        || !A.equal(A.binding(detail.suggestion), A.binding(preview.suggestion)) || !A.equal(A.input(draft), preview.input)) return;
      lock.current = true; setBusy(true); setError(''); setNotice('');
      try {
        A.check(navigator.locks && typeof navigator.locks.request === 'function', '浏览器请求锁不可用，不能开始采纳。');
        await navigator.locks.request(KEY, { ifAvailable: true }, async acquired => {
          A.check(acquired, '另一页面正在采纳，请先读取原请求。');
          const original = begin(preview, active.current);
          active.current = original; setSaved(original); setPreview(null); setConsent(false);
          try { accept(await api.adopt(original, preview.write_context.write_token), original); }
          catch (e) {
            if (A.isRejected(e)) { const rejected = save({ ...original, phase: 'rejected' }, original); if (mounted.current) setSaved(rejected); }
            if (mounted.current) setError(A.isRejected(e) ? e.message + ' 本次未采用；请明确刷新并重新预览。' : '采用响应未核实，已保留原请求，请查询回执。');
          }
        });
      } catch (e) { if (mounted.current) setStorageError(e.message); }
      finally { lock.current = false; if (mounted.current) { setBusy(false); refresh(); } }
    }
    function finish() {
      try { A.check(saved && saved.phase !== 'pending', '未知结果不能丢弃原请求。'); save(null, saved); setOpen(false); setPreview(null); setConsent(false); }
      catch (e) { setStorageError(e.message); }
    }
    return { saved, draft, open, preview, consent, busy, error, notice, storageError, setOpen, setConsent, change, inspect, submit, finish,
      lookup: refresh, sync, close: () => { if (request.current) request.current.abort(); setOpen(false); setPreview(null); setConsent(false); } };
  }
  window.CalibrationAdoptionState = { KEY, EVENT, read, save, begin, useSession };
})();
