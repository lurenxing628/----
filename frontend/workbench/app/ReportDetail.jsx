(function () {
  'use strict';
  const fields = [['actual_start', '实际开工'], ['actual_end', '本次实际结束'], ['completed_quantity', '本次完成数量'],
    ['effective_processing_hours', '有效加工工时'], ['remark', '备注']];
  function Evidence({ record }) {
    const { text, time } = window.ReportTable;
    const basis = record.recorded_at_time_basis === 'factory_local' ? '工厂本地时间' : '旧系统原存储时间，未转换';
    return <details className="rw-limitations" style={{ overflowWrap: 'anywhere' }}><summary>{record.record_kind_label} · {record.report_no || record.event_label} · {time(record.event_time)}</summary>
      <p>登记时间：{record.recorded_at_time_basis === 'factory_local' ? time(record.recorded_at) : text(record.recorded_at)}（{basis}）</p>
      {record.record_kind === 'legacy_event' ? <><h4>旧原始事实</h4><window.ReportEvidence.StructuredFacts value={record.legacy_evidence} /></> : <>
        <p>报工来源：{record.source}；登记人员：{text(record.local_operator)}；声明人员：{text(record.declared_operator)}</p>
        <h4>逐次报工修订历史（{record.correction_history.length} 次登记）</h4>
        {record.correction_history.map(revision => <details key={revision.revision_ref}><summary>{({ create: '首次报工', correct: '更正', supplement: '补录' })[revision.action] || revision.action} · {time(revision.recorded_at)}</summary>
          <p>原因：{revision.reason || '无'}；登记人员：{text(revision.local_operator)}；声明人员：{text(revision.declared_operator)}</p>
          <window.ReportEvidence.TableFrame caption="报工修订前后值"><window.APSWorkbenchUI.DataTable className="rw-record-detail" rowKey="field"
            columns={[{ key: 'label', title: '字段', width: 150 }, { key: 'before', title: '修订前' }, { key: 'after', title: '修订后' }].map(column => ({ ...column, sortable: false, filterable: false }))}
            rows={fields.map(([key, label]) => ({ field: key, label, before: revision.before === null ? '首次登记，无前值' : text(revision.before[key]), after: text(revision.after[key]) }))} /></window.ReportEvidence.TableFrame>
          <window.WorkbenchReference entries={{ '修订编号': revision.revision_ref, '回执编号': revision.receipt_ref,
            '原设备编号': revision.before && revision.before.actual_machine_ref, '新设备编号': revision.after.actual_machine_ref,
            '原人员编号': revision.before && revision.before.actual_operator_ref, '新人员编号': revision.after.actual_operator_ref }} />
        </details>)}</>}
    </details>;
  }
  function Detail({ api, operationRef, input, onClose, onOpenOperation, initialView, onView }) {
    const { useRead, Button, ErrorBox } = window.ReportControls;
    const { text, time, Table } = window.ReportTable;
    const identity = operationRef + JSON.stringify(input);
    const request = useRead(signal => api.detail(operationRef, { ...input, page: 1, topic: 'delivery', sort: 'batch_label' }, signal), identity);
    const detail = request.result && request.result.data.detail;
    const [page, setPage] = React.useState(initialView ? initialView.page : 1), [size, setSize] = React.useState(initialView ? initialView.size : 10);
    React.useEffect(() => setPage(initialView ? initialView.page : 1), [operationRef, input.snapshot_ref]);
    const row = detail && detail.operation;
    const actions = <div className="rw-actions">
        <Button icon="arrow-right" disabled={!row || request.busy} reasonDisplay="inline" reason={typeof onOpenOperation !== 'function' ? '跨工作区工序详情尚未接合。' : ''}
          onClick={() => onOpenOperation(operationRef, input, row, 'field')}>查看现场记录</Button>
        <Button icon="chart-gantt" disabled={!row || request.busy} reasonDisplay="inline" reason={typeof onOpenOperation !== 'function' ? '跨工作区工序详情尚未接合。' : ''}
          onClick={() => onOpenOperation(operationRef, input, row, 'fieldgantt')}>查看实际甘特</Button>
        </div>;
    return <window.WorkbenchDetailPanel className="rw-detail" detailKey={operationRef} title={row ? row.batch_label + ' · ' + row.operation_label : '工序详情'}
      subtitle="工序报表详情" actions={actions} onClose={onClose}>
      <ErrorBox error={request.error} />{request.busy && <window.WorkbenchListControls.EmptyState kind="loading" title="正在读取工序事实" />}
      {row && <><dl className="rw-detail-facts"><div><dt>整道完成</dt><dd>{row.execution_label}</dd></div><div><dt>已确认完工时间</dt><dd>{time(row.confirmed_finish)}</dd></div><div><dt>已知累计数量</dt><dd>{text(row.known_completed_quantity)}；数量未知 {row.unknown_record_count} 条</dd></div><div><dt>有效加工工时</dt><dd>{text(row.effective_processing_hours)}；已知小计 {text(row.known_effective_processing_hours)}</dd></div></dl>
        <p>旧现场事件 {row.event_count} 条；逐次报工 {row.production_report_count} 条；全部记录 {row.record_count} 条。剩余数量：{text(row.remaining_quantity)}。</p>
        <p>{row.data_gaps.join(' ')}</p><Table data={{ topic: 'records', rows: detail.records.slice((page - 1) * size, page * size) }}
          onLocate={typeof onOpenOperation === 'function' ? record => onOpenOperation(operationRef, input, row, 'fieldgantt', record.report_ref) : undefined} />
        {detail.records.slice((page - 1) * size, page * size).map(record => <Evidence key={record.record_kind + ':' + record.projection_index} record={record} />)}
        <window.ReportControls.Page page={{ number: page, size, total: detail.records.length, pages: Math.max(1, Math.ceil(detail.records.length / size)) }} onChange={patch => {
          setPage(patch.page); if (patch.size) setSize(patch.size); if (onView) onView({ page: patch.page, size: patch.size || size });
        }} /></>}
    </window.WorkbenchDetailPanel>;
  }
  window.ReportDetail = Detail;
})();
