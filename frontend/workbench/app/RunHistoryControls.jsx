import React from './shared/runtime/react.js';
import A from './RunHistoryAPI.js';
import WorkbenchTerms from './WorkbenchTerms.js';
import ResourceControls, { Pager as SharedPager } from './ResourceControls.jsx';
import WorkbenchFormat from './WorkbenchFormat.js';
import RunGenerationContract from './RunGenerationContract.js';
import { WorkbenchReference, WorkbenchError } from './WorkbenchReferences.jsx';

function Button(props) { return <ResourceControls.Button {...props} className="btn wb-action" />; }
const timeLabel = v => WorkbenchFormat.dateTime(v);
const number = v => WorkbenchFormat.number(v, { digits: 0 });
function ErrorBox({ error }) {
  if (!error) return null;
  return <>{error.code === 'snapshot_stale' && <strong>数据已更新。</strong>}<WorkbenchError error={error} fallback="排产记录读取失败，请重新查询。" /></>;
}
function Filters({ value, busy, onApply }) {
  const [draft, setDraft] = React.useState(value), [error, setError] = React.useState(null);
  React.useEffect(() => { setDraft(value); setError(null); }, [value]);
  const set = patch => { setDraft(v => ({ ...v, ...patch })); setError(null); };
  function submit(e) {
    e.preventDefault();
    try {
      const q = { ...draft, page: 1 }; delete q.snapshot_ref;
      if (!q.accepted_from && !q.accepted_to) { delete q.accepted_from; delete q.accepted_to; }
      const next = A.scope(q); onApply(next); setError(null);
    } catch (failure) { setError(failure); }
  }
  return <form className="rh-filters" aria-label="排产记录筛选" onSubmit={submit} noValidate><div className="rh-filter-row">
    <label>排产状态<select aria-label="排产记录状态" value={draft.state} disabled={busy} onChange={e => set({ state: e.target.value })}>
      {[['all', '全部状态'], ...Object.entries(WorkbenchTerms.run_statuses)].map(([state, label]) => <option key={state} value={state}>{label}</option>)}</select></label>
    <label>提交起日<input type="date" aria-label="排产记录提交起日" value={draft.accepted_from || ''} disabled={busy} onChange={e => set({ accepted_from: e.target.value })} /></label>
    <label>提交止日<input type="date" aria-label="排产记录提交止日" value={draft.accepted_to || ''} disabled={busy} onChange={e => set({ accepted_to: e.target.value })} /></label>
    <label>排序<select aria-label="排产记录排序项" value={draft.sort} disabled={busy} onChange={e => set({ sort: e.target.value })}>
      <option value="accepted_at">提交时间</option><option value="started_at">开始时间</option><option value="finished_at">结束时间</option></select></label>
    <label>顺序<select aria-label="排产记录排序方向" value={draft.order} disabled={busy} onChange={e => set({ order: e.target.value })}>
      <option value="desc">从新到旧</option><option value="asc">从旧到新</option></select></label>
    <div className="rh-tools"><Button type="submit" icon="search" aria-label="查询排产记录" busy={busy}>查询</Button>
      <Button icon="x" aria-label="清除筛选" disabled={busy} onClick={() => { setError(null); onApply(A.scope({ size: value.size })); }} /></div>
  </div><ErrorBox error={error} /></form>;
}
function Status({ run }) {
  const tone = run.recovery_required || ['partial', 'interrupted'].includes(run.state) ? 'rh-warning' : run.state === 'failed' ? 'rh-danger' : run.state === 'complete' ? 'rh-success' : '';
  return <div><strong className={'rh-state ' + tone}>{run.recovery_required ? '等待核对' : WorkbenchTerms.run_status(run.state)}</strong>
    <small>{run.recovery_required ? run.recovery_reason.message : { queued: '尚未开始计算', running: '排产尚未结束', complete: '计算结束，约束未核验',
      partial: '保留部分结果，须查看候选', failed: '未保存可用候选', interrupted: '排产中断，未自动重跑' }[run.state]}</small>
    {run.recovery_required && <small>原状态：{WorkbenchTerms.run_status(run.state)}</small>}{run.error && <small className="rh-danger">{run.error.message}</small>}</div>;
}
function ScopeSummary({ value }) {
  const options = value.run_options;
  return <div><span>{value.start_date} 至 {value.end_date}</span>
    <small>物料齐套规则：{WorkbenchTerms.material_strategy(value.material_strategy, value.ready_check)}</small>
    <small>选批 {number(value.batch_count)} 批 · 齐套{value.ready_check ? '开启' : '关闭'}</small>
    <small>主目标：{RunGenerationContract.objectiveLabel(options.primary_objective)}</small>
    <small>同时探索：{options.target_objectives.map(RunGenerationContract.objectiveLabel).join(' · ')}</small>
    <small>总计算预算：{number(options.time_budget_seconds)} 秒 · {WorkbenchTerms.condition_value('algo_mode', options.algo_mode)}</small>
    <details><summary>排产设置</summary><small>缺资源：{WorkbenchTerms.missing_resource_policies[value.missing_resource_policy]} · {WorkbenchTerms.completed_policies[value.completed_policy]}</small>
      <small data-hold-window>不重排时段：{WorkbenchTerms.hold_window(value.hold_window)}</small>
      <small>图分析：{WorkbenchTerms.condition_value('graph_analysis_mode', options.graph_analysis_mode)}</small></details></div>;
}
function Table({ runs, onOpen }) {
  return <div className="rh-table wb-table-frame" data-sticky-head data-sticky-actions tabIndex={0} aria-label="排产记录表格滚动区域"><table className="wb-table" aria-label="排产记录"><caption className="wb-visually-hidden">排产记录</caption>
    <colgroup>{['submitted', 'state', 'scope', 'times', 'candidates', 'tasks', 'actions'].map(key => <col key={key} className={'rh-col-' + key} />)}</colgroup>
    <thead><tr><th scope="col" className="wb-col-key">提交时间</th><th scope="col">排产状态</th><th scope="col">排产范围</th><th scope="col">开始 / 结束时间</th><th scope="col" className="rh-num">候选数</th><th scope="col" className="rh-num">安排数</th><th scope="col" className="wb-col-actions">操作</th></tr></thead>
    <tbody>{runs.map(run => <tr key={run.run_ref} data-run-ref={run.run_ref} data-run-state={run.state}>
      <td className="wb-col-key"><time>{timeLabel(run.accepted_at)}</time><WorkbenchReference value={run.run_ref} label="记录编号" /></td><td><Status run={run} /></td>
      <td><ScopeSummary value={run.scope_summary} /></td><td><time>{run.started_at === null ? '尚未开始' : timeLabel(run.started_at)}</time>
        <small>{run.finished_at === null ? '尚未结束' : timeLabel(run.finished_at)}</small></td>
      <td className={'rh-num' + (run.counts_final && run.candidate_count > 0 ? ' rh-accent' : '')}>{number(run.candidate_count)}{!run.counts_final && <small>非最终</small>}</td>
      <td className="rh-num">{number(run.task_count)}{!run.counts_final && <small>非最终</small>}</td>
      <td className="wb-col-actions"><Button icon="arrow-right" aria-label={'查看 ' + timeLabel(run.accepted_at) + ' 提交的排产记录'} onClick={() => onOpen(run)} /></td>
    </tr>)}</tbody></table></div>;
}
function Pager({ page, busy, onChange }) {
  return <div className="rh-pagination"><SharedPager page={page} sizes={[10, 20, 50]} unit="次" label="排产记录" sizeLabel="排产记录每页数量" busy={busy}
    onSize={size => onChange({ page: 1, size }, false)} onPage={number => onChange({ page: number }, true)} /></div>;
}
const RunHistoryControls = { Button, ErrorBox, Filters, Table, Pager };
export { RunHistoryControls, Button, ErrorBox, Filters, Table, Pager };
export default RunHistoryControls;
