(function () {
  'use strict';
  const U = window.TrialControls;
  function Summary({ data }) {
    const c = data.comparison;
    return <div className="tt-summary">{[[c.late_count, window.WorkbenchTerms.overdue_count], [c.total_delay_hours, window.WorkbenchTerms.total_tardiness_hours + ' h'], [c.changed_operations, '调整工序'], [c.moved_operations, '换设备工序']].map(([value, label]) =>
      <div key={label}><span>{label}</span><strong>{U.number(value)}</strong></div>)}<div><span>换型次数</span><strong>{c.changeovers === null ? '未评估' : U.number(c.changeovers)}</strong></div></div>;
  }
  function Calendar({ resource }) {
    return <details><summary>时段与日历</summary><div className="tt-subtable"><U.Table label="占用时段" rows={resource.segments} size={10}
      columns={[["开始", r => U.timeLabel(r.start)], ['结束', r => U.timeLabel(r.end)], ['并行工序', r => r.concurrent_operations]]} />
      <h4>可用窗口</h4>{resource.calendar.windows === null ? <p>真实日历不可用</p> : <U.Table label="可用窗口" rows={resource.calendar.windows} size={10}
        columns={[["开始", r => U.timeLabel(r.start)], ['结束', r => U.timeLabel(r.end)], ['效率', r => U.number(r.efficiency)], ['普通 / 急件', r => (r.allow_normal ? '允许' : '不允许') + ' / ' + (r.allow_urgent ? '允许' : '不允许')]]} />}
      <U.Issues rows={resource.calendar.issues} />{resource.calendar.downtime_windows && <><h4>停机时段</h4><U.Table label="停机时段" rows={resource.calendar.downtime_windows}
        columns={[["开始", r => U.timeLabel(r.start)], ['结束', r => U.timeLabel(r.end)]]} /></>}</div></details>;
  }
  function Results({ data, onSelect }) {
    const H = window.TrialAdoptionHistoryState, V = window.TrialViewState, preferences = V.useView(data);
    function readEntry() {
      try {
        const saved = history.state && history.state.trialAdoptionHistory;
        if (!data.scenario_ref || !saved || saved.scenario_ref !== data.scenario_ref) return { tab: null, error: null };
        if (!H) throw new Error('本页试调页签恢复组件未加载，未替换原记录。');
        return { tab: H.restore(data.scenario_ref).tab, error: null };
      } catch (_) { return { tab: null, error: new Error('本页试调页签记录无法恢复，未用默认页签覆盖。') }; }
    }
    const [entry, setEntry] = React.useState(readEntry), name = window.TrialGantt.resourceNames(data), c = data.comparison;
    const tab = entry.tab || preferences.value && preferences.value.result_tab;
    function clearEntry() {
      try {
        const current = history.state, saved = current && current.trialAdoptionHistory;
        if (saved && saved.scenario_ref === data.scenario_ref) {
          const next = { ...current }; delete next.trialAdoptionHistory; history.replaceState(next, '', location.href);
        }
        setEntry(readEntry());
      } catch (_) { setEntry({ ...entry, error: new Error('本页试调页签记录未能清除，未清理其他页面。') }); }
    }
    function selectTab(next) {
      preferences.change({ result_tab: next });
      try { if (H) H.remember(data.scenario_ref, { tab: next }); setEntry({ tab: next, error: null }); }
      catch (_) { setEntry({ tab: next, error: new Error('本页试调页签记录保存失败，返回后可能无法恢复。') }); }
    }
    if (!preferences.value || entry.error) return <section className="tt-results" aria-label="试调结果恢复">
      <V.Notice state={preferences} label="试调结果查看偏好" />{entry.error && <><U.ErrorBox error={entry.error} /><div className="tt-tools">
        <U.Button icon="refresh-cw" onClick={() => setEntry(readEntry())}>重读本页页签记录</U.Button>
        <U.Button icon="rotate-ccw" onClick={clearEntry}>清除本页页签记录</U.Button></div></>}</section>;
    const arrangement = r => <>{name(r.machine_ref)}<br />{name(r.operator_ref)}<br />{U.timeLabel(r.start)}<br />{U.timeLabel(r.end)}</>;
    return <section className="tt-results"><V.Notice state={preferences} label="试调结果查看偏好" /><U.Tabs value={tab} onChange={selectTab} label="试调结果" options={[
      ['delivery', '批次对比'], ['capacity', '资源占用'], ['history', '调整记录'], ['adoptions', '采用记录'], ['issues', '约束问题'], ['tasks', '完整任务'], ['unplanned', '未排工序']]} />
      <div role="tabpanel">
        {tab === 'adoptions' && (window.TrialAdoptionHistory ? <window.TrialAdoptionHistory data={data} /> : <p role="alert">采用记录组件尚未登记加载，未显示替代历史。</p>)}
        {tab === 'delivery' && <><p className="tt-muted">对比基础：原试调来源。交期截止为截至日次日零点（不含）；{c.changeover_reason}</p>
          <U.Table rows={c.batches} label="批次交付对比" columns={[
            ['批次 / 零件', r => <>{r.batch_id}<br />{r.part_name}</>], ['批次数量', r => U.number(r.quantity)], ['交付截至日', r => r.due_date || '未知'],
            ['原完工', r => U.timeLabel(r.baseline_finish)], ['试调完工', r => U.timeLabel(r.finish)], ['提前 h', r => U.number(r.improvement_hours)],
            ['预计交付', r => ({ on_time: '可按期', overdue: '预计晚交', unavailable: '约束阻断，不可评估', invalid_data: '交期数据无效' }[r.risk] || '未知')],
            ['晚交 h', r => U.number(r.late_hours)]]} /></>}
        {tab === 'capacity' && <><p className="tt-muted">仅此试调占用，非全厂利用率。{U.timeLabel(data.capacity.start)} 至 {U.timeLabel(data.capacity.end)}</p>
          {data.capacity.reason && <p className="tt-notice">{data.capacity.reason}</p>}<U.Table label="资源占用" rows={data.capacity.resources} columns={[
            ['资源', r => (r.resource_type === 'machine' ? '设备 ' : '人员 ') + name(r.resource_ref)], ['安排 h', r => U.number(r.arranged_hours)], ['去重占用 h', r => U.number(r.occupied_hours)],
            ['并行重叠 h', r => U.number(r.overlap_hours)], ['可用 h', r => U.number(r.available_hours)], ['窗口外 h', r => U.number(r.outside_available_hours)],
            ['本范围占用率', r => r.utilization === null ? '不可评估' : U.number(r.utilization * 100) + '%'], ['依据', r => <Calendar resource={r} />]]} /></>}
        {tab === 'history' && <><p className="tt-muted">本草稿的原子调整记录，不是正式采用记录。</p><U.Table label="调整记录" rows={data.change_history.slice().reverse()} columns={[
          ['记录时间', r => U.timeLabel(r.recorded_at)], ['操作者', r => r.local_operator], ['调整前', r => arrangement(r.before)], ['调整后', r => arrangement(r.after)],
          ['当时约束', r => U.statusLabel(r.validation.constraints_status)], ['记录依据', r => <details><summary>永久记录</summary><div className="tt-ref">{r.change_ref}</div><div className="tt-ref">{r.task_ref}</div></details>]]} /></>}
        {tab === 'issues' && <><p>整体约束：{U.statusLabel(data.validation.constraints_status)}</p><U.Issues rows={data.validation.issues} onSelect={onSelect} /></>}
        {tab === 'tasks' && <U.Table label="完整任务明细" rows={data.tasks} size={50} columns={[
          ['批次 / 工序', t => <U.Button icon="arrow-right" onClick={() => onSelect(t.task_ref)}>{t.batch_id + ' · ' + t.process_label + ' ' + t.sequence}</U.Button>],
          ['分件', t => t.piece_id || '整批'], ['目标量', t => U.number(t.quantity)], ['设备 / 人员', t => <>{name(t.machine_ref)}<br />{name(t.operator_ref)}</>],
          ['开始', t => U.timeLabel(t.start)], ['结束', t => U.timeLabel(t.end)], ['变更', t => t.changed ? '已调整' : '未变']]} />}
        {tab === 'unplanned' && <><p className="tt-muted">完整基础未排工序 {data.unplanned_operations.length} 道；未排完整不能当作可按期。</p><U.Table label="未排工序" rows={data.unplanned_operations} columns={[
          ['工序顺序', r => r.sequence], ['分件', r => r.piece_id || '整批'], ['原因', r => r.reason.message], ['永久工序引用', r => <span className="tt-ref">{r.operation_ref}</span>]]} /></>}
      </div></section>;
  }
  window.TrialResults = { Summary, Results };
})();
