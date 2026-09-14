(function () {
  'use strict';
  const A = window.RunJobAPI, U = window.RunJobControls;
  function useRunAdapter(onNavigate) {
    const navigate = React.useRef(onNavigate); navigate.current = onNavigate;
    return React.useMemo(() => ({ ...A.create(), openCandidate: value => navigate.current('analysis', value) }), []);
  }
  function ReadRun({ runRef, api }) {
    const [record, setRecord] = React.useState(null), [error, setError] = React.useState('');
    const [checking, setChecking] = React.useState(false), [verified, setVerified] = React.useState(false);
    const [paused, setPaused] = React.useState(document.hidden), [revision, refresh] = React.useReducer(v => v + 1, 0);
    React.useEffect(() => {
      if (!A.ref(runRef)) return undefined;
      let disposed = false, timer, controller, querying = false, done = false, attempt = 0;
      function schedule() { if (!disposed && !done && !document.hidden) timer = setTimeout(read, A.pollDelay(attempt++)); }
      async function read() {
        if (disposed || querying || document.hidden || done) return;
        querying = true; controller = new AbortController(); setChecking(true); setVerified(false);
        try {
          const value = A.run(A.envelope(await api.get(runRef, controller.signal)), runRef);
          if (disposed || controller.signal.aborted) return;
          setRecord(value); setVerified(true); setError(''); done = A.terminal(value);
        } catch (problem) {
          if (!disposed && !controller.signal.aborted) { setError(A.message(problem)); setVerified(false); }
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
    return <section className="plana run-job-panel" aria-label="这次排产"><U.Styles />
      <div className="rj-heading"><h2>这次排产</h2><U.Button icon="refresh-cw" aria-label="刷新这次排产" busy={checking} disabled={!A.ref(runRef)} onClick={refresh} /></div>
      {!A.ref(runRef) ? <p role="alert">这条排产记录已失效，页面没有切换。请点「排产记录」重新选择。</p> : <>
        <window.WorkbenchReference entries={{ '排产编号': runRef }} />{error && <div className="rj-notice" role="alert">{error}</div>}
        {record && <U.Record run={record} intent={null} paused={paused} checking={checking} verified={verified} api={api} />}
        {!record && <p role="status" className="rj-muted">{checking ? '正在读取这次排产。' : paused ? '返回本页后继续读取这次排产。' : '还没读到这次排产的结果。请点右上角的刷新按钮。'}</p>}
      </>}
    </section>;
  }
  function Navigation({ children }) {
    return <div className="scheduling-navigation">{children}</div>;
  }
  function RunWorkspace({ onNavigate, initialContext }) {
    const api = useRunAdapter(onNavigate), specified = initialContext && Object.prototype.hasOwnProperty.call(initialContext, 'run_ref');
    const history = <U.Button icon="history" onClick={() => onNavigate('analysis', { source: 'run_history' })}>排产记录</U.Button>;
    // The preflight page carries 排产记录 in its own heading; only the specified-run view keeps the navigation strip.
    return specified ? <><Navigation>{history}<U.Button icon="plus" onClick={() => onNavigate('run', {})}>开始新排产</U.Button></Navigation>
      <ReadRun key={initialContext.run_ref} runRef={initialContext.run_ref} api={api} /></> :
      <window.PreflightWorkspace initialContext={initialContext} onNavigate={onNavigate} actions={history}
        renderRunPanel={data => <window.RunJobPanel preflight={data} adapter={api} />} />;
  }
  function PlanCenterWorkspace({ view, onNavigate, initialContext }) {
    const context = initialContext || {}, candidate = Object.prototype.hasOwnProperty.call(context, 'run_ref') || Object.prototype.hasOwnProperty.call(context, 'candidate_ref');
    const history = !candidate && context.source === 'run_history';
    const historyQuery = candidate ? context.return_history_context : history ? context.history_query : undefined;
    function renderTrial({ planRef, candidateRef, scope, query, disabled, taskOrigin, label = '试调' }) {
      const display = { query };
      if (scope.range_start && scope.range_end) { display.range_start = scope.range_start; display.range_end = scope.range_end; }
      if (scope.batch_ref) display.batch_refs = [scope.batch_ref];
      return <U.Button icon="square-pen" disabled={disabled} onClick={() => onNavigate('trial', {
        base: candidateRef ? { candidate_ref: candidateRef } : { plan_ref: planRef }, scope: display,
        ...(taskOrigin ? { task_origin: taskOrigin } : {}),
      })}>{label}</U.Button>;
    }
    return <><Navigation>
      <U.Button icon="files" aria-pressed={!candidate && !history} onClick={() => onNavigate(view, {})}>计划版本</U.Button>
      <U.Button icon="history" aria-pressed={history} onClick={() => onNavigate('analysis', { source: 'run_history', ...(historyQuery ? { history_query: historyQuery } : {}) })}>排产记录</U.Button>
      {candidate && <U.Button icon="chart" aria-pressed={true} aria-current="page">候选方案</U.Button>}
      {candidate && <span className="scheduling-source">不是正式计划</span>}
    </Navigation>{candidate ? <window.RunCandidateWorkspace view={view} initialContext={initialContext} onNavigate={onNavigate}
      renderAdoption={candidateRef => <window.RunAdoptionAction candidateRef={candidateRef} onNavigate={onNavigate} />} renderTrial={renderTrial} /> : history ?
      <window.RunHistoryWorkspace initialContext={context.history_query} onNavigate={onNavigate} /> :
      <window.PlanWorkspace view={view} initialContext={initialContext} onNavigate={onNavigate} renderTrial={renderTrial} />}</>;
  }
  window.RunWorkspace = RunWorkspace;
  window.PlanCenterWorkspace = PlanCenterWorkspace;
})();
