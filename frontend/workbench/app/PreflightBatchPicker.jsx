(function () {
  'use strict';
  const C = window.PreflightContract, { Button, ErrorBox } = window.PreflightControls;
  const baseScope = () => ({ query: '', page: 1, size: 20, sort: 'business_code', direction: 'asc', column_filters: { status: ['pending', 'scheduled', 'processing'] } });
  function PreflightBatchPicker({ adapter, selected, onChange, disabled }) {
    const [scope, setScope] = React.useState(baseScope), [query, setQuery] = React.useState('');
    const [result, setResult] = React.useState(null), [error, setError] = React.useState(null), [loading, setLoading] = React.useState(true), [selecting, setSelecting] = React.useState(false);
    const serial = React.useRef(0), selectionController = React.useRef(null);
    React.useEffect(() => {
      let alive = true; const controller = new AbortController();
      setLoading(true); setResult(null); setError(null);
      adapter.list(scope, controller.signal).then(value => { if (alive) setResult(value); }, problem => { if (alive) setError(problem); }).finally(() => { if (alive) setLoading(false); });
      return () => { alive = false; controller.abort(); };
    }, [adapter, scope]);
    React.useEffect(() => () => { serial.current++; if (selectionController.current) selectionController.current.abort(); }, []);
    const data = result && result.data, snapshot = result && result.meta.snapshot_ref, chosen = new Set(selected);
    const busy = disabled || loading || selecting;
    function filter(patch) { setScope(old => ({ ...old, ...patch, page: 1, snapshot_ref: undefined })); }
    function toggle(ref) {
      if (busy) return;
      const next = chosen.has(ref) ? selected.filter(item => item !== ref) : selected.concat(ref);
      if (!C.refs(next)) { setError(C.fail('最多选择5000个批次，请先缩小范围。')); return; }
      onChange(next);
    }
    async function select(mode) {
      if (busy || mode === 'filtered' && !snapshot) return;
      const id = ++serial.current, controller = new AbortController(); selectionController.current = controller;
      setSelecting(true); setError(null);
      try {
        let requestScope = { ...scope, snapshot_ref: snapshot };
        if (mode !== 'filtered') {
          const next = { ...baseScope(), ...(mode === 'ready' ? { ready_status: 'yes' } : {}) };
          const listed = await adapter.list(next, controller.signal);
          requestScope = { ...next, snapshot_ref: listed.meta.snapshot_ref };
        }
        const result = await adapter.selection(requestScope, controller.signal), refs = C.selection(result, requestScope.snapshot_ref);
        if (id === serial.current) onChange(refs);
      } catch (problem) { if (id === serial.current) setError(problem); }
      finally { if (id === serial.current) setSelecting(false); }
    }
    const visible = data ? data.entities : [], hidden = selected.filter(ref => !visible.some(row => row.ref === ref)).length;
    return <section className="pf-picker" aria-label="选择排产批次">
      <form className="pf-tools" onSubmit={event => { event.preventDefault(); if (!busy) filter({ query }); }}>
        <input type="search" aria-label="搜索排产批次" placeholder="批次号、图号、零件名" value={query} disabled={busy} onChange={event => setQuery(event.target.value)} />
        <Button icon="search" type="submit" disabled={busy}>搜索</Button>
        <label>齐套<select aria-label="批次齐套筛选" disabled={busy} value={scope.ready_status || ''} onChange={event => filter({ ready_status: event.target.value || undefined })}>
          <option value="">全部</option><option value="yes">已齐套</option><option value="partial">部分齐套</option><option value="no">未齐套</option>
        </select></label><Button icon="refresh-cw" aria-label="刷新批次范围" disabled={busy} onClick={() => filter({})} />
      </form>
      <div className="pf-tools"><Button disabled={busy} onClick={() => select('all')}>全部待排</Button><Button disabled={busy} onClick={() => select('ready')}>仅已齐套</Button>
        <Button disabled={busy || !snapshot} onClick={() => select('filtered')}>全选当前筛选</Button><Button icon="x" disabled={disabled || selecting || !selected.length} onClick={() => onChange([])}>清空选择</Button>
        <span aria-live="polite">已选 {selected.length} 批{hidden > 0 ? ' · 含非当前页 ' + hidden + ' 批' : ''}</span></div>
      <ErrorBox error={error} />{error && <Button icon="refresh-cw" disabled={disabled || loading || selecting} onClick={() => filter({})}>重读批次</Button>}
      {loading || selecting ? <p role="status">{selecting ? '正在核对全部选择范围…' : '正在读取批次…'}</p> : data && !visible.length ? <p role="status">当前筛选没有待排批次。</p> : null}
      {!loading && data && <div className="pf-picker-list">{visible.map(row => <label className="pf-picker-row" key={row.ref}>
        <input type="checkbox" aria-label={'选择 ' + row.business_code} checked={chosen.has(row.ref)} disabled={busy} onChange={() => toggle(row.ref)} />
        <strong>{row.business_code}</strong><span>{row.relationships.part_no} · {row.label}</span><span>{row.relationships.operation_count} 道工序</span>
        <span>{window.APSBatchContract.label('ready_status', row.fields.ready_status)}</span>
      </label>)}</div>}
      {data && <div className="pf-tools"><span>共 {data.page.total} 批 · 第 {data.page.number} / {data.page.pages} 页</span>
        <label>每页<select aria-label="批次每页条数" value={scope.size} disabled={busy} onChange={event => filter({ size: Number(event.target.value) })}>{[20, 50, 100].map(size => <option key={size} value={size}>{size}</option>)}</select></label>
        <Button icon="chevron-left" aria-label="批次上一页" disabled={busy || data.page.number <= 1} onClick={() => setScope(old => ({ ...old, page: old.page - 1, snapshot_ref: snapshot }))} />
        <Button icon="chevron-right" aria-label="批次下一页" disabled={busy || data.page.number >= data.page.pages} onClick={() => setScope(old => ({ ...old, page: old.page + 1, snapshot_ref: snapshot }))} />
      </div>}
    </section>;
  }
  window.PreflightBatchPicker = PreflightBatchPicker;
})();
