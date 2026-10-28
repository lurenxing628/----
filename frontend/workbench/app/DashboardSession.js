(function () {
  'use strict';
  const C = window.DashboardContract, KEY = 'aps_dashboard_pending_v1', EVENT = KEY + '_changed';
  function valid(v) {
    try { return v && v.version === 1 && /^dashboard-[a-f0-9]{48}$/.test(v.request_key) && C.ref(v.item_ref) && ['transition', 'reopen'].includes(v.action)
      && ['pending', 'confirmed', 'rejected'].includes(v.phase) && C.object(v.input) && C.object(v.source) && C.object(v.risk)
      && !!C.baseHandling(v.before) && !!C.baseHandling(C.expected(v)) && (v.phase !== 'confirmed' || !!C.receipt(v.receipt, v)); } catch (_) { return false; }
  }
  const { read, save } = window.APSWorkbenchTransport.pendingStore({
    key: KEY, event: EVENT, validate: valid,
    readError: '上次操作记录读不出来，不能开始新的处置。请重新打开页面。',
    corruptError: '上次操作记录已损坏，不能开始新的处置。请不要再操作，联系维护人员。',
    invalidError: '上次操作记录不完整，不能重新提交。请不要再操作，联系维护人员。',
    conflictError: '上次操作已在另一个页面变化，这里没有覆盖它。请刷新后重试。',
    invalidWriteError: '值班台读到的数据不完整，请刷新后重试。',
    writeError: '上次操作记录保存不了，不能开始处置。请重新打开页面。'
  });
  function useCommand() {
    const [initial] = React.useState(() => { try { return { saved: read(), error: null }; } catch (error) { return { saved: error.saved || null, error }; } });
    const [saved, setSaved] = React.useState(initial.saved), [storageError, setStorageError] = React.useState(initial.error);
    const [error, setError] = React.useState(null), [busy, setBusy] = React.useState(false), [notice, setNotice] = React.useState('');
    const mounted = React.useRef(false), running = React.useRef(false), active = React.useRef(saved); active.current = saved;
    function sync(event) {
      try {
        const v = event && event.type === EVENT ? event.detail : read();
        if (!C.equal(v, active.current)) { active.current = v; setSaved(v); setError(null); setNotice(''); }
        setStorageError(null);
      } catch (e) {
        if (e.saved !== undefined && !C.equal(e.saved, active.current)) { active.current = e.saved; setSaved(e.saved); setError(null); setNotice(''); }
        setStorageError(e);
      }
    }
    React.useEffect(() => {
      mounted.current = true; const changed = e => { if (!e.key || e.key === KEY) sync(e); };
      window.addEventListener('storage', changed); window.addEventListener(EVENT, changed);
      return () => { mounted.current = false; window.removeEventListener('storage', changed); window.removeEventListener(EVENT, changed); };
    }, []);
    // C.command/C.lookup already checked the receipt; a failed local write belongs to storageError.
    function accept(v, original) {
      if (!C.equal(active.current, original)) { if (mounted.current) sync(); return; }
      const confirmed = { ...original, phase: 'confirmed', receipt: v };
      try { save(confirmed, original); active.current = confirmed; }
      catch (e) {
        if (!mounted.current) return;
        if (!C.equal(active.current, confirmed)) sync();
        setStorageError(e);
      }
      if (mounted.current && C.equal(active.current, confirmed)) { setError(null); setNotice('请点「完成」查看最新风险。'); }
    }
    async function lookup(preserveError = false) {
      if (running.current || !active.current || active.current.phase !== 'pending') return;
      const original = active.current; running.current = true; setBusy(true); if (!preserveError) setError(null);
      try { const v = await C.lookup(original); if (v) accept(v, original); else if (mounted.current && C.equal(active.current, original)) setNotice('还是没有查到结果。请稍后再点「查询结果」，不要重复提交。'); }
      catch (e) { if (mounted.current && C.equal(active.current, original)) setError(e); }
      finally { running.current = false; if (mounted.current) setBusy(false); }
    }
    React.useEffect(() => { if (initial.saved && initial.saved.phase === 'pending') lookup(); }, []);
    async function submit(item, action, input) {
      if (running.current || storageError || active.current) return;
      running.current = true; setBusy(true); setError(null); setNotice('');
      let original, needLookup = false;
      try {
        if (!navigator.locks || typeof navigator.locks.request !== 'function') { if (mounted.current) setError(new Error('当前浏览器不支持，请用 Chrome 打开。')); return; }
        await navigator.locks.request(KEY, { ifAvailable: true }, async acquired => {
          if (!acquired) { if (mounted.current) setError(new Error('另一个页面正在处置，这里没有开始新的处置。请先完成那边的处置。')); return; }
          if (!mounted.current) return;
          if (!item.write_context || item.write_context.capabilities[action] !== true) { if (mounted.current) setError(new Error('这条记录现在不能处置，请刷新后重试。')); return; }
          original = { version: 1, request_key: window.APSWorkbenchTransport.requestKey('dashboard'),
            phase: 'pending', item_ref: item.item_ref, subject: item.subject, action, input, before: C.baseHandling(item.handling), source: item.source, risk: item.risk };
          save(original, null); active.current = original;
          try { accept(await C.command(original, item.write_context.write_token), original); }
          catch (e) {
            if (!C.equal(active.current, original)) { if (mounted.current) sync(); return; }
            // Receipt owns the rejected/pending outcome; the error box owns the failure reason.
            if (window.APSWorkbenchTransport.rejected(e)) {
              const rejected = { ...original, phase: 'rejected' };
              try { save(rejected, original); active.current = rejected; }
              catch (storageErr) {
                if (!mounted.current) return;
                if (!C.equal(active.current, rejected)) { sync(); setStorageError(storageErr); return; }
                setStorageError(storageErr);
              }
              if (mounted.current && C.equal(active.current, rejected)) setError(e);
            } else {
              needLookup = true;
              if (mounted.current) setError(e);
            }
          }
        });
      } catch (e) { if (mounted.current) setStorageError(e); }
      finally { running.current = false; if (mounted.current) setBusy(false); }
      // Only an unanswered command follows up; the lookup keeps the submit failure unless it finds a receipt or fails itself.
      if (mounted.current && needLookup && active.current && active.current.request_key === original.request_key && active.current.phase === 'pending') await lookup(true);
    }
    function finish() {
      if (running.current) return false;
      try {
        const value = active.current && active.current.phase !== 'pending' ? active.current : read();
        C.check(value && value.phase !== 'pending', '上次处置的结果还没有确认，不能丢弃这条记录。请先点「查询结果」。');
        save(null, value); setError(null); setNotice(''); return true;
      } catch (e) { setStorageError(e); return false; }
    }
    return { saved, busy, error, storageError, notice, lookup: () => lookup(), submit, finish, sync };
  }
  function useRead(load, dependencies, enabled = true) { return window.APSResourceSession.useQuery(load, dependencies, enabled); }
  const tabs = { items: '处置清单', analysis: '影响分析', compare: '方案对比', records: '处置历史' };
  function context(value) {
    C.check(C.object(value) && Object.keys(value).every(k => ['scope', 'tab', 'item_ref', 'history_page', 'source'].includes(k)) && (value.source === undefined || value.source === 'production'), '本页数据已过期，请刷新后重试。');
    const q = C.scope(value.scope === undefined ? {} : value.scope), tab = value.tab === undefined ? 'items' : value.tab;
    const selected = value.item_ref === undefined ? null : value.item_ref, historyPage = value.history_page === undefined ? 1 : value.history_page;
    C.check(Object.prototype.hasOwnProperty.call(tabs, tab) && (selected === null || C.ref(selected)) && Number.isSafeInteger(historyPage) && historyPage > 0);
    return { q, tab, selected, historyPage };
  }
  window.DashboardSession = { KEY, read, save, useCommand, useRead, context, tabs };
})();
