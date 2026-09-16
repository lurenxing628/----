(function () {
  'use strict';
  const C = window.APSResourceContract, S = window.APSResourceSession;
  const { Button, Icon, ErrorBox, Modal } = window.ResourceControls;
  const levels = [['beginner', '初级'], ['normal', '普通'], ['expert', '熟练']];
  const primaries = [['no', '否'], ['yes', '是']];
  const fields = rows => rows.map(({ machine_ref, skill_level, is_primary }) => ({ machine_ref, skill_level, is_primary }));
  const isPrimary = value => ['yes', 'y', 'true', '是', '主', '主操', 'on', '1'].includes(String(value).trim().toLowerCase());
  function PermissionSelect({ value, choices, label, disabled, onChange }) {
    const old = !choices.some(([item]) => item === value);
    return <select aria-label={label} value={JSON.stringify(value)} disabled={disabled} onChange={event => onChange(JSON.parse(event.target.value))}>
      {old && <option value={JSON.stringify(value)}>原值：{value === null ? '未填写' : String(value)}</option>}
      {choices.map(([item, name]) => <option key={item} value={JSON.stringify(item)}>{name}</option>)}
    </select>;
  }
  function OperatorMachinePermissions({ adapter, entity, source, command, onClose, refreshState = {}, onRefresh, Feedback }) {
    const [current, setCurrent] = React.useState(entity);
    const original = current.relationships.machine_permissions;
    const [rows, setRows] = React.useState(() => Array.isArray(original) ? original.map(row => ({ ...row })) : []);
    const [search, setSearch] = React.useState(''), [query, setQuery] = React.useState(''), [selected, setSelected] = React.useState('');
    const [preview, setPreview] = React.useState(null), [busy, setBusy] = React.useState(false), [error, setError] = React.useState(null);
    const done = command.phase === 'done', disabled = busy || command.locked || done;
    const read = S.useQuery(signal => adapter.choices('machine', { query, page: 1, size: 20, sort: 'business_code', direction: 'asc' }, signal), [adapter, query]);
    const choices = read.result && read.result.data.entities || [];
    const reason = !Array.isArray(original) ? '设备关联尚未完整读取，请关闭后重新打开人员详情。'
      : C.blocked(current.write_context, 'operator', 'update', source);
    const owner = window.WorkbenchGuards.useDirtyGuard({ dirty: !done && JSON.stringify(fields(rows)) !== JSON.stringify(fields(original || [])),
      message: '可操作设备有尚未保存的修改。', locked: command.locked });
    async function close(detail) {
      if (disabled && !done) return;
      if (!(detail && detail.guardConfirmed === true && detail.guardOwner === owner) && !await window.WorkbenchGuards.confirmLeave({ owner })) return;
      onClose();
    }
    function change(next) { setRows(next); setPreview(null); setError(null); }
    function edit(ref, key, value) {
      change(rows.map(row => row.machine_ref === ref ? { ...row, [key]: value }
        : key === 'is_primary' && value === 'yes' && isPrimary(row.is_primary) ? { ...row, is_primary: 'no' } : row));
    }
    function add() {
      const machine = choices.find(item => item.ref === selected);
      if (!machine || rows.some(row => row.machine_ref === selected)) return;
      change(rows.concat({ machine_ref: machine.ref, business_code: machine.business_code, label: machine.label, skill_level: 'normal', is_primary: 'no' }));
      setSelected('');
    }
    async function reload() {
      if (disabled || !await window.WorkbenchGuards.confirmLeave({ owner })) return;
      setBusy(true); setError(null);
      try {
        const result = C.query(await adapter.detail('operator', entity.ref, new AbortController().signal), 'entity');
        if (result.data.ref !== entity.ref || result.meta.source !== source || !Array.isArray(result.data.relationships.machine_permissions))
          throw C.failure('没有取得当前人员的完整设备关联。');
        setCurrent(result.data); setRows(result.data.relationships.machine_permissions.map(row => ({ ...row })));
        setPreview(null); setSelected('');
      } catch (failure) { setError(failure); }
      finally { setBusy(false); }
    }
    async function inspect() {
      if (disabled || reason) return;
      setBusy(true); setError(null); setPreview(null);
      try {
        const result = await adapter.preview('entities/operator/' + entity.ref + '/machine-permissions/preview',
          { machine_permissions: fields(rows), write_token: current.write_context.write_token }, new AbortController().signal);
        const data = result && result.data;
        if (!data || data.operator_ref !== entity.ref || !Array.isArray(data.rows) || !data.write_context
            || data.write_context.capabilities['operator.machine_permissions'] !== true || typeof data.preview_ref !== 'string')
          throw C.failure('设备关联预览不完整，请重新预览。');
        setPreview(data);
      } catch (failure) { setError(failure); }
      finally { setBusy(false); }
    }
    const changed = preview ? preview.rows.filter(row => row.result !== 'unchanged') : [];
    const display = (key, value) => ((key === 'skill_level' ? levels : primaries).find(([item]) => item === value) || [null, value === null ? '未填写' : String(value)])[1];
    return <div className="wb-machine-permissions-host"><Modal title={'可操作设备 · ' + current.business_code + ' · ' + current.label} icon="machine" onClose={close} guardOwner={owner} locked={command.locked || busy}
      footer={<><Button onClick={close} disabled={command.locked || busy}>{done ? '关闭' : '取消'}</Button>
        {!done && (preview ? <Button icon="check" className="btn primary" busy={disabled} onClick={() => command.submit('operator', 'machine_permissions', entity.ref,
          preview.write_context, { preview_ref: preview.preview_ref })}>确认保存设备关联</Button>
          : <Button icon="check" className="btn primary" reason={reason} busy={disabled} onClick={inspect}>预览变更</Button>)}</>}>
      <div className="modal-b scroll wb-machine-permissions">
        <p>可操作设备决定这个人能分配到哪些设备。工种技能在人员资料中单独维护；同一人员最多设置一台主操设备。</p>
        {!done && <form className="toolbar" onSubmit={event => { event.preventDefault(); setQuery(search.trim()); setSelected(''); }}>
          <label className="search"><span className="ic"><Icon name="search" /></span><input type="search" aria-label="搜索可关联设备" placeholder="设备编号、名称" value={search} disabled={disabled} onChange={event => setSearch(event.target.value)} /></label>
          <Button icon="search" type="submit" disabled={disabled} busy={read.loading}>搜索设备</Button>
          <select aria-label="选择关联设备" value={selected} disabled={disabled || read.loading} onChange={event => setSelected(event.target.value)}>
            <option value="">请选择设备</option>{choices.filter(item => !rows.some(row => row.machine_ref === item.ref)).map(item => <option key={item.ref} value={item.ref}>{item.business_code} · {item.label}</option>)}
          </select><Button icon="plus" disabled={disabled || !selected} onClick={add}>添加关联</Button>
          {read.result && read.result.data.page.total > 20 && <span className="muted">显示前 20 台，请输入编号或名称缩小范围。</span>}
        </form>}
        <ErrorBox error={read.error} />
        <div className="wb-table-frame"><table className="wb-table"><caption>全部可操作设备（{rows.length} 台）</caption><thead><tr><th>设备</th><th>技能等级</th><th>主操设备</th><th>操作</th></tr></thead>
          <tbody>{rows.map(row => <tr key={row.machine_ref}><td>{row.business_code} · {row.label}</td><td><PermissionSelect value={row.skill_level} choices={levels} label={'技能等级 ' + row.business_code} disabled={disabled} onChange={value => edit(row.machine_ref, 'skill_level', value)} /></td>
            <td><PermissionSelect value={row.is_primary} choices={primaries} label={'主操设备 ' + row.business_code} disabled={disabled} onChange={value => edit(row.machine_ref, 'is_primary', value)} /></td>
            <td><Button disabled={disabled} onClick={() => change(rows.filter(item => item.machine_ref !== row.machine_ref))}>解除关联</Button></td></tr>)}</tbody></table>
          {!rows.length && <p className="muted">尚未设置可操作设备。</p>}
        </div>
        {preview && !done && <section className="wb-permission-preview" aria-label="设备关联变更预览"><h3>本次变更</h3>
          {changed.length ? <ul>{changed.map(row => <li key={row.entity_ref}><strong>{({ new: '新增关联', delete: '解除关联', update: '修改关联' })[row.result]}</strong>：{row.business_code} · {row.label}
            {row.result === 'update' && Object.entries(row.changes).map(([key, pair]) => <span key={key}>；{key === 'skill_level' ? '技能等级' : '主操设备'}：{display(key, pair[0])} → {display(key, pair[1])}</span>)}</li>)}</ul> : <p>设备关联没有变化。</p>}
          <p className="muted">保存后，新的资源分配按这份设备关联判断；已保存的计划和报工记录保留。</p></section>}
        <ErrorBox error={error} /><Feedback command={command} />
        {!done && (error || command.error) && <Button icon="refresh-cw" disabled={disabled} onClick={reload}>重新读取设备关联</Button>}
        {done && <><p role="status">{refreshState.done ? '已重新读取人员资料，设备关联已保存。' : refreshState.loading ? '正在重新读取人员资料…' : '请刷新保存结果，核对人员资料。'}</p>
          <ErrorBox error={refreshState.error} />{refreshState.error && <Button icon="refresh-cw" onClick={onRefresh}>刷新保存结果</Button>}</>}
      </div>
    </Modal></div>;
  }
  window.OperatorMachinePermissions = OperatorMachinePermissions;
})();
