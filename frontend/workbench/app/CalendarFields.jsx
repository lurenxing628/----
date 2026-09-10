(function () {
  'use strict';
  const { Button, ErrorBox } = window.ResourceControls;
  function Segment({ label, value, options, onChange, disabled }) {
    return <div className="field full"><label>{label}</label><div className="seg" role="group" aria-label={label} style={{ flexWrap: 'wrap', maxWidth: '100%' }}>
      {options.map(([key, text]) => <button type="button" key={key} className={value === key ? 'on' : ''} aria-pressed={value === key}
        disabled={disabled} onClick={() => onChange(key)}>{text}</button>)}</div></div>;
  }
  function CalendarFields({ value, onChange, disabled, error, noteEnabled = true }) {
    const work = value.type === 'work';
    const change = (key, next) => onChange({ ...value, [key]: next });
    const id = React.useId();
    return <>
      <Segment label="这一天是否排产" value={value.type} options={[["work", "工作日"], ["rest", "休息日"]]} onChange={next => change('type', next)} disabled={disabled} />
      <div className="fgrid cal-work-fields" style={work ? undefined : { opacity: .55 }}>
        <div className="field"><label htmlFor={id + '-hours'}>可排工时（小时）</label><input id={id + '-hours'} name="hours" className="cal-hours" type="number" min="0" max="24" step="any" data-wb-step="0.5"
          value={value.hours} disabled={disabled || !work} onChange={event => change('hours', event.target.value)} /></div>
        <div className="field"><label htmlFor={id + '-eff'}>效率（%）</label><input id={id + '-eff'} name="eff" className="cal-eff" type="number" min="0" max="200" step="any" data-wb-step="5"
          value={value.eff} disabled={disabled || !work} onChange={event => change('eff', event.target.value)} /></div>
        {['allowNormal', 'allowUrgent'].map(key => <div className="field" key={key}><Segment label={key === 'allowNormal' ? '允许普通件排产' : '允许急件排产'} value={value[key]}
          options={[["yes", "是"], ["no", "否"]]} onChange={next => change(key, next)} disabled={disabled || !work} /></div>)}
      </div>
      <div className="field full"><label htmlFor={id + '-note'}>备注</label><input id={id + '-note'} className="cal-note" value={value.note} disabled={disabled || !noteEnabled}
        onChange={event => change('note', event.target.value)} /></div><ErrorBox error={error} />
    </>;
  }
  function Policy({ value, raw = true }) {
    const fields = value.fields, stored = value.stored;
    const number = window.APSCalendarContract.displayNumber;
    const yesNo = item => ({ yes: '可排', no: '不可排' })[item] || String(item);
    return <div style={{ overflowWrap: 'anywhere', lineHeight: 1.65 }}>
      <div><b>{value.explicit ? '单独配置' : '默认规则'}</b> · {value.effective.is_working ? '可排产' : '不排产'}</div>
      <div>{number(fields.hours)} 小时 · 效率 {number(fields.eff)}% · 普通件{fields.allowNormal === 'yes' ? '可排' : '不可排'} · 急件{fields.allowUrgent === 'yes' ? '可排' : '不可排'}</div>
      <div className="muted">有效时段：{value.effective.window_start.replace('T', ' ')} 至 {value.effective.window_end.replace('T', ' ')}</div>
      {raw && stored && <div className="muted">原始配置（只读）：{({ workday: '工作日', holiday: '休息日' })[stored.day_type] || String(stored.day_type)}；起止 {stored.shift_start == null ? '未设置' : stored.shift_start} / {stored.shift_end == null ? '未设置' : stored.shift_end}；
        工时 {number(stored.shift_hours)}；效率 {typeof stored.efficiency === 'number' ? number(stored.efficiency * 100) + '%' : String(stored.efficiency)}；普通件{yesNo(stored.allow_normal)}；急件{yesNo(stored.allow_urgent)}</div>}
      <div className="muted">备注：{fields.note || '未填写'}</div>
    </div>;
  }
  function RefreshResult({ state, onRefresh }) {
    return <><p role="status">{state.loading ? '正在重读保存后的工作日历…' : state.done ? '已重新读取最新工作日历。' : '最新工作日历尚未确认。'}</p>
      <ErrorBox error={state.error} />{state.error && <Button icon="refresh-cw" onClick={onRefresh}>重新读取保存结果</Button>}</>;
  }
  window.CalendarFields = { Fields: CalendarFields, Segment, Policy, RefreshResult };
})();
