(function () {
  'use strict';
  const A = window.RunJobAPI, U = window.RunJobControls;
  function savedRecord() {
    const store = A.pending(), pending = store.read(), recent = pending ? null : store.recent();
    return { intent: pending || recent && recent.intent, pending: !!pending, resolution: recent && recent.resolution, error: '' };
  }
  function RunJobPanel({ preflight, preflightOwner, onRecheck, onNavigate }) {
    const [initial] = React.useState(() => { try { return savedRecord(); } catch (e) { return { intent: null, pending: false, error: e.message }; } });
    const [intent, setIntent] = React.useState(initial.intent), [storageError, setStorageError] = React.useState(initial.error);
    const [pendingActive, setPendingActive] = React.useState(initial.pending), [resolution, setResolution] = React.useState(initial.resolution || 'unresolved');
    const [retryPaused, setRetryPaused] = React.useState(false), [lastChecked, setLastChecked] = React.useState(null);
    const [run, setRun] = React.useState(null), [preview, setPreview] = React.useState(null), [confirming, setConfirming] = React.useState(false);
    const [confirmationData, setConfirmationData] = React.useState(null), [timeBudget, setTimeBudget] = React.useState(null), [submitting, setSubmitting] = React.useState(false);
    const [error, setError] = React.useState(''), [errorDetails, setErrorDetails] = React.useState(null), [notice, setNotice] = React.useState(''), [busy, setBusy] = React.useState(false);
    // 错误正文只说人话；版本号之类的技术细节走 A.details 进折叠编号区。
    const fail = (e, text) => { setError(text || A.message(e)); setErrorDetails(A.details(e)); };
    const clearError = () => { setError(''); setErrorDetails(null); };
    const [unavailable, setUnavailable] = React.useState('');
    const [verified, setVerified] = React.useState(false);
    const [checking, setChecking] = React.useState(false), [paused, setPaused] = React.useState(document.hidden), [revision, refresh] = React.useReducer(v => v + 1, 0);
    const alive = React.useRef(false), locked = React.useRef(false), previewRequest = React.useRef(null), confirmationSession = React.useRef(null), currentPreview = React.useRef(null), activeInput = React.useRef(null), activeIntent = React.useRef(intent);
    const inputRef = preflight && A.token(preflight.input_ref) ? preflight.input_ref : null;
    activeInput.current = inputRef; activeIntent.current = intent;
    function closeConfirmation() {
      if (locked.current) return;
      confirmationSession.current = null; currentPreview.current = null;
      if (previewRequest.current) previewRequest.current.abort();
      previewRequest.current = null; setPreview(null); setConfirming(false); setConfirmationData(null); setBusy(false);
    }
    React.useEffect(() => { alive.current = true; return () => {
      alive.current = false; confirmationSession.current = null; currentPreview.current = null;
      if (previewRequest.current) previewRequest.current.abort();
    }; }, []);
    React.useEffect(() => {
      // A budget check continues the same confirmation even while the parent clears its old result.
      // Its owner also prevents a closed confirmation from reopening when a check has already finished.
      if (preflightOwner) { if (confirmationSession.current !== preflightOwner) closeConfirmation(); return; }
      if (!inputRef && confirmationSession.current && confirmationSession.current.rechecking) return;
      closeConfirmation(); setUnavailable('');
      if (inputRef && !storageError && !pendingActive) inspect();
    }, [inputRef, preflightOwner]);
    React.useEffect(() => {
      function changed(event) {
        if (![A.PENDING_KEY, A.RECENT_KEY, null].includes(event.key)) return;
        try { const saved = savedRecord(); closeConfirmation(); setIntent(saved.intent); setPendingActive(saved.pending); setResolution(saved.resolution || 'unresolved'); setRun(null); setVerified(false); setStorageError(''); refresh(); }
        catch (e) { setStorageError(e.message); }
      }
      window.addEventListener('storage', changed); return () => window.removeEventListener('storage', changed);
    }, []);
    React.useEffect(() => {
      if (!intent || storageError) return undefined;
      if (!pendingActive && resolution === 'context_replaced') return undefined;
      setVerified(false);
      setRetryPaused(false);
      let disposed = false, timer, controller, attempt = 0, querying = false, done = false, unsettledSince = null;
      const current = () => !disposed && alive.current && activeIntent.current && activeIntent.current.request_key === intent.request_key;
      function schedule() { if (current() && !done && !document.hidden) timer = setTimeout(query, A.pollDelay(attempt++)); }
      function unresolved(started) {
        if (unsettledSince === null) unsettledSince = started;
        if (Date.now() - unsettledSince >= 60000) { done = true; setRetryPaused(true); }
      }
      async function query() {
        if (!current() || querying || document.hidden || done) return;
        querying = true; const localController = new AbortController(); controller = localController; setChecking(true); const started = Date.now();
        try {
          const found = await A.lookup(intent, localController.signal);
          if (!current() || localController.signal.aborted) return;
          setLastChecked(Date.now()); setResolution(found.resolution); clearError(); setNotice('');
          if (!found.found) {
            setVerified(false);
            if (found.resolution === 'context_replaced') {
              setRun(null); done = true;
              try { A.pending().finish(activeIntent.current, 'context_replaced'); setPendingActive(false); }
              catch (e) { setStorageError(e.message); }
            } else if (!pendingActive) {
              setRun(null); done = true;
            } else unresolved(started);
            return;
          }
          const result = found.run;
          // 活跃任务保持正常读取频率；待恢复记录、未决结果和读取失败沿用退避。
          if (!result.recovery_required) attempt = 0;
          setRun(result); setVerified(true); unsettledSince = null; done = A.terminal(result);
          if (pendingActive && !activeIntent.current.run_ref) {
            const attached = { ...activeIntent.current, run_ref: result.run_ref };
            try { A.pending().attach(activeIntent.current, result.run_ref); }
            catch (e) {
              activeIntent.current = attached; setIntent(attached);
              setStorageError(e.message); return;
            }
            activeIntent.current = attached; setIntent(attached);
          }
          if (done && pendingActive) {
            try { A.pending().finish(activeIntent.current, 'found'); }
            catch (e) { setStorageError(e.message); return; }
            setPendingActive(false);
            onNavigate('run', { run_ref: result.run_ref });
          }
        } catch (e) { if (current() && !localController.signal.aborted) { setLastChecked(Date.now()); setResolution('lookup_failed'); setVerified(false); fail(e, e.code === 'run_result_inconsistent' ? A.message(e) : '查询暂未成功，请点「查询结果」重试。'); unresolved(started); } }
        finally {
          if (controller === localController) {
            querying = false;
            if (current()) {
              setChecking(false);
              if (!localController.signal.aborted) schedule();
              else if (!document.hidden && !done) query();
            }
          }
        }
      }
      function visibility() {
        setPaused(document.hidden); clearTimeout(timer);
        if (document.hidden) { if (controller) controller.abort(); }
        else { attempt = 0; if (!querying) query(); }
      }
      document.addEventListener('visibilitychange', visibility); visibility();
      return () => { disposed = true; clearTimeout(timer); if (controller) controller.abort(); document.removeEventListener('visibilitychange', visibility); };
    }, [intent && intent.request_key, revision, storageError]);
    function beginPreviewRequest() {
      if (previewRequest.current) previewRequest.current.abort();
      const controller = new AbortController(); previewRequest.current = controller; currentPreview.current = null;
      setBusy(true); clearError(); setNotice(''); setPreview(null); setUnavailable('');
      return controller;
    }
    function ownsPreview(owner, controller) {
      return alive.current && confirmationSession.current === owner && previewRequest.current === controller && !controller.signal.aborted;
    }
    async function readPreview(checked, owner, controller) {
      const value = await A.preview(checked.input_ref, controller.signal);
      if (!ownsPreview(owner, controller)) return;
      if (JSON.stringify(window.PreflightContract.input(value.normalized_input)) !== JSON.stringify(window.PreflightContract.input(checked.normalized_input))
          || (checked.run_options === null) !== (value.run_options === null)
          || checked.run_options !== null && Object.keys(checked.run_options).some(key => JSON.stringify(checked.run_options[key]) !== JSON.stringify(value.run_options[key])))
        throw window.PreflightContract.fail('核对结果与本次排产检查不一致，请重新检查。');
      currentPreview.current = value; setPreview(value); setConfirming(value.write_context.capabilities['scheduling.run']);
      if (!value.write_context.capabilities['scheduling.run']) setUnavailable(value.write_context.blocked_reasons[0].message || A.message(value.write_context.blocked_reasons[0]));
    }
    function previewFailure(error, owner, controller) {
      if (!ownsPreview(owner, controller)) return;
      fail(error, A.previewMessage(error));
      if (['run_schema_unavailable', 'run_worker_not_connected'].includes(error.code)) setUnavailable(A.message(error));
    }
    function finishPreview(owner, controller) {
      if (previewRequest.current !== controller) return;
      previewRequest.current = null; owner.rechecking = false;
      if (alive.current) setBusy(false);
    }
    async function inspect() {
      if (locked.current || previewRequest.current || storageError || !inputRef || pendingActive) return;
      const owner = { preflight, rechecking: false }; confirmationSession.current = owner;
      setConfirmationData(preflight); setTimeBudget(preflight.run_options === null ? null : preflight.run_options.time_budget_seconds); setConfirming(false);
      const controller = beginPreviewRequest();
      try {
        await readPreview(preflight, owner, controller);
      } catch (e) { previewFailure(e, owner, controller); }
      finally { finishPreview(owner, controller); }
    }
    async function recheckBudget(seconds) {
      const owner = confirmationSession.current;
      if (locked.current || !owner || !window.RunGenerationContract.budget(seconds) || pendingActive || storageError) return;
      owner.rechecking = true; setTimeBudget(seconds);
      const controller = beginPreviewRequest();
      try {
        const checked = await onRecheck({ ...owner.preflight.normalized_input, time_budget_seconds: seconds }, controller.signal, owner);
        if (!checked || !ownsPreview(owner, controller)) return;
        owner.preflight = checked; setConfirmationData(checked);
        await readPreview(checked, owner, controller);
      } catch (e) { previewFailure(e, owner, controller); }
      finally { finishPreview(owner, controller); }
    }
    async function submit() {
      if (locked.current || !confirmationSession.current || confirmationSession.current.rechecking || !preview || currentPreview.current !== preview
          || preview.input_ref !== activeInput.current || preview.write_context.capabilities['scheduling.run'] !== true || storageError) return;
      locked.current = true; setSubmitting(true); setBusy(true); clearError();
      let original, storageFailed = false;
      try {
        // Keep admission and the durable identity claim serialized across browser tabs.
        if (!navigator.locks || typeof navigator.locks.request !== 'function') { if (alive.current) fail(null, '当前浏览器不支持，请用 Chrome 打开。'); return; }
        await navigator.locks.request(A.PENDING_KEY, { ifAvailable: true }, async lock => {
          if (!lock) { if (alive.current) fail(null, '另一个页面正在提交排产，请稍后点「查询结果」。'); return; }
          if (!alive.current || currentPreview.current !== preview || preview.input_ref !== activeInput.current) return;
          if (pendingActive) { fail(null, '上次排产还没确认结果，不能开始下一次排产。'); return; }
          original = A.pending().begin(preview.input_ref, null, preview.data_context_ref);
          confirmationSession.current = null; currentPreview.current = null;
          activeIntent.current = original; setIntent(original); setPendingActive(true); setResolution('unresolved'); setRun(null); setVerified(false); setConfirming(false);
          try {
            const receipt = await A.accept(original, preview.write_context.write_token);
            const owned = alive.current && activeIntent.current && activeIntent.current.request_key === original.request_key;
            // 服务端已受理：先发布这次排产，本机记录写入失败只报存储问题，不当成结果没查到。
            if (owned) {
              setRun(receipt.data); setVerified(true);
              setNotice(receipt.dispatch_pending ? '排产已接收，交给计算程序时没有确认。正在查询结果，没有重新提交。' : '');
            }
            try { const saved = A.pending().attach(original, receipt.run_ref); if (owned) { activeIntent.current = saved; setIntent(saved); } }
            catch (_) { if (alive.current) setStorageError('排产已接收，但本机没能保存这次排产的编号。请不要重新提交，到排产记录页查看结果。'); }
          } catch (e) {
            if (window.APSWorkbenchTransport.rejected(e)) {
              if (alive.current) { activeIntent.current = null; setIntent(null); setPendingActive(false); setRun(null); fail(e); }
              try { A.pending().reject(original); }
              catch (storageErr) { if (alive.current) setStorageError(storageErr.message); }
            } else if (alive.current) fail(null, window.WorkbenchTerms.outcomes.pending('排产'));
          }
        });
      } catch (e) { storageFailed = true; if (alive.current) setStorageError(e.message); }
      finally {
        locked.current = false;
        if (alive.current) {
          setSubmitting(false); setBusy(false);
          // 锁被占用或前置检查拦下时保留这次确认，锁释放后可在同一弹窗里重试。
          if (original || storageFailed) { setPreview(null); setConfirming(false); refresh(); }
        }
      }
    }
    function rereadStorage() {
      try { const saved = savedRecord(); setIntent(saved.intent); setPendingActive(saved.pending); setResolution(saved.resolution || 'unresolved'); setStorageError(''); setVerified(false); setRun(null); refresh(); }
      catch (e) { setStorageError(e.message); }
    }
    const selected = preflight && preflight.normalized_input && preflight.normalized_input.batch_refs;
    const effective = preflight && preview && preflight.input_ref === preview.input_ref ? preflight.effective_config : null;
    const reason = storageError || (!inputRef ? '请先完成排产检查。' : selected && !selected.length ? '请先选择要排产的批次。' : pendingActive ? '上次排产尚未确认结果，请先查询。' : unavailable);
    return <section className="plana run-job-panel" data-run-job-panel="true" aria-label="候选排产">
      <div className="rj-heading"><div><h3>候选排产</h3><p className="rj-muted">选择范围并完成检查后，计算本次候选方案。</p></div></div>
      <div className="rj-actions"><div className="rj-tools">
        <U.Button icon="play" className={inputRef && selected && selected.length ? 'btn primary' : 'btn'} reason={reason} reasonDisplay="tooltip" busy={busy} onClick={inspect}>核对并开始排产</U.Button>
        {unavailable && <U.Button icon="refresh-cw" busy={busy} onClick={inspect}>重新核对排产条件</U.Button>}
        {intent && resolution !== 'context_replaced' && <U.Button icon="refresh-cw" busy={checking || busy} onClick={() => { setNotice(''); refresh(); }}>查询结果</U.Button>}
      </div>{reason && <p className="rj-muted rj-action-reason">{reason}</p>}</div>
      {storageError && <div className="rj-notice" role="alert">{storageError}<div className="rj-tools"><U.Button icon="refresh-cw" disabled={busy} onClick={rereadStorage}>刷新上次操作记录</U.Button></div></div>}
      {error && <div className="rj-notice" role="alert">{error}{errorDetails && <window.WorkbenchReference entries={errorDetails} />}</div>}{notice && <div className="rj-notice" role="status">{notice}</div>}
      {preview && !confirming && <><U.Scope preview={preview} effective={effective} /><U.Reasons rows={preview.write_context.blocked_reasons} /></>}
      {intent && <U.Record run={run} intent={intent} title={pendingActive ? '本次排产' : '上次排产'} paused={paused} retryPaused={retryPaused} lastChecked={lastChecked} resolution={resolution} checking={checking} verified={verified} onNavigate={onNavigate} />}
      {confirming && confirmationData && <U.Confirmation preview={preview} preflight={confirmationData} effective={confirmationData.effective_config}
        batches={confirmationData.included_batches.concat(confirmationData.excluded_batches)} operationCount={confirmationData.counts.selected_tasks}
        timeBudget={timeBudget} onBudgetChange={recheckBudget} busy={busy} submitting={submitting} error={error}
        onConfirm={submit} onClose={closeConfirmation} onRetry={() => recheckBudget(timeBudget)} />}
    </section>;
  }
  window.RunJobPanel = RunJobPanel;
})();
