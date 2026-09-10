(function () {
  const HOUR = 3600000, MAX_HOUR_WIDTH = 480, ZOOM = 1.6;
  const STEPS = [0.5, 1, 2, 3, 6, 12, 24, 48, 72, 168, 336, 672, 1344];
  const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
  const duration = (view) => (view.end - view.start) / HOUR;
  const center = (view) => view.start + (view.offset + view.availableWidth / 2) / view.hourw * HOUR;

  function measure(board) {
    const corner = board && board.querySelector('.gb-corner');
    if (!corner) return 0;
    const frozen = corner.getBoundingClientRect().width || corner.offsetWidth || corner.clientWidth;
    const style = window.getComputedStyle(board);
    const borders = (parseFloat(style.borderLeftWidth) || 0) + (parseFloat(style.borderRightWidth) || 0);
    const width = board.clientWidth || Math.max(0, board.getBoundingClientRect().width - borders);
    return frozen > 0 && width > 0 ? Math.max(0, width - frozen) : 0;
  }

  function scaled(view, requested, anchor, availableWidth) {
    const fit = availableWidth / duration(view);
    const hourw = clamp(requested, fit, Math.max(fit, MAX_HOUR_WIDTH));
    const mode = hourw <= fit * (1 + 1e-10) ? 'auto' : 'manual';
    const width = duration(view) * hourw;
    return { ...view, availableWidth, hourw: mode === 'auto' ? fit : hourw, mode,
      offset: mode === 'auto' ? 0 : clamp((anchor - view.start) / HOUR * hourw - availableWidth / 2, 0, width - availableWidth) };
  }

  function reconcile(previous, input, availableWidth) {
    const sourceChanged = !Object.is(previous.sourceKey, input.sourceKey);
    const rangeChanged = previous.start !== input.start || previous.end !== input.end;
    if (!sourceChanged && !rangeChanged && (!availableWidth || previous.availableWidth === availableWidth)) return previous;
    const next = { ...previous, ...input };
    if (input.start === null) return { ...next, availableWidth: 0, hourw: 0, offset: 0, mode: 'auto' };
    const width = availableWidth || (sourceChanged ? 0 : previous.availableWidth);
    if (sourceChanged || !previous.hourw || previous.mode === 'auto') {
      return { ...next, availableWidth: width, hourw: width / duration(next), offset: 0, mode: 'auto' };
    }
    return scaled(next, previous.hourw, center(previous), width);
  }

  function tickStep(hourw, minimum, minPixels) {
    let step = STEPS.find((hours) => hours >= minimum && hours * hourw >= minPixels);
    if (!step) {
      step = STEPS[STEPS.length - 1];
      while (step < minimum || step * hourw < minPixels) step *= 2;
    }
    return step;
  }

  function stepLabel(hours) {
    if (hours < 1) return '30 分钟';
    if (hours < 24) return hours + ' 小时';
    return hours % 168 === 0 ? hours / 168 + ' 周' : hours / 24 + ' 天';
  }

  function makeTicks(view, step, major) {
    const span = view.end - view.start, size = step * HOUR;
    // Week boundaries start on Monday UTC. Overscan is one visible span on either side.
    const origin = step >= 168 ? Date.UTC(1970, 0, 5) : 0;
    const visibleStart = view.start + (view.offset - view.availableWidth) / view.hourw * HOUR;
    const visibleEnd = view.start + (view.offset + 2 * view.availableWidth) / view.hourw * HOUR;
    const from = Math.max(view.start, visibleStart), to = Math.min(view.end, visibleEnd), ticks = [];
    for (let boundary = Math.floor((from - origin) / size) * size + origin; boundary < to; boundary += size) {
      const left = Math.max(view.start, boundary), right = Math.min(view.end, boundary + size);
      const iso = new Date(left).toISOString();
      ticks.push({ key: (major ? 'major:' : 'tick:') + boundary,
        label: major ? iso.slice(0, 10) : step < 24 ? iso.slice(11, 16) : iso.slice(5, 10),
        left: (left - view.start) / span * 100, width: (right - left) / span * 100 });
    }
    return ticks;
  }

  function useFieldGanttViewport({ boardRef, axis, sourceKey }) {
    const valid = !!axis && Number.isFinite(axis.start) && Number.isFinite(axis.end) && axis.end > axis.start;
    const start = valid ? axis.start : null, end = valid ? axis.end : null;
    const [view, setView] = React.useState(() => ({ start, end, sourceKey, availableWidth: 0, hourw: 0, offset: 0, mode: 'auto' }));
    const live = React.useRef({ view, input: { start, end, sourceKey }, pending: null });
    const binding = React.useRef({ board: null, corner: null, dispose: null });

    const publish = React.useCallback((next, position) => {
      if (next === live.current.view) return;
      live.current.view = next;
      if (position) live.current.pending = { view: next, ...position };
      setView(next);
    }, []);

    const sync = React.useCallback(() => {
      const { view: previous, input } = live.current;
      const next = reconcile(previous, input, measure(boardRef.current));
      const resetTop = !Object.is(previous.sourceKey, input.sourceKey);
      publish(next, next !== previous ? { left: next.offset, resetTop } : null);
    }, [boardRef, publish]);

    React.useLayoutEffect(() => {
      live.current.input = { start, end, sourceKey };
      sync();
    }, [start, end, sourceKey, sync]);

    const bindBoard = React.useCallback(() => {
      const board = boardRef.current;
      const corner = board && board.querySelector('.gb-corner');
      if (binding.current.board === board && binding.current.corner === corner) return;
      if (binding.current.dispose) binding.current.dispose();
      const onScroll = () => {
        const previous = live.current.view;
        if (!board || !previous.hourw || live.current.pending) return;
        const width = measure(board);
        if (width && width !== previous.availableWidth) { sync(); return; }
        const offset = clamp(board.scrollLeft, 0, Math.max(0, duration(previous) * previous.hourw - previous.availableWidth));
        if (offset !== previous.offset) publish({ ...previous, offset });
      };
      const observer = typeof window.ResizeObserver === 'function' ? new window.ResizeObserver(sync) : null;
      if (observer && board) observer.observe(board);
      if (observer && corner) observer.observe(corner);
      if (board) board.addEventListener('scroll', onScroll, { passive: true });
      binding.current = { board, corner, dispose: () => {
        if (observer) observer.disconnect();
        if (board) board.removeEventListener('scroll', onScroll);
      } };
      sync();
    }, [boardRef, sync, publish]);

    // Refs change during commit, not render. Probe identity only; hover never remeasures.
    React.useLayoutEffect(bindBoard);
    React.useLayoutEffect(() => {
      window.addEventListener('resize', sync);
      return () => {
        window.removeEventListener('resize', sync);
        if (binding.current.dispose) binding.current.dispose();
        binding.current = { board: null, corner: null, dispose: null };
      };
    }, [sync]);

    // Apply only queued commands, after React has committed the new track width.
    React.useLayoutEffect(() => {
      const pending = live.current.pending, board = boardRef.current;
      if (!pending || pending.view !== view || !board) return;
      board.scrollLeft = pending.left;
      if (pending.resetTop) board.scrollTop = 0;
      live.current.pending = null;
    }, [view, boardRef]);

    const changeZoom = React.useCallback((factor) => {
      sync();
      const previous = live.current.view, board = boardRef.current;
      if (!board || !previous.hourw) return;
      const anchor = center({ ...previous, offset: board.scrollLeft });
      const next = scaled(previous, previous.hourw * factor, anchor, previous.availableWidth);
      publish(next, { left: next.offset, resetTop: false });
    }, [boardRef, sync, publish]);
    const zoomIn = React.useCallback(() => changeZoom(ZOOM), [changeZoom]);
    const zoomOut = React.useCallback(() => changeZoom(1 / ZOOM), [changeZoom]);
    const fitAll = React.useCallback(() => {
      sync();
      const previous = live.current.view;
      const next = { ...previous, mode: 'auto', offset: 0,
        hourw: previous.start === null ? 0 : previous.availableWidth / duration(previous) };
      publish(next, { left: 0, resetTop: true });
    }, [sync, publish]);
    const focusRange = React.useCallback((startMs, endMs) => {
      if (!Number.isFinite(startMs) || !Number.isFinite(endMs) || endMs < startMs) return false;
      sync();
      const previous = live.current.view;
      if (!previous.hourw || endMs < previous.start || startMs > previous.end) return false;
      const from = Math.max(previous.start, startMs), to = Math.min(previous.end, endMs);
      const next = scaled(previous, previous.availableWidth / Math.max(0.5, (to - from) / HOUR), (from + to) / 2, previous.availableWidth);
      publish(next, { left: next.offset, resetTop: false });
      return true;
    }, [sync, publish]);

    const ready = view.start !== null && view.hourw > 0 && view.availableWidth > 0;
    const ticks = React.useMemo(() => {
      if (!ready) return { ticks: [], majorTicks: [], tickHours: 0, tickOffset: 0 };
      const tickHours = tickStep(view.hourw, 0.5, 72);
      const majorHours = tickStep(view.hourw, Math.max(24, tickHours * 2), 112);
      const origin = tickHours >= 168 ? Date.UTC(1970, 0, 5) : 0, step = tickHours * HOUR;
      const boundary = Math.floor((view.start - origin) / step) * step + origin;
      return { ticks: makeTicks(view, tickHours, false), majorTicks: makeTicks(view, majorHours, true), tickHours,
        tickOffset: (boundary - view.start) / HOUR * view.hourw };
    }, [ready, view]);
    const fit = ready ? view.availableWidth / duration(view) : 0;
    return { hourw: view.hourw, trackWidth: ready ? duration(view) * view.hourw : 0, mode: view.mode,
      tickLabel: ready ? stepLabel(ticks.tickHours) : '', availableWidth: view.availableWidth, ready,
      canZoomIn: ready && view.hourw < Math.max(fit, MAX_HOUR_WIDTH) * (1 - 1e-10),
      canZoomOut: ready && view.mode === 'manual', zoomIn, zoomOut, fitAll, focusRange, ...ticks };
  }

  function FieldGanttAxis({ axis, viewport, clock, fmt }) {
    const valid = !!axis && Number.isFinite(axis.start) && Number.isFinite(axis.end) && axis.end > axis.start;
    const clockVisible = valid && Number.isFinite(clock) && clock >= axis.start && clock <= axis.end;
    const position = clockVisible ? (clock - axis.start) / (axis.end - axis.start) * 100 : 0;
    const atEnd = position > 50;
    const iso = clockVisible ? new Date(clock).toISOString().slice(0, 16) : '';
    const stamp = clockVisible ? '时点 ' + (typeof fmt === 'function' ? fmt(iso) : iso.replace('T', ' ')) : '';
    const width = viewport ? viewport.trackWidth : 0;
    const tier = (items, major) => <div className={'fg-viewport-tier' + (major ? ' is-major' : '')}>
      {(items || []).map((tick) => <div key={tick.key} className="fg-viewport-tick" title={tick.label}
        style={{ left: tick.left + '%', width: tick.width + '%' }}><span className="fg-viewport-tick-label" style={{ visibility: tick.width * viewport.trackWidth / 100 < (major ? 90 : 46) ? 'hidden' : undefined }}>{tick.label}</span></div>)}
    </div>;
    return <div className="fg-axis fg-viewport-axis" aria-label="时间轴" style={{ width: width + 'px' }}>
      {tier(viewport && viewport.majorTicks, true)}
      {tier(viewport && viewport.ticks, false)}
      <div className="fg-viewport-clock">
        {clockVisible && <span className="fg-now fg-now-header fg-viewport-now" data-clock={clock} style={{ left: position + '%' }}>
          <span className={'fg-now-label fg-viewport-now-label' + (atEnd ? ' align-end' : '')} title={stamp}
            style={{ maxWidth: Math.max(0, (atEnd ? position : 100 - position) / 100 * width - 8) + 'px' }}>{stamp}</span>
        </span>}
      </div>
    </div>;
  }

  window.useFieldGanttViewport = useFieldGanttViewport;
  window.FieldGanttAxis = FieldGanttAxis;
})();
