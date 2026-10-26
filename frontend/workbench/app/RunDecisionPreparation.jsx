(function () {
  'use strict';
  const C = window.RunCandidateControls, D = window.RunDecisionComparison, E = window.RunOperationEffort, M = window.RunCandidateModel, T = window.WorkbenchTerms, F = window.WorkbenchFormat;
  const prepKeys = ['pending_setup_hours', 'scheduled_setup_hours', 'unplanned_setup_hours', 'deferred_setup_hours', 'pending_processing_hours', 'scheduled_processing_hours', 'unplanned_processing_hours', 'deferred_processing_hours'];
  const labels = { pending_setup_hours: '本次准备标准工时需求', scheduled_setup_hours: '新安排准备标准工时', unplanned_setup_hours: '其他未安排准备标准工时', deferred_setup_hours: '缺料未安排准备标准工时', pending_processing_hours: '本次加工标准工时需求', scheduled_processing_hours: '新安排加工标准工时', unplanned_processing_hours: '其他未安排加工标准工时', deferred_processing_hours: '缺料未安排加工标准工时', type_changeover_count: T.changeover_count, changed_machine_count: '发生工种切换的设备数' };
  const prepSorts = [['sequence', '工序顺序'], ['batch_id', '批次编号'], ['after_setup_hours', '当前准备工时'], ['after_required_hours', '当前标准需求'], ['setup_delta_hours', '准备工时变化']];
  const eventSorts = [['next_start', '后序开始'], ['machine_label', '设备名称'], ['next_batch_id', '后序批次']];
  const queryKeys = ['page', 'size', 'sort', 'order', 'machine_ref', 'batch_ref', 'allocation_state', 'work_scope', 'event_side', 'snapshot_ref'];
  function definition(key, definitions) {
    return definitions && definitions.find(row => row.key === key) || { key, label: labels[key], precision: 3, unit: key.endsWith('_hours') ? '小时' : key === 'changed_machine_count' ? '台' : '次', source: key.endsWith('_hours') ? 'runtime_operation_effort' : 'archived_changeover_events' };
  }
  function RoleTotals({ data }) {
    const roles = data.summary.role_totals;
    return <details className="rd-preparation-roles"><summary>保留原安排与报工工序</summary><div className="rd-preparation-role-grid">{['retained', 'execution', 'completed'].map(role => <div key={role}><strong>{T.effort_roles[role]}</strong>{['before', 'after'].map(side => <div key={side}><small>{side === 'before' ? '基准' : '当前方案'}</small>{side === 'before' && data.baseline.state !== 'available' ? <span>比较基准缺失</span> : <><span>{roles[side][role].count} 道工序</span>{['setup_standard_hours', 'processing_standard_hours', 'required_standard_hours'].map(key => <div key={key}><small>{T.operation_effort_labels[key]}</small><D.Metric metric={roles[side][role][key]} definition={{ key, label: T.operation_effort_labels[key], source: 'runtime_operation_effort', unit: '小时', precision: 3 }} /></div>)}</>}</div>)}</div>)}</div></details>;
  }
  function PreparationSummary({ data, definitions, keys, record = false }) {
    return <div className="rc-table wb-table-frame rd-preparation-summary-frame" data-sticky-head><table className="wb-table rd-preparation-summary-table" aria-label="准备与加工工时汇总"><caption className="wb-visually-hidden">本次全部工序的准备与加工工时对照</caption>
      <thead><tr><th scope="col">本次全部工序 · 小时</th><th scope="col">比较基准</th><th scope="col">当前方案</th><th scope="col">差值</th></tr></thead>
      <tbody>{keys.map(key => { const def = definition(key, definitions); return <tr key={key} data-preparation-summary={record ? key : undefined} data-preparation-highlight={record ? undefined : key}><th scope="row"><strong>{def.label}</strong><details className="rd-summary-basis"><summary aria-label={def.label + '依据'}>依据</summary><div><strong>基准</strong>{data.baseline.state !== 'available' ? <span>{D.referenceNotice(data)}</span> : <D.Metric metric={data.summary.before[key]} definition={def} />}<strong>当前方案</strong><D.Metric metric={data.summary.after[key]} definition={def} delta={data.summary.deltas[key]} /></div></details></th>
        <td>{data.baseline.state !== 'available' ? <span title={D.referenceNotice(data)}>比较基准缺失</span> : <D.CompactValue metric={data.summary.before[key]} definition={def} />}</td><td><D.CompactValue metric={data.summary.after[key]} definition={def} /></td><td className={'rd-change rd-' + data.summary.deltas[key].direction}>{D.deltaText(data.summary.deltas[key], def)}</td></tr>; })}</tbody></table></div>;
  }
  function Summary({ data, definitions, section }) {
    if (section === 'preparation') {
      const meaningful = ['scheduled_setup_hours', 'unplanned_setup_hours', 'deferred_setup_hours'].filter(key => ['before', 'after'].some(side => (side === 'after' || data.baseline.state === 'available') && (data.summary[side][key].value === null || data.summary[side][key].value > 0)));
      return <>{meaningful.length > 0 && <PreparationSummary data={data} definitions={definitions} keys={meaningful} />}<details className="rd-effort-record"><summary>全部工时汇总</summary><PreparationSummary data={data} definitions={definitions} keys={prepKeys} record /></details></>;
    }
    const keys = ['type_changeover_count', 'changed_machine_count'];
    return <><div className="rd-preparation-summary rd-changeover-summary">{keys.map(key => {
      const def = definition(key, definitions);
      return <div key={key}><strong>{def.label}</strong><div className="rd-effort-pair"><div><small>比较基准</small>{data.baseline.state !== 'available' ? <span>{D.referenceNotice(data)}</span> : <D.Metric metric={data.summary.before[key]} definition={def} />}</div>
        <div><small>当前方案</small><D.Metric metric={data.summary.after[key]} definition={def} delta={data.summary.deltas[key]} /></div></div></div>;
    })}</div><div className="rd-changeover-diagnostics">{['before', 'after'].map(side => {
      // 换型汇总两侧恒带 issues 列表（decision_changeovers.py public_summary ← changeover_events.py changeover_projection）。
      const issues = data.summary[side].issues;
      return issues.length > 0 && (side !== 'before' || data.baseline.state === 'available') && <div key={side}><strong>{side === 'before' ? '基准' : '当前方案'}设备安排资料缺失</strong><C.Reasons rows={issues} /></div>;
    })}</div></>;
  }
  function Difference({ value }) {
    const keys = ['setup_standard_hours', 'processing_standard_hours', 'required_standard_hours'];
    const pending = keys.filter(key => value[key].value === null), explained = keys.filter(key => value[key].reason);
    const causes = explained.filter((key, index) => explained.findIndex(other => value[other].reason.message === value[key].reason.message) === index);
    return <>
      {pending.length > 0 && <span className="rc-muted">{pending.length === keys.length ? '差值待确认' : '部分差值待确认'}</span>}
      {keys.filter(key => value[key].value !== null).map(key => <div key={key}><small>{T.operation_effort_labels[key]}</small>
        <span className={'rd-change rd-' + value[key].direction}>{D.deltaText(value[key], { source: 'runtime_operation_effort', unit: '小时', precision: 3 })}</span></div>)}
      {(pending.length > 0 || explained.length > 0) && <details className="rd-effort-record"><summary>差值计算依据</summary>
        {keys.map(key => <div key={key}><strong>{T.operation_effort_labels[key]}</strong><dl>{[
          ['reference_value', '基准原值'], ['selected_value', '当前原值'], ['value', '保存差值'],
        ].map(([field, label]) => <div key={field}><dt>{label}</dt><dd title={value[key][field] === null ? undefined : String(value[key][field])}>{value[key][field] === null ? '—' : E.amount(value[key][field], ' 小时')}</dd></div>)}</dl>
          <window.WorkbenchReference entries={{ '保存状态': value[key].state, '变化方向': value[key].direction }} /></div>)}
        {causes.map(key => <div key={key}><strong>{explained.filter(other => value[other].reason.message === value[key].reason.message).map(other => T.operation_effort_labels[other]).join(' / ')}</strong>
          <C.Reasons rows={[value[key].reason]} /></div>)}
      </details>}
    </>;
  }
  function Locate({ drill, onDrill }) {
    return onDrill && <div className="rd-locate"><C.Button icon="chart-gantt" className="mini" onClick={() => onDrill(drill.selected)}>查看当前甘特</C.Button><C.Button icon="chart-gantt" className="mini" disabled={!drill.reference} onClick={() => onDrill(drill.reference)}>查看对照甘特</C.Button></div>;
  }
  function PreparationTable({ data, onDrill }) {
    const [openOperation, setOpenOperation] = React.useState(null);
    React.useEffect(() => { setOpenOperation(null); }, [data]);
    return <><p className="rd-preparation-direction">工时：对照 → 当前；相同值显示一次。</p><div className="rc-table wb-table-frame rd-preparation-frame" data-sticky-head data-sticky-key data-sticky-actions><table className="wb-table rd-preparation-table" aria-label="逐道准备与加工需求"><caption className="wb-visually-hidden">逐道工序准备与加工工时及安排方式</caption>
      <thead><tr><th scope="col" className="wb-col-key">批次 / 工序</th><th scope="col">准备工时<small>小时</small></th><th scope="col">加工工时<small>小时</small></th><th scope="col">合计<small>小时</small></th><th scope="col">安排状态</th><th scope="col" className="wb-col-actions">查看</th></tr></thead>
      <tbody>{data.items.map(row => <React.Fragment key={row.operation_ref}><tr data-decision-preparation={row.operation_ref}><td className="wb-col-key">{onDrill ? <C.Button className="btn link" data-preparation-operation={row.operation_ref} onClick={() => onDrill(row.drill.selected)}>{row.batch_label} · {E.amount(row.sequence)} {row.process_label || T.name_missing}</C.Button> : <strong>{row.batch_label} · {E.amount(row.sequence)} {row.process_label || T.name_missing}</strong>}<small>{row.part_label || T.name_missing} · {M.pieceLabel(row)}</small></td>
        {['setup_standard_hours', 'processing_standard_hours', 'required_standard_hours'].map(key => <td key={key} className="rd-preparation-hours"><strong>{data.baseline.state === 'available' && row.before[key] !== row.after[key] && <>{row.before[key] === null ? E.hours(row.before[key], row.before.state) : E.amount(row.before[key])} → </>}{row.after[key] === null ? E.hours(row.after[key], row.after.state) : E.amount(row.after[key])}</strong></td>)}
        <td><strong>{T.preparation_allocations[row.after.allocation_state]}</strong></td><td className="wb-col-actions"><C.Button className="mini" aria-expanded={openOperation === row.operation_ref} data-preparation-detail={row.operation_ref} onClick={() => setOpenOperation(openOperation === row.operation_ref ? null : row.operation_ref)}>工时详情</C.Button>{onDrill && <C.Button icon="chart-gantt" className="mini" onClick={() => onDrill(row.drill.selected)}>看甘特</C.Button>}</td></tr>
        {openOperation === row.operation_ref && <tr className="rd-preparation-expanded"><td colSpan={6}><div className="rd-preparation-effort-pair"><div><h4>对照</h4><E.Effort value={row.before} absent={data.baseline.state !== 'available'} showMachines /></div><div><h4>当前方案</h4><E.Effort value={row.after} showMachines /></div></div><Difference value={row.deltas} />{row.data_gaps.length > 0 && <C.Reasons rows={row.data_gaps} />}<window.WorkbenchReference value={row.operation_ref} /><Locate drill={row.drill} onDrill={onDrill} /></td></tr>}</React.Fragment>)}</tbody></table></div></>;
  }
  function EventOperation({ row, start, end }) {
    return <><strong>{row.batch_label || '批次未记录'} · {row.process_label || T.name_missing}</strong><small>工种 {row.type_label || '工种未记录'}</small><span title={F.dateTime(start, { seconds: true, fractions: true }) + ' 至 ' + F.dateTime(end, { seconds: true, fractions: true })}>{F.compactRange(start, end)}</span></>;
  }
  function ChangeoverTable({ data, onDrill }) {
    const [openEvent, setOpenEvent] = React.useState(null);
    React.useEffect(() => { setOpenEvent(null); }, [data]);
    return <div className="rc-table wb-table-frame rd-changeover-frame" data-sticky-head data-sticky-key data-sticky-actions><table className="wb-table rd-changeover-table" aria-label="设备工种切换"><caption className="wb-visually-hidden">设备工种切换，包含范围开始前的前序工序</caption>
      <thead><tr><th scope="col" className="wb-col-key">设备 / 方案</th><th scope="col">切换时间</th><th scope="col">前一道工序 → 后一道工序</th><th scope="col">异常</th><th scope="col" className="wb-col-actions">查看</th></tr></thead>
      <tbody>{data.items.map(row => <React.Fragment key={row.event_ref}><tr data-decision-changeover={row.event_ref}><td className="wb-col-key"><strong>{row.machine_label || T.name_missing}</strong><small>{T.changeover_sides[row.event_side]}</small></td>
        <td><span title={F.dateTime(row.next_start, { seconds: true, fractions: true })}>{F.dateTime(row.next_start)}</span></td><td><div className="rd-changeover-flow">{onDrill ? <><C.Button className="btn link" data-changeover-operation={row.previous_operation_ref} onClick={() => onDrill(row.drill.previous)}>{row.previous.batch_label || '批次未记录'} · {row.previous.process_label || T.name_missing}</C.Button><span aria-hidden="true">→</span><C.Button className="btn link" data-changeover-operation={row.next_operation_ref} onClick={() => onDrill(row.drill.next)}>{row.next.batch_label || '批次未记录'} · {row.next.process_label || T.name_missing}</C.Button></> : <span>{row.previous.batch_label} · {row.previous.process_label} → {row.next.batch_label} · {row.next.process_label}</span>}</div><small>{row.previous.type_label || '工种未记录'} → {row.next.type_label || '工种未记录'}</small></td>
        <td>{row.predecessor_outside_window && <small>前序在范围外</small>}{row.overlap !== false && <small>{row.overlap === null ? '重叠待确认' : '前后安排重叠'}</small>}{row.state !== 'complete' && <small>资料待确认</small>}</td>
        <td className="wb-col-actions"><C.Button className="mini" data-changeover-detail={row.event_ref} aria-expanded={openEvent === row.event_ref} onClick={() => setOpenEvent(openEvent === row.event_ref ? null : row.event_ref)}>切换详情</C.Button>{onDrill && <div className="rd-locate"><C.Button icon="chart-gantt" className="mini" onClick={() => onDrill(row.drill.previous)}>看前序甘特</C.Button><C.Button icon="chart-gantt" className="mini" onClick={() => onDrill(row.drill.next)}>看后序甘特</C.Button></div>}</td></tr>
        {openEvent === row.event_ref && <tr className="rd-preparation-expanded"><td colSpan={5}><div className="rd-changeover-times"><div><h4>前一道工序</h4><EventOperation row={row.previous} start={row.previous_start} end={row.previous_end} /></div><div><h4>后一道工序</h4><EventOperation row={row.next} start={row.next_start} end={row.next_end} /></div></div><C.Reasons rows={row.data_gaps} /><window.WorkbenchReference entries={{ '设备': row.machine_ref, '前序工序': row.previous_operation_ref, '后序工序': row.next_operation_ref, '前序安排': row.previous_row_ref, '后序安排': row.next_row_ref }} /></td></tr>}</React.Fragment>)}</tbody></table></div>;
  }
  function Pane({ adapter, result, section, query, onQuery, onDrill, enabled = true }) {
    const overview = result.data, scope = overview.scope, runRef = overview.run.run_ref, preparation = section === 'preparation';
    const shared = { comparison_mode: scope.comparison_mode, resource_view: scope.resource_view, selected_candidate_ref: scope.selected_candidate_ref, range_start: scope.range_start, range_end: scope.range_end,
      ...(scope.comparison_mode === 'candidates' ? { reference_candidate_ref: scope.reference.candidate_ref } : {}) };
    const stored = Object.fromEntries(Object.entries(query).filter(([key]) => queryKeys.includes(key))), q = window.RunDecisionAPI.preparationScope(runRef, { ...stored, ...shared }, section);
    const [paused, setPaused] = React.useState(false), key = JSON.stringify(q);
    React.useEffect(() => { setPaused(false); }, [runRef, key, section, result.meta.snapshot_ref]);
    const read = window.APSResourceSession.useQuery(signal => adapter[section](runRef, q, signal), [adapter, runRef, key, section, result.meta.snapshot_ref], enabled && !paused), detail = read.result, data = detail && detail.data;
    function update(change, paging = false) {
      const next = { ...q, ...change, page: paging ? change.page : 1 }; delete next.snapshot_ref;
      if (paging && detail) next.snapshot_ref = detail.meta.snapshot_ref;
      setPaused(false); onQuery(Object.fromEntries(Object.entries(next).filter(([name]) => queryKeys.includes(name))));
    }
    function reload() { update({}); read.reload(); }
    const options = data && data.filter_options, sorts = preparation ? prepSorts : eventSorts;
    return <section className="rd-preparation" aria-label={preparation ? '准备需求明细' : '工种切换明细'}><div className="rd-detail-filters">
      {preparation && <><label>需求范围<select aria-label="准备需求范围" value={q.work_scope} disabled={read.loading} onChange={event => update({ work_scope: event.target.value })}><option value="all">本次全部工序</option><option value="remaining">未安排工序（含缺料）</option></select></label>
        <label>批次<select aria-label="准备需求批次" value={q.batch_ref || ''} disabled={read.loading || !data} onChange={event => update({ batch_ref: event.target.value || undefined })}><option value="">全部批次</option>{options && options.batches.map(row => <option key={row.ref} value={row.ref}>{row.label || T.name_missing}</option>)}</select></label></>}
      <label>设备<select aria-label="准备与切换设备" value={q.machine_ref || ''} disabled={read.loading || !data} onChange={event => update({ machine_ref: event.target.value || undefined })}><option value="">全部设备</option>{options && options.machines.map(row => <option key={row.ref} value={row.ref}>{row.label || T.name_missing}</option>)}</select></label>
      {preparation ? <label>安排状态<select aria-label="准备需求安排状态" value={q.allocation_state} disabled={read.loading} onChange={event => update({ allocation_state: event.target.value })}><option value="all">全部安排方式</option>{Object.entries(T.preparation_allocations).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        : <label>方案<select aria-label="工种切换方案" value={q.event_side} disabled={read.loading} onChange={event => update({ event_side: event.target.value })}><option value="all">双方安排</option>{Object.entries(T.changeover_sides).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>}
      <details className="rd-preparation-more"><summary>排序与分页</summary><div className="rd-detail-filters"><label>排序<select aria-label="准备与切换排序" value={q.sort} disabled={read.loading} onChange={event => update({ sort: event.target.value })}>{sorts.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      <label>顺序<select aria-label="准备与切换排序顺序" value={q.order} disabled={read.loading} onChange={event => update({ order: event.target.value })}><option value="asc">升序</option><option value="desc">降序</option></select></label>
      </div></details>
      <div className="rc-tools rd-detail-actions">{data && <D.Export key={detail.meta.snapshot_ref} adapter={adapter} result={detail} initialSection={section} filterQuery={q} />}<C.Button icon="refresh-cw" aria-label="刷新准备与切换明细" disabled={read.loading} onClick={reload} /></div></div>
      <C.ErrorBox error={read.error} />{read.loading && <div className="rc-tools"><span role="status">正在读取{preparation ? '工序准备需求' : '设备工种切换'}。</span><C.Button icon="x" onClick={() => setPaused(true)}>取消读取</C.Button></div>}{paused && <p className="rc-muted" role="status">读取已取消，点击刷新继续。</p>}
      {data && <><Summary data={data} definitions={overview.metric_definitions} section={section} /><C.Reasons rows={detail.warnings} />
        {data.items.length ? preparation ? <PreparationTable data={data} onDrill={onDrill} /> : <ChangeoverTable data={data} onDrill={onDrill} /> : <p className="rc-empty">当前筛选下没有{preparation ? '准备需求工序' : '工种切换事件'}。</p>}
        <div className="rc-heading rd-detail-pages"><span className="rc-muted">当前筛选 {data.page.total} 条 · 本页 {data.items.length} 条</span><div className="rc-tools"><label>每页<select aria-label="准备与切换每页条数" value={q.size} disabled={read.loading} onChange={event => update({ size: Number(event.target.value) })}><option value="20">20 条</option><option value="50">50 条</option></select></label><C.Pager label={preparation ? '准备需求' : '工种切换'} page={data.page.number} pages={Math.max(1, Math.ceil(data.page.total / data.page.size))} disabled={read.loading} onPage={page => update({ page }, true)} /></div></div>
        {preparation && <RoleTotals data={data} />}<details className="rd-effort-record"><summary>计算范围</summary><p>{preparation ? '工时汇总包含本次全部工序；明细按上方条件筛选。未安排工序包含缺料和其他原因，数量与工时沿用排产时保存记录。' : '按后序工序的开始时间筛选切换记录，包含范围开始前的前序工序。范围开始时间包含在内，结束时间不包含在内。'}</p></details></>}
    </section>;
  }
  window.RunDecisionPreparation = { Pane, Summary, PreparationTable, ChangeoverTable, RoleTotals, Difference };
})();
