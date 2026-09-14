(function () {
  'use strict';
  const C = window.APSResourceContract, K = window.APSCalendarContract;
  const { Button, ErrorBox, Modal, focusFirstInvalid } = window.ResourceControls;
  const { Fields, Policy, RefreshResult } = window.CalendarFields;
  const Feedback = window.ResourceForms.Feedback;
  function CalendarDayDialog({ adapter, day, source, command, onClose, refreshState, onRefresh }) {
    const [base, setBase] = React.useState(day), [value, setValue] = React.useState(() => K.draft(day));
    const [error, setError] = React.useState(null), [review, setReview] = React.useState(null), [reading, setReading] = React.useState(false);
    const [clearing, setClearing] = React.useState(false), [readError, setReadError] = React.useState(null);
    const original = React.useRef(day), mounted = React.useRef(true), controller = React.useRef(null), formRef = React.useRef(null), formId = React.useId();
    React.useEffect(() => { mounted.current = true; return () => { mounted.current = false; if (controller.current) controller.current.abort(); }; }, []);
    const done = command.phase === 'done', disabled = command.locked || done || reading;
    const guardOwner = window.WorkbenchGuards.useDirtyGuard({ owner: 'calendar-day-' + formId,
      dirty: !done && JSON.stringify(value) !== JSON.stringify(K.draft(original.current)), locked: command.locked, message: '工作日历有尚未保存的修改。' });
    async function close() { if (!command.locked && !reading && await window.WorkbenchGuards.confirmLeave({ owner: guardOwner })) onClose(); }
    React.useEffect(() => { if (error || command.error) focusFirstInvalid(formRef.current); }, [error, command.error]);
    const reason = K.stale(command) ? window.WorkbenchTerms.outcomes.stale : review ? '请先核对最新资料。' :
      C.blocked(base.write_context, 'calendar', clearing ? 'delete' : 'upsert', source);
    async function reloadContext() {
      if (disabled) return;
      setReading(true); setReadError(null); setReview(null);
      controller.current = new AbortController();
      try {
        const year = Number(base.date.slice(0, 4)), month = Number(base.date.slice(5, 7));
        const result = K.month(await adapter.query(K.path + '/month', { year, month }, controller.current.signal), year, month);
        if (mounted.current) setReview({ day: result.data.days.find(row => row.date === base.date), source: result.meta.source });
      } catch (failure) { if (mounted.current) setReadError(failure); }
      finally { if (mounted.current) setReading(false); }
    }
    async function save(event) {
      event.preventDefault(); if (disabled || reason) return;
      try {
        const input = clearing ? { date: base.date } : { date: base.date, fields: K.input(value, original.current) };
        setError(null); await command.submit('calendar', clearing ? 'delete' : 'upsert', base.date, base.write_context, input);
      } catch (failure) { setError(failure); }
    }
    function accept() {
      if (!review || review.source !== 'production' || !command.reset()) return;
      const previous = K.draft(original.current), merged = K.draft(review.day);
      Object.keys(previous).forEach(key => { if (value[key] !== previous[key]) merged[key] = value[key]; });
      original.current = review.day; setValue(merged);
      setBase(review.day); setReview(null); setReadError(null); setError(null);
    }
    return <Modal title={base.date + ' · 工作日历'} icon="calendar-days" onClose={onClose} guardOwner={guardOwner} locked={command.locked || reading}
      footer={<><Button disabled={command.locked || reading} onClick={close}>{done ? '关闭' : '取消'}</Button>
        {!done && !clearing && base.explicit && <Button icon="minus" disabled={disabled || !!review} onClick={() => setClearing(true)}>清除配置</Button>}
        {!done && clearing && <Button disabled={disabled} onClick={() => setClearing(false)}>返回编辑</Button>}
        {!done && <Button type="submit" form={formId} className="btn primary" icon={clearing ? 'minus' : 'check'} busy={disabled} reason={reason}>
          {clearing ? '确认清除，恢复默认' : '保存配置'}</Button>}</>}>
      <form id={formId} ref={formRef} className="modal-b form scroll" onSubmit={save} noValidate>
        <div style={{ borderBottom: '1px solid var(--ui-border)', paddingBottom: 12, marginBottom: 16 }}><Policy value={base} /></div>
        {clearing ? <p>将清除 <b>{base.date}</b> 的全局日历配置，改用该日期的默认规则。人员专属日历和班次不变。</p> :
          <Fields value={value} error={error || command.error} showSummary={false} disabled={disabled} onChange={next => { setValue(next); setError(null); }} />}
        <ErrorBox error={error} excludePaths={clearing ? [] : window.CalendarFields.fieldPaths} /><Feedback command={command} excludePaths={clearing ? [] : window.CalendarFields.fieldPaths} /><ErrorBox error={readError} />
        {!done && <Button icon="refresh-cw" busy={reading} disabled={command.locked} onClick={reloadContext}>刷新最新资料</Button>}
        {review && <div className="match-note" style={{ display: 'block' }}>
          <p>最新资料已读取，已填写的内容保持不变。请核对后继续编辑。</p><Policy value={review.day} />
          <Button disabled={disabled} reason={C.blocked(review.day.write_context, 'calendar', clearing ? 'delete' : 'upsert', review.source)} onClick={accept}>已核对，继续编辑</Button></div>}
        {reason && <p role="status">{reason}</p>}
        {done && <RefreshResult state={refreshState} onRefresh={onRefresh} />}
      </form></Modal>;
  }
  window.CalendarDayDialog = CalendarDayDialog;
})();
