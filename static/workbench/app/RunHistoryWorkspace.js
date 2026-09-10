(function () {
  'use strict';

  const A = window.RunHistoryAPI,
    C = window.RunHistoryControls;
  const adapterIds = new WeakMap();
  let nextAdapter = 0;
  function useRead(adapter, query, revision) {
    const identity = React.useMemo(() => ({}), [adapter, query, revision]);
    const [state, setState] = React.useState({});
    React.useEffect(() => {
      const controller = new AbortController();
      let active = true;
      setState({
        identity,
        busy: true,
        result: null,
        error: null
      });
      Promise.resolve().then(() => adapter.catalog(query, controller.signal)).then(result => {
        A.catalog(result, query);
        if (active) setState({
          identity,
          busy: false,
          result,
          error: null
        });
      }).catch(error => {
        if (active) setState({
          identity,
          busy: false,
          result: null,
          error
        });
      });
      return () => {
        active = false;
        controller.abort();
      };
    }, [identity]);
    return state.identity === identity ? state : {
      busy: true,
      result: null,
      error: null
    };
  }
  function Session({
    adapter,
    start,
    onNavigate
  }) {
    const [query, setQuery] = React.useState(start.query),
      [revision, refresh] = React.useReducer(v => v + 1, 0);
    const read = useRead(adapter, query, revision),
      result = read.result,
      data = result && result.data;
    const stale = read.error && read.error.code === 'snapshot_stale';
    function reload() {
      setQuery(q => {
        const next = {
          ...q,
          page: 1
        };
        delete next.snapshot_ref;
        return next;
      });
      refresh();
    }
    function apply(q) {
      setQuery(q);
      refresh();
    }
    function change(patch, paging) {
      const q = {
        ...query,
        ...patch
      };
      delete q.snapshot_ref;
      if (paging && result) q.snapshot_ref = result.meta.snapshot_ref;
      apply(A.scope(q));
    }
    function open(run) {
      if (typeof onNavigate !== 'function') return;
      const context = {
        run_ref: run.run_ref,
        return_history_context: A.returnContext(query, start.returnPlan)
      };
      if (Object.keys(start.returnPlan).length) context.return_plan_context = start.returnPlan;
      onNavigate('analysis', context);
    }
    return /*#__PURE__*/React.createElement("div", {
      className: "plana run-history-workspace",
      "data-run-history-workspace": true,
      "aria-busy": read.busy
    }, /*#__PURE__*/React.createElement(C.Styles, null), /*#__PURE__*/React.createElement("header", {
      className: "rh-heading"
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("h2", null, "\u6392\u4EA7\u5386\u53F2"), /*#__PURE__*/React.createElement("span", {
      className: "rh-muted"
    }, "\u8FD0\u884C\u8BB0\u5F55 \xB7 \u53EA\u8BFB")), /*#__PURE__*/React.createElement("div", {
      className: "rh-tools"
    }, typeof onNavigate === 'function' && /*#__PURE__*/React.createElement(C.Button, {
      icon: "chevron-left",
      "aria-label": "\u8FD4\u56DE\u65B9\u6848\u9875",
      onClick: () => onNavigate('analysis', start.returnPlan)
    }, "\u8FD4\u56DE\u65B9\u6848"), /*#__PURE__*/React.createElement(C.Button, {
      icon: "refresh-cw",
      "aria-label": "\u5237\u65B0\u6392\u4EA7\u5386\u53F2",
      busy: read.busy,
      onClick: reload
    }))), /*#__PURE__*/React.createElement(C.Filters, {
      value: query,
      busy: read.busy,
      onApply: apply
    }), /*#__PURE__*/React.createElement(C.ErrorBox, {
      error: read.error
    }), read.error && /*#__PURE__*/React.createElement(C.Button, {
      icon: "refresh-cw",
      onClick: reload
    }, stale ? '明确重读历史' : '重新读取历史'), read.busy && /*#__PURE__*/React.createElement("div", {
      className: "rh-empty",
      role: "status"
    }, /*#__PURE__*/React.createElement("strong", null, "\u6B63\u5728\u8BFB\u53D6\u6392\u4EA7\u5386\u53F2"), "\u5F53\u524D\u7B5B\u9009\u7ED3\u679C\u5C1A\u672A\u8FD4\u56DE"), data && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      className: "rh-source"
    }, /*#__PURE__*/React.createElement("span", null, "\u76EE\u5F55\u5171 ", data.run_count.toLocaleString('zh-CN'), " \u6B21 \xB7 \u53D7\u7406\u65E5\u671F\u6309\u5DE5\u5382\u672C\u5730\u65F6\u95F4\uFF0C\u542B\u8D77\u6B62\u65E5"), /*#__PURE__*/React.createElement("span", null, "\u8BFB\u53D6\u4E8E ", C.timeLabel(result.meta.as_of))), result.warnings.map((w, i) => /*#__PURE__*/React.createElement("div", {
      key: i,
      className: "rh-notice",
      role: "status"
    }, w.message)), data.runs.length ? /*#__PURE__*/React.createElement(C.Table, {
      runs: data.runs,
      canNavigate: typeof onNavigate === 'function',
      onOpen: open
    }) : /*#__PURE__*/React.createElement("div", {
      className: "rh-empty",
      role: "status"
    }, /*#__PURE__*/React.createElement("strong", null, data.run_count === 0 ? '尚无排产运行记录' : data.page.total === 0 ? '当前筛选没有匹配的运行记录' : '当前页没有运行记录'), data.run_count === 0 ? '排产运行受理后会保留在此目录。' : data.page.total === 0 ? '其他运行未包含在当前筛选中。' : '当前页超出结果范围。', data.page.total > 0 && /*#__PURE__*/React.createElement(C.Button, {
      icon: "chevron-left",
      onClick: () => change({
        page: 1
      }, true)
    }, "\u8FD4\u56DE\u7B2C\u4E00\u9875")), /*#__PURE__*/React.createElement(C.Pager, {
      page: data.page,
      busy: read.busy,
      onChange: change
    }), /*#__PURE__*/React.createElement("div", {
      className: "rh-muted"
    }, "\u5B89\u6392\u884C\u6570\u662F\u5404\u5019\u9009\u5DF2\u4FDD\u5B58\u884C\u7684\u5408\u8BA1\uFF0C\u4E0D\u662F\u53BB\u91CD\u5DE5\u5E8F\u6570\u3002\u8BA1\u7B97\u5B8C\u6210\u4EC5\u8868\u793A\u8FD0\u884C\u7ED3\u675F\uFF1B\u7EA6\u675F\u4E0E\u4EFB\u52A1\u5185\u5BB9\u987B\u5728\u5019\u9009\u4E2D\u6838\u5BF9\u3002")));
  }
  function RunHistoryWorkspace({
    initialContext = {},
    onNavigate,
    adapter
  }) {
    const fallback = React.useMemo(() => A.create(), []),
      active = adapter || fallback;
    let start;
    try {
      start = A.context(initialContext);
      A.check(active && typeof active.catalog === 'function', '排产历史读取适配器不可用。');
    } catch (error) {
      return /*#__PURE__*/React.createElement("div", {
        className: "plana run-history-workspace",
        "data-run-history-workspace": true
      }, /*#__PURE__*/React.createElement(C.Styles, null), /*#__PURE__*/React.createElement("h2", null, "\u6392\u4EA7\u5386\u53F2"), /*#__PURE__*/React.createElement(C.ErrorBox, {
        error: error
      }));
    }
    if (!adapterIds.has(active)) adapterIds.set(active, ++nextAdapter);
    return /*#__PURE__*/React.createElement(Session, {
      key: adapterIds.get(active) + ':' + JSON.stringify(start),
      adapter: active,
      start: start,
      onNavigate: onNavigate
    });
  }
  window.RunHistoryWorkspace = RunHistoryWorkspace;
})();
