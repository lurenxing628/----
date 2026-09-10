(function () {
  'use strict';
  const { Button } = window.FieldControls;
  function FieldFilters({ scope, onChange, disabled, summary }) {
    const [draft, setDraft] = React.useState(scope);
    const counts = summary && summary.state_counts;
    React.useEffect(() => setDraft(scope), [scope]);
    return <><form className="field-filters" onSubmit={event => { event.preventDefault(); if (!disabled) onChange(draft); }}>
      <label>搜索批次或工序<input type="search" aria-label="搜索批次或工序" value={draft.query || ''} disabled={disabled} onChange={event => setDraft({ ...draft, query: event.target.value })} /></label>
      <label>计划完工起日<input type="date" aria-label="计划完工起日" value={draft.plan_finish_date_from || ''} disabled={disabled} onChange={event => setDraft({ ...draft, plan_finish_date_from: event.target.value })} /></label>
      <label>计划完工止日<input type="date" aria-label="计划完工止日" value={draft.plan_finish_date_to || ''} disabled={disabled} onChange={event => setDraft({ ...draft, plan_finish_date_to: event.target.value })} /></label>
      <Button type="submit" icon="search" aria-label="查询现场记录" disabled={disabled} /><Button icon="x" aria-label="清除现场筛选" disabled={disabled} onClick={() => onChange({ plan_ref: scope.plan_ref })} />
      <div className="field-states" role="group" aria-label="报工状态">{[['all', '全部'], ...Object.entries(window.FieldContract.states)].map(([state, label]) => <button key={state} type="button" aria-label={label} disabled={disabled} aria-pressed={(scope.state || 'all') === state} onClick={() => onChange({ ...scope, state })}>{label}{counts && <span data-field-state-count={state}> {state === 'all' ? summary.state_scope_tasks : counts[state]}</span>}</button>)}</div>
    </form>{(scope.range_start || scope.batch_ids || scope.resource_ref) && <div className="field-filters field-note">
      {scope.range_start && <span>计划重叠范围：{window.FieldContract.date(scope.range_start)} 至 {window.FieldContract.date(scope.range_end)}</span>}
      {scope.batch_ids && <span>指定批次：{scope.batch_ids.length} 个</span>}{scope.resource_ref && <span>已限定{scope.resource_type === 'machine' ? '设备' : '人员'}关联工序</span>}</div>}
      {summary && <div className="field-metrics">{[['unreported', '待报工'], ['started', '已登记开工'], ['partial', '部分完成'], ['complete', '已完工']].map(([key, label]) => <span key={key}>{label}<b>{counts ? counts[key] : '未读取'}</b></span>)}
        <span>累计实报工时<b>{summary.effective_processing_hours === null || summary.effective_processing_hours === undefined ? '未知' : Math.round(summary.effective_processing_hours * 1000) / 1000 + ' h'}</b>
          {summary.unknown_hour_reports > 0 && <small>已知小计 {summary.known_effective_processing_hours} h · {summary.unknown_hour_reports} 条待补</small>}</span></div>}</>;
  }
  window.FieldFilters = FieldFilters;
})();
