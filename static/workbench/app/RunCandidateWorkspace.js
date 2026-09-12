(function () {
  'use strict';

  const A = window.RunCandidateAPI,
    C = window.RunCandidateControls;
  const adapterIds = new WeakMap();
  let nextAdapter = 0;
  function useRead(load, deps, enabled) {
    const identity = React.useMemo(() => ({}), deps);
    const [state, setState] = React.useState({
      result: null,
      error: null,
      busy: false
    });
    React.useEffect(() => {
      const controller = new AbortController();
      let active = true;
      setState({
        identity,
        result: null,
        error: null,
        busy: enabled
      });
      if (enabled) Promise.resolve().then(() => load(controller.signal)).then(result => {
        if (active) setState({
          identity,
          result,
          error: null,
          busy: false
        });
      }).catch(error => {
        if (active) setState({
          identity,
          result: null,
          error,
          busy: false
        });
      });
      return () => {
        active = false;
        controller.abort();
      };
    }, deps);
    return state.identity === identity ? state : {
      result: null,
      error: null,
      busy: enabled
    };
  }
  function returnContext(value) {
    const result = {};
    for (const key of ['run_ref', 'candidate_ref', 'plan_ref', 'batch_ref']) if (value && A.ref(value[key])) result[key] = value[key];
    for (const key of ['range_start', 'range_end']) if (value && A.time(value[key])) result[key] = value[key];
    return result;
  }
  function Export({
    adapter,
    result,
    scope,
    query
  }) {
    const [busy, setBusy] = React.useState(false),
      [error, setError] = React.useState(null),
      [done, setDone] = React.useState('');
    const active = React.useRef(null);
    React.useEffect(() => () => {
      if (active.current) active.current.abort();
    }, []);
    const d = result.data,
      allowed = d.capabilities.export === true && d.candidate.capabilities.export === true && typeof adapter.export === 'function';
    async function save(fmt) {
      if (!allowed || active.current) return;
      const controller = new AbortController();
      active.current = controller;
      setBusy(true);
      setError(null);
      setDone('');
      try {
        const file = A.download(await adapter.export(d.candidate.candidate_ref, scope, result.meta.snapshot_ref, fmt, controller.signal), result, fmt);
        if (controller.signal.aborted) return;
        const url = URL.createObjectURL(file.blob),
          link = document.createElement('a');
        link.href = url;
        link.download = file.filename;
        document.body.appendChild(link);
        link.click();
        link.remove();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
        setDone('已下载 ' + file.row_count + ' 条记录（安排 ' + d.task_count + '，未安排 ' + (d.unplanned_operation_count === null ? '未知' : d.unplanned_operation_count) + '）。');
      } catch (e) {
        if (!controller.signal.aborted) setError(e);
      } finally {
        if (!controller.signal.aborted) {
          active.current = null;
          setBusy(false);
        }
      }
    }
    return /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
      className: "rc-tools"
    }, ['csv', 'xlsx'].map(fmt => /*#__PURE__*/React.createElement(C.Button, {
      key: fmt,
      icon: "download",
      title: "\u5BFC\u51FA\u5F53\u524D\u8BFB\u53D6\u8303\u56F4\u5168\u90E8\u5B89\u6392\u4E0E\u672A\u5B89\u6392\u8BB0\u5F55",
      disabled: !allowed,
      busy: busy,
      onClick: () => save(fmt)
    }, fmt.toUpperCase()))), query.trim() && /*#__PURE__*/React.createElement("small", null, "\u641C\u7D22\u4E0D\u6539\u53D8\u5BFC\u51FA\u8303\u56F4"), /*#__PURE__*/React.createElement(C.ErrorBox, {
      error: error
    }), done && /*#__PURE__*/React.createElement("small", {
      role: "status"
    }, done));
  }
  function Session({
    adapter,
    view = 'analysis',
    initialContext = {},
    onNavigate,
    renderAdoption,
    renderTrial
  }) {
    const M = window.RunCandidateModel,
      Analysis = window.RunCandidateAnalysis,
      AnalysisAPI = window.RunCandidateAnalysisAPI;
    const invalid = initialContext.run_ref !== undefined && !A.ref(initialContext.run_ref) || initialContext.candidate_ref !== undefined && !A.ref(initialContext.candidate_ref);
    const [runRef, setRunRef] = React.useState(initialContext.run_ref || null),
      [candidateRef, setCandidateRef] = React.useState(initialContext.candidate_ref || null);
    const [catalogQuery, setCatalogQuery] = React.useState({}),
      [scope, setScope] = React.useState(() => {
        const value = {};
        for (const key of ['range_start', 'range_end', 'batch_ref', 'sort', 'order']) if (initialContext[key] !== undefined) value[key] = initialContext[key];
        return value;
      });
    const [range, setRange] = React.useState({
        start: scope.range_start || '',
        end: scope.range_end || ''
      }),
      [rangeOpen, setRangeOpen] = React.useState(false);
    const [rangeError, setRangeError] = React.useState(null),
      [query, setQuery] = React.useState(typeof initialContext.query === 'string' ? initialContext.query : ''),
      [selected, setSelected] = React.useState(null);
    const [pendingRow, setPendingRow] = React.useState(A.ref(initialContext.selected_row_ref) ? initialContext.selected_row_ref : null);
    const [tab, setTab] = React.useState((view === 'delay' ? ['tasks', 'unplanned'] : ['tasks', 'unplanned', 'delivery', 'history']).includes(initialContext.candidate_tab) ? initialContext.candidate_tab : 'tasks'),
      [revision, refresh] = React.useReducer(v => v + 1, 0);
    const [analysisPaused, setAnalysisPaused] = React.useState(false);
    const directory = useRead(async signal => {
      const v = await adapter.catalog(runRef, catalogQuery, signal);
      A.catalog(v, runRef, catalogQuery);
      return v;
    }, [adapter, runRef, catalogQuery, revision], !!runRef && !invalid);
    const read = useRead(async signal => {
      const v = await adapter.workspace(candidateRef, scope, signal);
      A.workspace(v, candidateRef, scope, initialContext.run_ref);
      return v;
    }, [adapter, candidateRef, scope, revision], !!candidateRef && !invalid);
    const result = read.result,
      data = result && result.data;
    React.useEffect(() => {
      if (data && !runRef) setRunRef(data.candidate.run_ref);
    }, [data, runRef]);
    const shown = data && data.capabilities.view === true && data.candidate.capabilities.view === true ? data : null;
    const analysisRead = useRead(async signal => {
      if (typeof adapter.analysis !== 'function') throw new Error('完整候选比较接口尚未接入，未用可见安排估算。');
      const value = await adapter.analysis(candidateRef, runRef, signal);
      AnalysisAPI.analysis(value, candidateRef, runRef);
      return value;
    }, [adapter, candidateRef, runRef, revision, analysisPaused], !!candidateRef && !invalid && !analysisPaused);
    const historyRead = useRead(async signal => {
      if (typeof adapter.adoptions !== 'function') throw new Error('候选采用历史接口尚未接入，未显示其他来源记录。');
      const value = await adapter.adoptions(candidateRef, runRef, signal);
      AnalysisAPI.history(value, candidateRef, runRef);
      return value;
    }, [adapter, candidateRef, runRef, tab, revision, analysisPaused], !!candidateRef && !invalid && tab === 'history' && !analysisPaused);
    const analysis = shown && analysisRead.result && analysisRead.result.data.run_ref === shown.candidate.run_ref ? analysisRead.result.data : null;
    window.WorkbenchCaption.useCaption(shown && !read.busy && !read.error && shown.candidate.label ? {
      reference: shown.candidate.candidate_ref,
      label: '当前候选',
      name: shown.candidate.label,
      status: '候选预览 · ' + ({
        completed: '已完成',
        partial: '部分完成',
        failed: '失败',
        skipped: '已跳过'
      }[shown.candidate.status] || '状态待核实'),
      range: (scope.range_start ? M.timeLabel(scope.range_start) + ' 至 ' + M.timeLabel(scope.range_end) + '（不含结束）' : '完整候选范围') + ' · ' + shown.task_count + ' / ' + shown.candidate_task_count + ' 道安排'
    } : null);
    const tasks = React.useMemo(() => shown ? M.matching(shown.tasks, query) : [], [shown, query]);
    const unplanned = React.useMemo(() => shown ? M.matching(shown.unplanned_operations || [], query) : [], [shown, query]);
    const chosen = selected && selected.result === result ? selected.task : null;
    React.useEffect(() => {
      if (!shown || !pendingRow) return;
      const task = shown.tasks.find(row => row.row_ref === pendingRow);
      if (task) {
        setSelected({
          task,
          result
        });
        setPendingRow(null);
      } else if (!scope.range_start && !scope.batch_ref) {
        setRangeError(new Error('指定末端工序不在完整候选中，未替换为其他工序。'));
        setPendingRow(null);
      }
    }, [result, pendingRow]);
    const remembered = {
      ...initialContext,
      ...(runRef ? {
        run_ref: runRef
      } : {}),
      ...(candidateRef ? {
        candidate_ref: candidateRef
      } : {}),
      query,
      candidate_tab: tab
    };
    for (const key of ['range_start', 'range_end', 'batch_ref', 'sort', 'order', 'snapshot_ref', 'selected_row_ref']) delete remembered[key];
    Object.assign(remembered, scope, chosen ? {
      selected_row_ref: chosen.row_ref
    } : {});
    window.WorkbenchPageContext.useSnapshot(remembered, !!shown && !read.busy && !read.error && !invalid);
    function choose(candidate) {
      setCandidateRef(candidate.candidate_ref);
      setScope({});
      setRange({
        start: '',
        end: ''
      });
      setRangeError(null);
      setQuery('');
      setSelected(null);
      setAnalysisPaused(false);
    }
    function select(task) {
      setSelected({
        task,
        result
      });
    }
    function lastOperation(task) {
      setQuery('');
      const visible = shown.tasks.find(row => row.row_ref === task.row_ref);
      if (visible) select(visible);else {
        setPendingRow(task.row_ref);
        setScope({});
        setRange({
          start: '',
          end: ''
        });
        setSelected(null);
      }
    }
    function reload() {
      setCatalogQuery(q => {
        const value = {
          ...q
        };
        delete value.snapshot_ref;
        return value;
      });
      setSelected(null);
      setAnalysisPaused(false);
      refresh();
    }
    function rangeSubmit(e) {
      e.preventDefault();
      try {
        const seconds = value => value.length === 16 ? value + ':00' : value;
        const next = A.workspaceScope(candidateRef, {
          ...scope,
          range_start: seconds(range.start),
          range_end: seconds(range.end)
        });
        setScope(next);
        setRangeError(null);
        setSelected(null);
      } catch (error) {
        setRangeError(error);
      }
    }
    return /*#__PURE__*/React.createElement("div", {
      className: "plana run-candidate-workspace",
      "data-run-candidate-workspace": true
    }, /*#__PURE__*/React.createElement(C.Styles, null), /*#__PURE__*/React.createElement("div", {
      className: "rc-heading"
    }, /*#__PURE__*/React.createElement("div", {
      className: "rc-tools"
    }, /*#__PURE__*/React.createElement("h2", null, view === 'delay' ? '候选交付风险' : view === 'gantt' ? '候选甘特' : '候选排产结果'), /*#__PURE__*/React.createElement("span", {
      className: "rc-muted"
    }, "\u5DF2\u4FDD\u5B58\u7684\u5019\u9009\u65B9\u6848")), /*#__PURE__*/React.createElement("div", {
      className: "rc-tools"
    }, onNavigate && /*#__PURE__*/React.createElement(C.Button, {
      icon: "chevron-left",
      onClick: () => onNavigate('run', {
        ...returnContext(initialContext.return_run_context),
        ...(runRef ? {
          run_ref: runRef
        } : {})
      })
    }, "\u8FD4\u56DE\u8FD0\u884C\u9875"), onNavigate && initialContext.return_plan_context && A.ref(initialContext.return_plan_context.plan_ref) && /*#__PURE__*/React.createElement(C.Button, {
      icon: "chevron-left",
      onClick: () => onNavigate('analysis', returnContext(initialContext.return_plan_context))
    }, "\u8FD4\u56DE\u6B63\u5F0F\u65B9\u6848"), typeof renderAdoption === 'function' ? renderAdoption(candidateRef) : /*#__PURE__*/React.createElement(C.Button, {
      icon: "check",
      className: "btn primary",
      reasonDisplay: "inline",
      reason: "\u6B63\u5F0F\u91C7\u7528\u5165\u53E3\u672A\u63A5\u5165\uFF0C\u8BF7\u5148\u6838\u5BF9\u5B8C\u6574\u5019\u9009\u65B9\u6848\u3002"
    }, "\u91C7\u7528\u65B9\u6848"), typeof renderTrial === 'function' ? renderTrial({
      candidateRef,
      scope,
      query,
      disabled: !shown || read.busy || invalid
    }) : /*#__PURE__*/React.createElement(C.Button, {
      icon: "square-pen",
      reason: "\u8BD5\u8C03\u5165\u53E3\u672A\u63A5\u5165\uFF0C\u8BF7\u5148\u6838\u5BF9\u5B8C\u6574\u5019\u9009\u65B9\u6848\u3002"
    }, "\u8BD5\u8C03"), /*#__PURE__*/React.createElement(C.Button, {
      icon: "refresh-cw",
      "aria-label": "\u5237\u65B0\u6307\u5B9A\u5019\u9009\u6765\u6E90",
      disabled: invalid || !runRef && !candidateRef,
      busy: read.busy || directory.busy,
      onClick: reload
    }))), invalid && /*#__PURE__*/React.createElement(C.ErrorBox, {
      error: new Error('记录编号无效，未改查其他运行或最新候选。')
    }), !runRef && !candidateRef && /*#__PURE__*/React.createElement("div", {
      className: "rc-empty",
      role: "status"
    }, "\u5C1A\u672A\u6307\u5B9A\u8FD0\u884C\u6216\u5019\u9009\u6765\u6E90\u3002\u8BF7\u4ECE\u8FD0\u884C\u8BB0\u5F55\u6253\u5F00\u5019\u9009\uFF0C\u672A\u81EA\u52A8\u9009\u62E9\u6700\u65B0\u8FD0\u884C\u3002"), runRef && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(C.ErrorBox, {
      error: directory.error
    }), /*#__PURE__*/React.createElement(C.Catalog, {
      result: directory.result,
      selectedRef: candidateRef,
      busy: directory.busy,
      query: catalogQuery,
      onQuery: (change, paging) => setCatalogQuery(q => ({
        ...q,
        ...change,
        page: paging ? change.page : 1,
        snapshot_ref: paging ? directory.result.meta.snapshot_ref : undefined
      })),
      onSelect: choose
    })), /*#__PURE__*/React.createElement(C.ErrorBox, {
      error: read.error
    }), (read.busy || directory.busy) && /*#__PURE__*/React.createElement("p", {
      className: "rc-muted",
      role: "status"
    }, "\u6B63\u5728\u8BFB\u53D6\u6307\u5B9A\u5019\u9009\u6765\u6E90\u3002"), read.error && /*#__PURE__*/React.createElement("div", {
      className: "rc-empty"
    }, "\u6307\u5B9A\u5019\u9009\u672A\u8BFB\u53D6\u6210\u529F\uFF0C\u672A\u663E\u793A\u5176\u4ED6\u5019\u9009\u6216\u4E0A\u6B21\u5185\u5BB9\u3002"), (analysisRead.busy || historyRead.busy) && /*#__PURE__*/React.createElement("div", {
      className: "rc-tools"
    }, /*#__PURE__*/React.createElement("span", {
      role: "status"
    }, "\u6B63\u5728\u6838\u5BF9\u6307\u5B9A\u5019\u9009\u7684\u5B8C\u6574\u8BC1\u636E\u3002"), /*#__PURE__*/React.createElement(C.Button, {
      icon: "x",
      "aria-label": "\u53D6\u6D88\u5019\u9009\u6BD4\u8F83\u8BFB\u53D6",
      onClick: () => setAnalysisPaused(true)
    }, "\u53D6\u6D88\u8BFB\u53D6")), analysisPaused && /*#__PURE__*/React.createElement("div", {
      className: "rc-tools"
    }, /*#__PURE__*/React.createElement("span", {
      role: "status"
    }, "\u5019\u9009\u6BD4\u8F83\u8BFB\u53D6\u5DF2\u53D6\u6D88\uFF0C\u672A\u663E\u793A\u4E0A\u6B21\u6BD4\u8F83\u3002"), /*#__PURE__*/React.createElement(C.Button, {
      icon: "refresh-cw",
      onClick: reload
    }, "\u91CD\u65B0\u8BFB\u53D6\u5019\u9009\u6BD4\u8F83")), runRef && !candidateRef && /*#__PURE__*/React.createElement("div", {
      className: "rc-empty"
    }, "\u5C1A\u672A\u9009\u62E9\u6B64\u8FD0\u884C\u4E2D\u7684\u5019\u9009\u3002"), data && !shown && /*#__PURE__*/React.createElement("div", {
      className: "rc-notice"
    }, "\u63A5\u53E3\u672A\u6388\u6743\u67E5\u770B\u8BE5\u5019\u9009\u3002", /*#__PURE__*/React.createElement(C.Reasons, {
      rows: data.blocked_reasons
    })), shown && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(C.Generation, {
      key: shown.candidate.candidate_ref,
      data: shown,
      analysis: analysis
    }), /*#__PURE__*/React.createElement(C.Reasons, {
      rows: result.warnings
    }), /*#__PURE__*/React.createElement(C.ErrorBox, {
      error: analysisRead.error
    }), /*#__PURE__*/React.createElement("div", {
      className: "rc-heading"
    }, /*#__PURE__*/React.createElement("div", {
      className: "rc-tools"
    }, /*#__PURE__*/React.createElement("h3", null, "\u5019\u9009\u5DE5\u4F5C\u533A"), /*#__PURE__*/React.createElement("span", {
      className: "rc-muted"
    }, "\u8BFB\u53D6\u4E8E ", M.timeLabel(result.meta.as_of), " \xB7 \u5DE5\u5382\u672C\u5730\u65F6\u95F4")), /*#__PURE__*/React.createElement("div", {
      className: "rc-tools"
    }, /*#__PURE__*/React.createElement("input", {
      type: "search",
      "aria-label": "\u641C\u7D22\u5019\u9009\u5DE5\u5E8F",
      placeholder: "\u6279\u6B21\u3001\u5DE5\u5E8F\u3001\u8BBE\u5907\u3001\u4EBA\u5458",
      value: query,
      onChange: e => setQuery(e.target.value)
    }), /*#__PURE__*/React.createElement("span", {
      className: "rc-muted"
    }, "\u5339\u914D\u5B89\u6392 ", tasks.length, " / ", shown.task_count)), /*#__PURE__*/React.createElement("div", {
      className: "rc-tools"
    }, /*#__PURE__*/React.createElement(C.Button, {
      icon: "calendar-days",
      "aria-expanded": rangeOpen,
      onClick: () => setRangeOpen(!rangeOpen)
    }, "\u8BFB\u53D6\u8303\u56F4"), /*#__PURE__*/React.createElement(Export, {
      key: result.meta.snapshot_ref,
      adapter: adapter,
      result: result,
      scope: scope,
      query: query
    }))), rangeOpen && /*#__PURE__*/React.createElement("form", {
      className: "rc-range",
      onSubmit: rangeSubmit
    }, /*#__PURE__*/React.createElement("label", null, "\u5F00\u59CB\uFF08\u5305\u542B\uFF09", /*#__PURE__*/React.createElement("input", {
      type: "datetime-local",
      step: "1",
      "aria-label": "\u5019\u9009\u8BFB\u53D6\u5F00\u59CB",
      value: range.start,
      onChange: e => setRange({
        ...range,
        start: e.target.value
      })
    })), /*#__PURE__*/React.createElement("label", null, "\u7ED3\u675F\uFF08\u4E0D\u542B\uFF09", /*#__PURE__*/React.createElement("input", {
      type: "datetime-local",
      step: "1",
      "aria-label": "\u5019\u9009\u8BFB\u53D6\u7ED3\u675F",
      value: range.end,
      onChange: e => setRange({
        ...range,
        end: e.target.value
      })
    })), /*#__PURE__*/React.createElement(C.Button, {
      icon: "check",
      type: "submit"
    }, "\u5E94\u7528\u8303\u56F4"), /*#__PURE__*/React.createElement(C.Button, {
      icon: "chart-gantt",
      onClick: () => {
        setScope({});
        setRange({
          start: '',
          end: ''
        });
        setRangeError(null);
      }
    }, "\u5B8C\u6574\u5019\u9009")), /*#__PURE__*/React.createElement(C.ErrorBox, {
      error: rangeError
    }), /*#__PURE__*/React.createElement("div", {
      className: "rc-scope"
    }, /*#__PURE__*/React.createElement("span", null, "\u8BFB\u53D6\u8303\u56F4\uFF1A", scope.range_start ? M.timeLabel(scope.range_start) + ' 至 ' + M.timeLabel(scope.range_end) + '（不含结束）' : '全部时间', scope.batch_ref && ' · 指定批次', ' · 安排 ' + shown.task_count + ' / 候选共 ' + shown.candidate_task_count + ' 道 · 未安排 ' + (shown.unplanned_operation_count === null ? '未知（未记录）' : shown.unplanned_operation_count + ' 道')), scope.batch_ref && /*#__PURE__*/React.createElement(window.WorkbenchReference, {
      entries: {
        '筛选批次编号': scope.batch_ref
      }
    }), /*#__PURE__*/React.createElement("details", null, /*#__PURE__*/React.createElement("summary", null, "\u8303\u56F4\u4E0E\u5BFC\u51FA\u53E3\u5F84"), /*#__PURE__*/React.createElement("div", null, "\u65F6\u95F4\u7B5B\u9009\u6309\u91CD\u53E0\u8BFB\u53D6\uFF0C\u4FDD\u7559\u6BCF\u9053\u5B89\u6392\u5B8C\u6574\u8D77\u6B62\uFF1B\u672A\u5B89\u6392\u9879\u6CA1\u6709\u65F6\u95F4\u533A\u95F4\uFF0C\u4ECD\u968F\u8303\u56F4\u4FDD\u7559\u3002\u641C\u7D22\u4EC5\u5F71\u54CD\u9884\u89C8\u548C\u660E\u7EC6\uFF0C\u4E0D\u6539\u53D8\u5BFC\u51FA\u8303\u56F4\u3002\u5BFC\u51FA\u5F53\u524D\u8BFB\u53D6\u8303\u56F4\u5168\u90E8\u5B89\u6392\u4E0E\u672A\u5B89\u6392\u8BB0\u5F55\u3002"))), view === 'delay' && /*#__PURE__*/React.createElement(C.Delivery, {
      data: shown.delivery_risks,
      onLast: lastOperation
    }), /*#__PURE__*/React.createElement("div", {
      className: "rc-main",
      style: ['delivery', 'history'].includes(tab) ? {
        gridTemplateColumns: 'minmax(0,1fr)'
      } : undefined
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement(window.RunCandidateGantt, {
      data: shown,
      query: query,
      selected: chosen,
      onSelect: select
    }), /*#__PURE__*/React.createElement("section", {
      "aria-label": "\u5019\u9009\u660E\u7EC6"
    }, /*#__PURE__*/React.createElement("div", {
      className: "rc-heading"
    }, /*#__PURE__*/React.createElement("div", {
      role: "tablist",
      className: "rc-tabs",
      "aria-label": "\u5019\u9009\u660E\u7EC6\u7C7B\u522B"
    }, ['tasks', 'unplanned', ...(view === 'delay' ? [] : ['delivery', 'history'])].map(t => /*#__PURE__*/React.createElement(C.Button, {
      key: t,
      role: "tab",
      icon: t === 'tasks' ? 'chart-gantt' : t === 'history' ? 'history' : 'circle-alert',
      "aria-selected": tab === t,
      onClick: () => setTab(t)
    }, t === 'tasks' ? '任务安排' : t === 'delivery' ? '交付风险' : t === 'history' ? '采用记录' : '未安排明细')))), tab === 'history' ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(C.ErrorBox, {
      error: historyRead.error
    }), historyRead.result && /*#__PURE__*/React.createElement(Analysis.History, {
      data: historyRead.result.data,
      onPlan: onNavigate && (plan => onNavigate('analysis', {
        plan_ref: plan.plan_ref
      }))
    })) : tab === 'delivery' ? analysis && /*#__PURE__*/React.createElement(Analysis.Batches, {
      key: analysis.candidate_ref,
      data: analysis,
      onLast: task => {
        lastOperation(task);
        setTab('tasks');
      },
      onBatch: onNavigate && (row => onNavigate('gantt', {
        run_ref: analysis.run_ref,
        candidate_ref: analysis.candidate_ref,
        batch_ref: row.batch_ref,
        candidate_tab: 'tasks'
      }))
    }) : tab === 'unplanned' && shown.unplanned_operations === null ? /*#__PURE__*/React.createElement("div", {
      className: "rc-notice"
    }, "\u751F\u6210\u65F6\u672A\u4FDD\u7559\u53EF\u6838\u5B9E\u7684\u672A\u5B89\u6392\u660E\u7EC6\uFF0C\u4E0D\u80FD\u5F53\u6210\u96F6\u9879\u3002") : /*#__PURE__*/React.createElement(window.RunCandidateGantt.TaskList, {
      key: tab + ':' + query + ':' + result.meta.snapshot_ref,
      tasks: tab === 'tasks' ? tasks : unplanned,
      selected: chosen,
      onSelect: select,
      planned: tab === 'tasks'
    }))), !['delivery', 'history'].includes(tab) && /*#__PURE__*/React.createElement(C.Detail, {
      task: chosen,
      onClose: () => setSelected(null)
    })), analysis && /*#__PURE__*/React.createElement(Analysis.Overview, {
      data: analysis
    })));
  }
  function RunCandidateWorkspace(props) {
    const adapter = React.useMemo(() => props.adapter || window.RunCandidateAnalysisAPI.create(), [props.adapter]);
    if (!adapterIds.has(adapter)) adapterIds.set(adapter, ++nextAdapter);
    const context = props.initialContext || {},
      identity = [context.run_ref, context.candidate_ref, context.range_start, context.range_end, context.batch_ref];
    return /*#__PURE__*/React.createElement(Session, {
      key: adapterIds.get(adapter) + ':' + JSON.stringify(identity),
      ...props,
      adapter: adapter
    });
  }
  window.RunCandidateWorkspace = RunCandidateWorkspace;
})();
