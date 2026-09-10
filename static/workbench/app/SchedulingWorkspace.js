(function () {
  'use strict';

  const A = window.RunJobAPI,
    U = window.RunJobControls;
  function useRunAdapter(onNavigate) {
    const navigate = React.useRef(onNavigate);
    navigate.current = onNavigate;
    return React.useMemo(() => ({
      ...A.create(),
      openCandidate: value => navigate.current('analysis', value)
    }), []);
  }
  function ReadRun({
    runRef,
    api
  }) {
    const [record, setRecord] = React.useState(null),
      [error, setError] = React.useState('');
    const [checking, setChecking] = React.useState(false),
      [verified, setVerified] = React.useState(false);
    const [paused, setPaused] = React.useState(document.hidden),
      [revision, refresh] = React.useReducer(v => v + 1, 0);
    React.useEffect(() => {
      if (!A.ref(runRef)) return undefined;
      let disposed = false,
        timer,
        controller,
        querying = false,
        done = false,
        attempt = 0;
      function schedule() {
        if (!disposed && !done && !document.hidden) timer = setTimeout(read, A.pollDelay(attempt++));
      }
      async function read() {
        if (disposed || querying || document.hidden || done) return;
        querying = true;
        controller = new AbortController();
        setChecking(true);
        setVerified(false);
        try {
          const value = A.run(A.envelope(await api.get(runRef, controller.signal)), runRef);
          if (disposed || controller.signal.aborted) return;
          setRecord(value);
          setVerified(true);
          setError('');
          done = A.terminal(value);
        } catch (problem) {
          if (!disposed && !controller.signal.aborted) {
            setError(A.message(problem));
            setVerified(false);
          }
        } finally {
          querying = false;
          if (!disposed) {
            setChecking(false);
            schedule();
          }
        }
      }
      function visibility() {
        setPaused(document.hidden);
        clearTimeout(timer);
        if (document.hidden) {
          if (controller) controller.abort();
        } else {
          attempt = 0;
          read();
        }
      }
      document.addEventListener('visibilitychange', visibility);
      visibility();
      return () => {
        disposed = true;
        clearTimeout(timer);
        if (controller) controller.abort();
        document.removeEventListener('visibilitychange', visibility);
      };
    }, [runRef, api, revision]);
    return /*#__PURE__*/React.createElement("section", {
      className: "plana run-job-panel",
      "aria-label": "\u6307\u5B9A\u8FD0\u884C"
    }, /*#__PURE__*/React.createElement(U.Styles, null), /*#__PURE__*/React.createElement("div", {
      className: "rj-heading"
    }, /*#__PURE__*/React.createElement("h2", null, "\u6392\u4EA7\u8FD0\u884C"), /*#__PURE__*/React.createElement(U.Button, {
      icon: "refresh-cw",
      "aria-label": "\u5237\u65B0\u6307\u5B9A\u8FD0\u884C",
      busy: checking,
      disabled: !A.ref(runRef),
      onClick: refresh
    })), !A.ref(runRef) ? /*#__PURE__*/React.createElement("p", {
      role: "alert"
    }, "\u8FD0\u884C\u6765\u6E90\u65E0\u6548\uFF0C\u672A\u5207\u6362\u5230\u5176\u4ED6\u8FD0\u884C\u3002") : /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("p", {
      className: "rj-identity"
    }, "\u6307\u5B9A\u8FD0\u884C\uFF1A", runRef), error && /*#__PURE__*/React.createElement("div", {
      className: "rj-notice",
      role: "alert"
    }, error), record && /*#__PURE__*/React.createElement(U.Record, {
      run: record,
      intent: null,
      paused: paused,
      checking: checking,
      verified: verified,
      api: api
    }), !record && /*#__PURE__*/React.createElement("p", {
      role: "status",
      className: "rj-muted"
    }, checking ? '正在读取指定运行。' : paused ? '返回页面后继续读取指定运行。' : '尚未核实指定运行，未显示其他运行结果。')));
  }
  function Navigation({
    children
  }) {
    return /*#__PURE__*/React.createElement("div", {
      className: "scheduling-navigation"
    }, children, /*#__PURE__*/React.createElement("style", null, `
      .scheduling-navigation{display:flex;align-items:center;flex-wrap:wrap;gap:8px;padding:8px 10px;margin-bottom:16px;background:var(--ui-surface-muted);border-bottom:1px solid var(--ui-border);min-width:0;color:var(--ui-text)}
      .scheduling-navigation .btn[aria-pressed="true"]{color:var(--ui-primary-text,var(--ui-text));background:var(--ui-surface-selected,var(--ui-surface));border-color:var(--ui-border-strong,var(--ui-border))}
      .scheduling-navigation .scheduling-source{font-size:12px;color:var(--ui-info-muted);margin-left:auto}
    `));
  }
  function RunWorkspace({
    onNavigate,
    initialContext
  }) {
    const api = useRunAdapter(onNavigate),
      specified = initialContext && Object.prototype.hasOwnProperty.call(initialContext, 'run_ref');
    return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Navigation, null, /*#__PURE__*/React.createElement(U.Button, {
      icon: "history",
      onClick: () => onNavigate('analysis', {
        source: 'run_history'
      })
    }, "\u6392\u4EA7\u8BB0\u5F55"), specified && /*#__PURE__*/React.createElement(U.Button, {
      icon: "plus",
      onClick: () => onNavigate('run', {})
    }, "\u65B0\u5EFA\u6392\u4EA7\u8303\u56F4")), specified ? /*#__PURE__*/React.createElement(ReadRun, {
      key: initialContext.run_ref,
      runRef: initialContext.run_ref,
      api: api
    }) : /*#__PURE__*/React.createElement(window.PreflightWorkspace, {
      initialContext: initialContext,
      onNavigate: onNavigate,
      renderRunPanel: data => /*#__PURE__*/React.createElement(window.RunJobPanel, {
        preflight: data,
        adapter: api
      })
    }));
  }
  function PlanCenterWorkspace({
    view,
    onNavigate,
    initialContext
  }) {
    const context = initialContext || {},
      candidate = Object.prototype.hasOwnProperty.call(context, 'run_ref') || Object.prototype.hasOwnProperty.call(context, 'candidate_ref');
    const history = !candidate && context.source === 'run_history';
    const historyQuery = candidate ? context.return_history_context : history ? context.history_query : undefined;
    function renderTrial({
      planRef,
      candidateRef,
      scope,
      query,
      disabled,
      taskOrigin,
      label = '试调'
    }) {
      const display = {
        query
      };
      if (scope.range_start && scope.range_end) {
        display.range_start = scope.range_start;
        display.range_end = scope.range_end;
      }
      if (scope.batch_ref) display.batch_refs = [scope.batch_ref];
      return /*#__PURE__*/React.createElement(U.Button, {
        icon: "square-pen",
        disabled: disabled,
        onClick: () => onNavigate('trial', {
          base: candidateRef ? {
            candidate_ref: candidateRef
          } : {
            plan_ref: planRef
          },
          scope: display,
          ...(taskOrigin ? {
            task_origin: taskOrigin
          } : {})
        })
      }, label);
    }
    return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Navigation, null, /*#__PURE__*/React.createElement(U.Button, {
      icon: "files",
      "aria-pressed": !candidate && !history,
      onClick: () => onNavigate(view, {})
    }, "\u8BA1\u5212\u7248\u672C"), /*#__PURE__*/React.createElement(U.Button, {
      icon: "history",
      "aria-pressed": history,
      onClick: () => onNavigate('analysis', {
        source: 'run_history',
        ...(historyQuery ? {
          history_query: historyQuery
        } : {})
      })
    }, "\u6392\u4EA7\u8BB0\u5F55"), candidate && /*#__PURE__*/React.createElement("span", {
      className: "scheduling-source"
    }, "\u5019\u9009\u9884\u89C8 \xB7 \u975E\u6B63\u5F0F\u6267\u884C\u5B89\u6392")), candidate ? /*#__PURE__*/React.createElement(window.RunCandidateWorkspace, {
      view: view,
      initialContext: initialContext,
      onNavigate: onNavigate,
      renderAdoption: candidateRef => /*#__PURE__*/React.createElement(window.RunAdoptionAction, {
        candidateRef: candidateRef,
        onNavigate: onNavigate
      }),
      renderTrial: renderTrial
    }) : history ? /*#__PURE__*/React.createElement(window.RunHistoryWorkspace, {
      initialContext: context.history_query,
      onNavigate: onNavigate
    }) : /*#__PURE__*/React.createElement(window.PlanWorkspace, {
      view: view,
      initialContext: initialContext,
      onNavigate: onNavigate,
      renderTrial: renderTrial
    }));
  }
  window.RunWorkspace = RunWorkspace;
  window.PlanCenterWorkspace = PlanCenterWorkspace;
})();
