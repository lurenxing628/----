(function () {
  'use strict';
  const C = window.APSResourceContract, P = window.APSProcessContract, E = window.ProcessStageEditor, { Button } = window.ResourceControls;
  const numericText = value => value === null ? '' : String(value);
  function mergedGroups(entity) {
    const refs = new Set(E.active(entity).map(row => row.external_group_ref));
    return entity.external_groups.filter(row => row.merge_mode === 'merged' && refs.has(row.ref));
  }
  function build(entity) {
    return { operations: Object.fromEntries(E.active(entity).map(row => [row.ref, { ref: row.ref, setup_hours: numericText(row.setup_hours), unit_hours: numericText(row.unit_hours), external_days: numericText(row.external_days),
      confirmed: !!(row.confirmation && row.confirmation.hours.state === 'confirmed') }])),
      groups: Object.fromEntries(mergedGroups(entity).map(row => [row.ref, numericText(row.total_days)])), zero: false };
  }
  function reconcile(draft, before, after) {
    const next = build(after), original = build(before), old = new Map(before.operations.map(row => [row.ref, row]));
    const oldGroups = new Map(before.external_groups.map(row => [row.ref, row])), newGroups = new Map(after.external_groups.map(row => [row.ref, row]));
    E.active(after).forEach(row => {
      const current = draft.operations[row.ref], previous = original.operations[row.ref], fresh = next.operations[row.ref];
      fresh.confirmed = false;
      if (!current || !previous || old.get(row.ref).source !== row.source) return;
      const fields = row.source === 'internal' ? ['setup_hours', 'unit_hours'] : ['external_days'];
      fields.forEach(key => { if (current[key] !== previous[key]) fresh[key] = current[key]; });
      fresh.confirmed = E.same(old.get(row.ref), row) && E.same(oldGroups.get(row.external_group_ref), newGroups.get(row.external_group_ref)) && current.confirmed;
    });
    mergedGroups(after).forEach(row => {
      if (C.own(original.groups, row.ref) && C.own(draft.groups, row.ref) && draft.groups[row.ref] !== original.groups[row.ref]) next.groups[row.ref] = draft.groups[row.ref];
    });
    return next;
  }
  function number(text, label, positive) {
    if (text === null || text === undefined || String(text).trim() === '' || !Number.isFinite(Number(text)) || (positive ? Number(text) <= 0 : Number(text) < 0))
      throw C.failure(label + (positive ? '必须填写大于 0 的有限数。' : '必须填写大于等于 0 的有限数；空值不能按 0 保存。'));
    return Number(text);
  }
  function input(entity, draft) {
    const merged = new Set(mergedGroups(entity).map(row => row.ref));
    const operations = E.active(entity).map(row => {
      const current = draft.operations[row.ref];
      if (!current.confirmed) throw C.failure('请明确勾选确认工序 ' + row.sequence + ' 的工时 / 周期。');
      if (row.source === 'external') return { ref: row.ref, external_days: P.groupCycle(row, entity.external_groups) || merged.has(row.external_group_ref)
        && current.external_days.trim() === '' && !row.issues.some(item => item.code === 'value_invalid') ? null : number(current.external_days, '工序 ' + row.sequence + ' 外协周期', true) };
      if (row.source !== 'internal') throw C.failure('工序 ' + row.sequence + ' 尚未明确归属。');
      return { ref: row.ref, setup_hours: number(current.setup_hours, '工序 ' + row.sequence + ' 换型工时', false), unit_hours: number(current.unit_hours, '工序 ' + row.sequence + ' 单件工时', false) };
    });
    if (!operations.length) throw C.failure('尚无有效工序，不能保存工时。');
    if (operations.some(row => row.unit_hours === 0) && !draft.zero) throw C.failure('单件工时为 0，需要明确勾选复核。');
    return { operations, groups: mergedGroups(entity).map(row => ({ ref: row.ref, total_days: number(draft.groups[row.ref], '外协组 ' + row.start_sequence + ' 至 ' + row.end_sequence + ' 总周期', true) })), confirm_zero_unit_hours: draft.zero };
  }
  function ProcessHoursEditor({ adapter, result, command, disabled, saved, onDirty, onFileAction }) {
    const model = E.useDraft({ result, adapter, stage: 'hours', build, reconcile, saved, onDirty });
    const entity = model.base.data, draft = model.draft, paging = E.usePage(entity.operations);
    const blocked = disabled || command.locked || command.phase === 'done', stageReason = E.reason(model, adapter, 'hours');
    const editBlocked = blocked || entity.workflow.source.state !== 'confirmed' || entity.capabilities.stage_confirm !== true;
    function change(ref, patch) { model.edit(current => ({ ...current, zero: false, operations: { ...current.operations, [ref]: { ...current.operations[ref], ...patch } } })); }
    function changeGroup(ref, total) {
      model.edit(current => {
        const operations = { ...current.operations };
        E.active(entity).filter(row => row.external_group_ref === ref).forEach(row => { operations[row.ref] = { ...operations[row.ref], confirmed: false }; });
        return { ...current, operations, groups: { ...current.groups, [ref]: total } };
      });
    }
    async function save() {
      if (blocked || stageReason) return;
      try { const body = input(entity, draft); model.setError(null); await command.submit('process', 'hours_confirm', entity.ref, entity.write_context, body); }
      catch (error) { model.setError(error); }
    }
    const all = paging.rows.filter(row => row.status === 'active');
    return <section data-process-hours-editor><div className="toolbar"><E.Search paging={paging} disabled={blocked} /><span>有效工序 {E.active(entity).length}</span><span className="tb-spacer" /><window.ProcessFileButtons capabilities={entity.capabilities} disabled={blocked} hoursOnly onAction={onFileAction} /></div>
      <div className="toolbar"><label><input type="checkbox" aria-label="确认本页已核对工时" checked={!!all.length && all.every(row => draft.operations[row.ref].confirmed)} disabled={editBlocked || !all.length}
        onChange={event => { const confirmed = event.target.checked; model.edit(current => { const operations = { ...current.operations }; all.forEach(row => { operations[row.ref] = { ...operations[row.ref], confirmed }; }); return { ...current, operations }; }); }} />确认本页已核对工时</label></div>
      <div className="wb-table-frame"><div className="card-scroll wb-table-shell"><table className="tbl wb-table" aria-label="工时定额明细" style={{ minWidth: 1000, tableLayout: 'fixed' }}><thead><tr>
        <th style={{ width: 180 }}>工序 / 工种</th><th style={{ width: 85 }}>归属</th><th style={{ width: 140 }}>换型工时（h）</th><th style={{ width: 140 }}>单件工时（h）</th><th style={{ width: 140 }}>外协周期（天）</th><th>核对 / 确认记录</th></tr></thead>
        <tbody>{paging.rows.map(row => {
          const current = draft.operations[row.ref], inactive = !current, cycle = P.groupCycle(row, entity.external_groups);
          const cell = (key, title) => <td><input className="wt-in" type="number" step="any" min="0" aria-label={'工序 ' + row.sequence + ' ' + title} placeholder="未填写" value={current ? current[key] : numericText(row[key])} disabled={editBlocked || inactive}
            onChange={event => change(row.ref, { [key]: event.target.value, confirmed: false })} style={{ width: '100%' }} />{key === 'unit_hours' && current && current[key].trim() !== '' && Number(current[key]) === 0 && <span className="prov">0 · 请复核</span>}</td>;
          return <tr key={row.ref}><td><b>{row.sequence}</b> {row.label}<div className="muted">{row.op_type_label || '未绑定工种'}</div></td><td>{window.APSProcessContract.sourceLabel(row.source)}</td>
            {row.source === 'external' ? <td colSpan={2} className="muted">外协工序不填工时</td> : <>{cell('setup_hours', '换型工时')}{cell('unit_hours', '单件工时')}</>}
            {row.source === 'external' ? cycle ? <td data-process-cycle-group={row.external_group_ref}>{cycle}</td> : cell('external_days', '外协周期') : <td className="muted">不适用</td>}
            <td>{inactive ? '已停用工序' : <label><input type="checkbox" aria-label={'确认工序 ' + row.sequence + ' 工时'} checked={current.confirmed} disabled={editBlocked} onChange={event => change(row.ref, { confirmed: event.target.checked })} />已核对</label>}
              <div className="muted"><E.Confirmation record={row.confirmation && row.confirmation.hours} /></div><window.ResourceControls.Issues issues={row.issues} /></td></tr>;
        })}{!paging.rows.length && <tr><td colSpan={6}>{entity.operations.length ? '没有匹配的工序。' : '尚无工序记录。'}</td></tr>}</tbody></table></div></div><E.Pager paging={paging} disabled={blocked} />
      <E.Groups rows={entity.external_groups} totals={draft.groups} disabled={editBlocked} onTotal={changeGroup} />
      <p><label><input type="checkbox" aria-label="已复核单件工时为0" checked={draft.zero} disabled={editBlocked} onChange={event => model.edit(current => ({ ...current, zero: event.target.checked }))} />已复核单件工时为 0，确认按 0 保存</label></p>
      <E.Feedback model={model} disabled={blocked} /><div className="pd-foot"><span className="muted">空值不补 0；合并组成员周期可空，按组总周期。已填周期必须大于 0。</span><Button className="btn primary" icon="check" disabled={blocked} reason={stageReason} onClick={save}>保存工时</Button></div>
    </section>;
  }
  window.ProcessHoursEditor = ProcessHoursEditor;
})();
