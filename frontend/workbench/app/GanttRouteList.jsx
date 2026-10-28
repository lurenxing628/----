(function () {
  'use strict';
  const { Button } = window.ResourceControls, G = window.GanttGraph, F = window.WorkbenchFormat;
  const pieceLabel = node => node.piece_id === null ? '共同工序' : '分件 ' + node.piece_id;
  const operationLabel = node => (node.sequence === null ? '' : node.sequence + ' ') + (node.process_label || '工序名称未记录');
  function RouteGroup({ group, selectedPiece, collapsible, children }) {
    const label = group.pieceId === null ? '共同工序' : '分件 ' + group.pieceId;
    return collapsible ? <details className="gantt-route-group" open={group.pieceId === null || group.pieceId === selectedPiece}>
      <summary className="gantt-route-group-heading">{label}<small> · {group.nodes.length} 道</small></summary>{children}</details>
      : <div className="gantt-route-group"><h4>{label}</h4>{children}</div>;
  }
  function GanttRouteList({ index, targetRef, loadedRefs, onSelect, disabled = false, collapsible = false }) {
    const graph = index.graph;
    const route = React.useMemo(() => G.route(index, targetRef), [index, targetRef]);
    const pieceCount = route ? route.groups.filter(group => group.pieceId !== null).length : 0, missing = index.missingPredecessors.get(targetRef);
    return <section className="gantt-route" aria-label="完整工艺路线"><h3>完整工艺路线</h3>
      {graph.state !== 'available' ? <p className="gantt-route-summary">{graph.reason}</p> : !route ?
        <p className="gantt-route-summary">此工序未安排，暂无甘特节点。</p> : <>
          <p className="gantt-route-summary">{route.target.batch_id} · {route.count} 道已安排{pieceCount > 0 &&
            ' · ' + pieceCount + ' 个分件'}。点击工序定位；前序按实际关系显示。</p>
          {route.groups.map(group => <RouteGroup group={group} selectedPiece={route.target.piece_id} collapsible={collapsible} key={(route.target.piece_id || 'common') + ':' + (group.pieceId === null ? 'common' : 'piece:' + group.pieceId)}>
            <ul className="gantt-route-list">{group.nodes.map(node => {
              const outside = !loadedRefs.has(node.task_ref), previous = route.previous.get(node.task_ref);
              const related = route.target.piece_id === null || node.piece_id === null || node.piece_id === route.target.piece_id;
              const start = F.dateTime(node.start), end = F.dateTime(node.end), sameDay = start.slice(0, 10) === end.slice(0, 10);
              return <li key={node.task_ref} className="gantt-route-node" data-gantt-route-node={node.task_ref} data-selected={node.task_ref === targetRef || undefined}
                data-related={related || undefined} data-outside={outside || undefined}>
                <Button className="btn gantt-route-select" disabled={disabled} aria-current={node.task_ref === targetRef ? 'step' : undefined}
                  aria-label={'定位工序 ' + pieceLabel(node) + ' · ' + operationLabel(node)} onClick={() => onSelect(node.task_ref)}
                  title={F.dateTime(node.start, { seconds: true, fractions: true }) + ' 至 ' + F.dateTime(node.end, { seconds: true, fractions: true })}>
                  <strong>{operationLabel(node)}</strong><small>{start.slice(5)} → {end.slice(sameDay ? 11 : 5)}{outside && ' · 范围外'}</small>
                </Button>
                {!!previous.length && <div className="gantt-route-dependencies"><span>前序</span>{previous.map(parent =>
                  <Button key={parent.task_ref} className="linkbtn gantt-route-predecessor" disabled={disabled} onClick={() => onSelect(parent.task_ref)}
                    aria-label={'定位前序 ' + pieceLabel(parent) + ' · ' + operationLabel(parent)}>{pieceLabel(parent)} · {operationLabel(parent)}</Button>)}</div>}
              </li>;
            })}</ul></RouteGroup>)}
          {missing > 0 && <p className="plan-muted">所选工序有 {missing} 道前序未在本计划安排。</p>}
        </>}
    </section>;
  }
  window.GanttRouteList = GanttRouteList;
})();
