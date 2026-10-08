(function () {
  'use strict';

  const C = window.PreflightContract,
    {
      Button,
      ErrorBox,
      Rules,
      Metrics,
      Reasons,
      HoldSummary
    } = window.PreflightControls;
  const labels = {
    eligible: '资料有效',
    auto_assign_required: '自动分配待补',
    skipped: '本次跳过',
    blocked: '缺资料',
    protected: '已开工保护'
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
    }, /*#__PURE__*/React.createElement("summary", null, "\u68C0\u67E5\u660E\u7EC6 \xB7 ", data.tasks.length, " \u9053"), /*#__PURE__*/React.createElement("div", {
      className: "pf-results wb-table-frame",
      "data-sticky-head": true,
      "data-sticky-actions": true
    }, /*#__PURE__*/React.createElement("table", {
      className: "wb-table",
      "aria-label": "\u6392\u4EA7\u68C0\u67E5\u660E\u7EC6"
    }, /*#__PURE__*/React.createElement("caption", {
      className: "wb-visually-hidden"
    }, "\u6392\u4EA7\u68C0\u67E5\u660E\u7EC6"), /*#__PURE__*/React.createElement("colgroup", null, ['batch', 'operation', 'status', 'reason'].map(key => /*#__PURE__*/React.createElement("col", {
      key: key,
      className: 'pf-col-' + key
    }))), /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u6279\u6B21"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u5DE5\u5E8F"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u68C0\u67E5\u7ED3\u679C"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u539F\u56E0"))), /*#__PURE__*/React.createElement("tbody", null, data.tasks.slice((page - 1) * 100, page * 100).map(row => /*#__PURE__*/React.createElement("tr", {
      key: row.operation_ref
    }, /*#__PURE__*/React.createElement("td", null, row.batch_id), /*#__PURE__*/React.createElement("td", null, row.sequence, " \xB7 ", row.label, row.piece_id ? ' · ' + row.piece_id : ''), /*#__PURE__*/React.createElement("td", null, labels[row.status]), /*#__PURE__*/React.createElement("td", null, row.issues.map((item, index) => /*#__PURE__*/React.createElement("p", {
      key: index
    }, item.message, item.predecessor_sequence ? ' 前序：' + item.predecessor_sequence : '')), row.material_ready_date && /*#__PURE__*/React.createElement("p", null, "\u7528\u6599\u53EF\u7528\u65E5\u671F\uFF1A", window.WorkbenchFormat.date(row.material_ready_date)), row.execution.first_actual_start && /*#__PURE__*/React.createElement("p", null, "\u5B9E\u9645\u5F00\u5DE5\uFF1A", window.WorkbenchFormat.dateTime(row.execution.first_actual_start)), row.execution.confirmed_finish && /*#__PURE__*/React.createElement("p", null, "\u786E\u8BA4\u5B8C\u5DE5\uFF1A", window.WorkbenchFormat.dateTime(row.execution.confirmed_finish)), row.status === 'protected' && /*#__PURE__*/React.createElement("p", null, "\u5269\u4F59\u6570\u91CF\uFF1A", row.execution.remaining_quantity === null ? '未知' : row.execution.remaining_quantity), row.held && /*#__PURE__*/React.createElement("p", null, row.held.basis === 'locked' ? '正式计划里已锁定' : '因不重排时段', "\uFF0C\u4FDD\u6301\u539F\u5B89\u6392\uFF1A", window.WorkbenchFormat.dateTime(row.held.start), " \u81F3 ", window.WorkbenchFormat.dateTime(row.held.end)))))))), pages > 1 && /*#__PURE__*/React.createElement(window.WorkbenchListControls.Pager, {
      page: page,
      pages: pages,
      total: data.tasks.length,
      size: 100,
      unit: "\u9053",
      label: "\u68C0\u67E5\u660E\u7EC6",
      onPage: setPage
    }));
  }
  function NoRoutes({
    rows
  }) {
    const [page, setPage] = React.useState(1),
      pages = Math.max(1, Math.ceil(rows.length / 100));
    return /*#__PURE__*/React.createElement("details", {
      className: "pf-detail"
    }, /*#__PURE__*/React.createElement("summary", null, "\u672A\u751F\u6210\u5DE5\u827A \xB7 ", rows.length, " \u6279"), /*#__PURE__*/React.createElement("div", {
      className: "pf-results wb-table-frame",
      "data-sticky-head": true,
      "data-sticky-actions": true
    }, rows.slice((page - 1) * 100, page * 100).map(row => /*#__PURE__*/React.createElement("p", {
      key: row.batch_ref
    }, row.batch_id, " \xB7 \u5C1A\u672A\u751F\u6210\u5DE5\u827A"))), pages > 1 && /*#__PURE__*/React.createElement(window.WorkbenchListControls.Pager, {
      page: page,
      pages: pages,
      total: rows.length,
      size: 100,
      unit: "\u6279",
      label: "\u672A\u751F\u6210\u5DE5\u827A",
      onPage: setPage
    }));
  }
  function PreflightWorkspace({
    onNavigate,
    initialContext,
    renderRunPanel,
    actions
  }) {
    const adapter = React.useMemo(() => window.PreflightAPI.create(), []);
    const [initial, setInitial] = React.useState(() => contextState(initialContext));
    const [value, setValue] = React.useState(initial.value),
      [error, setError] = React.useState(null),
      [result, setResult] = React.useState(null);
    const [busy, setBusy] = React.useState(false),
      [expanded, setExpanded] = React.useState(false);
    const [splitExpanded, setSplitExpanded] = React.useState(false),
      [splitBusy, setSplitBusy] = React.useState(false);
    const [needsRecheck, setNeedsRecheck] = React.useState(false);
    // 上次检查按交付设置推算出的不重排时段（从开始日期起算）；开始日期没变时继续用它填显示值。
    const [holdDefault, setHoldDefault] = React.useState(null);
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
    const onSplitActivity = React.useCallback(inProgress => {
      setSplitBusy(inProgress);
      if (inProgress) invalidate();
    }, []);
    function change(patch) {
      if (result || busy) setNeedsRecheck(true);
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
      if (busy || splitBusy || initial.error) return;
      invalidate();
      const id = ++serial.current,
        controller = new AbortController();
      active.current = controller;
      setBusy(true);
      try {
        const input = C.input(value),
          response = await adapter.preflight(input, controller.signal);
        C.result(response, input);
        if (serial.current === id) {
          setResult(response);
          setNeedsRecheck(false);
          rememberHold(input, response.data.effective_config);
        }
      } catch (problem) {
        if (serial.current === id) setError(problem);
      } finally {
        if (serial.current === id) setBusy(false);
      }
    }
    function rememberHold(input, config) {
      if (config.hold_window_source === 'default') setHoldDefault({
        start_date: input.start_date,
        hold_window: config.hold_window
      });
    }
    const effectiveHold = holdDefault && holdDefault.start_date === value.start_date ? holdDefault : null;
    const data = result && result.data,
      counts = data && data.counts,
      currentStep = window.RunPresentation.step(remembered, data);
    const runBlocked = !data || data.write_context.capabilities['scheduling.run'] !== true || typeof adapter.run !== 'function';
    const runReason = data && data.run_blocked_reasons[0].message || window.WorkbenchTerms.outcomes.unavailable;
    const inputDisabled = !!initial.error || busy || splitBusy;
    function inspectMaterials() {
      if (inputDisabled || !value.ready_check) return;
      if (splitExpanded) setSplitExpanded(false);else {
        invalidate();
        setSplitExpanded(true);
      }
    }
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
    const checks = [['设备 / 人员', counts ? counts.missing_resource_tasks + ' 道缺资源；' + (value.missing_resource_policy === 'auto_assign' ? counts.auto_assign_required + ' 道待自动分配。' : '按本次规则暂不排入。') : '尚未检查设备与人员。', 'resources', '去补齐'], ['齐套状态', counts ? counts.unready_batches + ' 批未齐套；' + (value.ready_check ? '本次执行齐套检查。' : '本次关闭齐套检查。') : '尚未读取齐套情况。', 'unready', '查看批次'], ['工时 / 工艺 / 外协', counts ? counts.blocked_tasks + ' 道缺资料，' + counts.no_route_batches + ' 批未生成工艺。' : '尚未检查必填资料。', 'gaps', '处理缺项'], ['班表与产能', '本次不检查。夜班、停机和产能是否够用，请到「工作日历」核对。', null, null]];
    return /*#__PURE__*/React.createElement("div", {
      className: "plana preflight-workspace",
      "data-preflight-workspace": true
    }, /*#__PURE__*/React.createElement("div", {
      className: "pf-heading"
    }, /*#__PURE__*/React.createElement("h2", {
      className: "wb-page-title"
    }, "\u6267\u884C\u6392\u4EA7"), /*#__PURE__*/React.createElement("span", {
      className: "pf-muted wb-page-context"
    }, "\u5F53\u524D\u751F\u4EA7\u8D44\u6599 \xB7 \u5355\u6B21\u6392\u4EA7\u8303\u56F4"), actions && /*#__PURE__*/React.createElement("div", {
      className: "pf-tools"
    }, actions)), /*#__PURE__*/React.createElement("section", {
      className: "pf-scope",
      "aria-label": "\u6392\u4EA7\u8303\u56F4"
    }, /*#__PURE__*/React.createElement("ol", {
      className: "pf-stepper",
      "aria-label": "\u6267\u884C\u6392\u4EA7\u6B65\u9AA4"
    }, ['选批次和日期', '检查', '计算'].map((label, index) => /*#__PURE__*/React.createElement("li", {
      key: label,
      "aria-current": currentStep === index + 1 ? 'step' : undefined,
      "data-step-state": currentStep > index + 1 ? 'complete' : currentStep === index + 1 ? 'current' : 'upcoming'
    }, /*#__PURE__*/React.createElement("span", {
      "aria-hidden": "true"
    }, index + 1), label))), /*#__PURE__*/React.createElement(ErrorBox, {
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
    }, /*#__PURE__*/React.createElement("strong", null, "\u6392\u4EA7\u65E5\u671F\u8303\u56F4"), /*#__PURE__*/React.createElement("label", null, "\u5F00\u59CB\u65E5\u671F", /*#__PURE__*/React.createElement("input", {
      type: "date",
      "aria-label": "\u8BA1\u5212\u5F00\u59CB\u65E5\u671F",
      min: "1900-01-01",
      max: "9999-12-30",
      value: value.start_date,
      disabled: inputDisabled,
      onChange: event => change({
        start_date: event.target.value
      })
    })), /*#__PURE__*/React.createElement("label", null, "\u7ED3\u675F\u65E5\u671F", /*#__PURE__*/React.createElement("input", {
      type: "date",
      "aria-label": "\u8BA1\u5212\u7ED3\u675F\u65E5\u671F",
      min: "1900-01-01",
      max: "9999-12-30",
      value: value.end_date,
      disabled: inputDisabled,
      onChange: event => change({
        end_date: event.target.value
      })
    })), /*#__PURE__*/React.createElement("span", null, "\u5DF2\u9009 ", value.batch_refs.length, " \u6279"), /*#__PURE__*/React.createElement(Button, {
      icon: expanded ? 'chevron-up' : 'chevron-down',
      className: currentStep === 1 ? 'btn primary' : 'btn',
      disabled: inputDisabled,
      "aria-expanded": expanded,
      onClick: () => setExpanded(old => !old)
    }, expanded ? '收起范围' : '选择批次')), expanded && !initial.error && /*#__PURE__*/React.createElement(window.PreflightBatchPicker, {
      adapter: adapter,
      selected: value.batch_refs,
      onChange: batch_refs => change({
        batch_refs
      }),
      disabled: inputDisabled
    }), /*#__PURE__*/React.createElement(Metrics, {
      counts: counts
    })), /*#__PURE__*/React.createElement("section", {
      className: "pf-review",
      "aria-label": "\u6392\u4EA7\u89C4\u5219\u4E0E\u68C0\u67E5"
    }, /*#__PURE__*/React.createElement("div", {
      className: "pf-body"
    }, /*#__PURE__*/React.createElement(Rules, {
      value: value,
      effective: effectiveHold,
      onChange: change,
      disabled: inputDisabled,
      onInspectMaterials: window.BatchSplitPanel && inspectMaterials,
      splitExpanded: splitExpanded,
      materialPanel: splitExpanded && window.BatchSplitPanel && /*#__PURE__*/React.createElement(window.BatchSplitPanel, {
        refs: value.batch_refs,
        day: value.start_date,
        disabled: !!initial.error || busy || !value.ready_check,
        onActivityChange: onSplitActivity,
        onCommitted: (child, source) => change({
          batch_refs: value.batch_refs.map(ref => ref === source ? child : ref)
        })
      })
    }), /*#__PURE__*/React.createElement("section", {
      "aria-labelledby": "pf-check-title"
    }, /*#__PURE__*/React.createElement("h3", {
      id: "pf-check-title"
    }, "\u6392\u4EA7\u68C0\u67E5"), /*#__PURE__*/React.createElement("div", {
      className: "pf-rows"
    }, checks.map(([title, description, kind, action]) => /*#__PURE__*/React.createElement("div", {
      className: "pf-check",
      key: title
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("strong", null, title), /*#__PURE__*/React.createElement("p", null, description)), kind && /*#__PURE__*/React.createElement(Button, {
      disabled: !data || !onNavigate || busy || !(kind === 'resources' ? counts.missing_resource_tasks : kind === 'unready' ? counts.unready_batches : counts.blocked_tasks + counts.no_route_batches),
      onClick: () => navigate(kind)
    }, action)))))), /*#__PURE__*/React.createElement(ErrorBox, {
      error: error
    }), needsRecheck && /*#__PURE__*/React.createElement("p", {
      className: "pf-recheck",
      role: "status"
    }, "\u6392\u4EA7\u53C2\u6570\u5DF2\u53D8\u5316\uFF0C\u8BF7\u91CD\u65B0\u68C0\u67E5\u540E\u518D\u5F00\u59CB\u8BA1\u7B97\u3002"), busy && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, "\u6B63\u5728\u8BFB\u53D6\u6279\u6B21\u3001\u8BBE\u5907\u4EBA\u5458\u548C\u62A5\u5DE5\u8BB0\u5F55\uFF0C\u8FD8\u6CA1\u5F00\u59CB\u6392\u4EA7\u3002"), data && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("p", {
      className: "pf-muted",
      role: "status"
    }, "\u68C0\u67E5\u65F6\u95F4\uFF1A", window.WorkbenchFormat.dateTime(result.meta.as_of), " \xB7 \u7ED3\u679C\u6709\u6548\u81F3 ", window.WorkbenchFormat.dateTime(data.input_expires_at), " \xB7 \u73ED\u8868\u672A\u6838\u5BF9"), /*#__PURE__*/React.createElement(HoldSummary, {
      key: 'hold-' + data.input_ref,
      data: data
    }), /*#__PURE__*/React.createElement(Details, {
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
    }, data ? '排产检查不生成版本、不写入业务或审计数据。' : renderRunPanel ? '请先选择批次和排产日期范围，再点「开始排产检查」。' : window.WorkbenchTerms.outcomes.unavailable), /*#__PURE__*/React.createElement("div", {
      className: "pf-tools"
    }, /*#__PURE__*/React.createElement(Button, {
      icon: "search",
      className: currentStep === 2 ? 'btn primary' : 'btn',
      busy: busy,
      disabled: !!initial.error || splitBusy,
      reason: !initial.error && !value.batch_refs.length ? '请先选择要排产的批次。' : '',
      reasonDisplay: "tooltip",
      onClick: check
    }, data ? '重新检查' : '开始排产检查'), !renderRunPanel && /*#__PURE__*/React.createElement(Button, {
      icon: "play",
      className: currentStep === 3 ? 'btn primary' : 'btn',
      disabled: runBlocked,
      reason: runReason
    }, "\u5F00\u59CB\u6392\u4EA7")))), renderRunPanel && renderRunPanel(data));
  }
  window.PreflightWorkspace = PreflightWorkspace;
})();
