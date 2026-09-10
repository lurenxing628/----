(function () {
  'use strict';
  const C = window.FieldContract, { Button, ErrorBox, Issues, State } = window.FieldControls;
  function Timeline({ task }) {
    const [selected, setSelected] = React.useState(null), [tip, setTip] = React.useState(null);
    const parse = value => value ? Date.parse(value.replace(' ', 'T') + 'Z') : null;
    const plan = { ...task, start: task.planned_start, end: task.planned_end };
    const rows = [{ key: 'plan', label: '计划安排', start: plan.start, end: plan.end, point: window.PointContract.isPoint(plan) },
      ...task.execution.reports.map(row => ({ key: row.report_ref, label: row.report_no, start: row.actual_start, end: row.actual_end,
        point: !!row.actual_start && (!row.actual_end || row.actual_start === row.actual_end) }))];
    const points = rows.flatMap(row => [parse(row.start), parse(row.end)]).filter(Number.isFinite);
    const axis = window.PointGanttModel.bounds(Math.min(...points), Math.max(...points), rows.some(row => row.point));
    function hover(title, event) {
      if (!event) { setTip(null); return; }
      const rect = event.currentTarget.getBoundingClientRect();
      setTip({ title, x: rect.left, y: rect.bottom });
    }
    return <div className="field-timeline" aria-label="作业时间线"><window.PointGantt.Styles /><style>{`
      .field-timeline .field-timeline-track{height:26px}.field-timeline .field-timeline-track i{min-width:0}
      .field-timeline .field-point-tip{position:fixed;z-index:200;max-width:320px;padding:8px;background:var(--ui-card-bg);color:var(--ui-text);border:1px solid var(--ui-border);white-space:pre-line;overflow-wrap:anywhere;pointer-events:none}
    `}</style><div className="field-timeline-axis"><span>{C.date(new Date(Math.min(...points)).toISOString().slice(0, 19))}</span><span>{C.date(new Date(Math.max(...points)).toISOString().slice(0, 19))}</span></div>
      {rows.map(row => {
        const title = (row.key === 'plan' ? row.point ? '计划点 · 0 秒 · 不占用排产资源；完成状态以实际记录为准' : '计划安排' : row.point ? '报工时点' : '实际报工时段')
          + '\n' + row.label + '\n' + C.date(row.start) + ' 至 ' + (row.end ? C.date(row.end) : '结束未填写');
        const left = ((parse(row.start) - axis.start) / (axis.end - axis.start)) * 100 + '%';
        return <div key={row.key} className="field-timeline-row"><span>{row.label}</span><div className="field-timeline-track" title={title}>
          {!row.start ? <span>实际开工待补</span> : row.point ? <window.PointGantt.Marker
            task={row.key === 'plan' ? plan : { task_ref: row.key, start: row.start }} x={left} top={0} title={title}
            tone={row.key === 'plan' ? 'plan' : ''} selected={selected === row.key} data-field-point={row.key === 'plan' ? 'plan' : 'report'}
            data-task-ref={task.task_ref} data-report-ref={row.key === 'plan' ? undefined : row.key}
            onSelect={() => setSelected(row.key)} onHover={event => hover(title, event)} onFocus={event => hover(title, event)} onBlur={() => setTip(null)} />
            : <i className={row.key === 'plan' ? 'planned' : 'actual'} style={{ left, width: ((parse(row.end) - parse(row.start)) / (axis.end - axis.start)) * 100 + '%' }} />}
        </div><span>{row.end ? '' : '结束待补'}</span></div>;
      })}
      {tip && <div className="field-point-tip" role="tooltip" style={{ left: Math.max(8, Math.min(tip.x, window.innerWidth - 336)), top: Math.max(8, Math.min(tip.y + 8, window.innerHeight - 170)) }}>{tip.title}</div>}
    </div>;
  }
  function History({ record }) {
    return <div className="field-history"><dl><dt>录入时间</dt><dd>{C.date(record.recorded_at)}</dd><dt>本机操作者</dt><dd>{C.display(record.local_operator)}</dd><dt>现场声明人</dt><dd>{C.display(record.declared_operator)}</dd><dt>录入来源</dt><dd>{record.source === 'excel' ? 'Excel' : '手工'}</dd></dl>
        {record.correction_history.map((item, index) => <div key={index}><strong>{item.action === 'supplement' ? '补齐' : item.action === 'create' ? '新增' : '更正'}</strong> {C.date(item.recorded_at)} · {item.reason}
          {item.before && item.after && <dl>{C.fields.filter(key => item.before[key] !== item.after[key]).map(key => <React.Fragment key={key}><dt>{({ completed_quantity: '数量', effective_processing_hours: '有效工时', actual_start: '实际开工', actual_end: '本次完工', actual_machine_ref: '实际设备', actual_operator_ref: '实际人员', remark: '备注' })[key]}</dt><dd>{key.endsWith('_ref') ? '资源已更正' : C.display(item.before[key]) + ' → ' + C.display(item.after[key])}</dd></React.Fragment>)}</dl>}</div>)}</div>;
  }
  function FieldDetail({ adapter, taskRef, scope, snapshot, revision, command, editor, retained, onDraft, onEdit, onCloseEditor, onDone, onNavigate }) {
    const [historyRef, setHistoryRef] = React.useState(null);
    const [timeline, setTimeline] = React.useState(false);
    const request = window.APSResourceSession.useQuery(async signal => C.query(await adapter.detail(taskRef, { ...scope, snapshot_ref: snapshot }, signal), 'detail', taskRef), [adapter, taskRef, scope, snapshot, revision]);
    const task = request.result && request.result.data.task, p = task && task.execution;
    if (request.loading) return <div className="field-note" role="status">正在读取逐次报工…</div>;
    if (!task) return <div className="field-error"><ErrorBox error={request.error} /><Button icon="refresh-cw" onClick={request.reload} disabled={command.locked}>重读详情</Button>
      {editor && <Button onClick={onCloseEditor} disabled={command.locked}>取消暂存编辑</Button>}</div>;
    const report = editor && p.reports.find(row => row.report_ref === editor.reportRef);
    const legacy = editor && p.legacy_facts.find(row => row.legacy_fact_ref === editor.legacyRef);
    const missingOriginal = editor && (editor.reportRef && !report || editor.legacyRef && !legacy);
    return <section className="field-detail" aria-label={'逐次报工 ' + task.batch_id}>
      <div className="field-detail-heading"><h3 style={{ maxWidth: '100%', overflowWrap: 'anywhere' }}>{task.batch_id} · {task.operation_label} · {C.pieceLabel(task)}</h3><State value={p.execution_state} /><span className="field-note">计划应做 {C.quantity(task.quantity)} 件 · 批次 {C.quantity(task.batch_quantity)} 件{task.quantity_reason ? ' · ' + C.quantityReasons[task.quantity_reason] : ''}</span>
        <Button icon="clock-3" aria-expanded={timeline} onClick={() => setTimeline(value => !value)}>作业时间线</Button>
        <Button icon="plus" disabled={command.locked || !!editor} reason={p.execution_state === 'complete' ? '工序已完工，请补齐原记录或明确更正。' : C.blocked(p.write_context, 'create')} onClick={() => onEdit({ taskRef, action: 'create' })}>新增本次报工</Button>
        {onNavigate && <Button icon="chart-gantt" disabled={command.locked || !!editor} onClick={() => {
          const common = { ...scope }; delete common.state;
          onNavigate('fieldgantt', { plan_ref: task.plan_ref, task_ref: taskRef, operation_ref: task.operation_ref, scope: common,
            return_to: { view: 'field', context: { plan_ref: task.plan_ref, task_ref: taskRef, scope } } });
        }}>实际甘特</Button>}</div>
      {timeline && <Timeline task={task} />}
      {p.completion_basis === 'legacy_finish_event' && <div className="field-note">已有旧完工事实，工序仍为已完工；缺失的数量和有效工时未补造。</div>}
      <Issues issues={p.data_gaps} />
      <div className="field-scroll"><table className="field-table" aria-label="逐次报工记录"><colgroup><col style={{ width: '17%' }} /><col style={{ width: '7%' }} /><col style={{ width: '16%' }} /><col style={{ width: '16%' }} /><col style={{ width: '9%' }} /><col style={{ width: '12%' }} /><col style={{ width: '12%' }} /><col style={{ width: '11%' }} /></colgroup>
        <thead><tr>{['报工编号', '本次数量', '实际开工', '本次完工', '有效工时(h)', '实际设备 / 人员', '备注', '操作'].map(name => <th key={name}>{name}</th>)}</tr></thead>
        <tbody>{p.reports.map(record => <React.Fragment key={record.report_ref}><tr><td>{record.report_no}<small>{record.recorded_against_plan_ref !== task.plan_ref ? '按旧计划录入' : '按本计划录入'}</small><Button icon="history" aria-label={'录入信息 ' + record.report_no} aria-expanded={historyRef === record.report_ref} onClick={() => setHistoryRef(historyRef === record.report_ref ? null : record.report_ref)} /></td>
          <td>{C.display(record.completed_quantity)}</td><td>{C.date(record.actual_start)}</td><td>{C.date(record.actual_end)}</td><td>{C.display(record.effective_processing_hours)}</td>
          <td>{C.display(record.actual_machine_label)}<small>{C.display(record.actual_operator_label)}</small></td><td>{C.display(record.remark)}</td><td>
            <Button icon="file-plus" aria-label={'补齐 ' + record.report_no} reason={C.blocked(record.write_context, 'supplement')} disabled={command.locked || !!editor} onClick={() => onEdit({ taskRef, reportRef: record.report_ref, action: 'supplement' })} />
            <Button icon="square-pen" aria-label={'更正 ' + record.report_no} reason={C.blocked(record.write_context, 'correct')} disabled={command.locked || !!editor} onClick={() => onEdit({ taskRef, reportRef: record.report_ref, action: 'correct' })} /></td></tr>{historyRef === record.report_ref && <tr><td colSpan="8"><History record={record} /></td></tr>}</React.Fragment>)}
          {!p.reports.length && <tr><td colSpan="8" className="field-empty">暂无逐次报工</td></tr>}</tbody></table></div>
      {missingOriginal && <div className="field-note"><p role="alert">原记录已不在当前任务中，暂存内容未写入，未改指其他记录。</p><Button onClick={onCloseEditor} disabled={command.locked}>取消暂存编辑</Button></div>}
      {editor && !missingOriginal && (editor.action === 'create' || report) && <window.FieldEditor key={editor.action + ':' + (editor.reportRef || editor.legacyRef || taskRef)} task={task} record={report} legacy={legacy} action={editor.action} adapter={adapter} command={command} retained={retained} onDraft={onDraft} onClose={onCloseEditor} onDone={onDone} />}
      {p.legacy_facts.length > 0 && <details className="field-note"><summary>原始执行事实 · {p.legacy_facts.length} 条</summary>{p.legacy_facts.map((fact, index) => <div key={fact.legacy_fact_ref || index}>{C.date(fact.event_time)} · {({ start: '开工', finish: '完工', pause: '暂停', resume: '恢复', exception: '异常' })[fact.event_type] || '原始事实'} · {C.display(fact.remark)}
        {fact.event_type === 'finish' && !p.reports.some(row => row.legacy_fact_ref === fact.legacy_fact_ref) && <Button icon="plus" disabled={command.locked || !!editor} reason={C.blocked(p.write_context, 'create')} onClick={() => onEdit({ taskRef, legacyRef: fact.legacy_fact_ref, action: 'create' })}>补齐原始完工记录</Button>}</div>)}</details>}
    </section>;
  }
  window.FieldDetail = FieldDetail;
})();
