(function () {
  'use strict';
  const A = window.RunJobAPI, U = window.RunJobControls;
  function RunJobPanel({ preflight, onNavigate, adapter }) {
    const api = React.useMemo(() => adapter || A.create(), [adapter]);
    const [initial] = React.useState(() => { try { return { intent: A.pending().read(), error: '' }; } catch (e) { return { intent: null, error: e.message }; } });
    const [intent, setIntent] = React.useState(initial.intent), [storageError, setStorageError] = React.useState(initial.error);
    const [run, setRun] = React.useState(null), [preview, setPreview] = React.useState(null), [confirming, setConfirming] = React.useState(false);
    const [error, setError] = React.useState(''), [errorDetails, setErrorDetails] = React.useState(null), [notice, setNotice] = React.useState(''), [busy, setBusy] = React.useState(false);
    // 错误正文只说人话；版本号之类的技术细节走 A.details 进折叠编号区。
    const fail = (e, text) => { setError(text || A.message(e)); setErrorDetails(A.details(e)); };
    const clearError = () => { setError(''); setErrorDetails(null); };
    const [unavailable, setUnavailable] = React.useState('');
    const [verified, setVerified] = React.useState(false);
    const [checking, setChecking] = React.useState(false), [paused, setPaused] = React.useState(document.hidden), [revision, refresh] = React.useReducer(v => v + 1, 0);
    const alive = React.useRef(false), locked = React.useRef(false), previewRequest = React.useRef(null), activeInput = React.useRef(null), activeIntent = React.useRef(intent);
    const inputRef = preflight && A.token(preflight.input_ref) ? preflight.input_ref : null;
    activeInput.current = inputRef; activeIntent.current = intent;
    React.useEffect(() => { alive.current = true; return () => { alive.current = false; if (previewRequest.current) previewRequest.current.abort(); }; }, []);
    React.useEffect(() => {
      setPreview(null); setConfirming(false); setUnavailable('');
      if (previewRequest.current) previewRequest.current.abort();
    }, [inputRef, api]);
    React.useEffect(() => {
      function changed(event) {
        if (event.key !== A.PENDING_KEY && event.key !== null) return;
        try { const saved = A.pending().read(); setIntent(saved); setRun(null); setVerified(false); setPreview(null); setConfirming(false); setStorageError(''); refresh(); }
        catch (e) { setStorageError(e.message); }
      }
      window.addEventListener('storage', changed); return () => window.removeEventListener('storage', changed);
    }, []);
    React.useEffect(() => {
      if (!intent || storageError) return undefined;
      setVerified(false);
      let disposed = false, timer, controller, attempt = 0, querying = false, boundRef = null, done = false;
      const current = () => !disposed && alive.current && activeIntent.current && activeIntent.current.request_key === intent.request_key;
      function schedule() { if (current() && !done && !document.hidden) timer = setTimeout(query, A.pollDelay(attempt++)); }
      async function query() {
        if (!current() || querying || document.hidden || done) return;
        querying = true; controller = new AbortController(); setChecking(true);
        try {
          let result;
          if (!boundRef) {
            const found = A.lookup(await api.lookup(intent.request_key, controller.signal), intent.run_ref);
            if (!current() || controller.signal.aborted) return;
            if (!found.found) { setVerified(false); setNotice(window.WorkbenchTerms.outcomes.pending('排产')); clearError(); return; }
            result = found.run; boundRef = result.run_ref;
          } else result = A.run(A.envelope(await api.get(boundRef, controller.signal)), boundRef);
          if (!current() || controller.signal.aborted) return;
          if (!intent.run_ref) {
            try { const saved = A.pending().attach(intent, result.run_ref); activeIntent.current = saved; setIntent(saved); }
            catch (e) { setStorageError(e.message); return; }
          }
          setRun(result); setVerified(true); clearError(); setNotice(''); done = A.terminal(result);
        } catch (e) { if (current() && !controller.signal.aborted) { setVerified(false); fail(e); } }
        finally {
          querying = false;
          if (current()) { setChecking(false); schedule(); }
        }
      }
      function visibility() {
        setPaused(document.hidden); clearTimeout(timer);
        if (document.hidden) { if (controller) controller.abort(); }
        else { attempt = 0; if (!querying) query(); }
      }
      document.addEventListener('visibilitychange', visibility); visibility();
      return () => { disposed = true; clearTimeout(timer); if (controller) controller.abort(); document.removeEventListener('visibilitychange', visibility); };
    }, [api, intent, revision, storageError]);
    async function inspect() {
      if (locked.current || storageError || !inputRef || intent && (!A.terminal(run) || !verified)) return;
      locked.current = true; setBusy(true); clearError(); setNotice(''); setPreview(null); setUnavailable('');
      const original = inputRef, controller = new AbortController(); previewRequest.current = controller;
      try {
        const value = A.preview(await api.preview(original, controller.signal), original);
        if (!alive.current || controller.signal.aborted || activeInput.current !== original) return;
        setPreview(value); setConfirming(value.write_context.capabilities['scheduling.run']);
        if (!value.write_context.capabilities['scheduling.run']) setUnavailable(A.message(value.write_context.blocked_reasons[0]));
      } catch (e) {
        if (alive.current && !controller.signal.aborted) {
          fail(e);
          if (['run_schema_unavailable', 'run_worker_not_connected'].includes(e.code)) setUnavailable(A.message(e));
        }
      }
      finally { locked.current = false; if (alive.current) setBusy(false); }
    }
    async function submit() {
      if (locked.current || !preview || preview.input_ref !== activeInput.current || preview.write_context.capabilities['scheduling.run'] !== true || storageError) return;
      locked.current = true; setBusy(true); clearError();
      let original;
      try {
        // Keep admission and the durable identity claim serialized across browser tabs.
        if (!navigator.locks || typeof navigator.locks.request !== 'function') throw new Error('当前浏览器不支持，请用 Chrome 打开。');
        await navigator.locks.request(A.PENDING_KEY, { ifAvailable: true }, async lock => {
          if (!lock) throw new Error('另一个页面正在提交排产，请稍后点「查询结果」。');
          if (!alive.current || preview.input_ref !== activeInput.current) return;
          const previous = activeIntent.current;
          if (previous && (!A.terminal(run) || !verified)) throw new Error('上次排产还没确认结果，不能开始下一次排产。');
          original = A.pending().begin(preview.input_ref, previous);
          activeIntent.current = original; setIntent(original); setRun(null); setVerified(false); setConfirming(false);
          try {
            const receipt = A.accepted(await api.accept(original, preview.write_context.write_token));
            const saved = A.pending().attach(original, receipt.run_ref);
            if (alive.current && activeIntent.current && activeIntent.current.request_key === original.request_key) {
              activeIntent.current = saved; setIntent(saved); setRun(receipt.data); setVerified(true);
              setNotice(receipt.dispatch_pending ? '排产已接收，交给计算程序时没有确认。正在查询结果，没有重新提交。' : '');
            }
          } catch (e) {
            if (A.isRejected(e)) {
              A.pending().reject(original);
              if (alive.current) { activeIntent.current = null; setIntent(null); setRun(null); fail(e); }
            } else if (alive.current) fail(null, window.WorkbenchTerms.outcomes.pending('排产'));
          }
        });
      } catch (e) { if (alive.current) setStorageError(e.message); }
      finally { locked.current = false; if (alive.current) { setBusy(false); setPreview(null); setConfirming(false); refresh(); } }
    }
    function rereadStorage() {
      try { setIntent(A.pending().read()); setStorageError(''); setVerified(false); setRun(null); refresh(); }
      catch (e) { setStorageError(e.message); }
    }
    const reason = storageError || (!inputRef ? '请先完成排产检查，再确认本次计算。' : intent && (!A.terminal(run) || !verified) ? '上次排产还没结束或结果未知，请先点「查询结果」。' : unavailable);
    const selected = preflight && preflight.normalized_input && preflight.normalized_input.batch_refs;
    return <section className="plana run-job-panel" data-run-job-panel="true" aria-label="候选排产"><U.Styles />
      <div className="rj-heading"><h2>候选排产</h2><div className="rj-tools">
        <U.Button icon="play" className={inputRef && selected && selected.length ? 'btn primary' : 'btn'} reason={reason} reasonDisplay="inline" busy={busy} onClick={inspect}>核对并开始排产</U.Button>
        {unavailable && <U.Button icon="refresh-cw" aria-label="重新核对排产条件" busy={busy} onClick={inspect} />}
        {intent && <U.Button icon="refresh-cw" aria-label={window.WorkbenchTerms.actions.query_result} busy={checking || busy} onClick={() => { setNotice(''); refresh(); }} />}
        {typeof onNavigate === 'function' && <U.Button icon="arrow-left" onClick={() => onNavigate('run')}>返回排产检查</U.Button>}
      </div></div>
      {storageError && <div className="rj-notice" role="alert">{storageError}<div className="rj-tools"><U.Button icon="refresh-cw" disabled={busy} onClick={rereadStorage}>刷新上次操作记录</U.Button></div></div>}
      {error && <div className="rj-notice" role="alert">{error}{errorDetails && <window.WorkbenchReference entries={errorDetails} />}</div>}{notice && <div className="rj-notice" role="status">{notice}</div>}
      {preview && !confirming && <><U.Scope preview={preview} /><U.Reasons rows={preview.write_context.blocked_reasons} /></>}
      {intent && <U.Record run={run} intent={intent} paused={paused} checking={checking} verified={verified} api={api} />}
      {confirming && preview && <U.Confirmation preview={preview} busy={busy} onConfirm={submit} onClose={() => { if (!locked.current) { setConfirming(false); setPreview(null); } }} />}
    </section>;
  }
  window.RunJobPanel = RunJobPanel;
})();
