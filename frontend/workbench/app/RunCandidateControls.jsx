(function () {
  'use strict';
  const { Button, Icon } = window.ResourceControls;
  function ErrorBox({ error }) { return error ? <div className="rc-notice rc-error" role="alert">{error.message || '候选方案读取失败，请刷新后重试。'}</div> : null; }
  function Reasons({ rows = [] }) {
    const groups = new Map();
    rows.forEach(r => { const key = [r.field, r.code, r.message].join('\n'); if (!groups.has(key)) groups.set(key, { ...r, count: 0 }); groups.get(key).count++; });
    const [page, setPage] = React.useState(1), values = Array.from(groups.values()), pages = Math.max(1, Math.ceil(values.length / 20)), current = Math.min(page, pages);
    if (!values.length) return null;
    return <details className="rc-reasons"><summary>原因与数据缺项 · {rows.length} 项</summary>
      {values.slice((current - 1) * 20, current * 20).map((r, i) => <div key={i}>{r.message}{r.count > 1 && '（' + r.count + ' 项）'}{r.field && <window.WorkbenchReference entries={{ '数据项': r.field, '原因码': r.code }} />}</div>)}
      {pages > 1 && <Pager page={current} pages={pages} onPage={setPage} label="原因" />}</details>;
  }
  function Pager({ page, pages, onPage, disabled, label }) {
    return <window.WorkbenchListControls.Pager page={page} pages={pages} onPage={onPage} disabled={disabled} label={label} />;
  }
  function Metric({ metric, suffix = '', kind }) {
    if (metric.state === 'not_applicable' && metric.reason && metric.reason.code === 'shared_run_time')
      return <details className="rc-metric rc-muted" data-metric-state="not_applicable"><summary title={metric.reason.message}>N/A</summary><small>{metric.reason.message}</small></details>;
    return metric.value === null ? <details className="rc-metric rc-muted"><summary title={metric.reason.message}>未知</summary><small>{metric.reason.message}</small></details> :
      <span>{['machine_util_avg', 'operator_util_avg'].includes(kind) ? window.RunCandidateModel.percent(metric.value) : window.RunCandidateModel.number(metric.value)}{suffix}</span>;
  }
  function ScoringScope({ value }) {
    const labels = { all_batches: '本次参与计算的全部批次', completed_batches_only: '本次计算范围内工序已排齐的批次', unknown: '评分范围待确认' };
    return <div className="rc-scoring-scope" data-scoring-scope={value.objective_scope}>
      <span>已安排 {window.RunCandidateModel.number(value.scheduled_operation_refs.length)} 道工序，已排齐 {window.RunCandidateModel.number(value.complete_batch_refs.length)} 批</span>
      <small>{labels[value.objective_scope]} · {value.is_complete ? '完整安排范围' : '部分安排范围'} · {value.components_known ? '评分分量已知' : '评分分量待确认'}</small>
    </div>;
  }
  function GenerationMetadata({ value, runRef }) {
    const G = window.RunGenerationContract, origin = value.origin, evidence = value.search_evidence_ref;
    const elapsed = window.WorkbenchFormat.number(value.first_found_elapsed_ms / 1000, { digits: 6, trim: true });
    return <dl className="rc-meta" data-generation-policy={value.generation_policy_version}>
      <div><dt>搜索来源</dt><dd>本轮共同优化<small>由“{G.objectiveLabel(origin.search_objective)}”方向发现</small></dd></div>
      <div><dt>代表方向</dt><dd>{value.representative_objectives.map(G.objectiveLabel).join(' · ') || '本方案未标记代表方向'}</dd></div>
      <div><dt>首次发现</dt><dd><span title={value.first_found_elapsed_ms + ' ms'} data-first-found-elapsed-ms={value.first_found_elapsed_ms}>本轮开始后 {elapsed} 秒</span></dd></div>
      <div><dt>生成与派工记录</dt><dd><window.WorkbenchReference label="查看实际来源记录" entries={{
        '运行永久编号': runRef || evidence.run_ref, '来源事件编号': evidence.source_event_id,
        '来源类型': origin.origin, '生成阶段': origin.phase, '生成策略': origin.strategy,
        '派工模式': origin.dispatch_mode, '派工规则': origin.dispatch_rule, '搜索方向': origin.search_objective,
        '计算请求编号': origin.request_id, '执行方式': origin.execution_kind, '修整记录': origin.repair_decision
      }} />{evidence.source_event_id === null && <small>来源事件未记录</small>}</dd></div>
    </dl>;
  }
  function Status({ candidate }) {
    return <><span className={'pill ' + (candidate.status === 'completed' && candidate.completeness === 'complete' ? 'ok' : 'warn')} data-candidate-status={candidate.status}>
      <span className="dot" />{window.WorkbenchTerms.candidate_statuses[candidate.status]}
      {candidate.completeness === 'unknown' && ' · 工序安排待确认'}</span>
      {candidate.status === 'partial' && <small data-candidate-persisted-status={candidate.persisted_status}>计算状态：{window.WorkbenchTerms.candidate_statuses[candidate.persisted_status] || '未记录'}</small>}</>;
  }
  function Catalog({ result, selectedRef, busy, query, onQuery, onSelect }) {
    const d = result && result.data;
    const [open, setOpen] = React.useState(!selectedRef), panel = React.useRef(null);
    React.useEffect(() => {
      if (selectedRef && panel.current && panel.current.contains(document.activeElement))
        panel.current.querySelector(':scope > summary').focus({ preventScroll: true });
      setOpen(!selectedRef);
    }, [selectedRef]);
    return <details className="rc-catalog" ref={panel} open={open} onToggle={e => setOpen(e.currentTarget.open)}>
      <summary>候选比较{d && ' · ' + d.candidate_count + ' 项'}{selectedRef && !open ? ' · 展开查看其他候选' : ''}</summary>
      <section aria-label="候选比较"><div className="rc-heading"><h3>候选比较{d && ' · ' + d.candidate_count + ' 项'}</h3>
      <div className="rc-tools"><label>状态 <select aria-label="候选状态" value={query.status || 'all'} disabled={busy} onChange={e => onQuery({ status: e.target.value })}>
        {[['all', '全部'], ...Object.entries(window.WorkbenchTerms.candidate_statuses)].map(([v, t]) => <option key={v} value={v}>{t}</option>)}</select></label>
        <label>排序 <select aria-label="候选排序" value={query.sort || 'sequence'} disabled={busy} onChange={e => onQuery({ sort: e.target.value })}>
          <option value="sequence">生成顺序</option><option value="label">名称</option><option value="task_count">安排数</option></select></label></div></div>
      {d && <><div className="rc-table wb-table-frame" data-sticky-head data-sticky-actions><table className="wb-table" aria-label="候选比较"><caption className="wb-visually-hidden">候选比较</caption><thead><tr><th scope="col" className="wb-col-key">{window.WorkbenchTerms.candidate}</th><th scope="col">状态</th><th scope="col">安排</th><th scope="col">{window.WorkbenchTerms.overdue_count}</th><th scope="col">{window.WorkbenchTerms.total_tardiness_hours}（小时）</th><th scope="col">时长（小时）</th><th scope="col" className="wb-col-actions">操作</th></tr></thead><tbody>
        {d.candidates.map((c, index) => <tr key={c.candidate_ref} data-candidate-ref={c.candidate_ref} aria-current={c.candidate_ref === selectedRef ? 'true' : undefined}>
          <td className="wb-col-key"><div className="rc-name"><span>{c.label || window.WorkbenchTerms.name_missing}</span><window.WorkbenchReference value={c.candidate_ref} /></div></td><td><Status candidate={c} /></td><td>{c.task_count}</td>
          {['overdue_count', 'total_tardiness_hours', 'makespan_hours'].map(k => <td key={k}><Metric metric={c.metrics[k]} /></td>)}
          <td className="wb-col-actions"><Button icon="search" className="mini" aria-label={'查看候选 ' + (c.label || '第 ' + ((d.page.number - 1) * d.page.size + index + 1) + ' 项')} disabled={busy || d.capabilities.view !== true || c.capabilities.view !== true} onClick={() => onSelect(c)}>查看</Button></td></tr>)}</tbody></table></div>
        {!d.candidates.length && <p className="rc-muted">这次排产在当前筛选下没有候选方案。</p>}
        {!d.catalog_complete && <p className="rc-notice">这次排产还没结束，候选方案列表还不完整。</p>}
      <div className="rc-heading"><details className="rc-muted"><summary>统计范围</summary><div>此表为排产时保存的计算统计：交付按工序已排齐批次，资源按已有安排。统一范围的资源比较请打开方案对比。</div></details>
          <Pager page={d.page.number} pages={Math.max(1, Math.ceil(d.page.total / d.page.size))} disabled={busy} label="候选" onPage={page => onQuery({ page }, true)} /></div></>}
    </section></details>;
  }
  function Generation({ data, analysis, meta }) {
    const g = data.generation, input = g.input, M = window.RunCandidateModel, unified = window.RunGenerationContract.unified(g.algorithm);
    return <div className="rc-source-summary" aria-label="全方案资料"><details className="rc-reasons rc-generation wb-ref"><summary>全方案资料与记录编号</summary><dl className="rc-meta">
        <div><dt>全方案排产日期</dt><dd>{input.start_date || '未记录'} 至 {input.end_date || '未记录'}</dd></div>
        <div><dt>提交 / 结束时间</dt><dd>{M.timeLabel(g.accepted_at)}<small>{M.timeLabel(g.finished_at)}</small></dd></div>
        <div><dt>计算状态</dt><dd data-candidate-persisted-status={data.candidate.persisted_status}>{window.WorkbenchTerms.candidate_statuses[data.candidate.persisted_status] || '未记录'}</dd></div>
        {meta && <div><dt>本次刷新时间</dt><dd>{M.timeLabel(meta.as_of)}</dd></div>}
        <div><dt>计算方式</dt><dd>{[g.algorithm.mode_label, g.algorithm.strategy_label].filter(Boolean).join(' · ') || '未记录'}</dd></div>
        {unified && <><div><dt>主目标</dt><dd>{window.RunGenerationContract.objectiveLabel(g.algorithm.primary_objective)}</dd></div>
          <div><dt>同时探索</dt><dd>{g.algorithm.target_objectives.map(window.RunGenerationContract.objectiveLabel).join(' · ')}</dd></div>
          {input.time_budget_seconds !== undefined && <div><dt>总计算预算</dt><dd>{M.number(input.time_budget_seconds)} 秒</dd></div>}</>}
        <div><dt>物料齐套规则</dt><dd>{window.WorkbenchTerms.material_strategy(input.material_strategy, input.ready_check)}</dd></div><div><dt>不重排时段</dt><dd data-hold-window>{window.WorkbenchTerms.hold_window(input.hold_window, g.data_gaps.some(gap => gap.field === 'input.hold_window'))}</dd></div><div><dt>齐套检查 / 缺资源</dt><dd>{input.ready_check === null ? '未记录' : input.ready_check ? '开启' : '关闭'} / {{ auto_assign: '自动分配', exclude: '暂不排' }[input.missing_resource_policy] || '未记录'}</dd></div>
        <div><dt>{'已有执行 / ' + window.WorkbenchTerms.baseline_plan}</dt><dd>{input.completed_policy === 'preserve_actuals' ? '保留已有开工和完工记录' : '执行规则未记录'}<small>{g.baseline.captured_task_count === null ? '正式计划安排数未记录' : '已保留 ' + g.baseline.captured_task_count + ' 道正式计划安排'}</small></dd></div></dl>
      {unified && <GenerationMetadata value={g.algorithm} runRef={g.run_ref} />}
      <div>原安排：{g.baseline.version === null ? '提交试排时没有正式计划' : '提交试排时保存的正式 v' + M.number(g.baseline.version) + ' · ' + M.timeLabel(g.baseline.captured_at)}</div>
      <div className="rc-muted">生成资料：提交试排时保存。{analysis && analysis.baseline.reason && analysis.baseline.reason.message}</div>
      <div className="rc-muted">{analysis ? '全方案选批：' + analysis.batches.map(row => row.batch_id).join(' / ') : '全方案的批次清单暂不可用。'}</div>
      <div>{analysis ? '全方案排产范围 ' + analysis.batch_refs.length + ' 批' : '全方案排产范围待核对'}</div>
      <div>排产记录编号：<code>{g.run_ref}</code></div><div>候选记录编号：<code>{data.candidate.candidate_ref}</code></div>
        </details>
      <Reasons rows={[...data.data_gaps, ...data.candidate.data_gaps, ...g.data_gaps, ...data.blocked_reasons, ...data.candidate.blocked_reasons]} /></div>;
  }
  function DetailFacts({ rows }) {
    return <dl>{rows.map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{value == null ? '未记录' : value}</dd></div>)}</dl>;
  }
  function Detail({ data, task, onClose, onRelated, onCollapse }) {
    const M = window.RunCandidateModel;
    const loadedRefs = React.useMemo(() => new Set(data.tasks.map(row => row.row_ref)), [data.tasks]);
    const segments = task && data.tasks.filter(row => row.operation_ref === task.operation_ref);
    const compact = !!onCollapse, execution = task && task.execution_at_generation;
    const routineUnreported = execution && execution.execution_state === 'unreported' && ['complete', 'incomplete'].includes(execution.data_quality);
    const recordsCollapsible = compact || routineUnreported, RecordSection = recordsCollapsible ? 'details' : 'section', RecordHeading = recordsCollapsible ? 'summary' : 'h4', panel = React.useRef(null);
    React.useEffect(() => { if (compact && window.matchMedia('(max-width:1050px)').matches) panel.current.scrollIntoView({ block: 'nearest' }); }, [compact]);
    const batchQuantityLabel = data.reference ? '排产时整批量' : '生成时整批量', savedLockLabel = data.reference ? '基准保存标记' : '方案保存标记';
    const supplierApplicable = task && (task.source === 'external' || task.supplier && (task.supplier.ref || task.supplier.label));
    const sourceKeys = new Set([batchQuantityLabel, '外协商', '来源', savedLockLabel]);
    const facts = task ? [['零件', task.part_label], ['工序顺序', M.number(task.sequence)],
          ['分件', task.piece_id === null ? task.data_gaps.some(g => g.field === 'piece_id') ? '分件未记录' : '共同工序' : task.piece_id],
          ['本工序目标量', M.quantityLabel(task)], [batchQuantityLabel, M.quantityLabel(task, 'batch_quantity')], ['交期', window.WorkbenchTerms.due_date(task.due_date, task.due_state || (task.due_date === '9999-12-31' ? 'unspecified' : task.due_date === null ? 'invalid' : 'specified'), task.due_issue || (task.due_date === null ? 'due_date_missing' : null))],
          ['开始', task.start && M.timeLabel(task.start)], ['结束', task.end && M.timeLabel(task.end)], ['设备', M.resourceLabel(task, 'machine')], ['人员', M.resourceLabel(task, 'operator')],
          ...(supplierApplicable ? [['外协商', M.resourceLabel(task, 'supplier')]] : []), ['来源', task.source === 'internal' ? '内部' : task.source === 'external' ? '外协' : null],
          [savedLockLabel, typeof task.locked === 'boolean' ? task.locked ? '是' : '否' : null], ['安排状态', task.reason ? task.reason.message : data.reference ? '已保存正式归档安排' : '已保存候选安排']] : [];
    const reference = task && <window.WorkbenchReference entries={{ '安排编号': task.row_ref, '工序编号': task.operation_ref, '批次编号': task.batch_ref,
      '设备编号': task.machine && task.machine.ref, '人员编号': task.operator && task.operator.ref, '供应商编号': task.supplier && task.supplier.ref }} />;
    return <aside ref={panel} className={'rc-detail' + (compact ? ' wb-gantt-detail-panel' : '')} id={compact ? 'candidate-gantt-detail' : undefined} aria-label={data.reference ? '正式归档工序详情' : '候选工序详情'}>
      <header className={compact ? 'wb-gantt-detail-header' : 'rc-heading'}><h3>工序详情</h3>{compact ? <Button icon="panel-right-close" onClick={onCollapse}>收起详情</Button> : task && <Button icon="x" aria-label="关闭工序详情" onClick={onClose} />}</header>
      <div className={compact ? 'wb-gantt-detail-body' : undefined} data-wb-scroll-key={compact ? 'candidate-inspector' : undefined}>
      {!task ? <p className="rc-muted">尚未选择工序</p> : <><strong>{task.batch_label || '批次名称未填写'} · {task.process_label || '工序名称未填写'}</strong>
        <DetailFacts rows={compact ? facts.filter(([key]) => !sourceKeys.has(key)) : facts} />
        <window.RunOperationEffort.Detail value={task.operation_effort} compact={compact} />
        {!compact && reference}
        {segments.length > 1 && <details className="wb-gantt-detail-section"><summary>本工序分段安排 · {segments.length} 段</summary><div className="wb-gantt-detail-section-body">{segments.map(segment => <div className="rc-saved-segment" key={segment.row_ref}><Button className="btn link" onClick={() => onRelated(segment.row_ref)}>{M.timeLabel(segment.start)} 至 {M.timeLabel(segment.end)}</Button><small>设备 {M.resourceLabel(segment, 'machine')} · 人员 {M.resourceLabel(segment, 'operator')}</small></div>)}</div></details>}
        <window.GanttRouteList graph={data.gantt_graph} targetRef={task.row_ref} loadedRefs={loadedRefs} onSelect={onRelated} collapsible={compact} />
        {compact && <details className="wb-gantt-detail-section"><summary>来源与记录编号</summary><div className="wb-gantt-detail-section-body"><DetailFacts rows={facts.filter(([key]) => sourceKeys.has(key))} />{reference}</div></details>}
        <RecordSection className={compact ? 'wb-gantt-detail-section' : routineUnreported ? 'rc-reasons' : undefined}><RecordHeading>{data.reference ? '排产时的开工和完工记录' : '生成时的开工和完工记录'}</RecordHeading><div className={compact ? 'wb-gantt-detail-section-body' : undefined}>
          {task.execution_at_generation ? <DetailFacts rows={Object.keys(task.execution_at_generation).map(key => [M.executionLabels[key], M.executionField(task, key)])} /> : <p className="rc-muted">提交试排时的开工和完工记录缺失，请核对该工序的生成资料。</p>}
        </div></RecordSection><Reasons rows={task.data_gaps} /></>}</div>
    </aside>;
  }
  function Delivery({ data, onLast }) {
    const M = window.RunCandidateModel, F = window.WorkbenchFormat, T = window.WorkbenchTerms;
    const [page, setPage] = React.useState(1), summary = data.summary;
    const pages = Math.max(1, Math.ceil(data.items.length / 20)), current = Math.min(page, pages);
    const reasons = { operations_unscheduled: '尚有工序未安排', operations_missing: '排产时工序未记录',
      schedule_time_invalid: '安排时间无效', saved_plan_incomplete: '候选结果不完整', due_date_missing: '交期未记录',
      due_date_invalid: '交期无效', due_date_unspecified: '未指定交期', part_label_missing: '零件名称未填写' };
    return <section aria-label="候选逐批交付风险"><h3>逐批交付风险</h3>
      <dl className="rc-meta">{[[summary.overdue_count, '预计超期批次'], [summary.total_tardiness_hours, '总拖期（小时）']].map(([value, label]) => <div key={label}><dt>{label}</dt><dd>{summary.state === 'not_applicable' ? '本范围未指定交期' : M.number(value)}
        {value === null && summary.known_due_count > 0 && <small>已知小计 {M.number(label === '预计超期批次' ? summary.known_overdue_count : summary.known_tardiness_hours)}</small>}</dd></div>)}
        <div><dt>关联批次</dt><dd>{M.number(summary.batch_count)}</dd></div></dl>
      {data.issues.map((issue, index) => <p className="rc-notice" key={index}>{issue.message}</p>)}
      <div className="rc-table wb-table-frame" data-sticky-head data-sticky-actions><table className="wb-table" aria-label="候选交付风险列表"><caption className="wb-visually-hidden">候选交付风险列表</caption><thead><tr>{['批次 / 零件', '批量 / ' + T.arrangement_labels.status, '交期', T.arrangement_labels.planned_finish, '预计交付', '末端工序 / 依据'].map(label => <th scope="col" key={label}>{label}</th>)}</tr></thead>
        <tbody>{data.items.slice((current - 1) * 20, current * 20).map(row => <tr key={row.batch_ref}>
          <td>{row.batch_id}<small>{row.part_no || '图号未记录'} · {row.part_label || '名称未填写'}</small></td>
          <td>{M.number(row.quantity)} 件<small>{row.scheduled_operation_count} / {row.operation_count} 道 · {T.delivery_completion_states[row.completion_state]}</small>{T.missing_arrangements(row.ordinary_unscheduled_operation_count, row.deferred_operation_count) && <small>{T.missing_arrangements(row.ordinary_unscheduled_operation_count, row.deferred_operation_count)}</small>}</td>
          <td>{T.due_date(row.due_date, row.due_state, row.due_issue)}</td><td title={row.planned_finish ? M.timeLabel(row.planned_finish) : undefined}>{row.planned_finish ? F.dateTime(row.planned_finish) : ['complete', 'unknown'].includes(row.completion_state) ? '预计完工时间待确认' : '待工序排齐后确定'}
            {!row.planned_finish && row.partial_planned_finish && <small title={M.timeLabel(row.partial_planned_finish)}>{T.arrangement_labels.partial_finish}：{F.dateTime(row.partial_planned_finish)}</small>}</td>
          <td>{T.delivery_risks[row.risk]}{row.delay_hours > 0 && <small>{M.number(row.delay_hours)} 小时</small>}</td>
          <td>{row.last_operations.map(task => <Button key={task.row_ref} icon="search" className="mini" onClick={() => onLast(task)}
            aria-label={'定位末端工序 ' + row.batch_id + ' ' + task.sequence + (task.piece_id ? ' ' + task.piece_id : '')}>
            {M.number(task.sequence)} {task.process_label || '工序未记录'}{task.piece_id && ' · ' + task.piece_id}</Button>)}
            {row.issues.map((code, index) => <small key={index}>{reasons[code] || '排产时依据不完整，交付结论待确认'}</small>)}</td>
        </tr>)}{!data.items.length && <tr><td colSpan={6}>{data.items_complete ? '当前读取范围没有批次。' : '交付资料不完整，暂无法评估。'}</td></tr>}</tbody></table></div>
      <Pager page={current} pages={pages} onPage={setPage} label="候选交付风险" />
      <details className="rc-reasons"><summary>交期数据范围</summary><div>按排产时的交期和完整工艺安排判断预计交付；工序排齐情况另列。</div>
        <div>交期评价 {M.number(summary.due_evaluation_count)} 批 · 未指定交期 {M.number(summary.excluded_due_count)} 批 · 交付待确认 {M.number(summary.unknown_due_count)} 批</div></details>
    </section>;
  }
  window.RunCandidateControls = { Button, Icon, ErrorBox, Reasons, Pager, Metric, ScoringScope, GenerationMetadata, Status, Catalog, Generation, Detail, Delivery };
})();
