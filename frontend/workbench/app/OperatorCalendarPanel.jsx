(function () {
  'use strict';
  // Load after OperatorCalendarContract.js and before ResourceWorkspace.jsx，所以反馈组件由宿主注入，
  // 和 OperatorMachinePermissions.jsx 一样，不在模块级引用后加载的文件。
  const C = window.APSResourceContract, O = window.APSOperatorCalendar, S = window.APSResourceSession;
  const { Button, ErrorBox, Issues, Modal, Field } = window.ResourceControls;
  function Segment({ label, value, options, disabled, onChange }) {
    return <div className="rm-format"><span className="seclabel">{label}</span>
      <div className="seg" role="group" aria-label={label}>{options.map(([key, text]) =>
        <button key={key} type="button" disabled={disabled} className={value === key ? 'on' : ''}
          aria-pressed={value === key} onClick={() => onChange(key)}>{text}</button>)}</div></div>;
  }
  function RefreshResult({ state, onRefresh }) {
    if (state && state.error) return <><ErrorBox error={state.error} />
      <Button icon="refresh-cw" onClick={onRefresh}>刷新保存结果</Button></>;
    return <p role="status">{state && state.done ? '已刷新，显示最新个人日历。'
      : state && state.loading ? '正在刷新…' : '请刷新保存结果，核对个人日历。'}</p>;
  }
  const PATH = ref => 'entities/operator/' + ref + '/calendar';
  function todayMonth() {
    const now = new Date();
    return { year: now.getFullYear(), month: now.getMonth() + 1 };
  }
  function monthDays(year, month) {
    return [31, year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0) ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1];
  }
  function monthKey(year, month) { return String(year).padStart(4, '0') + '-' + String(month).padStart(2, '0'); }
  function DayEditor({ day, draft, setDraft, disabled, error, onSave, onClear, saveReason, clearReason, clearing, onClearing }) {
    const rest = draft.type === 'rest';
    // 清除单独设置与全局日历同一套两步：先点「清除单独设置」，再点「确认清除，恢复默认」才真正提交。
    if (clearing) return <div className="iopane on">
      <div className="chead"><h3 style={{ margin: 0 }}>{day.date} · 清除单独设置</h3></div>
      <p>将清除 <b>{day.date}</b> 的单独设置，这一天恢复按班次轮换或全局工作日历排产。</p>
      <div className="wb-actions" style={{ marginTop: 12 }}>
        <Button disabled={disabled} onClick={() => onClearing(false)}>返回编辑</Button>
        <Button icon="trash-2" className="btn danger" disabled={disabled} reason={clearReason} onClick={onClear}>确认清除，恢复默认</Button>
      </div>
    </div>;
    return <div className="iopane on">
      <div className="chead"><h3 style={{ margin: 0 }}>{day.date} · {day.explicit ? '已单独设置' : '未单独设置'}</h3></div>
      <Segment label="这一天" value={draft.type} disabled={disabled} options={[['work', '上班'], ['rest', '休息']]}
        onChange={type => setDraft(O.switchType(day, draft, type))} />
      {!rest && draft.periods == null && <div className="fgrid">
        <Field label="班次开始" path="fields.shiftStart" error={error} required>
          <input type="time" value={draft.shiftStart} disabled={disabled}
            onChange={event => setDraft({ ...draft, shiftStart: event.target.value })} /></Field>
        <Field label="班次结束" path="fields.shiftEnd" error={error}>
          <input type="time" value={draft.shiftEnd} disabled={disabled}
            onChange={event => setDraft({ ...draft, shiftEnd: event.target.value })} /></Field>
      </div>}
      {!rest && <window.WorkPeriodFields value={draft.periods} start={draft.shiftStart} end={draft.shiftEnd} disabled={disabled}
        onChange={periods => setDraft({ ...draft, periods })} />}
      {!rest && draft.periods == null && <p className="iohint">工时由班次起止算出来，不用单独填。结束时刻早于开始时刻表示跨零点的夜班。
        留空结束时刻时，由系统按默认班次时长推算。</p>}
      <div className="fgrid">
        <Field label="效率（%）" path="fields.eff" error={error} required>
          <input type="number" min="0" max="200" step="any" data-wb-step="5" value={draft.eff} disabled={disabled}
            onChange={event => setDraft({ ...draft, eff: event.target.value })} /></Field>
        <Field label="备注" path="fields.note" error={error}>
          <input type="text" value={draft.note} disabled={disabled}
            onChange={event => setDraft({ ...draft, note: event.target.value })} /></Field>
      </div>
      {!rest && <div className="fgrid">
        <Segment label="允许普通件" value={draft.allowNormal} disabled={disabled} options={[['yes', '可以'], ['no', '不可以']]}
          onChange={allowNormal => setDraft({ ...draft, allowNormal })} />
        <Segment label="允许急件" value={draft.allowUrgent} disabled={disabled} options={[['yes', '可以'], ['no', '不可以']]}
          onChange={allowUrgent => setDraft({ ...draft, allowUrgent })} />
      </div>}
      {rest && <p className="iohint">休息日不排产，工时按 0 计。</p>}
      <div className="wb-actions" style={{ marginTop: 12 }}>
        <Button icon="check" className="btn primary" disabled={disabled} reason={saveReason} onClick={onSave}>保存这一天</Button>
        {day.explicit && <Button icon="minus" disabled={disabled} reason={clearReason} onClick={() => onClearing(true)}>清除单独设置</Button>}
      </div>
    </div>;
  }
  function RangeClear({ range, setRange, disabled, error, preview, onPreview, onConfirm, reason, busy }) {
    return <div className="iopane on">
      <div className="chead"><h3 style={{ margin: 0 }}>按日期范围清除</h3></div>
      <p className="iohint">清除后这些日期恢复成按班次轮换或全局工作日历排产。文件导入不会删除任何日期，
        导错了就从这里批量清掉。</p>
      <div className="fgrid">
        <Field label="开始日期" path="start_date" error={error} required>
          <input type="date" value={range.start_date} disabled={disabled}
            onChange={event => setRange({ ...range, start_date: event.target.value })} /></Field>
        <Field label="结束日期" path="end_date" error={error} required>
          <input type="date" value={range.end_date} disabled={disabled}
            onChange={event => setRange({ ...range, end_date: event.target.value })} /></Field>
      </div>
      <div className="wb-actions" style={{ marginTop: 12 }}>
        <Button icon="list-checks" disabled={disabled} busy={busy} onClick={onPreview}>预检要清除的日期</Button>
        {preview && <Button icon="trash-2" className="btn danger" disabled={disabled} reason={reason}
          onClick={onConfirm}>确认清除 {preview.data.count} 天</Button>}
      </div>
      {preview && <p role="status">{preview.data.count ? '这段时间里单独设置过的日期：'
        + preview.data.days.map(day => day.date).join('、') : '这段时间里没有单独设置过的日期，不需要清除。'}</p>}
    </div>;
  }
  function OperatorCalendarPanel({ adapter, entity, source, command, onClose, refreshState, onRefresh, Feedback }) {
    const ref = entity.ref;
    const [month, setMonth] = React.useState(todayMonth);
    const [editBase, setEditBase] = React.useState(null);
    const [selected, setSelected] = React.useState(null), [draft, setDraft] = React.useState(null);
    const [mode, setMode] = React.useState('day');
    const [range, setRange] = React.useState(() => ({ start_date: monthKey(month.year, month.month) + '-01',
      end_date: monthKey(month.year, month.month) + '-' + monthDays(month.year, month.month) }));
    const [preview, setPreview] = React.useState(null), [busy, setBusy] = React.useState(false);
    const [error, setError] = React.useState(null), [clearing, setClearing] = React.useState(false);
    const mounted = React.useRef(true), lastResult = React.useRef(null);
    React.useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
    const request = S.useQuery(async signal => {
      if (typeof adapter.query !== 'function') throw C.failure('dependency not wired: adapter.query');
      return O.month(await adapter.query(PATH(ref) + '/month', month, signal), { ...month, ref });
    }, [adapter, ref, month.year, month.month]);
    const result = request.result, data = result && result.data;
    if (result) lastResult.current = result;
    // 刷新本月时保留上一次读到的月历，不把整块清空闪烁；写入仍只认最新读到的 data。
    // 翻月时标题已经指向新月，旧月网格不能继续显示在新标题下。
    const previous = lastResult.current && lastResult.current.data;
    const baseline = data || (previous && previous.year === month.year && previous.month === month.month ? previous : null);
    const shown = data || (request.loading ? baseline : null);
    const done = command.phase === 'done', disabled = command.locked || done || request.loading || busy;
    // 刷新开始或失败时 data 会暂时为空，但不能因此把尚未保存的草稿判成 clean。
    // baseline 只给草稿身份和 dirty guard 用；保存仍由下方 data 门禁只使用最新写入上下文。
    const current = baseline && selected ? baseline.days.find(day => day.date === selected) : null;
    React.useEffect(() => {
      if (current && (!draft || draft.date !== current.date)) { setDraft({ ...O.draftOf(current), date: current.date }); setEditBase(current); }
    }, [current && current.date, current && current.calendar_ref]);
    const staleDraft = !!current && !!editBase && (current.calendar_ref !== editBase.calendar_ref
      || JSON.stringify(O.draftOf(current)) !== JSON.stringify(O.draftOf(editBase)));
    const dirty = !done && mode === 'day' && !!current && !!draft && draft.date === current.date
      && JSON.stringify(draft) !== JSON.stringify({ ...O.draftOf(editBase || current), date: current.date });
    const owner = window.WorkbenchGuards.useDirtyGuard({ dirty, message: window.WorkbenchTerms.personal_calendar + '有尚未保存的修改。', locked: command.locked });
    async function close(detail) {
      if (command.locked) return;
      if (!(detail && detail.guardConfirmed === true && detail.guardOwner === owner) && !await window.WorkbenchGuards.confirmLeave({ owner })) return;
      onClose();
    }
    async function confirmDraftTransition() {
      if (disabled) return false;
      return window.WorkbenchGuards.confirmLeave({ owner });
    }
    async function openDay(day) {
      if (disabled) return;
      if (mode === 'day' && day.date === selected) return;
      if (!await confirmDraftTransition()) return;
      if (!command.reset()) return;
      setError(null); setMode('day'); setClearing(false); setSelected(day.date); setEditBase(day); setDraft({ ...O.draftOf(day), date: day.date });
    }
    async function changeMonth(next) {
      if (!next || !await confirmDraftTransition()) return;
      if (!command.reset()) return;
      setError(null); setClearing(false); setSelected(null); setDraft(null); setMonth(next);
    }
    async function toggleMode() {
      const abandonDraft = dirty;
      if (!await confirmDraftTransition()) return;
      if (!command.reset()) return;
      // Only a confirmed dirty transition abandons the day draft. Keep the established clean-mode round trip, but clear
      // a discarded draft's identity as well as its fields so returning from range mode cannot register it dirty again.
      setMode(value => value === 'range' ? 'day' : 'range');
      if (abandonDraft) { setSelected(null); setDraft(null); }
      setClearing(false); setError(null); setPreview(null);
    }
    function capability(action) {
      if (!data) return '请先读取这个月的个人日历。';
      if (source !== 'production') return '当前不是生产数据，不能修改个人日历。';
      return C.blocked(data.write_context, 'operator', action, source);
    }
    function save() {
      if (disabled || !current || staleDraft) return;
      try {
        setError(null);
        if (!command.reset()) return;
        command.submit('operator', 'calendar_upsert', ref, data.write_context,
          { date: current.date, fields: O.input(draft, editBase || current) });
      } catch (failure) { setError(failure); }
    }
    function clearDay() {
      if (disabled || !current || !current.explicit || !clearing) return;
      setError(null);
      if (!command.reset()) return;
      command.submit('operator', 'calendar_delete', ref, data.write_context, { date: current.date });
    }
    async function previewRange() {
      if (disabled) return;
      try {
        setError(null); setPreview(null);
        const input = O.rangeInput(range);
        if (!command.reset()) return;
        setBusy(true);
        const raw = await adapter.preview(PATH(ref) + '/range-preview', { input }, new AbortController().signal);
        if (mounted.current) setPreview(O.rangePreview(raw, input));
      } catch (failure) { if (mounted.current) setError(failure); }
      finally { if (mounted.current) setBusy(false); }
    }
    function confirmRange() {
      if (disabled || !preview || !preview.data.count) return;
      setError(null);
      if (!command.reset()) return;
      command.submit('operator', 'calendar_range_clear', ref, preview.data.write_context, preview.data.range);
    }
    const saveReason = staleDraft ? '这一天的配置已变化，请先采用最新配置后重新填写。' : capability('calendar_upsert');
    const clearReason = capability('calendar_delete');
    const rangeReason = !preview ? '请先预检要清除的日期。' : !preview.data.count ? '这段时间没有要清除的日期。'
      : capability('calendar_range_clear');
    return <div className="plana resource-calendar wb-operator-calendar">
      <Modal title={(entity.business_code || '') + ' · ' + window.WorkbenchTerms.personal_calendar} icon="calendar-days" onClose={close} guardOwner={owner} locked={command.locked}
        footer={<Button onClick={close} reason={command.locked ? '结果还没确认，暂时不能关闭。' : ''}>{done ? '完成' : '关闭'}</Button>}>
        <div className="modal-b scroll">
          <p className="iohint">{window.WorkbenchTerms.personal_calendar}只管这一个人。某一天设了{window.WorkbenchTerms.personal_calendar}，这一天就整天按这里的安排排产，
            不再套用他的班次轮换，也不看全局工作日历。没有单独设置的日期显示「按班次」。</p>
          <div className="cal-top" style={{ flexWrap: 'wrap' }}>
            <Button className="cal-nav" icon="chevron-left" aria-label="上一月" disabled={disabled || !data || !data.previous_month}
              onClick={() => changeMonth(data.previous_month)} />
            <span className="cal-title">{month.year} 年 {month.month} 月</span>
            <Button className="cal-nav" icon="chevron-right" aria-label="下一月" disabled={disabled || !data || !data.next_month}
              onClick={() => changeMonth(data.next_month)} />
            <Button icon="refresh-cw" aria-label="刷新本月" busy={request.loading} disabled={disabled} onClick={request.reload} />
            <span className="tb-spacer" style={{ flex: 1 }} />
            <Button icon={mode === 'range' ? 'calendar-days' : 'trash-2'} disabled={disabled} onClick={toggleMode}>
              {mode === 'range' ? '返回按天维护' : '按日期范围清除'}</Button>
          </div>
          {shown && <p className="muted" role="status">本月单独设置了 <b>{shown.stats.configured}</b> 天，
            其中上班 {shown.stats.work_days} 天。</p>}
          <ErrorBox error={request.error} /><Issues issues={result && result.warnings || []} />
          {request.loading && !shown && <window.WorkbenchControls.EmptyState kind="loading" title={'正在读取' + window.WorkbenchTerms.personal_calendar + '…'} />}
          {request.loading && shown && <p role="status" className="muted">正在刷新本月…</p>}
          {shown && mode === 'day' && <div className="cal-grid" aria-busy={request.loading || undefined}>
            {['一', '二', '三', '四', '五', '六', '日'].map(name => <div className="cal-wd" key={name}>{name}</div>)}
            {shown.cells.map((cell, index) => {
              if (!cell) return <div key={'empty-' + index} className="cal-cell empty" />;
              const meta = O.tag(cell);
              return <button key={cell.date} type="button" disabled={disabled}
                className={'cal-cell ' + meta.tone + (cell.is_today ? ' today' : '') + (cell.date === selected ? ' sel' : '')}
                style={{ minWidth: 0, textAlign: 'left', color: 'inherit', fontFamily: 'inherit' }}
                data-operator-calendar-date={cell.date}
                aria-label={cell.date + ' ' + (cell.explicit ? '已单独设置' : '未单独设置') + ' ' + meta.text}
                onClick={() => openDay(cell)}><span className="d">{cell.day}</span>
                <span className="tag" style={{ whiteSpace: 'normal', overflowWrap: 'anywhere' }}>{meta.text}</span></button>;
            })}</div>}
          {data && mode === 'day' && current && draft && <DayEditor day={current} draft={draft} setDraft={setDraft}
            disabled={disabled} error={error} onSave={save} onClear={clearDay} saveReason={saveReason} clearReason={clearReason}
            clearing={clearing && current.explicit} onClearing={value => { setClearing(value); setError(null); }} />}
          {data && mode === 'day' && !current && <p role="status">点一天开始维护。</p>}
          {data && mode === 'range' && <RangeClear range={range} setRange={next => { setRange(next); setPreview(null); }} disabled={disabled} error={error}
            preview={preview} onPreview={previewRange} onConfirm={confirmRange} reason={rangeReason} busy={busy} />}
          <ErrorBox error={error} /><Feedback command={command} />
          {staleDraft && !done && <div role="status"><p>这一天已被修改，旧草稿不会覆盖最新配置。采用最新配置会放弃本次未保存的内容。</p><Button disabled={command.locked || request.loading} onClick={() => { setDraft({ ...O.draftOf(current), date: current.date }); setEditBase(current); setError(null); command.reset(); }}>采用最新配置并重新填写</Button></div>}
          {done && <RefreshResult state={refreshState} onRefresh={onRefresh} />}
        </div></Modal></div>;
  }
  window.OperatorCalendarPanel = OperatorCalendarPanel;
})();
