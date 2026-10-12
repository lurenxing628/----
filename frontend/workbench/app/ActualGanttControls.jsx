(function () {
  'use strict';
  const { Button, Icon, TimelineZoom } = window.ResourceControls, M = window.ActualGanttModel;
  // 工序说明只有 ActualGanttModel 那一份写法，这里不再改写措辞。
  const describe = M.describe;
  function Toolbar({ view, patch, model, data, zoom, width, onZoom, onFit, onLocate, onExport, busy }) {
    const allCollapsed = model.groups.length > 0 && model.groups.every(g => view.collapsed[g.id]);
    const counts = Object.fromEntries(Object.keys(M.lateLabels).map(key => [key, key === 'all' ? data.items.length : data.items.filter(item => M.deadlines(item, M.wire(model.asOf))[key]).length]));
    return <div className="gb-toolbar fg-toolbar">
      <div className="fg-toolbar-main"><div className="seg" role="group" aria-label="甘特视图">
        {Object.entries(M.views).map(([key, label]) => <button type="button" key={key} className={'seg-btn' + (view.mode === key ? ' on' : '')} aria-pressed={view.mode === key} onClick={() => patch({ mode: key, collapsed: {} })}>{label}</button>)}</div>
        <label className="fg-search"><Icon name="search" /><input type="search" aria-label="搜索现场甘特" placeholder="批次 / 工序 / 设备 / 人员" maxLength={200} value={view.query} onChange={e => patch({ query: e.target.value })} /></label>
        <span className="fg-muted" data-actual-count>{model.groups.length} 组 · {model.items.length} / {data.task_count} 道工序</span>
        <label className="fg-late-filter">{window.WorkbenchTerms.overdue}<select aria-label={window.WorkbenchTerms.overdue + '筛选'} value={view.late} onChange={e => patch({ late: e.target.value })}>{Object.entries(M.lateLabels).map(([key, label]) => <option key={key} value={key}>{label} ({counts[key]})</option>)}</select></label>
        <Button transfer="export" busy={busy} disabled={!model.items.length || data.availability.state !== 'available'} onClick={onExport}>导出</Button>
      </div>
      <div className="fg-toolbar-chart"><div className="fg-legend"><span className="fg-lg"><i className="fg-sw-plan" />原计划</span><span className="fg-lg"><i className="fg-sw-act" />实际报工</span><span className="fg-lg"><i className="fg-sw-remaining" />已有剩余安排</span>
        </div>
        <div className="fg-toolbar-chart-actions">
          <Button className="fg-icon-button" icon={allCollapsed ? 'unfold-vertical' : 'fold-vertical'} aria-label={allCollapsed ? '全部展开' : '全部折叠'} disabled={!model.groups.length} onClick={() => patch({ collapsed: allCollapsed ? {} : Object.fromEntries(model.groups.map(g => [g.id, true])) })} />
          <label className="fg-chain-toggle"><input type="checkbox" checked={view.onlySelected} disabled={!view.selected && !view.onlySelected} onChange={e => patch({ onlySelected: e.target.checked })} />只看选中</label>
          <Button icon={view.details ? 'panel-right-close' : 'panel-right-open'} aria-expanded={view.details} aria-controls="actual-gantt-detail" onClick={() => patch({ details: !view.details })}>{view.details ? '收起详情' : '详情'}</Button>
          <TimelineZoom zoom={zoom} max={1024} onZoom={onZoom} onFit={onFit} className="fg-icon-button" />
          <span className="fg-muted" aria-label="时间轴刻度" data-tick-step={M.tickStep(model, width)}>刻度 {M.tickLabel(M.tickStep(model, width))}</span>
          <Button className="fg-icon-button" icon="search" aria-label="定位选中工序" disabled={!model.items.some(i => i.task.task_ref === view.selected)} onClick={onLocate} />
        </div></div>
    </div>;
  }
  function Chain({ graph, model, onLocate }) {
    const visible = new Set(model.items.map(item => item.task.task_ref)), nodes = new Map(graph.nodes.map(node => [node.task_ref, node]));
    const incoming = new Map(graph.critical_edges.map(edge => [edge.to_task_ref, edge]));
    const edgeLabels = { process: '工艺先后', machine: '设备接续', operator: '人员接续' };
    return <div className="fg-chain-strip" aria-label="所选计划关键链">
      <div className="fg-chain-flow" role="group" aria-label="关键链工序">
        {graph.critical_task_refs.map(ref => {
          const node = nodes.get(ref), edge = incoming.get(ref);
          return <div className="fg-chain-step" key={ref}>
            {edge && <span className="fg-chain-edge-label" data-edge-type={edge.edge_type} data-chain-edge-reason>{edgeLabels[edge.edge_type]}</span>}
            <Button className="fg-chain-node" icon="search" data-chain-node={ref}
              title={M.taskLabel(node) + ' · ' + M.time(node.start) + ' 至 ' + M.time(node.end)} onClick={() => onLocate(ref)}>
              <span className="fg-chain-node-label"><span>{node.batch_id} · {M.pieceLabel(node)}</span><small>{node.sequence} {node.process_label}</small>
                <small>{M.time(node.start)} 至 {M.time(node.end)}{!visible.has(ref) && ' · 当前视图外'}</small></span>
            </Button>
          </div>;
        })}</div>
      <span className="fg-muted">当前显示 {graph.critical_task_refs.filter(ref => visible.has(ref)).length} / {graph.critical_task_refs.length} 道关键工序 · 与图中的金色标记一致</span>
    </div>;
  }
  function Range({ scope, resources, onApply, busy }) {
    const [draft, setDraft] = React.useState(scope), [batches, setBatches] = React.useState((scope.batch_ids || []).join(','));
    React.useEffect(() => { setDraft(scope); setBatches((scope.batch_ids || []).join(',')); }, [scope]);
    const patch = value => setDraft(previous => ({ ...previous, ...value }));
    return <form className="fg-range" onSubmit={event => { event.preventDefault(); const next = { ...draft };
      Object.keys(next).forEach(key => { if (next[key] === '' || next[key] === null) delete next[key]; });
      if (!next.resource_ref) delete next.resource_type;
      if (batches.trim()) next.batch_ids = batches.split(/[,，]+/).map(v => v.trim()).filter(Boolean); else delete next.batch_ids;
      delete next.snapshot_ref; onApply(next);
    }}>
      {scope.range_start && <span className="fg-muted">原计划时段 {M.time(scope.range_start)} 至 {M.time(scope.range_end)}<small>按原计划时段有重叠来挑工序；选中的工序保留全部有效报工</small></span>}
      <label>计划完工日<input type="date" aria-label="计划完工开始日" value={draft.plan_finish_date_from || ''} onChange={e => patch({ plan_finish_date_from: e.target.value })} /></label>
      <label>至<input type="date" aria-label="计划完工结束日" value={draft.plan_finish_date_to || ''} onChange={e => patch({ plan_finish_date_to: e.target.value })} /></label>
      <label>资源<select aria-label="资源范围" value={draft.resource_ref || ''} onChange={e => { const row = resources.find(r => r.ref === e.target.value); patch({ resource_ref: e.target.value, resource_type: row ? row.kind : '' }); }}>
        <option value="">全部计划或实际资源</option>{resources.filter(r => r.kind !== 'supplier').map(r => <option key={r.ref} value={r.ref}>{M.views[r.kind]} · {r.label || r.business_code}</option>)}</select></label>
      <label>批次<input className="fg-batches" aria-label="批次范围" placeholder="多个批次用逗号分隔" value={batches} onChange={e => setBatches(e.target.value)} /></label>
      <Button type="submit" icon="search" busy={busy}>应用范围</Button><Button icon="x" aria-label="清除来源范围" disabled={busy} onClick={() => onApply({ plan_ref: scope.plan_ref })} />
    </form>;
  }
  window.ActualGanttControls = { Toolbar, Range, Chain, describe };
})();
