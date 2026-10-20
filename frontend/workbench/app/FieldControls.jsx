(function () {
  'use strict';
  const { Icon, ErrorBox, Modal, Issues } = window.ResourceControls;
  const iconAliases = { 'arrow-left': 'chevron-left', 'file-spreadsheet': 'file-input', 'file-plus': 'plus', info: 'history', 'chevron-up': 'fold-vertical' };
  function Button({ icon, ...props }) { return <window.ResourceControls.Button {...props} icon={iconAliases[icon] || icon} />; }
  function State({ value }) { return <span className={'field-state ' + value}>{window.FieldContract.states[value] || '未读取'}</span>; }
  function Conflicts({ rows = [] }) {
    const C = window.FieldContract;
    return rows.length > 0 ? <section className="field-note" aria-label="报工影响明细"><ul>{rows.map((item, index) => <li key={index} data-field-conflict={item.operation_ref}>
      <strong>{[item.batch_id, item.operation_label, item.piece_id ? '分件 ' + item.piece_id : ''].filter(Boolean).join(' · ')}</strong>：{item.message}
      {item.plan && <div>正式 v{item.plan.version} 安排：{C.date(item.plan.start)} 至 {C.date(item.plan.end)}</div>}
      <window.WorkbenchReference label="关联记录编号" entries={{ '工序编号': item.operation_ref, '工序代码': item.operation_code,
        '正式计划编号': item.plan && item.plan.plan_ref, '安排编号': item.plan && item.plan.task_ref,
        '定额采用编号': item.adoption_ref, '模板工序编号': item.template_operation_ref, '约束编号': item.code }} />
    </li>)}</ul></section> : null;
  }
  function Feedback({ command, onDone, excludePaths = [] }) {
    const error = command.error && (command.error.error || command.error);
    return <div aria-live="polite"><ErrorBox error={command.error} excludePaths={excludePaths} />
      <Conflicts rows={error && error.conflicts || []} />
      {command.locked && <div className="field-note">{command.phase === 'sending' ? '正在保存，请保留当前页面。' : window.WorkbenchTerms.outcomes.pending('报工')} <Button icon="refresh-cw" disabled={command.phase !== 'pending'} onClick={command.check}>{window.WorkbenchTerms.actions.query_result}</Button></div>}
      {command.phase === 'done' && <div className="field-note">{command.result.result === 'unchanged' ? '内容没有变化，已确认。' : window.WorkbenchTerms.outcomes.done('保存')} <Button icon="check" onClick={onDone}>刷新已确认结果</Button></div>}
    </div>;
  }
  window.FieldControls = { Button, Icon, ErrorBox, Modal, Issues, State, Feedback, Conflicts };
})();
