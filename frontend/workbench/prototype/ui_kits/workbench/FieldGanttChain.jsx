function fgPlanElement(grid, id) {
  const row = grid && Array.from(grid.querySelectorAll('.fg-plan-row')).find((el) => el.dataset.taskId === id);
  const actual = grid && Array.from(grid.querySelectorAll('.gb-row')).find(el => el.dataset.taskId === id);
  return row && row.querySelector('.fg-plan') || actual && actual.querySelector('.fg-task-name');
}

function FieldGanttChainStrip({ chain, model, hoverTarget, onLocate, visibleIds, selectedTaskId }) {
  const visible = new Set(visibleIds), tasks = new Map(model.tasks.map((t) => [t.id, t]));
  const names = { task: '工序', batch: '批次', device: '设备', person: '人员' };
  const task = hoverTarget && hoverTarget.kind === 'task' && tasks.get(hoverTarget.key);
  const subject = task ? task.batch + ' · ' + task.op : hoverTarget && hoverTarget.key;
  const caption = hoverTarget ? names[hoverTarget.kind] + ' ' + subject + ' · 关联关键链'
    : chain && chain.kind === 'computed-example' ? '默认 · 当前样例关键链' : '默认 · 全局最长关键链';
  const minutes = chain && chain.durationMinutes;
  const duration = Number.isFinite(minutes) ? Math.floor(minutes / 60) + 'h' + (minutes % 60 ? ' ' + minutes % 60 + 'm' : '') : '时长未提供';
  return <div className="fg-chain-strip" aria-label={caption} data-chain-id={chain ? chain.id : ''} data-chain-context={hoverTarget ? hoverTarget.kind : 'default'}>
    <div className="fg-chain-caption"><strong title={caption}>{caption}</strong>{chain && <span className="fg-chain-duration">{chain.kind === 'computed-example' ? '计划跨度' : '累计计划'} {duration} · {chain.taskIds.length} 道</span>}
      <small>{chain && chain.kind === 'preset-example' ? '预设演示' : chain && chain.kind === 'computed-example' ? '样例计算 · v' + chain.planVersion : ''}</small></div>
    <div className="fg-chain-list">{!chain ? <span className="fg-chain-empty">当前对象暂无关联关键链</span> : chain.taskIds.map((id, index) => {
      const task = tasks.get(id), edge = chain.edges.find((item) => item.to === id);
      return <React.Fragment key={id}>
        {index > 0 && <span className="fg-chain-link" title={edge ? edge.reason : ''}>{fgIcon('chevron-right')}</span>}
        <button className={"fg-chain-node" + (selectedTaskId === id ? ' is-selected' : '')} disabled={!visible.has(id) || !task}
          aria-current={selectedTaskId === id ? 'true' : undefined} title={task ? task.batch + ' · ' + task.op + (edge ? ' · ' + edge.reason : '') : '工序未加载：' + id}
          onClick={() => onLocate(id)}>
          <span>{task ? task.batch + ' · ' + task.op : id}</span><small>{task ? task.machine + ' / ' + task.person : '工序未加载'}</small>
        </button>
      </React.Fragment>;
    })}</div>
    <span className="fg-chain-filtered">{chain && chain.taskIds.some((id) => !visible.has(id)) ? '筛选内 ' + chain.taskIds.filter((id) => visible.has(id)).length + ' / ' + chain.taskIds.length + ' 个节点'
      : chain && !chain.edges.length ? '本样例内无前驱连线' : '工序关系：实线 · 资源衔接：虚线'}</span>
  </div>;
}

function FieldGanttChainLines({ chain, gridRef, layoutKey }) {
  const [geometry, setGeometry] = React.useState({ width: 0, height: 0, paths: [] });
  const markerId = 'fg-arrow-' + React.useId().replace(/:/g, '');
  React.useLayoutEffect(() => {
    const measure = () => {
      const grid = gridRef.current;
      if (!grid) return;
      const base = grid.getBoundingClientRect(), paths = [];
      const plans = new Map(Array.from(grid.querySelectorAll('.fg-plan-row')).map((row) => [row.dataset.taskId, row.querySelector('.fg-plan')]));
      chain.edges.forEach((edge) => {
        const from = plans.get(edge.from), to = plans.get(edge.to);
        if (!from || !to) return;
        const a = from.getBoundingClientRect(), b = to.getBoundingClientRect();
        if (!a.width || !b.width) return;
        const sx = a.right - base.left, sy = a.top + a.height / 2 - base.top;
        const tx = b.left - base.left, ty = b.top + b.height / 2 - base.top;
        const middle = Math.max(sx + 12, (sx + tx) / 2);
        paths.push({ ...edge, d: 'M' + sx + ',' + sy + ' H' + middle + ' V' + ty + ' H' + tx });
      });
      setGeometry({ width: base.width, height: base.height, paths });
    };
    measure();
    const raf = requestAnimationFrame(measure);
    const observer = window.ResizeObserver ? new window.ResizeObserver(measure) : null;
    if (observer && gridRef.current) observer.observe(gridRef.current);
    window.addEventListener('resize', measure);
    return () => { cancelAnimationFrame(raf); if (observer) observer.disconnect(); window.removeEventListener('resize', measure); };
  }, [chain, gridRef, layoutKey]);
  return <svg className="fg-chain-lines" width={geometry.width} height={geometry.height} aria-label="当前关键链连线" data-chain-id={chain.id}>
    <defs><marker id={markerId} viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto"><path d="M1 1L7 4L1 7" className="fg-chain-arrow" /></marker></defs>
    {geometry.paths.map((edge) => <path key={edge.from + ':' + edge.to} className={'fg-chain-edge ' + edge.type} d={edge.d}
      data-from={edge.from} data-to={edge.to} markerEnd={'url(#' + markerId + ')'} role="img" aria-label={edge.reason}><title>{edge.reason}</title></path>)}
  </svg>;
}
window.FieldGanttChainStrip = FieldGanttChainStrip;
window.FieldGanttChainLines = FieldGanttChainLines;
