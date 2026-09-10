(function () {
  'use strict';

  const C = window.PreflightContract,
    {
      Button,
      ErrorBox,
      Rules,
      Metrics,
      Reasons,
      Styles
    } = window.PreflightControls;
  const labels = {
    eligible: '资料有效',
    auto_assign_required: '自动分配待补',
    skipped: '本次跳过',
    blocked: '资料阻塞',
    protected: '执行保护'
  };
  function contextState(value) {
    try {
      return {
        value: C.initial(value),
        error: null
      };
    } catch (error) {
      return {
        value: C.defaults(),
        error
      };
    }
  }
  function Details({
    data
  }) {
    const [page, setPage] = React.useState(1),
      pages = Math.max(1, Math.ceil(data.tasks.length / 100));
    return /*#__PURE__*/React.createElement("details", {
      className: "pf-detail"
    }, /*#__PURE__*/React.createElement("summary", null, "\u9010\u5DE5\u5E8F\u68C0\u67E5 \xB7 ", data.tasks.length, " \u9053"), /*#__PURE__*/React.createElement("div", {
      className: "pf-results"
    }, /*#__PURE__*/React.createElement("table", {
      "aria-label": "\u6392\u4EA7\u524D\u68C0\u67E5\u660E\u7EC6"
    }, /*#__PURE__*/React.createElement("colgroup", null, /*#__PURE__*/React.createElement("col", {
      style: {
        width: '18%'
      }
    }), /*#__PURE__*/React.createElement("col", {
      style: {
        width: '20%'
      }
    }), /*#__PURE__*/React.createElement("col", {
      style: {
        width: '15%'
      }
    }), /*#__PURE__*/React.createElement("col", null)), /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", null, "\u6279\u6B21"), /*#__PURE__*/React.createElement("th", null, "\u5DE5\u5E8F"), /*#__PURE__*/React.createElement("th", null, "\u68C0\u67E5\u7ED3\u679C"), /*#__PURE__*/React.createElement("th", null, "\u539F\u56E0"))), /*#__PURE__*/React.createElement("tbody", null, data.tasks.slice((page - 1) * 100, page * 100).map(row => /*#__PURE__*/React.createElement("tr", {
      key: row.operation_ref
    }, /*#__PURE__*/React.createElement("td", null, row.batch_id), /*#__PURE__*/React.createElement("td", null, row.sequence, " \xB7 ", row.label, row.piece_id ? ' · ' + row.piece_id : ''), /*#__PURE__*/React.createElement("td", null, labels[row.status]), /*#__PURE__*/React.createElement("td", null, row.issues.map((item, index) => /*#__PURE__*/React.createElement("p", {
      key: index
    }, item.message, item.predecessor_sequence ? ' 前序：' + item.predecessor_sequence : '')), row.execution.first_actual_start && /*#__PURE__*/React.createElement("p", null, "\u5B9E\u9645\u5F00\u5DE5\uFF1A", row.execution.first_actual_start.replace('T', ' ')), row.execution.confirmed_finish && /*#__PURE__*/React.createElement("p", null, "\u786E\u8BA4\u5B8C\u5DE5\uFF1A", row.execution.confirmed_finish.replace('T', ' ')), row.status === 'protected' && /*#__PURE__*/React.createElement("p", null, "\u5269\u4F59\u6570\u91CF\uFF1A", row.execution.remaining_quantity === null ? '未知' : row.execution.remaining_quantity))))))), pages > 1 && /*#__PURE__*/React.createElement("div", {
      className: "pf-tools"
    }, /*#__PURE__*/React.createElement("span", null, "\u7B2C ", page, " / ", pages, " \u9875 \xB7 \u6BCF\u9875100\u9053"), /*#__PURE__*/React.createElement(Button, {
      icon: "chevron-left",
      "aria-label": "\u68C0\u67E5\u660E\u7EC6\u4E0A\u4E00\u9875",
      disabled: page <= 1,
      onClick: () => setPage(old => old - 1)
    }), /*#__PURE__*/React.createElement(Button, {
      icon: "chevron-right",
      "aria-label": "\u68C0\u67E5\u660E\u7EC6\u4E0B\u4E00\u9875",
      disabled: page >= pages,
      onClick: () => setPage(old => old + 1)
    })));
  }
  function NoRoutes({
    rows
  }) {
    const [page, setPage] = React.useState(1),
      pages = Math.max(1, Math.ceil(rows.length / 100));
    return /*#__PURE__*/React.createElement("details", {
      className: "pf-detail"
    }, /*#__PURE__*/React.createElement("summary", null, "\u672A\u751F\u6210\u5DE5\u827A \xB7 ", rows.length, " \u6279"), /*#__PURE__*/React.createElement("div", {
      className: "pf-results"
    }, rows.slice((page - 1) * 100, page * 100).map(row => /*#__PURE__*/React.createElement("p", {
      key: row.batch_ref
    }, row.batch_id, " \xB7 \u5C1A\u672A\u751F\u6210\u5DE5\u827A"))), pages > 1 && /*#__PURE__*/React.createElement("div", {
      className: "pf-tools"
    }, /*#__PURE__*/React.createElement("span", null, "\u7B2C ", page, " / ", pages, " \u9875 \xB7 \u6BCF\u9875100\u6279"), /*#__PURE__*/React.createElement(Button, {
      icon: "chevron-left",
      "aria-label": "\u672A\u751F\u6210\u5DE5\u827A\u4E0A\u4E00\u9875",
      disabled: page <= 1,
      onClick: () => setPage(old => old - 1)
    }), /*#__PURE__*/React.createElement(Button, {
      icon: "chevron-right",
      "aria-label": "\u672A\u751F\u6210\u5DE5\u827A\u4E0B\u4E00\u9875",
      disabled: page >= pages,
      onClick: () => setPage(old => old + 1)
    })));
  }
  function PreflightWorkspace({
    onNavigate,
    initialContext,
    renderRunPanel
  }) {
    const adapter = React.useMemo(() => window.PreflightAPI.create(), []);
    const [initial, setInitial] = React.useState(() => contextState(initialContext));
    const [value, setValue] = React.useState(initial.value),
      [error, setError] = React.useState(null),
      [result, setResult] = React.useState(null);
    const [busy, setBusy] = React.useState(false),
      [expanded, setExpanded] = React.useState(false);
    const serial = React.useRef(0),
      active = React.useRef(null),
      context = React.useRef(initialContext);
    const remembered = React.useMemo(() => {
      try {
        return C.input(value);
      } catch (_) {
        return null;
      }
    }, [value]);
    window.WorkbenchPageContext.useSnapshot(remembered, !initial.error && remembered !== null);
    function invalidate() {
      serial.current++;
      if (active.current) active.current.abort();
      setResult(null);
      setError(null);
      setBusy(false);
    }
    function change(patch) {
      invalidate();
      setValue(old => ({
        ...old,
        ...patch
      }));
    }
    React.useEffect(() => {
      if (context.current !== initialContext) {
        context.current = initialContext;
        const next = contextState(initialContext);
        invalidate();
        setInitial(next);
        setValue(next.value);
      }
    }, [initialContext]);
    React.useEffect(() => () => {
      serial.current++;
      if (active.current) active.current.abort();
    }, []);
    async function check() {
      if (busy || initial.error) return;
      invalidate();
      const id = ++serial.current,
        controller = new AbortController();
      active.current = controller;
      setBusy(true);
      try {
        const input = C.input(value),
          response = await adapter.preflight(input, controller.signal);
        C.result(response, input);
        if (serial.current === id) setResult(response);
      } catch (problem) {
        if (serial.current === id) setError(problem);
      } finally {
        if (serial.current === id) setBusy(false);
      }
    }
    const data = result && result.data,
      counts = data && data.counts;
    const runBlocked = !data || data.write_context.capabilities['scheduling.run'] !== true || typeof adapter.run !== 'function';
    const runReason = data && data.run_blocked_reasons[0].message || '候选排产运行服务尚未接入，不能开始排产。';
    function navigate(kind) {
      if (!onNavigate || !data) return;
      const rows = kind === 'unready' ? data.unready_batches : kind === 'resources' ? data.tasks.filter(row => row.issues.some(item => ['machine_missing', 'operator_missing', 'operator_skill_missing', 'machine_authorization_missing'].includes(item.code))) : data.tasks.filter(row => row.status === 'blocked').concat(data.no_route_batches);
      const ids = Array.from(new Set(rows.map(row => row.batch_id)));
      invalidate();
      onNavigate('batches', {
        focus: kind === 'unready' ? 'unready' : 'gaps',
        batchIds: ids,
        return_to: 'run'
      });
    }
    const checks = [['设备 / 人员', counts ? counts.missing_resource_tasks + ' 道缺资源；' + (value.missing_resource_policy === 'auto_assign' ? counts.auto_assign_required + ' 道待自动分配。' : '按本次策略暂不排入。') : '尚未检查设备与人员。', 'resources', '去补齐'], ['齐套状态', counts ? counts.unready_batches + ' 批未齐套；' + (value.ready_check ? '本次执行齐套检查。' : '本次关闭齐套检查。') : '尚未读取齐套事实。', 'unready', '查看批次'], ['工时 / 工艺 / 外协', counts ? counts.blocked_tasks + ' 道阻塞，' + counts.no_route_batches + ' 批未生成工艺。' : '尚未检查必填资料。', 'gaps', '处理缺项'], ['日历与产能', '未验证，不能据此认定夜班、停机及产能约束通过。', null, null]];
    return /*#__PURE__*/React.createElement("div", {
      className: "plana preflight-workspace",
      "data-preflight-workspace": true
    }, /*#__PURE__*/React.createElement(Styles, null), /*#__PURE__*/React.createElement("div", {
      className: "pf-heading"
    }, /*#__PURE__*/React.createElement("h2", null, "\u6392\u4EA7\u524D\u68C0\u67E5"), /*#__PURE__*/React.createElement("span", {
      className: "pf-muted"
    }, "\u5F53\u524D\u751F\u4EA7\u8D44\u6599 \xB7 \u5355\u6B21\u6392\u4EA7\u8303\u56F4")), /*#__PURE__*/React.createElement(ErrorBox, {
      error: initial.error
    }), initial.error && /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      onClick: () => {
        const next = contextState(undefined);
        invalidate();
        setInitial(next);
        setValue(next.value);
      }
    }, "\u91CD\u65B0\u9009\u62E9\u8303\u56F4"), /*#__PURE__*/React.createElement("div", {
      className: "pf-window"
    }, /*#__PURE__*/React.createElement("strong", null, "\u8BA1\u5212\u7A97\u53E3"), /*#__PURE__*/React.createElement("label", null, "\u5F00\u59CB\u65E5\u671F", /*#__PURE__*/React.createElement("input", {
      type: "date",
      "aria-label": "\u8BA1\u5212\u5F00\u59CB\u65E5\u671F",
      min: "1900-01-01",
      max: "9999-12-30",
      value: value.start_date,
      disabled: !!initial.error,
      onChange: event => change({
        start_date: event.target.value
      })
    })), /*#__PURE__*/React.createElement("label", null, "\u7ED3\u675F\u65E5\u671F", /*#__PURE__*/React.createElement("input", {
      type: "date",
      "aria-label": "\u8BA1\u5212\u7ED3\u675F\u65E5\u671F",
      min: "1900-01-01",
      max: "9999-12-30",
      value: value.end_date,
      disabled: !!initial.error,
      onChange: event => change({
        end_date: event.target.value
      })
    })), /*#__PURE__*/React.createElement("span", null, "\u5DF2\u9009 ", value.batch_refs.length, " \u6279"), /*#__PURE__*/React.createElement(Button, {
      icon: expanded ? 'chevron-up' : 'chevron-down',
      disabled: !!initial.error,
      "aria-expanded": expanded,
      onClick: () => setExpanded(old => !old)
    }, expanded ? '收起范围' : '选择批次')), expanded && !initial.error && /*#__PURE__*/React.createElement(window.PreflightBatchPicker, {
      adapter: adapter,
      selected: value.batch_refs,
      onChange: batch_refs => change({
        batch_refs
      }),
      disabled: busy
    }), /*#__PURE__*/React.createElement(Metrics, {
      counts: counts
    }), /*#__PURE__*/React.createElement("div", {
      className: "pf-body"
    }, /*#__PURE__*/React.createElement(Rules, {
      value: value,
      onChange: change,
      disabled: !!initial.error
    }), /*#__PURE__*/React.createElement("section", {
      "aria-labelledby": "pf-check-title"
    }, /*#__PURE__*/React.createElement("h3", {
      id: "pf-check-title"
    }, "\u5C31\u7EEA\u68C0\u67E5"), /*#__PURE__*/React.createElement("div", {
      className: "pf-rows"
    }, checks.map(([title, description, kind, action]) => /*#__PURE__*/React.createElement("div", {
      className: "pf-check",
      key: title
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("strong", null, title), /*#__PURE__*/React.createElement("p", null, description)), kind && /*#__PURE__*/React.createElement(Button, {
      disabled: !data || !onNavigate || busy || !(kind === 'resources' ? counts.missing_resource_tasks : kind === 'unready' ? counts.unready_batches : counts.blocked_tasks + counts.no_route_batches),
      onClick: () => navigate(kind)
    }, action)))))), /*#__PURE__*/React.createElement(ErrorBox, {
      error: error
    }), busy && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, "\u6B63\u5728\u8BFB\u53D6\u6279\u6B21\u3001\u8D44\u6E90\u53CA\u6267\u884C\u4E8B\u5B9E\uFF1B\u672A\u521B\u5EFA\u8FD0\u884C\u3002"), data && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("p", {
      className: "pf-muted",
      role: "status"
    }, "\u68C0\u67E5\u65F6\u95F4\uFF1A", result.meta.as_of.replace('T', ' '), " \xB7 \u8F93\u5165\u6709\u6548\u81F3 ", data.input_expires_at.replace('T', ' '), " \xB7 \u65E5\u5386\u672A\u9A8C\u8BC1"), /*#__PURE__*/React.createElement(Details, {
      key: data.input_ref,
      data: data
    }), !!data.no_route_batches.length && /*#__PURE__*/React.createElement(NoRoutes, {
      key: data.input_ref,
      rows: data.no_route_batches
    }), /*#__PURE__*/React.createElement(Reasons, {
      data: data
    })), /*#__PURE__*/React.createElement("div", {
      className: "pf-footer"
    }, /*#__PURE__*/React.createElement("span", {
      className: "pf-muted"
    }, data ? '预检不生成版本、不写入业务或审计数据。' : renderRunPanel ? '请先选择批次与计划窗口，再检查排产资料。' : '尚未检查；候选排产运行服务尚未接入。'), /*#__PURE__*/React.createElement("div", {
      className: "pf-tools"
    }, /*#__PURE__*/React.createElement(Button, {
      icon: "search",
      busy: busy,
      disabled: !!initial.error,
      onClick: check
    }, data ? '重新检查' : '开始排产检查'), !renderRunPanel && /*#__PURE__*/React.createElement(Button, {
      icon: "play",
      className: "btn primary",
      disabled: runBlocked,
      reason: runReason
    }, "\u5F00\u59CB\u6392\u4EA7"))), renderRunPanel && renderRunPanel(data));
  }
  window.PreflightWorkspace = PreflightWorkspace;
})();
