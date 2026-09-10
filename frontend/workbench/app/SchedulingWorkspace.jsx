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
    return <section className="plana run-job-panel" aria-label="指定运行"><U.Styles />
      <div className="rj-heading"><h2>排产运行</h2><U.Button icon="refresh-cw" aria-label="刷新指定运行" busy={checking} disabled={!A.ref(runRef)} onClick={refresh} /></div>
      {!A.ref(runRef) ? <p role="alert">运行来源无效，未切换到其他运行。</p> : <>
        <p className="rj-identity">指定运行：{runRef}</p>{error && <div className="rj-notice" role="alert">{error}</div>}
        {record && <U.Record run={record} intent={null} paused={paused} checking={checking} verified={verified} api={api} />}
        {!record && <p role="status" className="rj-muted">{checking ? '正在读取指定运行。' : paused ? '返回页面后继续读取指定运行。' : '尚未核实指定运行，未显示其他运行结果。'}</p>}
      </>}
    </section>;
  }
  function Navigation({ children }) {
    return <div className="scheduling-navigation">{children}<style>{`
      .scheduling-navigation{display:flex;align-items:center;flex-wrap:wrap;gap:8px;padding:8px 10px;margin-bottom:16px;background:var(--ui-surface-muted);border-bottom:1px solid var(--ui-border);min-width:0;color:var(--ui-text)}
      .scheduling-navigation .btn[aria-pressed="true"]{color:var(--ui-primary-text,var(--ui-text));background:var(--ui-surface-selected,var(--ui-surface));border-color:var(--ui-border-strong,var(--ui-border))}
      .scheduling-navigation .scheduling-source{font-size:12px;color:var(--ui-info-muted);margin-left:auto}
    `}</style></div>;
  }
  function RunWorkspace({ onNavigate, initialContext }) {
    const api = useRunAdapter(onNavigate), specified = initialContext && Object.prototype.hasOwnProperty.call(initialContext, 'run_ref');
    return <><Navigation><U.Button icon="history" onClick={() => onNavigate('analysis', { source: 'run_history' })}>排产记录</U.Button>
      {specified && <U.Button icon="plus" onClick={() => onNavigate('run', {})}>新建排产范围</U.Button>}</Navigation>
      {specified ? <ReadRun key={initialContext.run_ref} runRef={initialContext.run_ref} api={api} /> :
        <window.PreflightWorkspace initialContext={initialContext} onNavigate={onNavigate}
          renderRunPanel={data => <window.RunJobPanel preflight={data} adapter={api} />} />}
    </>;
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
      {candidate && <span className="scheduling-source">候选预览 · 非正式执行安排</span>}
    </Navigation>{candidate ? <window.RunCandidateWorkspace view={view} initialContext={initialContext} onNavigate={onNavigate}
      renderAdoption={candidateRef => <window.RunAdoptionAction candidateRef={candidateRef} onNavigate={onNavigate} />} renderTrial={renderTrial} /> : history ?
      <window.RunHistoryWorkspace initialContext={context.history_query} onNavigate={onNavigate} /> :
      <window.PlanWorkspace view={view} initialContext={initialContext} onNavigate={onNavigate} renderTrial={renderTrial} />}</>;
  }
  window.RunWorkspace = RunWorkspace;
  window.PlanCenterWorkspace = PlanCenterWorkspace;
})();
