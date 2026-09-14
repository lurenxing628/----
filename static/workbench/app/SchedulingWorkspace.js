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
      "aria-label": "\u8FD9\u6B21\u6392\u4EA7"
    }, /*#__PURE__*/React.createElement(U.Styles, null), /*#__PURE__*/React.createElement("div", {
      className: "rj-heading"
    }, /*#__PURE__*/React.createElement("h2", null, "\u8FD9\u6B21\u6392\u4EA7"), /*#__PURE__*/React.createElement(U.Button, {
      icon: "refresh-cw",
      "aria-label": "\u5237\u65B0\u8FD9\u6B21\u6392\u4EA7",
      busy: checking,
      disabled: !A.ref(runRef),
      onClick: refresh
    })), !A.ref(runRef) ? /*#__PURE__*/React.createElement("p", {
      role: "alert"
    }, "\u8FD9\u6761\u6392\u4EA7\u8BB0\u5F55\u5DF2\u5931\u6548\uFF0C\u9875\u9762\u6CA1\u6709\u5207\u6362\u3002\u8BF7\u70B9\u300C\u6392\u4EA7\u8BB0\u5F55\u300D\u91CD\u65B0\u9009\u62E9\u3002") : /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(window.WorkbenchReference, {
      entries: {
        '排产编号': runRef
      }
    }), error && /*#__PURE__*/React.createElement("div", {
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
    }, checking ? '正在读取这次排产。' : paused ? '返回本页后继续读取这次排产。' : '还没读到这次排产的结果。请点右上角的刷新按钮。')));
  }
  function Navigation({
    children
  }) {
    return /*#__PURE__*/React.createElement("div", {
      className: "scheduling-navigation"
    }, children);
  }
  function RunWorkspace({
    onNavigate,
    initialContext
  }) {
    const api = useRunAdapter(onNavigate),
      specified = initialContext && Object.prototype.hasOwnProperty.call(initialContext, 'run_ref');
    const history = /*#__PURE__*/React.createElement(U.Button, {
      icon: "history",
      onClick: () => onNavigate('analysis', {
        source: 'run_history'
      })
    }, "\u6392\u4EA7\u8BB0\u5F55");
    // The preflight page carries 排产记录 in its own heading; only the specified-run view keeps the navigation strip.
    return specified ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Navigation, null, history, /*#__PURE__*/React.createElement(U.Button, {
      icon: "plus",
      onClick: () => onNavigate('run', {})
    }, "\u5F00\u59CB\u65B0\u6392\u4EA7")), /*#__PURE__*/React.createElement(ReadRun, {
      key: initialContext.run_ref,
      runRef: initialContext.run_ref,
      api: api
    })) : /*#__PURE__*/React.createElement(window.PreflightWorkspace, {
      initialContext: initialContext,
      onNavigate: onNavigate,
      actions: history,
      renderRunPanel: data => /*#__PURE__*/React.createElement(window.RunJobPanel, {
        preflight: data,
        adapter: api
      })
    });
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
    }, "\u6392\u4EA7\u8BB0\u5F55"), candidate && /*#__PURE__*/React.createElement(U.Button, {
      icon: "chart",
      "aria-pressed": true,
      "aria-current": "page"
    }, "\u5019\u9009\u65B9\u6848"), candidate && /*#__PURE__*/React.createElement("span", {
      className: "scheduling-source"
    }, "\u4E0D\u662F\u6B63\u5F0F\u8BA1\u5212")), candidate ? /*#__PURE__*/React.createElement(window.RunCandidateWorkspace, {
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
