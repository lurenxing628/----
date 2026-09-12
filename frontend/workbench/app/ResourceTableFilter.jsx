(function () {
  'use strict';
  const M = window.ResourceTableFilterModel, C = window.APSResourceContract;
  const { Button, ErrorBox } = window.ResourceControls;
  function initialRule(value) {
    try { return { value: M.rule(value), error: null }; }
    catch (error) { return { value: M.rule(null), error }; }
  }
  function ResourceTableFilter({ column, kind, scope, adapter, filter, matchingCount, owner, onFilter, onClose, scopeTransform = M.toolbarScope, pageSize = 100 }) {
    const current = React.useMemo(() => initialRule(filter), [filter]), panel = React.useRef(null), search = React.useRef(null), service = React.useRef(adapter);
    service.current = adapter;
    const close = React.useRef(onClose); close.current = onClose;
    const [request, setRequest] = React.useState({ query: '', page: 1, size: pageSize });
    const [version, setVersion] = React.useState(0), [reading, setReading] = React.useState({ loading: true, result: null, error: null });
    const [keysState, setKeysState] = React.useState({}), cache = React.useRef(null);
    const [changeError, setChangeError] = React.useState(null);
    const [position, setPosition] = React.useState({ visibility: 'hidden' });
    const baseScope = scopeTransform(scope, column.key), scopeKey = M.signature(baseScope), id = React.useId(), portal = owner.closest('[role="dialog"]') || document.body;
    const queryText = request.query.trim();
    const requestKey = M.signature({ kind, column: column.key, scope: baseScope, request: { ...request, query: queryText }, version });
    React.useEffect(() => {
      const controller = new AbortController(); let live = true;
      const query = { scope: baseScope, column: column.key, ...request, query: queryText };
      setReading({ key: requestKey, loading: true, result: null, error: null });
      Promise.resolve().then(() => {
        if (typeof service.current.facets !== 'function') throw C.failure('列值读取接口尚未接入。');
        return service.current.facets(kind, query, controller.signal);
      }).then(raw => {
        if (live && !controller.signal.aborted) setReading({ key: requestKey, loading: false, result: M.facets(raw, query), error: null });
      }).catch(error => { if (live && !controller.signal.aborted) setReading({ key: requestKey, loading: false, result: null, error }); });
      return () => { live = false; controller.abort(); };
    }, [requestKey]);
    const validReading = reading.key === requestKey, result = validReading && reading.result, data = result && result.data;
    const loading = !validReading || reading.loading, readError = validReading && reading.error;
    const normalized = current.value, selectedKeys = React.useMemo(() => new Set(normalized.values), [normalized]);
    const needed = !!queryText || normalized.values.length > 0;
    const snapshot = request.snapshot_ref || result && result.meta.snapshot_ref;
    // List filtering and paging cannot invalidate the menu's own facet snapshot or complete key set.
    const keysKey = snapshot ? M.signature({ kind, column: column.key, scopeKey, query: queryText, snapshot, version }) : '';
    React.useEffect(() => {
      if (!keysKey || !needed) return;
      if (cache.current && cache.current.key === keysKey) { setKeysState(cache.current); return; }
      const controller = new AbortController(); let live = true;
      const query = { scope: baseScope, column: column.key, query: queryText, size: pageSize, snapshot_ref: snapshot };
      setKeysState({ key: keysKey, loading: true });
      Promise.resolve().then(() => {
        if (typeof service.current.facetSelection !== 'function') throw C.failure('全部匹配值接口尚未接入，未改变筛选。');
        return service.current.facetSelection(kind, query, controller.signal);
      }).then(raw => {
        if (!live || controller.signal.aborted) return;
        const result = M.selection(raw, { ...query, expected_total: data ? data.page.total : undefined }), state = { key: keysKey, loading: false, result };
        cache.current = state; setKeysState(state);
      }).catch(error => { if (live && !controller.signal.aborted) setKeysState({ key: keysKey, loading: false, error }); });
      return () => { live = false; controller.abort(); };
    }, [keysKey, needed]);
    const keyResult = keysState.key === keysKey && keysState.result, keyError = needed && keysState.key === keysKey && keysState.error;
    const keyLoading = needed && !!keysKey && !readError && (keysState.key !== keysKey || keysState.loading);
    const group = React.useMemo(() => keyResult ? M.groupState(normalized, keyResult.data.keys) : { all: !needed && normalized.mode === 'exclude' && !!data && data.page.total > 0, mixed: false }, [keyResult, normalized, needed, data && data.page.total]);
    const blocked = loading || !!readError || !!current.error || keyLoading;
    React.useLayoutEffect(() => {
      const scrollPositions = new Map();
      for (let node = owner; node; node = node.parentElement) scrollPositions.set(node, [node.scrollLeft, node.scrollTop]);
      const anchors = Array.from(scrollPositions.keys()).map(node => {
        const value = node.style.getPropertyValue('overflow-anchor'), priority = node.style.getPropertyPriority('overflow-anchor');
        node.style.setProperty('overflow-anchor', 'none', 'important');
        return { node, value, priority };
      });
      function place() {
        if (!owner.isConnected || owner.disabled || !owner.getClientRects().length) { close.current(false); return; }
        const rect = owner.getBoundingClientRect(), width = Math.min(300, innerWidth - 16);
        const below = innerHeight - rect.bottom - 12, above = rect.top - 12, down = below >= 440 || below >= above;
        const height = Math.min(440, Math.max(0, down ? below : above));
        setPosition({ visibility: 'visible', width, height, maxHeight: innerHeight - 16,
          left: Math.max(8, Math.min(rect.left, innerWidth - width - 8)), top: down ? rect.bottom + 4 : Math.max(8, rect.top - height - 4) });
      }
      function outside(event) { if (!panel.current.contains(event.target) && !owner.contains(event.target)) close.current(false); }
      function scroll(event) {
        if (panel.current.contains(event.target)) return;
        const target = event.target === document ? document.scrollingElement : event.target;
        const before = scrollPositions.get(target);
        // A pre-open scroll can be delivered after mounting; the anchor has not moved since opening.
        if (before && target.scrollLeft === before[0] && target.scrollTop === before[1]) return;
        if (before) {
          const left = Math.min(before[0], Math.max(0, target.scrollWidth - target.clientWidth));
          const top = Math.min(before[1], Math.max(0, target.scrollHeight - target.clientHeight));
          const clamped = left < before[0] - 1 || top < before[1] - 1;
          // Loading or empty rows can shorten the list and force the browser to clamp its scroll offset.
          if (clamped && Math.abs(target.scrollLeft - left) <= 1 && Math.abs(target.scrollTop - top) <= 1) {
            scrollPositions.set(target, [target.scrollLeft, target.scrollTop]);
            place();
            return;
          }
        }
        close.current(false);
      }
      function keys(event) {
        if (event.key === 'Escape') { event.preventDefault(); event.stopImmediatePropagation(); close.current(true); return; }
        if (event.key !== 'Tab' || !panel.current.contains(event.target)) return;
        event.stopPropagation();
        const items = Array.from(panel.current.querySelectorAll('button:not(:disabled),input:not(:disabled),[tabindex="0"]')).filter(item => item.getClientRects().length);
        const first = items[0], last = items[items.length - 1];
        if (event.shiftKey && event.target === first || !event.shiftKey && event.target === last) {
          event.preventDefault(); (event.shiftKey ? last : first).focus();
        }
      }
      function focus(event) { if (!panel.current.contains(event.target) && event.target !== owner) close.current(false); }
      place(); search.current.focus({ preventScroll: true });
      // Follow list reflow without letting browser scroll anchoring move the open menu's context.
      const observer = new ResizeObserver(place); anchors.forEach(({ node }) => observer.observe(node));
      window.addEventListener('resize', place); window.addEventListener('keydown', keys, true);
      document.addEventListener('pointerdown', outside, true); document.addEventListener('scroll', scroll, true); document.addEventListener('focusin', focus);
      return () => {
        observer.disconnect(); window.removeEventListener('resize', place); window.removeEventListener('keydown', keys, true);
        anchors.forEach(({ node, value, priority }) => node.style.setProperty('overflow-anchor', value, priority));
        document.removeEventListener('pointerdown', outside, true); document.removeEventListener('scroll', scroll, true); document.removeEventListener('focusin', focus);
      };
    }, [owner]);
    function readFirst() { cache.current = null; setRequest({ query: request.query, page: 1, size: pageSize }); setVersion(value => value + 1); }
    function changePage(number) { setRequest({ ...request, page: number, snapshot_ref: result.meta.snapshot_ref }); }
    function commitChange(makeRule, dismiss) {
      try {
        const next = makeRule(); onFilter(next); setChangeError(null);
        if (dismiss) close.current(true);
      } catch (error) { setChangeError(error); }
    }
    function selectAll(enabled) {
      if (blocked || keyError || !data || !data.page.total) return;
      if (!queryText) commitChange(() => ({ mode: enabled ? 'exclude' : 'include', values: [] }));
      else if (keyResult) commitChange(() => M.toggleKeys(filter, keyResult.data.keys, enabled));
    }
    return ReactDOM.createPortal(<section ref={panel} className="wb-resource-table-filter wb-control-popup" data-wb-table-filter="true"
      role="dialog" aria-modal="true" aria-labelledby={id} style={{ position: 'fixed', zIndex: 'var(--wb-z-popup)', padding: 8, display: 'flex', flexDirection: 'column', gap: 6, boxSizing: 'border-box', overflow: 'auto', ...position }}>
      <div className="wb-popup-header" style={{ margin: 0, padding: '0 0 6px' }}><strong id={id} style={{ overflowWrap: 'anywhere' }}>筛选 · {column.title}</strong>
        <Button className="mini" icon="x" aria-label="关闭列筛选" onClick={() => close.current(true)} /></div>
      <div style={{ display: 'flex', gap: 6, flex: 'none', minWidth: 0 }}>
        <input ref={search} type="text" aria-label={'搜索' + column.title + '列值'} value={request.query} placeholder="搜索列值" style={{ flex: '1 1 auto', width: 0 }}
          onChange={event => setRequest({ query: event.target.value, page: 1, size: pageSize })} onKeyDown={event => { if (event.key === 'Enter') { event.preventDefault(); event.stopPropagation(); } }} />
        <Button className="mini" icon="search" aria-label="搜索列值" onClick={readFirst} /></div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 'none', flexWrap: 'wrap' }}>
        <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}><input type="checkbox" aria-label="全选" checked={group.all} disabled={blocked || !!keyError || !data || !data.page.total}
          ref={node => { if (node) node.indeterminate = group.mixed; }}
          onChange={event => selectAll(event.target.checked)} />（全选）</label>
        <span className="muted">{data ? data.page.total + ' 个值' : ''}</span></div>
      <ErrorBox error={current.error} /><ErrorBox error={readError} /><ErrorBox error={keyError} /><ErrorBox error={changeError} />
      {(readError || keyError) && <Button className="mini" icon="refresh-cw" onClick={readFirst}>回到首页重新读取</Button>}
      {keyLoading && <span role="status" className="muted">正在读取全部匹配值…</span>}
      <div className="wb-table-facet-options" role="group" aria-label={column.title + '列值'} aria-busy={loading || keyLoading} style={{ overflowY: 'auto', minHeight: 40, flex: '1 1 auto', borderTop: '1px solid var(--ui-border)', borderBottom: '1px solid var(--ui-border)' }}>
        {loading && <p role="status">正在读取列值…</p>}
        {data && !data.options.length && <p role="status">{queryText ? '没有匹配的列值' : '当前范围没有列值'}</p>}
        {data && data.options.map(option => <label key={option.key} data-facet-key={option.key} className="wb-table-facet-option" style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '6px 4px', minHeight: 30, cursor: 'pointer' }}>
          <input type="checkbox" aria-label={option.label === '' ? '（空白）' : option.label} checked={(normalized.mode === 'include') === selectedKeys.has(option.key)} disabled={blocked}
            style={{ marginTop: 2, flex: 'none' }} onChange={event => { const checked = event.target.checked; commitChange(() => M.toggle(filter, option.key, checked)); }} />
          <span style={{ minWidth: 0, flex: '1 1 auto', whiteSpace: 'normal', overflowWrap: 'anywhere', lineHeight: '20px' }}>{option.label === '' ? '（空白）' : option.label}</span>
          <span className="muted" style={{ flex: 'none', fontVariantNumeric: 'tabular-nums' }}>{option.count}</span></label>)}
      </div>
      {[result, needed && keyResult].filter(Boolean).map((item, group) => item.warnings.length > 0 && <div key={group} role="status" style={{ overflowWrap: 'anywhere' }}>{item.warnings.map((warning, index) => <div key={index}>{warning.message}</div>)}</div>)}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, flex: 'none', minHeight: 30 }}>
        <span className="muted" style={{ flex: 1 }}>{data ? '列值分页' : '列值尚未读取'}</span>
        <Button className="mini" icon="chevron-left" aria-label="列值上一页" disabled={!data || data.page.number <= 1} onClick={() => changePage(data.page.number - 1)} />
        <span aria-label="列值页码">{data ? data.page.number + '/' + data.page.pages : '—'}</span>
        <Button className="mini" icon="chevron-right" aria-label="列值下一页" disabled={!data || data.page.number >= data.page.pages} onClick={() => changePage(data.page.number + 1)} /></div>
      <div className="wb-popup-footer" style={{ margin: 0, padding: '6px 0 0', justifyContent: 'space-between', alignItems: 'center' }}>
        <span className="muted" role="status">{Number.isSafeInteger(matchingCount) && matchingCount >= 0 ? matchingCount + ' 行匹配' : '匹配行数待读取'}</span>
        <Button className="mini" onClick={() => commitChange(() => null, true)}>清除</Button></div>
    </section>, portal);
  }
  window.ResourceTableFilter = ResourceTableFilter;
})();
