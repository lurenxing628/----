(function () {
  'use strict';
  const A = window.TrialAPI;
  function useRead(load, deps, enabled = true) {
    const read = window.APSResourceSession.useQuery(load, deps, enabled);
    return { ...read, busy: read.loading };
  }
  function useCommands(onReceipt) {
    const [state, set] = React.useState({ key: null, error: null, busy: false, note: '' }), running = React.useRef(false);
    const live = React.useRef(true), callback = React.useRef(onReceipt), settled = React.useRef(null); callback.current = onReceipt;
    const patch = data => { if (live.current) set(s => ({ ...s, ...data })); };
    // The server outcome is final; only the local key may remain. settled keeps that key until a later clear succeeds.
    function release(key, done, note) {
      try { A.clear(key); settled.current = null; patch({ key: null, ...done }); }
      catch (error) { settled.current = { key, note }; patch({ key, error, note }); }
    }
    // Restore and lookup share this: a settled key retries its local cleanup instead of asking the server again.
    function retry(key) {
      if (!settled.current || settled.current.key !== key) { settled.current = null; return false; }
      release(key, { error: null, note: '' }, settled.current.note); return true;
    }
    function restore() { try { const key = A.pending(); if (!retry(key)) patch({ key, error: null, note: '' }); } catch (error) { patch({ error }); } }
    function clearError() { if (live.current && !running.current) set(s => s.busy || s.key ? s : { ...s, error: null, note: '' }); }
    React.useEffect(() => {
      live.current = true; restore();
      const listener = e => { if (e.key === A.PENDING_KEY || e.key === null) restore(); };
      window.addEventListener('storage', listener);
      return () => { live.current = false; window.removeEventListener('storage', listener); };
    }, []);
    async function confirmed(receipt, key) {
      if (!live.current) return;
      // Ignore write contexts embedded in old immutable receipts; the parent reads the object afresh.
      // A failed local clear keeps the key and its error, but never withholds the confirmed receipt.
      patch({ receipt }); release(key, { error: null, note: '' }, '');
      if (live.current) callback.current(receipt);
    }
    async function execute(intent, token) {
      if (running.current) return false;
      let key; running.current = true; patch({ busy: true, error: null, receipt: null, note: '' });
      try {
        key = A.reserve(); patch({ key });
        const result = await A.command(intent, token, key); await confirmed(result, key); return true;
      } catch (error) {
        if (key && window.APSWorkbenchTransport.rejected(error)) release(key, { error, note: '这次没有写入。填写内容已保留，请点「刷新」后重新确认。' }, '这次没有写入，但本机操作记录还没清掉。请点「查询结果」重试清理。');
        else patch({ error, ...(key ? { key, note: window.WorkbenchTerms.outcomes.pending('提交') } : {}) });
        return false;
      } finally { running.current = false; patch({ busy: false }); }
    }
    async function lookup() {
      if (running.current) return;
      running.current = true; patch({ busy: true, error: null });
      try {
        const key = A.pending(); if (retry(key)) return;
        if (!key) { patch({ key: null, note: '' }); return; }
        const result = await A.lookup(key);
        if (result.state === 'committed') await confirmed(result.receipt, key);
        else patch({ key, note: window.WorkbenchTerms.outcomes.pending('提交') });
      } catch (error) { patch({ error }); }
      finally { running.current = false; patch({ busy: false }); }
    }
    return { ...state, execute, lookup, restore, clearError, blocked: state.busy || !!state.key || !!state.error };
  }
  window.TrialSession = { useRead, useCommands };
})();
