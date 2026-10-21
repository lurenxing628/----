(function () {
  'use strict';
  const U = window.TrialControls, T = window.WorkbenchTerms;
  function DeliveryValue({ summary, metric }) {
    const value = summary[metric], subtotal = metric === 'overdue_count' ? summary.known_overdue_count : summary.known_tardiness_hours;
    return <>{summary.state === 'not_applicable' ? '不适用' : U.number(value)}{value === null && summary.state !== 'not_applicable' && <small>已知小计 {U.number(subtotal)} · 未知 {summary.unknown_due_count} 批</small>}</>;
  }
  function Finish({ row }) {
    const missing = T.missing_arrangements(row.ordinary_unscheduled_operation_count, row.deferred_operation_count);
    return <>{T.delivery_completion_states[row.completion_state]}{row.planned_finish && <div title={window.WorkbenchFormat.dateTime(row.planned_finish, { seconds: true, fractions: true })}>{U.timeLabel(row.planned_finish)}</div>}
      {row.partial_planned_finish && <div className="tt-muted">{T.arrangement_labels.partial_finish}：{U.timeLabel(row.partial_planned_finish)}</div>}
      {missing && <div className="tt-muted">{missing}</div>}</>;
  }
  function Summary({ data }) {
    const c = data.comparison;
    return <div className="tt-summary">{[['overdue_count', T.overdue_count], ['total_tardiness_hours', T.total_tardiness_hours + '（小时）']].map(([metric, label]) =>
      <div key={metric}><span>{label}</span><strong><DeliveryValue summary={c.delivery_summary} metric={metric} /></strong></div>)}{[[c.changed_operations, '调整工序'], [c.moved_operations, '换设备工序']].map(([value, label]) =>
      <div key={label}><span>{label}</span><strong>{U.number(value)}</strong></div>)}<div><span>{T.changeover_count}</span><strong>{c.changeovers === null ? '未知' : U.number(c.changeovers)}</strong>{c.changeovers === null && c.changeover_reason && <small>{c.changeover_reason}</small>}</div>
      {c.preparation_common && <div><span>新安排准备标准工时</span><strong><RequirementMetric value={c.preparation_common.after.scheduled_setup_hours} /></strong></div>}</div>;
  }
  function RequirementMetric({ value }) {
    return <>{value.state === 'not_applicable' ? '不适用' : U.number(value.value)}{value.value === null && <small>已知小计 {U.number(value.known_subtotal)} · 未知 {value.unknown_count} 道</small>}</>;
  }
  function Preparation({ data, name, onSelect }) {
    const c = data.comparison, p = c.preparation_common, changes = c.changeover_common;
    const tasksByOpRef = React.useMemo(() => new Map(data.tasks.map(row => [row.operation_ref, row])), [data.tasks]);
    const metrics = [['pending_setup_hours', '待执行准备标准工时'], ['scheduled_setup_hours', '新安排准备标准工时'],
      ['unplanned_setup_hours', '其他未安排准备标准工时'], ['deferred_setup_hours', '缺料未安排准备标准工时'],
      ['pending_processing_hours', '待执行加工标准工时'], ['scheduled_processing_hours', '新安排加工标准工时'],
      ['unplanned_processing_hours', '其他未安排加工标准工时'], ['deferred_processing_hours', '缺料未安排加工标准工时']];
    const summaryColumns = [
      ['标准需求（小时）', row => row[1]], ['原安排', row => <RequirementMetric value={p.before[row[0]]} />],
      ['当前试调', row => <RequirementMetric value={p.after[row[0]]} />], ['变化（小时）', row => <>{U.number(p.deltas[row[0]].value)}{p.deltas[row[0]].reason && <small>{p.deltas[row[0]].reason.message}</small>}</>]
    ];
    const primaryMetrics = p ? metrics.filter(([key]) => ['scheduled_setup_hours', 'unplanned_setup_hours'].includes(key)
      || key === 'deferred_setup_hours' && ['before', 'after'].some(side => p[side][key].total_count > 0)) : [];
    function operation(ref, label) {
      const task = tasksByOpRef.get(ref);
      return task ? <U.Button icon="arrow-right" onClick={() => onSelect(task.task_ref)}>{label}</U.Button> : <span>{label}</span>;
    }
    return <>
      {p ? <><U.Table label="准备需求汇总" rows={primaryMetrics} columns={summaryColumns} />
        <details><summary>全部工时汇总</summary><U.Table label="全部工时汇总" rows={metrics} columns={summaryColumns} /></details>
        <details><summary>保留安排与报工工序</summary><U.Table label="保留与报工工序的工时" rows={['retained', 'execution', 'completed']} columns={[
          ['工序类别', role => T.effort_roles[role]], ['原 / 当前工序数', role => U.number(p.role_totals.before[role].count) + ' / ' + U.number(p.role_totals.after[role].count)],
          ['当前准备（小时）', role => <RequirementMetric value={p.role_totals.after[role].setup_standard_hours} />],
          ['当前加工（小时）', role => <RequirementMetric value={p.role_totals.after[role].processing_standard_hours} />]]} /></details></>
        : <p className="tt-notice">原草稿的需求保存来源缺失，原标准与实际需求在任务明细中分别查看。</p>}
      <p className="tt-muted">工时单位为小时，箭头表示原安排 → 当前试调。</p>
      <U.Table label="工序准备需求" rows={data.tasks} columns={[
        ['批次 / 工序', task => <U.Button icon="arrow-right" onClick={() => onSelect(task.task_ref)}>{task.batch_id + ' · ' + task.process_label + ' ' + task.sequence}</U.Button>],
        ...[['setup_standard_hours', '准备工时'], ['processing_standard_hours', '加工工时'], ['required_standard_hours', '合计']].map(([key, label]) => [label, task => {
          const pair = task.operation_effort;
          if (!pair) return '需求未保存';
          const values = ['before', 'after'].map(side => pair[side].state === 'not_applicable' ? '外协按周期' : pair[side][key] === null ? '待确认' : U.number(pair[side][key]));
          return pair.before[key] === pair.after[key] && (pair.before.state === 'not_applicable') === (pair.after.state === 'not_applicable') ? values[1] : values.join(' → ');
        }]),
        ['安排状态', task => { const value = task.operation_effort && task.operation_effort.after; return value ? <>{T.preparation_allocations[value.allocation_state]}<div className="tt-muted">{T.setup_states[value.setup_state]}</div></> : '需求未保存'; }],
        ['查看', task => <details><summary>工时详情</summary><h4>原安排需求</h4><window.RunOperationEffort.Effort value={task.operation_effort && task.operation_effort.before} />
          <h4>当前试调需求</h4><window.RunOperationEffort.Effort value={task.operation_effort && task.operation_effort.after} /></details>]]} />
      <h4>{T.changeover_count}</h4>{changes ? <><U.Table label="工种切换汇总" rows={['before', 'after']} columns={[
        ['安排', side => side === 'before' ? '原安排' : '当前试调'], [T.changeover_count, side => <>{U.number(changes[side].count)}{changes[side].count === null && <small>已知 {U.number(changes[side].known_count)} 次 · 未知 {changes[side].unknown_count} 道</small>}</>],
        ['发生切换的设备', side => U.number(changes[side].changed_machine_count)], ['安排冲突', side => U.number(changes[side].conflict_count)]]} />
        {['before', 'after'].map(side => <section key={side}><h4>{side === 'before' ? '原安排' : '当前试调'}工种切换明细</h4><U.Issues rows={changes[side].issues} />
          <U.Table label={(side === 'before' ? '原安排' : '当前试调') + '工种切换'} rows={changes[side].events} columns={[
            ['设备', event => event.machine_label || name(event.machine_ref)], ['前工序', event => operation(event.previous_operation_ref, event.previous_type || '工种名称未保存')],
            ['后工序', event => operation(event.next_operation_ref, event.next_type || '工种名称未保存')], ['前序预计完工', event => U.timeLabel(event.previous_end)],
            ['后序预计开工', event => U.timeLabel(event.next_start)], ['重叠', event => event.overlap ? '有重叠' : '无重叠']]} /></section>)}</>
        : <p className="tt-notice">工种切换的原保存序列缺失。</p>}</>;
  }
  function Calendar({ resource }) {
    const w = resource.window_metrics, calendar = resource.calendar;
    return <details><summary>时段与计算详情</summary><div className="tt-subtable"><dl className="tt-facts">
      <dt>工序跨度累计（小时）</dt><dd>{U.number(resource.arranged_hours)}</dd><dt>保留跨度重叠（小时）</dt><dd>{U.number(resource.overlap_hours)}</dd>
      <dt>跨休息保留跨度（小时）</dt><dd>{U.number(resource.outside_available_hours)}</dd><dt>班内工序累计（小时）</dt><dd>{U.number(w.summed_load_hours)}</dd>
      <dt>班内重复计时（小时）</dt><dd>{U.number(w.overlap_hours)}</dd><dt>班内工序累计 / 可排时间</dt><dd>{U.percent(w.demand_ratio)}</dd>
      <dt>资料状态</dt><dd>{T.resource_states[w.state]}{w.unknown_days > 0 && ' · ' + w.unknown_days + ' 天班表未记录'}</dd>
    </dl><p className="tt-muted">预留跨度包含休息和夜间等待；班内重复计时按同时多占的份数累计。</p>
      <U.Table label="占用时段" rows={resource.segments} size={10}
      columns={[["开始", r => U.timeLabel(r.start)], ['结束', r => U.timeLabel(r.end)], ['同时安排工序', r => r.concurrent_operations]]} />
      <h4>可排时段</h4>{calendar.windows === null ? <p>班表暂不可用</p> : <U.Table label="可排时段" rows={calendar.windows} size={10}
        columns={[["开始", r => U.timeLabel(r.start)], ['结束', r => U.timeLabel(r.end)], ['效率', r => U.number(r.efficiency)], ['普通 / 急件', r => (r.allow_normal ? '允许' : '不允许') + ' / ' + (r.allow_urgent ? '允许' : '不允许')]]} />}
      <details><summary>折算标准工时</summary><dl className="tt-facts"><dt>普通件（小时）</dt><dd>{U.number(calendar.normal_effective_hours)}</dd><dt>急件（小时）</dt><dd>{U.number(calendar.urgent_effective_hours)}</dd></dl><p>各自按允许时段乘效率计算。同一时段可能同时允许普通件和急件，两项分别查看。</p></details>
      <U.Issues rows={calendar.issues} /><U.Issues rows={w.issues} />{calendar.downtime_windows && calendar.downtime_windows.length > 0 && <><h4>停机时段</h4><U.Table label="停机时段" rows={calendar.downtime_windows}
        columns={[["开始", r => U.timeLabel(r.start)], ['结束', r => U.timeLabel(r.end)]]} /></>}</div></details>;
  }
  function Results({ data, onSelect }) {
    const H = window.TrialAdoptionHistoryState, V = window.TrialViewState, preferences = V.useView(data);
    function readEntry() {
      try {
        const saved = history.state && history.state.trialAdoptionHistory;
        if (!data.scenario_ref || !saved || saved.scenario_ref !== data.scenario_ref) return { tab: null, error: null };
        return { tab: H.restore(data.scenario_ref).tab, error: null };
      } catch (_) { return { tab: null, error: new Error('试调页签记录无法恢复，请刷新或清除本页页签记录。') }; }
    }
    const [entry, setEntry] = React.useState(readEntry), c = data.comparison;
    const name = React.useMemo(() => window.TrialGantt.resourceNames(data), [data.resources]);
    // When the local preference cannot be read, the result still renders with defaults and the tab choice stays on this page.
    const [local, setLocal] = React.useState(null), values = preferences.value || local || V.defaults(data);
    const tab = entry.tab || values.result_tab;
    function clearEntry() {
      try {
        const current = history.state, saved = current && current.trialAdoptionHistory;
        if (saved && saved.scenario_ref === data.scenario_ref) {
          const next = { ...current }; delete next.trialAdoptionHistory; history.replaceState(next, '', location.href);
        }
        setEntry({ tab: null, error: null });
      } catch (_) { setEntry({ ...entry, error: new Error('本页试调页签记录清除失败，请重试。') }); }
    }
    function selectTab(next) {
      if (!preferences.change({ result_tab: next })) setLocal({ ...values, result_tab: next });
      try { H.remember(data.scenario_ref, { tab: next }); setEntry({ tab: next, error: null }); }
      catch (_) { setEntry({ tab: next, error: new Error('本页试调页签记录保存失败，返回后可能无法恢复。') }); }
    }
    const arrangement = r => <>{name(r.machine_ref)}<br />{name(r.operator_ref)}<br />{U.timeLabel(r.start)}<br />{U.timeLabel(r.end)}</>;
    return <section className="tt-results"><V.Notice state={preferences} label="试调结果查看偏好" />
      {entry.error && <div className="tt-notice" role="region" aria-label="试调页签记录恢复"><U.ErrorBox error={entry.error} /><div className="tt-tools">
        <U.Button icon="refresh-cw" onClick={() => setEntry(readEntry())}>刷新本页页签记录</U.Button>
        <U.Button icon="rotate-ccw" onClick={clearEntry}>清除本页页签记录</U.Button></div></div>}
      <U.Tabs value={tab} onChange={selectTab} label="试调结果" idPrefix="tt-result-tab-" panelId="tt-result-panel" options={[
      ['delivery', '批次对比'], ['capacity', '资源占用'], ['preparation', '准备与切换'], ['history', '调整记录'], ['adoptions', '采用记录'], ['issues', '约束问题'], ['tasks', '全部安排'], ['unplanned', '未安排工序']]} />
      <div role="tabpanel" id="tt-result-panel" aria-labelledby={'tt-result-tab-' + tab}>
        {tab === 'adoptions' && <window.TrialAdoptionHistory data={data} />}
        {tab === 'preparation' && <Preparation data={data} name={name} onSelect={onSelect} />}
        {tab === 'delivery' && <><details><summary>交期数据范围</summary><p>原安排：{T.delivery_coverage(c.before_delivery_summary)}</p><p>当前试调：{T.delivery_coverage(c.delivery_summary)}</p></details>
          <U.Table rows={c.batches} label="批次交付对比" columns={[
            ['批次 / 零件', r => <>{r.batch_id}<br />{r.part_name}</>], ['批次数量', r => U.number(r.quantity)], ['交期', r => <span title={r.due_state === 'specified' ? '交期截至当日结束，次日零点起计为超期。' : undefined}>{T.due_date(r.due_date, r.due_state, r.due_issue)}</span>],
            ['原工序安排 / 预计完工', r => <Finish row={r.before} />], ['试调工序安排 / 预计完工', r => <Finish row={r.after} />], ['提前（小时）', r => U.number(r.improvement_hours)],
            ['预计交付', r => T.delivery_risks[r.risk]], ['超期（小时）', r => r.due_state === 'unspecified' ? '不适用' : U.number(r.late_hours)]]} /></>}
        {tab === 'capacity' && <><details><summary>资源统计范围与班表来源</summary><p>创建草稿时保存的班表，包含原安排和当前试调涉及的设备、人员。</p>
          <p>资源统计从 {window.WorkbenchFormat.dateTime(data.capacity.start, { seconds: true, fractions: true })} 至 {window.WorkbenchFormat.dateTime(data.capacity.end, { seconds: true, fractions: true })}，结束时刻不计入。</p></details>
          {data.capacity.reason && <p className="tt-notice">{data.capacity.reason}</p>}<U.Table label="资源占用" rows={data.capacity.resources} columns={[
            ['资源', r => T.resource_kinds[r.resource_type] + ' ' + name(r.resource_ref)], ['可排（小时）', r => U.number(r.window_metrics.available_hours)], ['班内已占（小时）', r => U.number(r.window_metrics.occupied_hours)],
            ['占用比例', r => U.percent(r.window_metrics.utilization_ratio)], ['班内重叠（小时）', r => U.number(r.window_metrics.overlap_hours)], ['详情', r => <Calendar resource={r} />]]} /></>}
        {tab === 'history' && <><U.Table label="调整记录" rows={data.change_history.slice().reverse()} columns={[
          ['记录时间', r => U.timeLabel(r.recorded_at)], ['记录人', r => r.local_operator], ['调整前', r => arrangement(r.before)], ['调整后', r => arrangement(r.after)],
          ['当时约束', r => U.statusLabel(r.validation.constraints_status)], ['记录依据', r => <details><summary>编号</summary><div className="tt-ref">{r.change_ref}</div><div className="tt-ref">{r.task_ref}</div></details>]]} /></>}
        {tab === 'issues' && <><p>约束检查：{U.statusLabel(data.validation.constraints_status)}</p><U.Issues rows={data.validation.issues} onSelect={onSelect} /></>}
        {tab === 'tasks' && <U.Table label="全部工序安排" rows={data.tasks} size={50} columns={[
          ['批次 / 工序', t => <U.Button data-wb-print-value icon="arrow-right" onClick={() => onSelect(t.task_ref)}>{t.batch_id + ' · ' + t.process_label + ' ' + t.sequence}</U.Button>],
          ['分件', t => t.piece_id || window.WorkbenchTerms.shared_operation], ['目标量', t => U.number(t.quantity)], ['设备 / 人员', t => <>{name(t.machine_ref)}<br />{name(t.operator_ref)}</>],
          ['预计开工', t => U.timeLabel(t.start)], ['预计完工', t => U.timeLabel(t.end)], ['变更', t => t.changed ? '已调整' : '未变']]} />}
        {tab === 'unplanned' && <U.Table label="未安排工序" rows={data.unplanned_operations} columns={[
          ['工序顺序', r => r.sequence], ['分件', r => r.piece_id || window.WorkbenchTerms.shared_operation], ['原因', r => r.reason.message], ['编号', r => <window.WorkbenchReference value={r.operation_ref} label="工序编号" />]]} />}
      </div></section>;
  }
  window.TrialResults = { Summary, Results, Preparation };
})();
