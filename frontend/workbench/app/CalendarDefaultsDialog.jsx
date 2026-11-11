import React from './shared/runtime/react.js';
import C from './resource-contract.js';
import P from './WorkPeriods.js';
import { useQuery } from './shared/session/query.js';
import { Button, ErrorBox, Modal, focusFirstInvalid } from './ResourceControls.jsx';
import WorkbenchGuards from './WorkbenchGuards.js';
import WorkPeriodFields from './WorkPeriodFields.jsx';
import { Feedback } from './ResourceForms.jsx';
import { RefreshResult } from './CalendarFields.jsx';

function CalendarDefaultsDialog({ adapter, command, onClose, refreshState, onRefresh }) {
  const request = useQuery(async signal => {
    const result = await adapter.query('/api/workbench/v1/calendar/defaults', {}, signal), data = result.data;
    if (!Array.isArray(data.periods) || !data.write_context)
      throw C.failure('默认工作时间读取不完整，请刷新后重试。');
    return result;
  }, [adapter]);
  const [base, setBase] = React.useState(null), [periods, setPeriods] = React.useState(null), [error, setError] = React.useState(null);
  const formRef = React.useRef(null), formId = React.useId(), done = command.phase === 'done', disabled = command.locked || done || request.loading;
  React.useEffect(() => { if (!base && request.result) { setBase(request.result); setPeriods(P.clone(request.result.data.periods)); } }, [request.result, base]);
  React.useEffect(() => { if (error || command.error) focusFirstInvalid(formRef.current); }, [error, command.error]);
  const owner = WorkbenchGuards.useDirtyGuard({ owner: 'calendar-defaults-' + formId,
    dirty: !done && !!base && JSON.stringify(periods) !== JSON.stringify(base.data.periods), locked: command.locked,
    message: '默认工作时间有尚未保存的修改。' });
  async function close() { if (!command.locked && await WorkbenchGuards.confirmLeave({ owner })) onClose(); }
  const reason = !base ? '请先读取默认工作时间。' : C.blocked(base.data.write_context, 'calendar', 'defaults', base.meta.source);
  async function save(event) {
    event.preventDefault();
    if (disabled || reason) return;
    const issue = P.validate(periods) || (!periods.length ? '至少填写一个工作时段。' : '');
    if (issue) { setError(C.failure(issue, [{ path: 'periods', message: issue }])); return; }
    setError(null);
    await command.submit('calendar', 'defaults', 'calendar-defaults', base.data.write_context, { periods: P.clone(periods) });
  }
  function reload() {
    if (!command.reset()) return;
    setBase(null); setPeriods(null); setError(null); request.reload();
  }
  function updatePeriods(next) {
    setPeriods(next); setError(null);
    command.clearRejection();
  }
  return <Modal title="修改默认工作时间" icon="calendar-days" onClose={onClose} guardOwner={owner} locked={command.locked}
    footer={<><Button disabled={command.locked} onClick={close}>{done ? '关闭' : '取消'}</Button>
      {!done && <Button type="submit" form={formId} className="btn primary" disabled={disabled} reason={reason}>保存默认工作时间</Button>}</>}>
    <form id={formId} ref={formRef} className="modal-b form scroll" onSubmit={save} noValidate>
      <p>保存后，所有未单独设置的工作日使用这些时段；已有单日班表和个人班表按各自设置执行，周末默认休息。</p>
      {periods && <WorkPeriodFields value={periods} path="periods" error={error || command.error} onChange={updatePeriods} disabled={disabled} label="默认工作时段" />}
      {request.loading && <p role="status">正在读取默认工作时间…</p>}
      <ErrorBox error={request.error} /><ErrorBox error={error} excludePaths={periods ? ['periods'] : []} /><Feedback command={command} excludePaths={error || !periods ? [] : ['periods']} />
      {!done && (request.error || command.phase === 'rejected') && <Button disabled={command.locked} icon="refresh-cw" onClick={reload}>采用最新设置，重新填写</Button>}
      {done && <RefreshResult state={refreshState} onRefresh={onRefresh} />}
    </form>
  </Modal>;
}

export { CalendarDefaultsDialog };
export default CalendarDefaultsDialog;
