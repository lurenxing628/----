(function () {
  'use strict';
  const { Button, ErrorBox } = window.ResourceControls;
  const titles = { empty: '暂无记录', filtered: '当前筛选没有匹配项', loading: '正在读取…', error: '读取未完成' };
  function EmptyState({ kind = 'empty', title, hint, action, error }) {
    if (!Object.prototype.hasOwnProperty.call(titles, kind)) throw new TypeError('Unknown empty state kind');
    if ((kind === 'filtered' || kind === 'error') && !action) throw new TypeError(kind + ' state requires a recovery action');
    return <div className={'wb-empty wb-empty-' + kind} role={kind === 'error' ? undefined : 'status'} aria-busy={kind === 'loading' || undefined}>
      <p className="wb-empty-title">{title || titles[kind]}</p>
      {hint && <p className="wb-empty-hint">{hint}</p>}
      {kind === 'error' && error && <ErrorBox error={error} />}
      {action && <div className="wb-empty-action">{action}</div>}</div>;
  }
  function Pager({ page = 1, pages, total, size, sizes, unit = '项', onPage, onSize, disabled, busy, label = '记录', sizeLabel,
    mode = 'pages', hasPrevious, hasNext, onPrevious, onNext, showPageSelect = false, showPageJump = false, jumpLabel = '跳转页码', jumpActionLabel = '跳转' }) {
    const data = page && typeof page === 'object' ? page : { number: page, pages, total, size };
    const number = data.number || 1, count = data.total == null ? total : data.total, perPage = data.size || size;
    const pageCount = data.pages || pages || (Number.isFinite(count) && perPage ? Math.max(1, Math.ceil(count / perPage)) : undefined);
    const [jump, setJump] = React.useState(String(number)), [jumpError, setJumpError] = React.useState(false);
    const jumpErrorId = React.useId();
    React.useEffect(() => { setJump(String(number)); setJumpError(false); }, [number]);
    if (!['pages', 'cursor'].includes(mode)) throw new TypeError('Unknown pager mode');
    if (onSize && (!Array.isArray(sizes) || !sizes.length || !sizes.every(value => Number.isSafeInteger(value) && value > 0))) {
      throw new TypeError('Pager sizes must explicitly match the domain API');
    }
    const locked = disabled || busy;
    const previous = mode === 'cursor' ? !!hasPrevious : number > 1;
    const next = mode === 'cursor' ? !!hasNext : pageCount != null ? number < pageCount : !!hasNext;
    const previousAction = onPrevious || (onPage && (() => onPage(number - 1)));
    const nextAction = onNext || (onPage && (() => onPage(number + 1)));
    function goToPage() {
      const target = Number(jump);
      if (!/^\d+$/.test(jump) || !Number.isSafeInteger(target) || target < 1 || target > pageCount) { setJumpError(true); return; }
      setJumpError(false); onPage(target);
    }
    return <nav className="wb-pager" aria-label={label + '分页'} aria-busy={busy || undefined}>
      <span className="wb-pager-summary">{mode === 'cursor' ? '按读取顺序翻页' : <>{count != null && <>共 {count} {unit} · </>}第 {number}{pageCount != null && <> / {pageCount}</>} 页</>}</span>
      <div className="wb-pager-actions">
        {mode === 'pages' && showPageSelect && pageCount && onPage && <label className="wb-pager-size">页码<select aria-label={label + '页码'} value={number} disabled={locked} onChange={event => onPage(Number(event.target.value))}>
          {Array.from({ length: pageCount }, (_, index) => index + 1).map(value => <option key={value} value={value}>{value}</option>)}</select></label>}
        {mode === 'pages' && showPageJump && pageCount && onPage && <div className="wb-pager-jump">
          <input type="number" aria-label={jumpLabel} aria-invalid={jumpError || undefined} aria-describedby={jumpError ? jumpErrorId : undefined} min={1} max={pageCount} step={1} value={jump} disabled={locked}
            onChange={event => { setJump(event.target.value); setJumpError(false); }} onKeyDown={event => { if (event.key === 'Enter') { event.preventDefault(); goToPage(); } }} />
          <Button aria-label={jumpActionLabel} disabled={locked} onClick={goToPage}>跳转</Button>
          {jumpError && <span id={jumpErrorId} role="status" className="wb-field-error">请输入 1 到 {pageCount} 之间的页码。</span>}</div>}
        {onSize && <label className="wb-pager-size">每页<select aria-label={sizeLabel || label + '每页条数'} value={perPage} disabled={locked} onChange={event => onSize(Number(event.target.value))}>
          {!sizes.includes(perPage) && <option value={perPage} disabled>{perPage} {unit}（当前）</option>}
          {sizes.map(value => <option key={value} value={value}>{value} {unit}</option>)}</select></label>}
        <Button icon="chevron-left" aria-label={label + '上一页'} disabled={locked || !previous || !previousAction} onClick={previousAction}>上一页</Button>
        <Button icon="chevron-right" aria-label={label + '下一页'} disabled={locked || !next || !nextAction} onClick={nextAction}>下一页</Button>
      </div></nav>;
  }
  window.WorkbenchListControls = { EmptyState, Pager };
  Object.assign(window.WorkbenchControls, window.WorkbenchListControls);
})();
