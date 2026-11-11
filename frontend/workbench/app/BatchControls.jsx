import React from './shared/runtime/react.js';
import B from './BatchContract.js';
import { Field } from './ResourceControls.jsx';
import WorkbenchFormat from './WorkbenchFormat.js';

function display(key, value) {
  if (key === 'quantity') return WorkbenchFormat.number(value, { digits: 0 });
  if (key === 'due_date' || key === 'ready_date') return WorkbenchFormat.date(value);
  return B.label(key, value);
}
function BaseFields({ value, setValue, disabled, entity, choices, error, errors }) {
  const set = (key, next) => setValue(current => ({ ...current, [key]: next }));
  const path = key => ['business_code', 'part_ref'].includes(key) ? key : 'fields.' + key;
  const input = (key, label, type = 'text') => <Field key={key} label={label} path={path(key)} error={error} errors={errors} required={key === 'business_code' || key === 'quantity'}><input type={type} value={value[key]} disabled={disabled}
    min={type === 'number' ? 1 : undefined} step={type === 'number' ? 1 : undefined} onChange={event => set(key, event.target.value)} /></Field>;
  const select = (key, label, options) => <Field label={label} path={path(key)} error={error} errors={errors}><select value={value[key]} disabled={disabled} onChange={event => set(key, event.target.value)}>
    {!options.some(row => row[0] === value[key]) && <option value={value[key]}>原值待核对</option>}{options.map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></Field>;
  return <div className="fgrid batch-fields">
    {entity ? <><Field label="批次号"><input readOnly value={entity.business_code} /></Field><Field label="图号"><input readOnly value={entity.relationships.part_no + ' · ' + entity.label} /></Field></>
      : <>{input('business_code', '批次号')}<Field label="图号" path="part_ref" error={error} errors={errors} required><select value={value.part_ref} disabled={disabled || !choices} onChange={event => set('part_ref', event.target.value)}>
        <option value="">请选择图号</option>{choices && choices.parts.map(row => <option key={row.ref} value={row.ref}>{row.business_code} · {row.label}</option>)}</select></Field></>}
    {input('quantity', '数量', 'number')}{input('due_date', '交期', 'date')}{select('priority', '优先级', B.priority)}
    {entity && entity.relationships.material_requirement_count > 0
      ? <Field label="当前有效齐套" hint={'原维护标记：' + B.label('ready_status', value.ready_status) + '。请在物料需求中核对；修改数量后需要重新确认齐套。'}><input readOnly value={B.label('ready_status', entity.display_ready_status)} /></Field>
      : select('ready_status', '齐套显示', B.ready)}{input('ready_date', '齐套日期', 'date')}{input('remark', '备注')}
  </div>;
}
const BatchControls = { Field, BaseFields, display };

export { BatchControls, Field, BaseFields, display };
export default BatchControls;
