(function () {
  'use strict';
  const { Button, Issues } = window.ResourceControls, M = window.DashboardTimelineModel;
  const value = v => v === null || v === undefined ? '未知' : typeof v === 'number' ? M.number(v) : String(v);
  const risk = row => row.risk === 'overdue' ? '超期 ' + value(row.delay_hours) + ' 小时' : row.risk === 'on_time' ? '预计准时' : '交付未知';
  function Batch({ row, selected, onSelect }) { return <Button reasonDisplay="inline" className="mini" icon="search" data-analysis-select-batch={row.batch_ref}
    aria-pressed={selected === row.batch_ref} onClick={() => onSelect(row.batch_ref)}>{row.batch_id}</Button>; }
  function Delivery({ data, selected, onSelect, onCompare }) { return <>
    <window.DashboardTimeline data={data} selectedBatch={selected} onSelect={onSelect} />
    <section aria-label="影响批次"><div className="dy-heading"><h3>影响批次</h3><Button reasonDisplay="inline" icon="git-compare-arrows" onClick={onCompare}>对比候选方案</Button></div>
      <div className="dy-scroll"><table className="dy-analysis-table"><caption className="wb-sr-only">影响批次交付</caption><thead><tr><th scope="col">批次 / 零件</th><th scope="col">交期</th><th scope="col">计划完工</th><th scope="col">交付判断</th><th scope="col">优先级</th></tr></thead>
        <tbody>{data.deliveries.map(row => <tr key={row.batch_ref} data-analysis-delivery={row.batch_ref} data-selected={selected === row.batch_ref}>
          <td><Batch row={row} selected={selected} onSelect={onSelect} /><small>{value(row.part_label)}</small></td><td>{value(row.due_date)}</td><td>{M.timeLabel(row.planned_finish)}</td>
          <td>{risk(row)}</td><td>{({ normal: '普通', urgent: '急件', critical: '特急' })[row.priority] || '未知'}</td></tr>)}</tbody></table></div>
      {!data.deliveries.length && <window.WorkbenchListControls.EmptyState kind="empty" title="当前正式计划没有批次交付记录。" />}
    </section>
  </>; }
  function Downtime({ data, selected, onSelect }) { return <>
    <window.DashboardTimeline data={data} mode="downtime" selectedBatch={selected} onSelect={onSelect} />
    <section aria-label="直接重叠工序"><h3>直接重叠的工序</h3><div className="dy-scroll"><table className="dy-analysis-table"><caption className="wb-sr-only">直接重叠的工序</caption><thead><tr><th scope="col">批次 / 工序</th><th scope="col">原计划开始</th><th scope="col">原计划结束</th><th scope="col">重叠时间</th></tr></thead>
      <tbody>{data.overlaps.map(row => <tr key={row.task_ref} data-overlap-task={row.task_ref} data-selected={selected === row.batch_ref}>
        <td><Batch row={row} selected={selected} onSelect={onSelect} /><small>{row.process_label}</small></td><td>{M.timeLabel(row.source.planned_start)}</td>
        <td>{M.timeLabel(row.source.planned_end)}</td><td>{value(row.source.overlap_hours)} 小时</td></tr>)}</tbody></table></div>
      {!data.overlaps.length && <window.WorkbenchListControls.EmptyState kind="empty" title="当前时间范围内没有确认到直接重叠。来源读不到的部分另行列出。" />}
    </section>
    <section aria-label="停机登记依据"><h3>登记依据</h3>{data.downtimes.map(row => <dl className="dy-facts" key={row.downtime_ref}>
      <div><dt>设备</dt><dd>{value((data.resources.find(r => r.resource_ref === row.machine_ref) || {}).label)}</dd></div><div><dt>原因</dt><dd>{value(row.reason)}</dd></div>
      <div><dt>开始 / 结束</dt><dd>{M.timeLabel(row.start)} / {M.timeLabel(row.end)}</dd></div><div><dt>登记时间</dt><dd>{M.timeLabel(row.recorded_at)}</dd></div>
    </dl>)}</section>
  </>; }
  function Material({ data }) {
    const p = data.pending;
    return <section aria-label="待排批次与齐套日期"><h3>待排批次与齐套日期</h3><div className="dy-context">待排 {value(p.count)} 批 · 已读取 {p.known_count} 批</div><Issues issues={p.issues} />
      <div className="dy-scroll"><table className="dy-analysis-table"><caption className="wb-sr-only">待排批次与齐套日期</caption><thead><tr><th scope="col">批次 / 零件</th><th scope="col">数量</th><th scope="col">交期</th><th scope="col">齐套状态</th><th scope="col">齐套日期</th></tr></thead><tbody>{p.items.map(row => <tr key={row.batch_ref} data-pending-batch={row.batch_ref}>
        <td><b>{row.batch_id}</b><small>{value(row.part_label)}</small></td><td>{value(row.quantity)}</td><td>{value(row.due_date)}</td>
        <td>{({ yes: '已齐套', no: '未齐套', partial: '部分齐套' })[row.ready_status] || '未知'}</td><td>{value(row.ready_date)}</td></tr>)}</tbody></table></div>
      {!p.items.length && <window.WorkbenchListControls.EmptyState kind="empty" title={p.count === 0 ? '当前没有待排批次。' : '待排批次没有完整读到，数量可能不全。'} />}
      <h3>本次排产约束</h3><dl className="dy-facts"><div><dt>当前范围</dt><dd>本机全部待排批次</dd></div><div><dt>排产输入</dt><dd>当前未选定</dd></div>
        <div><dt>齐套检查</dt><dd>未选定排产输入</dd></div><div><dt>缺设备人员 / 已开工的规则</dt><dd>未选定排产输入</dd></div></dl>
    </section>;
  }
  function Actual({ data, navigate }) { return <section aria-label="工序执行偏差"><h3>工序报工与定额对照</h3><div className="dy-scroll"><table className="dy-analysis-table"><caption className="wb-sr-only">工序执行偏差</caption>
    <thead><tr><th scope="col">批次 / 工序</th><th scope="col">定额加工小时</th><th scope="col">有效加工小时</th><th scope="col">超耗判断</th><th scope="col">现场记录</th></tr></thead><tbody>{data.execution.map(row => {
      const source = row.source, hours = source.hours || {}, context = { plan_ref: source.plan_ref, task_ref: source.task_ref, operation_ref: source.operation_ref };
      return <tr key={source.task_ref}><td>{row.subject}</td><td>{value(hours.quota_processing_hours)} 小时</td><td>{value(hours.effective_processing_hours)} 小时</td>
        <td>{hours.overrun === true ? '已确认超耗' : hours.overrun === false ? '未超耗' : '暂无数据'}</td><td><Button reasonDisplay="inline" icon="square-pen" onClick={() => navigate({ view: 'field', context, enabled: true })}>现场记录</Button>
          <Button reasonDisplay="inline" icon="chart-gantt" onClick={() => navigate({ view: 'fieldgantt', context, enabled: true })}>现场实际</Button></td></tr>;
    })}</tbody></table></div></section>; }
  window.DashboardAnalysisPanels = { Delivery, Downtime, Material, Actual, value };
})();
