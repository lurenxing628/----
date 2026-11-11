import React from './shared/runtime/react.js';
import TrialAPI from './TrialAPI.js';
import TrialContract from './TrialContract.js';
import TrialControls from './TrialControls.jsx';
import TrialSession from './TrialSession.js';
import WorkbenchTerms from './WorkbenchTerms.js';
import WorkbenchGuards from './WorkbenchGuards.js';
import { WorkbenchReference } from './WorkbenchReferences.jsx';

const A = TrialAPI, C = TrialContract, U = TrialControls, S = TrialSession;
function Directory({ revision, onOpen, filterBase, fixedBase }) {
  const [collection, setCollection] = React.useState('drafts'), [query, setQuery] = React.useState({ revision, page: 1, size: 20, status: 'all' });
  const [onlyBase, setOnlyBase] = React.useState(false), [reload, refresh] = React.useReducer(n => n + 1, 0);
  const activeQuery = query.revision === revision ? query : { revision, page: 1, size: query.size, status: query.status };
  const { revision: _, ...cleanQuery } = activeQuery;
  const selectedBase = fixedBase || (onlyBase ? filterBase : null);
  const q = { ...cleanQuery, ...(selectedBase ? { base_kind: Object.keys(selectedBase)[0], base_ref: Object.values(selectedBase)[0] } : {}) };
  const read = S.useRead(signal => A.read('/trial/' + collection, q, signal, v => { C.catalog(v, collection, q); return v; }), [collection, JSON.stringify(q), revision, reload]);
  const data = read.result && read.result.data;
  function reset(patch = {}) { setQuery({ revision, page: 1, size: activeQuery.size, status: activeQuery.status, ...patch }); refresh(); }
  return <section aria-label="试调草稿与试调方案" className="tt-directory"><div className="tt-heading"><U.Tabs value={collection} label="试调列表类别"
    options={[["drafts", '试调草稿'], ['scenarios', '试调方案']]} onChange={value => { setCollection(value); reset({ status: 'all' }); }} />
    <div className="tt-tools"><label>状态 <select aria-label="列表状态" value={activeQuery.status} onChange={e => reset({ status: e.target.value })}>
      {(collection === 'drafts' ? ['all', 'editing', 'saved', 'discarded'] : ['all', 'saved']).map(s => <option key={s} value={s}>{s === 'all' ? '全部' : U.statusLabel(s)}</option>)}</select></label>
      <label>每页 <select aria-label="列表每页数量" value={activeQuery.size} onChange={e => reset({ size: Number(e.target.value) })}>{[10, 20, 50].map(n => <option key={n}>{n}</option>)}</select></label>
      {filterBase && <label className="tt-check"><input type="checkbox" checked={!!fixedBase || onlyBase} disabled={!!fixedBase} onChange={e => { setOnlyBase(e.target.checked); reset(); }} />仅此原来源</label>}
      <U.Button icon="refresh-cw" aria-label="刷新试调列表" busy={read.busy} onClick={() => reset()} /></div></div>
    <U.ErrorBox error={read.error} />{read.busy && <p role="status">正在读取列表…</p>}
    <div className="tt-directory-scroll"><table className="tt-table" aria-label="试调列表"><caption className="wb-visually-hidden">{"试调列表"}</caption><thead><tr><th scope="col">名称</th><th scope="col">原来源</th><th scope="col">状态</th><th scope="col">安排</th><th scope="col">更新时间</th><th scope="col">记录人</th><th scope="col">操作</th></tr></thead>
      <tbody>{data && data.items.map(r => <tr key={r.detail_target} data-trial-ref={r.open_target.draft_ref || r.open_target.scenario_ref}><td>{r.display_name}</td><td>{r.base_display_name}</td><td>{U.statusLabel(r.status)}</td>
        <td>{r.task_count}</td><td>{U.timeLabel(r.updated_at)}</td><td>{r.local_operator}</td><td><U.Button icon="arrow-right" onClick={() => onOpen(r.open_target)}>打开</U.Button></td></tr>)}</tbody></table>
      {data && !data.items.length && <div className="tt-empty">此范围暂无{collection === 'drafts' ? '试调草稿' : '试调方案'}</div>}</div>
    <U.Pager page={data ? data.page : { number: activeQuery.page, size: activeQuery.size }} label="列表" busy={read.busy || !read.result} onPage={page => setQuery({ ...activeQuery, page, snapshot_ref: read.result ? read.result.meta.snapshot_ref : activeQuery.snapshot_ref })} />
  </section>;
}
function SourceCatalog({ onSelect, selected }) {
  const [kind, setKind] = React.useState(selected && selected.candidate_ref ? 'candidate' : 'plan'), [run, setRun] = React.useState(null), [q, setQ] = React.useState({}), [epoch, refresh] = React.useReducer(n => n + 1, 0);
  const path = kind === 'plan' ? '/plans' : run ? '/scheduling/runs/' + run.run_ref + '/candidates' : '/scheduling/runs';
  const query = kind === 'plan' ? { collection: 'history', size: 10, ...q } : { page: 1, size: 10, ...q };
  const read = S.useRead(async signal => {
    const v = await A.read(path, query, signal), d = v.data;
    if (kind === 'plan') {
      C.check(d.page && d.page.collection === 'history' && d.page.size === 10);
    } else {
      C.check(d.page && d.page.number === query.page && d.page.size === query.size && (!run || d.run_ref === run.run_ref));
    }
    return v;
  }, [path, JSON.stringify(query), epoch]);
  const d = read.result && read.result.data, rows = d ? kind === 'plan' ? d.plans.filter(p => p.kind === 'official') : run ? d.candidates : d.runs : [];
  return <><U.Tabs label="原来源类型" value={kind} options={[["plan", '原正式计划'], ['candidate', '排产候选']]}
    onChange={value => { setKind(value); setRun(null); setQ({}); }} />
    <div className="tt-heading"><span>{run ? '候选来源：' + U.timeLabel(run.accepted_at) : kind === 'plan' ? '正式计划列表' : '排产记录列表'}</span>
      <div className="tt-tools">{run && <U.Button icon="chevron-left" onClick={() => { setRun(null); setQ({}); }}>排产记录列表</U.Button>}
        <U.Button icon="refresh-cw" aria-label="刷新原来源列表" busy={read.busy} onClick={() => { setQ({}); refresh(); }} /></div></div>
    <U.ErrorBox error={read.error} />{read.busy && <p role="status">正在读取原来源…</p>}
    {d && <div className="tt-source-list">{rows.map(r => {
      const key = kind === 'plan' ? 'plan_ref' : run ? 'candidate_ref' : 'run_ref', id = r[key];
      const title = kind === 'plan' ? U.sourceLabel(r) : run ? r.label || WorkbenchTerms.name_missing : U.timeLabel(r.accepted_at) + ' · ' + U.runStatusLabel(r.state);
      const disabled = kind === 'plan' ? !r.capabilities.view : run ? !r.capabilities.view || !r.task_count : !r.candidate_count;
      return <div key={id || title} className="tt-source-row">{key === 'run_ref' ? <U.Button icon="arrow-right" disabled={disabled} onClick={() => { setRun(r); setQ({}); }}>{title}</U.Button> :
        <label><input type="radio" name="trial-base" disabled={disabled} checked={!!selected && selected[key] === id} onChange={() => onSelect({ [key]: id }, title)} />{title}</label>}
        <span className="tt-muted">{kind === 'plan' ? r.is_current_official ? WorkbenchTerms.current_official : WorkbenchTerms.historical_official : (r.task_count + ' 道安排')}{run && ' · ' + U.candidateStatusLabel(r.status)}</span></div>;
    })}{!rows.length && <p className="tt-empty">本页没有可选来源</p>}</div>}
    {kind === 'plan' ? <div className="tt-tools"><U.Button icon="chevron-left" disabled={read.busy || !q.cursor} onClick={() => setQ({})}>第一页</U.Button>
      <U.Button icon="chevron-right" disabled={read.busy || !d || !d.page.has_more} onClick={() => setQ({ cursor: d.page.next_cursor, snapshot_ref: read.result.meta.snapshot_ref })}>下一页</U.Button></div> :
      <U.Pager label="来源" page={d ? d.page : { number: query.page, size: query.size }} busy={read.busy || !d} onPage={page => setQ({ ...q, page, snapshot_ref: read.result ? read.result.meta.snapshot_ref : q.snapshot_ref })} />}
  </>;
}
function Create({ initialBase, initialScope = {}, commands, onClose, fixedBase = false, onExisting }) {
  const [base, setBase] = React.useState(initialBase || null), [label, setLabel] = React.useState(''), [epoch, refresh] = React.useReducer(n => n + 1, 0);
  const [choosing, setChoosing] = React.useState(!initialBase);
  // A source carried in from the plan or candidate page is checked at once so its name and version show instead of a placeholder.
  const [inspect, setInspect] = React.useState(!!initialBase), [agreed, setAgreed] = React.useState(false);
  const input = { base, scope: initialScope };
  const baseline = React.useRef(initialBase || null);
  const guardOwner = WorkbenchGuards.useDirtyGuard({ dirty: JSON.stringify(base) !== JSON.stringify(baseline.current),
    locked: commands.busy || !!commands.key, message: '新增试调的来源选择或确认还没提交。' });
  async function close(detail) {
    if (detail && detail.guardConfirmed === true && detail.guardOwner === guardOwner || await WorkbenchGuards.confirmLeave({ owner: guardOwner })) onClose();
  }
  const read = S.useRead(signal => A.preview(input, signal), [JSON.stringify(input), epoch], inspect && !!base);
  function select(value, title) { setBase(value); setLabel(title); setChoosing(false); setInspect(false); setAgreed(false); }
  const d = read.result && read.result.data;
  const sourceType = base && base.candidate_ref ? '排产候选' : '正式计划';
  const sourceName = d ? U.sourceLabel(d.base_identity) : label || (base ? '已带入' + sourceType + '，请核对来源' : '尚未选择');
  return <U.Modal title="从原来源新增试调" icon="square-pen" onClose={close} guardOwner={guardOwner} locked={commands.busy || !!commands.key}
    footer={<><U.Button icon="x" disabled={commands.busy || !!commands.key} onClick={close}>取消</U.Button>
      {onExisting && <U.Button icon="folder-open" disabled={commands.busy || !!commands.key} onClick={async () => { if (await WorkbenchGuards.confirmLeave({ owner: guardOwner })) onExisting(); }}>打开已有草稿</U.Button>}
      <U.Button icon="refresh-cw" disabled={!base || commands.busy} onClick={() => { commands.restore(); setInspect(true); setAgreed(false); refresh(); }}>核对原来源</U.Button>
      {commands.key && <U.Button icon="refresh-cw" busy={commands.busy} onClick={commands.lookup}>{WorkbenchTerms.actions.query_result}</U.Button>}
      <U.Button icon="plus" className="btn primary" reason={!d ? '请先核对原来源' : !agreed ? '请先勾选确认' : ''} disabled={commands.blocked} onClick={() => commands.execute({ action: 'create', input }, d.write_context.write_token)}>确认新增草稿</U.Button></>}>
    <div className="trial-modal-body">{!fixedBase && choosing && <SourceCatalog selected={base} onSelect={select} />}
      <section aria-label="已选择的试调来源"><div className="tt-heading"><strong>{base ? '来源类型：' + sourceType : '请选择试调来源'}</strong>
        {!fixedBase && base && !choosing && <U.Button icon="refresh-cw" disabled={commands.busy || !!commands.key} onClick={() => setChoosing(true)}>更换来源</U.Button>}</div>
        <p>已选择：{sourceName}</p>{base && <WorkbenchReference value={Object.values(base)[0]} />}</section>
      <U.ErrorBox error={read.error} /><U.ErrorBox error={commands.error} />
      {commands.key && <section className="tt-notice" aria-label="待确认的试调提交"><p>{commands.note || '上次提交结果尚未确认。'}</p><WorkbenchReference value={commands.key} /></section>}
      {read.busy && <p role="status">正在核对完整原来源…</p>}{d && <><p>将完整复制原方案的 {d.task_count} 道安排。</p>
        <U.Issues rows={d.validation.issues} /><label className="tt-check"><input type="checkbox" checked={agreed} onChange={e => setAgreed(e.target.checked)} />确认基于此来源新增独立草稿，正式计划保持不变</label></>}
    </div></U.Modal>;
}
const TrialCatalog = { Directory, Create };
export { TrialCatalog, Directory, Create };
export default TrialCatalog;
