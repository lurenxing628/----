(function () {
  'use strict';
  const { validate, hours, duration } = window.APSWorkPeriods;
  function Fields({ value, onChange, disabled, start = '08:00', end = '16:00', label = '工作时段' }) {
    const { Button, Field } = window.ResourceControls;
    if (value == null) return <div className="field full"><Button disabled={disabled}
      onClick={() => onChange([{ start: start || '08:00', end: end || '16:00', day_offset: 0 }])}>分段设置工作时间</Button>
      <span className="muted"> 可分别填写上午、下午或夜班，中间休息不计工时。</span></div>;
    const change = (index, key, next) => onChange(value.map((row, i) => i === index ? { ...row, [key]: next } : row));
    const error = validate(value), total = hours(value);
    return <div className="field full" role="group" aria-label={label}>
      <b>{label}</b>
      {value.map((row, index) => <div className="fgrid" key={index}>
        <Field label={label + '第 ' + (index + 1) + ' 段开始日期'}>
          <select value={row.day_offset} disabled={disabled || index === 0}
            onChange={event => change(index, 'day_offset', Number(event.target.value))}><option value={0}>当天</option><option value={1}>次日</option></select></Field>
        <Field label={label + '第 ' + (index + 1) + ' 段开始'}><input type="time" value={row.start} disabled={disabled}
          onChange={event => change(index, 'start', event.target.value)} /></Field>
        <Field label={label + '第 ' + (index + 1) + ' 段结束'}><input type="time" value={row.end} disabled={disabled}
          onChange={event => change(index, 'end', event.target.value)} /></Field>
        <div className="field"><span className="muted">{row.start && row.end && row.end <= row.start ? '跨到下一天结束' : '当天结束'}</span>
          <Button disabled={disabled} onClick={() => onChange(value.filter((_, i) => i !== index))}>移除第 {index + 1} 段</Button></div>
      </div>)}
      <div className="wb-actions"><Button disabled={disabled || value.length >= 8}
        onClick={() => onChange([...value, { start: '', end: '', day_offset: 0 }])}>新增工作时段</Button>
        <span className="muted">{error || '实际工作 ' + duration(total) + '；时段之间不排产。'}</span></div>
    </div>;
  }
  window.WorkPeriodFields = Fields;
})();
