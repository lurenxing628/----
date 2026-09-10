(function () {
  'use strict';

  const A = window.RunCandidateAPI,
    B = window.RunBaselineAPI,
    Q = window.DashboardCandidateComparisonAPI,
    C = window.DashboardContract;
  const P = window.DashboardCandidatePanels,
    {
      Button,
      ErrorBox,
      Issues
    } = window.ResourceControls;
  function rangeFor(input) {
    const start = input && input.start_date + 'T00:00:00',
      raw = input && input.end_date + 'T00:00:00';
    C.check(A.time(start) && A.time(raw), '运行未提供有效的受理时间范围。');
    const end = new Date(Date.parse(raw + 'Z') + 86400000).toISOString().slice(0, 19);
    C.check(A.time(end) && start < end);
    return {
      range_start: start,
      range_end: end
    };
  }
  async function allCandidates(api, runRef, signal) {
    const first = await api.catalog(runRef, {
        size: 50
      }, signal),
      rows = first.data.candidates.slice();
    let page = 1,
      next = first;
    while (next.data.page.has_more) {
      next = await api.catalog(runRef, {
        page: ++page,
        size: 50,
        snapshot_ref: first.meta.snapshot_ref
      }, signal);
      C.check(next.data.candidate_count === first.data.candidate_count);
      rows.push(...next.data.candidates);
    }
    C.check(rows.length === first.data.candidate_count && new Set(rows.map(row => row.candidate_ref)).size === rows.length);
    return {
      ...first.data,
      candidates: rows
    };
  }
  function Candidates({
    catalog,
    initialContext = {},
    onState,
    selectedBatch,
    onSelectBatch,
    issueBatchRef = null
  }) {
    const api = React.useMemo(() => A.create(), []),
      baselineApi = React.useMemo(() => B.create(), []),
      comparisonApi = React.useMemo(() => Q.create(), []);
    const [choice, setChoice] = React.useState(() => Q.context(initialContext)),
      [revision, refresh] = React.useReducer(n => n + 1, 0);
    const [list, setList] = React.useState({
      run: null,
      data: null,
      error: null,
      loading: false
    });
    const [read, setRead] = React.useState({
      signature: null,
      data: null,
      error: null,
      loading: false
    });
    const [range, setRange] = React.useState({
        start: choice.range_start || '',
        end: choice.range_end || ''
      }),
      [rangeError, setRangeError] = React.useState(null);
    const [summary, setSummary] = React.useState(false),
      signature = JSON.stringify(choice);
    React.useEffect(() => {
      setRange({
        start: choice.range_start || '',
        end: choice.range_end || ''
      });
    }, [choice.range_start, choice.range_end]);
    React.useEffect(() => {
      const controller = new AbortController(),
        run = choice.run_ref;
      setList({
        run,
        data: null,
        error: null,
        loading: !!run
      });
      if (run) allCandidates(api, run, controller.signal).then(data => {
        if (!controller.signal.aborted) setList({
          run,
          data,
          error: null,
          loading: false
        });
      }).catch(error => {
        if (!controller.signal.aborted) setList({
          run,
          data: null,
          error,
          loading: false
        });
      });
      return () => controller.abort();
    }, [api, choice.run_ref, revision]);
    React.useEffect(() => {
      const controller = new AbortController();
      setSummary(false);
      setRead({
        signature,
        data: null,
        error: null,
        loading: !!choice.candidate_ref
      });
      if (!choice.candidate_ref) return () => controller.abort();
      const load = async () => {
        if (!choice.range_start || !choice.range_end) {
          const first = await api.workspace(choice.candidate_ref, {}, controller.signal);
          A.workspace(first, choice.candidate_ref, {}, choice.run_ref);
          if (!controller.signal.aborted) setChoice(previous => JSON.stringify(previous) === signature ? {
            ...previous,
            ...rangeFor(first.data.generation.input)
          } : previous);
          return;
        }
        const scope = {
          range_start: choice.range_start,
          range_end: choice.range_end,
          ...(choice.batch_ref ? {
            batch_ref: choice.batch_ref
          } : {})
        };
        const workspace = await api.workspace(choice.candidate_ref, scope, controller.signal);
        A.workspace(workspace, choice.candidate_ref, scope, choice.run_ref);
        const baseline = await baselineApi.read(workspace.data, controller.signal);
        const comparison = await comparisonApi.read(workspace.data, baseline.data, controller.signal);
        if (!controller.signal.aborted) setRead({
          signature,
          data: {
            workspace,
            baseline,
            comparison
          },
          error: null,
          loading: false
        });
      };
      load().catch(error => {
        if (!controller.signal.aborted) setRead({
          signature,
          data: null,
          error,
          loading: false
        });
      });
      return () => controller.abort();
    }, [api, baselineApi, comparisonApi, signature, revision]);
    const current = read.signature === signature ? read : null,
      result = current && current.data;
    const data = result && result.comparison.data,
      options = list.run === choice.run_ref && list.data;
    const caption = data ? {
      reference: data.candidate.candidate_ref,
      label: '比较方案',
      name: data.candidate.label || '候选名称未记录',
      status: data.baseline.available ? '持久候选 · 受理时正式基线对照' : '持久候选 · 无受理时正式基线'
    } : null;
    const captionKey = JSON.stringify(caption);
    React.useLayoutEffect(() => {
      if (onState) onState({
        context: choice,
        caption
      });
    }, [onState, signature, captionKey]);
    function changeRun(ref) {
      setRangeError(null);
      if (!ref) {
        setChoice({});
        return;
      }
      const run = catalog.runs.find(row => row.run_ref === ref);
      let bounds = {};
      if (run && run.scope_summary && run.scope_summary.start_date && run.scope_summary.end_date) {
        try {
          bounds = rangeFor(run.scope_summary);
        } catch (error) {
          setRangeError(error);
        }
      }
      setChoice({
        run_ref: ref,
        ...bounds,
        ...(issueBatchRef ? {
          batch_ref: issueBatchRef
        } : {})
      });
    }
    function applyRange(event) {
      event.preventDefault();
      try {
        const normalize = value => /^\d{4}-\d\d-\d\dT\d\d:\d\d$/.test(value) ? value + ':00' : value;
        const next = Q.context({
          ...choice,
          range_start: normalize(range.start),
          range_end: normalize(range.end)
        });
        setRangeError(null);
        setChoice(next);
      } catch (error) {
        setRangeError(error);
      }
    }
    return /*#__PURE__*/React.createElement("section", {
      "aria-label": "\u6301\u4E45\u5019\u9009\u540C\u8303\u56F4\u6BD4\u8F83",
      "data-dashboard-candidates": true,
      "data-comparison-ready": !!data
    }, /*#__PURE__*/React.createElement("div", {
      className: "dy-heading"
    }, /*#__PURE__*/React.createElement("h3", null, "\u540C\u4E00\u53D7\u7406\u8303\u56F4\u4E0B\u6BD4\u8F83"), /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      "aria-label": "\u91CD\u65B0\u8BFB\u53D6\u5019\u9009\u6BD4\u8F83",
      onClick: refresh
    })), /*#__PURE__*/React.createElement("label", {
      className: "dy-run-picker"
    }, "\u6392\u4EA7\u8FD0\u884C", /*#__PURE__*/React.createElement("select", {
      "aria-label": "\u9009\u62E9\u6392\u4EA7\u8FD0\u884C",
      value: choice.run_ref || '',
      onChange: event => changeRun(event.target.value)
    }, /*#__PURE__*/React.createElement("option", {
      value: ""
    }, "\u8BF7\u9009\u62E9\u8FD0\u884C"), choice.run_ref && !catalog.runs.some(row => row.run_ref === choice.run_ref) && /*#__PURE__*/React.createElement("option", {
      value: choice.run_ref
    }, "\u539F\u8FD0\u884C ", choice.run_ref), catalog.runs.map(run => /*#__PURE__*/React.createElement("option", {
      key: run.run_ref,
      value: run.run_ref
    }, run.accepted_at.replace('T', ' '), " \xB7 ", run.candidate_count, " \u4EFD\u5019\u9009 \xB7 ", run.run_ref.slice(0, 12))))), /*#__PURE__*/React.createElement(Issues, {
      issues: catalog.issues || []
    }), /*#__PURE__*/React.createElement(ErrorBox, {
      error: list.error
    }), /*#__PURE__*/React.createElement(ErrorBox, {
      error: rangeError || current && current.error
    }), issueBatchRef && /*#__PURE__*/React.createElement("div", {
      className: "dy-context"
    }, "\u539F\u95EE\u9898\u6279\u6B21\u5F15\u7528 ", issueBatchRef, " \xB7 \u4E0D\u501F\u7528\u5176\u4ED6\u6279\u6B21\u7ED3\u679C"), list.loading && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, "\u6B63\u5728\u8BFB\u53D6\u539F\u8FD0\u884C\u7684\u6301\u4E45\u5019\u9009\u76EE\u5F55\u3002"), options && /*#__PURE__*/React.createElement("fieldset", {
      className: "dy-candidate-options"
    }, /*#__PURE__*/React.createElement("legend", null, "\u5019\u9009\u65B9\u6848"), options.candidates.map(row => /*#__PURE__*/React.createElement("label", {
      key: row.candidate_ref,
      "data-candidate-choice": row.candidate_ref
    }, /*#__PURE__*/React.createElement("input", {
      type: "radio",
      name: "dashboard-candidate",
      value: row.candidate_ref,
      checked: choice.candidate_ref === row.candidate_ref,
      onChange: () => setChoice({
        ...choice,
        candidate_ref: row.candidate_ref
      })
    }), /*#__PURE__*/React.createElement("span", null, /*#__PURE__*/React.createElement("b", null, row.label || '候选名称未记录'), /*#__PURE__*/React.createElement("small", null, {
      completed: '计算完成',
      partial: '部分完成',
      failed: '失败',
      skipped: '已跳过'
    }[row.status], " \xB7 ", row.task_count, " \u9053\u5B89\u6392")))), !options.candidates.length && /*#__PURE__*/React.createElement("p", {
      className: "dy-empty"
    }, "\u539F\u8FD0\u884C\u5C1A\u65E0\u6301\u4E45\u5019\u9009\u7ED3\u679C\u3002")), choice.run_ref && /*#__PURE__*/React.createElement("form", {
      className: "dy-compare-range",
      onSubmit: applyRange
    }, /*#__PURE__*/React.createElement("label", null, "\u5171\u540C\u5F00\u59CB", /*#__PURE__*/React.createElement("input", {
      type: "datetime-local",
      step: "1",
      "aria-label": "\u5019\u9009\u6BD4\u8F83\u5171\u540C\u5F00\u59CB",
      value: range.start,
      onChange: event => setRange({
        ...range,
        start: event.target.value
      })
    })), /*#__PURE__*/React.createElement("label", null, "\u5171\u540C\u7ED3\u675F", /*#__PURE__*/React.createElement("input", {
      type: "datetime-local",
      step: "1",
      "aria-label": "\u5019\u9009\u6BD4\u8F83\u5171\u540C\u7ED3\u675F",
      value: range.end,
      onChange: event => setRange({
        ...range,
        end: event.target.value
      })
    })), /*#__PURE__*/React.createElement(Button, {
      icon: "check",
      type: "submit"
    }, "\u5E94\u7528\u8303\u56F4")), current && current.loading && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, "\u6B63\u5728\u6838\u5BF9\u6240\u9009\u5019\u9009\u3001\u53D7\u7406\u65F6\u57FA\u7EBF\u4E0E\u5171\u540C\u8303\u56F4\u3002"), data && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      className: "dy-context"
    }, /*#__PURE__*/React.createElement("span", null, data.time_scope.range_start.replace('T', ' '), " \u81F3 ", data.time_scope.range_end.replace('T', ' '), " \xB7 \u5DE6\u95ED\u53F3\u5F00"), /*#__PURE__*/React.createElement("span", null, data.batch_refs.length, " \u4E2A\u53D7\u7406\u65F6\u6279\u6B21 \xB7 \u5B8C\u5DE5\u4F9D\u636E\u4E3A\u5B8C\u6574\u5DE5\u5E8F")), !data.baseline.available && /*#__PURE__*/React.createElement("p", {
      className: "dy-note warning"
    }, "\u53D7\u7406\u65F6\u6CA1\u6709\u6B63\u5F0F\u57FA\u7EBF\uFF0C\u76F8\u5BF9\u53D8\u5316\u4FDD\u6301\u672A\u77E5\u3002"), /*#__PURE__*/React.createElement(P.Metrics, {
      data: data
    }), /*#__PURE__*/React.createElement(P.Batches, {
      data: data,
      selected: selectedBatch,
      onSelect: onSelectBatch
    }), /*#__PURE__*/React.createElement("div", {
      className: "dy-heading"
    }, /*#__PURE__*/React.createElement("h3", null, data.candidate.label || '候选名称未记录'), /*#__PURE__*/React.createElement(Button, {
      icon: "chart-gantt",
      onClick: () => setSummary(true)
    }, "\u67E5\u770B\u65B9\u6848\u6458\u8981")), /*#__PURE__*/React.createElement("details", {
      className: "dy-evidence"
    }, /*#__PURE__*/React.createElement("summary", null, "\u53D7\u7406\u65F6\u6392\u4EA7\u7EA6\u675F"), /*#__PURE__*/React.createElement("dl", {
      className: "dy-facts"
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u9F50\u5957\u68C0\u67E5"), /*#__PURE__*/React.createElement("dd", null, data.generation.input.ready_check ? '开启' : '关闭')), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u7F3A\u8D44\u6E90\u7B56\u7565"), /*#__PURE__*/React.createElement("dd", null, data.generation.input.missing_resource_policy === 'auto_assign' ? '按匹配规则自动分配' : '排除缺资源工序')), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u5DF2\u5F00\u5DE5\u7B56\u7565"), /*#__PURE__*/React.createElement("dd", null, "\u4FDD\u7559\u5DF2\u8BB0\u5F55\u5B9E\u9645\u53CA\u53D7\u4FDD\u62A4\u5B89\u6392")), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u8FD0\u884C\u5F15\u7528"), /*#__PURE__*/React.createElement("dd", null, data.generation.run_ref)))), summary && /*#__PURE__*/React.createElement(P.Summary, {
      data: data,
      onClose: () => setSummary(false)
    })));
  }
  window.DashboardCandidates = Candidates;
})();
