(function () {
  'use strict';
  const { Button, Icon } = window.ResourceControls, M = window.ActualGanttModel;
  function describe(item, labels, report) {
    const wording = { '执行投影不可用': '执行记录不可用', '完成依据：逐次执行投影': '完成依据：逐次报工记录' };
    return M.describe(item, labels, report).map(line => wording[line] || line);
  }
  function Styles() {
    return <window.PointGantt.Styles />;
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
