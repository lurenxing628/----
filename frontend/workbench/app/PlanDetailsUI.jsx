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
  function TaskDetail({ data, selected, onSelect }) {
    const task = selected && selected.task, labels = React.useMemo(() => M.names(data), [data]);
    const baseline = data.projections.baseline;
    const comparison = task && baseline.state === 'available' && baseline.items.find(item => item.operation_ref === task.operation_ref);
    const risk = task && data.projections.delivery_risks.items.find(row => row.batch_id === task.batch_id);
    const resources = task ? data.projections.occupancy.resources.filter(row => [task.machine_ref, task.operator_ref].includes(row.resource_ref)) : [];
    return <aside className="plan-inspector" aria-label="任务详情" data-plan-inspector>
      <section><h2>任务详情</h2>{!task ? <div className="plan-empty">尚未选中任务</div> : <>
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
        <div className="plan-actions"><Button icon="square-pen" reason="暂不支持试调，当前只能查看计划。">试调</Button>
          <Button icon="file" reason="暂不支持保存试调，不会保存修改或改变正式计划。">保存</Button></div>
      </>}</section>
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
          ['超期时长', risk.delay_hours === null ? '无法核实' : M.number(risk.delay_hours) + ' h'],
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
      </div>)}</section>
    </aside>;
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
      <div className="plan-projection-table"><table aria-label={tab === 'risk' ? '交付风险列表' : tab === 'load' ? '资源负荷列表' : '资源日历列表'}>
        <thead><tr>{(tab === 'risk' ? ['批次 / 零件', '交期', '计划完工', '交付风险', '未排工序', '证据'] : tab === 'load' ? ['资源', '安排 h', '已占 h', '可用 h', '重叠 h', '日历内占用率'] : ['资源', '可用 h', '普通有效 h', '急件有效 h', '窗口', '证据']).map(label => <th key={label}>{label}</th>)}</tr></thead>
        <tbody>{visible.map(row => tab === 'risk' ? <tr key={row.batch_ref}>
          <td><Button className="linkbtn" onClick={() => onBatch(row.batch_id)}>{row.batch_id}</Button><div className="plan-muted">{row.part_no || '图号未记录'} · {row.part_label || '名称未记录'}</div></td>
          <td>{row.due_date || '未记录'}</td><td>{M.timeLabel(row.planned_finish)}{row.partial_planned_finish && <div className="plan-muted">已安排部分结束于：{M.timeLabel(row.partial_planned_finish)}</div>}</td>
          <td className={row.risk === 'overdue' ? 'plan-danger' : ''}>{riskLabel[row.risk]}{row.delay_hours !== null && <div>{M.number(row.delay_hours)} h</div>}</td>
          <td>{row.unscheduled_operation_count}</td><td>{issueText(row.issues) || '当前工序安排已覆盖'}</td>
        </tr> : <tr key={row.resource_ref}><td><Button className="linkbtn" onClick={() => onResource(labels.get(row.resource_ref) || '')}>{row.label || labels.get(row.resource_ref) || '名称未记录'}</Button><div className="plan-muted">{M.kindLabels[row.kind]}</div></td>
          {tab === 'load' ? <><td>{M.number(row.arranged_hours)}</td><td>{M.number(row.occupied_hours)}</td><td>{M.number(row.available_hours)}</td><td className={row.has_overlap ? 'plan-danger' : ''}>{M.number(row.overlap_hours)}</td>
            <td>{row.utilization === null ? '无法核实' : <>{M.number(row.utilization * 100)}%<span className="plan-meter"><i style={{ width: row.utilization * 100 + '%' }} /></span></>}<div className="plan-muted">{issueText(row.issues)}</div></td></> :
            <><td>{M.number(row.available_hours)}</td><td>{M.number(row.normal_effective_hours)}</td><td>{M.number(row.urgent_effective_hours)}</td><td><CalendarWindows windows={row.windows} /></td>
              <td>{issueText(row.issues) || '已读取真实日历'}</td></>}
        </tr>)}{!visible.length && <tr><td colSpan={6} className="plan-empty">{projection.state === 'available' ? '所选时间范围内没有记录。' : '资料未记录或无法核实。'}</td></tr>}</tbody>
      </table></div>
      <div className="plan-pager"><span>所选时间范围 · {rows.length} 项</span><span className="plan-actions"><Button className="btn plan-icon" icon="chevron-left" aria-label="分析上一页" disabled={page === 0} onClick={() => setPage(page - 1)} />
        <span>{page + 1} / {Math.max(1, Math.ceil(rows.length / 20))}</span><Button className="btn plan-icon" icon="chevron-right" aria-label="分析下一页" disabled={(page + 1) * 20 >= rows.length} onClick={() => setPage(page + 1)} /></span></div>
    </section>;
  }
  window.PlanDetailsUI = { TaskDetail, ProjectionTables, Facts };
})();
