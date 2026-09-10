function GanttBoard({ onNav, initialContext }) {
  const plan = usePlanWorkspace(), { state, vm, save } = plan;
  const api = window.APSTrialSample, { Panel } = window.APSDesignSystem_edbc5d;
  const { ControlButton: Button } = window.APSWorkbenchUI;
  const [missing, setMissing] = React.useState('');
  React.useEffect(() => {
    const apply = batch => {
      if (!batch) return;
      const task = vm.scenario.tasks.find(t => t.batch === batch);
      if (task) { save({ taskId: task.id }); setMissing(''); }
      else setMissing('当前方案样例不包含 ' + batch + '，未替换为其他批次。');
    };
    apply(initialContext && initialContext.batch);
    if (window.__apsPendingGanttFocus) { apply(window.__apsPendingGanttFocus); window.__apsPendingGanttFocus = null; }
    const focus = e => apply(e.detail);
    window.addEventListener('aps-gantt-focus', focus);
    return () => window.removeEventListener('aps-gantt-focus', focus);
  }, [initialContext]);
  const task = vm.task, batch = api.batches.find(b => b.id === task.batch), delivery = vm.report.rows.find(b => b.id === task.batch);
  const chain = vm.scenario.tasks.filter(t => t.batch === task.batch);
  // 工艺顺序以显式前置关系为准，不能按计划时间排序掩盖冲突草稿。
  const ordered = [], pending = chain.slice();
  while (pending.length) {
    const index = pending.findIndex(t => !t.predecessor || ordered.some(p => p.id === t.predecessor));
    if (index < 0) { ordered.push(...pending); break; }
    ordered.push(pending.splice(index, 1)[0]);
  }
  return <Panel className="wb-page-panel pw-gantt" title="设备 / 人员 / 批次甘特" description="计划安排 · 日班 08:00–18:00 · 非现场报工进度">
    <PlanContextBar plan={plan} onNav={onNav} detail /><PlanError error={plan.error || missing} />
    <div className={'pw-plan-body' + (state.expanded ? ' pw-expanded' : '')}><PlanTimeline plan={plan} />
      <aside className="pw-plan-detail" aria-label="计划工序详情"><h3>{task.batch}</h3><p>{batch.name} · {batch.qty} 件</p><span className={'tr-status ' + (vm.issues.length ? 'warning' : delivery.lateHours ? 'danger' : 'ok')}>{vm.issues.length ? '冲突待处理' : delivery.lateHours ? '预计晚交 ' + delivery.lateHours + ' h' : '预计按期'}</span>
        <dl className="tr-facts"><dt>选中工序</dt><dd>{task.op}</dd><dt>设备 / 人员</dt><dd>{task.resource} / {task.person}</dd><dt>计划开工</dt><dd>{api.formatTime(task.start)}</dd><dt>计划完工</dt><dd>{api.formatTime(task.end)}</dd><dt>交付截至</dt><dd>{api.formatTime(batch.due)}</dd><dt>固定状态</dt><dd>{task.locked ? '固定工序' : '可试调'}</dd></dl>
        <h4>工艺顺序</h4><ol className="pw-chain">{ordered.map(t => <li key={t.id}><button onClick={() => save({ taskId: t.id })} aria-current={t.id === task.id ? 'step' : undefined}>{t.op} · {t.resource}</button><small>{api.formatTime(t.start)} 至 {api.formatTime(t.end)}</small></li>)}</ol>
        {vm.issues.length > 0 && <div className="tr-error" role="alert">{vm.issues.map((issue, i) => <p key={i}>{issue.message}</p>)}</div>}
        <div className="pw-actions"><Button size="sm" onClick={() => onNav('delay', { batch: task.batch })}>交付风险</Button><a className="tr-button" href="trial-sample.html">调整工序</a></div>
      </aside>
    </div>
    <p className="pw-footnote">本范围 2 个日班。时段占用不代表全厂利用率；工艺顺序不等于关键路径。</p>
  </Panel>;
}
window.GanttBoard = GanttBoard;
