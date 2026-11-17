import React, { createPortal } from './shared/runtime/react.js';
import M from './ResourceTableFilterModel.js';
import { Button, ErrorBox } from './ResourceControls.jsx';
import { useQuery } from './shared/session/query.js';
import APSResourceAPI from './resource-api.js';
import APSProcessAPI from './ProcessAPI.js';
import CalibrationAPI from './CalibrationAPI.js';

function initialRule(value) {
  try { return { value: M.rule(value), error: null }; }
  catch (error) { return { value: M.rule(null), error }; }
}
// 列筛选取值的唯一数据源入口：按表格所属的领域选——零件工艺表、校准明细表，其余是基础资料列表。
function facetSource(kind) {
  return kind === 'part' ? APSProcessAPI : kind === 'calibration' ? CalibrationAPI : APSResourceAPI.forNamespace('resources');
}
function ResourceTableFilter({ column, kind, scope, filter, matchingCount, owner, onFilter, onClose, scopeTransform = M.toolbarScope, pageSize = 100 }) {
  const current = React.useMemo(() => initialRule(filter), [filter]), panel = React.useRef(null), search = React.useRef(null);
  const close = React.useRef(onClose); close.current = onClose;
  const [draftQuery, setDraftQuery] = React.useState('');
  const [request, setRequest] = React.useState({ query: '', page: 1, size: pageSize });
  const [version, setVersion] = React.useState(0);
  const [changeError, setChangeError] = React.useState(null);
  const [position, setPosition] = React.useState({ visibility: 'hidden' });
  const baseScope = scopeTransform(scope, column.key), scopeKey = M.signature(baseScope), id = React.useId(), portal = owner.closest('[role="dialog"]') || document.body;
  const queryText = request.query.trim();
  const facetQuery = { scope: baseScope, column: column.key, ...request, query: queryText };
  const facetRead = useQuery(signal => facetSource(kind).facets(kind, facetQuery, signal).then(raw => M.facets(raw, facetQuery)),
    [M.signature({ kind, column: column.key, scope: baseScope, request: { ...request, query: queryText }, version })]);
  const result = facetRead.result, data = result && result.data, loading = facetRead.loading, readError = facetRead.error;
  const normalized = current.value, selectedKeys = React.useMemo(() => new Set(normalized.values), [normalized]);
  const needed = !!queryText || normalized.values.length > 0;
  const snapshot = request.snapshot_ref || result && result.meta.snapshot_ref;
  // List filtering and paging cannot invalidate the menu's own facet snapshot or complete key set.
  // 全部匹配值只在用得上（needed）时读；同一个 keysKey 下改勾选让它暂时用不上再用上，是同一读取身份，沿用已读到的结果不重读。
  const keysKey = snapshot ? M.signature({ kind, column: column.key, scopeKey, query: queryText, snapshot, version }) : '';
  const keysQuery = { scope: baseScope, column: column.key, query: queryText, size: pageSize, snapshot_ref: snapshot };
  const keyRead = useQuery(signal => facetSource(kind).facetSelection(kind, keysQuery, signal)
    .then(raw => M.selection(raw, { ...keysQuery, expected_total: data ? data.page.total : undefined })), [keysKey], { enabled: !!keysKey && needed });
  const keyResult = keyRead.result, keyError = needed && keyRead.error, keyLoading = needed && keyRead.loading && !readError;
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
      // Only the anchor's own scroll ancestors can move it; scrolling an unrelated container keeps the popover open.
      if (!before) return;
      // A pre-open scroll can be delivered after mounting; the anchor has not moved since opening.
      if (target.scrollLeft === before[0] && target.scrollTop === before[1]) return;
      {
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
  function readFirst() { setRequest({ query: draftQuery, page: 1, size: pageSize }); setVersion(value => value + 1); }
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
  return createPortal(<section ref={panel} className="wb-resource-table-filter wb-control-popup wb-filter-pop" data-wb-table-filter="true"
    role="dialog" aria-modal="true" aria-labelledby={id} style={{ position: 'fixed', zIndex: 'var(--wb-z-popup)', ...position }}>
    <div className="wb-popup-header wb-filter-pop-head"><strong id={id}>筛选 · {column.title}</strong>
      <Button className="mini" icon="x" aria-label="关闭列筛选" onClick={() => close.current(true)} /></div>
    <div className="wb-filter-pop-search">
      <input ref={search} type="text" aria-label={'搜索' + column.title + '列值'} value={draftQuery} placeholder="搜索列值"
        onChange={event => setDraftQuery(event.target.value)} onKeyDown={event => {
          const nativeEvent = event.nativeEvent || event;
          if (event.key !== 'Enter' || event.isComposing || nativeEvent.isComposing || event.keyCode === 229 || nativeEvent.keyCode === 229) return;
          event.preventDefault(); event.stopPropagation(); readFirst();
        }} />
      <Button className="mini" icon="search" aria-label="搜索列值" onClick={readFirst} /></div>
    <div className="wb-filter-pop-all">
      <label><input type="checkbox" aria-label="全选" checked={group.all} disabled={blocked || !!keyError || !data || !data.page.total}
        ref={node => { if (node) node.indeterminate = group.mixed; }}
        onChange={event => selectAll(event.target.checked)} />（全选）</label>
      <span className="muted">{data ? data.page.total + ' 个值' : ''}</span></div>
    <ErrorBox error={current.error} /><ErrorBox error={readError} /><ErrorBox error={keyError} /><ErrorBox error={changeError} />
    {(readError || keyError) && <Button className="mini" icon="refresh-cw" onClick={readFirst}>回到第 1 页重新查询</Button>}
    {keyLoading && <span role="status" className="muted">正在读取全部匹配值…</span>}
    <div className="wb-table-facet-options wb-filter-pop-options" role="group" aria-label={column.title + '列值'} aria-busy={loading || keyLoading}>
      {loading && <p role="status">正在读取列值…</p>}
      {data && !data.options.length && <p role="status">{queryText ? '没有匹配的列值' : '当前范围没有列值'}</p>}
      {data && data.options.map(option => <label key={option.key} data-facet-key={option.key} className="wb-table-facet-option wb-filter-pop-option">
        <input type="checkbox" aria-label={option.label === '' ? '（空白）' : option.label} checked={(normalized.mode === 'include') === selectedKeys.has(option.key)} disabled={blocked}
          onChange={event => { const checked = event.target.checked; commitChange(() => M.toggle(filter, option.key, checked)); }} />
        <span className="wb-filter-pop-option-label">{option.label === '' ? '（空白）' : option.label}</span>
        <span className="muted wb-filter-pop-option-count">{option.count}</span></label>)}
    </div>
    {[result, needed && keyResult].filter(Boolean).map((item, group) => item.warnings.length > 0 && <div key={group} role="status" className="wb-filter-pop-warnings">{item.warnings.map((warning, index) => <div key={index}>{warning.message}</div>)}</div>)}
    <div className="wb-filter-pop-pager">
      <span className="muted wb-filter-pop-pager-note">{data ? '列值分页' : '列值尚未读取'}</span>
      <Button className="mini" icon="chevron-left" aria-label="列值上一页" disabled={!data || data.page.number <= 1} onClick={() => changePage(data.page.number - 1)} />
      <span aria-label="列值页码">{data ? data.page.number + '/' + data.page.pages : '—'}</span>
      <Button className="mini" icon="chevron-right" aria-label="列值下一页" disabled={!data || data.page.number >= data.page.pages} onClick={() => changePage(data.page.number + 1)} /></div>
    <div className="wb-popup-footer wb-filter-pop-foot">
      <span className="muted" role="status">{Number.isSafeInteger(matchingCount) && matchingCount >= 0 ? matchingCount + ' 行匹配' : '匹配行数未读取'}</span>
      <Button className="mini" onClick={() => commitChange(() => null, true)}>清除</Button></div>
  </section>, portal);
}

export { ResourceTableFilter };
export default ResourceTableFilter;
