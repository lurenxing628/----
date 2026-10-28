(function () {
  'use strict';
  function Controls({ graph, enabled, onChange, active, geometry, onClear, disabled = false }) {
    if (graph.state === 'unavailable') return <div className="wb-gantt-graph-note" role="status">工序关联暂不可用：{graph.reason}</div>;
    const unseen = active.related.size - geometry.relatedVisible, criticalUnseen = active.critical.size - geometry.criticalVisible;
    return <div className="wb-gantt-graph-tools">
      <label title="关键任务始终用金色标记。开启后显示全部关键链；指向或选中工序时只显示该分件工艺。"><input type="checkbox" checked={enabled} disabled={disabled} onChange={event => onChange(event.target.checked)} />显示关键链连线</label>
      <span><i className="wb-gantt-chain-swatch" />{active.critical.size} 道关键任务{criticalUnseen > 0 && '（画面外 ' + criticalUnseen + ' 道）'}</span>
      <div className="wb-gantt-route-caption" data-gantt-route-count={active.target ? true : undefined}>{active.target
        ? <><i className="wb-gantt-route-swatch" />{active.target.batch_id} · {active.target.piece_id === null ? '全部工艺分支' : '分件 ' + active.target.piece_id + ' 的完整工艺'} {active.related.size} 道{unseen > 0 && '（画面外 ' + unseen + ' 道）'}</>
        : '指向工序查看前后关联，点击保留。'}</div>
      <window.ResourceControls.Button className="btn mini" style={{ visibility: active.target ? 'visible' : 'hidden' }} disabled={disabled || !active.target} onClick={onClear}>清除工艺聚焦</window.ResourceControls.Button>
    </div>;
  }
  function Lines({ geometry, width, height, labelWidth, top = 0, rowTop = null }) {
    // Printed rows paginate independently. Each row carries its own vertical slice of the same graph.
    const paths = rowTop === null ? geometry.paths : geometry.paths.filter(edge => edge.bottom > rowTop && edge.top < rowTop + height);
    return <svg className="wb-gantt-graph-lines" style={{ left: labelWidth, top, width, height }} viewBox={'0 ' + (rowTop === null ? 0 : rowTop) + ' ' + width + ' ' + Math.max(1, height)} preserveAspectRatio="none"
      aria-label="关键链与工序前后关联" data-gantt-graph-lines data-gantt-graph-slice={rowTop === null ? undefined : rowTop} data-route-active={geometry.focused || undefined}>
      {paths.map(edge => <path key={edge.from_task_ref + ':' + edge.to_task_ref + ':' + edge.edge_type} d={edge.d}
        data-gantt-edge={edge.edge_type} data-gantt-edge-kind={edge.kind} data-from-task={edge.from_task_ref} data-to-task={edge.to_task_ref}
        strokeDasharray={edge.edge_type === 'process' ? undefined : '5 4'} />)}
    </svg>;
  }
  window.GanttGraphLayer = { Controls, Lines };
})();
