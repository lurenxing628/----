(function () {
  'use strict';
  const fields = [['actual_start', '实际开工'], ['actual_end', '本次实际结束'], ['completed_quantity', '本次完成数量'],
    ['effective_processing_hours', '有效加工工时（小时）'], ['remark', '备注']];
  function Evidence({ record }) {
    const { text, time, amount } = window.ReportTable;
    // 工时列表头已写明单位，格子里只放整形后的数字；其余项照原值显示。
    const cell = (key, value) => key === 'effective_processing_hours' ? amount(value) : text(value);
    const legacy = record.record_kind === 'legacy_event';
    return <details className="rw-limitations rw-record-evidence"><summary>{record.record_kind_label} · {record.report_no || record.event_label} · {time(record.event_time, '未知')}</summary>
      {legacy ? <><h4>{window.WorkbenchTerms.legacy_field_records}</h4><window.ReportEvidence.LegacyRecord value={record.legacy_evidence} /></> : <>
        <p>登记时间：{time(record.recorded_at)}（现场记录时间）；记录人：{text(record.local_operator)}；经办人：{text(record.declared_operator)}</p>
        <window.WorkbenchReference entries={{ '报工来源': record.source }} />
        <h4>逐次报工更正记录（{record.correction_history.length} 次）</h4>
        {record.correction_history.map(revision => <details key={revision.revision_ref}><summary>{window.WorkbenchTerms.report_actions[revision.action] || revision.action} · {time(revision.recorded_at)}</summary>
          <p>原因：{revision.reason || '无'}；记录人：{text(revision.local_operator)}；经办人：{text(revision.declared_operator)}</p>
          <window.ReportEvidence.TableFrame caption="报工更正前后的值"><window.APSWorkbenchUI.DataTable className="rw-record-detail" rowKey="field"
            columns={[{ key: 'label', title: '项目', width: 150 }, { key: 'before', title: '更正前' }, { key: 'after', title: '更正后' }].map(column => ({ ...column, sortable: false, filterable: false }))}
            rows={fields.map(([key, label]) => ({ field: key, label, before: revision.before === null ? '新增，无原值' : cell(key, revision.before[key]), after: cell(key, revision.after[key]) }))} /></window.ReportEvidence.TableFrame>
          <window.WorkbenchReference entries={{ '版本编号': revision.revision_ref, '结果编号': revision.receipt_ref,
            '原设备编号': revision.before && revision.before.actual_machine_ref, '新设备编号': revision.after.actual_machine_ref,
            '原人员编号': revision.before && revision.before.actual_operator_ref, '新人员编号': revision.after.actual_operator_ref }} />
        </details>)}</>}
    </details>;
  }
  function Detail({ api, operationRef, input, onClose, onOpenOperation, initialView, onView }) {
    const { useRead, Button, ErrorBox } = window.ReportControls;
    const { text, time, hoursText, Table } = window.ReportTable;
    const identity = operationRef + JSON.stringify(input);
    const request = useRead(signal => api.detail(operationRef, { ...input, page: 1, topic: 'delivery', sort: 'batch_label' }, signal), identity);
    const detail = request.result && request.result.data.detail;
    const [page, setPage] = React.useState(initialView ? initialView.page : 1), [size, setSize] = React.useState(initialView ? initialView.size : 10);
    React.useEffect(() => setPage(initialView ? initialView.page : 1), [operationRef, input.snapshot_ref]);
    const row = detail && detail.operation;
    const actions = <div className="rw-actions">
        <Button icon="arrow-right" disabled={!row || request.busy} reasonDisplay="inline" reason={typeof onOpenOperation !== 'function' ? window.WorkbenchTerms.outcomes.unavailable : ''}
          onClick={() => onOpenOperation(operationRef, input, row, 'field')}>查看现场记录</Button>
        <Button icon="chart-gantt" disabled={!row || request.busy} reasonDisplay="inline" reason={typeof onOpenOperation !== 'function' ? window.WorkbenchTerms.outcomes.unavailable : ''}
          onClick={() => onOpenOperation(operationRef, input, row, 'fieldgantt')}>查看现场实际甘特</Button>
        </div>;
    const records = detail ? detail.records.slice((page - 1) * size, page * size) : [];
    return <window.WorkbenchDetailPanel className="rw-detail" detailKey={operationRef} title={row ? row.batch_label + ' · ' + row.operation_label : '工序详情'}
      subtitle="工序报表详情" actions={actions} onClose={onClose}>
      <ErrorBox error={request.error} />{request.busy && <window.WorkbenchListControls.EmptyState kind="loading" title="正在读取工序记录" />}
      {row && <><dl className="rw-detail-facts"><div><dt>整道完成</dt><dd>{row.execution_label}</dd></div><div><dt>已确认完工时间</dt><dd>{time(row.confirmed_finish)}</dd></div><div><dt>已知累计数量</dt><dd>{text(row.known_completed_quantity)}；数量未知 {row.unknown_record_count} 条</dd></div><div><dt>有效加工工时</dt><dd>{hoursText(row.effective_processing_hours)}；已知小计 {hoursText(row.known_effective_processing_hours)}</dd></div></dl>
        <p>{window.WorkbenchTerms.legacy_field_records} {row.event_count} 条；逐次报工 {row.production_report_count} 条；全部记录 {row.record_count} 条。剩余数量：{text(row.remaining_quantity)}。</p>
        <p>{row.data_gaps.join(' ')}</p><Table data={{ topic: 'records', rows: records }} empty={{ title: '这道工序暂无报工记录', hint: '' }}
          onLocate={typeof onOpenOperation === 'function' ? record => onOpenOperation(operationRef, input, row, 'fieldgantt', record.report_ref) : undefined} />
        {records.map(record => <Evidence key={record.record_kind + ':' + record.projection_index} record={record} />)}
        <div className="rw-detail-pager"><window.ReportControls.Page page={{ number: page, size, total: detail.records.length, pages: Math.max(1, Math.ceil(detail.records.length / size)) }} onChange={patch => {
          setPage(patch.page); if (patch.size) setSize(patch.size); if (onView) onView({ page: patch.page, size: patch.size || size });
        }} /></div></>}
    </window.WorkbenchDetailPanel>;
  }
  window.ReportDetail = Detail;
})();
