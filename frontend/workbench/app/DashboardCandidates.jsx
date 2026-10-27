(function () {
  'use strict';
  const A = window.RunCandidateAPI, Q = window.DashboardCandidateComparisonAPI, C = window.DashboardContract;
  const P = window.DashboardCandidatePanels, { Button, ErrorBox, Issues } = window.ResourceControls;
  // Q.context 保证 range_start / range_end 成对出现；未设置范围时输入框显示为空。
  const rangeDraft = value => value.range_start === undefined ? { start: '', end: '' } : { start: value.range_start, end: value.range_end };
  function rangeFor(input) {
    const start = input && input.start_date + 'T00:00:00', raw = input && input.end_date + 'T00:00:00';
    C.check(A.time(start) && A.time(raw), '这次排产没有有效的提交时间范围，无法比较。请重新选择排产记录。');
    const end = new Date(Date.parse(raw + 'Z') + 86400000).toISOString().slice(0, 19);
    C.check(A.time(end) && start < end); return { range_start: start, range_end: end };
  }
  async function allCandidates(runRef, signal) {
    const first = await A.catalog(runRef, { size: 50 }, signal), rows = first.data.candidates.slice();
    let page = 1, next = first;
    while (next.data.page.has_more) {
      next = await A.catalog(runRef, { page: ++page, size: 50, snapshot_ref: first.meta.snapshot_ref }, signal);
      C.check(next.data.candidate_count === first.data.candidate_count); rows.push(...next.data.candidates);
    }
    C.check(rows.length === first.data.candidate_count && new Set(rows.map(row => row.candidate_ref)).size === rows.length);
    return { ...first.data, candidates: rows };
  }
  function Candidates({ catalog, initialContext, onState, selectedBatch, onSelectBatch, issueBatchRef }) {
    const [choice, setChoice] = React.useState(() => { const value = Q.context(initialContext); delete value.batch_ref; return value; }), [revision, refresh] = React.useReducer(n => n + 1, 0);
    const context = Q.context({ ...choice, ...(issueBatchRef ? { batch_ref: issueBatchRef } : {}) });
    const [list, setList] = React.useState({ run: null, data: null, error: null, loading: false });
    const [read, setRead] = React.useState({ signature: null, data: null, error: null, loading: false });
    const [range, setRange] = React.useState(() => rangeDraft(choice)), [rangeError, setRangeError] = React.useState(null);
    const [summary, setSummary] = React.useState(false), [rangeOpen, setRangeOpen] = React.useState(false), signature = JSON.stringify(context);
    React.useEffect(() => { setRange(rangeDraft(choice)); }, [choice.range_start, choice.range_end]);
    React.useEffect(() => {
      const controller = new AbortController(), run = choice.run_ref;
      setList({ run, data: null, error: null, loading: !!run });
      if (run) allCandidates(run, controller.signal).then(data => { if (!controller.signal.aborted) setList({ run, data, error: null, loading: false }); })
        .catch(error => { if (!controller.signal.aborted) setList({ run, data: null, error, loading: false }); });
      return () => controller.abort();
    }, [choice.run_ref, revision]);
    React.useEffect(() => {
      const controller = new AbortController(); setSummary(false);
      setRead({ signature, data: null, error: null, loading: !!context.candidate_ref });
      if (!context.candidate_ref) return () => controller.abort();
      const load = async () => {
        if (!context.range_start || !context.range_end) {
          const first = await A.workspace(context.candidate_ref, context.batch_ref ? { batch_ref: context.batch_ref } : {}, controller.signal);
          C.check(first.data.candidate.run_ref === context.run_ref, '返回的候选不属于原排产记录，未改指其他记录。');
          if (!controller.signal.aborted) setChoice(previous => C.equal(previous, choice) ? { ...previous, ...rangeFor(first.data.generation.input) } : previous);
          return;
        }
        const comparison = await Q.read(context, controller.signal);
        if (!controller.signal.aborted) setRead({ signature, data: comparison, error: null, loading: false });
      };
      load().catch(error => { if (!controller.signal.aborted) setRead({ signature, data: null, error, loading: false }); });
      return () => controller.abort();
    }, [signature, revision]);
    const current = read.signature === signature ? read : null, result = current && current.data;
    const data = result && result.data, options = list.run === choice.run_ref && list.data;
    const caption = data ? { reference: data.candidate.candidate_ref, label: '比较方案', name: data.candidate.label || window.WorkbenchTerms.name_missing,
      status: data.baseline.available ? '已保存候选方案 · 与排产时的正式计划对照' : '已保存候选方案 · 排产时没有正式计划' } : null;
    const captionKey = JSON.stringify(caption);
    React.useLayoutEffect(() => { onState({ context, caption }); }, [onState, signature, captionKey]);
    function changeRun(ref) {
      setRangeError(null);
      if (!ref) { setChoice({}); return; }
      const run = catalog.runs.find(row => row.run_ref === ref);
      let bounds = {};
      if (run && run.scope_summary && run.scope_summary.start_date && run.scope_summary.end_date) {
        try { bounds = rangeFor(run.scope_summary); } catch (error) { setRangeError(error); }
      }
      setChoice({ run_ref: ref, ...bounds });
    }
    function applyRange(event) {
      event.preventDefault();
      try {
        const normalize = window.WorkbenchDatePickerModel.factoryTime;
        const next = Q.context({ ...choice, range_start: range.start === choice.range_start ? choice.range_start : normalize(range.start),
          range_end: range.end === choice.range_end ? choice.range_end : normalize(range.end) });
        setRangeError(null); setChoice(next); setRangeOpen(false);
      } catch (error) { setRangeError(error); }
    }
    return <section aria-label="已保存候选方案同范围比较" data-dashboard-candidates data-comparison-ready={!!data}>
      <div className="dy-heading"><h3>与排产时的正式计划比较</h3><div className="dy-tools">
        {choice.run_ref && <Button reasonDisplay="inline" icon="calendar-days" aria-expanded={rangeOpen} aria-controls="dashboard-comparison-range" title={choice.range_start && choice.range_end ? '开始（包含）' + window.WorkbenchFormat.dateTime(choice.range_start, { seconds: true, fractions: true }) + '；结束（不含）' + window.WorkbenchFormat.dateTime(choice.range_end, { seconds: true, fractions: true }) : '编辑比较时间范围'}
          aria-label="编辑候选比较时间范围" onClick={() => { if (!rangeOpen) setRange(rangeDraft(choice)); setRangeOpen(!rangeOpen); }}>{choice.range_start && choice.range_end ? window.WorkbenchFormat.compactRange(choice.range_start, choice.range_end) : '时间范围'}</Button>}
        <Button reasonDisplay="inline" icon="refresh-cw" aria-label="刷新候选方案比较" onClick={refresh} />
      </div></div>
      <label className="dy-run-picker">排产记录<select aria-label="选择排产记录" value={choice.run_ref === undefined ? '' : choice.run_ref} onChange={event => changeRun(event.target.value)}><option value="">请选择排产记录</option>
        {choice.run_ref && !catalog.runs.some(row => row.run_ref === choice.run_ref) && <option value={choice.run_ref}>原来选中的排产记录</option>}
        {catalog.runs.map(run => <option key={run.run_ref} value={run.run_ref}>{window.WorkbenchFormat.compactDateTime(run.accepted_at)} · {run.candidate_count} 份候选</option>)}
      </select></label>
      <Issues issues={catalog.issues} /><ErrorBox error={list.error} /><ErrorBox error={rangeError || current && current.error} />
      {context.batch_ref && <div className="dy-context">仅比较原问题批次。<window.WorkbenchReference entries={{ '原问题批次编号': context.batch_ref }} /></div>}
      {list.loading && <p role="status">正在读取这次排产已保存的候选方案列表。</p>}
      {options && <fieldset className="dy-candidate-options"><legend>候选方案</legend>{options.candidates.map(row => <label key={row.candidate_ref} data-candidate-choice={row.candidate_ref} data-selected={choice.candidate_ref === row.candidate_ref}>
        <input type="radio" name="dashboard-candidate" value={row.candidate_ref} checked={choice.candidate_ref === row.candidate_ref}
          onChange={() => setChoice({ ...choice, candidate_ref: row.candidate_ref })} />
        <span><b>{row.label || window.WorkbenchTerms.name_missing}</b><small>{window.WorkbenchTerms.candidate_statuses[row.status]} · {row.task_count} 道安排</small></span>
      </label>)}{!options.candidates.length && <window.WorkbenchListControls.EmptyState kind="empty" title="这次排产还没有保存候选方案。" />}</fieldset>}
      {choice.run_ref && rangeOpen && <form id="dashboard-comparison-range" className="dy-compare-range" onSubmit={applyRange}><label>开始（包含）<input type="text" data-picker-type="factory-local" spellCheck={false} aria-label="候选比较共同开始" value={range.start} onChange={event => setRange({ ...range, start: event.target.value })} /></label>
        <label>结束（不含）<input type="text" data-picker-type="factory-local" spellCheck={false} aria-label="候选比较共同结束" value={range.end} onChange={event => setRange({ ...range, end: event.target.value })} /></label><Button reasonDisplay="inline" icon="check" type="submit">应用范围</Button></form>}
      {current && current.loading && <p role="status">正在核对所选候选方案、排产时的正式计划和共同范围。</p>}
      {data && <>
        <P.Metrics data={data} /><P.Batches data={data} selected={selectedBatch} onSelect={onSelectBatch} />
        <div className="dy-tools"><Button reasonDisplay="inline" icon="chart-gantt" onClick={() => setSummary(true)}>查看方案摘要</Button></div>
        <details className="dy-evidence"><summary>排产时的范围与规则</summary><dl className="dy-facts"><div><dt>比较批次</dt><dd>{data.batch_refs.length} 批；预计完工按全部工序安排计算</dd></div><div><dt>齐套检查</dt><dd>{data.generation.input.ready_check ? '开启' : '关闭'}</dd></div>
          <div><dt>物料齐套规则</dt><dd>{window.WorkbenchTerms.material_strategy(data.generation.input.material_strategy, data.generation.input.ready_check)}</dd></div>
          <div><dt>缺设备人员时的规则</dt><dd>{data.generation.input.missing_resource_policy === 'auto_assign' ? '按匹配规则自动分配' : '排除缺设备人员的工序'}</dd></div>
          <div><dt>不重排时段</dt><dd>{window.WorkbenchTerms.hold_window(data.generation.input.hold_window)}</dd></div>
          <div><dt>已开工工序的规则</dt><dd>保留已登记的实际数据和受保护的安排</dd></div></dl><window.WorkbenchReference entries={{ '排产编号': data.generation.run_ref }} /></details>
        {summary && <P.Summary data={data} onClose={() => setSummary(false)} />}
      </>}
    </section>;
  }
  window.DashboardCandidates = Candidates;
})();
