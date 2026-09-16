(function () {
  'use strict';
  const C = window.PreflightContract, { Button, ErrorBox, Rules, Metrics, Reasons, Styles } = window.PreflightControls;
  const labels = { eligible: '资料有效', auto_assign_required: '自动分配待补', skipped: '本次跳过', blocked: '缺资料', protected: '已开工保护' };
  function contextState(value) {
    try { return { value: C.initial(value), error: null }; }
    catch (error) { return { value: C.defaults(), error }; }
  }
  function Details({ data }) {
    const [page, setPage] = React.useState(1), pages = Math.max(1, Math.ceil(data.tasks.length / 100));
    return <details className="pf-detail"><summary>检查明细 · {data.tasks.length} 道</summary>
      <div className="pf-results wb-table-frame" data-sticky-head data-sticky-actions><table className="wb-table" aria-label="排产检查明细"><caption className="wb-visually-hidden">排产检查明细</caption><colgroup><col style={{ width: '18%' }} /><col style={{ width: '20%' }} /><col style={{ width: '15%' }} /><col /></colgroup>
        <thead><tr><th scope="col">批次</th><th scope="col">工序</th><th scope="col">检查结果</th><th scope="col">原因</th></tr></thead><tbody>{data.tasks.slice((page - 1) * 100, page * 100).map(row => <tr key={row.operation_ref}>
          <td>{row.batch_id}</td><td>{row.sequence} · {row.label}{row.piece_id ? ' · ' + row.piece_id : ''}</td><td>{labels[row.status]}</td>
          <td>{row.issues.map((item, index) => <p key={index}>{item.message}{item.predecessor_sequence ? ' 前序：' + item.predecessor_sequence : ''}</p>)}
            {row.execution.first_actual_start && <p>实际开工：{window.WorkbenchFormat.dateTime(row.execution.first_actual_start)}</p>}
            {row.execution.confirmed_finish && <p>确认完工：{window.WorkbenchFormat.dateTime(row.execution.confirmed_finish)}</p>}
            {row.status === 'protected' && <p>剩余数量：{row.execution.remaining_quantity === null ? '未知' : row.execution.remaining_quantity}</p>}</td>
        </tr>)}</tbody></table></div>
      {pages > 1 && <window.WorkbenchListControls.Pager page={page} pages={pages} total={data.tasks.length} size={100} unit="道" label="检查明细" onPage={setPage} />}
    </details>;
  }
  function NoRoutes({ rows }) {
    const [page, setPage] = React.useState(1), pages = Math.max(1, Math.ceil(rows.length / 100));
    return <details className="pf-detail"><summary>未生成工艺 · {rows.length} 批</summary>
      <div className="pf-results wb-table-frame" data-sticky-head data-sticky-actions>{rows.slice((page - 1) * 100, page * 100).map(row => <p key={row.batch_ref}>{row.batch_id} · 尚未生成工艺</p>)}</div>
      {pages > 1 && <window.WorkbenchListControls.Pager page={page} pages={pages} total={rows.length} size={100} unit="批" label="未生成工艺" onPage={setPage} />}
    </details>;
  }
  function PreflightWorkspace({ onNavigate, initialContext, renderRunPanel, actions }) {
    const adapter = React.useMemo(() => window.PreflightAPI.create(), []);
    const [initial, setInitial] = React.useState(() => contextState(initialContext));
    const [value, setValue] = React.useState(initial.value), [error, setError] = React.useState(null), [result, setResult] = React.useState(null);
    const [busy, setBusy] = React.useState(false), [expanded, setExpanded] = React.useState(false);
    const [needsRecheck, setNeedsRecheck] = React.useState(false);
    const serial = React.useRef(0), active = React.useRef(null), context = React.useRef(initialContext);
    const remembered = React.useMemo(() => {
      try { return C.input(value); }
      catch (_) { return null; }
    }, [value]);
    window.WorkbenchPageContext.useSnapshot(remembered, !initial.error && remembered !== null);
    function invalidate() { serial.current++; if (active.current) active.current.abort(); setResult(null); setError(null); setBusy(false); }
    function change(patch) { if (result || busy) setNeedsRecheck(true); invalidate(); setValue(old => ({ ...old, ...patch })); }
    React.useEffect(() => {
      if (context.current !== initialContext) { context.current = initialContext; const next = contextState(initialContext); invalidate(); setInitial(next); setValue(next.value); }
    }, [initialContext]);
    React.useEffect(() => () => { serial.current++; if (active.current) active.current.abort(); }, []);
    async function check() {
      if (busy || initial.error) return;
      invalidate(); const id = ++serial.current, controller = new AbortController(); active.current = controller;
      setBusy(true);
      try { const input = C.input(value), response = await adapter.preflight(input, controller.signal); C.result(response, input); if (serial.current === id) { setResult(response); setNeedsRecheck(false); } }
      catch (problem) { if (serial.current === id) setError(problem); }
      finally { if (serial.current === id) setBusy(false); }
    }
    const data = result && result.data, counts = data && data.counts, currentStep = window.RunPresentation.step(remembered, data);
    const runBlocked = !data || data.write_context.capabilities['scheduling.run'] !== true || typeof adapter.run !== 'function';
    const runReason = data && data.run_blocked_reasons[0].message || window.WorkbenchTerms.outcomes.unavailable;
    function navigate(kind) {
      if (!onNavigate || !data) return;
      const rows = kind === 'unready' ? data.unready_batches : kind === 'resources' ? data.tasks.filter(row => row.issues.some(item => ['machine_missing', 'operator_missing', 'operator_skill_missing', 'machine_authorization_missing'].includes(item.code)))
        : data.tasks.filter(row => row.status === 'blocked').concat(data.no_route_batches);
      const ids = Array.from(new Set(rows.map(row => row.batch_id)));
      invalidate();
      onNavigate('batches', { focus: kind === 'unready' ? 'unready' : 'gaps', batchIds: ids, return_to: 'run' });
    }
    const checks = [
      ['设备 / 人员', counts ? counts.missing_resource_tasks + ' 道缺资源；' + (value.missing_resource_policy === 'auto_assign' ? counts.auto_assign_required + ' 道待自动分配。' : '按本次规则暂不排入。') : '尚未检查设备与人员。', 'resources', '去补齐'],
      ['齐套状态', counts ? counts.unready_batches + ' 批未齐套；' + (value.ready_check ? '本次执行齐套检查。' : '本次关闭齐套检查。') : '尚未读取齐套情况。', 'unready', '查看批次'],
      ['工时 / 工艺 / 外协', counts ? counts.blocked_tasks + ' 道缺资料，' + counts.no_route_batches + ' 批未生成工艺。' : '尚未检查必填资料。', 'gaps', '处理缺项'],
      ['班表与产能', '本次不检查。夜班、停机和产能是否够用，请到「工作日历」核对。', null, null]
    ];
    return <div className="plana preflight-workspace" data-preflight-workspace><Styles />
      <div className="pf-heading"><h2 className="wb-page-title">执行排产</h2><span className="pf-muted wb-page-context">当前生产资料 · 单次排产范围</span>{actions && <div className="pf-tools">{actions}</div>}</div>
      <section className="pf-scope" aria-label="排产范围">
      <ol className="pf-stepper" aria-label="执行排产步骤">{['选批次和日期', '检查', '计算'].map((label, index) => <li key={label} aria-current={currentStep === index + 1 ? 'step' : undefined} data-step-state={currentStep > index + 1 ? 'complete' : currentStep === index + 1 ? 'current' : 'upcoming'}><span aria-hidden="true">{index + 1}</span>{label}</li>)}</ol>
      <ErrorBox error={initial.error} />{initial.error && <Button icon="refresh-cw" onClick={() => { const next = contextState(undefined); invalidate(); setInitial(next); setValue(next.value); }}>重新选择范围</Button>}
      <div className="pf-window"><strong>排产日期范围</strong><label>开始日期<input type="date" aria-label="计划开始日期" min="1900-01-01" max="9999-12-30" value={value.start_date} disabled={!!initial.error} onChange={event => change({ start_date: event.target.value })} /></label>
        <label>结束日期<input type="date" aria-label="计划结束日期" min="1900-01-01" max="9999-12-30" value={value.end_date} disabled={!!initial.error} onChange={event => change({ end_date: event.target.value })} /></label>
        <span>已选 {value.batch_refs.length} 批</span><Button icon={expanded ? 'chevron-up' : 'chevron-down'} className={currentStep === 1 ? 'btn primary' : 'btn'} disabled={!!initial.error} aria-expanded={expanded} onClick={() => setExpanded(old => !old)}>{expanded ? '收起范围' : '选择批次'}</Button></div>
      {expanded && !initial.error && <window.PreflightBatchPicker adapter={adapter} selected={value.batch_refs} onChange={batch_refs => change({ batch_refs })} disabled={busy} />}
      <Metrics counts={counts} /></section>
      <section className="pf-review" aria-label="排产规则与检查"><div className="pf-body"><Rules value={value} onChange={change} disabled={!!initial.error} />
        <section aria-labelledby="pf-check-title"><h3 id="pf-check-title">排产检查</h3><div className="pf-rows">{checks.map(([title, description, kind, action]) => <div className="pf-check" key={title}>
          <div><strong>{title}</strong><p>{description}</p></div>{kind && <Button disabled={!data || !onNavigate || busy || !(kind === 'resources' ? counts.missing_resource_tasks : kind === 'unready' ? counts.unready_batches : counts.blocked_tasks + counts.no_route_batches)} onClick={() => navigate(kind)}>{action}</Button>}
        </div>)}</div></section></div>
      <ErrorBox error={error} />{needsRecheck && <p className="pf-recheck" role="status">排产参数已变化，请重新检查后再开始计算。</p>}{busy && <p role="status">正在读取批次、设备人员和报工记录，还没开始排产。</p>}
      {data && <><p className="pf-muted" role="status">检查时间：{window.WorkbenchFormat.dateTime(result.meta.as_of)} · 结果有效至 {window.WorkbenchFormat.dateTime(data.input_expires_at)} · 班表未核对</p>
        <Details key={data.input_ref} data={data} />
        {!!data.no_route_batches.length && <NoRoutes key={data.input_ref} rows={data.no_route_batches} />}
        <Reasons data={data} /></>}
      <div className="pf-footer"><span className="pf-muted">{data ? '排产检查不生成版本、不写入业务或审计数据。' : renderRunPanel ? '请先选择批次和排产日期范围，再点「开始排产检查」。' : window.WorkbenchTerms.outcomes.unavailable}</span>
        <div className="pf-tools"><Button icon="search" className={currentStep === 2 ? 'btn primary' : 'btn'} busy={busy} disabled={!!initial.error} onClick={check}>{data ? '重新检查' : '开始排产检查'}</Button>
          {!renderRunPanel && <Button icon="play" className={currentStep === 3 ? 'btn primary' : 'btn'} disabled={runBlocked} reason={runReason}>开始排产</Button>}</div></div></section>
      {renderRunPanel && renderRunPanel(data)}
    </div>;
  }
  window.PreflightWorkspace = PreflightWorkspace;
})();
