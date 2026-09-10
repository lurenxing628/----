(function () {
  'use strict';

  function Workspace({
    initialContext = {},
    onNavigate,
    adapter
  }) {
    const A = window.CalibrationAPI,
      C = window.CalibrationControls;
    const {
      Button,
      ErrorBox,
      useRead
    } = C;
    const api = React.useMemo(() => adapter || A.create(), [adapter]);
    const partAdapter = React.useMemo(() => ({
      detail: (...args) => window.APSProcessAPI.create().detail(...args)
    }), []);
    const [part, setPart] = React.useState(null);
    const [input, setInput] = React.useState(() => A.initial(initialContext));
    const [widths, setWidths] = React.useState(initialContext.table_widths || {});
    const [selected, setSelected] = React.useState(initialContext.selected || null),
      [sampleRef, setSample] = React.useState(initialContext.sample_ref || null);
    const [revision, refresh] = React.useReducer(value => value + 1, 0),
      [format, setFormat] = React.useState('csv');
    const [notice, setNotice] = React.useState(''),
      [error, setError] = React.useState(null),
      [downloading, setDownloading] = React.useState(false);
    const [stale, setStale] = React.useState(false),
      downloadAbort = React.useRef(null);
    const identity = JSON.stringify(input) + ':' + revision;
    const request = useRead(signal => A.readView(api, input, signal), identity, api);
    const result = request.result,
      data = result && result.data;
    const bound = {
      ...input,
      snapshot_ref: result ? result.meta.snapshot_ref : input.snapshot_ref
    };
    const detail = useRead(async signal => A.validate(await api.detail(selected, bound, signal), bound, selected), selected + ':' + JSON.stringify(bound) + ':' + revision, api, !!(selected && result && data.capabilities.view === true && !stale));
    const isStale = failure => failure && failure.error && ['snapshot_stale', 'calibration_source_changed'].includes(failure.error.code);
    window.WorkbenchPageContext.useSnapshot(data ? {
      scope: Object.fromEntries(Object.entries(input).filter(([key]) => !['page', 'size', 'sort', 'direction', 'snapshot_ref'].includes(key))),
      table: {
        page: input.page,
        size: input.size,
        sort: input.sort,
        direction: input.direction
      },
      selected,
      sample_ref: sampleRef,
      table_widths: widths
    } : null, !!data && !request.busy && !request.error && !stale && (!selected || !!detail.result && !detail.busy && !detail.error));
    React.useEffect(() => {
      if (isStale(request.error) || isStale(detail.error)) setStale(true);
    }, [request.error, detail.error]);
    React.useEffect(() => () => {
      if (downloadAbort.current) downloadAbort.current.abort();
    }, [api]);
    function reload() {
      if (downloadAbort.current) downloadAbort.current.abort();
      setInput(old => ({
        ...old,
        snapshot_ref: undefined
      }));
      setError(null);
      setNotice('');
      setStale(false);
      refresh();
    }
    function change(patch) {
      setInput(old => A.input({
        ...old,
        ...patch,
        page: 1,
        snapshot_ref: undefined
      }));
      setSelected(null);
      setSample(null);
      setError(null);
      setNotice('');
    }
    function page(patch) {
      if (patch.size !== undefined) return change(patch);
      setInput(old => A.input({
        ...old,
        ...patch,
        snapshot_ref: result.meta.snapshot_ref
      }));
      setNotice('');
    }
    async function download() {
      const controller = new AbortController();
      downloadAbort.current = controller;
      setDownloading(true);
      setNotice('');
      setError(null);
      try {
        const receipt = await api.download(result, bound, format, controller.signal);
        if (!controller.signal.aborted) {
          if (!receipt || receipt.rows !== data.summary.total || receipt.snapshot_ref !== result.meta.snapshot_ref) throw A.failure('导出结果未核实，未报告成功。');
          setNotice('已核对快照和数量，导出全部筛选 ' + receipt.rows + ' 项。');
        }
      } catch (failure) {
        if (!controller.signal.aborted) {
          setError(failure);
          if (isStale(failure)) setStale(true);
        }
      } finally {
        if (downloadAbort.current === controller) {
          downloadAbort.current = null;
          setDownloading(false);
        }
      }
    }
    const disabled = request.busy || downloading || stale;
    const viewError = selected && data && data.capabilities.view !== true ? A.failure('查看权限尚未确认，暂不能读取样本来源。') : null;
    return /*#__PURE__*/React.createElement("section", {
      className: "calib-workbench calibration-live",
      "aria-label": "\u5DE5\u65F6\u5B9A\u989D\u6821\u51C6",
      "data-ready": !!data,
      "data-source": "production",
      "data-stale": stale
    }, /*#__PURE__*/React.createElement(C.Styles, null), /*#__PURE__*/React.createElement("header", {
      className: "ca-heading"
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("h2", null, "\u5DE5\u65F6\u5B9A\u989D\u6821\u51C6"), /*#__PURE__*/React.createElement("p", {
      className: "ca-muted"
    }, "\u6A21\u677F\u5B9A\u989D\u4E0E\u5B9E\u9645\u52A0\u5DE5\u8BB0\u5F55", result ? ' · 数据截至 ' + result.meta.as_of.replace('T', ' ') : '')), /*#__PURE__*/React.createElement("div", {
      className: "ca-actions"
    }, /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      "aria-label": "\u5237\u65B0\u6821\u51C6\u6570\u636E",
      busy: request.busy,
      disabled: downloading,
      onClick: reload
    }), window.CalibrationAdoptionAction && /*#__PURE__*/React.createElement(window.CalibrationAdoptionAction, {
      detail: detail.result && detail.result.data,
      stale: stale || detail.busy,
      onRefresh: reload
    }), typeof onNavigate === 'function' && /*#__PURE__*/React.createElement(Button, {
      icon: "arrow-right",
      disabled: !data || disabled,
      onClick: () => onNavigate('review', {
        returnTo: {
          view: 'calib',
          context: {
            scope: Object.fromEntries(Object.entries(input).filter(([key]) => !['page', 'size', 'sort', 'direction', 'snapshot_ref'].includes(key))),
            table: {
              page: input.page,
              size: input.size,
              sort: input.sort,
              direction: input.direction
            },
            selected,
            sample_ref: sampleRef,
            table_widths: widths
          }
        }
      })
    }, "\u6267\u884C\u590D\u76D8"))), /*#__PURE__*/React.createElement(C.Filters, {
      value: input,
      onChange: change,
      disabled: disabled
    }), input.part_ref && /*#__PURE__*/React.createElement("p", {
      className: "ca-muted"
    }, "\u5DF2\u9650\u5B9A\u96F6\u4EF6\u6765\u6E90 ", /*#__PURE__*/React.createElement(Button, {
      icon: "x",
      "aria-label": "\u6E05\u9664\u96F6\u4EF6\u9650\u5B9A",
      disabled: disabled,
      onClick: () => change({
        part_ref: null
      })
    })), /*#__PURE__*/React.createElement(ErrorBox, {
      error: request.error || error
    }), stale && /*#__PURE__*/React.createElement("p", {
      className: "ca-note",
      role: "alert"
    }, "\u524D\u540E\u5FEB\u7167\u4E0D\u4E00\u81F4\uFF0C\u8BF7\u660E\u786E\u5237\u65B0\u3002\u5DF2\u9009\u8BB0\u5F55\u548C\u6837\u672C\u6765\u6E90\u4FDD\u7559\uFF0C\u4E0D\u4F1A\u81EA\u52A8\u8DF3\u5230\u6700\u65B0\u8BB0\u5F55\u3002"), (stale || request.error) && /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      disabled: downloading,
      onClick: reload
    }, "\u660E\u786E\u5237\u65B0"), request.busy && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, "\u6B63\u5728\u8BFB\u53D6\u6821\u51C6\u8BB0\u5F55..."), notice && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, notice), data && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      className: "ca-metrics"
    }, [['模板工序', 'total'], ['偏差 > 20%', 'over_20_percent'], ['已有建议', 'suggested'], ['数据不足', 'insufficient_data']].map(([label, key]) => /*#__PURE__*/React.createElement("div", {
      className: "ca-metric",
      key: key
    }, /*#__PURE__*/React.createElement("span", null, label), /*#__PURE__*/React.createElement("strong", null, data.summary[key])))), data.source_constraints.map(item => /*#__PURE__*/React.createElement("p", {
      className: "ca-note",
      key: item.code
    }, item.message)), /*#__PURE__*/React.createElement("div", {
      className: "ca-tools"
    }, /*#__PURE__*/React.createElement("h3", null, "\u6821\u51C6\u660E\u7EC6"), /*#__PURE__*/React.createElement("label", null, "\u6392\u5E8F", /*#__PURE__*/React.createElement("select", {
      "aria-label": "\u6392\u5E8F\u5B57\u6BB5",
      disabled: disabled,
      value: input.sort,
      onChange: event => change({
        sort: event.target.value
      })
    }, Object.entries(A.sorts).map(([value, label]) => /*#__PURE__*/React.createElement("option", {
      key: value,
      value: value
    }, label)))), /*#__PURE__*/React.createElement("label", null, "\u987A\u5E8F", /*#__PURE__*/React.createElement("select", {
      "aria-label": "\u6392\u5E8F\u65B9\u5411",
      disabled: disabled,
      value: input.direction,
      onChange: event => change({
        direction: event.target.value
      })
    }, /*#__PURE__*/React.createElement("option", {
      value: "asc"
    }, "\u5347\u5E8F"), /*#__PURE__*/React.createElement("option", {
      value: "desc"
    }, "\u964D\u5E8F"))), /*#__PURE__*/React.createElement("div", {
      className: "ca-actions",
      style: {
        marginLeft: 'auto'
      }
    }, /*#__PURE__*/React.createElement("label", null, "\u683C\u5F0F", /*#__PURE__*/React.createElement("select", {
      "aria-label": "\u5BFC\u51FA\u683C\u5F0F",
      value: format,
      disabled: disabled,
      onChange: event => setFormat(event.target.value)
    }, /*#__PURE__*/React.createElement("option", {
      value: "csv"
    }, "CSV"), /*#__PURE__*/React.createElement("option", {
      value: "xlsx"
    }, "XLSX"))), /*#__PURE__*/React.createElement(Button, {
      transfer: "export",
      busy: downloading,
      disabled: disabled,
      reason: A.exportReason(data, format),
      onClick: download
    }, "\u5BFC\u51FA\u5168\u90E8\u7B5B\u9009"))), /*#__PURE__*/React.createElement(C.Table, {
      rows: data.items,
      selected: selected,
      disabled: disabled,
      canView: data.capabilities.view === true,
      onPart: setPart,
      onSelect: value => {
        setSelected(value);
        setSample(null);
      },
      scope: bound,
      adapter: api,
      widths: widths,
      total: data.summary.total,
      onResize: (key, value) => setWidths(old => ({
        ...old,
        [key]: value
      })),
      onSort: (sort, direction) => change({
        sort: direction ? sort : 'part_no',
        direction: direction || 'asc'
      }),
      onFilter: (key, rule) => {
        const filters = {
          ...input.column_filters
        };
        if (rule === null) delete filters[key];else filters[key] = rule;
        change({
          column_filters: filters
        });
      }
    }), /*#__PURE__*/React.createElement(C.Page, {
      page: data.page,
      onChange: page,
      disabled: disabled
    }), data.capabilities.export !== true && /*#__PURE__*/React.createElement("p", {
      className: "ca-note"
    }, "\u5BFC\u51FA\u6743\u9650\u5C1A\u672A\u786E\u8BA4\uFF0C\u6682\u4E0D\u80FD\u5BFC\u51FA\u3002"), /*#__PURE__*/React.createElement("p", {
      className: "ca-muted"
    }, C.writeReason)), selected && /*#__PURE__*/React.createElement(window.CalibrationDetail, {
      result: detail.result,
      busy: detail.busy,
      error: detail.error || viewError,
      stale: stale,
      selected: selected,
      sampleRef: sampleRef,
      onSample: setSample,
      onClose: () => {
        setSelected(null);
        setSample(null);
      },
      onRefresh: reload
    }), part && /*#__PURE__*/React.createElement(window.ProcessDetail, {
      adapter: partAdapter,
      partRef: part.part_ref,
      initialStage: "hours",
      templateOperationRef: part.template_operation_ref,
      navigationReadOnly: true,
      disabled: true,
      onClose: () => setPart(null)
    }));
  }
  function CalibrationWorkspace(props) {
    window.WorkbenchCaption.useCaption(null);
    try {
      window.CalibrationAPI.initial(props.initialContext || {});
    } catch (error) {
      return /*#__PURE__*/React.createElement("section", {
        className: "calibration-live"
      }, /*#__PURE__*/React.createElement(window.CalibrationControls.Styles, null), /*#__PURE__*/React.createElement("h2", null, "\u5DE5\u65F6\u5B9A\u989D\u6821\u51C6"), /*#__PURE__*/React.createElement(window.ResourceControls.ErrorBox, {
        error: error
      }));
    }
    return /*#__PURE__*/React.createElement(Workspace, {
      key: JSON.stringify(props.initialContext || {}),
      ...props
    });
  }
  window.CalibrationWorkspace = CalibrationWorkspace;
})();
