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
    planRef,
    initialContext = {},
    disabled = false,
    renderTrial,
    navigation
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
    const initialTaskRef = React.useRef(typeof initialContext.selected_task_ref === 'string' ? initialContext.selected_task_ref : null);
    const read = S.useQuery(async signal => {
      if (typeof adapter.workspace !== 'function') throw C.failure('暂时无法读取计划，请稍后重试。');
      P.workspaceScope(selection.plan_ref, scope);
      return P.workspace(await adapter.workspace(selection.plan_ref, scope, signal), selection.plan_ref, scope);
    }, [adapter, selection && selection.plan_ref, scope], !!selection && !paused);
    const result = read.result,
      data = result && result.data;
    const chosen = selected && selected.result === result ? selected : null;
    React.useEffect(() => {
      if (!data || read.loading || read.error) return;
      const target = relatedRef || initialTaskRef.current;
      // The saved task belongs to this session's first successful read only.
      initialTaskRef.current = null;
      if (!target) return;
      const task = data.tasks.find(row => row.task_ref === target);
      if (task) setSelected({
        task,
        before: false,
        result,
        ...(relatedRef ? {
          locate: true
        } : {})
      });else setRangeError(C.failure(relatedRef ? '此计划中未找到相关工序。' : '要恢复的工序不在当前范围内。'));
      if (relatedRef) setRelatedRef(null);
    }, [relatedRef, result, read.loading, read.error]);
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
      initialTaskRef.current = null;
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
      initialTaskRef.current = null;
      setSelected({
        task,
        before,
        result
      });
    }
    function selectRelated(ref) {
      initialTaskRef.current = null;
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
        initialTaskRef.current = null;
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
    const scopeCaption = !data ? '' : includesPlanEnd && data.plan_span.start === data.plan_span.end ? `计划时刻：${M.timeLabel(data.plan_span.start)}` : `计划时间范围：${M.timeLabel(data.time_scope.range_start)} → ${M.timeLabel(data.time_scope.range_end)}（${includesPlanEnd ? '包含末端零工时工序' : '不含结束时刻'}）`;
    window.WorkbenchCaption.useCaption(data && !read.loading && !read.error && !paused ? {
      reference: data.plan.plan_ref,
      label: '正式计划',
      name: data.plan.display_name,
      status: data.plan.is_current_official ? '当前正式' : data.plan.kind === 'official' ? '历史正式' : data.plan.kind === 'candidate' ? '候选方案' : '试调方案',
      ...(data.plan.kind === 'official' && data.plan.version !== null ? {
        version: '第 ' + data.plan.version + ' 版'
      } : {}),
      range: scopeCaption
    } : null);
    return /*#__PURE__*/React.createElement("div", {
      className: "plana plan-workspace",
      "data-plan-workspace": true
    }, /*#__PURE__*/React.createElement(window.PlanLayout, null), /*#__PURE__*/React.createElement("section", {
      className: "plan-scope wb-surface",
      "aria-label": "\u65B9\u6848\u4E0E\u8303\u56F4"
    }, /*#__PURE__*/React.createElement("div", {
      className: "wb-surface-row plan-scope-heading"
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("h3", null, "\u65B9\u6848\u4E0E\u8303\u56F4"), data && /*#__PURE__*/React.createElement(Identity, {
      plan: data.plan
    })), navigation), /*#__PURE__*/React.createElement(Catalog, {
      adapter: adapter,
      selectedRef: selection && selection.plan_ref,
      onSelect: choose,
      autoSelect: !planRef && Object.keys(initialContext).length === 0,
      disabled: disabled,
      actions: /*#__PURE__*/React.createElement(React.Fragment, null, typeof renderTrial === 'function' && renderTrial({
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
      }))
    }), /*#__PURE__*/React.createElement("div", {
      className: "wb-surface-row plan-read-heading"
    }, /*#__PURE__*/React.createElement("div", {
      className: "plan-scope-meta"
    }, data && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("span", {
      className: "plan-scope-caption"
    }, scopeCaption, data.scope.range_start !== null && ' · 显示所选时间段内的工序安排'), /*#__PURE__*/React.createElement("span", null, "\u8BFB\u53D6\u4E8E ", M.timeLabel(result.meta.as_of), query.trim() && ` · 甘特搜索 ${matches.length} / ${data.task_count} 道；分析和导出共 ${data.task_count} 道`))), /*#__PURE__*/React.createElement("div", {
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
      className: "plan-range wb-surface-body wb-surface-divider",
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
        initialTaskRef.current = null;
        setScope({});
        setRange({
          start: '',
          end: ''
        });
        setRangeError(null);
        setPaused(false);
        read.reload();
      }
    }, "\u5B8C\u6574\u8BA1\u5212")), (rangeError || read.error || result && result.warnings.length > 0 || !data || paused) && /*#__PURE__*/React.createElement("div", {
      className: "wb-surface-body plan-read-state"
    }, /*#__PURE__*/React.createElement(ErrorBox, {
      error: rangeError
    }), /*#__PURE__*/React.createElement(ErrorBox, {
      error: read.error
    }), result && /*#__PURE__*/React.createElement(Issues, {
      issues: result.warnings
    }), !data && !read.error && /*#__PURE__*/React.createElement(window.WorkbenchControls.EmptyState, {
      kind: read.loading ? 'loading' : 'empty',
      title: read.loading ? '正在读取所选计划、工序安排和分析结果…' : paused ? '计划读取已取消。' : '请在计划列表里选一个可查看的计划。'
    }), (read.error || paused) && /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      onClick: refresh
    }, "\u5237\u65B0\u91CD\u8BD5")), data && /*#__PURE__*/React.createElement("div", {
      className: "statline wb-metrics",
      style: {
        '--wb-columns': 4
      }
    }, [[data.task_count, '范围内安排', 'primary'], [risks.length, '关联批次', 'primary'], [risks.filter(row => row.risk === 'overdue').length, '已确认预计超期', 'warn'], [risks.filter(row => row.risk === 'unknown').length, '交付风险暂无数据', 'warn']].map(([value, label, tone]) => /*#__PURE__*/React.createElement("div", {
      className: "stat wb-metric",
      key: label,
      "data-tone": tone === 'warn' && value === 0 ? 'neutral' : tone
    }, /*#__PURE__*/React.createElement("span", {
      className: "sl wb-metric-label"
    }, label), /*#__PURE__*/React.createElement("span", {
      className: "sv wb-metric-value"
    }, value))))), data && /*#__PURE__*/React.createElement("div", {
      className: "plan-main"
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement(window.PlanGantt, {
      key: 'gantt:' + result.meta.snapshot_ref,
      data: data,
      asOf: result.meta.as_of,
      selected: chosen,
      onSelect: selectTask,
      query: query,
      onQuery: setQuery,
      disabled: disabled
    }), /*#__PURE__*/React.createElement(ProjectionTables, {
      key: 'risk:' + result.meta.snapshot_ref,
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
    })), /*#__PURE__*/React.createElement(TaskDetail, {
      data: data,
      selected: chosen,
      onSelect: selectTask,
      onRelated: selectRelated,
      renderTrial: renderTrial,
      scope: scope,
      query: query,
      disabled: !ready || read.loading || !!read.error
    })));
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
