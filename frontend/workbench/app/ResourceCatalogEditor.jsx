(function () {
  'use strict';
  const C = window.APSResourceContract, M = window.APSResourceCatalogModel;
  const { Button, ErrorBox, Issues } = window.ResourceControls;
  function Field({ label, name, required, error, children, full }) {
    const id = React.useId(), errors = C.fieldErrors(error).filter(row => row.path === name || row.path === 'fields.' + name);
    return <div className={'field' + (full ? ' full' : '') + (errors.length ? ' err' : '')}>
      <label htmlFor={id}>{label}{required && <span className="req" aria-hidden="true">*</span>}</label>
      {React.cloneElement(children, { id, name, 'aria-label': label, 'aria-required': required || undefined, 'aria-invalid': errors.length ? true : undefined,
        'aria-describedby': errors.length ? id + '-error' : undefined })}
      {errors.length > 0 && <span id={id + '-error'} className="rc-error">{errors.map(row => row.message).join(' ')}</span>}</div>;
  }
  function Pattern({ value, onChange, disabled, error }) {
    const [trim, setTrim] = React.useState(null), [localError, setLocalError] = React.useState(null);
    function generate() {
      setLocalError(null);
      try {
        const length = M.cycle(value.cycle_days);
        if (length < value.pattern.length) { setTrim(length); return; }
        onChange('pattern', M.resized(value.pattern, length));
      } catch (failure) { setLocalError(failure); }
    }
    function rowChange(index, key, next) {
      const rows = value.pattern.map(row => ({ ...row })), row = rows[index]; row[key] = next;
      // Rest has no working interval; retain existing times, canonicalize only empty rest markers.
      if (key === 'is_rest' && next === true) {
        if (!row.shift_start) row.shift_start = '00:00';
        if (!row.shift_end) row.shift_end = '00:00';
      }
      onChange('pattern', rows);
    }
    return <section className="rc-pattern" aria-label="轮换逐日规则">
      <div className="rc-section-head"><h3>逐日规则</h3><span className="muted">{value.pattern.length} 天</span>
        <Button icon="calendar-days" disabled={disabled || trim !== null} onClick={generate}>{value.pattern.length ? '调整逐日规则' : '生成逐日规则'}</Button></div>
      <ErrorBox error={localError} />
      {trim !== null && <div role="alert" className="match-note rc-note">
        <p>将移除第 {trim + 1} 至第 {value.pattern.length} 天，共 {value.pattern.length - trim} 天。其余日期保持原值。</p>
        <div className="rowact"><Button disabled={disabled} onClick={() => { onChange('cycle_days', String(value.pattern.length)); setTrim(null); }}>保留原周期</Button>
          <Button icon="minus" disabled={disabled} onClick={() => { onChange('pattern', M.resized(value.pattern, trim)); setTrim(null); }}>确认移除末尾 {value.pattern.length - trim} 天</Button></div></div>}
      {!value.pattern.length ? <p className="muted">尚未登记逐日规则。</p> : <table className="tbl rc-pattern-table"><thead><tr>
        <th>轮换日</th><th>工作 / 休息</th><th>开始</th><th>结束</th><th>跨夜</th></tr></thead><tbody>
        {value.pattern.map((row, index) => <tr key={index}>
          <td>第 {index + 1} 天</td><td className="field"><select aria-label={'第 ' + (index + 1) + ' 天工作安排'} value={row.is_rest === null ? '' : row.is_rest ? 'rest' : 'work'} disabled={disabled || trim !== null}
            onChange={event => rowChange(index, 'is_rest', event.target.value === 'rest')}><option value="" disabled>请选择</option><option value="work">工作</option><option value="rest">休息</option></select></td>
          {['shift_start', 'shift_end'].map((key, position) => <td key={key}><div className="field"><input type="time" step="60" aria-label={'第 ' + (index + 1) + ' 天' + (position ? '结束' : '开始')}
            value={row[key]} disabled={disabled || trim !== null || row.is_rest === true} onChange={event => rowChange(index, key, event.target.value)}
            aria-invalid={C.fieldErrors(error).some(item => item.path === 'pattern.' + index) || undefined} /></div></td>)}
          <td className="muted">{row.is_rest === true ? '休息' : row.shift_start && row.shift_end ? row.shift_end <= row.shift_start ? '次日结束' : '当日结束' : '未填写'}</td>
        </tr>)}</tbody></table>}
    </section>;
  }
  function Facts({ kind, entity }) {
    const count = M.memberCount(kind, entity);
    return <section className="rc-facts"><div className="rc-section-head"><b>{entity.business_code} · {entity.label}</b><span>{entity.status === 'active' ? '启用' : entity.status === 'inactive' ? '停用' : '旧状态未知'}</span></div>
      <p>已关联{kind === 'machine_group' ? '设备' : '人员'}：{count === null ? '未读取' : count}</p>
      {kind === 'shift_profile' && <><p>周期起始日期：{entity.fields.anchor_date} · 轮换天数：{entity.fields.cycle_days}</p>
        <table className="tbl"><thead><tr><th>轮换日</th><th>工作 / 休息</th><th>开始</th><th>结束</th></tr></thead><tbody>
          {(entity.fields.pattern || []).map(row => <tr key={row.day_offset}><td>第 {row.day_offset + 1} 天</td><td>{row.is_rest ? '休息' : '工作'}</td><td>{row.shift_start}</td><td>{row.shift_end}</td></tr>)}</tbody></table></>}
      <p className="rc-wrap">备注：{entity.fields.remark || '未填写'}</p><Issues issues={entity.issues} /></section>;
  }
  function Editor({ kind, editor, disabled, error, onChange }) {
    const { draft: value, action, base } = editor;
    if (action === 'delete') return <><p>确认删除该{M.names[kind]}？服务端将再次核对引用，已被使用的目录不能删除。</p><Facts kind={kind} entity={base} /></>;
    const field = (name, label, options = {}) => <Field name={name} label={label} required={options.required} error={error} full={options.full}>
      {options.area ? <textarea value={value[name]} disabled={disabled} onChange={event => onChange(name, event.target.value)} /> :
        <input type={options.type || 'text'} value={value[name]} disabled={disabled} readOnly={options.readOnly} min={options.type === 'number' ? 1 : undefined}
          max={options.type === 'number' ? 366 : undefined} step={options.type === 'number' ? 1 : undefined} onChange={event => onChange(name, event.target.value)} />}</Field>;
    return <><div className="fgrid">
      {field('business_code', '编号', { required: action === 'create', readOnly: action !== 'create' })}{field('label', '名称', { required: true })}
      <Field name="status" label="状态" required error={error}><select value={value.status} disabled={disabled} onChange={event => onChange('status', event.target.value)}>
        <option value="" disabled>请选择状态</option><option value="active">启用</option><option value="inactive">停用</option>
        {value.status && !['active', 'inactive'].includes(value.status) && <option value={value.status}>旧状态未知（保持原值）</option>}</select></Field>
      {kind === 'shift_profile' && <>{field('anchor_date', '周期起始日期', { required: true, type: 'date' })}{field('cycle_days', '轮换天数', { required: true, type: 'number' })}</>}
      {field('remark', '备注', { area: true, full: true })}</div>
      {kind === 'shift_profile' && <Pattern value={value} onChange={onChange} disabled={disabled} error={error} />}
      <Issues issues={base && base.issues || []} /></>;
  }
  Editor.Facts = Facts;
  window.ResourceCatalogEditor = Editor;
})();
