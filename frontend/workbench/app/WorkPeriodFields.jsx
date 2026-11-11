import React from './shared/runtime/react.js';
import C from './resource-contract.js';
import { validate, hours, duration } from './WorkPeriods.js';
import ResourceControls from './ResourceControls.jsx';

const fieldPath = path => path.replace(/^input\./, '');

function WorkPeriodFields({ value, onChange, disabled, label = '工作时段', path, error }) {
  const { Button, Field } = ResourceControls;
  const errorId = React.useId() + '-error';
  const change = (index, key, next) => onChange(value.map((row, i) => i === index ? { ...row, [key]: next } : row));
  const target = path === undefined ? null : fieldPath(path);
  const messages = target === null ? [] : Array.from(new Set(
    C.fieldErrors(error).filter(row => fieldPath(row.path) === target).map(row => row.message)
  ));
  const invalid = messages.length > 0, liveError = validate(value);
  const hint = liveError ? (messages.includes(liveError) ? null : liveError)
    : '实际工作 ' + duration(hours(value)) + '；时段之间不排产。';
  return <div className={'field wb-field full' + (invalid ? ' err' : '')} data-field-path={path} role="group" aria-label={label}>
    <b>{label}</b>
    {value.map((row, index) => {
      const offsetInvalid = invalid && index === 0 && row.day_offset !== 0;
      return <div className="fgrid" key={index}>
        <Field label={label + '第 ' + (index + 1) + ' 段开始日期'}>
          <select value={row.day_offset} disabled={disabled || (index === 0 && row.day_offset === 0)}
            aria-invalid={offsetInvalid || undefined} aria-describedby={offsetInvalid ? errorId : undefined}
            onChange={event => change(index, 'day_offset', Number(event.target.value))}><option value={0}>当天</option><option value={1}>次日</option></select></Field>
        <Field label={label + '第 ' + (index + 1) + ' 段开始'}><input type="time" value={row.start} disabled={disabled}
          aria-invalid={invalid || undefined} aria-describedby={invalid ? errorId : undefined}
          onChange={event => change(index, 'start', event.target.value)} /></Field>
        <Field label={label + '第 ' + (index + 1) + ' 段结束'}><input type="time" value={row.end} disabled={disabled}
          aria-invalid={invalid || undefined} aria-describedby={invalid ? errorId : undefined}
          onChange={event => change(index, 'end', event.target.value)} /></Field>
        <div className="field"><span className="muted">{row.start && row.end && row.end <= row.start ? '跨到下一天结束' : '当天结束'}</span>
          <Button disabled={disabled} onClick={() => onChange(value.filter((_, i) => i !== index))}>移除第 {index + 1} 段</Button></div>
      </div>;
    })}
    <div className="wb-actions"><Button disabled={disabled || value.length >= 8}
      onClick={() => onChange([...value, { start: '', end: '', day_offset: 0 }])}>新增工作时段</Button>
      {hint && <span className="muted">{hint}</span>}</div>
    {invalid && <span id={errorId} role="alert" className="wb-field-error">{messages.join(' ')}</span>}
  </div>;
}

export { WorkPeriodFields };
export default WorkPeriodFields;
