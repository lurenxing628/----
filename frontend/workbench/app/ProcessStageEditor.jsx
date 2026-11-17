import React from './shared/runtime/react.js';
import C from './resource-contract.js';
import P from './ProcessContract.js';
import APSProcessAPI from './ProcessAPI.js';
import { Button, ErrorBox, FieldCell, Issues, Search as ControlSearch } from './ResourceControls.jsx';
import WorkbenchFormat from './WorkbenchFormat.js';
import { Pager as ResourceTablePager } from './ResourceTables.jsx';
import { WorkbenchReference } from './WorkbenchReferences.jsx';
import WorkbenchTerms from './WorkbenchTerms.js';
import { failure, ref48 } from './shared/contract/kit.js';

const active = entity => entity.operations.filter(row => row.status === 'active');
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const value = item => item === null || item === undefined ? '未填写' : String(item);
function confirmationTime(text) {
  if (!text) return '未填写';
  return /(?:Z|[+-]\d\d:\d\d)$/.test(text) ? WorkbenchFormat.instant(text, { seconds: true })
    : WorkbenchFormat.dateTime(text, { seconds: true });
}
function Confirmation({ record }) {
  return <span className="process-confirmation">{record && record.state === 'confirmed' ? <>已确认{record.confirmed_at && <time dateTime={record.confirmed_at} title={record.confirmed_at}>{confirmationTime(record.confirmed_at)}</time>}{record.confirmed_by && <> · {record.confirmed_by}</>}</> : '未人工确认'}</span>;
}
function location(stage, operationRef, groupRef) {
  if (stage != null && !['route', 'source', 'hours'].includes(stage) || operationRef != null && !ref48(operationRef) || groupRef != null && !ref48(groupRef))
    throw failure('所选阶段或工序已失效，请重新选择。');
  return { stage: stage || null, operationRef: operationRef || null, groupRef: groupRef || null };
}
function locate(entity, target) {
  const operation = target.operationRef && entity.operations.find(row => row.ref === target.operationRef);
  const group = target.groupRef && entity.external_groups.find(row => row.ref === target.groupRef);
  if (target.operationRef && (!operation || operation.status !== 'active')) throw failure('目标工序已删除、停用或不属于此零件，未按序号或同名替代。');
  if (target.groupRef && !group) throw failure('目标外协组已删除或不属于此零件，未按工序范围替代。');
  if (operation && group && operation.external_group_ref !== group.ref) throw failure('要定位的工序不属于指定外协组，不能混用两种定位。');
  return target;
}
function useFocus(root, ref, page) {
  React.useEffect(() => {
    if (!ref || !root.current) return undefined;
    const frame = requestAnimationFrame(() => {
      const row = root.current && Array.from(root.current.querySelectorAll('[data-process-location]')).find(node => node.dataset.processLocation === ref);
      if (row) { row.focus({ preventScroll: true }); row.scrollIntoView({ block: 'center', inline: 'nearest' }); }
    });
    return () => cancelAnimationFrame(frame);
  }, [root, ref, page]);
}
function usePage(rows, focusRef = null) {
  const [query, setQuery] = React.useState(''), [number, setNumber] = React.useState(1), [size, setSize] = React.useState(50);
  React.useEffect(() => {
    if (!focusRef) return;
    const index = rows.findIndex(row => row.ref === focusRef);
    if (index >= 0) { setQuery(''); setNumber(Math.floor(index / size) + 1); }
  }, [rows, focusRef, size]);
  const filtered = React.useMemo(() => {
    const needle = query.toLowerCase();
    return !needle ? rows : rows.filter(row => [row.sequence, row.label, row.op_type_label].some(item => String(item ?? '').toLowerCase().includes(needle)));
  }, [rows, query]);
  const pages = Math.max(1, Math.ceil(filtered.length / size)), page = Math.min(number, pages);
  return { query, setQuery: text => { setQuery(text); setNumber(1); }, setNumber, setSize: next => { setSize(next); setNumber(1); }, rows: filtered.slice((page - 1) * size, page * size),
    page: { number: page, size, total: filtered.length, pages, sort: [] } };
}
function Pager({ paging, disabled }) {
  return paging.page.total > 50 || paging.page.pages > 1 ? <ResourceTablePager page={paging.page} disabled={disabled} onPage={paging.setNumber} onSize={paging.setSize} /> : null;
}
function Search({ paging, disabled }) {
  return <ControlSearch aria-label="搜索工序、工种" placeholder="搜索工序、工种…" value={paging.query} disabled={disabled} onChange={event => paging.setQuery(event.target.value)} />;
}
// error 只在工时页传入：已有合并组的统一周期报 groups.<外协组编号>.total_days，标在这一组的输入框上。
function Groups({ rows, affected = [], discarded = [], onDiscard, totals, onTotal, disabled, title = '外协组原记录', empty = '尚无外协组记录。', focusRef = null, error = null }) {
  const selected = new Set(discarded), changed = new Set(affected);
  const paging = usePage(rows, focusRef), root = React.useRef(null);
  useFocus(root, focusRef, paging.page.number);
  return <section ref={root}><h3>{title}</h3>{!rows.length ? <p className="muted">{empty}</p> : <>
    <div className="wb-table-frame wb-table-shell" data-sticky-head><table className={'tbl wb-table' + (onTotal || onDiscard ? ' wb-table--editable' : '')} aria-label={title} style={{ minWidth: 850, tableLayout: 'fixed' }}><caption className="wb-visually-hidden">{title}</caption>
      <thead><tr><th scope="col">工序范围</th><th scope="col">周期算法</th><th scope="col">总周期（天）</th><th scope="col">供应商</th><th scope="col">备注 / 问题</th>{onDiscard && <th scope="col">解除原组</th>}</tr></thead>
      <tbody>{paging.rows.map(row => <tr key={row.ref} data-process-location={row.ref} tabIndex={row.ref === focusRef ? -1 : undefined} aria-current={row.ref === focusRef ? 'true' : undefined}>
        <td>{row.start_sequence} 至 {row.end_sequence}{row.ref === focusRef && <WorkbenchReference value={row.ref} />}</td><td>{WorkbenchTerms.merge_modes[row.merge_mode] || (row.merge_mode === null ? '未填写' : '其他周期规则')}</td>
        <td>{onTotal && row.merge_mode === 'merged' && C.own(totals, row.ref) ? <FieldCell path={'groups.' + row.ref + '.total_days'} error={error}><input className="wt-in" type="number" step="any" min="0" aria-label={'外协组 ' + row.start_sequence + ' 至 ' + row.end_sequence + ' 总周期'} value={totals[row.ref]} disabled={disabled} onChange={event => onTotal(row.ref, event.target.value)} style={{ width: '100%' }} /></FieldCell> : P.valueText(row.total_days)}</td>
        <td>{value(row.supplier_label)}</td><td style={{ whiteSpace: 'pre-wrap' }}>{value(row.remark)}<Issues issues={row.issues} /></td>
        {onDiscard && <td>{changed.has(row.ref) ? <label><input type="checkbox" aria-label={'解除外协组 ' + row.start_sequence + ' 至 ' + row.end_sequence} checked={selected.has(row.ref)} disabled={disabled}
          onChange={event => onDiscard(event.target.checked ? discarded.concat(row.ref) : discarded.filter(ref => ref !== row.ref))} />明确解除</label> : '保持原组'}</td>}</tr>)}</tbody>
    </table></div><Pager paging={paging} disabled={disabled} /></> }</section>;
}
function changes(before, after) {
  const result = [], old = new Map(before.operations.map(row => [row.ref, row]));
  const oldGroups = new Map(before.external_groups.map(row => [row.ref, row])), newGroups = new Map(after.external_groups.map(row => [row.ref, row]));
  const range = group => group ? value(group.start_sequence) + ' 至 ' + value(group.end_sequence) : '范围未填写';
  const stage = item => P.stageLabel(item);
  const cycleMode = item => WorkbenchTerms.merge_modes[item] || (item === null ? '未设置' : '原周期算法未明确');
  function field(label, previous, current, format = value) {
    if (previous !== current) result.push({ label, previous: format(previous), current: format(current) });
  }
  function relation(label, previousRef, currentRef, previousLabel, currentLabel) {
    if (previousRef === currentRef && previousLabel === currentLabel) return;
    const previous = previousRef ? previousLabel || '名称未填写' : '未选';
    let current = currentRef ? currentLabel || '名称未填写' : '未选';
    if (previousRef && currentRef && previousRef !== currentRef && previous === current) current += '（关联记录已更换）';
    result.push({ label, previous, current });
  }
  function confirmation(label, previous, current, key) {
    field(label + '状态', previous.state, current.state, item => P.workflowStateLabel(key, item));
    field(label + '时间', previous.confirmed_at, current.confirmed_at, confirmationTime);
    if (previous.confirmed_by !== current.confirmed_by) result.push({ label: label + '记录', previous: '原确认记录', current: '确认记录已更新' });
  }
  after.operations.forEach(row => {
    const previous = old.get(row.ref); old.delete(row.ref);
    if (!previous) result.push({ label: '工序 ' + row.sequence, previous: '不存在', current: '新增记录' });
    else {
      const prefix = '工序 ' + row.sequence + ' · ';
      [['sequence', '序号'], ['label', '工序名称'], ['setup_hours', '换型工时（小时）'], ['unit_hours', '单件工时（小时）'], ['external_days', '外协周期（天）']].forEach(([key, label]) => field(prefix + label, previous[key], row[key]));
      field(prefix + '归属', previous.source, row.source, P.sourceLabel);
      field(prefix + '状态', previous.status, row.status, item => ({ active: '有效', deleted: '已停用' })[item] || '原状态未明确');
      relation(prefix + '工种', previous.op_type_ref, row.op_type_ref, previous.op_type_label, row.op_type_label);
      relation(prefix + '供应商', previous.supplier_ref, row.supplier_ref, previous.supplier_label, row.supplier_label);
      relation(prefix + '外协组', previous.external_group_ref, row.external_group_ref, range(oldGroups.get(previous.external_group_ref)), range(newGroups.get(row.external_group_ref)));
      confirmation(prefix + '归属确认', previous.confirmation.source, row.confirmation.source, 'source');
      confirmation(prefix + '工时确认', previous.confirmation.hours, row.confirmation.hours, 'hours');
    }
  });
  old.forEach(row => result.push({ label: '工序 ' + row.sequence, previous: row.label, current: '已移除' }));
  new Set([...oldGroups.keys(), ...newGroups.keys()]).forEach(ref => {
    const previous = oldGroups.get(ref), current = newGroups.get(ref), prefix = '外协组 ' + range(current || previous) + ' · ';
    if (!previous || !current) result.push({ label: prefix + '记录', previous: previous ? '原有外协组' : '无原记录', current: current ? '新增外协组' : '已移除' });
    [['工序范围', range], ['周期算法', row => cycleMode(row.merge_mode)], ['总周期（天）', row => value(row.total_days)], ['备注', row => value(row.remark)]].forEach(([label, format]) => {
      field(prefix + label, previous ? format(previous) : '无原记录', current ? format(current) : '已移除');
    });
    relation(prefix + '供应商', previous && previous.supplier_ref, current && current.supplier_ref, previous && previous.supplier_label, current && current.supplier_label);
  });
  field('当前阶段', before.workflow.stage, after.workflow.stage, stage);
  field('工艺就绪状态', before.workflow.ready, after.workflow.ready, ready => ready ? '已就绪' : '未就绪');
  field('工艺记录来源', before.workflow.origin, after.workflow.origin, origin => ({ legacy: '原有工艺记录', managed: '三阶段工艺记录' })[origin] || '来源未明确');
  ['route', 'source', 'hours'].forEach(key => confirmation(stage(key) + ' · 确认', before.workflow[key], after.workflow[key], key));
  return result;
}
function Review({ before, after, onAccept, disabled }) {
  const rows = React.useMemo(() => changes(before, after), [before, after]), paging = usePage(rows);
  return <section className="match-note is-block" role="status">
    <p>最新资料已读取，草稿没有被替换。差异 {rows.length} 项，请核对下表和当前草稿。点「{WorkbenchTerms.accept_latest}」后：已改过且仍适用的项保留，其余按最新值；有变化的工序要重新确认，已移除的工序不再提交。</p>
    {!!rows.length && <><div className="card-scroll"><table className="tbl wb-table" aria-label="最新资料差异" style={{ tableLayout: 'fixed', width: '100%' }}><caption className="wb-visually-hidden">{'最新资料差异'}</caption><thead><tr><th scope="col">项目</th><th scope="col">编辑前资料</th><th scope="col">最新资料</th></tr></thead>
      <tbody>{paging.rows.map((row, index) => <tr key={index}><td>{row.label}</td><td style={{ overflowWrap: 'anywhere' }}>{row.previous}</td><td style={{ overflowWrap: 'anywhere' }}>{row.current}</td></tr>)}</tbody></table></div><Pager paging={paging} disabled={disabled} /></>}
    <Button icon="check" disabled={disabled} onClick={onAccept}>{WorkbenchTerms.accept_latest}</Button>
  </section>;
}
function useDraft({ result, stage, build, reconcile, saved, onDirty }) {
  const [base, setBase] = React.useState(result), [draft, setDraft] = React.useState(() => build(result.data));
  const [review, setReview] = React.useState(null), [error, setError] = React.useState(null), [busy, setBusy] = React.useState(false);
  const baseline = React.useMemo(() => build(base.data), [base.data]);
  const dirty = React.useMemo(() => !same(draft, baseline), [draft, baseline]);
  const seenSaved = React.useRef(saved), request = React.useRef(null);
  React.useEffect(() => () => { if (request.current) request.current.abort(); }, []);
  React.useEffect(() => { onDirty(stage, dirty); }, [dirty, stage, onDirty]);
  React.useLayoutEffect(() => {
    if (base === result) return;
    if (seenSaved.current !== saved || !dirty) { setBase(result); setDraft(build(result.data)); setReview(null); setError(null); }
    else setReview(result);
    seenSaved.current = saved;
  }, [result, saved]);
  function edit(next) { setDraft(next); setError(null); }
  async function reload() {
    if (busy) return;
    const controller = new AbortController(); request.current = controller; setBusy(true); setError(null);
    try { const fresh = P.detail(await APSProcessAPI.detail('part', base.data.ref, controller.signal), base.data.ref); if (!controller.signal.aborted) setReview(fresh); }
    catch (failure) { if (!controller.signal.aborted) setError(failure); }
    finally { if (!controller.signal.aborted) setBusy(false); if (request.current === controller) request.current = null; }
  }
  function accept() {
    setDraft(reconcile(draft, base.data, review.data)); setBase(review); setReview(null); setError(null);
  }
  return { base, draft, edit, dirty, review, error, setError, busy, reload, accept };
}
// 出错工序所在的页：字段路径 operations.<工序编号>.<项> 只认本页负责的项（keys），按工序在未筛选列表里的位置和当前每页条数换算，
// 取第一道出错的工序。归属、工时页共用同一份命令，别页的被拒不会在这里定位。
function errorPage(error, operations, size, keys) {
  const paths = new Set(C.fieldErrors(error).map(row => row.path));
  const index = operations.findIndex(row => keys.some(key => paths.has('operations.' + row.ref + '.' + key)));
  return index < 0 ? null : Math.floor(index / size) + 1;
}
// 总错误框只显示本页检查的错误，命令错误由详情页统一显示；分页的工序表另传 paging 与 errorPage 算出的 page。
function Feedback({ model, disabled, paging, page }) {
  return <><ErrorBox error={model.error} />
    {page && <Button icon="arrow-right" disabled={disabled} onClick={() => { paging.setQuery(''); paging.setNumber(page); }}>定位到第 {page} 页</Button>}
    <Button icon="refresh-cw" busy={model.busy} disabled={disabled} onClick={model.reload}>{WorkbenchTerms.refresh_latest}</Button>
    {model.review && <Review before={model.base.data} after={model.review.data} disabled={disabled || model.busy} onAccept={model.accept} />}</>;
}
function reason(model, stage) {
  const entity = model.base.data;
  return model.review ? '请先核对最新资料。' : model.busy ? '正在读取最新资料。' :
    (entity.workflow[stage === 'source' ? 'route' : 'source'].state !== 'confirmed' ? stage === 'source' ? '请先确认路线。' : '请先确认归属。' : '') ||
    (stage === 'source' ? model.base.meta.source !== 'production' ? '当前不是生产数据，不能保存。' : '' : C.blocked(entity.write_context, 'process', stage + '_confirm', model.base.meta.source));
}
const ProcessStageEditor = { active, same, value, Confirmation, usePage, Pager, Search, Groups, Review, useDraft, errorPage, Feedback, reason, location, locate, useFocus };

export {
  ProcessStageEditor,
  active,
  same,
  value,
  Confirmation,
  usePage,
  Pager,
  Search,
  Groups,
  Review,
  useDraft,
  errorPage,
  Feedback,
  reason,
  location,
  locate,
  useFocus
};
export default ProcessStageEditor;
