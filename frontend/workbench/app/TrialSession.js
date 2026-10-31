(function () {
  'use strict';
  const A = window.TrialAPI, T = window.APSWorkbenchTransport;
  function useRead(load, deps, enabled = true) {
    const read = window.APSResourceSession.useQuery(load, deps, enabled);
    return { ...read, busy: read.loading };
  }
  function useCommands(onReceipt) {
    const [state, set] = React.useState({ key: null, error: null, busy: false, note: '' }), running = React.useRef(false);
    const live = React.useRef(true), callback = React.useRef(onReceipt); callback.current = onReceipt;
    const patch = data => { if (live.current) set(s => ({ ...s, ...data })); };
    // The server outcome is final; only the local key may remain. TrialAPI.settled holds that key until a later clear succeeds.
    // 本机 key 的转换都在跨页互斥里执行，调用方负责持锁。
    function release(key, done, note) {
      try {
        A.clear(key, note);
        patch({ key: null, ...done });
      } catch (error) {
        if (error.conflict === true) {
          if (live.current && (!A.settled || A.settled.key === key)) set(s => s.key && s.key !== key ? s : { ...s, key: null, error, note: '' });
          return false;
        }
        patch({ key, error, note });
      }
      return true;
    }
    // Ignore write contexts embedded in old immutable receipts; the parent reads the object afresh.
    // A failed local clear keeps the key and its error, but never withholds the confirmed receipt.
    function confirmed(receipt, key) {
      if (release(key, { error: null, note: '' }, '') && live.current) callback.current(receipt);
    }
    // Restore and lookup share this: a settled key retries its local cleanup instead of asking the server again.
    async function retry(key) {
      if (!A.settled || A.settled.key !== key) return false;
      await T.exclusive(A.PENDING_KEY, { wait: true }, () => { if (A.settled && A.settled.key === key) release(key, { error: null, note: '' }, A.settled.note); });
      return true;
    }
    async function restore() {
      try {
        const key = A.pending();
        if (!await retry(key)) patch({ key, error: null, note: '' });
      } catch (error) {
        if (A.settled) patch({ key: A.settled.key, error, note: A.settled.note });
        else patch({ error });
      }
    }
    function clearError() { if (live.current && !running.current) set(s => s.busy || s.key ? s : { ...s, error: null, note: '' }); }
    React.useEffect(() => {
      live.current = true; restore();
      const listener = e => { if (e.key === A.PENDING_KEY || e.key === null) restore(); };
      window.addEventListener('storage', listener);
      return () => { live.current = false; window.removeEventListener('storage', listener); };
    }, []);
    async function execute(intent, token) {
      if (running.current) return false;
      running.current = true; patch({ busy: true, error: null, note: '' });
      try {
        // 预留 key、提交和本机清理在跨页互斥里串行，持锁跨过提交命令。
        const { acquired, value } = await T.exclusive(A.PENDING_KEY, {}, async () => {
          let key;
          try {
            key = A.reserve(); patch({ key });
            confirmed(await A.command(intent, token, key), key); return true;
          } catch (error) {
            if (key && T.rejected(error))
              release(key, { error, note: '这次没有写入。填写内容已保留，请点「刷新」后重新确认。' }, '这次没有写入，但本机操作记录还没清掉。请点「查询结果」重试清理。');
            else if (!A.settled || !key || A.settled.key === key)
              patch({ error, ...(key ? { key, note: window.WorkbenchTerms.outcomes.pending('提交') } : {}) });
            return false;
          }
        });
        if (!acquired) patch({ error: new Error('另一个页面正在提交试调，请稍后重试。') });
        return acquired && value;
      } catch (error) { patch({ error }); return false; }
      finally { running.current = false; patch({ busy: false }); }
    }
    async function lookup() {
      if (running.current) return;
      running.current = true; patch({ busy: true, error: null });
      try {
        // 已结算的 key 直接进锁重试清理；先读本机记录只会报它还没清掉。
        const key = A.settled ? A.settled.key : A.pending(); if (await retry(key)) return;
        if (!key) { patch({ key: null, note: '' }); return; }
        const result = await A.lookup(key);
        if (result.state === 'committed') await T.exclusive(A.PENDING_KEY, { wait: true }, () => confirmed(result.receipt, key));
        else patch({ key, note: window.WorkbenchTerms.outcomes.pending('提交') });
      } catch (error) {
        if (A.settled) patch({ key: A.settled.key, error, note: A.settled.note });
        else patch({ error });
      }
      finally { running.current = false; patch({ busy: false }); }
    }
    return { ...state, execute, lookup, restore, clearError, blocked: state.busy || !!state.key || !!state.error };
  }
  window.TrialSession = { useRead, useCommands };
})();
