(function () {
  'use strict';
  function Workspace({ initialContext = {}, onNavigate, adapter }) {
    const A = window.CalibrationAPI, C = window.CalibrationControls;
    const { Button, ErrorBox, useRead } = C;
    const api = React.useMemo(() => adapter || A.create(), [adapter]);
    const partAdapter = React.useMemo(() => ({ detail: (...args) => window.APSProcessAPI.create().detail(...args) }), []);
    const [part, setPart] = React.useState(null);
    const [input, setInput] = React.useState(() => A.initial(initialContext));
    const [widths, setWidths] = React.useState(initialContext.table_widths || {});
    const [selected, setSelected] = React.useState(initialContext.selected || null), [sampleRef, setSample] = React.useState(initialContext.sample_ref || null);
    const [revision, refresh] = React.useReducer(value => value + 1, 0), [format, setFormat] = React.useState('csv');
    const [notice, setNotice] = React.useState(''), [error, setError] = React.useState(null), [downloading, setDownloading] = React.useState(false);
    const [stale, setStale] = React.useState(false), downloadAbort = React.useRef(null);
    const identity = JSON.stringify(input) + ':' + revision;
    const request = useRead(signal => A.readView(api, input, signal), identity, api);
    const result = request.result, data = result && result.data;
    const bound = { ...input, snapshot_ref: result ? result.meta.snapshot_ref : input.snapshot_ref };
    const detail = useRead(async signal => A.validate(await api.detail(selected, bound, signal), bound, selected),
      selected + ':' + JSON.stringify(bound) + ':' + revision, api, !!(selected && result && data.capabilities.view === true && !stale));
    const isStale = failure => failure && failure.error && ['snapshot_stale', 'calibration_source_changed'].includes(failure.error.code);
    window.WorkbenchPageContext.useSnapshot(data ? {
      scope: Object.fromEntries(Object.entries(input).filter(([key]) => !['page', 'size', 'sort', 'direction', 'snapshot_ref'].includes(key))),
      table: { page: input.page, size: input.size, sort: input.sort, direction: input.direction },
      selected, sample_ref: sampleRef, table_widths: widths
    } : null, !!data && !request.busy && !request.error && !stale && (!selected || !!detail.result && !detail.busy && !detail.error));
    React.useEffect(() => { if (isStale(request.error) || isStale(detail.error)) setStale(true); }, [request.error, detail.error]);
    React.useEffect(() => () => { if (downloadAbort.current) downloadAbort.current.abort(); }, [api]);
    function reload() {
      if (downloadAbort.current) downloadAbort.current.abort();
      setInput(old => ({ ...old, snapshot_ref: undefined })); setError(null); setNotice(''); setStale(false); refresh();
    }
    function change(patch) {
      setInput(old => A.input({ ...old, ...patch, page: 1, snapshot_ref: undefined }));
      setSelected(null); setSample(null); setError(null); setNotice('');
    }
    function page(patch) {
      if (patch.size !== undefined) return change(patch);
      setInput(old => A.input({ ...old, ...patch, snapshot_ref: result.meta.snapshot_ref })); setNotice('');
    }
    async function download() {
      const controller = new AbortController(); downloadAbort.current = controller;
      setDownloading(true); setNotice(''); setError(null);
      try {
        const receipt = await api.download(result, bound, format, controller.signal);
        if (!controller.signal.aborted) {
          if (!receipt || receipt.rows !== data.summary.total || receipt.snapshot_ref !== result.meta.snapshot_ref) throw A.failure('导出结果未核实，未报告成功。');
          setNotice('已核对快照和数量，导出全部筛选 ' + receipt.rows + ' 项。');
        }
      } catch (failure) { if (!controller.signal.aborted) { setError(failure); if (isStale(failure)) setStale(true); } }
      finally { if (downloadAbort.current === controller) { downloadAbort.current = null; setDownloading(false); } }
    }
    const disabled = request.busy || downloading || stale;
    const viewError = selected && data && data.capabilities.view !== true ? A.failure('查看权限尚未确认，暂不能读取样本来源。') : null;
    return <section className="calib-workbench calibration-live" aria-label="工时定额校准" data-ready={!!data} data-source="production" data-stale={stale}>
      <C.Styles /><header className="ca-heading"><div><h2>工时定额校准</h2><p className="ca-muted">模板定额与实际加工记录{result ? ' · 数据截至 ' + result.meta.as_of.replace('T', ' ') : ''}</p></div>
        <div className="ca-actions"><Button icon="refresh-cw" aria-label="刷新校准数据" busy={request.busy} disabled={downloading} onClick={reload} />
          {window.CalibrationAdoptionAction && <window.CalibrationAdoptionAction detail={detail.result && detail.result.data} stale={stale || detail.busy} onRefresh={reload} />}
          {typeof onNavigate === 'function' && <Button icon="arrow-right" disabled={!data || disabled} onClick={() => onNavigate('review', { returnTo: { view: 'calib', context: {
            scope: Object.fromEntries(Object.entries(input).filter(([key]) => !['page', 'size', 'sort', 'direction', 'snapshot_ref'].includes(key))),
            table: { page: input.page, size: input.size, sort: input.sort, direction: input.direction }, selected, sample_ref: sampleRef, table_widths: widths } } })}>执行复盘</Button>}</div></header>
      <C.Filters value={input} onChange={change} disabled={disabled} />
      {input.part_ref && <p className="ca-muted">已限定零件来源 <Button icon="x" aria-label="清除零件限定" disabled={disabled} onClick={() => change({ part_ref: null })} /></p>}
      <ErrorBox error={request.error || error} />
      {stale && <p className="ca-note" role="alert">前后快照不一致，请明确刷新。已选记录和样本来源保留，不会自动跳到最新记录。</p>}
      {(stale || request.error) && <Button icon="refresh-cw" disabled={downloading} onClick={reload}>明确刷新</Button>}
      {request.busy && <p role="status">正在读取校准记录...</p>}{notice && <p role="status">{notice}</p>}
      {data && <><div className="ca-metrics">{[['模板工序', 'total'], ['偏差 > 20%', 'over_20_percent'], ['已有建议', 'suggested'], ['数据不足', 'insufficient_data']].map(([label, key]) =>
        <div className="ca-metric" key={key}><span>{label}</span><strong>{data.summary[key]}</strong></div>)}</div>
        {data.source_constraints.map(item => <p className="ca-note" key={item.code}>{item.message}</p>)}
        <div className="ca-tools"><h3>校准明细</h3><label>排序<select aria-label="排序字段" disabled={disabled} value={input.sort} onChange={event => change({ sort: event.target.value })}>
          {Object.entries(A.sorts).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
          <label>顺序<select aria-label="排序方向" disabled={disabled} value={input.direction} onChange={event => change({ direction: event.target.value })}><option value="asc">升序</option><option value="desc">降序</option></select></label>
          <div className="ca-actions" style={{ marginLeft: 'auto' }}><label>格式<select aria-label="导出格式" value={format} disabled={disabled} onChange={event => setFormat(event.target.value)}><option value="csv">CSV</option><option value="xlsx">XLSX</option></select></label>
            <Button transfer="export" busy={downloading} disabled={disabled} reason={A.exportReason(data, format)} onClick={download}>导出全部筛选</Button></div></div>
        <C.Table rows={data.items} selected={selected} disabled={disabled} canView={data.capabilities.view === true} onPart={setPart} onSelect={value => { setSelected(value); setSample(null); }}
          scope={bound} adapter={api} widths={widths} total={data.summary.total} onResize={(key, value) => setWidths(old => ({ ...old, [key]: value }))}
          onSort={(sort, direction) => change({ sort: direction ? sort : 'part_no', direction: direction || 'asc' })}
          onFilter={(key, rule) => { const filters = { ...input.column_filters }; if (rule === null) delete filters[key]; else filters[key] = rule; change({ column_filters: filters }); }} />
        <C.Page page={data.page} onChange={page} disabled={disabled} />
        {data.capabilities.export !== true && <p className="ca-note">导出权限尚未确认，暂不能导出。</p>}
        <p className="ca-muted">{C.writeReason}</p>
      </>}
      {selected && <window.CalibrationDetail result={detail.result} busy={detail.busy} error={detail.error || viewError} stale={stale} selected={selected} sampleRef={sampleRef} onSample={setSample}
        onClose={() => { setSelected(null); setSample(null); }} onRefresh={reload} />}
      {part && <window.ProcessDetail adapter={partAdapter} partRef={part.part_ref} initialStage="hours" templateOperationRef={part.template_operation_ref}
        navigationReadOnly disabled onClose={() => setPart(null)} />}
    </section>;
  }
  function CalibrationWorkspace(props) {
    window.WorkbenchCaption.useCaption(null);
    try { window.CalibrationAPI.initial(props.initialContext || {}); }
    catch (error) { return <section className="calibration-live"><window.CalibrationControls.Styles /><h2>工时定额校准</h2><window.ResourceControls.ErrorBox error={error} /></section>; }
    return <Workspace key={JSON.stringify(props.initialContext || {})} {...props} />;
  }
  window.CalibrationWorkspace = CalibrationWorkspace;
})();
