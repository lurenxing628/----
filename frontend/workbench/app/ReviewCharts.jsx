(function () {
  'use strict';
  const title = '趋势、偏差与资源分析';
  function ResourceHours({ data, onDrill, view, onChange }) {
    const { Button } = window.ResourceControls, { kind, page } = view, { hoursText } = window.ReportTable;
    const rows = data.resources[kind === 'machine' ? 'machines' : 'people'], pages = Math.max(1, Math.ceil(rows.length / 6));
    const current = Math.min(page, pages), maximum = Math.max(1, ...rows.map(row => row.known_effective_processing_hours || 0));
    const visible = rows.slice((current - 1) * 6, current * 6);
    const open = row => onDrill('records', { resource_type: kind, resource_ref: row.resource_ref || 'unassigned' });
    return <section className="er-section er-resource-hours" aria-label="实际资源工时">

      <div className="rw-section-heading"><h3>实际资源工时</h3><div className="seg" role="group" aria-label="资源工时类型">
        {[['machine', '设备'], ['operator', '人员']].map(([key, label]) => <Button key={key} aria-pressed={kind === key} className={'seg-btn' + (kind === key ? ' on' : '')}
          onClick={() => onChange({ kind: key, page: 1 })}>{label}</Button>)}</div></div>
      <div className="er-resource-list">{visible.map(row => <div className="er-resource-row" key={row.resource_ref || 'unassigned'} data-resource-ref={row.resource_ref || 'unassigned'}>
        <Button className="lnk er-resource-name" disabled={!onDrill} onClick={() => open(row)}>{row.resource_label}</Button>
        <Button className="er-resource-bar" aria-label={'查看 ' + row.resource_label + ' 关联记录'} disabled={!onDrill} onClick={() => open(row)}
          title={'已知工时 ' + hoursText(row.known_effective_processing_hours) + '；未知 ' + row.unknown_hour_events + ' 条'}>
          {row.known_effective_processing_hours !== null && <i aria-hidden="true" style={{ width: row.known_effective_processing_hours / maximum * 100 + '%' }} />}</Button>
        <span className="er-resource-value">{row.effective_processing_hours === null ? '总工时未知' : '总工时 ' + hoursText(row.effective_processing_hours)} · 已知 {hoursText(row.known_effective_processing_hours)} · 待补 {row.unknown_hour_events} 条</span>
      </div>)}{!rows.length && <window.WorkbenchListControls.EmptyState kind="empty" title="当前范围没有资源工时记录" />}</div>
      <window.WorkbenchListControls.Pager page={current} pages={pages} total={rows.length} size={6} unit="组" label="资源工时"
        onPage={number => onChange({ kind, page: number })} />
      <p className="er-method">点击资源查看报工明细。</p>
      <window.ReportTable.Table data={{ topic: kind === 'machine' ? 'machines' : 'people', rows: visible, columns: window.ReviewChartViews.resourceColumns() }} />
    </section>;
  }
  // expanded：执行复盘页把图表当主体，直接展开，不再折叠；报表中心仍是可折叠的辅助区。
  function Charts({ data, open, onChange, onDrill, resourceView, onResourceView, expanded = false }) {
    const { DistributionChart, TrendChart } = window.ReviewChartViews, { hoursText } = window.ReportTable, legacy = window.WorkbenchTerms.legacy_field_records;
    const points = data.charts.trend.map(row => ({ time: new Date(row.date + 'T00:00:00').getTime(), label: row.date,
      planned: row.planned, actual: row.actual, unclosed: row.actual == null ? null : Math.max(0, row.planned - row.actual) }));
    const items = (rows, tone) => rows.map(row => ({ ...row, id: row.label, tone }));
    const body = <>
      <div className="er-overview-grid"><section className="er-section er-trend"><h3>计划与实际累计完工</h3><TrendChart points={points} label="范围内工序累计完工" /></section>
        <section className="er-section er-insights"><h3>记录要点</h3><p>已确认晚完成 {data.summary.finish_late} 道；到期未确认 {data.summary.unclosed_due} 道。</p>
          <p>{legacy} {data.summary.events} 条；逐次报工 {data.summary.production_reports} 条；全部记录 {data.summary.records} 条。</p>
          {!window.ReportEvidence.noFeedback(data.summary) && <p>有效加工工时 {hoursText(data.summary.effective_processing_hours)}；已知小计 {hoursText(data.summary.known_effective_processing_hours)}；工时未知 {data.summary.unknown_hour_events} 条。</p>}
          <div className="rw-actions">{[['finish_late', '晚完成明细'], ['unclosed', '未确认明细'], [data.scope.focus, '工序明细']].map(([focus, label]) =>
            <window.ResourceControls.Button key={label} icon="arrow-right" disabled={!onDrill} onClick={() => onDrill('delivery', { focus })}>{label}</window.ResourceControls.Button>)}</div></section></div>
      <div className="er-distribution-grid"><DistributionChart items={items(data.charts.finish, 'info')} label="已确认整道完工偏差" />
        <DistributionChart items={items(data.charts.aging, 'warning')} label="到期未确认已过时长" /></div>
      <p className="er-method">按当前完工记录汇总每日累计完工数；待确认时长从计划完工时间起计算。</p>
      <ResourceHours data={data} onDrill={onDrill} view={resourceView} onChange={onResourceView} />
    </>;
    if (expanded) return <section className="er-chart-disclosure er-chart-expanded" data-expanded="true" aria-label={title}><h3 className="er-chart-title">{title}</h3>{body}</section>;
    return <details className="er-chart-disclosure" open={open} onToggle={event => onChange(event.currentTarget.open)}><summary>{title}</summary>{body}</details>;
  }
  window.ReviewCharts = Charts;
})();
