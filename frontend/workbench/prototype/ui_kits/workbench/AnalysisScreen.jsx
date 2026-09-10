function AnalysisScreen({ onNav }) {
  const plan = usePlanWorkspace(), { state, saved, vm, save, setUI } = plan;
  const { Panel } = window.APSDesignSystem_edbc5d, { ControlButton: Button, MetricStrip, Metric } = window.APSWorkbenchUI;
  const report = vm.report, unavailable = vm.issues.length > 0;
  return <Panel className="wb-page-panel pw-analysis" title="方案对比" description="回转壳体单元 · 09-08 至 09-09 · 日班 08:00–18:00">
    <PlanContextBar plan={plan} onNav={onNav} /><PlanError error={plan.error} />
    <MetricStrip>
      <Metric label="预计晚交" value={unavailable ? '不可评估' : report.lateCount} unit={unavailable ? '' : '批'} tone={unavailable ? 'warning' : report.lateCount ? 'danger' : 'neutral'} helper="按各批最后工序完工与交期比较" />
      <Metric label="总拖期" value={unavailable ? '不可评估' : report.totalDelayHours} unit={unavailable ? '' : 'h'} tone={unavailable ? 'warning' : report.totalDelayHours ? 'danger' : 'neutral'} helper="各批晚交小时之和" />
      <Metric label="调整工序" value={report.changedOperations} unit="道" helper="相对初始基线 v15" />
      <Metric label="换设备" value={report.movedOperations} unit="道" helper="固定工序保持原安排" />
    </MetricStrip>
    <div className="pw-summary pw-decision"><div className="pw-summary-main"><h3>{vm.scenario.name}</h3><p>{vm.scenario.summary}</p><p className="muted">{vm.scenario.tradeoff}</p></div><div className="pw-actions">
      <Button onClick={() => onNav('gantt')}>查看此方案甘特</Button><Button onClick={() => onNav('delay')}>交付风险</Button><PlanAdopt plan={plan} />
    </div></div>
    <div className="pw-comparison" onClick={event => { if (event.target.name === 'scheme') save({ selected: event.target.value }); }} dangerouslySetInnerHTML={{ __html: window.APSTrialViews.comparison(saved, vm) }} />
    <div onClick={event => {
      const button = event.target.closest('button'); if (!button) return;
      if (button.dataset.tab) setUI({ tab: button.dataset.tab });
      if (button.dataset.batch) { const task = vm.scenario.tasks.find(t => t.batch === button.dataset.batch); if (save({ taskId: task.id })) onNav('gantt'); }
    }} dangerouslySetInnerHTML={{ __html: window.APSTrialViews.impact(state, vm) }} />
    <div className="pw-summary"><p className="pw-scenario-note">预置候选，未调用排产引擎。换型次数为预置值，手工试调后不推断。</p><Button size="sm" disabled={unavailable} onClick={() => planDownload(plan)}>导出方案对比</Button></div>
  </Panel>;
}
window.AnalysisScreen = AnalysisScreen;
