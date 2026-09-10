(function () {
  'use strict';
  const { Button, Issues } = window.ResourceControls, M = window.DashboardTimelineModel;
  const value = v => v === null || v === undefined ? '未知' : typeof v === 'number' ? M.number(v) : String(v);
  const risk = row => row.risk === 'overdue' ? '晚交 ' + value(row.delay_hours) + ' h' : row.risk === 'on_time' ? '预计准时' : '交付未知';
  function Batch({ row, selected, onSelect }) { return <Button className="mini" icon="search" data-analysis-select-batch={row.batch_ref}
    aria-pressed={selected === row.batch_ref} onClick={() => onSelect(row.batch_ref)}>{row.batch_id}</Button>; }
  function Delivery({ data, selected, onSelect, onCompare }) { return <>
    <window.DashboardTimeline data={data} selectedBatch={selected} onSelect={onSelect} />
    <section aria-label="影响批次"><div className="dy-heading"><h3>影响批次</h3><Button icon="git-compare-arrows" onClick={onCompare}>对比调整方案</Button></div>
      <div className="dy-scroll"><table className="dy-analysis-table"><thead><tr><th>批次 / 零件</th><th>交期</th><th>计划完工</th><th>交付判断</th><th>优先级</th></tr></thead>
        <tbody>{data.deliveries.map(row => <tr key={row.batch_ref} data-analysis-delivery={row.batch_ref} data-selected={selected === row.batch_ref}>
          <td><Batch row={row} selected={selected} onSelect={onSelect} /><small>{value(row.part_label)}</small></td><td>{value(row.due_date)}</td><td>{M.timeLabel(row.planned_finish)}</td>
          <td>{risk(row)}</td><td>{({ normal: '普通', urgent: '急件', critical: '特急' })[row.priority] || '未知'}</td></tr>)}</tbody></table></div>
      {!data.deliveries.length && <p className="dy-empty">当前正式计划没有批次交付记录。</p>}
    </section>
  </>; }
  function Downtime({ data, selected, onSelect }) { return <>
    <window.DashboardTimeline data={data} mode="downtime" selectedBatch={selected} onSelect={onSelect} />
    <section aria-label="直接重叠工序"><h3>直接重叠的工序</h3><div className="dy-scroll"><table className="dy-analysis-table"><thead><tr><th>批次 / 工序</th><th>原计划开始</th><th>原计划结束</th><th>重叠小时</th></tr></thead>
      <tbody>{data.overlaps.map(row => <tr key={row.task_ref} data-overlap-task={row.task_ref} data-selected={selected === row.batch_ref}>
        <td><Batch row={row} selected={selected} onSelect={onSelect} /><small>{row.process_label}</small></td><td>{M.timeLabel(row.source.planned_start)}</td>
        <td>{M.timeLabel(row.source.planned_end)}</td><td>{value(row.source.overlap_hours)} h</td></tr>)}</tbody></table></div>
      {!data.overlaps.length && <p className="dy-empty">当前读取范围未确认直接重叠，来源异常仍单独列示。</p>}
    </section>
    <section aria-label="停机登记依据"><h3>登记依据</h3>{data.downtimes.map(row => <dl className="dy-facts" key={row.downtime_ref}>
      <div><dt>设备</dt><dd>{value((data.resources.find(r => r.resource_ref === row.machine_ref) || {}).label)}</dd></div><div><dt>原因</dt><dd>{value(row.reason)}</dd></div>
      <div><dt>开始 / 结束</dt><dd>{M.timeLabel(row.start)} / {M.timeLabel(row.end)}</dd></div><div><dt>登记时间（原存值）</dt><dd>{M.timeLabel(row.recorded_at)}</dd></div>
    </dl>)}</section>
  </>; }
  function Material({ data }) {
    const p = data.pending;
    return <section aria-label="待排批次与齐套日期"><h3>待排批次与齐套日期</h3><div className="dy-context">待排 {value(p.count)} 批 · 已读取 {p.known_count} 批</div><Issues issues={p.issues} />
      <div className="dy-scroll"><table className="dy-analysis-table"><thead><tr><th>批次 / 零件</th><th>数量</th><th>交期</th><th>齐套状态</th><th>齐套日期</th></tr></thead><tbody>{p.items.map(row => <tr key={row.batch_ref} data-pending-batch={row.batch_ref}>
        <td><b>{row.batch_id}</b><small>{value(row.part_label)}</small></td><td>{value(row.quantity)}</td><td>{value(row.due_date)}</td>
        <td>{({ yes: '已齐套', no: '未齐套', partial: '部分齐套' })[row.ready_status] || '未知'}</td><td>{value(row.ready_date)}</td></tr>)}</tbody></table></div>
      {!p.items.length && <p className="dy-empty">{p.count === 0 ? '当前没有待排批次。' : '待排批次来源未能完整读取。'}</p>}
      <h3>本次排产约束</h3><dl className="dy-facts"><div><dt>当前范围</dt><dd>本机待排批次池</dd></div><div><dt>排产输入</dt><dd>当前未选定</dd></div>
        <div><dt>齐套检查</dt><dd>未选定排产输入</dd></div><div><dt>缺资源 / 已开工策略</dt><dd>未选定排产输入</dd></div></dl>
    </section>;
  }
  function Actual({ data, navigate }) { return <section aria-label="工序执行偏差"><h3>工序执行事实与定额对照</h3><div className="dy-scroll"><table className="dy-analysis-table">
    <thead><tr><th>批次 / 工序</th><th>定额加工小时</th><th>有效加工小时</th><th>超耗判断</th><th>现场记录</th></tr></thead><tbody>{data.execution.map(row => {
      const source = row.source, hours = source.hours || {}, context = { plan_ref: source.plan_ref, task_ref: source.task_ref, operation_ref: source.operation_ref };
      return <tr key={source.task_ref}><td>{row.subject}</td><td>{value(hours.quota_processing_hours)} h</td><td>{value(hours.effective_processing_hours)} h</td>
        <td>{hours.overrun === true ? '已确认超耗' : hours.overrun === false ? '未超耗' : '无法评估'}</td><td><Button icon="square-pen" onClick={() => navigate({ view: 'field', context, enabled: true })}>现场报工</Button>
          <Button icon="chart-gantt" onClick={() => navigate({ view: 'fieldgantt', context, enabled: true })}>现场实际</Button></td></tr>;
    })}</tbody></table></div></section>; }
  window.DashboardAnalysisPanels = { Delivery, Downtime, Material, Actual, value };
})();
