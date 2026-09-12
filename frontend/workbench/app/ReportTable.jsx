(function () {
  'use strict';
  const { Button } = window.ReportControls;
  const text = value => value == null ? '未知' : Array.isArray(value) ? value.join('；') : String(value);
  const time = value => value ? window.WorkbenchFormat.dateTime(value) : '未确认';
  function CellText({ value, label }) {
    if (typeof value !== 'string' || value.length <= 80) return value;
    return <details className="rw-cell-text"><summary aria-label={'展开' + label} title={'展开或收起' + label}><span className="rw-cell-preview">{value}</span><window.ReportControls.Icon name="chevron-down" /></summary></details>;
  }
  const stack = (first, second) => <div className="rw-stack"><div><CellText value={first} label="主信息" /></div><div className="rw-muted"><CellText value={second} label="工序信息" /></div></div>;
  function status(row) { return <span className={row.finish_late ? 'rw-danger' : row.late_open ? 'rw-warning' : row.complete ? 'rw-success' : 'rw-muted'}>{row.execution_label}</span>; }
  function Table({ data, onDetail, onLocate, busy, primary }) {
    const { DataTable } = window.APSWorkbenchUI;
    const empty = window.ReportEvidence.noFeedback(data.summary);
    const actual = value => window.ReportEvidence.actualValue(value, empty);
    const actualTime = value => value == null && empty ? actual(value) : time(value);
    let columns;
    const detail = row => <Button className="rw-icon-button" icon="search" aria-label={'查看工序 ' + row.operation_label} disabled={busy || !row.operation_ref} onClick={() => onDetail(row.operation_ref)} />;
    if (data.topic === 'delivery') columns = [
      { key: 'batch_label', title: '批次 / 工序', width: 185, render: row => stack(row.batch_label, row.operation_label) },
      { key: 'planned_end', title: '计划开工 / 完工', width: 165, render: row => stack(time(row.planned_start), time(row.planned_end)) },
      { key: 'confirmed_finish', title: '实际开工 / 整道完工', width: 165, render: row => stack(actualTime(row.actual_start), actualTime(row.confirmed_finish)) },
      { key: 'execution_label', title: '执行情况 / 到期', width: 170, render: row => stack(status(row), row.unclosed ? '到期未确认完成' : row.due ? '到期已确认完成' : '计划尚未到期') },
      { key: 'finish_deviation_minutes', title: '整道完工偏差', width: 118, render: row => row.finish_deviation_minutes == null ? empty ? actual(null) : '尚不可比较' : <span className={row.finish_late ? 'rw-danger' : ''}>{row.finish_deviation_minutes > 0 ? '+' : ''}{row.finish_deviation_minutes} 分钟</span> },
      { key: 'known_completed_quantity', title: '已知累计数量', width: 145, render: row => stack(actual(row.known_completed_quantity), row.unknown_record_count > 0 ? '数量未知 ' + row.unknown_record_count + ' 条' : null) },
      { key: 'effective_processing_hours', title: '有效工时 / 已知小计', width: 145, render: row => stack(actual(row.effective_processing_hours), actual(row.known_effective_processing_hours)) },
      { key: 'action', title: '详情', width: 66, render: detail }
    ];
    else if (data.topic === 'records') columns = [
      { key: 'batch_label', title: '批次 / 工序', width: 185, render: row => stack(row.batch_label, row.operation_label) },
      { key: 'event_label', title: '记录来源 / 内容', width: 140, render: row => stack(row.record_kind_label, row.record_kind === 'production_report' ? row.report_no : row.event_label) },
      { key: 'event_time', title: '实际时段 / 事件时间', width: 164, render: row => row.record_kind === 'production_report' ? stack(time(row.actual_start), time(row.actual_end)) : time(row.event_time) },
      { key: 'quantity_done', title: '本次 / 旧登记量', width: 130, render: row => text(row.quantity_done) },
      { key: 'effective_processing_hours', title: '有效工时', width: 100, render: row => text(row.effective_processing_hours) },
      { key: 'machine_label', title: '实际设备 / 人员', width: 148, render: row => stack(row.machine_label, row.operator_label) },
      { key: 'remark', title: '备注', width: 150, render: row => <CellText value={row.remark || '无'} label="备注" /> }, { key: 'action', title: '工序', width: 66, render: detail }
    ];
    else if (data.topic === 'quality') columns = [
      { key: 'batch_label', title: '批次 / 工序', width: 210, render: row => stack(row.batch_label, row.operation_label) },
      { key: 'execution_label', title: '执行情况', width: 135, render: status },
      { key: 'event_count', title: '旧现场事件数', width: 112 },
      { key: 'production_report_count', title: '逐次报工数', width: 110 },
      { key: 'record_count', title: '全部记录数', width: 110 },
      { key: 'data_gaps', title: '数据缺口', render: row => <span className="rw-warning">{text(row.data_gaps)}</span> },
      { key: 'action', title: '详情', width: 66, render: detail }
    ];
    else columns = data.columns.filter(column => !column.key.endsWith('_ref')).map(column => ({ key: column.key, title: column.label,
      render: row => <CellText value={text(row[column.key])} label={column.label} />, align: ['operations', 'batches', 'events', 'production_reports', 'records', 'effective_processing_hours', 'known_effective_processing_hours', 'unknown_hour_events'].includes(column.key) ? 'right' : 'left' }));
    if (data.topic === 'records' && typeof onLocate === 'function') columns.push({ key: 'locate', title: '定位', width: 52,
      render: row => <Button className="rw-icon-button" icon="chart-gantt" aria-label={'定位实际甘特 ' + (row.report_no || row.event_label)} disabled={busy} onClick={() => onLocate(row)} /> });
    const visible = columns.filter(column => column.key !== 'action' || typeof onDetail === 'function');
    const fixedWidth = visible.every(column => typeof column.width === 'number') ? visible.reduce((sum, column) => sum + column.width, 0) : 0;
    return data.rows.length ? <window.ReportEvidence.TableFrame className={primary ? 'rw-primary-table' : ''} caption={data.topic === 'records' ? '逐次报工与旧现场事件' : '当前范围报表结果'}
      actionColumn={visible.findIndex(column => ['action', 'locate'].includes(column.key))} tabIndex={0} role="region" aria-label={primary ? '报表结果表格' : '报表明细表格'}><DataTable className={['machines', 'people'].includes(data.topic) ? 'rw-resource-table' : 'rw-table'}
      aria-label={data.topic === 'records' ? '逐次报工与旧现场事件' : '当前筛选范围的' + ({ delivery: '工序完成情况', quality: '数据完整性', machines: '设备工时', people: '人员工时' }[data.topic] || '报表结果')}
      columns={visible.map(column => ({ ...column, width: fixedWidth ? column.width / fixedWidth * 100 + '%' : column.width, sortable: false, filterable: false }))}
      rows={data.rows.map((row, index) => ({ ...row, _key: (row.operation_ref || row.resource_ref || row.batch_ref || 'row') + ':' + (row.projection_index == null ? index : row.projection_index) }))} rowKey="_key" /></window.ReportEvidence.TableFrame> : <window.WorkbenchListControls.EmptyState kind="empty" title="当前筛选没有结果" hint="调整计划完工日期、批次或搜索条件后重新查询。" />;
  }
  function Metrics({ summary: s, topic }) {
    const { MetricStrip, Metric } = window.APSWorkbenchUI;
    const empty = window.ReportEvidence.noFeedback(s), actual = value => window.ReportEvidence.actualValue(value, empty);
    const pct = value => value == null ? actual(value) : window.WorkbenchFormat.percent(value);
    const values = topic === 'delivery' ? [
      ['到期工序完成率', pct(s.completion_rate), s.confirmed_due + ' 已确认 / ' + s.due + ' 已到期'],
      ['到期工序按时完成率', pct(s.on_time_rate), s.due_on_time + ' 按时 / ' + s.due + ' 已到期'],
      ['超时未确认完成', s.late_open, '不等于未生产', s.late_open ? 'warning' : undefined],
      ['完工偏差中位数', actual(s.median_finish_minutes), s.finish_sample ? '样本 ' + s.finish_sample + ' 道 · P90 ' + text(s.p90_finish_minutes) + ' 分钟' : '暂无已确认完工样本']
    ] : [['范围内工序', s.operations, s.reported_operations + ' 道有反馈；' + s.unreported + ' 道暂无反馈'],
      ['逐次报工', s.production_reports, '旧现场事件 ' + s.events + ' 条'], ['全部记录', s.records, '旧事件与逐次报工合计，不含额外修订次数'],
      ['有效加工工时', actual(s.effective_processing_hours), empty ? '暂无现场工时记录' : '已知小计 ' + text(s.known_effective_processing_hours) + '；未知 ' + s.unknown_hour_events + ' 条']];
    return <MetricStrip columns={4} className="rw-metrics">{values.map(([label, value, helper, tone]) => <Metric key={label} label={label} value={value} helper={helper} tone={tone} />)}</MetricStrip>;
  }
  window.ReportTable = { Table, Metrics, text, time };
})();
