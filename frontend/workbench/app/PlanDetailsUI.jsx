(function () {
  'use strict';
  const { Button, Issues } = window.ResourceControls, M = window.PlanGanttModel;
  const T = window.WorkbenchTerms, F = window.WorkbenchFormat, riskLabel = T.delivery_risks;
  const deliveryIssues = {
    operations_unscheduled: '尚有工序未安排', material_deferred: '因缺料暂未安排', operations_missing: '工序资料未记录', schedule_time_invalid: '安排时间无效',
    saved_plan_incomplete: '保存的计划不完整', due_date_missing: '交期未记录', due_date_invalid: '交期无效',
    part_label_missing: '零件名称或图号未记录'
  };
  const issueText = issues => issues.map(issue => typeof issue === 'string' ? deliveryIssues[issue] || '原因说明缺失' : issue.message).join('；');
  function Facts({ items }) {
    return <dl className="plan-facts">{items.map(([key, value]) => <React.Fragment key={key}><dt>{key}</dt><dd>{value}</dd></React.Fragment>)}</dl>;
  }
  function OccupancyDetails({ row }) {
    return <details className="plan-row-details"><summary>预留跨度明细</summary><Facts items={[
      ['工序区间累加', F.hours(row.arranged_hours, 2)], ['自然跨度已占', F.hours(row.occupied_hours, 2)],
      ['自然跨度重叠', F.hours(row.overlap_hours, 2)], ['班表外预留跨度', row.outside_available_hours === null ? '暂无数据' : F.hours(row.outside_available_hours, 2)]
    ]} /><p className="plan-muted">工序区间累加重复计入重叠跨度，自然跨度已占只计一次；班表外预留跨度可包含休息和夜间等待。</p></details>;
  }
  function TimeValue({ value }) {
    return value ? <time title={M.timeLabel(value)}>{F.compactDateTime(value)}</time> : '暂无数据';
  }
  function CalendarWindows({ windows }) {
    const [open, setOpen] = React.useState(false), [page, setPage] = React.useState(0);
    if (windows === null) return '暂无数据';
    const pages = Math.ceil(windows.length / 10), current = Math.min(page, Math.max(0, pages - 1));
    return <div><Button className="linkbtn" aria-expanded={open} onClick={() => setOpen(!open)}>{windows.length} 段</Button>
      {open && <>{windows.slice(current * 10, current * 10 + 10).map((item, index) => <div key={index} title={M.timeLabel(item.start) + ' 至 ' + M.timeLabel(item.end)}>{F.compactRange(item.start, item.end)}
        <div className="plan-muted">普通件{item.allow_normal ? '允许' : '禁止'} · 急件{item.allow_urgent ? '允许' : '禁止'} · 效率 {F.percent(item.efficiency, { digits: 0 })}</div></div>)}
        {windows.length > 10 && <div className="plan-pager"><Button className="btn plan-icon" icon="chevron-left" aria-label="可工作时段上一段" disabled={!current} onClick={() => setPage(current - 1)} />
          <span>{current + 1}</span><Button className="btn plan-icon" icon="chevron-right" aria-label="可工作时段下一段" disabled={(current + 1) * 10 >= windows.length} onClick={() => setPage(current + 1)} /></div>}</>}
    </div>;
  }
  function DetailSection({ title, collapsible, children }) {
    return collapsible ? <details className="wb-gantt-detail-section"><summary>{title}</summary><div className="wb-gantt-detail-section-body">{children}</div></details>
      : <section><h3>{title}</h3>{children}</section>;
  }
  function Route({ data, prepared, selected, onRelated, disabled, collapsible }) {
    const loadedRefs = React.useMemo(() => prepared && prepared.loadedRefs || new Set(data.tasks.map(task => task.task_ref)), [prepared, data.tasks]);
    if (selected.before) return <section><h3>完整工艺路线</h3><p className="plan-muted">切换到当前安排查看完整工艺路线。</p></section>;
    return <window.GanttRouteList index={prepared.graph} targetRef={selected.task.task_ref} loadedRefs={loadedRefs} onSelect={onRelated} disabled={disabled} collapsible={collapsible} />;
  }
  function TaskDetail({ data, prepared, selected, onSelect, onRelated, onCollapse, renderTrial, scope = {}, query = '', disabled = false }) {
    const task = selected && selected.task, labels = prepared.labels;
    const baseline = data.projections.baseline;
    const comparison = task && baseline.state === 'available' && prepared.comparisons.get(task.operation_ref);
    const changes = [];
    if (comparison && comparison.before && comparison.after) {
      for (const [field, label] of [['start', '开始'], ['end', '结束']]) {
        const delta = comparison.afterTime[field] - comparison.beforeTime[field];
        if (delta) {
          const minutes = Math.abs(delta) >= 60000, value = Math.abs(delta) / (minutes ? 60000 : 1000);
          changes.push([label + '变化', (delta < 0 ? '提前 ' : '延后 ') + window.WorkbenchFormat.number(value, { digits: minutes ? 2 : 6, trim: true }) + (minutes ? ' 分钟' : ' 秒')]);
        }
      }
      for (const [kind, label] of [['machine', '设备'], ['operator', '人员']]) if (comparison.before[kind + '_ref'] !== comparison.after[kind + '_ref'])
        changes.push([label + '变化', M.resourceLabel(comparison.before, kind, labels) + ' → ' + M.resourceLabel(comparison.after, kind, labels)]);
    }
    const risk = task && (prepared.deliveryRisks ? prepared.deliveryRisks.get(task.batch_id) : data.projections.delivery_risks.items.find(row => row.batch_id === task.batch_id));
    const taskFact = task && (comparison ? comparison[selected.before ? 'beforeTime' : 'afterTime'] : prepared.taskIndex.get(task.task_ref));
    const resources = task ? [task.machine_ref, task.operator_ref].map(ref => prepared.occupancy.get(ref)).filter(Boolean).map(value => value.resource) : [];
    const compact = !!onCollapse, panel = React.useRef(null);
    React.useEffect(() => { if (compact && window.matchMedia('(max-width:1050px)').matches) panel.current.scrollIntoView({ block: 'nearest' }); }, [compact]);
    return <aside ref={panel} className={'plan-inspector' + (compact ? ' wb-gantt-detail-panel' : '')} id={compact ? 'plan-gantt-detail' : undefined} aria-label="工序详情" data-plan-inspector data-plan-inspector-empty={!task || undefined} data-wb-scroll-key={compact ? undefined : 'plan-inspector'}>
      {compact && <header className="wb-gantt-detail-header"><h2>工序详情</h2><Button icon="panel-right-close" onClick={onCollapse}>收起详情</Button></header>}
      <div className={compact ? 'wb-gantt-detail-body' : undefined} data-wb-scroll-key={compact ? 'plan-inspector' : undefined}>
      <section>{!compact && <h2>工序详情</h2>}{!task ? <div className="plan-empty">选择批次或甘特中的工序，查看安排详情。</div> : <>
        <div className="plan-muted plan-inspector-kind">{selected.before ? '原安排' : '当前所选计划安排'}</div>
        <h3 className="plan-inspector-title">{task.batch_id} · {task.sequence}</h3><p className="plan-wrap">{task.process_label}</p>
        <Facts items={[
          ['分件', <span className="plan-wrap">{M.pieceLabel(task)}</span>],
          ['本工序目标量', M.quantityLabel(task.quantity, task.quantity_reason)], ...(!compact ? [['计划来源整批量', M.quantityLabel(task.batch_quantity, task.quantity_reason)],
            ['数量依据', task.quantity_reason ? M.quantityReasons[task.quantity_reason] : task.quantity_basis === 'run_admission' ? '来自上次排产候选方案的数据，已核对采用记录' : '来自新增试调草稿时的数据，已核对采用记录']] : []),
          ...(window.PointContract.isPoint(task) ? [['安排类型', '零工时工序'], ['本工序占用', '0 小时 · 不占设备人员']] : []),
          ['预计开始', <TimeValue value={task.start} />], ['预计结束', <TimeValue value={task.end} />], ['安排时长', F.hours((taskFact.end - taskFact.start) / 3600000, 2)],
          ...(!task.supplier_ref ? [['设备', M.resourceLabel(task, 'machine', labels)], ['人员', M.resourceLabel(task, 'operator', labels)]] : []),
          ...(task.supplier_ref || !task.machine_ref && !task.operator_ref && !window.PointContract.isPoint(task) ? [['供应商', task.supplier_ref ? labels.get(task.supplier_ref) || '名称未填写' :
            data.provenance.state === 'unavailable' ? data.provenance.reason : '未记录']] : [])
        ]} />
        <div className="plan-actions">{typeof renderTrial === 'function' ? renderTrial({ planRef: data.plan.plan_ref, scope, query,
          taskOrigin: { plan_ref: data.plan.plan_ref, operation_ref: task.operation_ref, task_ref: task.task_ref },
          disabled: disabled || selected.before || task.plan_ref !== data.plan.plan_ref, label: '调整此工序' }) :
          <Button icon="square-pen" reason={window.WorkbenchTerms.outcomes.unavailable}>调整此工序</Button>}</div>
      </>}</section>
      {task && <><Route data={data} prepared={prepared} selected={selected} onRelated={onRelated} disabled={disabled} collapsible={compact} />
      {compact && <DetailSection title="计划来源" collapsible><Facts items={[
        ['计划来源整批量', M.quantityLabel(task.batch_quantity, task.quantity_reason)],
        ['数量依据', task.quantity_reason ? M.quantityReasons[task.quantity_reason] : task.quantity_basis === 'run_admission' ? '来自上次排产候选方案的数据，已核对采用记录' : '来自新增试调草稿时的数据，已核对采用记录']
      ]} /></DetailSection>}
      {baseline.state === 'available' && <DetailSection title="原安排对照" collapsible={compact}>{comparison ? <>
        <Facts items={[
          ['变化', ({ added: '新增安排', removed: '移除安排', changed: '安排已变更', unchanged: '安排未变更' })[comparison.change]],
          ...changes,
          ['原开始', comparison.before ? <TimeValue value={comparison.before.start} /> : '未记录'], ['原结束', comparison.before ? <TimeValue value={comparison.before.end} /> : '未记录'],
          ['当前开始', comparison.after ? <TimeValue value={comparison.after.start} /> : '未记录'], ['当前结束', comparison.after ? <TimeValue value={comparison.after.end} /> : '未记录']
        ]} />
        {!comparison.before_in_scope && comparison.before && <p className="plan-muted">原安排在所选时间范围外，仍显示完整起止时间。</p>}
        {!comparison.after_in_scope && comparison.after && <p className="plan-muted">当前安排已移出所选时间范围，仍显示完整起止时间。</p>}
        {comparison.before && !selected.before && <Button icon="arrow-right" onClick={() => onSelect(comparison.before, true, true)}>查看原安排</Button>}
        {comparison.after && selected.before && <Button icon="arrow-right" onClick={() => onSelect(comparison.after, false, true)}>查看当前安排</Button>}
      </> : <p className="plan-muted">未找到对应对照记录</p>}</DetailSection>}
      <DetailSection title="交付风险" collapsible={compact}>{selected.before ? <p className="plan-muted">暂无原安排的交付风险数据。</p> : risk ? <>
        <Facts items={[
          ['判定', <span className={risk.risk === 'overdue' ? 'plan-danger' : ''}>{riskLabel[risk.risk]}</span>],
          ['交期', T.due_date(risk.due_date, risk.due_state, risk.due_issue)], [T.arrangement_labels.status, T.delivery_completion_states[risk.completion_state]], [T.arrangement_labels.planned_finish, <TimeValue value={risk.planned_finish} />],
          [T.delay_hours, risk.due_state === 'unspecified' ? '不适用' : risk.delay_hours === null ? '交付待确认' : window.WorkbenchFormat.hours(risk.delay_hours, 2)],
          [T.arrangement_labels.other_unplanned, M.count(risk.ordinary_unscheduled_operation_count)], [T.arrangement_labels.deferred, M.count(risk.deferred_operation_count)]
        ]} />
        {risk.partial_planned_finish && <p className="plan-muted">{T.arrangement_labels.partial_finish}：<TimeValue value={risk.partial_planned_finish} /></p>}
        {risk.issues.length > 0 && <p className="plan-muted">{issueText(risk.issues)}</p>}
      </> : <p className="plan-muted">暂无数据</p>}</DetailSection>
      <DetailSection title="资源总负荷" collapsible={compact}>{window.PointContract.isPoint(task) ? <p className="plan-muted">零工时工序，不占设备人员。</p> : selected.before ? <p className="plan-muted">暂无原安排的班表和资源占用数据。</p> : !resources.length ? <p className="plan-muted">暂无资源占用数据</p> : <><p className="plan-muted">以下汇总覆盖所选时间范围内该资源的全部安排。</p>{resources.map(row => <div key={row.resource_ref}>
        <strong>{row.label || labels.get(row.resource_ref) || '资源名称未填写'}</strong>
        <Facts items={[
          ['班内已占', row.available_occupied_hours === null ? '暂无数据' : F.hours(row.available_occupied_hours, 2)], ['可排总时长', row.available_hours === null ? '暂无数据' : F.hours(row.available_hours, 2)],
          ['占用比例', row.utilization === null ? issueText(row.issues) : F.percent(row.utilization, 2)],
          ['班表内重叠', row.metric_version !== 'decision-resource-v4' ? '旧资料未记录' : row.available_overlap_hours === null ? '待确认'
            : <span className={row.has_overlap ? 'plan-danger' : ''}>{F.hours(row.available_overlap_hours, 2)}</span>]
        ]} />
        <OccupancyDetails row={row} />
        <Issues issues={row.issues} />
      </div>)}</>}</DetailSection></>}</div>
    </aside>;
  }
  function conflictRows(data) {
    const projection = data.projections.occupancy;
    // The read contract validates identities and interval boundaries; the source supplies calendar-bound conflict segments.
    const rows = projection.resources.filter(resource => resource.metric_version === 'decision-resource-v4' && resource.has_overlap === true)
      .flatMap(resource => resource.conflict_segments.map(segment => ({ kind: resource.kind, resource_ref: resource.resource_ref, label: resource.label, ...segment })));
    return { rows, projection };
  }
  function Conflicts({ data, prepared }) {
    const [page, setPage] = React.useState(0);
    const { rows, projection } = React.useMemo(() => conflictRows(data), [data]);
    const current = Math.min(page, Math.max(0, Math.ceil(rows.length / 20) - 1));
    const visible = React.useMemo(() => {
      return rows.slice(current * 20, current * 20 + 20).map(row => {
        const start = M.instant(row.start), end = M.instant(row.end);
        const tasks = (prepared.resourceMembers.get(row.resource_ref) || [])
          .filter(item => item.start < end && item.end > start).map(item => item.task);
        return { row, tasks };
      });
    }, [rows, prepared, current]);
    const labels = prepared.labels;
    const legacy = projection.resources.some(resource => resource.metric_version !== 'decision-resource-v4');
    const known = projection.state === 'available' && !legacy;
    const empty = !known ? '班表内重叠资料未记录，暂无法完整核对。'
      : !projection.resources.length ? '当前读取范围没有资源占用记录。' : '当前读取范围未发现班表内资源安排重叠。';
    return <section className="plan-projections" aria-label="资源重叠明细"><h3>班表内资源重叠明细</h3>
      {!known && <div className="plan-note">{legacy ? '旧资料未保存班表内重叠时段，预留跨度保留在资源负荷详情。' : '部分班表资料缺失，以下为已确认的班表内重叠时段。'}</div>}
      <Issues issues={projection.issues} />
      {rows.length ? <><div className="plan-projection-table wb-table-frame" data-wb-scroll-key="plan-conflict-table" data-sticky-head data-sticky-actions><table className="wb-table" aria-label="资源重叠明细"><caption className="wb-visually-hidden">资源重叠明细</caption><thead><tr>
        {['资源', '同时安排的工序', '重叠时段'].map((label, index) => <th scope="col" className={index === 0 ? 'wb-col-key' : undefined} key={label}>{label}</th>)}
      </tr></thead><tbody>{visible.map(({ row, tasks }) => <tr key={row.resource_ref + ':' + row.start + ':' + row.end}>
        <td className="wb-col-key">{row.label || labels.get(row.resource_ref) || '资源名称未填写'}<div className="plan-muted">{M.kindLabels[row.kind]}</div></td>
        <td>{tasks.map(task => <div key={task.task_ref}>{task.batch_id} · {task.sequence} {task.process_label}</div>)}</td>
        <td title={M.timeLabel(row.start) + ' 至 ' + M.timeLabel(row.end) + '（不含结束时刻）'}>{F.compactRange(row.start, row.end)}</td>
      </tr>)}</tbody></table></div><window.WorkbenchControls.Pager label="重叠明细" page={current + 1} pages={Math.ceil(rows.length / 20)} total={rows.length} size={20} sizes={[20]} unit="段" onPage={next => setPage(next - 1)} /></> : <window.WorkbenchControls.EmptyState kind="empty" title={empty} />}
    </section>;
  }
  function ProjectionTables({ data, prepared, onBatch, onResource, tab = 'risk', onTab, page = 0, onPage }) {
    const projections = data.projections, labels = prepared.labels;
    const rows = tab === 'risk' ? projections.delivery_risks.items : tab === 'load' ? projections.occupancy.resources : projections.calendar.resources || [];
    const pages = Math.max(1, Math.ceil(rows.length / 20)), current = Math.min(page, pages - 1);
    const visible = rows.slice(current * 20, current * 20 + 20);
    const projection = tab === 'risk' ? projections.delivery_risks : tab === 'load' ? projections.occupancy : projections.calendar;
    return <section className="plan-projections" aria-label="计划分析">
      <window.PlanSegmentUI value={tab} options={[["risk", "交付风险"], ["load", "资源负荷"], ["calendar", "资源班表"]]} label="计划分析视图" onChange={value => { onTab(value); onPage(0); }} />
      {projection.state !== 'available' && <div className="plan-note">{projection.state === 'not_applicable' ? '当前范围未指定有效交期。' : projection.state === 'partial' ? '部分资料缺失，查看下方原因。' : '资料缺失，暂无法判断。'}</div>}
      {tab === 'load' && <details className="plan-table-help"><summary>负荷怎么算</summary><div>
        <p>占用比例 = 班表内已占时间 ÷ 可排总时长。同一资源的重叠安排只计一次已占时间。</p>
        <p>班表内重叠表示同一资源在可排时段内同时安排多道工序的时间；跨班表的预留跨度保留在详情。</p>
      </div></details>}
      {tab === 'calendar' && <details className="plan-table-help"><summary>班表怎么算</summary><div>
        <p>可排总时长是允许排产的时段长度，已扣除停机和停用时间。</p>
        <p>折算标准工时按许可时段乘以效率计算。普通件和急件可共用同一时段，两项不能相加。</p>
      </div></details>}
      <Issues issues={projection.issues || []} />
      <div className="plan-projection-table wb-table-frame" data-wb-scroll-key="plan-projection-table" data-sticky-head data-sticky-actions><table className="wb-table" aria-label={tab === 'risk' ? '交付风险列表' : tab === 'load' ? '资源负荷列表' : '资源班表列表'}>
        <caption className="wb-visually-hidden">{tab === 'risk' ? '交付风险列表' : tab === 'load' ? '资源负荷列表' : '资源班表列表'}</caption>
        <thead><tr>{(tab === 'risk' ? ['批次 / 零件', '交期', '工序安排 / 预计完工', '交付风险', '未安排', '原因'] : tab === 'load' ? ['资源', '可排总时长（小时）', '班内已占（小时）', '占用比例', '异常', '详情'] : ['资源', '可排总时长（小时）', '可排时段', '详情']).map((label, index) => <th scope="col" className={index === 0 ? 'wb-col-key' : undefined} key={label}>{label}</th>)}</tr></thead>
        <tbody>{visible.map(row => tab === 'risk' ? <tr key={row.batch_ref}>
          <td className="wb-col-key"><Button className="linkbtn" onClick={() => onBatch(row.batch_id)}>{row.batch_id}</Button><div className="plan-muted">{row.part_no || '图号未填写'} · {row.part_label || '名称未填写'}</div></td>
          <td>{T.due_date(row.due_date, row.due_state, row.due_issue)}</td><td>{T.delivery_completion_states[row.completion_state]}{row.planned_finish && <div><TimeValue value={row.planned_finish} /></div>}{row.partial_planned_finish && <div className="plan-muted">{T.arrangement_labels.partial_finish}：<TimeValue value={row.partial_planned_finish} /></div>}</td>
          <td className={row.risk === 'overdue' ? 'plan-danger' : ''}>{riskLabel[row.risk]}{row.delay_hours > 0 && <div>{F.hours(row.delay_hours, 2)}</div>}</td>
          <td>{row.unscheduled_operation_count} 道{row.ordinary_unscheduled_operation_count > 0 && <div className="plan-muted">{T.arrangement_labels.other_unplanned} {row.ordinary_unscheduled_operation_count} 道</div>}{row.deferred_operation_count > 0 && <div className="plan-muted">{T.arrangement_labels.deferred} {row.deferred_operation_count} 道</div>}</td>
          <td>{issueText(row.issues.filter(issue => !['operations_unscheduled', 'material_deferred'].includes(issue)))}</td>
        </tr> : <tr key={row.resource_ref}><td className="wb-col-key"><Button className="linkbtn" onClick={() => onResource(row)}>{row.label || labels.get(row.resource_ref) || '名称未填写'}</Button><div className="plan-muted">{M.kindLabels[row.kind]}</div></td>
          {tab === 'load' ? <><td>{M.number(row.available_hours)}</td><td>{M.number(row.available_occupied_hours)}</td>
            <td>{row.utilization === null ? '待确认' : <>{F.percent(row.utilization, 2)}<span className="plan-meter"><i style={{ width: row.utilization * 100 + '%' }} /></span></>}</td>
            <td>{row.metric_version !== 'decision-resource-v4' ? <div className="plan-muted">班表内重叠未记录</div>
              : row.has_overlap === true && <div className="plan-danger">班表内重叠 {F.hours(row.available_overlap_hours, 2)}</div>}{row.issues.length > 0 && <div className="plan-muted">{issueText(row.issues)}</div>}</td>
            <td><OccupancyDetails row={row} /></td></> :
            <><td>{M.number(row.available_hours)}</td><td><CalendarWindows windows={row.windows} /></td>
              <td><details className="plan-row-details"><summary>折算标准工时</summary><Facts items={[
                ['普通件', row.normal_effective_hours === null ? '暂无数据' : F.hours(row.normal_effective_hours, 2)],
                ['急件', row.urgent_effective_hours === null ? '暂无数据' : F.hours(row.urgent_effective_hours, 2)]
              ]} /></details>{row.issues.length > 0 && <div className="plan-muted">{issueText(row.issues)}</div>}</td></>}
        </tr>)}{!visible.length && <tr><td colSpan={tab === 'calendar' ? 4 : 6}><window.WorkbenchControls.EmptyState kind="empty" title={projection.state === 'available' ? '所选时间范围内没有记录。' : '资料未记录或读不到，暂无数据。'} /></td></tr>}</tbody>
      </table></div>
      <window.WorkbenchControls.Pager label="分析" page={current + 1} pages={pages} total={rows.length} size={20} sizes={[20]} onPage={next => onPage(next - 1)} />
    </section>;
  }
  window.PlanDetailsUI = { TaskDetail, ProjectionTables, Facts, Conflicts, conflictRows };
})();
