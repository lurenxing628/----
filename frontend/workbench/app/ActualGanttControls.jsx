(function () {
  'use strict';
  const { Button, Icon } = window.ResourceControls, M = window.ActualGanttModel;
  function describe(item, labels, report) {
    const wording = { '执行投影不可用': '执行记录不可用', '完成依据：逐次执行投影': '完成依据：逐次报工记录' };
    return M.describe(item, labels, report).map(line => wording[line] || line);
  }
  function Styles() {
    return <><window.PointGantt.Styles /><style>{`
      .plana.fg-live { width:100%; max-width:none; min-width:0; padding:0; font:13px/1.5 var(--font-family); color:var(--ui-text); }
      .fg-live * { box-sizing:border-box; letter-spacing:0; }.fg-live h2,.fg-live h3,.fg-live p { margin:0; }
      .fg-live h2 { font-size:17px; }.fg-live h3 { font-size:14px; }.fg-live button,.fg-live input,.fg-live select { font:inherit; }
      .fg-live :focus-visible { outline:2px solid var(--ui-primary); outline-offset:1px; }
      .fg-live .fg-heading,.fg-live .fg-range,.fg-live .fg-foot { display:flex; flex-wrap:wrap; align-items:center; gap:8px 12px; }
      .fg-live .fg-heading { justify-content:space-between; margin-bottom:10px; }.fg-live .fg-heading > div { min-width:0; overflow-wrap:anywhere; }
      .fg-live .fg-muted { color:var(--ui-info-muted); font-size:12px; }.fg-live .fg-range { padding:10px; border-block:1px solid var(--ui-border); background:var(--ui-card-bg); }
      .fg-live .fg-range label { display:flex; align-items:center; gap:6px; min-width:0; white-space:nowrap; }.fg-live .fg-range input { width:152px; min-width:0; }
      .fg-live .fg-range select { max-width:235px; }.fg-live .fg-range .fg-batches { width:180px; }
      .fg-live .fg-workspace { overflow:hidden; border:1px solid var(--ui-border); border-radius:0; box-shadow:none; background:var(--ui-card-bg); }
      .fg-live .fg-toolbar { margin:0; padding:8px 10px; background:var(--ui-card-bg); }.fg-live .fg-toolbar-main { display:flex; flex-wrap:wrap; align-items:center; gap:8px 12px; }
      .fg-live .fg-toolbar-chart { background:var(--ui-card-bg); gap:8px 12px; }.fg-live .fg-toolbar-chart-actions { gap:6px 10px; }
      .fg-live .fg-search { width:235px; max-width:100%; min-width:150px; }.fg-live .fg-search input { width:100%; min-width:0; }
      .fg-live .fg-chain-toggle { display:inline-flex; align-items:center; gap:5px; white-space:nowrap; }.fg-live input[type=checkbox] { width:14px; height:14px; margin:0; accent-color:var(--ui-primary); }
      .fg-live .fg-icon-button { width:32px; height:32px; min-width:32px; padding:6px; border:1px solid var(--ui-border); border-radius:var(--wb-radius-control); color:var(--ui-text); background:var(--ui-card-bg); }
      .fg-live .fg-icon-button svg { width:16px; height:16px; }.fg-live .fg-late-filter { display:flex; align-items:center; gap:5px; }
      .fg-live .fg-metrics { display:flex; flex-wrap:wrap; gap:10px 26px; margin:10px 0; padding:0 10px; }.fg-live .fg-metrics > div { border:0; padding:0; }.fg-live .fg-metrics dt { color:var(--ui-info-muted); font-size:12px; }.fg-live .fg-metrics dd { margin:0; font-size:20px; }
      .fg-live .fg-board { height:480px; overflow:auto; position:relative; overscroll-behavior:contain; }.fg-live .fg-board-inner { position:relative; min-height:100%; }
      .fg-live .fg-axis { position:sticky; top:0; z-index:8; height:52px; display:flex; background:var(--ui-card-bg); border-bottom:1px solid var(--ui-border); }
      .fg-live .fg-corner { position:sticky; left:0; z-index:10; width:var(--fg-label); min-width:var(--fg-label); height:52px; padding:5px 10px; background:var(--ui-card-bg); border-right:1px solid var(--ui-border); }
      .fg-live .fg-ticks { position:relative; flex:none; overflow:hidden; }.fg-live .fg-tick { position:absolute; width:134px; top:0; bottom:0; padding:5px 6px; border-left:1px solid var(--ui-border); font-size:12px; }.fg-live .fg-tick small { display:block; }
      .fg-live .fg-virtual-row { position:absolute; left:0; display:flex; border-bottom:1px solid var(--ui-border); }
      .fg-live .fg-frozen { position:sticky; left:0; z-index:5; flex:none; width:var(--fg-label); height:100%; overflow:hidden; padding:6px 10px; background:var(--ui-card-bg); border-right:1px solid var(--ui-border); }
      .fg-live .fg-frozen strong { font-weight:500; }.fg-live .fg-frozen .fg-task-select { display:block; max-width:100%; padding:0; border:0; background:none; color:var(--ui-text); text-align:left; font-size:12px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
      .fg-live .fg-row-caption { display:block; color:var(--ui-info-muted); font-size:11px; line-height:16px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
      .fg-live .fg-virtual-row.is-selected .fg-frozen { box-shadow:inset 3px 0 var(--ui-primary); }
      .fg-live .fg-group-row { background:var(--ui-surface-muted); }.fg-live .fg-group-row .fg-frozen { background:var(--ui-surface-muted); display:flex; align-items:center; gap:7px; }
      .fg-live .fg-resource-label { display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; overflow-wrap:anywhere; line-height:19px; min-width:0; font-size:12px; }
      .fg-live .fg-group-summary { padding:16px 12px; font-size:12px; color:var(--ui-info-muted); white-space:nowrap; }
      .fg-live .fg-track { position:relative; flex:none; height:100%; min-height:0; background:var(--ui-card-bg); overflow:hidden; }
      .fg-live .fg-gridline { position:absolute; top:0; bottom:0; border-left:1px solid var(--ui-border); pointer-events:none; opacity:.6; }
      .fg-live .fg-mark { position:absolute; min-width:0; margin:0; padding:0; transform:none; border:0; overflow:hidden; box-shadow:none; border-radius:var(--wb-gantt-radius-bar); cursor:pointer; }
      .fg-live .fg-mark.fg-act { background:var(--wb-gantt-primary-fill); color:var(--wb-gantt-primary-ink); box-shadow:inset 0 0 0 1px var(--wb-gantt-primary-edge); }
      .fg-live .fg-mark.fg-plan { background:var(--wb-gantt-plan-fill); color:var(--wb-gantt-plan-ink); border-block:1px dashed var(--wb-gantt-plan-edge); }
      .fg-live .fg-mark.fg-remaining { background:var(--wb-gantt-reference-fill); color:var(--wb-gantt-primary-ink); border-block:1px dashed var(--wb-gantt-primary-edge); box-shadow:inset 1px 0 var(--wb-gantt-primary-edge),inset -1px 0 var(--wb-gantt-primary-edge); }
      .fg-live .fg-mark span { display:block; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; padding:0 6px; font-size:11px; line-height:16px; }
      .fg-live .fg-mark[aria-pressed=true] { outline:1px solid var(--wb-gantt-gold); outline-offset:-1px; }.fg-live .fg-mark:focus-visible { outline-offset:-1px; }
      .fg-live .fg-row-canvas { position:absolute; top:0; height:100%; }.fg-live .fg-now { border-left-color:var(--wb-gantt-plan-edge); }
      .fg-live .fg-canvas-point::after { visibility:hidden; }
      .fg-live .fg-baseline-end { position:absolute; top:70px; height:14px; width:0; border-left:1px solid var(--wb-gantt-plan-edge); z-index:3; pointer-events:none; }
      .fg-live .fg-clock { position:absolute; top:3px; bottom:0; width:0; border-left:1px solid var(--wb-gantt-plan-edge); }
      .fg-live .fg-wait { position:sticky; left:12px; display:inline-block; margin:16px 12px; font-size:12px; color:var(--ui-info-muted); max-width:280px; z-index:5; background:var(--ui-card-bg); }
      .fg-live .fg-details { display:flex; flex-wrap:wrap; gap:5px 20px; max-height:230px; overflow:auto; padding:10px 12px; border-bottom:1px solid var(--ui-border); background:var(--ui-card-bg); }.fg-live .fg-details > span { overflow-wrap:anywhere; }.fg-live .fg-details .fg-report-selector { display:flex; align-items:center; gap:8px; width:100%; }
      .fg-live .fg-note { padding:7px 10px; font-size:12px; color:var(--ui-info-muted); background:var(--ui-card-bg); overflow-wrap:anywhere; }
      .fg-live .fg-foot { padding:7px 10px; border-top:1px solid var(--ui-border); background:var(--ui-card-bg); font-size:12px; }.fg-live .fg-foot input { flex:1; min-width:90px; height:12px; padding:0; accent-color:var(--ui-primary); }
      .fg-live .fg-zoom-value { display:inline-block; width:42px; text-align:center; }
      .fg-live .fg-empty { padding:28px 10px; }.fg-live .fg-error { white-space:normal; overflow-wrap:anywhere; }.fg-live .fg-chain-strip { display:flex; gap:8px; padding:8px; flex-wrap:wrap; }
      .fg-live .fg-tip { position:fixed; z-index:200; max-width:360px; padding:10px; font-size:12px; white-space:pre-line; background:var(--ui-card-bg); color:var(--ui-text); border:1px solid var(--ui-border); pointer-events:none; overflow-wrap:anywhere; }
      .fg-live .fg-chain-slot { height:160px; overflow:auto; border-bottom:1px solid var(--ui-border); }
      .fg-live .fg-chain-strip { height:100%; overflow:auto; align-items:center; align-content:flex-start; }
      .fg-live .fg-chain-strip .fg-chain-heading { flex-basis:100%; font-size:12px; }
      .fg-live .fg-chain-strip .fg-chain-node { max-width:250px; white-space:normal; overflow-wrap:anywhere; text-align:left; }
      .fg-live .fg-chain-edge-label { font-size:11px; max-width:200px; overflow-wrap:anywhere; }
      .fg-live .fg-chain-lines { position:absolute; z-index:4; pointer-events:none; overflow:hidden; }
      .fg-live .fg-chain-lines path { fill:none; stroke:var(--ui-info-text); stroke-width:1.5px; }
      @media(max-width:1500px) { .fg-live .fg-board { height:430px; }.fg-live .fg-toolbar-chart-actions { margin-left:0; } }
      @media(max-width:700px) { .fg-live .fg-range label { width:100%; justify-content:space-between; }.fg-live .fg-range input,.fg-live .fg-range select { max-width:65%; }.fg-live .fg-search { width:100%; }.fg-live .fg-details { max-height:190px; } }
    `}</style></>;
  }
  function Toolbar({ view, patch, model, data, zoom, width, onZoom, onFit, onLocate, onExport, busy }) {
    const allCollapsed = model.groups.length > 0 && model.groups.every(g => view.collapsed[g.id]);
    const counts = Object.fromEntries(Object.keys(M.lateLabels).map(key => [key, key === 'all' ? data.items.length : data.items.filter(item => M.deadlines(item, M.wire(model.asOf))[key]).length]));
    return <div className="gb-toolbar fg-toolbar">
      <div className="fg-toolbar-main"><div className="seg" role="group" aria-label="甘特视图">
        {Object.entries(M.views).map(([key, label]) => <button key={key} className={'seg-btn' + (view.mode === key ? ' on' : '')} aria-pressed={view.mode === key} onClick={() => patch({ mode: key, collapsed: {} })}>{label}</button>)}</div>
        <label className="fg-search"><Icon name="search" /><input type="search" aria-label="搜索现场甘特" placeholder="批次 / 工序 / 设备 / 人员" maxLength={200} value={view.query} onChange={e => patch({ query: e.target.value })} /></label>
        <span className="fg-muted" data-actual-count>{model.groups.length} 组 · {model.items.length} / {data.task_count} 道工序</span>
        <label className="fg-late-filter">晚期<select aria-label="晚期筛选" value={view.late} onChange={e => patch({ late: e.target.value })}>{Object.entries(M.lateLabels).map(([key, label]) => <option key={key} value={key}>{label} ({counts[key]})</option>)}</select></label>
        <Button transfer="export" busy={busy} disabled={!model.items.length || data.availability.state !== 'available'} onClick={onExport}>导出 CSV</Button>
      </div>
      <div className="fg-toolbar-chart"><div className="fg-legend"><span className="fg-lg"><i className="fg-sw-plan" />原计划基线</span><span className="fg-lg"><i className="fg-sw-act" />实际报工</span><span className="fg-lg"><i className="fg-sw-remaining" />已有剩余安排</span>
        {data.critical_chain.state === 'available' && <label className="fg-chain-toggle"><input type="checkbox" checked={view.chain} onChange={e => patch({ chain: e.target.checked })} />关键链</label>}</div>
        <div className="fg-toolbar-chart-actions">
          <Button className="fg-icon-button" icon={allCollapsed ? 'unfold-vertical' : 'fold-vertical'} aria-label={allCollapsed ? '全部展开' : '全部折叠'} disabled={!model.groups.length} onClick={() => patch({ collapsed: allCollapsed ? {} : Object.fromEntries(model.groups.map(g => [g.id, true])) })} />
          <label className="fg-chain-toggle"><input type="checkbox" checked={view.onlySelected} disabled={!view.selected && !view.onlySelected} onChange={e => patch({ onlySelected: e.target.checked })} />只看选中</label>
          <label className="fg-chain-toggle"><input type="checkbox" checked={view.details} onChange={e => patch({ details: e.target.checked })} />详情</label>
          {view.chain && data.critical_chain.state === 'available' && <label className="fg-chain-toggle"><input type="checkbox" checked={view.chainLines !== false}
            disabled={!data.critical_chain.edges.length} onChange={e => patch({ chainLines: e.target.checked })} />关键链连线</label>}
          <Button className="fg-icon-button" icon="minus" aria-label="缩小时间轴" disabled={zoom <= 1} onClick={() => onZoom(zoom / 2)} /><span className="fg-zoom-value" aria-label="时间轴缩放模式">{zoom === 1 ? '自动' : '手动'}</span>
          <Button className="fg-icon-button" icon="plus" aria-label="放大时间轴" disabled={zoom >= 1024} onClick={() => onZoom(zoom * 2)} />
          <span className="fg-muted" aria-label="时间轴刻度" data-tick-step={M.tickStep(model, width)}>刻度 {M.tickLabel(M.tickStep(model, width))}</span>
          <Button className="fg-icon-button" icon="chart-gantt" aria-label="适应全部" onClick={onFit} />
          <Button className="fg-icon-button" icon="search" aria-label="定位选中工序" disabled={!model.items.some(i => i.task.task_ref === view.selected)} onClick={onLocate} />
        </div></div>
    </div>;
  }
  function Chain({ chain, model, onLocate }) {
    const visible = new Set(model.items.map(item => item.task.task_ref));
    return <div className="fg-chain-strip" aria-label="所选计划关键链" data-chain-context={chain.mode} data-chain-target={chain.target_task_ref || ''}>
      <div className="fg-chain-heading"><strong>{chain.mode === 'related' ? '当前对象目标的控制前驱链' : '整版计划控制前驱链'}</strong> · 原算法近似 · {chain.mode === 'related' ? '目标计划结束' : '计划最晚结束'} {M.time(chain.makespan_end)}
        {chain.partial && <span role="status"> · 部分结果：原算法不含 {chain.omitted_point_count} 个零时长点</span>}</div>
      {chain.state === 'unavailable' ? <span role="status">关联链不可用：{chain.reason}</span> : chain.nodes.map((node, index) => <React.Fragment key={node.task_ref}>
        {index > 0 && <span className="fg-chain-edge-label" title={chain.edges[index - 1].reason} data-chain-edge-reason>{chain.edges[index - 1].reason} · 间隔 {chain.edges[index - 1].gap_minutes} 分钟</span>}
        <Button className="fg-chain-node" icon="search" disabled={!visible.has(node.task_ref)} data-chain-node={node.task_ref}
          title={M.taskLabel(node)} onClick={() => onLocate(node.task_ref)}>{node.batch_id} · {node.sequence} {node.process_label}</Button>
      </React.Fragment>)}
      <span className="fg-muted">筛选内 {chain.task_refs.filter(ref => visible.has(ref)).length} / {chain.task_refs.length} 个节点 · 工艺实线，资源虚线 · 不是实际工时或剩余预测</span>
    </div>;
  }
  function Range({ scope, resources, onApply, busy }) {
    const [draft, setDraft] = React.useState(scope), [batches, setBatches] = React.useState((scope.batch_ids || []).join(','));
    React.useEffect(() => { setDraft(scope); setBatches((scope.batch_ids || []).join(',')); }, [scope]);
    const patch = value => setDraft(previous => ({ ...previous, ...value }));
    return <form className="fg-range" onSubmit={event => { event.preventDefault(); const next = { ...draft };
      Object.keys(next).forEach(key => { if (next[key] === '' || next[key] === null) delete next[key]; });
      if (!next.resource_ref) delete next.resource_type;
      if (batches.trim()) next.batch_ids = batches.split(',').map(v => v.trim()); else delete next.batch_ids;
      delete next.snapshot_ref; onApply(next);
    }}>
      {scope.range_start && <span className="fg-muted" title="按原计划时段相交选择工序；入选工序保留全部有效报工">原计划时段 {M.time(scope.range_start)} 至 {M.time(scope.range_end)}</span>}
      <label>计划完工日<input type="date" aria-label="计划完工开始日" value={draft.plan_finish_date_from || ''} onChange={e => patch({ plan_finish_date_from: e.target.value })} /></label>
      <label>至<input type="date" aria-label="计划完工结束日" value={draft.plan_finish_date_to || ''} onChange={e => patch({ plan_finish_date_to: e.target.value })} /></label>
      <label>资源<select aria-label="资源范围" value={draft.resource_ref || ''} onChange={e => { const row = resources.find(r => r.ref === e.target.value); patch({ resource_ref: e.target.value, resource_type: row ? row.kind : '' }); }}>
        <option value="">全部计划或实际资源</option>{resources.filter(r => r.kind !== 'supplier').map(r => <option key={r.ref} value={r.ref}>{M.views[r.kind]} · {r.label || r.business_code}</option>)}</select></label>
      <label>批次<input className="fg-batches" aria-label="批次范围" value={batches} onChange={e => setBatches(e.target.value)} /></label>
      <Button type="submit" icon="search" busy={busy}>应用范围</Button><Button icon="x" aria-label="清除来源范围" disabled={busy} onClick={() => onApply({ plan_ref: scope.plan_ref })} />
    </form>;
  }
  window.ActualGanttControls = { Styles, Toolbar, Range, Chain, describe };
})();
