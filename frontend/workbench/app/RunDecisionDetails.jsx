(function () {
  'use strict';
  const C = window.RunCandidateControls, D = window.RunDecisionComparison, M = window.RunCandidateModel, T = window.WorkbenchTerms, F = window.WorkbenchFormat;
  const batchChanges = [['all', '全部'], ['changed', '有明确变化'], ['earlier', '预计完工提前'], ['later', '预计完工推迟'], ['new_overdue', '新增超期'], ['relieved_overdue', '解除超期'], ['completion_improved', '工序安排改善'], ['completion_worsened', '工序安排变差'], ['unchanged', '持平'], ['unknown', '差值待确认']];
  const operationChanges = [['all', '全部'], ['changed', '有明确变化'], ['added', '新增安排'], ['removed', '移除安排'], ['moved', '时间移动'], ['machine_changed', '设备变化'], ['operator_changed', '人员变化'], ['source_changed', '内外协变化'], ['status_changed', '排产状态变化'], ['unchanged', '持平'], ['unknown', '差值待确认']];
  const batchSorts = [['current_priority', '当前风险优先'], ['worsened', '恶化优先'], ['improved', '改善优先'], ['after_delay_hours', '当前拖期'], ['delay_delta_hours', '拖期变化'], ['finish_delta_hours', '完工变化'], ['batch_id', '批次编号']];
  const changeLabels = { ...Object.fromEntries([...batchChanges, ...operationChanges]), operation_changed: '工序安排变化' };
  const deliveryFilters = [['attention', '需关注：超期、待料、未排'], ['all', '全部批次'], ['overdue', '已确认超期'], ['deferred', '待料未排'], ['unplanned', '其他未排'], ['on_time', '已确认准时']];
  const detailKeys = ['page', 'size', 'change_kind', 'sort', 'order', 'batch_ref', 'resource_ref', 'snapshot_ref', 'delivery_filter', 'selected_batch_ref'];
  function amount(value, suffix = '') { return value == null ? '未记录' : M.number(value) + suffix; }
  function delta(value, negative = '提前', positive = '推迟', suffix = ' 小时') {
    return value == null ? '差值待确认' : value === 0 ? '持平' : (value < 0 ? negative : positive)
      + (Number(Math.abs(value).toFixed(3)) === 0 ? '不到 0.001' : ' ' + M.number(Math.abs(value))) + suffix;
  }
  function riskValue(summary, key) {
    return summary.state === 'not_applicable' ? '本范围未指定交期' : summary[key] == null ? '待确认' : M.number(summary[key]);
  }
  function SummarySide({ summary, label, absent, formal }) {
    return <div className="rd-summary-side"><strong>{label}</strong>{absent ? <p>{formal ? '排产时尚无正式计划，比较基准缺失。' : '请在上方选择比较基准候选。'}</p> : <>
      <span>工序已排齐 {amount(summary.complete_batch_count)} / {amount(summary.batch_count)} 批</span>
      <span>预计超期 {riskValue(summary, 'overdue_count')}{summary.overdue_count === null && summary.known_due_count > 0 && '（已知 ' + amount(summary.known_overdue_count, ' 批') + '）'} · 总拖期 {riskValue(summary, 'total_tardiness_hours')}{summary.total_tardiness_hours !== null ? ' 小时' : summary.known_due_count > 0 ? '（已知小计 ' + amount(summary.known_tardiness_hours, ' 小时') + '）' : ''}</span>
      <details className="rd-summary-basis"><summary>交期计算范围</summary><p>{T.delivery_coverage(summary)}</p>{summary.deferred_batch_count > 0 && <p>全部未安排工序均因缺料的批次 {amount(summary.deferred_batch_count, ' 批')}</p>}</details></>}</div>;
  }
  function Summary({ data }) {
    const summary = data.summary, common = summary.common_delivery;
    return <div className="rd-impact-summary"><SummarySide summary={summary.before} label="比较基准" absent={data.baseline.state !== 'available'} formal={data.baseline.kind === 'admission_official'} />
      <SummarySide summary={summary.after} label="当前方案" />
      <details className="rd-common-delivery"><summary>双方都已排齐 · {summary.common_completed_batch_refs.length} 批</summary>
        <span>总拖期：{riskValue(common.before, 'total_tardiness_hours')} → {riskValue(common.after, 'total_tardiness_hours')} 小时 · {delta(common.delay_delta_hours, '减少', '增加')}</span>
        <span>预计超期：{riskValue(common.before, 'overdue_count')} → {riskValue(common.after, 'overdue_count')} 批 · {delta(common.overdue_delta_count, '减少', '增加', ' 批')}</span>
        <small>{T.delivery_coverage(common.after)}</small></details></div>;
  }
  function Changes({ values }) { return <div className="rd-change-list">{values.map(value => <span key={value} className="rd-badge">{changeLabels[value] || value}</span>)}</div>; }
  function Locate({ row, onDrill }) {
    return <div className="rd-locate"><C.Button icon="chart-gantt" className="mini" onClick={() => onDrill(row.drill.selected)}>查看当前甘特</C.Button>
      <C.Button icon="chart-gantt" className="mini" disabled={!row.drill.reference} title={!row.drill.reference ? '对照安排未记录' : undefined} onClick={() => onDrill(row.drill.reference)}>查看对照甘特</C.Button>
      {row.unplanned_operation_refs && (row.unplanned_operation_refs.length > 0 || row.deferred_operation_refs.length > 0) && <C.Button icon="circle-alert" className="mini" onClick={() => onDrill({ ...row.drill.selected, candidate_tab: 'unplanned' })}>查看未安排工序</C.Button>}</div>;
  }
  function BatchDelivery({ value, absent, year = true }) {
    const missing = T.missing_arrangements(value.ordinary_unscheduled_operation_count, value.deferred_operation_count);
    const complete = value.completion_state === 'complete';
    return absent ? <span className="rc-muted">比较基准缺失</span> : <><strong>{complete ? T.delivery_completion_states.complete + ' · ' + amount(value.operation_count, ' 道工序') : '已安排 ' + amount(value.scheduled_operation_count) + ' / ' + amount(value.operation_count) + ' 道'}</strong>
      {missing && <small>{missing}</small>}
      {value.partial_planned_finish && <small title={F.dateTime(value.partial_planned_finish, { seconds: true, fractions: true })}>{T.arrangement_labels.partial_finish} {F.compactDateTime(value.partial_planned_finish, { year })}</small>}
      <span title={value.planned_finish ? F.dateTime(value.planned_finish, { seconds: true, fractions: true }) : undefined}>{value.planned_finish ? T.arrangement_labels.planned_finish + '：' + F.compactDateTime(value.planned_finish, { year }) : '批次完工待确认'}</span>
      {(complete || value.risk !== 'unknown' || value.delay_hours !== null) && <span>{T.delivery_risks[value.risk]}{value.delay_hours !== null && ' · ' + amount(value.delay_hours, ' 小时')}</span>}</>;
  }
  function ArrangementSegment({ row }) {
    return <><span title={F.dateTime(row.start, { seconds: true, fractions: true }) + ' 至 ' + F.dateTime(row.end, { seconds: true, fractions: true })}>{F.compactRange(row.start, row.end)}</span>
      <small>设备：{row.machine ? row.machine.label || T.name_missing : '未记录'} · 人员：{row.operator ? row.operator.label || T.name_missing : '未记录'}</small>
      <small>{row.source === 'internal' ? '本厂安排' : row.source === 'external' ? '外协安排' : '安排类型未记录'}</small></>;
  }
  function Arrangement({ row, absent, state }) {
    if (absent) return <span className="rc-muted">比较基准缺失</span>;
    if (!row) return <><span className="rc-muted">{state ? ({ deferred: '待料未排', missing: '未安排', unavailable: '安排资料未产出' }[state.status] || '安排待确认') : '未安排'}</span>{state && state.reason && <small>{state.reason.message}</small>}</>;
    return <>{row.segments ? <details className="rd-segments"><summary>已保存 {row.segments.length} 段安排</summary>{row.segments.map(segment => <div key={segment.row_ref}><ArrangementSegment row={segment} /></div>)}</details> : <ArrangementSegment row={row} />}
      <C.Reasons rows={row.data_gaps} /></>;
  }
  function Effort({ value }) {
    return <><strong>{value.standard_total_hours === null ? value.state === 'not_applicable' ? '外协按周期' : '标准工时待确认' : amount(value.standard_total_hours, ' 小时')}</strong>
      <details className="rd-effort-record"><summary>保存的工时标准与数量</summary><span>准备 {amount(value.setup_standard_hours, ' 小时')} · 单件 {amount(value.unit_standard_hours, ' 小时')}</span><span>报工目标 {amount(value.target_quantity, ' 件')} · 报工剩余 {amount(value.remaining_quantity, ' 件')}</span></details>
      {value.reason && <small>{value.reason.message}</small>}</>;
  }
  function Constraints({ value }) {
    const flag = marker => marker === null ? '未记录' : marker ? '是' : '否';
    const reported = value.execution_state && value.execution_state !== 'unreported';
    return <>{value.protected_at_admission && <strong>排产时保留原安排</strong>}
      {reported && <><span>{T.execution_states[value.execution_state] || '报工状态待确认'}{value.data_quality !== 'complete' && ' · ' + (T.data_quality[value.data_quality] || '资料质量未记录')}</span><small>已完工 {amount(value.known_completed_quantity, ' 件')} · 剩余 {amount(value.remaining_quantity, ' 件')}</small></>}
      {!reported && value.data_quality === 'invalid' && <span>报工资料需复核</span>}
      {value.first_actual_start && <small title={F.dateTime(value.first_actual_start, { seconds: true, fractions: true })}>实际开工 {F.compactDateTime(value.first_actual_start)}</small>}{value.confirmed_finish && <small title={F.dateTime(value.confirmed_finish, { seconds: true, fractions: true })}>报工完工 {F.compactDateTime(value.confirmed_finish)}</small>}
      <details className="rd-effort-record"><summary>报工与锁定记录</summary><span>报工：{T.execution_states[value.execution_state] || '未记录'} · {T.data_quality[value.data_quality] || '资料质量未记录'}</span><span>已完工 {amount(value.known_completed_quantity, ' 件')} · 剩余 {amount(value.remaining_quantity, ' 件')}</span><span>排产时保留 {flag(value.protected_at_admission)} · 当前方案锁定 {flag(value.selected_locked)} · 固定对照锁定 {flag(value.reference_locked)}</span></details>
      <C.Reasons rows={value.reasons} /></>;
  }
  function CurrentRisk({ row }) {
    const value = row.after, missing = T.missing_arrangements(value.ordinary_unscheduled_operation_count, value.deferred_operation_count);
    return <><span className={'rd-batch-risk rd-risk-' + value.risk}>{T.delivery_risks[value.risk]}{value.delay_hours !== null && ' · ' + amount(value.delay_hours, ' 小时')}</span>{missing && <small>{missing}</small>}<small>{amount(value.scheduled_operation_count)} / {amount(value.operation_count)} 道已安排</small></>;
  }
  function BatchList({ data, difference, selectedRef, onSelect }) {
    return <div className="wb-table-frame rd-master-frame" data-sticky-head data-sticky-key><table className={'wb-table rd-master-table' + (difference ? ' rd-master-differences' : '')} aria-label={difference ? '批次工序安排差异' : '当前方案交期与未排批次'}><thead><tr>
      <th scope="col">批次</th><th scope="col">交期</th><th scope="col">预计完工 / 待料</th>{difference && <th scope="col">与固定对照的变化</th>}<th scope="col">交付状态</th>
    </tr></thead><tbody>{data.items.map(row => <tr key={row.batch_ref} data-decision-batch={row.batch_ref} aria-selected={row.batch_ref === selectedRef}>
      <td><C.Button className="btn link" aria-label={'查看' + row.batch_id + (difference ? '安排差异' : '工序链')} aria-pressed={row.batch_ref === selectedRef} onClick={() => onSelect(row.batch_ref)}>{row.batch_id}</C.Button><small>{row.part_no || '图号未记录'} · {row.part_label || T.name_missing}</small></td><td>{T.due_date(row.due_date, row.due_state, row.due_issue)}</td>
      <td><span title={row.after.planned_finish ? F.dateTime(row.after.planned_finish, { seconds: true, fractions: true }) : undefined}>{row.after.planned_finish ? F.compactDateTime(row.after.planned_finish) : row.after.deferred_operation_count > 0 ? '待料未排' : row.after.ordinary_unscheduled_operation_count > 0 ? '尚有工序未安排' : '整批完工待确认'}</span>{!row.after.planned_finish && row.after.partial_planned_finish && <small title={F.dateTime(row.after.partial_planned_finish, { seconds: true, fractions: true })}>已排部分至 {F.compactDateTime(row.after.partial_planned_finish)}</small>}</td>
      {difference && <td><strong>{amount(row.operation_change_count, ' 道工序有变化')}</strong><small>批次末端 {delta(row.finish_delta_hours)}</small>{row.operation_unknown_count > 0 && <small>{amount(row.operation_unknown_count, ' 道工序差值待确认')}</small>}</td>}
      <td><CurrentRisk row={row} /></td>
    </tr>)}</tbody></table></div>;
  }
  function segments(value) { return value ? value.segments || [value] : []; }
  function ChainTimeline({ row, bounds, difference }) {
    if (!bounds) return <span className="rc-muted">安排时间待确认</span>;
    const sides = difference ? [['before', '固定对照'], ['after', '当前查看']] : [['after', '当前查看']], span = bounds.end - bounds.start;
    const descriptions = [], tracks = sides.map(([key, label]) => {
      const parts = segments(row[key]);
      descriptions.push(label + '：' + (parts.length ? parts.map(part => F.dateTime(part.start, { seconds: true, fractions: true }) + ' 至 ' + F.dateTime(part.end, { seconds: true, fractions: true })).join('；') : row[key + '_state'] && row[key + '_state'].status === 'deferred' ? '待料未排' : '未安排'));
      return <div key={key} className={'rd-chain-track rd-chain-' + key}><span className="wb-visually-hidden">{label}</span>{parts.filter(part => part.start && part.end).map(part => {
        const start = M.instant(part.start), end = M.instant(part.end);
        return <span key={part.row_ref} className={'rd-chain-bar' + (start === end ? ' rd-chain-point' : '')} title={label + ' · ' + F.dateTime(part.start, { seconds: true, fractions: true }) + ' 至 ' + F.dateTime(part.end, { seconds: true, fractions: true })} style={{ left: (start - bounds.start) / span * 100 + '%', width: start === end ? undefined : (end - start) / span * 100 + '%' }} />;
      })}</div>;
    });
    return <div className="rd-chain-timeline" role="img" aria-label={descriptions.join('；')}>{tracks}</div>;
  }
  function OperationFacts({ row, baseline }) {
    return <details className="rd-chain-facts"><summary>工时需求、锁定与报工</summary><div className="rd-chain-facts-body"><div>
      {row.runtime_effort ? <><strong>当前保存的需求</strong><window.RunOperationEffort.Effort value={row.runtime_effort.after} showStandard={false} /><strong>固定对照需求</strong><window.RunOperationEffort.Effort value={row.runtime_effort.before} absent={baseline.state !== 'available'} /><window.RunOperationEffort.Standard value={row.effort} /></> : <Effort value={row.effort} />}
    </div><div><Constraints value={row.constraints} />{row.data_gaps && row.data_gaps.length > 0 && <C.Reasons rows={row.data_gaps} />}</div><window.WorkbenchReference value={row.operation_ref} /></div></details>;
  }
  function OperationChain({ data, difference, onDrill }) {
    const intervals = data.items.flatMap(row => (difference ? ['before', 'after'] : ['after']).flatMap(side => segments(row[side]).filter(part => part.start && part.end).map(part => ({ start: M.instant(part.start), end: M.instant(part.end), startText: part.start, endText: part.end }))));
    const low = intervals.length ? intervals.reduce((a, b) => a.start < b.start ? a : b) : null, high = intervals.length ? intervals.reduce((a, b) => a.end > b.end ? a : b) : null;
    const bounds = low && high ? { start: low.start, end: high.end > low.start ? high.end : low.start + 1 } : null;
    return <div className="rd-chain">{bounds && <div className="rd-chain-axis"><span>本页工序时间轴</span><span>{F.dateTime(low.startText, { seconds: true, fractions: true })}</span><span>{F.dateTime(high.endText, { seconds: true, fractions: true })}</span></div>}
      {data.items.map(row => <article className="rd-chain-operation" key={row.operation_ref} data-decision-operation={row.operation_ref}><div className="rd-chain-row">
        <div className="rd-chain-label"><strong>{amount(row.sequence)} · {row.process_label || T.name_missing}</strong><small>{M.pieceLabel(row)} · {amount(row.quantity, ' 件')}</small></div>
        <ChainTimeline row={row} bounds={bounds} difference={difference} />
        <div className="rd-chain-arrangements">{difference && <div><small>固定对照</small><Arrangement row={row.before} absent={data.baseline.state !== 'available'} state={row.before_state} /></div>}<div>{difference && <small>当前查看</small>}<Arrangement row={row.after} state={row.after_state} /></div></div>
        {difference && <div className="rd-chain-changes"><Changes values={row.change_kinds} /><small>开始 {delta(row.start_delta_hours)}</small><small>结束 {delta(row.end_delta_hours)}</small></div>}
        <Locate row={row} onDrill={onDrill} />
      </div><OperationFacts row={row} baseline={data.baseline} /></article>)}
    </div>;
  }
  function BatchChain({ result, batch, difference, query, onQuery, onDrill, headingRef, enabled }) {
    const scope = result.data.scope, runRef = result.data.run.run_ref;
    const stored = Object.fromEntries(Object.entries(query).filter(([key]) => detailKeys.includes(key) && !['delivery_filter', 'selected_batch_ref'].includes(key)));
    const q = window.RunDecisionAPI.detailScope(runRef, { ...stored, comparison_mode: scope.comparison_mode, resource_view: scope.resource_view, selected_candidate_ref: scope.selected_candidate_ref, ...(scope.comparison_mode === 'candidates' ? { reference_candidate_ref: scope.reference.candidate_ref } : {}), range_start: scope.range_start, range_end: scope.range_end, batch_ref: batch.batch_ref, change_kind: difference ? stored.change_kind || 'changed' : 'all', sort: stored.sort || 'sequence', order: stored.order || 'asc' }, 'operations');
    const [paused, setPaused] = React.useState(false), key = JSON.stringify(q);
    React.useEffect(() => { setPaused(false); }, [runRef, key, result.meta.snapshot_ref]);
    const read = window.APSResourceSession.useQuery(signal => window.RunDecisionAPI.decisionDetails(runRef, q, 'operations', signal), [runRef, key, result.meta.snapshot_ref], enabled && !paused), detailResult = read.result, data = detailResult && detailResult.data;
    function update(change, paging = false) { const next = { ...stored, batch_ref: batch.batch_ref, ...change, page: paging ? change.page : 1 }; delete next.snapshot_ref; if (paging && detailResult) next.snapshot_ref = detailResult.meta.snapshot_ref; setPaused(false); onQuery(next); }
    return <section className="rd-batch-detail" aria-label={difference ? '选中批次的工序安排差异' : '选中批次的完整当前工序链'}><div className="rd-batch-detail-heading"><div><h3 tabIndex={-1} ref={headingRef}>{batch.batch_id} · {difference ? '工序安排差异' : '完整工序链'}</h3><p>{batch.part_no || '图号未记录'} · {batch.part_label || T.name_missing} · {amount(batch.quantity, ' 件')} · 优先级 {window.APSBatchContract.label('priority', batch.priority)}</p><small>{T.due_date(batch.due_date, batch.due_state, batch.due_issue)}</small></div><div className="rc-tools"><Locate row={batch} onDrill={onDrill} /><C.Button icon="refresh-cw" aria-label="刷新选中批次工序链" disabled={read.loading} onClick={() => { update({}); read.reload(); }} /></div></div>
      <div className="rd-batch-detail-status"><CurrentRisk row={batch} />{difference && <>{batch.operation_change_count > 0 && <span>{amount(batch.operation_change_count, ' 道工序有明确变化')}</span>}{batch.operation_unknown_count > 0 && <span>{amount(batch.operation_unknown_count, ' 道工序差值待确认')}</span>}</>}</div>
      <details className="rd-batch-source"><summary>批次交付与记录依据</summary><div className="rd-batch-source-sides"><div><strong>固定对照</strong><BatchDelivery value={batch.before} absent={result.data.baseline.state !== 'available'} /></div><div><strong>当前查看</strong><BatchDelivery value={batch.after} /></div><div><strong>批次末端与拖期</strong><span>预计完工 {delta(batch.finish_delta_hours)}</span><span>拖期 {delta(batch.delay_delta_hours, '减少', '增加')}</span><Changes values={batch.change_kinds} /></div></div><window.WorkbenchReference value={batch.batch_ref} /></details>
      <div className="rd-detail-filters">{difference && <label>工序变化<select aria-label="选中批次工序变化类型" value={q.change_kind} disabled={read.loading} onChange={event => update({ change_kind: event.target.value })}>{operationChanges.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>}
        {difference && data && <label>资源<select aria-label="选中批次变化资源" value={q.resource_ref || ''} disabled={read.loading} onChange={event => update({ resource_ref: event.target.value || undefined })}><option value="">全部设备 / 人员</option>{data.filter_options.resources.map(row => <option key={row.ref} value={row.ref}>{row.kind === 'machine' ? '设备' : '人员'} · {row.label || T.name_missing}</option>)}</select></label>}
        {detailResult && <D.Export key={detailResult.meta.snapshot_ref} result={detailResult} initialSection="operations" filterQuery={q} />}</div>
      <C.ErrorBox error={read.error} />{read.loading && <div className="rc-tools"><span role="status">正在读取选中批次的工序安排。</span><C.Button icon="x" onClick={() => setPaused(true)}>取消读取</C.Button></div>}{paused && <p className="rc-muted" role="status">工序链读取已取消，点击刷新继续。</p>}
      {data && <><C.Reasons rows={detailResult.warnings} />{data.items.length ? <OperationChain data={data} difference={difference} onDrill={onDrill} /> : <div className="rc-empty"><p>{data.page.total > 0 ? '当前页没有工序。' : difference ? '没有符合筛选的变化。' : '当前筛选下没有工序资料。'}</p><C.Button onClick={() => data.page.total > 0 ? update({ page: 1 }, true) : update({ change_kind: 'all', resource_ref: undefined })}>{data.page.total > 0 ? '返回第 1 页' : '清除工序筛选'}</C.Button></div>}
        {data.items.length > 0 && <div className="rc-heading rd-detail-pages"><span className="rc-muted">当前工序筛选 {data.page.total} 道 · 本页 {data.items.length} 道</span><label>每页<select aria-label="工序链每页条数" value={q.size} disabled={read.loading} onChange={event => update({ size: Number(event.target.value) })}><option value="20">20 条</option><option value="50">50 条</option></select></label><C.Pager label="选中批次工序链" page={data.page.number} pages={Math.max(1, Math.ceil(data.page.total / data.page.size))} disabled={read.loading} onPage={page => update({ page }, true)} /></div>}</>}
    </section>;
  }
  function Pane({ result, section, query, onQuery, selectedBatchRef, onSelectBatch, chainQuery, onChainQuery, onDrill, onChooseReference, enabled }) {
    const overview = result.data, scope = overview.scope, runRef = overview.run.run_ref, difference = section === 'differences';
    const sameCandidate = difference && scope.comparison_mode === 'candidates' && scope.selected_candidate_ref === scope.reference.candidate_ref;
    const shared = { comparison_mode: scope.comparison_mode, resource_view: scope.resource_view, selected_candidate_ref: scope.selected_candidate_ref, range_start: scope.range_start, range_end: scope.range_end,
      ...(scope.comparison_mode === 'candidates' ? { reference_candidate_ref: scope.reference.candidate_ref } : {}) };
    const stored = Object.fromEntries(Object.entries(query).filter(([name]) => detailKeys.includes(name)));
    const q = window.RunDecisionAPI.detailScope(runRef, { delivery_filter: difference ? 'all' : 'attention', change_kind: difference ? 'changed' : 'all', sort: 'current_priority', order: 'asc', ...stored, ...shared, ...(selectedBatchRef ? { selected_batch_ref: selectedBatchRef } : {}) }, 'batches'), key = JSON.stringify(q);
    const [paused, setPaused] = React.useState(false), headingRef = React.useRef(null), focusRequested = React.useRef(false);
    React.useEffect(() => { setPaused(false); }, [runRef, key, section, result.meta.snapshot_ref]);
    const read = window.APSResourceSession.useQuery(signal => window.RunDecisionAPI.decisionDetails(runRef, q, 'batches', signal), [runRef, key, section, result.meta.snapshot_ref], enabled && !paused && !sameCandidate);
    const detailResult = read.result, data = detailResult && detailResult.data, options = data && data.filter_options;
    const changed = data && data.summary.operation_changes.changed_operation_count;
    const arrangementsEqual = difference && !sameCandidate && changed && changed.scope === 'full_admission' && changed.state === 'complete' && changed.value === 0;
    const selected = data && (data.items.find(row => row.batch_ref === selectedBatchRef) || data.selected_batch || (!selectedBatchRef ? data.items[0] : null)), selectedRef = selected && selected.batch_ref;
    const retained = selected && !data.items.some(row => row.batch_ref === selectedRef);
    React.useEffect(() => { if (enabled && !selectedBatchRef && selectedRef && onSelectBatch) onSelectBatch(selectedRef); }, [enabled, selectedBatchRef, selectedRef, onSelectBatch]);
    React.useEffect(() => { if (enabled && focusRequested.current && headingRef.current) { headingRef.current.focus(); focusRequested.current = false; } }, [enabled, selectedRef, chainQuery.batch_ref, chainQuery.change_kind]);
    function selectBatch(ref) {
      focusRequested.current = true;
      if (ref !== selectedBatchRef && query.snapshot_ref !== undefined) onQuery(Object.fromEntries(Object.entries(query).filter(([name]) => detailKeys.includes(name) && name !== 'snapshot_ref')));
      if (chainQuery.batch_ref !== ref || arrangementsEqual && chainQuery.change_kind !== 'all') onChainQuery({ ...chainQuery, batch_ref: ref,
        ...(arrangementsEqual ? { change_kind: 'all' } : {}), page: 1, snapshot_ref: undefined });
      onSelectBatch(ref); if (ref === selectedRef && headingRef.current) { headingRef.current.focus(); focusRequested.current = false; }
    }
    function update(change, paging = false) {
      const next = { ...q, ...change, page: paging ? change.page : 1 }; delete next.snapshot_ref;
      if (paging && detailResult) next.snapshot_ref = detailResult.meta.snapshot_ref;
      setPaused(false); onQuery(Object.fromEntries(Object.entries(next).filter(([name]) => detailKeys.includes(name))));
    }
    function reload() { update({}); read.reload(); }
    const missingChanges = difference && changed && changed.value === null && changed.unknown_count > 0 && !q.batch_ref && q.change_kind === 'changed';
    return <section className="rd-impact rd-batch-workspace" aria-label={difference ? '方案差异与选中批次详情' : '当前交期与未排批次'}><div className="rd-pane-intro"><h3>{difference ? '方案差异' : '交期与未排'}</h3></div>
      {sameCandidate ? <div className="rc-empty"><p>正在查看同一个方案。</p><C.Button onClick={onChooseReference}>选择对照</C.Button></div> : <div className="rd-detail-filters"><label>批次<select aria-label="影响明细批次" value={q.batch_ref || ''} disabled={read.loading || !data} onChange={event => update({ batch_ref: event.target.value || undefined })}><option value="">全部批次</option>{options && options.batches.map(row => <option key={row.ref} value={row.ref}>{row.label || T.name_missing}</option>)}</select></label>
        {!difference && <label>当前状态<select aria-label="当前交期与未排筛选" value={q.delivery_filter} disabled={read.loading} onChange={event => update({ delivery_filter: event.target.value })}>{deliveryFilters.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>}
        {difference && <label>变化<select aria-label="影响明细变化类型" value={q.change_kind} disabled={read.loading} onChange={event => update({ change_kind: event.target.value })}>{batchChanges.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>}
        <details className="rd-detail-more"><summary>更多显示</summary><div className="rd-detail-filters"><label>排序<select aria-label="影响明细排序" value={q.sort} disabled={read.loading} onChange={event => update({ sort: event.target.value })}>{batchSorts.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
          <label>顺序<select aria-label="影响明细排序顺序" value={q.order} disabled={read.loading} onChange={event => update({ order: event.target.value })}><option value="desc">降序</option><option value="asc">升序</option></select></label></div></details>
        <div className="rc-tools rd-detail-actions">{data && <D.Export key={detailResult.meta.snapshot_ref} result={detailResult} initialSection="batches" filterQuery={q} />}<C.Button icon="refresh-cw" aria-label="刷新影响明细" disabled={read.loading} onClick={reload} /></div></div>}
      <C.ErrorBox error={read.error} />{read.loading && <div className="rc-tools"><span role="status">正在读取{difference ? '方案差异' : '当前交期与未排'}批次。</span><C.Button icon="x" onClick={() => setPaused(true)}>取消读取</C.Button></div>}
      {paused && <p className="rc-muted" role="status">明细读取已取消，点击刷新继续。</p>}
      {data && <><C.Reasons rows={detailResult.warnings} />
        {!sameCandidate && <>{arrangementsEqual && <div className="rc-empty"><p>工序安排一致。</p>{data.items.length === 0 && <C.Button onClick={() => update({ batch_ref: undefined, change_kind: 'all', delivery_filter: 'all' })}>查看全部批次</C.Button>}</div>}
          {data.items.length ? <BatchList data={data} difference={difference} selectedRef={selectedRef} onSelect={selectBatch} /> : !arrangementsEqual && <div className="rc-empty"><p>{data.page.total > 0 ? '当前页没有批次。' : missingChanges ? changed.reason ? changed.reason.message : '工序安排差值待确认。' : difference ? '没有符合筛选的变化。' : '没有符合筛选的批次。'}</p>
            <C.Button onClick={() => data.page.total > 0 ? update({ page: 1 }, true) : update({ batch_ref: undefined, change_kind: missingChanges ? 'all' : difference ? 'changed' : 'all', delivery_filter: 'all' })}>{data.page.total > 0 ? '返回第 1 页' : missingChanges ? '查看全部批次' : '清除筛选'}</C.Button></div>}
          {data.items.length > 0 && <div className="rc-heading rd-detail-pages"><span className="rc-muted">当前筛选 {data.page.total} 批 · 本页 {data.items.length} 批</span><label>每页<select aria-label="影响明细每页条数" value={q.size} disabled={read.loading} onChange={event => update({ size: Number(event.target.value) })}><option value="20">20 条</option><option value="50">50 条</option></select></label><C.Pager label={difference ? '方案差异批次' : '当前交期与未排'} page={data.page.number} pages={Math.max(1, Math.ceil(data.page.total / data.page.size))} disabled={read.loading} onPage={page => update({ page }, true)} /></div>}
          {retained && <div className="rd-retained-batch"><C.Button className="btn link" onClick={() => selectBatch(selectedRef)}>当前查看：{selected.batch_id}</C.Button></div>}
          {selected && (!arrangementsEqual || chainQuery.change_kind === 'all') && <BatchChain key={(difference ? 'difference:' : 'delivery:') + selected.batch_ref} result={result} batch={selected} difference={difference} query={chainQuery.batch_ref && chainQuery.batch_ref !== selected.batch_ref ? { ...chainQuery, page: 1, snapshot_ref: undefined } : chainQuery} onQuery={onChainQuery} onDrill={onDrill} headingRef={headingRef} enabled={enabled} />}</>}
        <details className="rd-delivery-source"><summary>数据来源</summary><Summary data={data} /></details></>}
    </section>;
  }
  window.RunDecisionDetails = { Pane, BatchList, BatchChain, OperationChain, ChainTimeline, CurrentRisk, Arrangement, Summary, delta };
})();
