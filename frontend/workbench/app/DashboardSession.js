(function () {
  'use strict';
  const C = window.DashboardContract, KEY = 'aps_dashboard_pending_v1', EVENT = KEY + '_changed';
  function valid(v) {
    try { return v && v.version === 1 && /^dashboard-[a-f0-9]{48}$/.test(v.request_key) && C.ref(v.item_ref) && ['transition', 'reopen'].includes(v.action)
      && ['pending', 'confirmed', 'rejected'].includes(v.phase) && C.object(v.input) && C.object(v.source) && C.object(v.risk)
      && !!C.baseHandling(v.before) && !!C.baseHandling(C.expected(v)) && (v.phase !== 'confirmed' || !!C.receipt(v.receipt, v)); } catch (_) { return false; }
  }
  function read() {
    let raw; try { raw = localStorage.getItem(KEY); } catch (_) { throw new Error('上次操作记录读不出来，不能开始新的处置。请重新打开页面。'); }
    if (raw === null) return null;
    let value; try { value = JSON.parse(raw); } catch (_) { throw new Error('上次操作记录已损坏，不能开始新的处置。请不要再操作，联系维护人员。'); }
    C.check(valid(value), '上次操作记录不完整，不能重新提交。请不要再操作，联系维护人员。'); return value;
  }
  function save(value, previous) {
    C.check(C.equal(read(), previous), '上次操作已在另一个页面变化，这里没有覆盖它。请刷新后重试。'); C.check(value === null || valid(value));
    try { if (value === null) localStorage.removeItem(KEY); else localStorage.setItem(KEY, JSON.stringify(value)); }
    catch (_) { throw new Error('上次操作记录保存不了，不能开始处置。请重新打开页面。'); }
    C.check(C.equal(read(), value)); window.dispatchEvent(new Event(EVENT)); return value;
  }
  function useCommand(api) {
    const [initial] = React.useState(() => { try { return { saved: read(), error: null }; } catch (error) { return { saved: null, error }; } });
    const [saved, setSaved] = React.useState(initial.saved), [storageError, setStorageError] = React.useState(initial.error);
    const [error, setError] = React.useState(null), [busy, setBusy] = React.useState(false), [notice, setNotice] = React.useState('');
    const mounted = React.useRef(false), running = React.useRef(false), active = React.useRef(saved); active.current = saved;
    function sync() { try { const v = read(); active.current = v; setSaved(v); setStorageError(null); } catch (e) { setStorageError(e); } }
    React.useEffect(() => {
      mounted.current = true; const changed = e => { if (!e.key || e.key === KEY) sync(); };
      window.addEventListener('storage', changed); window.addEventListener(EVENT, changed);
      return () => { mounted.current = false; window.removeEventListener('storage', changed); window.removeEventListener(EVENT, changed); };
    }, []);
    function accept(v, original) { C.receipt(v, original); save({ ...original, phase: 'confirmed', receipt: v }, original); if (mounted.current) { setError(null); setNotice('请点「完成」查看最新风险。'); } }
    async function lookup() {
      if (running.current || !active.current || active.current.phase !== 'pending') return;
      const original = active.current; running.current = true; setBusy(true); setError(null);
      try { const v = await api.lookup(original); if (v) accept(v, original); else if (mounted.current) setNotice('还是没有查到结果。请稍后再点「查询结果」，不要重复提交。'); }
      catch (e) { if (mounted.current) setError(e); }
      finally { running.current = false; if (mounted.current) setBusy(false); }
    }
    React.useEffect(() => { if (initial.saved && initial.saved.phase === 'pending') lookup(); }, []);
    async function submit(item, action, input) {
      if (running.current || storageError || active.current) return;
      running.current = true; setBusy(true); setError(null); setNotice('');
      let original;
      try {
        C.check(navigator.locks && typeof navigator.locks.request === 'function', '当前浏览器不支持，请用 Chrome 打开。');
        await navigator.locks.request(KEY, { ifAvailable: true }, async acquired => {
          C.check(acquired, '另一个页面正在处置，这里没有开始新的处置。请先完成那边的处置。'); C.check(read() === null, '上次处置还没确认结果，不能再提交新的处置。请点「查询结果」。');
          C.check(item.write_context && item.write_context.capabilities[action] === true, '这条记录现在不能处置，请刷新后重试。');
          original = { version: 1, request_key: 'dashboard-' + Array.from(crypto.getRandomValues(new Uint8Array(24)), n => n.toString(16).padStart(2, '0')).join(''),
            phase: 'pending', item_ref: item.item_ref, subject: item.subject, action, input, before: C.baseHandling(item.handling), source: item.source, risk: item.risk };
          save(original, null);
          try { accept(await api.command(original, item.write_context.write_token), original); }
          catch (e) {
            if (C.isRejected(e)) save({ ...original, phase: 'rejected' }, original);
            if (mounted.current) { setError(e); setNotice(C.isRejected(e) ? window.WorkbenchTerms.outcomes.rejected('处置', e.message) : window.WorkbenchTerms.outcomes.unknown('处置')); }
          }
        });
      } catch (e) { if (mounted.current) setStorageError(e); }
      finally { running.current = false; if (mounted.current) setBusy(false); }
      if (original && read() && read().phase === 'pending') await lookup();
    }
    function finish() {
      if (running.current) return false;
      try { const value = read(); C.check(value && value.phase !== 'pending', '上次处置的结果还没有确认，不能丢弃这条记录。请先点「查询结果」。'); save(null, value); setError(null); setNotice(''); return true; }
      catch (e) { setStorageError(e); return false; }
    }
    return { saved, busy, error, storageError, notice, lookup, submit, finish, sync };
  }
  function useRead(load, dependencies, enabled = true) { return window.APSResourceSession.useQuery(load, dependencies, enabled); }
  const tabs = { items: '处置清单', analysis: '影响分析', compare: '方案对比', records: '处置历史' };
  function context(value = {}) {
    C.check(C.object(value) && Object.keys(value).every(k => ['scope', 'tab', 'item_ref', 'history_page', 'source'].includes(k)) && (value.source === undefined || value.source === 'production'), '本页数据已过期，请刷新后重试。');
    const q = C.scope(value.scope === undefined ? {} : value.scope), tab = value.tab === undefined ? 'items' : value.tab;
    const selected = value.item_ref === undefined ? null : value.item_ref, historyPage = value.history_page === undefined ? 1 : value.history_page;
    C.check(Object.prototype.hasOwnProperty.call(tabs, tab) && (selected === null || C.ref(selected)) && Number.isSafeInteger(historyPage) && historyPage > 0);
    return { q, tab, selected, historyPage };
  }
  window.DashboardSession = { KEY, read, save, useCommand, useRead, context, tabs };
})();
