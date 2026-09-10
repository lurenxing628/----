(function () {
  'use strict';

  const C = window.APSResourceContract,
    P = window.APSPlanContract,
    S = window.APSResourceSession;
  const {
      Button,
      ErrorBox,
      Issues
    } = window.ResourceControls,
    {
      Catalog,
      Identity
    } = window.PlanCatalogUI;
  const M = window.PlanGanttModel,
    {
      TaskDetail,
      ProjectionTables,
      Conflicts
    } = window.PlanDetailsUI;
  const adapterIds = new WeakMap();
  let nextAdapter = 0;
  function adapterId(adapter) {
    if (!adapterIds.has(adapter)) adapterIds.set(adapter, ++nextAdapter);
    return adapterIds.get(adapter);
  }
  function WorkspaceSession({
    adapter,
    view,
    onNavigate,
    planRef,
    initialContext = {},
    disabled = false,
    renderTrial
  }) {
    const [selection, setSelection] = React.useState(() => planRef || initialContext.plan_ref ? {
      plan_ref: planRef || initialContext.plan_ref,
      display_name: '指定计划'
    } : null);
    const [scope, setScope] = React.useState(() => {
      const result = {};
      for (const key of ['range_start', 'range_end', 'snapshot_ref']) if (initialContext[key] !== undefined) result[key] = initialContext[key];
      return result;
    });
    const [range, setRange] = React.useState({
      start: scope.range_start || '',
      end: scope.range_end || ''
    });
    const [rangeOpen, setRangeOpen] = React.useState(false),
      [rangeError, setRangeError] = React.useState(null),
      [paused, setPaused] = React.useState(false);
    const [query, setQuery] = React.useState(typeof initialContext.query === 'string' ? initialContext.query : ''),
      [selected, setSelected] = React.useState(null);
    const [relatedRef, setRelatedRef] = React.useState(null);
    const read = S.useQuery(async signal => {
      if (typeof adapter.workspace !== 'function') throw C.failure('暂时无法读取计划，请稍后重试。');
      P.workspaceScope(selection.plan_ref, scope);
      return P.workspace(await adapter.workspace(selection.plan_ref, scope, signal), selection.plan_ref, scope);
    }, [adapter, selection && selection.plan_ref, scope], !!selection && !paused);
    const result = read.result,
      data = result && result.data;
    const chosen = selected && selected.result === result ? selected : null;
    React.useEffect(() => {
      if (!relatedRef || !data || read.loading || read.error) return;
      const task = data.tasks.find(row => row.task_ref === relatedRef);
      if (task) setSelected({
        task,
        before: false,
        result,
        locate: true
      });else setRangeError(C.failure('同一完整计划中未找到该关系任务，未定位到替代任务。'));
      setRelatedRef(null);
    }, [relatedRef, result, read.loading, read.error]);
    React.useEffect(() => {
      if (!data || selected || typeof initialContext.selected_task_ref !== 'string') return;
      const task = data.tasks.find(row => row.task_ref === initialContext.selected_task_ref);
      if (task) setSelected({
        task,
        before: false,
        result
      });
    }, [result, selected]);
    const remembered = {
      ...initialContext,
      ...(selection ? {
        plan_ref: selection.plan_ref
      } : {}),
      query
    };
    for (const key of ['range_start', 'range_end', 'snapshot_ref', 'selected_task_ref']) delete remembered[key];
    Object.assign(remembered, scope, chosen ? {
      selected_task_ref: chosen.task.task_ref
    } : {});
    window.WorkbenchPageContext.useSnapshot(remembered, !!data && !read.loading && !read.error && !paused);
    function choose(plan) {
      setSelection(plan);
      setScope({});
      setRange({
        start: '',
        end: ''
      });
      setRangeError(null);
      setPaused(false);
      setQuery('');
      setSelected(null);
      setRelatedRef(null);
      read.reload();
    }
    function refresh() {
      const next = {
        ...scope
      };
      delete next.snapshot_ref;
      setScope(next);
      setPaused(false);
      setSelected(null);
      read.reload();
    }
    function selectTask(task, before = false) {
      setSelected({
        task,
        before,
        result
      });
    }
    function selectRelated(ref) {
      const task = data.tasks.find(row => row.task_ref === ref);
      setQuery('');
      setRangeError(null);
      if (task) setSelected({
        task,
        before: false,
        result,
        locate: true
      });else {
        setRelatedRef(ref);
        setSelected(null);
        setScope({});
        setRange({
          start: '',
          end: ''
        });
        setPaused(false);
        read.reload();
      }
    }
    function applyRange(event) {
      event.preventDefault();
      if (!selection || disabled) return;
      try {
        const seconds = value => value && value.length === 16 ? value + ':00' : value;
        const next = P.workspaceScope(selection.plan_ref, {
          range_start: seconds(range.start),
          range_end: seconds(range.end)
        });
        setScope(next);
        setRangeError(null);
        setPaused(false);
        setSelected(null);
        read.reload();
      } catch (error) {
        setRangeError(error);
      }
    }
    const matches = React.useMemo(() => {
      if (!data) return [];
      const labels = M.names(data),
        needle = query.trim().toLocaleLowerCase();
      return data.tasks.filter(task => !needle || M.searchText(task, labels).includes(needle));
    }, [data, query]);
    const risks = data && data.projections.delivery_risks.items;
    const ready = !!data && !disabled;
    const includesPlanEnd = data && data.scope.range_start === null && data.plan_span.end_inclusive === true;
    const scopeCaption = !data ? '' : includesPlanEnd && data.plan_span.start === data.plan_span.end ? `计划时间点：${M.timeLabel(data.plan_span.start)}` : `计划时间范围：${M.timeLabel(data.time_scope.range_start)} → ${M.timeLabel(data.time_scope.range_end)}（${includesPlanEnd ? '包含末端计划点' : '不含结束时刻'}）`;
    window.WorkbenchCaption.useCaption(data && !read.loading && !read.error && !paused ? {
      reference: data.plan.plan_ref,
      label: '当前方案',
      name: data.plan.display_name,
      status: data.plan.is_current_official ? '当前正式' : data.plan.kind === 'official' ? '历史正式' : data.plan.kind === 'candidate' ? '候选预览' : '场景预览',
      ...(data.plan.kind === 'official' && data.plan.version !== null ? {
        version: '正式 v' + data.plan.version
      } : {}),
      range: scopeCaption
    } : null);
    return /*#__PURE__*/React.createElement("div", {
      className: "plana plan-workspace",
      "data-plan-workspace": true
    }, /*#__PURE__*/React.createElement(window.PlanLayout, null), /*#__PURE__*/React.createElement("div", {
      className: "plan-heading"
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("h2", null, view === 'gantt' ? '设备 / 人员 / 批次甘特' : view === 'delay' ? '交付风险' : '选择排产方案'), /*#__PURE__*/React.createElement("div", {
      className: "plan-muted"
    }, data ? data.plan.display_name : selection ? selection.display_name : '尚未选择计划', data && /*#__PURE__*/React.createElement(React.Fragment, null, " \xB7 ", /*#__PURE__*/React.createElement(Identity, {
      plan: data.plan
    })))), /*#__PURE__*/React.createElement("div", {
      className: "plan-actions"
    }, onNavigate && /*#__PURE__*/React.createElement(Button, {
      icon: "arrow-right",
      disabled: !selection,
      onClick: () => onNavigate(view === 'gantt' ? 'analysis' : 'gantt', {
        plan_ref: selection.plan_ref,
        ...scope,
        ...(result ? {
          snapshot_ref: result.meta.snapshot_ref
        } : {})
      })
    }, view === 'gantt' ? '选择方案' : '查看甘特'), onNavigate && /*#__PURE__*/React.createElement(Button, {
      icon: "circle-alert",
      disabled: !selection,
      onClick: () => onNavigate(view === 'delay' ? 'analysis' : 'delay', remembered)
    }, view === 'delay' ? '返回方案' : '交付风险'), typeof renderTrial === 'function' && renderTrial({
      planRef: selection && selection.plan_ref,
      scope,
      query,
      disabled: !ready || read.loading
    }), /*#__PURE__*/React.createElement(window.PlanExportUI, {
      key: result ? result.meta.snapshot_ref : 'unavailable',
      adapter: adapter,
      result: result,
      query: query,
      matched: matches.length,
      disabled: !ready
    }))), /*#__PURE__*/React.createElement(Catalog, {
      adapter: adapter,
      selectedRef: selection && selection.plan_ref,
      onSelect: choose,
      disabled: disabled
    }), /*#__PURE__*/React.createElement("div", {
      className: "plan-heading"
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("h3", null, "\u8BA1\u5212\u5DE5\u4F5C\u533A"), data && /*#__PURE__*/React.createElement("div", {
      className: "plan-muted"
    }, "\u8BFB\u53D6\u4E8E ", M.timeLabel(result.meta.as_of), " \xB7 \u5DE5\u5382\u672C\u5730\u65F6\u95F4")), /*#__PURE__*/React.createElement("div", {
      className: "plan-actions"
    }, /*#__PURE__*/React.createElement(Button, {
      icon: "calendar-days",
      "aria-expanded": rangeOpen,
      onClick: () => setRangeOpen(!rangeOpen),
      disabled: !selection
    }, "\u8BFB\u53D6\u8303\u56F4"), /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      className: "btn plan-icon",
      "aria-label": "\u5237\u65B0\u6240\u9009\u8BA1\u5212",
      disabled: !selection || disabled,
      busy: read.loading,
      onClick: refresh
    }), read.loading && /*#__PURE__*/React.createElement(Button, {
      icon: "x",
      "aria-label": "\u53D6\u6D88\u8BA1\u5212\u8BFB\u53D6",
      onClick: () => setPaused(true)
    }, "\u53D6\u6D88\u8BFB\u53D6"))), rangeOpen && /*#__PURE__*/React.createElement("form", {
      className: "plan-range",
      onSubmit: applyRange
    }, /*#__PURE__*/React.createElement("label", {
      className: "field"
    }, /*#__PURE__*/React.createElement("span", null, "\u5F00\u59CB\uFF08\u5305\u542B\uFF09"), /*#__PURE__*/React.createElement("input", {
      type: "datetime-local",
      step: "1",
      "aria-label": "\u8BFB\u53D6\u5F00\u59CB\u65F6\u95F4",
      value: range.start,
      onChange: event => setRange({
        ...range,
        start: event.target.value
      })
    })), /*#__PURE__*/React.createElement("label", {
      className: "field"
    }, /*#__PURE__*/React.createElement("span", null, "\u7ED3\u675F\uFF08\u4E0D\u542B\uFF09"), /*#__PURE__*/React.createElement("input", {
      type: "datetime-local",
      step: "1",
      "aria-label": "\u8BFB\u53D6\u7ED3\u675F\u65F6\u95F4",
      value: range.end,
      onChange: event => setRange({
        ...range,
        end: event.target.value
      })
    })), /*#__PURE__*/React.createElement(Button, {
      type: "submit",
      icon: "check",
      disabled: disabled || read.loading
    }, "\u5E94\u7528\u8303\u56F4"), /*#__PURE__*/React.createElement(Button, {
      icon: "chart-gantt",
      disabled: disabled || read.loading,
      onClick: () => {
        setScope({});
        setRange({
          start: '',
          end: ''
        });
        setRangeError(null);
        setPaused(false);
        read.reload();
      }
    }, "\u5B8C\u6574\u8BA1\u5212")), /*#__PURE__*/React.createElement(ErrorBox, {
      error: rangeError
    }), /*#__PURE__*/React.createElement(ErrorBox, {
      error: read.error
    }), result && /*#__PURE__*/React.createElement(Issues, {
      issues: result.warnings
    }), !data && /*#__PURE__*/React.createElement("div", {
      className: "plan-empty",
      role: "status"
    }, read.loading ? '正在读取所选计划、工序安排和分析结果…' : paused ? '计划读取已取消，未显示上次读取的内容。' : read.error ? '所选计划未读取成功，没有替换成其他计划。' : '从目录中选择一个可查看的计划。'), (read.error || paused) && /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      onClick: refresh
    }, "\u91CD\u65B0\u8BFB\u53D6\u6240\u9009\u8BA1\u5212"), data && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      className: "statline wb-metrics",
      style: {
        '--wb-columns': 4,
        marginBottom: 12
      }
    }, [[data.task_count, '范围内安排', 'primary'], [risks.length, '关联批次', 'primary'], [risks.filter(row => row.risk === 'overdue').length, '已核实预计超期', 'warn'], [risks.filter(row => row.risk === 'unknown').length, '交付风险待核实', 'warn']].map(([value, label, tone]) => /*#__PURE__*/React.createElement("div", {
      className: "stat wb-metric",
      key: label,
      "data-tone": tone === 'warn' && value === 0 ? 'neutral' : tone
    }, /*#__PURE__*/React.createElement("span", {
      className: "sl wb-metric-label"
    }, label), /*#__PURE__*/React.createElement("span", {
      className: "sv wb-metric-value"
    }, value)))), /*#__PURE__*/React.createElement("div", {
      className: "plan-note",
      style: {
        marginBottom: 10
      }
    }, scopeCaption, data.scope.range_start !== null && /*#__PURE__*/React.createElement("span", null, " \xB7 \u53EA\u5217\u51FA\u4E0E\u6B64\u65F6\u95F4\u6BB5\u6709\u91CD\u53E0\u7684\u5DE5\u5E8F\u5B89\u6392\uFF0C\u6BCF\u9053\u5B89\u6392\u7684\u8D77\u6B62\u65F6\u95F4\u5B8C\u6574\u4FDD\u7559\uFF0C\u4E0D\u4EE3\u8868\u6574\u4EFD\u8BA1\u5212"), query.trim() && /*#__PURE__*/React.createElement("span", null, " \xB7 \u641C\u7D22\u627E\u5230 ", matches.length, " / ", data.task_count, " \u9053\u5DE5\u5E8F\u5B89\u6392\uFF0C\u53EA\u5F71\u54CD\u7518\u7279\u56FE\u663E\u793A\uFF1B\u5206\u6790\u8868\u548C\u5BFC\u51FA\u4ECD\u5305\u542B\u6B64\u65F6\u95F4\u8303\u56F4\u5185\u7684\u5168\u90E8 ", data.task_count, " \u9053\u5B89\u6392")), /*#__PURE__*/React.createElement("div", {
      className: "plan-main"
    }, /*#__PURE__*/React.createElement("div", null, view === 'delay' && /*#__PURE__*/React.createElement(ProjectionTables, {
      key: 'risk-first:' + result.meta.snapshot_ref,
      data: data,
      onResource: setQuery,
      onBatch: batch => {
        setQuery(batch);
        const task = data.tasks.find(row => row.batch_id === batch);
        if (task) selectTask(task);
      }
    }), view === 'delay' && /*#__PURE__*/React.createElement(Conflicts, {
      key: 'conflicts:' + result.meta.snapshot_ref,
      data: data
    }), /*#__PURE__*/React.createElement(window.PlanGantt, {
      key: 'gantt:' + result.meta.snapshot_ref,
      data: data,
      selected: chosen,
      onSelect: selectTask,
      query: query,
      onQuery: setQuery,
      disabled: disabled
    }), view !== 'delay' && /*#__PURE__*/React.createElement(ProjectionTables, {
      key: 'risk-last:' + result.meta.snapshot_ref,
      data: data,
      onResource: setQuery,
      onBatch: batch => {
        setQuery(batch);
        const task = data.tasks.find(row => row.batch_id === batch);
        if (task) selectTask(task);
      }
    })), /*#__PURE__*/React.createElement(TaskDetail, {
      data: data,
      selected: chosen,
      onSelect: selectTask,
      onRelated: selectRelated,
      renderTrial: renderTrial,
      scope: scope,
      query: query,
      disabled: !ready || read.loading || !!read.error
    }))));
  }
  function PlanWorkspace(props) {
    const adapter = React.useMemo(() => props.adapter || (window.APSPlanAPI ? window.APSPlanAPI.create() : {}), [props.adapter]);
    const context = props.initialContext || {};
    const navigation = [props.planRef || context.plan_ref, context.range_start, context.range_end, context.snapshot_ref];
    return /*#__PURE__*/React.createElement(WorkspaceSession, {
      key: adapterId(adapter) + ':' + JSON.stringify(navigation),
      ...props,
      adapter: adapter
    });
  }
  window.PlanWorkspace = PlanWorkspace;
})();
