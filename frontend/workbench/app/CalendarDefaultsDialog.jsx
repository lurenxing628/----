(function () {
  'use strict';
  const C = window.APSResourceContract, P = window.APSWorkPeriods, S = window.APSResourceSession;
  const { Button, ErrorBox, Modal } = window.ResourceControls;
  function CalendarDefaultsDialog({ adapter, command, onClose, refreshState, onRefresh }) {
    const request = S.useQuery(async signal => {
      const result = await adapter.query('/api/workbench/v1/calendar/defaults', {}, signal), data = result.data;
      if (!data || !Array.isArray(data.periods) || !data.periods.length || P.validate(data.periods)
          || !Number.isFinite(data.hours) || !data.write_context)
        throw C.failure('默认工作时间读取不完整，请刷新后重试。');
      return result;
    }, [adapter]);
    const [base, setBase] = React.useState(null), [periods, setPeriods] = React.useState(null), [error, setError] = React.useState(null);
    const discarded = React.useRef(null);
    const formId = React.useId(), done = command.phase === 'done', disabled = command.locked || done || request.loading;
    React.useEffect(() => { if (!base && request.result && request.result !== discarded.current && !request.loading) { setBase(request.result); setPeriods(P.clone(request.result.data.periods)); } }, [request.result, request.loading, base]);
    const owner = window.WorkbenchGuards.useDirtyGuard({ owner: 'calendar-defaults-' + formId,
      dirty: !done && !!base && JSON.stringify(periods) !== JSON.stringify(base.data.periods), locked: command.locked,
      message: '默认工作时间有尚未保存的修改。' });
    async function close() { if (!command.locked && await window.WorkbenchGuards.confirmLeave({ owner })) onClose(); }
    const reason = !base ? '请先读取默认工作时间。' : C.blocked(base.data.write_context, 'calendar', 'defaults', base.meta.source);
    async function save(event) {
      event.preventDefault();
      if (disabled || reason) return;
      const issue = P.validate(periods) || (!periods.length ? '至少填写一个工作时段。' : '');
      if (issue) { setError(C.failure(issue)); return; }
      setError(null);
      await command.submit('calendar', 'defaults', 'calendar-defaults', base.data.write_context, { periods: P.clone(periods) });
    }
    function reload() {
      if (!command.reset()) return;
      discarded.current = request.result;
      setBase(null); setPeriods(null); setError(null); request.reload();
    }
    return <Modal title="修改默认工作时间" icon="calendar-days" onClose={close} guardOwner={owner} locked={command.locked}
      footer={<><Button disabled={command.locked} onClick={close}>{done ? '关闭' : '取消'}</Button>
        {!done && <Button type="submit" form={formId} className="btn primary" disabled={disabled} reason={reason}>保存默认工作时间</Button>}</>}>
      <form id={formId} className="modal-b form scroll" onSubmit={save} noValidate>
        <p>保存后，所有未单独设置的工作日使用这些时段；已有单日班表和个人班表按各自设置执行，周末默认休息。</p>
        {periods && <window.WorkPeriodFields value={periods} onChange={setPeriods} disabled={disabled} label="默认工作时段" />}
        {request.loading && <p role="status">正在读取默认工作时间…</p>}
        <ErrorBox error={request.error || error} /><window.ResourceForms.Feedback command={command} />
        {!done && (request.error || command.phase === 'rejected') && <Button disabled={command.locked} icon="refresh-cw" onClick={reload}>采用最新设置，重新填写</Button>}
        {done && <window.CalendarFields.RefreshResult state={refreshState} onRefresh={onRefresh} />}
      </form>
    </Modal>;
  }
  window.CalendarDefaultsDialog = CalendarDefaultsDialog;
})();
