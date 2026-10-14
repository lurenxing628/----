(function () {
  'use strict';
  const A = window.RunJobAPI, U = window.RunJobControls;
  function useRunAdapter(onNavigate) {
    const navigate = React.useRef(onNavigate); navigate.current = onNavigate;
    return React.useMemo(() => ({ ...A.create(), openCandidate: value => navigate.current('analysis', value) }), []);
  }
  function runHistoryDestination(context = {}) {
    const origin = context.return_decision_context || context;
    const saved = context.return_history_context || origin.return_history_context || context.history_query || origin.history_query || {};
    const returnPlan = context.return_plan_context || origin.return_plan_context || saved.return_plan_context;
    const restored = window.RunHistoryAPI.context({ ...saved, ...(returnPlan ? { return_plan_context: returnPlan } : {}) });
    return { view: 'analysis', context: { source: 'run_history', history_topic: 'run_catalog',
      history_query: window.RunHistoryAPI.returnContext(restored.query, restored.returnPlan) } };
  }
  function trialAction(onNavigate, { planRef, candidateRef, scope, query, disabled, taskOrigin, historyOrigin, label = '试调' }) {
    const display = { query };
    if (scope.range_start && scope.range_end) { display.range_start = scope.range_start; display.range_end = scope.range_end; }
    if (scope.batch_ref) display.batch_refs = [scope.batch_ref];
    return <U.Button icon="square-pen" disabled={disabled} onClick={() => onNavigate('trial', {
      base: candidateRef ? { candidate_ref: candidateRef } : { plan_ref: planRef }, scope: display,
      ...(taskOrigin ? { task_origin: taskOrigin } : {}),
      ...(historyOrigin ? { return_decision_history_context: historyOrigin } : {}),
    })}>{label}</U.Button>;
  }
  function ReadRun({ runRef, api, onNavigate, initialContext, runHistoryReturn }) {
    const [record, setRecord] = React.useState(null), [error, setError] = React.useState('');
    const [checking, setChecking] = React.useState(false), [verified, setVerified] = React.useState(false), [retryPaused, setRetryPaused] = React.useState(false);
    const [paused, setPaused] = React.useState(document.hidden), [revision, refresh] = React.useReducer(v => v + 1, 0);
    React.useEffect(() => {
      if (!A.ref(runRef)) return undefined;
      setRetryPaused(false);
      let disposed = false, timer, controller, querying = false, done = false, attempt = 0, unsettledSince = null;
      function schedule() { if (!disposed && !done && !document.hidden) timer = setTimeout(read, A.pollDelay(attempt++)); }
      // Same rule as the candidate panel: 60 seconds of failed reads stop the automatic query; the refresh button restarts it.
      function unresolved(started) {
        if (unsettledSince === null) unsettledSince = started;
        if (Date.now() - unsettledSince >= 60000) { done = true; setRetryPaused(true); }
      }
      async function read() {
        if (disposed || querying || document.hidden || done) return;
        querying = true; controller = new AbortController(); setChecking(true); setVerified(false); const started = Date.now();
        try {
          const value = A.run(A.envelope(await api.get(runRef, controller.signal)), runRef);
          if (disposed || controller.signal.aborted) return;
          setRecord(value); setVerified(true); setError(''); unsettledSince = null; done = A.terminal(value);
        } catch (problem) {
          if (!disposed && !controller.signal.aborted) { setError(A.message(problem)); setVerified(false); unresolved(started); }
        } finally { querying = false; if (!disposed) { setChecking(false); schedule(); } }
      }
      function visibility() {
        setPaused(document.hidden); clearTimeout(timer);
        if (document.hidden) { if (controller) controller.abort(); }
        else { attempt = 0; read(); }
      }
      document.addEventListener('visibilitychange', visibility); visibility();
      return () => { disposed = true; clearTimeout(timer); if (controller) controller.abort(); document.removeEventListener('visibilitychange', visibility); };
    }, [runRef, api, revision]);
    const historyReturn = <HistoryReturn context={initialContext || {}} onNavigate={onNavigate} />;
    const newRun = <U.Button icon="plus" onClick={() => onNavigate('run', {})}>新排产</U.Button>;
    const navigation = <Navigation>{historyReturn}<U.Button icon="history" onClick={() => onNavigate(runHistoryReturn.view, runHistoryReturn.context)}>排产记录</U.Button>{newRun}</Navigation>;
    if (record && verified && record.result_persisted && record.candidates.some(row => row.status === 'completed')) return <window.RunCandidateWorkspace view="analysis"
      initialContext={{ ...initialContext, run_ref: runRef }} onNavigate={onNavigate} runHistoryReturn={runHistoryReturn} navigation={<Navigation>{historyReturn}{newRun}</Navigation>} headerTitle="本次排产结果" runStatus={record.state} runTiming={record}
      renderAdoption={(candidateRef, metadata = {}) => <window.RunAdoptionAction candidateRef={candidateRef} {...metadata} onNavigate={onNavigate} />}
      renderTrial={value => trialAction(onNavigate, value)} />;
    return <section className="plana run-job-panel rj-status-workspace" aria-label="本次排产">
      {!A.ref(runRef) ? <><div className="rj-heading rj-business-heading"><h2>本次排产</h2>{navigation}</div><p role="alert">这条排产记录已失效，请点「排产记录」重新选择。</p></> : <>
        <U.Record run={record} paused={paused} checking={checking} verified={verified} retryPaused={retryPaused} retryHint="请点「刷新本次排产」再次核对。" api={api} onNavigate={onNavigate} navigation={navigation}
          actions={<U.Button icon="refresh-cw" aria-label="刷新本次排产" busy={checking} onClick={refresh} />} />
        {error && <div className="rj-notice" role="alert">{error}</div>}
      </>}
    </section>;
  }
  function Navigation({ children }) {
    return <div className="scheduling-navigation">{children}</div>;
  }
  function HistoryReturn({ context, onNavigate }) {
    if (!context.return_decision_history_context && !(context.return_decision_context && context.return_decision_context.return_decision_history_context)) return null;
    return window.DecisionHistoryAPI.returnState(context) ? <U.Button icon="chevron-left" onClick={() => onNavigate('analysis', window.DecisionHistoryAPI.historyContext(context))}>返回历史走势</U.Button> : null;
  }
  function RunWorkspace({ onNavigate, initialContext }) {
    const api = useRunAdapter(onNavigate), specified = initialContext && Object.prototype.hasOwnProperty.call(initialContext, 'run_ref');
    const runHistoryReturn = runHistoryDestination(initialContext);
    const history = <><HistoryReturn context={initialContext || {}} onNavigate={onNavigate} /><U.Button icon="history" onClick={() => onNavigate(runHistoryReturn.view, runHistoryReturn.context)}>排产记录</U.Button></>;
    return specified ? <ReadRun key={initialContext.run_ref} runRef={initialContext.run_ref} api={api} initialContext={initialContext} onNavigate={onNavigate} runHistoryReturn={runHistoryReturn} /> :
      <window.PreflightWorkspace initialContext={initialContext} onNavigate={onNavigate} actions={history}
        renderRunPanel={data => <window.RunJobPanel preflight={data} adapter={api} onNavigate={onNavigate} />} />;
  }
  function PlanCenterWorkspace({ view, onNavigate, initialContext }) {
    const context = initialContext || {}, candidate = Object.prototype.hasOwnProperty.call(context, 'run_ref') || Object.prototype.hasOwnProperty.call(context, 'candidate_ref');
    const history = !candidate && context.source === 'run_history';
    const runHistoryReturn = runHistoryDestination(context);
    function renderTrial(value) { return trialAction(onNavigate, { ...value, historyOrigin: window.DecisionHistoryAPI.returnState(context) }); }
    const navigation = <Navigation>
      {!history && <HistoryReturn context={context} onNavigate={onNavigate} />}
      <U.Button icon="files" aria-pressed={!candidate && !history} onClick={() => onNavigate(view, {})}>计划版本</U.Button>
      {!candidate && <U.Button icon="history" aria-pressed={history} onClick={() => onNavigate(runHistoryReturn.view, runHistoryReturn.context)}>排产记录</U.Button>}
    </Navigation>;
    return <>{candidate ? <window.RunCandidateWorkspace view={view} initialContext={initialContext} onNavigate={onNavigate} runHistoryReturn={runHistoryReturn} navigation={navigation}
      renderAdoption={(candidateRef, metadata = {}) => <window.RunAdoptionAction candidateRef={candidateRef} {...metadata} onNavigate={onNavigate} />} renderTrial={renderTrial} /> : history ?
      <window.RunHistoryWorkspace initialContext={context.history_query} pageContext={context} onNavigate={onNavigate} navigation={navigation} /> :
      <window.PlanWorkspace view={view} initialContext={initialContext} onNavigate={onNavigate} renderTrial={renderTrial} navigation={navigation} />}</>;
  }
  window.RunWorkspace = RunWorkspace;
  window.PlanCenterWorkspace = PlanCenterWorkspace;
})();
