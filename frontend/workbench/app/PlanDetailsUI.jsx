(function () {
  'use strict';
  const { Button, Issues } = window.ResourceControls, M = window.PlanGanttModel;
  const riskLabel = { overdue: '预计超期', on_time: '预计按期', unknown: '无法核实' };
  const deliveryIssues = {
    operations_unscheduled: '尚有工序未安排', operations_missing: '工序资料未记录', schedule_time_invalid: '安排时间无效',
    saved_plan_incomplete: '保存的计划不完整', due_date_missing: '交期未记录', due_date_invalid: '交期无效',
    due_date_unspecified: '未指定交期', part_label_missing: '零件名称或图号未记录'
  };
  const issueText = issues => (issues || []).map(issue => typeof issue === 'string' ? deliveryIssues[issue] || '无法核实（' + issue + '）' : issue.message).join('；');
  function Facts({ items }) {
    return <dl className="plan-facts">{items.map(([key, value]) => <React.Fragment key={key}><dt>{key}</dt><dd>{value}</dd></React.Fragment>)}</dl>;
  }
  function CalendarWindows({ windows }) {
    const [open, setOpen] = React.useState(false), [page, setPage] = React.useState(0);
    if (windows === null) return '无法核实';
    return <div><Button className="linkbtn" aria-expanded={open} onClick={() => setOpen(!open)}>{windows.length} 段</Button>
      {open && <>{windows.slice(page * 10, page * 10 + 10).map((item, index) => <div key={index}>{M.timeLabel(item.start)} → {M.timeLabel(item.end)}
        <div className="plan-muted">普通{item.allow_normal ? '允许' : '禁止'} · 急件{item.allow_urgent ? '允许' : '禁止'} · 效率 {M.number(item.efficiency)}</div></div>)}
        {windows.length > 10 && <div className="plan-pager"><Button className="btn plan-icon" icon="chevron-left" aria-label="日历窗口上一段" disabled={!page} onClick={() => setPage(page - 1)} />
          <span>{page + 1}</span><Button className="btn plan-icon" icon="chevron-right" aria-label="日历窗口下一段" disabled={(page + 1) * 10 >= windows.length} onClick={() => setPage(page + 1)} /></div>}</>}
    </div>;
  }
  function Relations({ data, selected, onRelated }) {
    const order = data.projections.process_order;
    const relations = window.PlanProcessOrder.relationships(data, selected);
    return <section aria-label="工艺前后序"><h3>工艺前后序</h3>{relations ? ['previous', 'next'].map(kind => <div key={kind}>
      <h4>{kind === 'previous' ? '前序' : '后序'}</h4>{!relations[kind].length && <p className="plan-muted">{kind === 'previous' ? '无前序工序' : '无后序工序'}</p>}
      <div className="plan-actions">{relations[kind].map((row, index) => {
        const task = row.task, prefix = kind === 'previous' ? '前序' : '后序';
        const label = task ? prefix + ' ' + task.batch_id + ' · ' + task.sequence + ' ' + task.process_label + ' · ' + M.pieceLabel(task) : prefix + '安排在当前读取范围外';
        return row.task_ref ? <Button key={row.task_ref} icon={kind === 'previous' ? 'chevron-left' : 'chevron-right'} title={label} aria-label={label}
          disabled={!onRelated} onClick={() => onRelated(row.task_ref)} style={{ height: 'auto', minHeight: 32, whiteSpace: 'normal', textAlign: 'left', overflowWrap: 'anywhere' }}>
          {task ? label : '读取完整计划并定位' + prefix}</Button> : <span key={'unplanned:' + index} className="plan-muted">{prefix}未在本计划安排</span>;
      })}</div>
    </div>) : <p className="plan-muted">{!selected ? '尚未选中任务' : selected.before ? '当前关系只属于所选计划，初始安排的关系未单独核实。' : order.issues.map(row => row.message).join('；') || '该任务的冻结关系无法核实。'}</p>}</section>;
  }
  function TaskDetail({ data, selected, onSelect, onRelated, renderTrial, scope = {}, query = '', disabled = false }) {
    const task = selected && selected.task, labels = React.useMemo(() => M.names(data), [data]);
    const baseline = data.projections.baseline;
    const comparison = task && baseline.state === 'available' && baseline.items.find(item => item.operation_ref === task.operation_ref);
    const risk = task && data.projections.delivery_risks.items.find(row => row.batch_id === task.batch_id);
    const resources = task ? data.projections.occupancy.resources.filter(row => [task.machine_ref, task.operator_ref].includes(row.resource_ref)) : [];
    return <aside className="plan-inspector" aria-label="任务详情" data-plan-inspector>
      <section><h2>任务详情</h2>{!task ? <div className="plan-empty">尚未选中任务。选中甘特中的安排后，这里显示工艺前后序、初始计划对照、交付风险和资源占用。</div> : <>
        <div className="plan-muted" style={{ marginTop: 9 }}>{selected.before ? '初始计划安排' : '当前所选计划安排'}</div>
        <h3 style={{ marginTop: 4, overflowWrap: 'anywhere' }}>{task.batch_id} · {task.sequence}</h3><p style={{ overflowWrap: 'anywhere' }}>{task.process_label}</p>
        <Facts items={[
          ['分件', <span style={{ overflowWrap: 'anywhere' }}>{M.pieceLabel(task)}</span>],
          ['本工序目标量', M.quantityLabel(task.quantity)], ['计划来源整批量', M.quantityLabel(task.batch_quantity)],
          ['数量依据', task.quantity_reason ? M.quantityReasons[task.quantity_reason] : task.quantity_basis === 'run_admission' ? '原候选受理快照，已核验采用审计与回执' : '原试调创建快照，已核验采用审计与回执'],
          ...(window.PointContract.isPoint(task) ? [['安排类型', '时间点'], ['本工序占用', '0 h · 不占用资源']] : []),
          ['计划开始', M.timeLabel(task.start)], ['计划结束', M.timeLabel(task.end)], ['时间跨度', M.number((M.instant(task.end) - M.instant(task.start)) / 3600000) + ' h'],
          ['设备', M.resourceLabel(task, 'machine', labels)], ['人员', M.resourceLabel(task, 'operator', labels)],
          ['供应商', selected.before && ['candidate_adoption', 'trial_adoption'].includes(baseline.basis)
            ? '未记录' : task.supplier_ref ? labels.get(task.supplier_ref) || '名称未记录' : '未绑定']
        ]} />
        <div className="plan-actions">{typeof renderTrial === 'function' ? renderTrial({ planRef: data.plan.plan_ref, scope, query,
          taskOrigin: { plan_ref: data.plan.plan_ref, operation_ref: task.operation_ref, task_ref: task.task_ref },
          disabled: disabled || selected.before || task.plan_ref !== data.plan.plan_ref, label: '调整此工序' }) :
          <Button icon="square-pen" reason="试调入口未接入，当前只能查看计划。">调整此工序</Button>}</div>
      </>}</section>
      {task && <><Relations data={data} selected={selected} onRelated={onRelated} />
      <section><h3>初始计划对照</h3>{comparison ? <>
        <Facts items={[
          ['变化', ({ added: '新增安排', removed: '移除安排', changed: '安排已变更', unchanged: '安排未变更' })[comparison.change]],
          ['初始开始', comparison.before ? M.timeLabel(comparison.before.start) : '未记录'], ['初始结束', comparison.before ? M.timeLabel(comparison.before.end) : '未记录'],
          ['当前开始', comparison.after ? M.timeLabel(comparison.after.start) : '未记录'], ['当前结束', comparison.after ? M.timeLabel(comparison.after.end) : '未记录']
        ]} />
        {!comparison.before_in_scope && comparison.before && <p className="plan-muted">初始安排在所选时间范围外，仍显示完整起止时间。</p>}
        {!comparison.after_in_scope && comparison.after && <p className="plan-muted">当前安排已移出所选时间范围，仍显示完整起止时间。</p>}
        {comparison.before && !selected.before && <Button icon="arrow-right" onClick={() => onSelect(comparison.before, true)}>查看初始安排</Button>}
        {comparison.after && selected.before && <Button icon="arrow-right" onClick={() => onSelect(comparison.after, false)}>查看当前安排</Button>}
      </> : <p className="plan-muted">{baseline.reason || (task ? '未找到对应对照记录' : '尚未选中任务')}</p>}</section>
      <section><h3>交付风险</h3>{!task ? <p className="plan-muted">尚未选中任务</p> : selected.before ? <p className="plan-muted">当前交付风险属于所选计划，未核实初始计划的交付风险。</p> : risk ? <>
        <Facts items={[
          ['判定', <span className={risk.risk === 'overdue' ? 'plan-danger' : ''}>{riskLabel[risk.risk]}</span>],
          ['交期', risk.due_date || '未记录'], ['计划完工', M.timeLabel(risk.planned_finish)],
          [window.WorkbenchTerms.delay_hours, risk.delay_hours === null ? '未知' : window.WorkbenchFormat.hours(risk.delay_hours, 2)],
          ['未排工序', M.number(risk.unscheduled_operation_count)]
        ]} />
        {risk.partial_planned_finish && <p className="plan-muted">已安排部分的结束时间：{M.timeLabel(risk.partial_planned_finish)}，不代表批次完工。</p>}
        {risk.issues.length > 0 && <p className="plan-muted">{issueText(risk.issues)}</p>}
      </> : <p className="plan-muted">未记录，无法核实</p>}</section>
      <section><h3>资源占用</h3>{window.PointContract.isPoint(task) ? <p className="plan-muted">本工序为时间点，资源占用 0 h。</p> : selected && selected.before ? <p className="plan-muted">初始计划的日历和占用未单独核实。</p> : !resources.length ? <p className="plan-muted">未记录可核实的资源占用</p> : resources.map(row => <div key={row.resource_ref}>
        <strong>{row.label || labels.get(row.resource_ref) || '资源名称未记录'}</strong>
        <Facts items={[
          ['已占时间', M.number(row.occupied_hours) + ' h'], ['可用时间', row.available_hours === null ? '无法核实' : M.number(row.available_hours) + ' h'],
          ['日历内占用', row.utilization === null ? '无法核实' : M.number(row.utilization * 100) + '%'],
          ['重叠时间', <span className={row.has_overlap ? 'plan-danger' : ''}>{M.number(row.overlap_hours)} h</span>]
        ]} />
        <Issues issues={row.issues} />
      </div>)}</section></>}
    </aside>;
  }
  function conflictRows(data) {
    const projection = data.projections.occupancy, scope = data.time_scope;
    const require = value => { if (!value) throw new Error('资源重叠明细的范围或并行依据无法核实，未按零重叠显示。'); };
    require(projection && projection.basis === 'selected_plan_only' && projection.plan_ref === data.plan.plan_ref
      && ['available', 'partial', 'unavailable'].includes(projection.state) && Array.isArray(projection.resources)
      && Array.isArray(projection.issues) && projection.time_scope && scope
      && ['range_start', 'range_end', 'selection', 'boundary', 'time_basis'].every(key => projection.time_scope[key] === scope[key]));
    const start = M.instant(scope.range_start), end = M.instant(scope.range_end), rows = [], seen = new Set();
    require(Number.isFinite(start) && Number.isFinite(end) && start <= end);
    for (const resource of projection.resources) {
      require(resource && ['machine', 'operator'].includes(resource.kind) && typeof resource.resource_ref === 'string'
        && /^[a-f0-9]{48}$/.test(resource.resource_ref) && !seen.has(resource.resource_ref)
        && Array.isArray(resource.segments) && typeof resource.has_overlap === 'boolean');
      seen.add(resource.resource_ref); let overlap = false;
      for (const segment of resource.segments) {
        const low = M.instant(segment.start), high = M.instant(segment.end), count = segment.concurrent_operations;
        require(Number.isFinite(low) && Number.isFinite(high) && start <= low && low < high && high <= end
          && Number.isSafeInteger(count) && count > 0);
        if (count <= 1) continue;
        overlap = true;
        rows.push({ kind: resource.kind, resource_ref: resource.resource_ref, label: resource.label,
          start: segment.start, end: segment.end, concurrent_operations: count });
      }
      require(overlap === resource.has_overlap);
    }
    return { rows, projection };
  }
  function Conflicts({ data }) {
    const [page, setPage] = React.useState(0), read = React.useMemo(() => {
      try { return conflictRows(data); } catch (error) { return { error }; }
    }, [data]);
    if (read.error) return <section className="plan-projections" aria-label="资源重叠明细"><h3>资源重叠明细</h3><window.ResourceControls.ErrorBox error={read.error} /></section>;
    const { rows, projection } = read, current = Math.min(page, Math.max(0, Math.ceil(rows.length / 20) - 1)), labels = M.names(data);
    const known = projection.state === 'available', scope = projection.time_scope;
    const empty = !known ? '当前范围仍有资料无法核实，不能认定为没有重叠。'
      : !projection.resources.length ? '当前读取范围没有资源占用记录。' : '当前读取范围未发现资源安排重叠。';
    return <section className="plan-projections" aria-label="资源重叠明细"><h3>资源重叠明细</h3>
      <div className="plan-note">{M.timeLabel(scope.range_start)} 至 {M.timeLabel(scope.range_end)}（不含结束）
        {data.scope.range_start !== null ? ' · 当前读取切片，不代表整份计划' : ' · 完整计划读取范围'}
        <div>仅列所选计划在该范围的资源安排重叠，不代表等待、停机、缺料或延期原因。</div>
        {!known && <div>{projection.state === 'partial' ? '部分资料无法核实。' : '资源依据不可完整核实。'}以下仅列已核实片段，未知部分不计为零。</div>}</div>
      <Issues issues={projection.issues} />
      {rows.length ? <><div className="plan-projection-table wb-table-frame" data-sticky-head data-sticky-actions><table className="wb-table" aria-label="资源重叠明细"><caption className="wb-visually-hidden">资源重叠明细</caption><thead><tr>
        {['资源', '开始（含）', '结束（不含）', '并行工序'].map((label, index) => <th scope="col" className={index === 0 ? 'wb-col-key' : undefined} key={label}>{label}</th>)}
      </tr></thead><tbody>{rows.slice(current * 20, current * 20 + 20).map(row => <tr key={row.resource_ref + ':' + row.start + ':' + row.end}>
        <td className="wb-col-key">{row.label || labels.get(row.resource_ref) || '资源名称未记录'}<div className="plan-muted">{M.kindLabels[row.kind]}</div></td>
        <td>{M.timeLabel(row.start)}</td><td>{M.timeLabel(row.end)}</td><td>{row.concurrent_operations}</td>
      </tr>)}</tbody></table></div><window.WorkbenchControls.Pager label="重叠明细" page={current + 1} pages={Math.ceil(rows.length / 20)} total={rows.length} size={20} sizes={[20]} unit="段" onPage={next => setPage(next - 1)} /></> : <window.WorkbenchControls.EmptyState kind="empty" title={empty} />}
    </section>;
  }
  function ProjectionTables({ data, onBatch, onResource }) {
    const [tab, setTab] = React.useState('risk'), [page, setPage] = React.useState(0);
    const projections = data.projections, labels = React.useMemo(() => M.names(data), [data]);
    const rows = tab === 'risk' ? projections.delivery_risks.items : tab === 'load' ? projections.occupancy.resources : projections.calendar.resources || [];
    const visible = rows.slice(page * 20, page * 20 + 20);
    const projection = tab === 'risk' ? projections.delivery_risks : tab === 'load' ? projections.occupancy : projections.calendar;
    return <section className="plan-projections" aria-label="计划分析">
      <window.PlanSegmentUI value={tab} options={[["risk", "交付风险"], ["load", "资源负荷"], ["calendar", "资源日历"]]} label="计划分析视图" onChange={value => { setTab(value); setPage(0); }} />
      <div className="plan-note">{tab === 'risk' ? '按所选计划的完整批次安排判定，不代表实际完工或发货。' : tab === 'load' ? '只统计所选计划在此时间范围内的安排；占用率 = 日历内已占时间 / 可用时间。设备有空闲时间不代表人员已就绪。' : '只列出所选时间范围内的可工作时段；普通件、急件能否安排及效率分别记录。'}
        {projection.state !== 'available' && <span> · {projection.state === 'partial' ? '部分资料无法核实' : '无法核实'}</span>}</div>
      <Issues issues={projection.issues || []} />
      <div className="plan-projection-table wb-table-frame" data-sticky-head data-sticky-actions><table className="wb-table" aria-label={tab === 'risk' ? '交付风险列表' : tab === 'load' ? '资源负荷列表' : '资源日历列表'}>
        <caption className="wb-visually-hidden">{tab === 'risk' ? '交付风险列表' : tab === 'load' ? '资源负荷列表' : '资源日历列表'}</caption>
        <thead><tr>{(tab === 'risk' ? ['批次 / 零件', '交期', '计划完工', '交付风险', '未排工序', '证据'] : tab === 'load' ? ['资源', '安排 h', '已占 h', '可用 h', '重叠 h', '日历内占用率'] : ['资源', '可用 h', '普通有效 h', '急件有效 h', '窗口', '证据']).map((label, index) => <th scope="col" className={index === 0 ? 'wb-col-key' : undefined} key={label}>{label}</th>)}</tr></thead>
        <tbody>{visible.map(row => tab === 'risk' ? <tr key={row.batch_ref}>
          <td className="wb-col-key"><Button className="linkbtn" onClick={() => onBatch(row.batch_id)}>{row.batch_id}</Button><div className="plan-muted">{row.part_no || '图号未记录'} · {row.part_label || '名称未记录'}</div></td>
          <td>{window.WorkbenchFormat.date(row.due_date)}</td><td>{M.timeLabel(row.planned_finish)}{row.partial_planned_finish && <div className="plan-muted">已安排部分结束于：{M.timeLabel(row.partial_planned_finish)}</div>}</td>
          <td className={row.risk === 'overdue' ? 'plan-danger' : ''}>{riskLabel[row.risk]}{row.delay_hours !== null && <div>{M.number(row.delay_hours)} h</div>}</td>
          <td>{row.unscheduled_operation_count}</td><td>{issueText(row.issues) || '当前工序安排已覆盖'}</td>
        </tr> : <tr key={row.resource_ref}><td className="wb-col-key"><Button className="linkbtn" onClick={() => onResource(labels.get(row.resource_ref) || '')}>{row.label || labels.get(row.resource_ref) || '名称未记录'}</Button><div className="plan-muted">{M.kindLabels[row.kind]}</div></td>
          {tab === 'load' ? <><td>{M.number(row.arranged_hours)}</td><td>{M.number(row.occupied_hours)}</td><td>{M.number(row.available_hours)}</td><td className={row.has_overlap ? 'plan-danger' : ''}>{M.number(row.overlap_hours)}</td>
            <td>{row.utilization === null ? '未知' : <>{window.WorkbenchFormat.percent(row.utilization)}<span className="plan-meter"><i style={{ width: row.utilization * 100 + '%' }} /></span></>}<div className="plan-muted">{issueText(row.issues)}</div></td></> :
            <><td>{M.number(row.available_hours)}</td><td>{M.number(row.normal_effective_hours)}</td><td>{M.number(row.urgent_effective_hours)}</td><td><CalendarWindows windows={row.windows} /></td>
              <td>{issueText(row.issues) || '已读取真实日历'}</td></>}
        </tr>)}{!visible.length && <tr><td colSpan={6}><window.WorkbenchControls.EmptyState kind="empty" title={projection.state === 'available' ? '所选时间范围内没有记录。' : '资料未记录或无法核实。'} /></td></tr>}</tbody>
      </table></div>
      <window.WorkbenchControls.Pager label="分析" page={page + 1} pages={Math.max(1, Math.ceil(rows.length / 20))} total={rows.length} size={20} sizes={[20]} onPage={next => setPage(next - 1)} />
    </section>;
  }
  window.PlanDetailsUI = { TaskDetail, ProjectionTables, Facts, Conflicts, conflictRows };
})();
