(function () {
  'use strict';
  const M = window.RunCandidateModel, B = window.RunBaselineModel, { Button } = window.RunCandidateControls;
  function usePrintLayout() { return window.WorkbenchControls.usePrintLayout(); }
  function useBaseline(data, available) {
    const [enabled, setEnabled] = React.useState(false);
    const active = enabled && available;
    const read = window.APSResourceSession.useQuery(signal => window.RunBaselineAPI.create().read(data, signal).catch(error => {
      throw new Error(error.name === 'AbortError' ? '原安排读取超时，请刷新原安排。' : error.message);
    }), [data], active);
    return { ...read, retainedResult: read.result, result: active ? read.result : null, error: active ? read.error : null,
      busy: active && read.loading, enabled: active, toggle: setEnabled, retry: read.reload };
  }
  function Toggle({ state }) {
    return <label className="rb-toggle" title="叠加提交试排时冻结的正式版安排，与新安排对照"><input type="checkbox" checked={state.enabled} onChange={e => state.toggle(e.target.checked)} />显示原安排</label>;
  }
  function Source({ workspace, comparison }) {
    const { algorithm, baseline } = workspace.generation;
    const algorithmLabel = [algorithm.mode_label, algorithm.strategy_label].filter(Boolean).join(' · ');
    const source = comparison && comparison.baseline;
    return <div className="wb-gantt-comparison-source" data-candidate-comparison-source>
      <span title={algorithmLabel || '计算方式未记录'}><strong>新安排</strong>：{workspace.candidate.label || '当前候选'}</span>
      <span title={M.timeLabel(baseline.captured_at)}><strong>原安排</strong>：{source && source.available === false ? source.reason.message : <>排产时的正式计划{baseline.version === null ? '（版本未记录）' : ' v' + M.number(baseline.version)} · {window.WorkbenchFormat.dateTime(baseline.captured_at)}</>}
        {source && source.available && !source.comparison_available && ' · 当前没有可对照工序'}</span>
    </div>;
  }
  function Problems({ workspace, issues, onInspect }) {
    const labels = React.useMemo(() => new Map([
      ...workspace.gantt_graph.nodes, ...workspace.tasks, ...(workspace.unplanned_operations || [])
    ].map(row => [row.operation_ref, row])), [workspace]);
    if (!issues.length) return null;
    return <details className="rb-panel" data-candidate-change-unknown><summary>查看无法对照工序（{issues.length} 道）</summary>
      <ul>{issues.map(issue => { const task = labels.get(issue.operation_ref);
        return <li key={issue.operation_ref}><strong>{task ? (task.batch_label || task.batch_id || '批次名称未记录') + ' · ' + M.number(task.sequence) + ' ' + (task.process_label || '工序名称未记录') : '当前范围没有该工序的名称记录'}</strong>
          {task && <span> · {M.pieceLabel(task)}</span>}
          {issue.reasons.map(reason => <div key={reason.code}>{reason.message}</div>)}
          <Button icon="search" className="mini" onClick={() => onInspect(issue.operation_ref)}>查看原安排详情</Button>
        </li>;
      })}</ul></details>;
  }
  function Segments({ row, chosen }) {
    const printing = usePrintLayout(), [top, setTop] = React.useState(0), host = React.useRef(null), first = printing ? 0 : Math.max(0, Math.floor(top / 76) - 2);
    const segments = printing ? row.baseline_segments : row.baseline_segments.slice(first, first + 6);
    React.useEffect(() => {
      const index = chosen ? row.baseline_segments.findIndex(s => s.row_ref === chosen.row_ref) : 0;
      if (host.current) host.current.scrollTop = Math.max(0, index) * 76;
    }, [row, chosen]);
    return <div ref={host} className="rb-segments" data-baseline-segments role="region" aria-label="原安排完整分段" onScroll={e => setTop(e.currentTarget.scrollTop)}>
      <div style={{ height: row.baseline_segments.length * 76, position: 'relative', minWidth: 510 }}>
        {segments.map((s, i) => <div key={s.row_ref} data-baseline-segment={s.row_ref} className="rb-segment"
          style={{ top: (first + i) * 76 }} aria-current={!!chosen && chosen.row_ref === s.row_ref ? 'true' : undefined}>
          <div>{M.timeLabel(s.start)} 至 {M.timeLabel(s.end)}{!s.interval_comparable && ' · 起止不可比较'}</div>
          <div>{B.sourceLabel(s)} · 设备 {B.resourceLabel(s, 'machine')} · 人员 {B.resourceLabel(s, 'operator')} · 供应商 {B.resourceLabel(s, 'supplier')} · 起止时长 {M.number(s.elapsed_hours)} 小时</div>
          <small>{s.data_gaps.map(g => g.message).join(' · ')}</small><window.WorkbenchReference value={s.row_ref} /></div>)}
      </div>{!row.baseline_segments.length && <div>原安排没有该工序安排。</div>}</div>;
  }
  function Detail({ row, segment, workspace }) {
    const c = row.candidate, delta = row.delta, execution = row.execution_at_generation;
    return <div className="rb-detail" role="region" aria-label="原安排工序对照">
      <strong>{row.batch_label || '批次未记录'} · {M.number(row.sequence)} {row.process_label || '工序未记录'} · {B.statusLabels[row.status]}</strong>
      <window.WorkbenchReference entries={{ '工序编号': row.operation_ref }} />
      {c ? <><div>新安排：{M.timeLabel(c.start)} 至 {M.timeLabel(c.end)} · {B.sourceLabel(c)} · 设备 {B.resourceLabel(c, 'machine')} · 人员 {B.resourceLabel(c, 'operator')} · 供应商 {B.resourceLabel(c, 'supplier')}</div>
        <window.WorkbenchReference entries={{ '新安排编号': c.row_ref }} />
        {!workspace.tasks.some(t => t.row_ref === c.row_ref) && <div>该新安排在所选时间范围外。</div>}</> : <div>此候选方案未安排该工序。</div>}
      <Segments key={row.operation_ref} row={row} chosen={segment} />
      {row.comparison_available && <div>安排变动（新安排减原安排）：开始 {M.number(delta.start_hours)} 小时 · 结束 {M.number(delta.end_hours)} 小时 · 起止时长 {M.number(delta.elapsed_hours)} 小时
        <small>设备变化：{B.resourceChange(row, 'machine')} · 人员变化：{B.resourceChange(row, 'operator')} · 供应商变化：{B.resourceChange(row, 'supplier')}</small></div>}
      <div>生成时报工：{execution ? M.executionField(row, 'execution_state') : '提交试排时的报工记录缺失'}</div>
      {execution && <><div>{['target_quantity', 'known_completed_quantity', 'remaining_quantity'].map(key => <div key={key}>{M.executionLabels[key]}：{M.executionField(row, key)}</div>)}</div>
        {execution.unknown_record_count > 0 && <div>缺少完成数量的报工记录：{execution.unknown_record_count} 条</div>}
        {execution.legacy_unavailable_field_count > 0 && <div>历史报工未保存的字段：{execution.legacy_unavailable_field_count} 项</div>}
        <div>生成时报工数据质量：{M.executionField(row, 'data_quality')}</div></>}
      {row.reasons.filter(reason => !['execution_affected', 'resource_identity_unavailable'].includes(reason.code)).concat(row.data_gaps.filter(gap => !gap.field.startsWith('execution_at_generation'))).map((r, i) => <div key={i}>{r.message}</div>)}
    </div>;
  }
  function ComparisonList({ rows, chosen, onChoose }) {
    const printing = usePrintLayout(), [top, setTop] = React.useState(0), host = React.useRef(null), first = printing ? 0 : Math.max(0, Math.floor(top / 40) - 2);
    const visible = printing ? rows : rows.slice(first, first + 12);
    React.useEffect(() => {
      const index = chosen ? rows.findIndex(r => r.operation_ref === chosen.comparison.operation_ref) : -1, node = host.current;
      if (node && index >= 0 && (index * 40 < node.scrollTop || index * 40 + 40 > node.scrollTop + node.clientHeight)) node.scrollTop = index * 40;
    }, [chosen, rows]);
    return <div ref={host} className="rb-list" data-baseline-list role="region" aria-label="原安排对照列表" onScroll={e => setTop(e.currentTarget.scrollTop)}>
      <div style={{ height: rows.length * 40, minWidth: 570, position: 'relative' }}>{visible.map((r, i) =>
        <div className="rb-row" data-baseline-operation={r.operation_ref} key={r.operation_ref} style={{ top: (first + i) * 40 }}
          aria-current={!!chosen && chosen.comparison.operation_ref === r.operation_ref ? 'true' : undefined}>
          <span title={r.batch_label || '未记录'}>{r.batch_label || '未记录'}</span><span title={r.process_label || '未记录'}>{M.number(r.sequence)} {r.process_label || '未记录'}</span>
          <span>{B.statusLabels[r.status]}</span><span>{r.baseline_segments.length} 段{r.execution_affected && ' · 有报工影响'}</span>
          <Button icon="search" className="mini" aria-label={'原安排对照 ' + (r.batch_label || '批次未记录') + ' ' + M.number(r.sequence) + ' ' + (r.process_label || '工序未记录')} onClick={() => onChoose({ comparison: r, segment: null })} /></div>)}</div>
      {!rows.length && <div className="rc-empty">当前范围没有匹配对照。</div>}</div>;
  }
  function Panel({ state, rows, chosen, onChoose, workspace, inspecting = false, onShowAll }) {
    const [open, setOpen] = React.useState(false), d = state.result && state.result.data;
    React.useEffect(() => { if (chosen || inspecting) setOpen(true); }, [chosen, inspecting]);
    return <>{state.enabled && <>
      {state.busy && <div className="rc-muted" role="status">正在读取排产时的原安排。</div>}
      {state.error && <div role="alert">{state.error.message}<Button icon="refresh-cw" onClick={state.retry}>刷新原安排</Button></div>}
      {d && <><div className="rb-legend"><span><i />新安排</span><span><i className="rb-before" />原安排</span><span><i className="rb-selected" />已选工序</span></div>
        <details className="rb-panel" open={open} onToggle={e => setOpen(e.currentTarget.open)}><summary>{inspecting ? '无法对照工序' : '原安排对照明细'}（{rows.length}）</summary>
          {open && <><div>提交于 {M.timeLabel(d.generation.accepted_at)} · {d.baseline.captured_task_count} 段原安排 · 有报工影响 {d.execution_affected_count} 道</div>
            {inspecting && onShowAll && <Button className="mini" onClick={onShowAll}>查看全部对照</Button>}
            {inspecting && !rows.length && <div>这些工序位于当前读取范围外，请在“读取范围”选择“完整候选”。</div>}
            {d.baseline.reason && <div>{d.baseline.reason.message}</div>}
            {d.data_gaps.concat(state.result.warnings).filter(g => g.code !== 'not_an_optimization_score').map((g, i) => <div key={i}>{g.message}</div>)}
            <ComparisonList rows={rows} chosen={chosen} onChoose={onChoose} />
            {chosen && <><div className="rc-tools"><Button icon="x" aria-label="关闭原安排工序对照" onClick={() => onChoose(null)} /></div>
              <Detail row={chosen.comparison} segment={chosen.segment} workspace={workspace} /></>}</>}
        </details></>}
    </>}</>;
  }
  window.RunBaselineControls = { useBaseline, usePrintLayout, Toggle, Source, Problems, Panel };
})();
