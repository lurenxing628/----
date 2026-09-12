(function () {
  'use strict';
  const { Button, Modal } = window.ResourceControls;
  const number = v => window.WorkbenchFormat.number(v, { digits: Number.isInteger(v) ? 0 : 2 });
  const signed = (v, scale = 1) => v === null ? '未知' : v === 0 ? '0' : (v > 0 ? '+' : '') + number(v * scale);
  const risk = row => row.risk === 'overdue' ? '晚交 ' + number(row.delay_hours) + ' h' : row.risk === 'on_time' ? '预计准时' : '交付未知';
  function Peak({ value }) { return value.peak_utilization !== null ? <>{window.WorkbenchFormat.percent(value.peak_utilization)}</> : value.state === 'available' ? <>零可用容量</> : <>容量未知</>; }
  function Metrics({ data }) {
    const old = data.summary.before, selected = data.summary.after;
    return <section aria-label="整体收益与代价"><h3>整体收益与代价</h3><div className="dy-scroll"><table className="dy-analysis-table"><caption className="wb-sr-only">候选方案收益与代价对照</caption><thead><tr><th scope="col">指标</th><th scope="col">受理时正式基线</th><th scope="col">所选候选方案</th><th scope="col">变化</th></tr></thead><tbody>
      <tr><td>{window.WorkbenchTerms.overdue_count}</td><td>{number(old.overdue_count)}</td><td>{number(selected.overdue_count)}</td><td>{signed(old.overdue_count === null || selected.overdue_count === null ? null : selected.overdue_count - old.overdue_count)}</td></tr>
      <tr><td>{window.WorkbenchTerms.total_tardiness_hours} h</td><td>{number(old.total_tardiness_hours)}</td><td>{number(selected.total_tardiness_hours)}</td><td>{signed(old.total_tardiness_hours === null || selected.total_tardiness_hours === null ? null : selected.total_tardiness_hours - old.total_tardiness_hours)}</td></tr>
      <tr><td>同时间窗换型次数</td><td title={old.changeovers.reason || ''}>{number(old.changeovers.value)}</td><td title={selected.changeovers.reason || ''}>{number(selected.changeovers.value)}</td><td>{signed(data.summary.changeover_delta)}</td></tr>
      {data.resources.map(row => <tr key={row.resource_ref} data-comparison-resource={row.resource_ref}><td>{row.label || '名称未记录'} · 日峰值</td><td><Peak value={row.before} /></td><td><Peak value={row.after} /></td><td>{signed(row.delta, 100)} 个百分点</td></tr>)}
    </tbody></table></div>
      <div className="dy-context"><span>交付未知：基线 {old.unknown_count} 批 / 候选 {selected.unknown_count} 批</span><span>资源日峰值：同范围自然日内可用时段占用率</span></div>
      {!data.resource_scope_complete && <div className="dy-note warning">{data.resource_scope_unknown_rows} 条安排的资源来源不完整，未将缺口视为零负荷。</div>}
    </section>;
  }
  function Batches({ data, selected, onSelect }) { return <section aria-label="逐批交期变化"><h3>逐批交期变化</h3><div className="dy-scroll"><table className="dy-analysis-table"><caption className="wb-sr-only">逐批交期变化</caption>
    <thead><tr><th scope="col">批次 / 零件</th><th scope="col">交期</th><th scope="col">基线计划完工</th><th scope="col">候选计划完工</th><th scope="col">基线 / 候选</th><th scope="col">拖期变化 h</th></tr></thead><tbody>{data.batches.map(row => <tr key={row.batch_ref} data-comparison-batch={row.batch_ref} data-selected={selected === row.batch_ref}>
      <td><Button reasonDisplay="inline" className="mini" icon="search" aria-pressed={selected === row.batch_ref} onClick={() => onSelect(row.batch_ref)}>{row.batch_id}</Button><small>{row.part_label || '名称未记录'}</small></td>
      <td>{row.after.due_date || '未知'}</td><td>{row.before.planned_finish ? window.WorkbenchFormat.dateTime(row.before.planned_finish) : '未确认完整排程'}</td>
      <td>{row.after.planned_finish ? window.WorkbenchFormat.dateTime(row.after.planned_finish) : '未确认完整排程'}</td><td>{risk(row.before)} / {risk(row.after)}</td><td>{signed(row.delay_delta_hours)}</td>
    </tr>)}</tbody></table></div></section>; }
  function Summary({ data, onClose }) { return <Modal title="候选方案摘要" icon="chart-gantt" onClose={onClose} footer={<Button reasonDisplay="inline" icon="arrow-left" onClick={onClose}>返回比较</Button>}>
    <div className="modal-b form dy-candidate-summary"><h3>{data.candidate.label || '候选名称未记录'}</h3><dl className="dy-facts">
      <div><dt>受理时正式基线</dt><dd>{data.baseline.baseline_ref ? '已核实受理时基线' : '受理时没有正式基线'}</dd></div>
      <div><dt>{window.WorkbenchTerms.overdue_count}</dt><dd>{number(data.summary.after.overdue_count)}</dd></div><div><dt>{window.WorkbenchTerms.total_tardiness_hours}</dt><dd>{number(data.summary.after.total_tardiness_hours)} h</dd></div>
      <div><dt>同窗换型次数</dt><dd>{number(data.summary.after.changeovers.value)}</dd></div><div><dt>换设备工序</dt><dd>{number(data.machine_changes.count)} · 已确认 {data.machine_changes.known_count} · 未知 {data.machine_changes.unknown_count}</dd></div>
    </dl><window.WorkbenchReference entries={{ '候选编号': data.candidate.candidate_ref, '受理时基线编号': data.baseline.baseline_ref }} /><details className="wb-ref"><summary>换设备工序编号</summary>{data.machine_changes.operation_refs.map(ref => <p key={ref}>{ref}</p>)}{!data.machine_changes.operation_refs.length && <p>没有已确认换设备的工序。</p>}</details></div>
  </Modal>; }
  window.DashboardCandidatePanels = { Metrics, Batches, Summary, number };
})();
