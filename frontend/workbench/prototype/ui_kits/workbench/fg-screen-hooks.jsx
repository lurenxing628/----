function useFieldGanttScreenState(initialContext, onSourceChange, onNav) {
  const api = window.APSFieldGanttUI;
  const [state, setState] = React.useState(() => api.initial(initialContext));
  const patch = React.useCallback(change => setState(previous => ({ ...previous,
    ...(typeof change === 'function' ? change(previous) : change) })), []);
  React.useEffect(() => { api.save(initialContext, state); }, [initialContext, state]);
  const changeSource = value => {
    const next = { ...state, source: value, scope: null, search: '', selectedTaskId: null,
      lateFilter: 'all', onlySelected: false, collapsed: {}, viewport: null };
    setState(next);
    const context = { ...initialContext, source: value, scope: null, search: '', taskId: null, returning: false };
    api.save(context, next);
    if (onNav) onNav('fieldgantt', context);
    else if (onSourceChange) onSourceChange(value, context);
  };
  return { state, patch, changeSource };
}

function useFieldGanttLocation({ model, axis, viewport, boardRef, gridRef, state, patch, visibleIds }) {
  const [request, setRequest] = React.useState(null);
  const restored = React.useRef(false), firstSelection = React.useRef(false);
  const visibleKey = visibleIds.join('\n');
  const revealFocus = React.useCallback(target => {
    const board = boardRef.current, corner = board && board.querySelector('.gb-corner');
    if (!corner || !target || !board.contains(target) || !viewport.availableWidth) return;
    const rect = target.getBoundingClientRect(), left = corner.getBoundingClientRect().right;
    if (!rect.height) return;
    const right = left + viewport.availableWidth, fits = rect.width <= viewport.availableWidth;
    // Native Tab scrolling sees the full board, including the frozen resource column.
    if (rect.left >= left && rect.right <= right || rect.left < left && rect.right > right) return;
    const offset = rect.left < left ? (fits ? rect.left - left : rect.right - right)
      : (fits ? rect.right - right : rect.left - left);
    board.scrollLeft = Math.max(0, Math.min(viewport.trackWidth - viewport.availableWidth, board.scrollLeft + offset));
  }, [boardRef, viewport.availableWidth, viewport.trackWidth]);
  const locateTask = React.useCallback(id => {
    if (!model || !model.tasks.some(t => t.id === id)) return;
    patch(previous => ({ selectedTaskId: id, collapsed: Object.fromEntries(Object.entries(previous.collapsed)
      .filter(([key]) => {
        const [source, view, name] = JSON.parse(key);
        if (source !== previous.source || view !== previous.view) return true;
        const task = model.tasks.find(t => t.id === id);
        const owners = [task, ...task.reports, task.remainingPlan].filter(Boolean);
        return view === 'batch' ? name !== task.batch : !owners.some(owner =>
          (view === 'device' ? owner.machine || '实际设备未填写' : owner.person || '实际人员未填写') === name);
      })) }));
    setRequest({ id });
  }, [model, patch]);
  React.useLayoutEffect(() => {
    if (!viewport.ready || restored.current) return;
    restored.current = true;
    const saved = state.viewport;
    if (saved && saved.source === state.source) {
      if (saved.mode === 'manual') viewport.focusRange(saved.start, saved.end);
      const raf = requestAnimationFrame(() => { if (boardRef.current) boardRef.current.scrollTop = saved.top; });
      return () => cancelAnimationFrame(raf);
    }
  }, [viewport.ready, state.source]);
  React.useEffect(() => {
    if (!viewport.ready || firstSelection.current) return;
    firstSelection.current = true;
    if (state.selectedTaskId && !state.viewport && visibleIds.includes(state.selectedTaskId)) locateTask(state.selectedTaskId);
  }, [viewport.ready, visibleKey, state.selectedTaskId, locateTask]);
  React.useLayoutEffect(() => {
    if (!request || !viewport.ready || !visibleIds.includes(request.id)) return;
    const t = model.tasks.find(item => item.id === request.id);
    const values = [t.planStart, t.planEnd, ...t.reports.flatMap(r => [r.start, r.end]),
      t.remainingPlan && t.remainingPlan.start, t.remainingPlan && t.remainingPlan.end].filter(Boolean).map(model.ms).filter(Number.isFinite);
    if (values.length) viewport.focusRange(Math.min(...values), Math.max(...values));
    const raf = requestAnimationFrame(() => {
      const target = fgPlanElement(gridRef.current, request.id), board = boardRef.current;
      if (target && board) {
        const header = board.querySelector('.gb-scale');
        board.scrollTop += target.getBoundingClientRect().top - board.getBoundingClientRect().top - (header ? header.getBoundingClientRect().height : 0) - 28;
        target.focus({ preventScroll: true });
      }
      setRequest(null);
    });
    return () => cancelAnimationFrame(raf);
  }, [request, viewport.ready, visibleKey, state.view]);
  const live = React.useRef(null);
  live.current = { state, viewport, axis };
  const rememberViewport = React.useCallback(() => {
    const current = live.current, board = boardRef.current;
    if (!board || !current.viewport.ready) return;
    const { hourw, availableWidth, mode } = current.viewport;
    patch({ viewport: { source: current.state.source, mode, top: board.scrollTop,
      start: current.axis.start + board.scrollLeft / hourw * 3600000,
      end: current.axis.start + (board.scrollLeft + availableWidth) / hourw * 3600000 } });
  }, [patch, boardRef]);
  React.useEffect(rememberViewport, [viewport.hourw, viewport.availableWidth, viewport.mode, rememberViewport]);
  React.useLayoutEffect(() => {
    const board = boardRef.current;
    if (!board) return;
    const resize = () => {
      const top = board.getBoundingClientRect().top;
      board.style.maxHeight = Math.max(240, window.innerHeight - top - 28) + 'px';
    };
    resize();
    const observer = window.ResizeObserver ? new window.ResizeObserver(resize) : null;
    if (observer) observer.observe(board.closest('.fg-page') || board.parentElement);
    window.addEventListener('resize', resize);
    window.addEventListener('scroll', resize, { passive: true });
    return () => { if (observer) observer.disconnect(); window.removeEventListener('resize', resize); window.removeEventListener('scroll', resize); };
  }, [state.showDetails, state.showChain, state.scope, state.source]);
  return { locateTask, rememberViewport, revealFocus };
}
window.useFieldGanttScreenState = useFieldGanttScreenState;
window.useFieldGanttLocation = useFieldGanttLocation;
