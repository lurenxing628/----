import React from './shared/runtime/react.js';
import C from './resource-contract.js';
import M from './ResourceCatalogModel.js';
import { Button, Issues, Field as SharedField, EmptyState } from './ResourceControls.jsx';
import APSWorkPeriods from './WorkPeriods.js';
import WorkPeriodFields from './WorkPeriodFields.jsx';
import WorkbenchFormat from './WorkbenchFormat.js';

const names = ['business_code', 'label', 'status', 'remark', 'anchor_date', 'cycle_days'];
const fieldPaths = names.concat(names.map(name => 'fields.' + name));
function Field({ label, name, required, errors, children, full }) {
  return <SharedField label={label} path={name} required={required} errors={errors} full={full}>
    {React.cloneElement(children, { name, 'aria-label': label })}</SharedField>;
}
function Pattern({ value, defaultPeriods, onChange, disabled, error, onValidationError }) {
  const [trim, setTrim] = React.useState(null);
  const priorPeriods = React.useRef({});
  function resize(length) {
    Object.keys(priorPeriods.current).forEach(key => { if (Number(key) >= length) delete priorPeriods.current[key]; });
    onChange('pattern', M.resized(value.pattern, length));
  }
  function generate() {
    onValidationError(null);
    try {
      const length = M.cycle(value.cycle_days);
      if (length < value.pattern.length) { setTrim(length); return; }
      resize(length);
    } catch (failure) { onValidationError(failure); }
  }
  function rowChange(index, key, next) {
    const rows = value.pattern.slice(), row = { ...rows[index] }; rows[index] = row; row[key] = next;
    if (key === 'is_rest' && next === true) {
      if (row.periods.length) priorPeriods.current[index] = APSWorkPeriods.clone(row.periods);
      row.periods = [];
    }
    if (key === 'is_rest' && next === false && !row.periods.length) {
      row.periods = APSWorkPeriods.clone(priorPeriods.current[index] || defaultPeriods);
    }
    onChange('pattern', rows);
  }
  const invalidDays = new Set(C.fieldErrors(error).map(item => item.path));
  return <section className="rc-pattern" aria-label="轮换逐日规则">
    <div className="rc-section-head"><h3>逐日规则</h3><span className="muted">{value.pattern.length} 天</span>
      <Button icon="calendar-days" disabled={disabled || trim !== null} onClick={generate}>{value.pattern.length ? '调整逐日规则' : '生成逐日规则'}</Button></div>
    {trim !== null && <div role="alert" className="match-note rc-note">
      <p>将移除第 {trim + 1} 至第 {value.pattern.length} 天，共 {value.pattern.length - trim} 天。其余日期保持原值。</p>
      <div className="rowact"><Button disabled={disabled} onClick={() => { onChange('cycle_days', String(value.pattern.length)); setTrim(null); }}>保留原周期</Button>
        <Button icon="minus" disabled={disabled} onClick={() => { resize(trim); setTrim(null); }}>确认移除末尾 {value.pattern.length - trim} 天</Button></div></div>}
    {!value.pattern.length ? <EmptyState kind="empty" title="尚未登记逐日规则" hint="填写轮换天数后，生成并核对每一天的工作安排。" /> : <div className="wb-table-frame rc-pattern-scroll" data-sticky-head data-sticky-actions><table className="tbl wb-table rc-pattern-table"><caption className="wb-visually-hidden">班次档逐日轮换规则</caption><thead><tr>
      <th scope="col" className="wb-col-key">轮换日</th><th scope="col">工作 / 休息</th><th scope="col">开始</th><th scope="col">结束</th><th scope="col">跨夜</th></tr></thead><tbody>
      {value.pattern.map((row, index) => {
        const rowInvalid = invalidDays.has('pattern.' + index) || undefined;
        return <tr key={index}>
        <td className="wb-col-key">第 {index + 1} 天</td><td className="field"><select aria-label={'第 ' + (index + 1) + ' 天工作安排'} aria-invalid={rowInvalid} value={row.is_rest === null ? '' : row.is_rest ? 'rest' : 'work'} disabled={disabled || trim !== null}
          onChange={event => rowChange(index, 'is_rest', event.target.value === 'rest')}><option value="" disabled>请选择</option><option value="work">工作</option><option value="rest">休息</option></select></td>
        <td colSpan={3}>
          <WorkPeriodFields label={'第 ' + (index + 1) + ' 天工作时段'} value={row.periods} disabled={disabled || trim !== null || row.is_rest !== false}
            onChange={periods => rowChange(index, 'periods', periods)} /></td>
      </tr>; })}</tbody></table></div>}
  </section>;
}
function Facts({ kind, entity }) {
  const count = M.memberCount(kind, entity);
  return <section className="rc-facts"><div className="rc-section-head"><b>{entity.business_code} · {entity.label}</b><span>{entity.status === 'active' ? '启用' : '停用'}</span></div>
    <p>已关联{kind === 'machine_group' ? '设备' : '人员'}：{count === null ? '未读取' : count}</p>
    {kind === 'shift_profile' && <><p>周期起始日期：{WorkbenchFormat.date(entity.fields.anchor_date)} · 轮换天数：{entity.fields.cycle_days}</p>
      <div className="wb-table-frame rc-pattern-scroll" data-sticky-head data-sticky-actions><table className="tbl wb-table"><caption className="wb-visually-hidden">班次档现有逐日轮换规则</caption><thead><tr><th scope="col" className="wb-col-key">轮换日</th><th scope="col">工作 / 休息</th><th scope="col">开始</th><th scope="col">结束</th></tr></thead><tbody>
        {entity.fields.pattern.map(row => <tr key={row.day_offset}><td className="wb-col-key">第 {row.day_offset + 1} 天</td><td>{row.is_rest ? '休息' : '工作'}</td><td colSpan={2}>{APSWorkPeriods.describe(row.periods)}</td></tr>)}</tbody></table></div></>}
    <p className="rc-wrap">备注：{entity.fields.remark || '未填写'}</p><Issues issues={entity.issues} /></section>;
}
function ResourceCatalogEditor({ kind, editor, disabled, error, onChange, onValidationError, onAcknowledge }) {
  const { draft: value, action, base } = editor;
  const normalizedErrors = React.useMemo(() => C.fieldErrors(error).map(row => ({ ...row, path: row.path.replace(/^input\./, '').replace(/^fields\./, '') })), [error]);
  // Deleting takes the same checkbox confirmation as the other delete paths; the host turns an unchecked box into the confirm button's reason.
  if (action === 'delete') return <><p>确认删除该{M.names[kind]}？系统会再次核对关联关系，已被使用的记录不能删除。</p><Facts kind={kind} entity={base} />
    <label className="rm-check"><input type="checkbox" checked={!!editor.acknowledged} disabled={disabled} onChange={event => onAcknowledge(event.target.checked)} />我已核对要删除的资料及其关联关系</label></>;
  const field = (name, label, options = {}) => <Field name={name} label={label} required={options.required} errors={normalizedErrors} full={options.full}>
    {options.area ? <textarea value={value[name]} disabled={disabled} onChange={event => onChange(name, event.target.value)} /> :
      <input type={options.type || 'text'} value={value[name]} disabled={disabled} readOnly={options.readOnly} min={options.type === 'number' ? 1 : undefined}
        max={options.type === 'number' ? 366 : undefined} step={options.type === 'number' ? 1 : undefined} onChange={event => onChange(name, event.target.value)} />}</Field>;
  return <><div className="fgrid">
    {field('business_code', '编号', { required: action === 'create', readOnly: action !== 'create' })}{field('label', '名称', { required: true })}
    <Field name="status" label="状态" required errors={normalizedErrors}><select value={value.status} disabled={disabled} onChange={event => onChange('status', event.target.value)}>
      <option value="" disabled>请选择状态</option><option value="active">启用</option><option value="inactive">停用</option></select></Field>
    {kind === 'shift_profile' && <>{field('anchor_date', '周期起始日期', { required: true, type: 'date' })}{field('cycle_days', '轮换天数', { required: true, type: 'number' })}</>}
    {field('remark', '备注', { area: true, full: true })}</div>
    {kind === 'shift_profile' && <Pattern value={value} defaultPeriods={editor.defaultPeriods} onChange={onChange} disabled={disabled} error={error} onValidationError={onValidationError} />}
    <Issues issues={base ? base.issues : undefined} /></>;
}
ResourceCatalogEditor.Facts = Facts;
ResourceCatalogEditor.fieldPaths = fieldPaths;

export { ResourceCatalogEditor, Facts, fieldPaths };
export default ResourceCatalogEditor;
