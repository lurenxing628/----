function DelayScreen({ onNav, initialContext }) {
  const plan = usePlanWorkspace(), { vm, save } = plan;
  const { Panel } = window.APSDesignSystem_edbc5d, { MetricStrip, Metric, ControlButton: Button } = window.APSWorkbenchUI;
  const api = window.APSTrialSample, rows = vm.report.rows;
  const [selected, setSelected] = React.useState(() => initialContext && initialContext.batch || vm.task.batch);
  const row = rows.find(r => r.id === selected) || rows[0], blocked = vm.issues.length > 0;
  const last = vm.scenario.tasks.filter(t => t.batch === row.id).sort((a, b) => b.end.localeCompare(a.end))[0];
  const goGantt = () => { if (save({ taskId: last.id })) onNav('gantt'); };
  return <Panel className="wb-page-panel pw-delay" title="交付风险" description="与当前查看方案共用工序安排，按批次最终完工判断交付">
    <PlanContextBar plan={plan} onNav={onNav} detail /><PlanError error={plan.error} />
    <MetricStrip><Metric label="预计晚交" value={blocked ? '不可评估' : vm.report.lateCount} unit={blocked ? '' : '批'} tone={blocked ? 'warning' : vm.report.lateCount ? 'danger' : 'neutral'} /><Metric label="总拖期" value={blocked ? '不可评估' : vm.report.totalDelayHours} unit={blocked ? '' : 'h'} tone={blocked ? 'warning' : vm.report.totalDelayHours ? 'danger' : 'neutral'} /><Metric label="约束冲突" value={vm.issues.length} unit="项" tone={blocked ? 'danger' : 'neutral'} helper="设备、人员、工艺、日历、固定工序" /><Metric label="评估范围" value={rows.length} unit="批" helper="09-08 至 09-09 计划样例" /></MetricStrip>
    <div className="tr-table-wrap pw-delay-table"><table className="tr-table"><thead><tr><th>批次 / 零件</th><th>交付截至</th><th>预览完工</th><th>预计交付</th><th>相对初始基线</th></tr></thead><tbody>{rows.map(r => <tr key={r.id} className={r.id === row.id ? 'selected' : ''}><td><button className="tr-batch-button" onClick={() => setSelected(r.id)}>{r.id}<small>{r.name} · {r.qty} 件</small></button></td><td>{api.formatTime(r.due)}</td><td>{api.formatTime(r.finish)}</td><td><span className={'tr-status ' + (blocked ? 'warning' : r.lateHours ? 'danger' : 'ok')}>{blocked ? '冲突待处理' : r.lateHours ? '晚 ' + r.lateHours + ' h' : '可按期'}</span></td><td>{r.improvementHours ? (r.improvementHours > 0 ? '提前 ' : '后移 ') + Math.abs(r.improvementHours) + ' h' : '不变'}</td></tr>)}</tbody></table></div>
    <section className="pw-risk-detail"><h3>{row.id} · 交付依据</h3><p>最后一道工序「{last.op}」安排在 {last.resource}，{api.formatTime(last.end)} 完成；交期为 {api.formatTime(row.due)}。{blocked ? '当前方案存在约束冲突，交付结论暂不可用。' : row.lateHours ? '晚于交期 ' + row.lateHours + ' 小时。' : '未超过交期。'}</p><p className="muted">当前样例不包含等待、停机或缺料原因记录，不能据此认定延期根因。</p><div className="pw-actions"><Button onClick={goGantt}>定位最后工序</Button><Button onClick={() => onNav('analysis')}>对比备选方案</Button></div></section>
    {blocked && <div className="tr-error">{vm.issues.map((issue, i) => <p key={i}>{issue.message}</p>)}</div>}
  </Panel>;
}
window.DelayScreen = DelayScreen;
