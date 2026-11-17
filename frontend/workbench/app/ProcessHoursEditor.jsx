import React, { createPortal } from './shared/runtime/react.js';
import C from './resource-contract.js';
import P from './ProcessContract.js';
import E from './ProcessStageEditor.jsx';
import { Button, FieldCell, Modal, Issues } from './ResourceControls.jsx';
import ProcessFileButtons from './ProcessControls.jsx';
import ProcessGroupEditor from './ProcessGroupEditor.jsx';
import { failure } from './shared/contract/kit.js';

const numericText = value => value === null ? '' : String(value);
// 工时页负责的工序项：三列数值格，以及本地检查发现的未定归属。
const cellKeys = ['setup_hours', 'unit_hours', 'external_days', 'source'];
function mergedGroups(entity, active) {
  const refs = new Set(active.map(row => row.external_group_ref));
  return entity.external_groups.filter(row => row.merge_mode === 'merged' && refs.has(row.ref));
}
function build(entity) {
  const active = E.active(entity);
  return { operations: Object.fromEntries(active.map(row => [row.ref, { ref: row.ref, setup_hours: numericText(row.setup_hours), unit_hours: numericText(row.unit_hours), external_days: numericText(row.external_days) }])),
    groups: Object.fromEntries(mergedGroups(entity, active).map(row => [row.ref, numericText(row.total_days)])) };
}
function reconcile(draft, before, after) {
  const next = build(after), original = build(before), old = new Map(before.operations.map(row => [row.ref, row])), active = E.active(after);
  active.forEach(row => {
    const current = draft.operations[row.ref], previous = original.operations[row.ref], fresh = next.operations[row.ref];
    if (!current || !previous || old.get(row.ref).source !== row.source || old.get(row.ref).op_type_ref !== row.op_type_ref) return;
    (row.source === 'internal' ? ['setup_hours', 'unit_hours'] : ['external_days']).forEach(key => { if (current[key] !== previous[key]) fresh[key] = current[key]; });
  });
  mergedGroups(after, active).forEach(row => {
    if (C.own(original.groups, row.ref) && C.own(draft.groups, row.ref) && draft.groups[row.ref] !== original.groups[row.ref]) next.groups[row.ref] = draft.groups[row.ref];
  });
  return next;
}
// 提交前只确认填了能解析成有限数的值；工时与周期的取值范围由后端校验，422 带字段路径。
// 本地错误与后端用同一套路径：工序格是 operations.<工序编号>.<项>，已有合并组是 groups.<外协组编号>.total_days。
function rejectAt(path, message) { throw failure(message, { fields: [{ path, message }] }); }
function number(text, path, label) {
  if (text === null || text === undefined || String(text).trim() === '' || !Number.isFinite(Number(text))) rejectAt(path, label + '要填写数字。');
  return Number(text);
}
function input(entity, draft) {
  const active = E.active(entity), mergedRows = mergedGroups(entity, active), merged = new Set(mergedRows.map(row => row.ref)), groups = P.groupIndex(entity.external_groups);
  const operations = active.map(row => {
    const current = draft.operations[row.ref], at = key => 'operations.' + row.ref + '.' + key;
    // 合并外协段里的工序周期由整段周期决定，留空就提交 null。
    if (row.source === 'external') return { ref: row.ref, external_days: P.groupCycle(row, groups) || merged.has(row.external_group_ref)
      && current.external_days.trim() === '' ? null : number(current.external_days, at('external_days'), '工序 ' + row.sequence + ' 外协周期') };
    if (row.source !== 'internal') rejectAt(at('source'), '工序 ' + row.sequence + ' 请先选定归属。');
    return { ref: row.ref, setup_hours: number(current.setup_hours, at('setup_hours'), '工序 ' + row.sequence + ' 换型工时'), unit_hours: number(current.unit_hours, at('unit_hours'), '工序 ' + row.sequence + ' 单件工时') };
  });
  if (!operations.length) throw failure('尚无有效工序，不能保存工时。');
  return { operations, groups: mergedRows.map(row => ({ ref: row.ref,
    total_days: number(draft.groups[row.ref], 'groups.' + row.ref + '.total_days', '外协组 ' + row.start_sequence + ' 至 ' + row.end_sequence + ' 总周期') })), confirm_zero_unit_hours: false };
}
function zeroRows(entity, body) {
  const before = new Map(entity.operations.map(row => [row.ref, row])), rows = [];
  for (const row of body.operations) {
    const old = before.get(row.ref);
    if (row.unit_hours === 0 && (old.confirmation.hours.state !== 'confirmed' || old.unit_hours !== row.unit_hours || old.setup_hours !== row.setup_hours)) rows.push(old);
  }
  return rows;
}
function ProcessHoursEditor({ result, command, disabled, saved, groupSaved, onDirty, onOverlay, onFileAction }) {
  const model = E.useDraft({ result, stage: 'hours', build, reconcile, saved, onDirty });
  const entity = model.base.data, draft = model.draft, paging = E.usePage(entity.operations), [zero, setZero] = React.useState(null), [groupsOpen, setGroupsOpen] = React.useState(false);
  const groups = React.useMemo(() => P.groupIndex(entity.external_groups), [entity.external_groups]);
  const blocked = disabled || command.locked || command.phase === 'done', stageReason = E.reason(model, 'hours');
  const editBlocked = blocked || entity.workflow.source.state !== 'confirmed';
  const originalTypes = new Map(entity.operations.map(row => [row.ref, row]));
  const changedTypes = model.review ? E.active(model.review.data).filter(row => {
    const old = originalTypes.get(row.ref);
    return old && old.source === row.source && old.op_type_ref !== row.op_type_ref;
  }) : [];
  React.useEffect(() => { setZero(null); }, [draft, model.base, model.review, disabled]);
  React.useEffect(() => { setGroupsOpen(false); }, [groupSaved]);
  // A verified receipt already confirms the group write. Close its overlay even
  // if the following detail read fails, so the parent's recovery control is reachable.
  React.useEffect(() => {
    if (command.phase === 'done' && command.intent && command.intent.action === 'groups_confirm') setGroupsOpen(false);
  }, [command.phase, command.intent]);
  React.useEffect(() => { if (onOverlay) onOverlay(!!zero || groupsOpen); return () => { if (onOverlay) onOverlay(false); }; }, [!!zero, groupsOpen, onOverlay]);
  // 改了输入就清掉被拒的提交，标红跟着消失；本页检查的错误由 model.edit 清。
  function change(ref, patch) { model.edit(current => ({ ...current, operations: { ...current.operations, [ref]: { ...current.operations[ref], ...patch } } })); command.clearRejection(); }
  function changeGroup(ref, total) { model.edit(current => ({ ...current, groups: { ...current.groups, [ref]: total } })); command.clearRejection(); }
  async function save(acknowledged = false) {
    if (blocked || stageReason) return;
    try {
      const body = input(entity, draft), rows = zeroRows(entity, body);
      if (rows.length && !acknowledged) { setZero(rows); return; }
      setZero(null); model.setError(null);
      await command.submit('process', 'hours_confirm', entity.ref, entity.write_context, { ...body, confirm_zero_unit_hours: acknowledged === true });
    } catch (error) { model.setError(error); }
  }
  const active = E.active(entity), merged = mergedGroups(entity, active), internal = paging.rows.filter(row => row.source !== 'external'), external = paging.rows.filter(row => row.source === 'external');
  // 本页检查的错误优先；否则是这道工艺上次提交被拒的错误（工时确认的路径不会和归属、外协段的路径重名）。
  const shownError = model.error || command.error;
  function operation(row) { return <><b>{row.sequence}</b> {row.label}<div className="muted">{row.op_type_label || '未选工种'}</div></>; }
  function record(row) { return <>{row.status !== 'active' ? '已停用工序' : <E.Confirmation record={row.confirmation.hours} />}<Issues issues={row.issues.filter(item => item.code !== 'zero_unit_hours_review')} /></>; }
  function cell(row, key, title, positive = false) {
    const current = draft.operations[row.ref];
    return <FieldCell path={'operations.' + row.ref + '.' + key} error={shownError}><input className="wt-in" type="number" step="any" min="0" aria-label={'工序 ' + row.sequence + ' ' + title} placeholder={positive ? '大于 0' : '未填写'} value={current ? current[key] : numericText(row[key])} disabled={editBlocked || !current}
      onChange={event => change(row.ref, { [key]: event.target.value })} /></FieldCell>;
  }
  return <section data-process-hours-editor><div className="toolbar"><E.Search paging={paging} disabled={blocked} /><span>共 {active.length} 道有效工序</span><span className="tb-spacer" /><ProcessFileButtons disabled={blocked} hoursOnly onAction={onFileAction} /></div>
    <section className="process-hours-section" aria-label="自制工时"><h3>自制工时</h3><p className="muted">加工时长 = 换型工时 + 单件工时 × 批次数量。</p>
      <div className="wb-table-frame"><table className="tbl wb-table wb-table--editable" aria-label="自制工时明细"><caption className="wb-visually-hidden">自制工时明细</caption><colgroup><col style={{ width: '32%' }} /><col style={{ width: '22%' }} /><col style={{ width: '22%' }} /><col style={{ width: '24%' }} /></colgroup>
        <thead><tr><th scope="col">工序 / 工种</th><th scope="col">换型工时（小时）</th><th scope="col">单件工时（小时）</th><th scope="col">保存记录</th></tr></thead>
        <tbody>{internal.map(row => <tr key={row.ref}><td>{operation(row)}</td><td>{cell(row, 'setup_hours', '换型工时')}</td><td>{cell(row, 'unit_hours', '单件工时')}</td><td>{record(row)}</td></tr>)}
          {!internal.length && <tr><td colSpan={4}>当前页没有自制工序。</td></tr>}</tbody></table></div></section>
    <section className="process-hours-section" aria-label="外协周期"><div className="toolbar"><h3>外协周期</h3><span className="tb-spacer" /><Button icon="square-pen" disabled={blocked || entity.workflow.route.state !== 'confirmed'} onClick={() => setGroupsOpen(true)}>管理外协段</Button></div><p className="muted">同一次送出的连续外协工序可设为一段，整段只计算一次统一周期。中间回厂加工后再送出的工序请另建一段。</p>
      <div className="wb-table-frame"><table className="tbl wb-table wb-table--editable" aria-label="外协周期明细"><caption className="wb-visually-hidden">外协周期明细</caption><colgroup><col style={{ width: '32%' }} /><col style={{ width: '22%' }} /><col style={{ width: '22%' }} /><col style={{ width: '24%' }} /></colgroup>
        <thead><tr><th scope="col">工序 / 工种</th><th scope="col">供应商</th><th scope="col">周期（天）</th><th scope="col">保存记录</th></tr></thead>
        <tbody>{external.map(row => { const cycle = P.groupCycle(row, groups); return <tr key={row.ref}><td>{operation(row)}</td><td>{row.supplier_label || '未选供应商'}</td>
          <td>{cycle ? <span className="process-group-cycle" data-process-cycle-group={row.external_group_ref}>{cycle}<small>在下方外协组填写统一周期</small></span> : cell(row, 'external_days', '外协周期', true)}</td><td>{record(row)}</td></tr>; })}
          {!external.length && <tr><td colSpan={4}>当前页没有外协工序。</td></tr>}</tbody></table></div>
      {!!merged.length && <E.Groups rows={merged} totals={draft.groups} disabled={editBlocked} onTotal={changeGroup} title="外协段统一周期" error={shownError} />}</section>
    <E.Pager paging={paging} disabled={blocked} />
    {!!changedTypes.length && <p role="status">工序 {changedTypes.map(row => row.sequence).join('、')} 的实际工种已更换。接受最新资料后将采用新工种的工时，原工种未保存的工时不会沿用，请重新核对填写。</p>}
    <E.Feedback model={model} disabled={blocked} paging={paging} page={E.errorPage(shownError, entity.operations, paging.page.size, cellKeys)} /><div className="pd-foot"><span className="muted">保存全部 {active.length} 道有效工序，包含其他页和筛选隐藏的工序。</span><Button className="btn primary" icon="check" disabled={blocked} reason={stageReason} onClick={() => save()}>保存工时</Button></div>
    {groupsOpen && <ProcessGroupEditor result={result} command={command} disabled={blocked} onDirty={onDirty} onClose={() => setGroupsOpen(false)} />}
    {zero && createPortal(<div className="plana process-detail"><Modal title="按零单件工时保存" icon="check" onClose={() => setZero(null)} locked={blocked} footer={<><Button disabled={blocked} onClick={() => setZero(null)}>返回修改</Button><Button className="btn primary" icon="check" disabled={blocked} onClick={() => save(true)}>按 0 保存</Button></>}>
      <div className="modal-b"><p>以下工序的单件工时为 0，排产只计算换型工时，数量增加不会增加加工时长。</p><ul>{zero.map(row => <li key={row.ref}>工序 {row.sequence} · {row.label}</li>)}</ul></div></Modal></div>, document.body)}
  </section>;
}

export { ProcessHoursEditor };
export default ProcessHoursEditor;
