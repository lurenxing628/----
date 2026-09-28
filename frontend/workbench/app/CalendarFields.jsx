(function () {
  'use strict';
  const { Button, ErrorBox, Field } = window.ResourceControls;
  const fieldPaths = ['fields.hours', 'fields.eff', 'fields.note', 'fields.shiftStart', 'fields.shiftEnd', 'fields.periods'];
  function Segment({ label, value, options, onChange, disabled }) {
    return <div className="field full"><label>{label}</label><div className="seg" role="group" aria-label={label} style={{ flexWrap: 'wrap', maxWidth: '100%' }}>
      {options.map(([key, text]) => <button type="button" key={key} className={value === key ? 'on' : ''} aria-pressed={value === key}
        disabled={disabled} onClick={() => onChange(key)}>{text}</button>)}</div></div>;
  }
  function CalendarFields({ value, onChange, disabled, error, noteEnabled = true, showSummary = true }) {
    const work = value.type === 'work';
    const change = (key, next) => {
      if (key === 'type' && next === 'work' && value.type === 'rest' && !value.periods?.length)
        onChange({ ...value, type: next, periods: window.APSWorkPeriods.clone(value.defaultPeriods || window.APSWorkPeriods.defaults()), hours: String(window.APSWorkPeriods.hours(value.defaultPeriods || window.APSWorkPeriods.defaults())), allowNormal: 'yes', allowUrgent: 'yes' });
      else onChange({ ...value, [key]: next });
    };
    const id = React.useId();
    return <>
      <Segment label="这一天是否排产" value={value.type} options={[["work", "工作日"], ["rest", "休息日"]]} onChange={next => change('type', next)} disabled={disabled} />
      <div className="fgrid cal-work-fields" style={work ? undefined : { opacity: .55 }}>
        {value.periods == null && <><Field label="班次开始" path="fields.shiftStart" error={error}><input type="time" value={value.shiftStart || ''} disabled={disabled || !work}
          onChange={event => onChange({ ...value, shiftStart: event.target.value, shiftEnd: '' })} /></Field>
        <Field label="班次结束（空白按工时推算）" path="fields.shiftEnd" error={error}><input type="time" value={value.shiftEnd || ''} disabled={disabled || !work}
          onChange={event => { const end = event.target.value, start = value.shiftStart;
            const minute = text => Number(text.slice(0, 2)) * 60 + Number(text.slice(3));
            onChange({ ...value, shiftEnd: end, hours: end && start ? String(((minute(end) - minute(start) + 1439) % 1440 + 1) / 60) : value.hours }); }} /></Field>
        <Field label="可排工时（小时）" path="fields.hours" error={error} required={work}><input id={id + '-hours'} name="hours" className="cal-hours" type="number" min="0" max="24" step="any" data-wb-step="0.5"
          value={value.hours} disabled={disabled || !work} onChange={event => onChange({ ...value, hours: event.target.value, shiftEnd: '' })} /></Field>
        </>}
        <window.WorkPeriodFields value={value.periods} start={value.shiftStart} end={value.shiftEnd} disabled={disabled || !work}
          onChange={periods => onChange({ ...value, periods, hours: String(window.APSWorkPeriods.hours(periods) ?? value.hours) })} />
        <Field label="效率（%）" path="fields.eff" error={error} required={work}><input id={id + '-eff'} name="eff" className="cal-eff" type="number" min="0" max="200" step="any" data-wb-step="5"
          value={value.eff} disabled={disabled || !work} onChange={event => change('eff', event.target.value)} /></Field>
        {['allowNormal', 'allowUrgent'].map(key => <div className="field" key={key}><Segment label={key === 'allowNormal' ? '允许普通件排产' : '允许急件排产'} value={value[key]}
          options={[["yes", "是"], ["no", "否"]]} onChange={next => change(key, next)} disabled={disabled || !work} /></div>)}
      </div>
      <Field label="备注" path="fields.note" error={error} full><input id={id + '-note'} className="cal-note" value={value.note} disabled={disabled || !noteEnabled}
        onChange={event => change('note', event.target.value)} /></Field>{showSummary && <ErrorBox error={error} excludePaths={fieldPaths} />}
    </>;
  }
  function Policy({ value, raw = true }) {
    const fields = value.fields, stored = value.stored;
    const number = window.APSCalendarContract.displayNumber;
    const yesNo = item => ({ yes: '可排', no: '不可排' })[item] || String(item);
    return <div style={{ overflowWrap: 'anywhere', lineHeight: 1.65 }}>
      <div><b>{value.explicit ? '单独设置' : '默认规则'}</b> · {value.effective.is_working ? '可排产' : '不排产'}</div>
      <div>{number(fields.hours)} 小时 · 效率 {number(fields.eff)}% · 普通件{fields.allowNormal === 'yes' ? '可排' : '不可排'} · 急件{fields.allowUrgent === 'yes' ? '可排' : '不可排'}</div>
      <div className="muted">有效时段：{value.effective.periods != null ? window.APSWorkPeriods.describe(value.effective.periods) : window.WorkbenchFormat.dateTime(value.effective.window_start) + " 至 " + window.WorkbenchFormat.dateTime(value.effective.window_end)}</div>
      {raw && stored && <div className="muted">原始配置（只读）：{({ workday: '工作日', holiday: '休息日' })[stored.day_type] || String(stored.day_type)}；起止 {stored.shift_start == null ? '未设置' : stored.shift_start} / {stored.shift_end == null ? '未设置' : stored.shift_end}；
        工时 {number(stored.shift_hours)}；效率 {typeof stored.efficiency === 'number' ? number(stored.efficiency * 100) + '%' : String(stored.efficiency)}；普通件{yesNo(stored.allow_normal)}；急件{yesNo(stored.allow_urgent)}</div>}
      <div className="muted">备注：{fields.note || '未填写'}</div>
    </div>;
  }
  function RefreshResult({ state, onRefresh }) {
    return <><p role="status">{state.loading ? '正在刷新工作日历…' : state.done ? '已刷新，显示最新工作日历。' : '最新工作日历尚未确认。'}</p>
      <ErrorBox error={state.error} />{state.error && <Button icon="refresh-cw" onClick={onRefresh}>刷新保存结果</Button>}</>;
  }
  window.CalendarFields = { Fields: CalendarFields, Segment, Policy, RefreshResult, fieldPaths };
})();
