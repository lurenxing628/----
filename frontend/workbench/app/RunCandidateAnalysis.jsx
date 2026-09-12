(function () {
  'use strict';
  const C = window.RunCandidateControls, M = window.RunCandidateModel;
  const labels = { overdue_count: window.WorkbenchTerms.overdue_count, total_tardiness_hours: window.WorkbenchTerms.total_tardiness_hours + ' h', changed_operation_count: '调整工序', machine_change_count: '换设备数' };
  function Value({ metric }) {
    return <>{metric.value === null ? '未知' : M.number(metric.value)}{metric.value === null && <small>已知小计 {M.number(metric.known_subtotal)} · 待核实 {metric.unknown_count} / {metric.total_count}</small>}
      {metric.reason && <details><summary>依据不足</summary><small>{metric.reason.message}</small></details>}</>;
  }
  function Overview({ data }) {
    return <section aria-label="完整候选比较摘要" data-candidate-analysis={data.candidate_ref}>
      <div className="rc-heading"><h3>整份候选与受理基线</h3><span className="rc-muted">{data.batch_refs.length} 批 · {data.operations.operation_refs.length} 道工序</span></div>
      <dl className="rc-meta" data-analysis-metrics>{Object.keys(labels).map(key => <div key={key} data-analysis-metric={key}><dt>{labels[key]}</dt><dd><Value metric={data.metrics[key]} /></dd></div>)}</dl>
      <div className="rc-scope" aria-label="候选变化与取舍">{Object.keys(data.delivery_deltas).map(key => <span key={key}>
        {labels[key]}：{data.delivery_deltas[key] === null ? '基准或候选依据不足，变化未知' : M.signedChange(data.delivery_deltas[key])}</span>)}
        <span>调整工序：{data.metrics.changed_operation_count.value === null ? '完整数量待核实' : data.metrics.changed_operation_count.value + ' 道'}</span>
        <span>换设备：{data.metrics.machine_change_count.value === null ? '完整数量待核实' : data.metrics.machine_change_count.value + ' 道'}</span>
        <span>仅陈述已保存安排的变化，未评估优化收益、实际工时或成本。</span></div>
      {!data.baseline.comparison_available && <p className="rc-notice">{data.baseline.reason.message}</p>}
      <C.Reasons rows={data.operations.issues.flatMap(row => row.reasons)} />
    </section>;
  }
  function Finish({ row }) {
    return <>{row.planned_finish ? M.timeLabel(row.planned_finish) : '无法核实'}{!row.planned_finish && row.partial_planned_finish
      && <small>已安排部分：{M.timeLabel(row.partial_planned_finish)}，非全批完工</small>}</>;
  }
  function Batches({ data, onBatch, onLast }) {
    const [page, setPage] = React.useState(1), pages = Math.max(1, Math.ceil(data.batches.length / 20)), current = Math.min(page, pages);
    return <section aria-label="候选批次交付对照"><div className="rc-heading"><h3>批次交付对照</h3><span className="rc-muted">完整受理批次 · 候选减受理基线</span></div>
      <div className="rc-table wb-table-frame" data-sticky-head data-sticky-actions><table className="wb-table" aria-label="候选批次交付对照"><caption className="wb-visually-hidden">候选批次交付对照</caption><thead><tr>{['批次 / 零件', '交付截至日', '基准完工', '预览完工', '拖期变化 h', '甘特定位'].map(label => <th scope="col" key={label}>{label}</th>)}</tr></thead>
        <tbody>{data.batches.slice((current - 1) * 20, current * 20).map(row => <tr key={row.batch_ref} data-analysis-batch={row.batch_ref}>
          <td>{row.batch_id}<small>{row.part_label || '名称未记录'}</small></td><td>{row.after.due_date || '未记录'}</td>
          <td><Finish row={row.before} /></td><td><Finish row={row.after} /></td><td>{row.delay_delta_hours === null ? '未知' : M.signedChange(row.delay_delta_hours)}</td>
          <td><C.Button icon="chart-gantt" disabled={!onBatch} aria-label={'查看批次甘特 ' + row.batch_id} onClick={() => onBatch(row)}>批次甘特</C.Button>
            {(row.after.last_operations || []).map(task => <C.Button key={task.row_ref} icon="search" className="mini" aria-label={'定位末端工序 ' + row.batch_id + ' ' + task.sequence + (task.piece_id ? ' ' + task.piece_id : '')}
              onClick={() => onLast(task)}>{M.number(task.sequence)} {task.process_label || '工序未记录'}{task.piece_id && ' · ' + task.piece_id}</C.Button>)}</td>
        </tr>)}</tbody></table></div><C.Pager page={current} pages={pages} onPage={setPage} label="批次交付对照" /></section>;
  }
  function History({ data, onPlan }) {
    const [page, setPage] = React.useState(1), pages = Math.max(1, Math.ceil(data.items.length / 20)), current = Math.min(page, pages);
    return <section aria-label="候选采用记录"><h3>采用记录 · {data.total}</h3>
      {!data.total ? <p className="rc-muted" role="status">此候选尚无已持久保存的采用记录。</p> : <div className="rc-table wb-table-frame" data-sticky-head data-sticky-actions><table className="wb-table" aria-label="候选采用记录"><caption className="wb-visually-hidden">候选采用记录</caption><thead><tr>{['原正式计划', '采用时间', '声明人 / 本机账号', '原因', '原回执', '操作'].map(label => <th scope="col" key={label}>{label}</th>)}</tr></thead>
        <tbody>{data.items.slice((current - 1) * 20, current * 20).map(row => <tr key={row.receipt_ref} data-adoption-receipt={row.receipt_ref}>
          <td>{row.official_plan.label}<small>{row.row_count} 道安排</small></td><td>{row.adoption ? M.timeLabel(row.adoption.adopted_at) : '本地时间未核实'}<small>回执保存：{window.WorkbenchFormat.instant(row.committed_at_utc)}</small></td>
          <td>{row.adoption ? <>{row.adoption.declared_operator}<small>{row.adoption.application_operator}</small></> : '未核实'}</td><td>{row.adoption ? row.adoption.reason : '未核实'}</td>
          <td><window.WorkbenchReference value={row.receipt_ref} label="回执编号" /><C.Reasons rows={row.evidence_gaps} /></td>
          <td><C.Button icon="chart-gantt" disabled={!row.can_open || !onPlan} title={row.evidence_gaps.map(gap => gap.message).join(' ')}
            aria-label={'打开原采用计划 v' + row.official_plan.version} onClick={() => onPlan(row.official_plan)}>打开原计划</C.Button></td>
        </tr>)}</tbody></table></div>}<C.Pager page={current} pages={pages} onPage={setPage} label="候选采用记录" /></section>;
  }
  window.RunCandidateAnalysis = { Overview, Batches, History };
})();
