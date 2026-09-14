(function () {
  'use strict';
  const C = window.APSResourceContract, K = window.APSCalendarContract;
  const { Button, ErrorBox, Issues, Modal, Field, focusFirstInvalid } = window.ResourceControls;
  const { Pager, EmptyState } = window.WorkbenchListControls;
  const { Fields, Segment, Policy, RefreshResult } = window.CalendarFields;
  const Feedback = window.ResourceForms.Feedback;
  function RangePreview({ result, page, setPage, onBack, disabled }) {
    const data = result.data, size = 10, pages = Math.max(1, Math.ceil(data.days.length / size));
    return <>
      <div className="match-note" style={{ display: 'block' }}><b>全部命中 {data.counts.selected} 天</b> · 变更 {data.counts.changed} 天 · 不变 {data.counts.unchanged} 天
        <div>{data.request.start_date} 至 {data.request.end_date} · {({ all: '范围内每天', weekday: '仅周一至周五', weekend: '仅周六、周日' })[data.request.scope]}</div>
        <div>确认作用于全部 {data.counts.selected} 天，包含其他分页日期。</div><div className="muted">预览变更有效至 {window.WorkbenchFormat.dateTime(data.expires_at)}</div></div>
      <Pager page={{ number: page, pages, total: data.days.length, size }} sizes={[size]} unit="天" label="预览变更" onPage={setPage} showPageSelect />
      {!data.days.length && <EmptyState kind="filtered" title="当前范围没有命中日期" hint="返回修改日期范围或「应用到」后，再预览变更。"
        action={<Button disabled={disabled} onClick={onBack}>修改日期范围</Button>} />}
      <div className="card-scroll wb-table-shell wb-table-frame cal-preview-scroll" data-sticky-head data-sticky-actions><table className="tbl wb-table cal-preview-table">
        <caption className="wb-visually-hidden">工作日历批量维护预览变更：第 {page} 页，确认将作用于全部 {data.counts.selected} 天</caption>
        <thead><tr><th scope="col" className="wb-col-key" style={{ width: 105 }}>日期</th><th scope="col">变更前</th><th scope="col">变更后</th></tr></thead>
        <tbody>{data.days.slice((page - 1) * size, page * size).map(row => <tr key={row.date}><td className="wb-col-key"><b>{row.date}</b><div className="muted">{row.changed ? '将变更' : '不变'}</div></td>
          <td><Policy value={row.before} /></td><td><Policy value={row.after} /></td></tr>)}</tbody></table></div>
    </>;
  }
  function CalendarRangeDialog({ adapter, month, source, command, onClose, refreshState, onRefresh }) {
    const [range, setRange] = React.useState({ start_date: K.monthKey(month.year, month.month) + '-01',
      end_date: K.monthKey(month.year, month.month) + '-' + K.monthDays(month.year, month.month), scope: 'all', operation: 'upsert' });
    const [value, setValue] = React.useState({ type: 'work', hours: '8', eff: '100', allowNormal: 'yes', allowUrgent: 'yes', note: '' });
    const [replaceNote, setReplaceNote] = React.useState(false);
    const [result, setResult] = React.useState(null), [loading, setLoading] = React.useState(false), [error, setError] = React.useState(null), [page, setPage] = React.useState(1);
    const controller = React.useRef(null), mounted = React.useRef(true), formRef = React.useRef(null), formId = React.useId();
    React.useEffect(() => { mounted.current = true; return () => { mounted.current = false; if (controller.current) controller.current.abort(); }; }, []);
    const done = command.phase === 'done', disabled = command.locked || done || loading;
    const original = React.useRef(JSON.stringify({ range, value, replaceNote }));
    const guardOwner = window.WorkbenchGuards.useDirtyGuard({ owner: 'calendar-range-' + formId,
      dirty: !done && JSON.stringify({ range, value, replaceNote }) !== original.current, locked: command.locked, message: '批量日历维护有尚未保存的范围或规则。' });
    async function close() { if (!command.locked && !loading && await window.WorkbenchGuards.confirmLeave({ owner: guardOwner })) onClose(); }
    React.useEffect(() => { if (error) focusFirstInvalid(formRef.current); }, [error]);
    const reason = K.stale(command) ? '预览变更已过期，没有写入。请点「重新预览变更」。' : !result ? '请先点「预览变更」查看全部命中日期。' :
      !result.data.counts.selected ? '当前范围没有命中日期。' : C.blocked(result.data.write_context, 'calendar', 'confirm', result.meta.source);
    async function preview(event) {
      if (event) event.preventDefault(); if (disabled) return;
      try {
        if (source !== 'production') throw C.failure('当前不是生产数据，不能执行日历维护。');
        if (!K.isDate(range.start_date) || !K.isDate(range.end_date) || range.start_date > range.end_date) throw C.failure('请选择正确的开始和结束日期。',
          [{ path: !K.isDate(range.start_date) ? 'start_date' : 'end_date', message: '日期须有效，且结束日期不能早于开始日期。' }]);
        const fields = range.operation === 'delete' ? {} : K.input(value);
        if (!replaceNote) delete fields.note;
        if (!command.reset()) return;
        setError(null); setResult(null); setLoading(true); controller.current = new AbortController();
        const next = K.preview(await adapter.preview(K.path + '/range/preview', { input: { ...range, fields } }, controller.current.signal));
        if (mounted.current) { setResult(next); setPage(1); }
      } catch (failure) { if (mounted.current) setError(failure); }
      finally { if (mounted.current) setLoading(false); }
    }
    function back() { if (!disabled && command.reset()) { setResult(null); setError(null); } }
    return <div className={'calendar-range-dialog' + (result ? ' is-preview' : '')}>
      <Modal title="批量维护工作日历" icon="calendar-days" onClose={onClose} guardOwner={guardOwner} locked={command.locked || loading}
      footer={<><Button disabled={command.locked || loading} onClick={close}>{done ? '关闭' : '取消'}</Button>
        {!done && result && <Button disabled={disabled} onClick={back}>返回修改范围</Button>}
        {!done && (!result || K.stale(command)) && <Button type="submit" form={formId} icon="list-checks" className="btn primary" busy={disabled}>{K.stale(command) ? '重新预览变更' : '预览变更'}</Button>}
        {!done && result && <Button icon="check" className="btn primary" busy={disabled} reason={reason} onClick={() => command.submit('calendar', 'confirm', result.data.preview_ref,
          result.data.write_context, { preview_ref: result.data.preview_ref })}>确认全部 {result.data.counts.selected} 天</Button>}</>}>
      <form id={formId} ref={formRef} className="modal-b form scroll" onSubmit={preview} noValidate>
        {!result && <><div className="fgrid"><Field label="开始日期" path="start_date" error={error} required>
          <input id={formId + '-from'} type="date" value={range.start_date} disabled={disabled} onChange={event => { setRange({ ...range, start_date: event.target.value }); setError(null); }} /></Field>
          <Field label="结束日期" path="end_date" error={error} required><input id={formId + '-to'} type="date" value={range.end_date}
            disabled={disabled} onChange={event => { setRange({ ...range, end_date: event.target.value }); setError(null); }} /></Field></div>
          <Button disabled={disabled} icon="calendar-days" onClick={() => setRange({ ...range, start_date: K.monthKey(month.year, month.month) + '-01',
            end_date: K.monthKey(month.year, month.month) + '-' + K.monthDays(month.year, month.month) })}>当前整月</Button>
          <Segment label="应用到" value={range.scope} disabled={disabled} options={[["all", "范围内每天"], ["weekday", "仅周一至周五"], ["weekend", "仅周六、周日"]]}
            onChange={scope => setRange({ ...range, scope })} />
          <Segment label="维护方式" value={range.operation} disabled={disabled} options={[["upsert", "设置日历"], ["delete", "清除配置，恢复默认"]]}
            onChange={operation => setRange({ ...range, operation })} />
          {range.operation === 'upsert' ? <><label style={{ display: 'flex', alignItems: 'center', gap: 8, margin: '12px 0' }}>
            <input type="checkbox" checked={replaceNote} disabled={disabled} style={{ width: 15, height: 15 }} onChange={event => setReplaceNote(event.target.checked)} />
            同时替换备注（留空即清除）</label><Fields value={value} error={error} showSummary={false} onChange={next => { setValue(next); setError(null); }} disabled={disabled} noteEnabled={replaceNote} /></> : <p>清除范围内命中日期的全局日历配置，恢复默认规则。人员专属日历和班次不变。</p>}</>}
        {loading && <p role="status">正在读取全部命中日期并计算变更前后配置…</p>}
        {result && <RangePreview result={result} page={page} setPage={setPage} onBack={back} disabled={disabled} />}
        <ErrorBox error={error} excludePaths={result ? [] : ['start_date', 'end_date'].concat(range.operation === 'upsert' ? window.CalendarFields.fieldPaths : [])} />
        <Issues issues={result && result.warnings || []} /><Feedback command={command} />
        {done && <RefreshResult state={refreshState} onRefresh={onRefresh} />}
      </form></Modal></div>;
  }
  window.CalendarRangeDialog = CalendarRangeDialog;
})();
