(function () {
  'use strict';

  const C = window.PreflightContract,
    {
      Button,
      ErrorBox
    } = window.PreflightControls;
  const baseScope = () => ({
    query: '',
    page: 1,
    size: 20,
    sort: 'business_code',
    direction: 'asc',
    column_filters: {
      status: ['pending', 'scheduled', 'processing']
    }
  });
  function DueDate({
    value
  }) {
    try {
      return /*#__PURE__*/React.createElement("span", null, "\u4EA4\u671F\uFF1A", window.WorkbenchFormat.date(value));
    } catch (error) {
      if (!(error instanceof TypeError)) throw error;
      return /*#__PURE__*/React.createElement("span", null, "\u4EA4\u671F\u539F\u503C\u5F85\u6838\u5BF9", /*#__PURE__*/React.createElement(window.WorkbenchReference, {
        entries: {
          '原交期': value,
          '格式说明': error.message
        }
      }));
    }
  }
  function PreflightBatchPicker({
    adapter,
    selected,
    onChange,
    disabled
  }) {
    const [scope, setScope] = React.useState(baseScope),
      [query, setQuery] = React.useState('');
    const [result, setResult] = React.useState(null),
      [error, setError] = React.useState(null),
      [loading, setLoading] = React.useState(true),
      [selecting, setSelecting] = React.useState(false);
    const serial = React.useRef(0),
      selectionController = React.useRef(null);
    React.useEffect(() => {
      let alive = true;
      const controller = new AbortController();
      setLoading(true);
      setResult(null);
      setError(null);
      adapter.list(scope, controller.signal).then(value => {
        if (alive) setResult(value);
      }, problem => {
        if (alive) setError(problem);
      }).finally(() => {
        if (alive) setLoading(false);
      });
      return () => {
        alive = false;
        controller.abort();
      };
    }, [adapter, scope]);
    React.useEffect(() => () => {
      serial.current++;
      if (selectionController.current) selectionController.current.abort();
    }, []);
    const data = result && result.data,
      snapshot = result && result.meta.snapshot_ref,
      chosen = new Set(selected);
    const busy = disabled || loading || selecting;
    function filter(patch) {
      setScope(old => ({
        ...old,
        ...patch,
        page: 1,
        snapshot_ref: undefined
      }));
    }
    function toggle(ref) {
      if (busy) return;
      const next = chosen.has(ref) ? selected.filter(item => item !== ref) : selected.concat(ref);
      if (!C.refs(next)) {
        setError(C.fail('最多选择5000个批次，请先缩小范围。'));
        return;
      }
      onChange(next);
    }
    async function select(mode) {
      if (busy || mode === 'filtered' && !snapshot) return;
      const id = ++serial.current,
        controller = new AbortController();
      selectionController.current = controller;
      setSelecting(true);
      setError(null);
      try {
        let requestScope = {
          ...scope,
          snapshot_ref: snapshot
        };
        if (mode !== 'filtered') {
          const next = {
            ...baseScope(),
            ...(mode === 'ready' ? {
              ready_status: 'yes'
            } : {})
          };
          const listed = await adapter.list(next, controller.signal);
          requestScope = {
            ...next,
            snapshot_ref: listed.meta.snapshot_ref
          };
        }
        const result = await adapter.selection(requestScope, controller.signal),
          refs = C.selection(result, requestScope.snapshot_ref);
        if (id === serial.current) onChange(refs);
      } catch (problem) {
        if (id === serial.current) setError(problem);
      } finally {
        if (id === serial.current) setSelecting(false);
      }
    }
    const visible = data ? data.entities : [],
      hidden = selected.filter(ref => !visible.some(row => row.ref === ref)).length;
    return /*#__PURE__*/React.createElement("section", {
      className: "pf-picker",
      "aria-label": "\u9009\u62E9\u6392\u4EA7\u6279\u6B21"
    }, /*#__PURE__*/React.createElement("form", {
      className: "pf-tools",
      onSubmit: event => {
        event.preventDefault();
        if (!busy) filter({
          query
        });
      }
    }, /*#__PURE__*/React.createElement("input", {
      type: "search",
      "aria-label": "\u641C\u7D22\u6392\u4EA7\u6279\u6B21",
      placeholder: "\u6279\u6B21\u53F7\u3001\u56FE\u53F7\u3001\u96F6\u4EF6\u540D",
      value: query,
      disabled: busy,
      onChange: event => setQuery(event.target.value)
    }), /*#__PURE__*/React.createElement(Button, {
      icon: "search",
      type: "submit",
      disabled: busy
    }, "\u641C\u7D22"), /*#__PURE__*/React.createElement("label", null, "\u9F50\u5957", /*#__PURE__*/React.createElement("select", {
      "aria-label": "\u6279\u6B21\u9F50\u5957\u7B5B\u9009",
      disabled: busy,
      value: scope.ready_status || '',
      onChange: event => filter({
        ready_status: event.target.value || undefined
      })
    }, /*#__PURE__*/React.createElement("option", {
      value: ""
    }, "\u5168\u90E8"), /*#__PURE__*/React.createElement("option", {
      value: "yes"
    }, "\u5DF2\u9F50\u5957"), /*#__PURE__*/React.createElement("option", {
      value: "partial"
    }, "\u90E8\u5206\u9F50\u5957"), /*#__PURE__*/React.createElement("option", {
      value: "no"
    }, "\u672A\u9F50\u5957"))), /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      "aria-label": "\u5237\u65B0\u6279\u6B21\u8303\u56F4",
      disabled: busy,
      onClick: () => filter({})
    })), /*#__PURE__*/React.createElement("div", {
      className: "pf-tools"
    }, /*#__PURE__*/React.createElement(Button, {
      disabled: busy,
      onClick: () => select('all')
    }, "\u5168\u90E8\u5F85\u6392"), /*#__PURE__*/React.createElement(Button, {
      disabled: busy,
      onClick: () => select('ready')
    }, "\u4EC5\u5DF2\u9F50\u5957"), /*#__PURE__*/React.createElement(Button, {
      disabled: busy || !snapshot,
      onClick: () => select('filtered')
    }, "\u5168\u9009\u5F53\u524D\u7B5B\u9009"), /*#__PURE__*/React.createElement(Button, {
      icon: "x",
      disabled: disabled || selecting || !selected.length,
      onClick: () => onChange([])
    }, "\u6E05\u7A7A\u9009\u62E9"), /*#__PURE__*/React.createElement("span", {
      "aria-live": "polite"
    }, "\u5DF2\u9009 ", selected.length, " \u6279", hidden > 0 ? ' · 含非当前页 ' + hidden + ' 批' : '')), /*#__PURE__*/React.createElement(ErrorBox, {
      error: error
    }), error && /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      disabled: disabled || loading || selecting,
      onClick: () => filter({})
    }, "\u91CD\u8BFB\u6279\u6B21"), loading || selecting ? /*#__PURE__*/React.createElement(window.WorkbenchListControls.EmptyState, {
      kind: "loading",
      title: selecting ? '正在核对全部选择范围' : '正在读取批次'
    }) : data && !visible.length ? /*#__PURE__*/React.createElement(window.WorkbenchListControls.EmptyState, {
      kind: "filtered",
      title: "\u5F53\u524D\u7B5B\u9009\u6CA1\u6709\u5F85\u6392\u6279\u6B21",
      hint: "\u8C03\u6574\u5173\u952E\u8BCD\u6216\u9F50\u5957\u7B5B\u9009\u540E\u518D\u8BD5\u3002",
      action: /*#__PURE__*/React.createElement(Button, {
        onClick: () => {
          setQuery('');
          setScope(baseScope());
        }
      }, "\u6E05\u9664\u7B5B\u9009")
    }) : null, !loading && data && /*#__PURE__*/React.createElement("div", {
      className: "pf-picker-list"
    }, visible.map(row => /*#__PURE__*/React.createElement("label", {
      className: "pf-picker-row",
      key: row.ref
    }, /*#__PURE__*/React.createElement("input", {
      type: "checkbox",
      "aria-label": '选择 ' + row.business_code,
      checked: chosen.has(row.ref),
      disabled: busy,
      onChange: () => toggle(row.ref)
    }), /*#__PURE__*/React.createElement("strong", null, row.business_code), /*#__PURE__*/React.createElement("span", null, row.relationships.part_no, " \xB7 ", row.label), /*#__PURE__*/React.createElement("span", null, row.relationships.operation_count, " \u9053\u5DE5\u5E8F"), /*#__PURE__*/React.createElement(DueDate, {
      value: row.fields.due_date
    }), /*#__PURE__*/React.createElement("span", null, "\u4F18\u5148\u7EA7\uFF1A", window.APSBatchContract.label('priority', row.fields.priority)), /*#__PURE__*/React.createElement("span", null, window.APSBatchContract.label('ready_status', row.fields.ready_status))))), data && /*#__PURE__*/React.createElement(window.WorkbenchListControls.Pager, {
      page: data.page,
      size: scope.size,
      sizes: [20, 50, 100],
      unit: "\u6279",
      label: "\u6279\u6B21",
      busy: busy,
      onSize: size => filter({
        size
      }),
      onPage: page => setScope(old => ({
        ...old,
        page,
        snapshot_ref: snapshot
      }))
    }));
  }
  window.PreflightBatchPicker = PreflightBatchPicker;
})();
