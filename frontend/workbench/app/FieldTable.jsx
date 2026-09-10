(function () {
  'use strict';
  const C = window.FieldContract, { Button, State } = window.FieldControls;
  function FieldTable({ tasks, loading, loaded, opened, onOpen, disabled, renderDetail }) {
    return <div className="field-scroll"><table className="field-table" aria-label="现场任务列表"><colgroup>{[22, 16, 18, 12, 8, 12, 12].map((width, index) => <col key={index} style={{ width: width + '%' }} />)}</colgroup>
      <thead><tr>{['批次 / 工序', '计划设备 / 人员', '计划开工 / 完工', '累计完成 / 计划应做', '执行剩余', '状态', '操作'].map(label => <th key={label}>{label}</th>)}</tr></thead>
      <tbody>{tasks.map(task => <React.Fragment key={task.task_ref}><tr data-field-task={task.task_ref} className={opened === task.task_ref ? 'field-selected' : ''}>
        <td><button type="button" className="field-link" disabled={disabled} aria-label={task.batch_id + ' · ' + task.operation_label + ' · ' + C.pieceLabel(task)} aria-expanded={opened === task.task_ref} onClick={() => onOpen(task.task_ref)}>{task.batch_id}</button><small>{task.part_name} · {task.operation_label}</small><small data-field-piece>{C.pieceLabel(task)}</small></td>
        <td>{C.display(task.planned_machine_label)}<small>{C.display(task.planned_operator_label)}</small></td><td>{C.date(task.planned_start)}<small>{C.date(task.planned_end)}</small></td>
        <td data-field-quantity>{C.display(task.execution.known_completed_quantity)} / {C.quantity(task.quantity)}<small>批次 {C.quantity(task.batch_quantity)} 件</small><small>{C.quantityReasons[task.quantity_reason]}</small><small>{task.execution.unknown_record_count ? task.execution.unknown_record_count + ' 条数量待补' : ''}</small></td>
        <td>{C.display(task.execution.remaining_quantity)}</td><td><State value={task.execution.execution_state} /><small>{task.execution.data_quality === 'invalid' ? '需复核' : task.execution.data_quality === 'complete' ? '' : '资料待补'}</small></td>
        <td><Button icon={opened === task.task_ref ? 'chevron-up' : 'chevron-down'} aria-label={'查看报工 ' + task.batch_id + ' ' + task.operation_label + ' · ' + C.pieceLabel(task)} disabled={disabled} onClick={() => onOpen(task.task_ref)} /> <span>{task.execution.reports.length} 次</span></td>
      </tr>{opened === task.task_ref && <tr><td colSpan="7" style={{ padding: 0 }}>{renderDetail(task)}</td></tr>}</React.Fragment>)}
        {!tasks.length && <tr><td colSpan="7" className="field-empty" role="status">{loading ? '正在读取现场任务…' : loaded ? '当前范围没有任务' : '现场任务尚未读取'}</td></tr>}</tbody></table></div>;
  }
  window.FieldTable = FieldTable;
})();
