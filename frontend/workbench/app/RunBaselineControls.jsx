(function () {
  'use strict';
  const M = window.RunCandidateModel, B = window.RunBaselineModel, { Button } = window.RunCandidateControls;
  function useBaseline(data) {
    const [enabled, setEnabled] = React.useState(false), [revision, refresh] = React.useReducer(v => v + 1, 0);
    const [state, setState] = React.useState({ result: null, error: null, busy: false }), request = React.useRef(null);
    const identity = React.useMemo(() => ({}), [data, enabled, revision]);
    React.useLayoutEffect(() => {
      const controller = new AbortController(); request.current = controller;
      setState({ identity, result: null, error: null, busy: enabled });
      if (enabled) window.RunBaselineAPI.create().read(data, controller.signal).then(result => {
        if (!controller.signal.aborted) setState({ identity, result, error: null, busy: false });
      }).catch(error => {
        if (!controller.signal.aborted) setState({ identity, result: null, error: new Error(error.name === 'AbortError' ? '初始计划读取超时，没有显示上次结果。请点「刷新初始计划」。' : error.message), busy: false });
      });
      return () => controller.abort();
    }, [identity]);
    function toggle(value) { if (request.current) request.current.abort(); setEnabled(value); }
    function retry() { if (request.current) request.current.abort(); refresh(); }
    return { ...(state.identity === identity ? state : { result: null, error: null, busy: enabled }), enabled, toggle, retry };
  }
  function Toggle({ state }) {
    return <label className="rb-toggle"><input type="checkbox" checked={state.enabled} onChange={e => state.toggle(e.target.checked)} />初始计划</label>;
  }
  function Segments({ row, chosen }) {
    const [top, setTop] = React.useState(0), host = React.useRef(null), first = Math.max(0, Math.floor(top / 76) - 2);
    React.useEffect(() => {
      const index = chosen ? row.baseline_segments.findIndex(s => s.row_ref === chosen.row_ref) : 0;
      if (host.current) host.current.scrollTop = Math.max(0, index) * 76;
    }, [row, chosen]);
    return <div ref={host} className="rb-segments" data-baseline-segments role="region" aria-label="初始计划完整分段" onScroll={e => setTop(e.currentTarget.scrollTop)}>
      <div style={{ height: row.baseline_segments.length * 76, position: 'relative', minWidth: 510 }}>
        {row.baseline_segments.slice(first, first + 6).map((s, i) => <div key={s.row_ref} data-baseline-segment={s.row_ref} className="rb-segment"
          style={{ top: (first + i) * 76 }} aria-selected={!!chosen && chosen.row_ref === s.row_ref}>
          <div>{M.timeLabel(s.start)} 至 {M.timeLabel(s.end)}{!s.interval_comparable && ' · 起止不可比较'}</div>
          <div>设备 {s.machine && s.machine.label || '未记录'} · 人员 {s.operator && s.operator.label || '未记录'} · 起止时长 {M.number(s.elapsed_hours)} 小时</div>
          <small>{s.data_gaps.map(g => g.message).join(' · ')}</small><window.WorkbenchReference value={s.row_ref} /></div>)}
      </div>{!row.baseline_segments.length && <div>初始计划没有该工序安排。</div>}</div>;
  }
  function Detail({ row, segment, workspace }) {
    const c = row.candidate, delta = row.delta;
    return <div className="rb-detail" role="region" aria-label="初始计划工序对照">
      <strong>{row.batch_label || '批次未记录'} · {M.number(row.sequence)} {row.process_label || '工序未记录'} · {B.statusLabels[row.status]}</strong>
      <window.WorkbenchReference entries={{ '工序编号': row.operation_ref }} />
      {c ? <><div>候选安排：{M.timeLabel(c.start)} 至 {M.timeLabel(c.end)} · 设备 {c.machine && c.machine.label || '未记录'} · 人员 {c.operator && c.operator.label || '未记录'}</div>
        <window.WorkbenchReference entries={{ '候选安排编号': c.row_ref }} />
        {!workspace.tasks.some(t => t.row_ref === c.row_ref) && <div>该候选安排不在当前读取范围；此处保留完整对照。</div>}</> : <div>候选没有安排此工序；未排不代表改善。</div>}
      <Segments key={row.operation_ref} row={row} chosen={segment} />
      {row.comparison_available && <div>安排变动（候选减初始计划）：开始 {M.number(delta.start_hours)} 小时 · 结束 {M.number(delta.end_hours)} 小时 · 起止时长 {M.number(delta.elapsed_hours)} 小时
        <small>设备变化 {delta.machine_changed === null ? '未知' : delta.machine_changed ? '有' : '无'} · 人员变化 {delta.operator_changed === null ? '未知' : delta.operator_changed ? '有' : '无'}</small></div>}
      <div>生成时报工：{row.execution_at_generation ? M.executionValue(row.execution_at_generation.execution_state) : '未记录'}{row.execution_affected && ' · 已有报工影响或数量未知'}</div>
      {row.reasons.concat(row.data_gaps).map((r, i) => <div key={i}>{r.message}</div>)}
    </div>;
  }
  function ComparisonList({ rows, chosen, onChoose }) {
    const [top, setTop] = React.useState(0), host = React.useRef(null), first = Math.max(0, Math.floor(top / 40) - 2);
    React.useEffect(() => {
      const index = chosen ? rows.findIndex(r => r.operation_ref === chosen.comparison.operation_ref) : -1, node = host.current;
      if (node && index >= 0 && (index * 40 < node.scrollTop || index * 40 + 40 > node.scrollTop + node.clientHeight)) node.scrollTop = index * 40;
    }, [chosen, rows]);
    return <div ref={host} className="rb-list" data-baseline-list role="region" aria-label="初始计划对照列表" onScroll={e => setTop(e.currentTarget.scrollTop)}>
      <div style={{ height: rows.length * 40, minWidth: 570, position: 'relative' }}>{rows.slice(first, first + 12).map((r, i) =>
        <div className="rb-row" data-baseline-operation={r.operation_ref} key={r.operation_ref} style={{ top: (first + i) * 40 }}
          aria-selected={!!chosen && chosen.comparison.operation_ref === r.operation_ref}>
          <span title={r.batch_label || '未记录'}>{r.batch_label || '未记录'}</span><span title={r.process_label || '未记录'}>{M.number(r.sequence)} {r.process_label || '未记录'}</span>
          <span>{B.statusLabels[r.status]}</span><span>{r.baseline_segments.length} 段{r.execution_affected && ' · 有报工影响'}</span>
          <Button icon="search" className="mini" aria-label={'初始计划对照 ' + (r.batch_label || '批次未记录') + ' ' + M.number(r.sequence) + ' ' + (r.process_label || '工序未记录')} onClick={() => onChoose({ comparison: r, segment: null })} /></div>)}</div>
      {!rows.length && <div className="rc-empty">当前范围没有匹配对照。</div>}</div>;
  }
  function Panel({ state, rows, chosen, onChoose, workspace }) {
    const [open, setOpen] = React.useState(false), d = state.result && state.result.data;
    React.useEffect(() => { if (chosen) setOpen(true); }, [chosen]);
    return <>{state.enabled && <>
      {state.busy && <div className="rc-muted" role="status">正在读取排产时的初始计划。</div>}
      {state.error && <div role="alert">{state.error.message}<Button icon="refresh-cw" aria-label="刷新初始计划" onClick={state.retry} /></div>}
      {d && <><div className="rb-legend"><span><i />候选安排</span><span><i className="rb-before" />初始计划</span><span><i className="rb-selected" />已选工序</span></div>
        <details className="rb-panel" open={open} onToggle={e => setOpen(e.currentTarget.open)}><summary>初始计划对照明细（{rows.length}） · 说明</summary>
          {open && <><div>提交于 {M.timeLabel(d.generation.accepted_at)} · {d.baseline.captured_task_count} 段初始安排 · 有报工影响 {d.execution_affected_count} 道</div>
            <div>安排变动不等于收益；未排不代表改善。</div>{d.baseline.reason && <div>{d.baseline.reason.message}</div>}
            {d.data_gaps.concat(state.result.warnings).map((g, i) => <div key={i}>{g.message}</div>)}
            <ComparisonList rows={rows} chosen={chosen} onChoose={onChoose} />
            {chosen && <><div className="rc-tools"><Button icon="x" aria-label="关闭初始计划工序对照" onClick={() => onChoose(null)} /></div>
              <Detail row={chosen.comparison} segment={chosen.segment} workspace={workspace} /></>}</>}
        </details></>}
    </>}</>;
  }
  window.RunBaselineControls = { useBaseline, Toggle, Panel };
})();
