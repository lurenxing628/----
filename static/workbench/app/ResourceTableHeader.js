(function () {
  'use strict';

  const M = window.ResourceTableFilterModel,
    {
      Button,
      Icon
    } = window.ResourceControls;
  function useResize({
    columnKey,
    kind,
    scopeKey,
    width,
    disabled,
    onResize
  }, holder) {
    const drag = React.useRef(null),
      live = React.useRef(null),
      [measured, setMeasured] = React.useState(56),
      [moving, setMoving] = React.useState(false);
    live.current = {
      columnKey,
      kind,
      disabled,
      onResize
    };
    const currentWidth = measured;
    function measure() {
      const th = holder.current && holder.current.closest('th');
      return Math.max(56, Math.round(th ? th.getBoundingClientRect().width : Number.isFinite(width) ? width : 56));
    }
    React.useLayoutEffect(() => {
      const th = holder.current && holder.current.closest('th');
      if (!th) return;
      const update = () => setMeasured(measure()),
        observer = new ResizeObserver(update);
      update();
      observer.observe(th);
      return () => observer.disconnect();
    }, [columnKey, kind, holder]);
    function finish(revert) {
      const state = drag.current;
      if (!state) return;
      drag.current = null;
      state.cleanup();
      if (state.node.hasPointerCapture(state.pointerId)) state.node.releasePointerCapture(state.pointerId);
      document.body.style.cursor = state.cursor;
      document.body.style.userSelect = state.userSelect;
      setMoving(false);
      if (revert && !live.current.disabled && live.current.columnKey === state.columnKey && live.current.kind === state.kind) state.resize(state.startWidth);
    }
    React.useEffect(() => () => finish(false), [columnKey, kind, scopeKey, disabled]);
    function start(event) {
      if (disabled || typeof onResize !== 'function' || event.button !== 0 || drag.current) return;
      event.preventDefault();
      event.stopPropagation();
      const node = event.currentTarget,
        startWidth = measure(),
        state = {
          node,
          pointerId: event.pointerId,
          startX: event.clientX,
          startWidth,
          columnKey,
          kind,
          resize: onResize,
          last: startWidth,
          cursor: document.body.style.cursor,
          userSelect: document.body.style.userSelect
        };
      function move(next) {
        if (next.pointerId !== state.pointerId || drag.current !== state) return;
        if (live.current.disabled || live.current.columnKey !== state.columnKey || live.current.kind !== state.kind) {
          finish(false);
          return;
        }
        next.preventDefault();
        const value = Math.max(56, Math.round(state.startWidth + next.clientX - state.startX));
        if (value !== state.last) {
          state.last = value;
          state.resize(value);
        }
      }
      function end(next) {
        if (next.pointerId === state.pointerId) finish(false);
      }
      function key(next) {
        if (next.key === 'Escape') {
          next.preventDefault();
          next.stopImmediatePropagation();
          finish(true);
        }
      }
      state.cleanup = () => {
        node.removeEventListener('pointermove', move);
        node.removeEventListener('pointerup', end);
        node.removeEventListener('pointercancel', end);
        node.removeEventListener('lostpointercapture', end);
        window.removeEventListener('keydown', key, true);
      };
      drag.current = state;
      setMoving(true);
      node.setPointerCapture(event.pointerId);
      document.body.style.cursor = 'col-resize';
      document.body.style.userSelect = 'none';
      node.addEventListener('pointermove', move);
      node.addEventListener('pointerup', end);
      node.addEventListener('pointercancel', end);
      node.addEventListener('lostpointercapture', end);
      window.addEventListener('keydown', key, true);
    }
    function keyboard(event) {
      if (disabled || typeof onResize !== 'function' || event.altKey || event.ctrlKey || event.metaKey) return;
      let next;
      if (event.key === 'Home') next = 56;else if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') next = measure() + (event.key === 'ArrowLeft' ? -1 : 1) * (event.shiftKey ? 32 : 8);else return;
      event.preventDefault();
      event.stopPropagation();
      onResize(Math.max(56, Math.round(next)));
    }
    return {
      currentWidth,
      moving,
      start,
      keyboard
    };
  }
  function ResourceTableHeader({
    column,
    kind,
    scope,
    adapter,
    sort,
    direction,
    sortActive,
    onSort,
    onFilter,
    filter = null,
    matchingCount,
    width,
    onResize,
    disabled = false,
    scopeTransform = M.toolbarScope,
    pageSize = 100
  }) {
    const holder = React.useRef(null),
      [opened, setOpened] = React.useState(null);
    const baseScope = scopeTransform(scope, column.key),
      scopeKey = M.signature(baseScope),
      identity = M.signature({
        kind,
        column: column.key,
        scope: baseScope
      });
    const resize = useResize({
      columnKey: column.key,
      kind,
      scopeKey,
      width,
      disabled,
      onResize
    }, holder);
    const sorted = !!sortActive && sort === column.key,
      next = !sorted ? 'asc' : direction === 'asc' ? 'desc' : null;
    let filtered;
    try {
      filtered = M.active(filter);
    } catch (_) {
      filtered = true;
    }
    function close(restore) {
      const owner = opened && opened.owner;
      setOpened(null);
      if (restore && owner) requestAnimationFrame(() => {
        if (owner.isConnected && !owner.disabled) owner.focus({
          preventScroll: true
        });
      });
    }
    React.useEffect(() => {
      setOpened(null);
    }, [identity, disabled]);
    const current = opened && opened.identity === identity && !disabled;
    return /*#__PURE__*/React.createElement("span", {
      ref: holder,
      className: "wb-resource-th",
      "data-column-key": column.key,
      "data-sort-direction": sorted ? direction : undefined,
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 3,
        minWidth: 0,
        width: '100%',
        position: 'relative',
        paddingRight: 5,
        boxSizing: 'border-box'
      }
    }, null, /*#__PURE__*/React.createElement("span", {
      className: "wb-th-sort-shell"
    }, /*#__PURE__*/React.createElement(Button, {
      className: "wb-th-sort",
      disabled: disabled || typeof onSort !== 'function',
      title: column.title + '：' + (next === 'asc' ? '升序' : next === 'desc' ? '降序' : '恢复默认顺序'),
      "aria-label": column.title + '排序',
      style: {
        justifyContent: column.numeric ? 'flex-end' : 'flex-start'
      },
      onClick: event => {
        event.stopPropagation();
        onSort(column.key, next);
      }
    }, /*#__PURE__*/React.createElement("span", {
      className: "wb-th-title"
    }, column.title), sorted && /*#__PURE__*/React.createElement("span", {
      className: "wb-th-sort-glyph",
      "aria-hidden": "true"
    }, /*#__PURE__*/React.createElement("span", {
      style: direction === 'asc' ? {
        transform: 'rotate(180deg)'
      } : undefined
    }, /*#__PURE__*/React.createElement(Icon, {
      name: "chevron-down"
    }))))), /*#__PURE__*/React.createElement(Button, {
      className: "wb-th-filter",
      icon: "search",
      disabled: disabled || typeof onFilter !== 'function',
      "aria-label": '筛选' + column.title,
      "aria-haspopup": "dialog",
      "aria-expanded": !!current,
      "aria-pressed": filtered,
      title: '筛选' + column.title + (filtered ? '（已筛选）' : ''),
      onClick: event => {
        event.stopPropagation();
        if (current) close(true);else setOpened({
          owner: event.currentTarget,
          identity
        });
      }
    }), /*#__PURE__*/React.createElement("span", {
      role: "separator",
      "aria-orientation": "vertical",
      "aria-label": '调整' + column.title + '列宽',
      "aria-valuemin": 56,
      "aria-valuenow": resize.currentWidth,
      "aria-valuetext": resize.currentWidth + ' 像素',
      "aria-disabled": disabled || typeof onResize !== 'function',
      tabIndex: disabled || typeof onResize !== 'function' ? -1 : 0,
      className: "wb-th-resize",
      "data-dragging": resize.moving || undefined,
      onPointerDown: resize.start,
      onKeyDown: resize.keyboard,
      onClick: event => event.stopPropagation()
    }), current && /*#__PURE__*/React.createElement(window.ResourceTableFilter, {
      key: identity,
      column,
      kind,
      adapter,
      filter,
      matchingCount,
      onFilter,
      scope,
      scopeTransform,
      pageSize,
      owner: opened.owner,
      onClose: close
    }));
  }
  window.ResourceTableHeader = ResourceTableHeader;
})();
