(function () {
  'use strict';
  const C = window.DashboardContract, KEY = 'aps_dashboard_pending_v1', EVENT = KEY + '_changed';
  function valid(v) {
    try { return v && v.version === 1 && /^dashboard-[a-f0-9]{48}$/.test(v.request_key) && C.ref(v.item_ref) && ['transition', 'reopen'].includes(v.action)
      && ['pending', 'confirmed', 'rejected'].includes(v.phase) && C.object(v.input) && C.object(v.source) && C.object(v.risk)
      && !!C.baseHandling(v.before) && !!C.baseHandling(C.expected(v)) && (v.phase !== 'confirmed' || !!C.receipt(v.receipt, v)); } catch (_) { return false; }
  }
  function read() {
    let raw; try { raw = localStorage.getItem(KEY); } catch (_) { throw new Error('原处置恢复记录不可读，不能开始新的处置。'); }
    if (raw === null) return null;
    let value; try { value = JSON.parse(raw); } catch (_) { throw new Error('原处置恢复记录损坏，请保留现场。'); }
    C.check(valid(value), '原处置恢复记录不完整，不能换请求重做。'); return value;
  }
  function save(value, previous) {
    C.check(C.equal(read(), previous), '原请求已在其他页面变化，未覆盖。'); C.check(value === null || valid(value));
    try { if (value === null) localStorage.removeItem(KEY); else localStorage.setItem(KEY, JSON.stringify(value)); }
    catch (_) { throw new Error('原请求无法持久保存，不能开始处置。'); }
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
    function accept(v, original) { C.receipt(v, original); save({ ...original, phase: 'confirmed', receipt: v }, original); if (mounted.current) { setError(null); setNotice('处置回执已确认。'); } }
    async function lookup() {
      if (running.current || !active.current || active.current.phase !== 'pending') return;
      const original = active.current; running.current = true; setBusy(true); setError(null);
      try { const v = await api.lookup(original); if (v) accept(v, original); else if (mounted.current) setNotice('尚未查到原回执，原请求仍可能完成；保留原 key，不重新提交。'); }
      catch (e) { if (mounted.current) setError(e); }
      finally { running.current = false; if (mounted.current) setBusy(false); }
    }
    React.useEffect(() => { if (initial.saved && initial.saved.phase === 'pending') lookup(); }, []);
    async function submit(item, action, input) {
      if (running.current || storageError || active.current) return;
      running.current = true; setBusy(true); setError(null); setNotice('');
      let original;
      try {
        C.check(navigator.locks && typeof navigator.locks.request === 'function', '浏览器请求锁不可用，暂不能开始处置。');
        await navigator.locks.request(KEY, { ifAvailable: true }, async acquired => {
          C.check(acquired, '另一页面正在处置，请先读取原请求。'); C.check(read() === null, '存在原处置请求，须先核实。');
          C.check(item.write_context && item.write_context.capabilities[action] === true, '该条目未提供当前处置能力，请刷新。');
          original = { version: 1, request_key: 'dashboard-' + Array.from(crypto.getRandomValues(new Uint8Array(24)), n => n.toString(16).padStart(2, '0')).join(''),
            phase: 'pending', item_ref: item.item_ref, subject: item.subject, action, input, before: C.baseHandling(item.handling), source: item.source, risk: item.risk };
          save(original, null);
          try { accept(await api.command(original, item.write_context.write_token), original); }
          catch (e) {
            if (C.isRejected(e)) save({ ...original, phase: 'rejected' }, original);
            if (mounted.current) { setError(e); setNotice(C.isRejected(e) ? '本次未写入，请明确刷新后再处置。' : '结果尚未确认，已保留原请求。'); }
          }
        });
      } catch (e) { if (mounted.current) setStorageError(e); }
      finally { running.current = false; if (mounted.current) setBusy(false); }
      if (original && read() && read().phase === 'pending') await lookup();
    }
    function finish() {
      if (running.current) return false;
      try { const value = read(); C.check(value && value.phase !== 'pending', '未知结果不能丢弃原请求。'); save(null, value); setError(null); setNotice(''); return true; }
      catch (e) { setStorageError(e); return false; }
    }
    return { saved, busy, error, storageError, notice, lookup, submit, finish, sync };
  }
  function useRead(load, dependencies, enabled = true) { return window.APSResourceSession.useQuery(load, dependencies, enabled); }
  const tabs = { items: '处置清单', analysis: '影响分析', compare: '方案对比', records: '处置历史' };
  function context(value = {}) {
    C.check(C.object(value) && Object.keys(value).every(k => ['scope', 'tab', 'item_ref', 'history_page', 'source'].includes(k)) && (value.source === undefined || value.source === 'production'), '值班台来源上下文无效，未忽略条件。');
    const q = C.scope(value.scope === undefined ? {} : value.scope), tab = value.tab === undefined ? 'items' : value.tab;
    const selected = value.item_ref === undefined ? null : value.item_ref, historyPage = value.history_page === undefined ? 1 : value.history_page;
    C.check(Object.prototype.hasOwnProperty.call(tabs, tab) && (selected === null || C.ref(selected)) && Number.isSafeInteger(historyPage) && historyPage > 0);
    return { q, tab, selected, historyPage };
  }
  window.DashboardSession = { KEY, read, save, useCommand, useRead, context, tabs };
})();
