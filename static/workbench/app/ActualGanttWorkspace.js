(function () {
  'use strict';

  const M = window.ActualGanttModel,
    C = window.ActualGanttContract,
    W = window.ActualGanttWindow;
  const {
    Button,
    ErrorBox,
    Modal
  } = window.ResourceControls;
  const {
    Styles,
    Toolbar,
    Range,
    Chain,
    describe
  } = window.ActualGanttControls;
  const sessions = new Map();
  function savedView(value) {
    if (value === undefined) return null;
    const object = item => item !== null && typeof item === 'object' && !Array.isArray(item);
    const reference = item => item === null || typeof item === 'string' && /^[0-9a-f]{48}$/.test(item);
    const valid = object(value) && object(value.view) && object(value.position) && Number.isFinite(value.zoom) && value.zoom >= 1 && value.zoom <= 1024;
    if (!valid) throw new Error('实际甘特查看状态无效，未改选其他对象。');
    const v = value.view;
    if (!Object.prototype.hasOwnProperty.call(M.views, v.mode) || !Object.prototype.hasOwnProperty.call(M.lateLabels, v.late) || typeof v.query !== 'string' || v.query.length > 200 || !reference(v.selected) || !reference(v.report) || !['onlySelected', 'details', 'chain'].every(key => typeof v[key] === 'boolean') || !object(v.collapsed) || !Object.values(v.collapsed).every(item => typeof item === 'boolean') || v.chainLines !== undefined && typeof v.chainLines !== 'boolean' || value.position.viewport !== undefined && (!Number.isFinite(value.position.viewport) || value.position.viewport < 80) || (value.position.centerAt !== undefined || value.position.windowSpan !== undefined) && (!Number.isFinite(value.position.centerAt) || !Number.isFinite(value.position.windowSpan) || value.position.windowSpan <= 0) || !['left', 'top'].every(key => Number.isFinite(value.position[key]) && value.position[key] >= 0)) throw new Error('实际甘特查看状态无效，未改选其他对象。');
    return value;
  }
  function initial(context) {
    const input = {
        ...(context.scope || {})
      },
      scope = {};
    for (const key of ['source', 'range_start', 'range_end', 'plan_finish_date_from', 'plan_finish_date_to', 'resource_type', 'resource_ref', 'batch_ids']) if (context[key] !== undefined && input[key] === undefined) input[key] = context[key];
    const allowed = ['plan_ref', 'source', 'range_start', 'range_end', 'plan_finish_date_from', 'plan_finish_date_to', 'resource_type', 'resource_ref', 'batch_ids', 'query', 'focus', 'as_of', 'snapshot_ref', 'kind', 'baseline_ref'];
    let issue = Object.keys(input).some(key => !allowed.includes(key)) ? '来源范围含未知条件，未忽略筛选。' : null;
    if (input.baseline_ref && input.baseline_ref !== (context.plan_ref || input.plan_ref)) issue = '现场实际甘特以所选计划为基线，未替换为另一个基线版本。';
    if (input.query !== undefined && (typeof input.query !== 'string' || input.query.length > 200)) issue = '来源搜索条件无效。';
    if (context.return_to && !['gantt', 'field', 'analysis', 'reports', 'review', 'dashboard'].includes(context.return_to.view)) issue = '返回来源不是已登记的工作台页面。';
    if (context.report_ref !== undefined && !C.ref(context.report_ref)) issue = '来源报工引用无效，未改指其他记录。';
    if (context.report_ref !== undefined && !C.ref(context.task_ref || context.entity_ref)) issue = '来源报工必须绑定明确任务，未猜测其他任务。';
    for (const key of ['plan_ref', 'source', 'range_start', 'range_end', 'plan_finish_date_from', 'plan_finish_date_to', 'resource_type', 'resource_ref', 'batch_ids']) if (input[key] !== undefined && input[key] !== null && input[key] !== '') scope[key] = input[key];
    if (context.plan_ref) scope.plan_ref = context.plan_ref;
    let persisted = null;
    try {
      persisted = savedView(context.actual_view);
    } catch (failure) {
      issue = failure.message;
    }
    return {
      scope,
      issue,
      persisted,
      query: typeof input.query === 'string' ? input.query : typeof context.query === 'string' ? context.query : '',
      selected: context.task_ref || context.entity_ref || null,
      report: context.report_ref || null
    };
  }
  function Content({
    onNavigate,
    initialContext = {},
    adapter: supplied
  }) {
    const seed = React.useMemo(() => initial(initialContext), []),
      key = JSON.stringify(initialContext),
      saved = sessions.get(key);
    const api = React.useMemo(() => supplied || window.ActualGanttAPI.create(), [supplied]);
    const [scope, setScope] = React.useState(saved ? saved.scope : seed.scope),
      [refresh, setRefresh] = React.useState(0);
    const [result, setResult] = React.useState(null),
      [loading, setLoading] = React.useState(false),
      [error, setError] = React.useState(null);
    const [view, setView] = React.useState(saved ? saved.view : seed.persisted ? seed.persisted.view : {
      mode: seed.scope.resource_type || 'machine',
      query: seed.query,
      selected: seed.selected,
      report: seed.report,
      late: 'all',
      collapsed: {},
      onlySelected: false,
      details: !!seed.report,
      chain: false
    });
    const [zoom, setZoom] = React.useState(saved ? saved.zoom : seed.persisted ? seed.persisted.zoom : 1),
      [position, setPosition] = React.useState({
        left: 0,
        top: 0,
        width: 1000,
        height: 480
      });
    const [hover, setHover] = React.useState(null),
      [exporting, setExporting] = React.useState(false),
      [exportBusy, setExportBusy] = React.useState(false);
    const [chainTarget, setChainTarget] = React.useState(null);
    const [relatedChain, setRelatedChain] = React.useState(null);
    const [exportError, setExportError] = React.useState(null),
      [restore, setRestore] = React.useState(saved ? saved.position : seed.persisted ? seed.persisted.position : null);
    const board = React.useRef(null),
      frame = React.useRef(null),
      pending = React.useRef(!saved && !seed.persisted && seed.report && seed.selected ? {
        task: seed.selected
      } : null),
      downloadController = React.useRef(null);
    const defaultWindowApplied = React.useRef(!!saved || !!seed.persisted);
    const measuredWidth = React.useRef(null),
      zoomRef = React.useRef(zoom),
      restoreRef = React.useRef(restore);
    zoomRef.current = zoom;
    restoreRef.current = restore;
    const {
      labelWidth,
      viewport
    } = W.dimensions(position.width);
    const patch = change => setView(previous => ({
      ...previous,
      ...change
    }));
    React.useEffect(() => {
      const controller = new AbortController();
      let active = true;
      setLoading(true);
      setResult(null);
      setError(null);
      (async () => {
        try {
          if (seed.issue) throw window.APSResourceContract.failure(seed.issue);
          let input = scope;
          if (input.source && input.source !== 'production') throw window.APSResourceContract.failure('现场实际甘特只读取生产数据，未将演示范围替换为生产范围。');
          if (!input.plan_ref) {
            if (Object.keys(input).some(k => k !== 'source')) throw window.APSResourceContract.failure('来源范围缺少明确计划，未自动扩大范围。');
            const catalog = await window.APSPlanAPI.create().catalog({
              collection: 'history',
              size: 20
            }, controller.signal);
            const current = catalog.data.plans.filter(p => p.is_current_official && p.capabilities.view);
            if (current.length !== 1) throw window.APSResourceContract.failure('没有唯一可读取的当前正式计划，请先选择计划。');
            if (active) setScope({
              plan_ref: current[0].plan_ref
            });
            return;
          }
          input = C.scope(input);
          const response = C.workspace(await api.load(input, controller.signal), input);
          if (initialContext.operation_ref && seed.selected) {
            const task = response.data.items.find(item => item.task.task_ref === seed.selected);
            if (task && task.task.operation_ref !== initialContext.operation_ref) throw window.APSResourceContract.failure('来源工序与所选计划任务不一致，未改指其他安排。');
          }
          if (active) setResult(response);
        } catch (failure) {
          if (active) setError(failure);
        } finally {
          if (active) setLoading(false);
        }
      })();
      return () => {
        active = false;
        controller.abort();
      };
    }, [api, scope, refresh]);
    React.useEffect(() => () => {
      if (downloadController.current) downloadController.current.abort();
      cancelAnimationFrame(frame.current);
    }, []);
    const data = result && result.data;
    const captionPlan = !loading && !error && data && data.plan;
    const captionStatus = captionPlan && {
      official: captionPlan.is_current_official ? '当前正式采用' : '历史正式方案',
      candidate: window.WorkbenchTerms.candidate,
      scenario: '试调场景'
    }[captionPlan.kind];
    window.WorkbenchCaption.useCaption(captionStatus ? {
      reference: captionPlan.plan_ref,
      label: '对照计划',
      name: captionPlan.display_name,
      status: captionStatus,
      version: captionPlan.kind === 'official' && Number.isSafeInteger(captionPlan.version) ? '正式 v' + captionPlan.version : undefined,
      range: data.scope.plan_finish_date_from && data.scope.plan_finish_date_to ? '计划完工 ' + data.scope.plan_finish_date_from + ' 至 ' + data.scope.plan_finish_date_to : undefined
    } : null);
    const model = React.useMemo(() => data ? M.layout(data, view, result.meta.as_of) : null, [data, view, result]);
    const snapshotPosition = model ? W.capture(position, viewport, model, zoom) : null;
    window.WorkbenchPageContext.useSnapshot(data ? {
      plan_ref: data.plan.plan_ref,
      scope: data.scope,
      task_ref: view.selected,
      actual_view: {
        view,
        zoom,
        position: snapshotPosition
      },
      return_to: initialContext.return_to
    } : null, !!data && !loading && !error && !seed.issue && !restore);
    const measure = () => {
      const node = board.current;
      if (!node) return;
      const previousWidth = measuredWidth.current;
      if (previousWidth !== null && previousWidth !== node.clientWidth && defaultWindowApplied.current && !restoreRef.current && !pending.current) {
        const previousViewport = W.dimensions(previousWidth).viewport;
        pending.current = {
          center: (node.scrollLeft + previousViewport / 2) / (previousViewport * zoomRef.current)
        };
      }
      measuredWidth.current = node.clientWidth;
      setPosition({
        left: node.scrollLeft,
        top: node.scrollTop,
        width: node.clientWidth,
        height: node.clientHeight
      });
    };
    React.useLayoutEffect(() => {
      if (!board.current) return;
      measure();
      const resize = new ResizeObserver(measure);
      resize.observe(board.current);
      return () => resize.disconnect();
    }, [data]);
    const width = viewport * zoom;
    React.useLayoutEffect(() => {
      const node = board.current;
      if (!node || !model) return;
      if (!defaultWindowApplied.current) {
        defaultWindowApplied.current = true;
        const next = W.initial(data, model);
        if (!pending.current) pending.current = {
          center: next.center
        };
        setZoom(next.zoom);
        if (next.zoom !== zoom) return;
      }
      // Restore only after the measured width is rendered; the initial width can clamp scrollLeft.
      if (restore && position.width !== node.clientWidth) {
        measure();
        return;
      }
      if (restore) {
        const nextZoom = W.restoreZoom(restore, model, zoom);
        if (nextZoom !== zoom) {
          setZoom(nextZoom);
          return;
        }
        node.scrollLeft = W.restoreLeft(restore, viewport, model, zoom);
        node.scrollTop = restore.top;
        setRestore(null);
      }
      if (pending.current) {
        if (pending.current.task) {
          const reportRow = model.reportLocations.get(view.report);
          const row = reportRow && reportRow.item.task.task_ref === pending.current.task ? reportRow : model.locations.get(pending.current.task);
          if (row) {
            const report = row.item.execution && row.item.execution.reports.find(r => r.report_ref === view.report),
              at = report && report.actual_start || row.item.task.start;
            node.scrollTop = Math.max(0, row.top - node.clientHeight / 3);
            node.scrollLeft = (M.instant(at) - model.start) / (model.end - model.start) * width - viewport / 3;
          }
        } else node.scrollLeft = pending.current.center * width - viewport / 2;
        pending.current = null;
      }
      measure();
    }, [width, model, restore, position.width]);
    React.useEffect(() => {
      if (snapshotPosition && !restore) sessions.set(key, {
        scope,
        view,
        zoom,
        position: snapshotPosition
      });
    }, [key, scope, view, zoom, position, model, restore]);
    React.useEffect(() => {
      setHover(null);
      setChainTarget(null);
    }, [view, position.top, position.left]);
    function zoomTo(next) {
      pending.current = {
        center: W.anchor(data, model, view.selected, view.report)
      };
      setZoom(Math.max(1, Math.min(1024, next)));
    }
    function pan(left) {
      if (board.current) {
        board.current.scrollLeft = Math.max(0, left);
        measure();
      }
    }
    function locate(taskRef = view.selected) {
      if (!model || !model.items.some(item => item.task.task_ref === taskRef)) return;
      const collapsed = {
        ...view.collapsed
      };
      model.groups.filter(g => g.members.has(taskRef)).forEach(g => delete collapsed[g.id]);
      pending.current = {
        task: taskRef
      };
      patch({
        selected: taskRef,
        collapsed
      });
    }
    function apply(next) {
      try {
        C.scope(next);
        defaultWindowApplied.current = false;
        pending.current = null;
        setRestore(null);
        setResult(null);
        setLoading(true);
        setScope(next);
        patch({
          collapsed: {}
        });
        setError(null);
      } catch (failure) {
        setError(failure);
      }
    }
    function reload() {
      if (snapshotPosition) setRestore(snapshotPosition);
      pending.current = null;
      const next = {
        ...scope
      };
      delete next.snapshot_ref;
      setResult(null);
      setLoading(true);
      setScope(next);
      setRefresh(n => n + 1);
    }
    function select(item, report) {
      patch({
        selected: item.task.task_ref,
        report: report ? report.report_ref : null
      });
    }
    const selected = data && data.items.find(item => item.task.task_ref === view.selected);
    const stats = data && M.metrics(data);
    const report = selected && selected.execution && selected.execution.reports.find(r => r.report_ref === view.report);
    const targetTask = data && chainTarget && data.items.map(item => item.task).filter(task => chainTarget.includes(task.task_ref)).sort((a, b) => a.end.localeCompare(b.end) || a.task_ref.localeCompare(b.task_ref)).pop();
    const targetRef = targetTask ? targetTask.task_ref : null;
    React.useEffect(() => {
      if (!view.chain || !targetRef || !data) return;
      const controller = new AbortController();
      setRelatedChain({
        target: targetRef,
        busy: true
      });
      const timer = setTimeout(async () => {
        try {
          if (typeof api.related !== 'function') throw window.APSResourceContract.failure('关联链读取接口未接入，未使用整版链替代。');
          const result = await api.related({
            ...scope,
            snapshot_ref: data.critical_chain.snapshot_ref
          }, targetRef, data, controller.signal);
          if (!controller.signal.aborted) setRelatedChain({
            target: targetRef,
            result,
            busy: false
          });
        } catch (error) {
          if (!controller.signal.aborted) setRelatedChain({
            target: targetRef,
            error,
            busy: false
          });
        }
      }, 120);
      return () => {
        clearTimeout(timer);
        controller.abort();
      };
    }, [api, data, scope, targetRef, view.chain]);
    const chain = view.chain && data && data.critical_chain.state === 'available' ? targetRef ? relatedChain && relatedChain.target === targetRef && relatedChain.result : data.critical_chain : null;
    const visibleChain = chain && chain.state === 'available' ? chain : null;
    const hoverMark = value => {
      setHover(value);
      setChainTarget(value && value.item ? [value.item.task.task_ref] : null);
    };
    const viewScope = () => ({
      ...scope,
      snapshot_ref: result.meta.snapshot_ref,
      format: 'csv',
      local_query: view.query.trim(),
      late_filter: view.late,
      ...(view.onlySelected ? {
        selected_task_ref: view.selected
      } : {})
    });
    async function download() {
      const controller = new AbortController();
      downloadController.current = controller;
      setExportBusy(true);
      setExportError(null);
      try {
        const output = await api.export(C.scope(viewScope(), true), controller.signal);
        if (controller.signal.aborted) return;
        if (!output || !output.blob || !output.blob.size || output.contentType.split(';')[0] !== 'text/csv' || !/^attachment;/i.test(output.disposition)) throw window.APSResourceContract.failure('下载不是有效的 CSV 附件。');
        const url = URL.createObjectURL(output.blob),
          a = document.createElement('a');
        try {
          a.href = url;
          a.download = '现场实际甘特-' + result.meta.as_of.replace(/:/g, '') + '.csv';
          document.body.appendChild(a);
          a.click();
        } finally {
          a.remove();
          setTimeout(() => URL.revokeObjectURL(url), 1000);
        }
        setExporting(false);
      } catch (failure) {
        if (!controller.signal.aborted) setExportError(failure);
      } finally {
        if (downloadController.current === controller) {
          downloadController.current = null;
          setExportBusy(false);
        }
      }
    }
    function navigate(viewName) {
      const returnContext = {
        plan_ref: scope.plan_ref,
        task_ref: view.selected,
        scope: {
          ...scope,
          query: view.query
        }
      };
      const destinationScope = {
        ...scope,
        query: view.query
      };
      // Actual uses [] for all batches; Field represents that scope by omission.
      if (viewName === 'field' && Array.isArray(destinationScope.batch_ids) && destinationScope.batch_ids.length === 0) delete destinationScope.batch_ids;
      if (snapshotPosition) sessions.set(JSON.stringify(returnContext), {
        scope,
        view,
        zoom,
        position: snapshotPosition
      });
      if (typeof onNavigate === 'function') onNavigate(viewName, {
        plan_ref: scope.plan_ref,
        task_ref: view.selected,
        operation_ref: selected ? selected.task.operation_ref : undefined,
        scope: destinationScope,
        return_to: {
          view: 'fieldgantt',
          context: returnContext
        }
      });
    }
    return /*#__PURE__*/React.createElement("div", {
      className: "plana fg-page fg-live",
      "data-actual-gantt": true
    }, /*#__PURE__*/React.createElement(Styles, null), /*#__PURE__*/React.createElement("div", {
      className: "fg-heading"
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("h2", {
      className: "wb-page-title"
    }, "\u73B0\u573A\u5B9E\u9645\u7518\u7279"), /*#__PURE__*/React.createElement("span", {
      className: "fg-muted wb-page-context"
    }, data ? data.plan.display_name + ' · 数据截至 ' + M.time(result.meta.as_of) : loading ? '正在读取计划与执行事实' : '计划与执行事实')), /*#__PURE__*/React.createElement("div", {
      className: "wb-actions"
    }, /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      "aria-label": "\u5237\u65B0\u5B9E\u9645\u7518\u7279",
      busy: loading,
      onClick: reload
    }), onNavigate && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
      icon: "chart-gantt",
      onClick: () => navigate('gantt')
    }, "\u8BA1\u5212\u7518\u7279"), /*#__PURE__*/React.createElement(Button, {
      icon: "arrow-right",
      onClick: () => navigate('field')
    }, "\u73B0\u573A\u62A5\u5DE5")), onNavigate && initialContext.return_to && /*#__PURE__*/React.createElement(Button, {
      icon: "chevron-left",
      onClick: () => {
        const target = initialContext.return_to;
        if (['gantt', 'field', 'analysis', 'reports', 'review', 'dashboard'].includes(target.view)) onNavigate(target.view, target.context || {});
      }
    }, "\u56DE\u6765\u6E90"))), /*#__PURE__*/React.createElement(ErrorBox, {
      error: error
    }), !data && /*#__PURE__*/React.createElement(window.WorkbenchControls.EmptyState, {
      kind: loading ? 'loading' : 'empty',
      title: loading ? '正在读取计划与执行事实…' : error ? '实际甘特未读取成功' : '暂无实际甘特数据'
    }), !data && !loading && onNavigate && /*#__PURE__*/React.createElement(Button, {
      icon: "chart-gantt",
      onClick: () => onNavigate('analysis', {})
    }, "\u9009\u62E9\u8BA1\u5212"), data && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Range, {
      scope: scope,
      resources: data.resources,
      onApply: apply,
      busy: loading
    }), data.availability.state !== 'available' && /*#__PURE__*/React.createElement("div", {
      role: "status",
      className: "fg-note"
    }, data.availability.reason), /*#__PURE__*/React.createElement("dl", {
      className: "fg-metrics",
      "aria-label": "\u5F53\u524D\u8303\u56F4\u6982\u51B5"
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u6574\u9053\u5DF2\u5B8C\u5DE5"), /*#__PURE__*/React.createElement("dd", null, stats.complete === null ? '不可用' : stats.complete)), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u5DF2\u62A5\u5DE5 \xB7 \u672A\u6574\u9053\u5B8C\u5DE5"), /*#__PURE__*/React.createElement("dd", null, stats.reported === null ? '不可用' : stats.reported)), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u5F85\u62A5\u5DE5"), /*#__PURE__*/React.createElement("dd", null, stats.pending === null ? '不可用' : stats.pending)), /*#__PURE__*/React.createElement("div", {
      title: "\u4EC5\u7EDF\u8BA1\u6709\u786E\u8BA4\u5B8C\u5DE5\u65F6\u95F4\u7684\u5DF2\u5B8C\u5DE5\u5DE5\u5E8F"
    }, /*#__PURE__*/React.createElement("dt", null, "\u5E73\u5747\u6574\u9053\u5B8C\u5DE5\u504F\u5DEE"), /*#__PURE__*/React.createElement("dd", null, stats.average === null ? '未核实' : (stats.average > 0 ? '+' : '') + window.WorkbenchFormat.number(Math.round(stats.average) + 0, {
      digits: 0
    }) + 'm'))), /*#__PURE__*/React.createElement("section", {
      className: "gb-workspace fg-workspace",
      "aria-label": "\u73B0\u573A\u5B9E\u9645\u7518\u7279\u5DE5\u4F5C\u533A"
    }, /*#__PURE__*/React.createElement(Toolbar, {
      view,
      patch,
      model,
      data,
      zoom,
      width,
      onZoom: zoomTo,
      onFit: () => {
        pending.current = {
          center: .5
        };
        setZoom(1);
        pan(0);
      },
      onLocate: () => locate(),
      onExport: () => {
        setExportError(null);
        setExporting(true);
      },
      busy: exportBusy
    }), data.critical_chain.state === 'unavailable' && /*#__PURE__*/React.createElement("div", {
      className: "fg-note",
      role: "status"
    }, "\u5173\u952E\u94FE\u4E0D\u53EF\u7528\uFF1A", data.critical_chain.reason), view.chain && data.critical_chain.state === 'available' && /*#__PURE__*/React.createElement("div", {
      className: "fg-chain-slot"
    }, chain && /*#__PURE__*/React.createElement(Chain, {
      chain: chain,
      model: model,
      onLocate: locate
    }), targetRef && (!relatedChain || relatedChain.target !== targetRef || relatedChain.busy) && /*#__PURE__*/React.createElement("div", {
      className: "fg-note",
      role: "status"
    }, "\u6B63\u5728\u8BFB\u53D6\u5F53\u524D\u5BF9\u8C61\u5173\u8054\u94FE..."), targetRef && relatedChain && relatedChain.target === targetRef && /*#__PURE__*/React.createElement(ErrorBox, {
      error: relatedChain.error
    })), view.selected && !model.items.some(i => i.task.task_ref === view.selected) && /*#__PURE__*/React.createElement("div", {
      role: "status",
      className: "fg-note"
    }, "\u9009\u4E2D\u5DE5\u5E8F\u4E0D\u5728\u5F53\u524D\u7B5B\u9009\u8303\u56F4\uFF0C\u672A\u6269\u5927\u6765\u6E90\u6761\u4EF6\u3002"), view.report && selected && !report && /*#__PURE__*/React.createElement("div", {
      role: "alert",
      className: "fg-note"
    }, "\u539F\u62A5\u5DE5\u8BB0\u5F55\u4E0D\u5728\u6240\u9009\u5DE5\u5E8F\u4E2D\uFF0C\u672A\u6539\u6307\u5176\u4ED6\u8BB0\u5F55\u3002"), view.details && /*#__PURE__*/React.createElement("div", {
      className: "fg-details",
      "aria-label": "\u5DE5\u5E8F\u8BE6\u60C5"
    }, selected ? /*#__PURE__*/React.createElement(React.Fragment, null, describe(selected, model.labels, report).map((line, i) => /*#__PURE__*/React.createElement("span", {
      key: i
    }, line)), selected.execution && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      className: "fg-report-selector"
    }, /*#__PURE__*/React.createElement("label", null, "\u9010\u6B21\u62A5\u5DE5 ", /*#__PURE__*/React.createElement("select", {
      "aria-label": "\u9009\u62E9\u62A5\u5DE5\u8BE6\u60C5",
      value: view.report || '',
      onChange: e => patch({
        report: e.target.value || null
      })
    }, /*#__PURE__*/React.createElement("option", {
      value: ""
    }, "\u6574\u9053\u5DE5\u5E8F"), selected.execution.reports.map(r => /*#__PURE__*/React.createElement("option", {
      key: r.report_ref,
      value: r.report_ref
    }, r.report_no)))), /*#__PURE__*/React.createElement(Button, {
      className: "fg-icon-button",
      icon: "search",
      "aria-label": "\u5B9A\u4F4D\u672C\u6B21\u62A5\u5DE5",
      disabled: !report || !report.actual_start,
      onClick: () => locate()
    })), selected.execution.remaining_plan && /*#__PURE__*/React.createElement("span", null, "\u5269\u4F59\u5B89\u6392\uFF1A", M.time(selected.execution.remaining_plan.start), " \u2192 ", M.time(selected.execution.remaining_plan.end)), selected.execution.data_gaps.map((gap, i) => /*#__PURE__*/React.createElement("span", {
      key: 'gap' + i
    }, gap.message || '执行记录待核对')), report && /*#__PURE__*/React.createElement("span", null, "\u767B\u8BB0\uFF1A", M.time(report.recorded_at), " \xB7 \u5386\u53F2\u7248\u672C ", report.correction_history.length, " \u6761"))) : /*#__PURE__*/React.createElement("span", null, "\u672A\u9009\u4E2D\u5DE5\u5E8F")), /*#__PURE__*/React.createElement("div", {
      className: "fg-board",
      ref: board,
      "data-actual-scroll": true,
      tabIndex: 0,
      "aria-label": "\u5206\u6B21\u62A5\u5DE5\u7518\u7279",
      style: {
        '--fg-label': labelWidth + 'px'
      },
      onScroll: () => {
        cancelAnimationFrame(frame.current);
        frame.current = requestAnimationFrame(measure);
      }
    }, /*#__PURE__*/React.createElement("div", {
      className: "fg-board-inner",
      style: {
        width: labelWidth + width,
        height: model.height + 52
      }
    }, /*#__PURE__*/React.createElement("div", {
      className: "fg-axis"
    }, /*#__PURE__*/React.createElement("div", {
      className: "fg-corner"
    }, M.views[view.mode], " / \u5DE5\u5E8F", /*#__PURE__*/React.createElement("small", {
      className: "fg-muted",
      style: {
        display: 'block'
      }
    }, "\u5DE5\u5382\u672C\u5730\u65F6\u95F4 \xB7 \u8FDE\u7EED\u8DE8\u591C")), /*#__PURE__*/React.createElement("div", {
      className: "fg-ticks",
      style: {
        width
      }
    }, M.ticks(model, width, position.left, viewport).map(tick => /*#__PURE__*/React.createElement("div", {
      className: "fg-tick",
      key: tick.at,
      title: M.time(tick.label),
      style: {
        left: tick.x,
        width: Math.min(134, width - tick.x)
      }
    }, tick.x + 110 <= width && /*#__PURE__*/React.createElement(React.Fragment, null, M.time(tick.label).slice(0, 10), /*#__PURE__*/React.createElement("small", null, M.time(tick.label).slice(11, 19))))), /*#__PURE__*/React.createElement("i", {
      className: "fg-clock",
      style: {
        left: (model.asOf - model.start) / (model.end - model.start) * width
      },
      title: '数据时点 ' + M.time(result.meta.as_of),
      "aria-hidden": "true"
    }))), /*#__PURE__*/React.createElement(window.ActualGanttRows, {
      model,
      view,
      width,
      viewport,
      labelWidth,
      patch,
      left: position.left,
      top: position.top,
      height: position.height,
      dense: data.task_count >= 1000,
      onSelect: select,
      onHover: hoverMark,
      onChainTarget: setChainTarget,
      chain: visibleChain
    }), !model.items.length && /*#__PURE__*/React.createElement(window.WorkbenchControls.EmptyState, {
      kind: view.query || view.late !== 'all' || view.onlySelected ? 'filtered' : 'empty',
      title: "\u5F53\u524D\u8303\u56F4\u6CA1\u6709\u5339\u914D\u7684\u5DE5\u5E8F\u3002",
      action: view.query || view.late !== 'all' || view.onlySelected ? /*#__PURE__*/React.createElement(Button, {
        onClick: () => patch({
          query: '',
          late: 'all',
          onlySelected: false
        })
      }, "\u6E05\u9664\u7B5B\u9009") : undefined
    }))), /*#__PURE__*/React.createElement("div", {
      className: "fg-foot"
    }, /*#__PURE__*/React.createElement("span", null, M.time(M.wire(model.start))), /*#__PURE__*/React.createElement("input", {
      type: "range",
      "aria-label": "\u65F6\u95F4\u8F74\u6C34\u5E73\u4F4D\u7F6E",
      min: 0,
      max: Math.max(0, width - viewport),
      value: Math.min(position.left, width - viewport),
      step: "any",
      onChange: e => pan(Number(e.target.value)),
      disabled: zoom === 1
    }), /*#__PURE__*/React.createElement("span", null, M.time(M.wire(model.end)))))), hover && model && /*#__PURE__*/React.createElement("div", {
      className: "fg-tip",
      role: "tooltip",
      style: {
        left: Math.max(8, Math.min(hover.x + 12, window.innerWidth - 368)),
        top: Math.max(8, Math.min(hover.y + 12, window.innerHeight - 360))
      }
    }, hover.title || describe(hover.item, model.labels, hover.report).join('\n')), exporting && data && /*#__PURE__*/React.createElement(Modal, {
      title: "\u5BFC\u51FA\u73B0\u573A\u5B9E\u9645\u7518\u7279",
      icon: "download",
      onClose: () => {
        if (downloadController.current) downloadController.current.abort();
        setExporting(false);
      },
      footer: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
        onClick: () => setExporting(false),
        disabled: exportBusy
      }, "\u53D6\u6D88"), /*#__PURE__*/React.createElement(Button, {
        transfer: "export",
        busy: exportBusy,
        onClick: download
      }, "\u4E0B\u8F7D CSV"))
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        padding: 16
      }
    }, /*#__PURE__*/React.createElement("p", null, "\u6309\u5F53\u524D\u67E5\u8BE2\u8303\u56F4\u548C\u672C\u6B21\u8BFB\u53D6\u7684\u6570\u636E\u5BFC\u51FA\u5168\u90E8 ", model.items.length, " \u9053\u5339\u914D\u5DE5\u5E8F\u53CA\u5176\u9010\u6B21\u62A5\u5DE5\uFF0C\u4E0D\u53D7\u6EDA\u52A8\u3001\u6298\u53E0\u548C\u8BE6\u60C5\u5F00\u5173\u5F71\u54CD\u3002"), /*#__PURE__*/React.createElement("p", null, "\u672C\u5730\u641C\u7D22\uFF1A", view.query.trim() || '无', "\uFF1B\u665A\u671F\uFF1A", M.lateLabels[view.late], "\uFF1B\u4EC5\u9009\u4E2D\uFF1A", view.onlySelected ? '是' : '否', "\u3002\u672A\u77E5\u6570\u91CF\u548C\u5DE5\u65F6\u4FDD\u6301\u7A7A\u503C\uFF0C\u65E7\u6267\u884C\u4E8B\u5B9E\u53E6\u5217\u3002"), /*#__PURE__*/React.createElement("p", null, "\u8BA1\u5212\u5B8C\u5DE5\u65E5\u671F\uFF1A", scope.plan_finish_date_from || '不限', " \u81F3 ", scope.plan_finish_date_to || '不限', "\uFF1B\u6570\u636E\u622A\u81F3 ", M.time(result.meta.as_of), "\u3002\u6570\u636E\u53D8\u5316\u65F6\u4E0B\u8F7D\u4F1A\u8981\u6C42\u5237\u65B0\u3002"), /*#__PURE__*/React.createElement(ErrorBox, {
      error: exportError
    }))));
  }
  function ActualGanttWorkspace(props) {
    return /*#__PURE__*/React.createElement(Content, {
      key: JSON.stringify(props.initialContext || {}),
      ...props
    });
  }
  window.ActualGanttWorkspace = ActualGanttWorkspace;
})();
