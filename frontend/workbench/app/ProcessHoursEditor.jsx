(function () {
  'use strict';
  const C = window.APSResourceContract, P = window.APSProcessContract, E = window.ProcessStageEditor, { Button, Modal, Issues } = window.ResourceControls;
  const numericText = value => value === null ? '' : String(value);
  function mergedGroups(entity) {
    const refs = new Set(E.active(entity).map(row => row.external_group_ref));
    return entity.external_groups.filter(row => row.merge_mode === 'merged' && refs.has(row.ref));
  }
  function build(entity) {
    return { operations: Object.fromEntries(E.active(entity).map(row => [row.ref, { ref: row.ref, setup_hours: numericText(row.setup_hours), unit_hours: numericText(row.unit_hours), external_days: numericText(row.external_days) }])),
      groups: Object.fromEntries(mergedGroups(entity).map(row => [row.ref, numericText(row.total_days)])) };
  }
  function reconcile(draft, before, after) {
    const next = build(after), original = build(before), old = new Map(before.operations.map(row => [row.ref, row]));
    E.active(after).forEach(row => {
      const current = draft.operations[row.ref], previous = original.operations[row.ref], fresh = next.operations[row.ref];
      if (!current || !previous || old.get(row.ref).source !== row.source) return;
      (row.source === 'internal' ? ['setup_hours', 'unit_hours'] : ['external_days']).forEach(key => { if (current[key] !== previous[key]) fresh[key] = current[key]; });
    });
    mergedGroups(after).forEach(row => {
      if (C.own(original.groups, row.ref) && C.own(draft.groups, row.ref) && draft.groups[row.ref] !== original.groups[row.ref]) next.groups[row.ref] = draft.groups[row.ref];
    });
    return next;
  }
  function number(text, label, positive) {
    if (text === null || text === undefined || String(text).trim() === '' || !Number.isFinite(Number(text)) || (positive ? Number(text) <= 0 : Number(text) < 0))
      throw C.failure(label + (positive ? '必须填写大于 0 的数。' : '必须填写大于等于 0 的数。'));
    return Number(text);
  }
  function input(entity, draft, pageSize) {
    const merged = new Set(mergedGroups(entity).map(row => row.ref));
    const operations = E.active(entity).map(row => {
      const current = draft.operations[row.ref];
      try {
        if (row.source === 'external') return { ref: row.ref, external_days: P.groupCycle(row, entity.external_groups) || merged.has(row.external_group_ref)
          && current.external_days.trim() === '' && !row.issues.some(item => item.code === 'value_invalid') ? null : number(current.external_days, '工序 ' + row.sequence + ' 外协周期', true) };
        if (row.source !== 'internal') throw C.failure('工序 ' + row.sequence + ' 请先选定归属。');
        return { ref: row.ref, setup_hours: number(current.setup_hours, '工序 ' + row.sequence + ' 换型工时', false), unit_hours: number(current.unit_hours, '工序 ' + row.sequence + ' 单件工时', false) };
      } catch (error) { error.locate_page = Math.floor(entity.operations.indexOf(row) / pageSize) + 1; throw error; }
    });
    if (!operations.length) throw C.failure('尚无有效工序，不能保存工时。');
    return { operations, groups: mergedGroups(entity).map(row => ({ ref: row.ref, total_days: number(draft.groups[row.ref], '外协组 ' + row.start_sequence + ' 至 ' + row.end_sequence + ' 总周期', true) })), confirm_zero_unit_hours: false };
  }
  function zeroRows(entity, body) {
    const before = new Map(entity.operations.map(row => [row.ref, row]));
    return body.operations.filter(row => {
      const old = before.get(row.ref);
      return row.unit_hours === 0 && (old.confirmation.hours.state !== 'confirmed' || old.unit_hours !== row.unit_hours || old.setup_hours !== row.setup_hours);
    }).map(row => before.get(row.ref));
  }
  function ProcessHoursEditor({ adapter, result, command, disabled, saved, onDirty, onOverlay, onFileAction }) {
    const model = E.useDraft({ result, adapter, stage: 'hours', build, reconcile, saved, onDirty });
    const entity = model.base.data, draft = model.draft, paging = E.usePage(entity.operations), [zero, setZero] = React.useState(null);
    const blocked = disabled || command.locked || command.phase === 'done', stageReason = E.reason(model, adapter, 'hours');
    const editBlocked = blocked || entity.workflow.source.state !== 'confirmed' || entity.capabilities.stage_confirm !== true;
    React.useEffect(() => { setZero(null); }, [draft, model.base, model.review, disabled]);
    React.useEffect(() => { if (onOverlay) onOverlay(!!zero); return () => { if (onOverlay) onOverlay(false); }; }, [!!zero, onOverlay]);
    function change(ref, patch) { model.edit(current => ({ ...current, operations: { ...current.operations, [ref]: { ...current.operations[ref], ...patch } } })); }
    function changeGroup(ref, total) { model.edit(current => ({ ...current, groups: { ...current.groups, [ref]: total } })); }
    async function save(acknowledged = false) {
      if (blocked || stageReason) return;
      try {
        const body = input(entity, draft, paging.page.size), rows = zeroRows(entity, body);
        if (rows.length && !acknowledged) { setZero(rows); return; }
        setZero(null); model.setError(null);
        await command.submit('process', 'hours_confirm', entity.ref, entity.write_context, { ...body, confirm_zero_unit_hours: acknowledged === true });
      } catch (error) { model.setError(error); }
    }
    const active = E.active(entity), internal = paging.rows.filter(row => row.source !== 'external'), external = paging.rows.filter(row => row.source === 'external');
    function operation(row) { return <><b>{row.sequence}</b> {row.label}<div className="muted">{row.op_type_label || '未选工种'}</div></>; }
    function record(row) { return <>{row.status !== 'active' ? '已停用工序' : <E.Confirmation record={row.confirmation && row.confirmation.hours} />}<Issues issues={row.issues.filter(item => item.code !== 'zero_unit_hours_review')} /></>; }
    function cell(row, key, title, positive = false) {
      const current = draft.operations[row.ref];
      return <input className="wt-in" type="number" step="any" min="0" aria-label={'工序 ' + row.sequence + ' ' + title} placeholder={positive ? '大于 0' : '未填写'} value={current ? current[key] : numericText(row[key])} disabled={editBlocked || !current}
        onChange={event => change(row.ref, { [key]: event.target.value })} />;
    }
    return <section data-process-hours-editor><div className="toolbar"><E.Search paging={paging} disabled={blocked} /><span>共 {active.length} 道有效工序</span><span className="tb-spacer" /><window.ProcessFileButtons capabilities={entity.capabilities} disabled={blocked} hoursOnly onAction={onFileAction} /></div>
      <section className="process-hours-section" aria-label="自制工时"><h3>自制工时</h3><p className="muted">加工时长 = 换型工时 + 单件工时 × 批次数量。</p>
        <div className="wb-table-frame"><table className="tbl wb-table wb-table--editable" aria-label="自制工时明细"><caption className="wb-visually-hidden">自制工时明细</caption><colgroup><col style={{ width: '32%' }} /><col style={{ width: '22%' }} /><col style={{ width: '22%' }} /><col style={{ width: '24%' }} /></colgroup>
          <thead><tr><th scope="col">工序 / 工种</th><th scope="col">换型工时（小时）</th><th scope="col">单件工时（小时）</th><th scope="col">保存记录</th></tr></thead>
          <tbody>{internal.map(row => <tr key={row.ref}><td>{operation(row)}</td><td>{cell(row, 'setup_hours', '换型工时')}</td><td>{cell(row, 'unit_hours', '单件工时')}</td><td>{record(row)}</td></tr>)}
            {!internal.length && <tr><td colSpan={4}>当前页没有自制工序。</td></tr>}</tbody></table></div></section>
      <section className="process-hours-section" aria-label="外协周期"><h3>外协周期</h3>
        <div className="wb-table-frame"><table className="tbl wb-table wb-table--editable" aria-label="外协周期明细"><caption className="wb-visually-hidden">外协周期明细</caption><colgroup><col style={{ width: '32%' }} /><col style={{ width: '22%' }} /><col style={{ width: '22%' }} /><col style={{ width: '24%' }} /></colgroup>
          <thead><tr><th scope="col">工序 / 工种</th><th scope="col">供应商</th><th scope="col">周期（天）</th><th scope="col">保存记录</th></tr></thead>
          <tbody>{external.map(row => { const cycle = P.groupCycle(row, entity.external_groups); return <tr key={row.ref}><td>{operation(row)}</td><td>{row.supplier_label || '未选供应商'}</td>
            <td>{cycle ? <span className="process-group-cycle" data-process-cycle-group={row.external_group_ref}>{cycle}<small>在下方外协组填写统一周期</small></span> : cell(row, 'external_days', '外协周期', true)}</td><td>{record(row)}</td></tr>; })}
            {!external.length && <tr><td colSpan={4}>当前页没有外协工序。</td></tr>}</tbody></table></div>
        {!!mergedGroups(entity).length && <E.Groups rows={mergedGroups(entity)} totals={draft.groups} disabled={editBlocked} onTotal={changeGroup} />}</section>
      <E.Pager paging={paging} disabled={blocked} />
      <E.Feedback model={model} disabled={blocked} paging={paging} /><div className="pd-foot"><span className="muted">保存全部 {active.length} 道有效工序，包含其他页和筛选隐藏的工序。</span><Button className="btn primary" icon="check" disabled={blocked} reason={stageReason} onClick={() => save()}>保存工时</Button></div>
      {zero && ReactDOM.createPortal(<div className="plana process-detail"><Modal title="按零单件工时保存" icon="check" onClose={() => setZero(null)} locked={blocked} footer={<><Button disabled={blocked} onClick={() => setZero(null)}>返回修改</Button><Button className="btn primary" icon="check" disabled={blocked} onClick={() => save(true)}>按 0 保存</Button></>}>
        <div className="modal-b"><p>以下工序的单件工时为 0，排产只计算换型工时，数量增加不会增加加工时长。</p><ul>{zero.map(row => <li key={row.ref}>工序 {row.sequence} · {row.label}</li>)}</ul></div></Modal></div>, document.body)}
    </section>;
  }
  window.ProcessHoursEditor = ProcessHoursEditor;
})();
