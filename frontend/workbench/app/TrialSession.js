(function () {
  'use strict';
  const A = window.TrialAPI;
  function useRead(load, deps, enabled = true) {
    const identity = React.useMemo(() => ({}), deps), [state, set] = React.useState({});
    React.useEffect(() => {
      let active = true; const controller = new AbortController();
      set({ identity, busy: enabled });
      if (enabled) Promise.resolve().then(() => load(controller.signal)).then(result => { if (active) set({ identity, result }); })
        .catch(error => { if (active) set({ identity, error }); });
      return () => { active = false; controller.abort(); };
    }, [identity, enabled]);
    return state.identity === identity ? state : { busy: enabled };
  }
  function useCommands(onReceipt) {
    const [state, set] = React.useState({ key: null, error: null, busy: false }), running = React.useRef(false);
    const live = React.useRef(true), callback = React.useRef(onReceipt); callback.current = onReceipt;
    const patch = data => { if (live.current) set(s => ({ ...s, ...data })); };
    function restore() { try { patch({ key: A.pending(), error: null }); } catch (error) { patch({ error }); } }
    React.useEffect(() => {
      live.current = true; restore();
      const listener = e => { if (e.key === A.PENDING_KEY || e.key === null) restore(); };
      window.addEventListener('storage', listener);
      return () => { live.current = false; window.removeEventListener('storage', listener); };
    }, []);
    async function confirmed(receipt, key) {
      if (!live.current) return;
      // Ignore write contexts embedded in old immutable receipts; the parent reads the object afresh.
      A.clear(key); patch({ key: null, receipt, error: null, note: '' });
      if (live.current) callback.current(receipt);
    }
    async function execute(intent, token) {
      if (running.current) return false;
      let key; running.current = true; patch({ busy: true, error: null, receipt: null, note: '' });
      try {
        key = A.reserve(); patch({ key });
        const result = await A.command(intent, token, key); await confirmed(result, key); return true;
      } catch (error) {
        if (key && error.rejected) {
          try { A.clear(key); patch({ key: null, error, note: '这次没有写入。填写内容已保留，请点「刷新」后重新确认。' }); }
          catch (storageError) { patch({ key, error: storageError }); }
        } else patch({ error, ...(key ? { key, note: window.WorkbenchTerms.outcomes.pending('提交') } : {}) });
        return false;
      } finally { running.current = false; patch({ busy: false }); }
    }
    async function lookup() {
      if (running.current) return;
      running.current = true; patch({ busy: true, error: null });
      try {
        const key = A.pending(); if (!key) { patch({ key: null }); return; }
        const result = await A.lookup(key);
        if (result.state === 'committed') await confirmed(result.receipt, key);
        else patch({ key, note: window.WorkbenchTerms.outcomes.pending('提交') });
      } catch (error) { patch({ error }); }
      finally { running.current = false; patch({ busy: false }); }
    }
    return { ...state, execute, lookup, restore, blocked: state.busy || !!state.key || !!state.error };
  }
  window.TrialSession = { useRead, useCommands };
})();
