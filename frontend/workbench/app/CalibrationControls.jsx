(function () {
  'use strict';
  const { Button, Icon, ErrorBox } = window.ResourceControls;
  const text = (value, missing = '未知') => value === null || value === undefined ? missing : String(value);
  const hours = (value, missing = '未提供') => value === null ? missing : text(value) + ' h';
  const source = value => ({ internal: '自制', external: '外协', unknown: '未确认' })[value] || '未确认';
  const writeReason = '采用与锁定须经独立真实预览核实；仅影响未来模板使用，不改已有批次、历史计划和执行。';
  function useRead(load, identity, adapter, enabled = true) {
    const [state, setState] = React.useState({ result: null, error: null, busy: true, identity });
    React.useEffect(() => {
      const controller = new AbortController(); let active = true;
      setState({ result: null, error: null, busy: enabled, identity });
      if (enabled) Promise.resolve().then(() => load(controller.signal)).then(result => {
        if (active) setState({ result, error: null, busy: false, identity });
      }, error => { if (active) setState({ result: null, error, busy: false, identity }); });
      return () => { active = false; controller.abort(); };
    }, [identity, adapter, enabled]);
    return state.identity === identity ? state : { result: null, error: null, busy: enabled };
  }
  function Styles() {
    return <style>{`
      .calibration-live{min-width:0;color:var(--ui-text);background:transparent;letter-spacing:0}
      .calibration-live h2{font-size:22px;line-height:30px;margin:0}.calibration-live h3{font-size:16px;line-height:24px;margin:0}
      .calibration-live p{margin:8px 0;line-height:20px}.ca-muted{color:var(--ui-info-muted)}
      .ca-heading,.ca-tools,.ca-page{display:flex;align-items:center;gap:8px 16px;flex-wrap:wrap;min-width:0}
      .ca-heading{justify-content:space-between;padding-bottom:12px}.ca-tools{padding:12px 0;border-top:1px solid var(--ui-border)}
      .ca-tools label,.ca-page label{display:flex;align-items:center;gap:8px;min-width:0;font-size:13px}
      .ca-tools .ca-search{flex:1 1 280px;max-width:480px}.ca-search input{width:100%}
      .ca-tools select{max-width:175px}.ca-tools .ca-check{white-space:nowrap}.ca-actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
      .ca-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));border-top:1px solid var(--ui-border);border-bottom:1px solid var(--ui-border);margin-bottom:12px}
      .ca-metric{padding:12px 16px;border-right:1px solid var(--ui-border)}.ca-metric:first-child{padding-left:0}.ca-metric:last-child{border-right:0}
      .ca-metric span{display:block;font-size:12px;color:var(--ui-info-muted)}.ca-metric strong{display:block;font-size:24px;line-height:32px;font-weight:600;font-variant-numeric:tabular-nums}
      .ca-note{padding:8px 12px;border-left:2px solid var(--ui-warning-text);background:var(--ui-surface-muted);font-size:13px;overflow-wrap:anywhere}
      .ca-table-scroll{overflow:auto;max-height:560px;max-height:min(560px,54vh);border-top:1px solid var(--ui-border);border-bottom:1px solid var(--ui-border)}
      .ca-table{border-collapse:collapse;width:100%;table-layout:fixed;font-size:13px;background:transparent}
      .ca-table th,.ca-table td{padding:10px 12px;border-bottom:1px solid var(--ui-border);text-align:left;overflow-wrap:anywhere;vertical-align:middle}
      .ca-table th{position:sticky;top:0;background:var(--ui-surface-muted);font-weight:500;z-index:1}
      .ca-table tbody tr:last-child td{border-bottom:0}.ca-table tr[data-selected=true]{background:var(--ui-info-bg)}
      .ca-table .ca-number{font-variant-numeric:tabular-nums}.ca-table .ca-business{width:29%}.ca-table .ca-op{width:18%}
      .ca-table .ca-small{width:10%}.ca-table .ca-action{width:60px}.ca-table button{max-width:100%}
      .ca-table td small{display:block;color:var(--ui-info-muted);line-height:18px}.ca-page{justify-content:flex-end;padding:10px 0}
      .ca-page>span:first-child{margin-right:auto;font-size:13px}.ca-empty{padding:36px 12px;text-align:center;color:var(--ui-info-muted)}
      .ca-detail{border-top:1px solid var(--ui-border);padding:16px 0;min-width:0;scroll-margin-top:72px}.ca-facts{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:12px 0}
      .ca-facts div{min-width:0}.ca-facts dt{font-size:12px;color:var(--ui-info-muted)}.ca-facts dd{margin:4px 0;overflow-wrap:anywhere;font-size:13px}
      .ca-evidence{border-top:1px solid var(--ui-border);padding:8px 0;min-width:0;font-size:13px;overflow-wrap:anywhere}
      .ca-evidence summary{white-space:normal}.ca-evidence details{margin:8px 0 8px 16px}.ca-evidence pre{white-space:pre-wrap;overflow-wrap:anywhere;font:12px/20px var(--font-family);color:var(--ui-text)}
      .ca-sample-group{padding-top:12px;min-width:0}.ca-sample-group h4{font-size:13px;line-height:20px;margin:0 0 8px}
      .ca-refs{display:grid;grid-template-columns:140px minmax(0,1fr);gap:6px 12px;margin:10px 0}.ca-refs dt{color:var(--ui-info-muted)}.ca-refs dd{margin:0;overflow-wrap:anywhere}
      @media(max-width:1000px){.ca-facts{grid-template-columns:repeat(2,minmax(0,1fr))}.ca-tools .ca-search{max-width:none}.ca-table{min-width:760px}}
    `}</style>;
  }
  function Filters({ value, onChange, disabled }) {
    const [query, setQuery] = React.useState(value.query);
    React.useEffect(() => setQuery(value.query), [value.query]);
    return <form className="ca-tools" aria-label="校准筛选" onSubmit={event => { event.preventDefault(); onChange({ query }); }}>
      <label className="ca-search"><input type="search" aria-label="搜索校准明细" placeholder="搜索图号、零件名、工序或序号" maxLength={200} value={query} disabled={disabled} onChange={event => setQuery(event.target.value)} /></label>
      <Button icon="search" type="submit" aria-label="搜索" disabled={disabled} />
      <label>工序来源<select aria-label="工序来源" disabled={disabled} value={value.source || ''} onChange={event => onChange({ source: event.target.value || null, query })}>
        <option value="">全部来源</option><option value="internal">自制</option><option value="external">外协</option><option value="unknown">未确认</option></select></label>
      <label>状态<select aria-label="建议状态" disabled={disabled} value={value.status} onChange={event => onChange({ status: event.target.value, query })}>
        <option value="all">全部状态</option><option value="suggested">已有建议</option><option value="insufficient_data">数据不足</option></select></label>
      <label className="ca-check"><input type="checkbox" checked={value.deviation === 'over_20_percent'} disabled={disabled} onChange={event => onChange({ deviation: event.target.checked ? 'over_20_percent' : 'all', query })} />仅看偏差 &gt; 20%</label>
      <Button icon="x" aria-label="清除筛选" disabled={disabled} onClick={() => { setQuery(''); onChange({ query: '', source: null, status: 'all', deviation: 'all', column_filters: {} }); }} />
    </form>;
  }
  function Page({ page, onChange, disabled, label = '' }) {
    return <div className="ca-page"><span aria-live="polite">共 {page.total} 项 · 第 {page.number} / {Math.max(1, page.total_pages)} 页</span>
      <label>每页<select aria-label={label + '每页数量'} value={page.size} disabled={disabled} onChange={event => onChange({ size: Number(event.target.value), page: 1 })}>
        {Array.from(new Set([10, 20, 50, page.size])).sort((a, b) => a - b).map(size => <option key={size} value={size}>{size}</option>)}</select></label>
      <Button icon="chevron-left" aria-label={label + '上一页'} disabled={disabled || page.number <= 1} onClick={() => onChange({ page: page.number - 1 })} />
      <Button icon="chevron-right" aria-label={label + '下一页'} disabled={disabled || page.number >= page.total_pages} onClick={() => onChange({ page: page.number + 1 })} /></div>;
  }
  function Table({ rows, selected, onSelect, onPart, disabled, canView, scope, adapter, onSort, onFilter, widths, onResize, total }) {
    const columns = [['part_no', '图号 / 零件', 240], ['operation_label', '工序 / 来源', 210], ['old_unit_hours', '原定额 h/件', 155],
      ['suggested_unit_hours', '建议 h/件', 140], ['sample_count', '有效样本', 125], ['absolute_deviation_percent', '偏差', 125], ['status', '状态', 125]];
    const width = (key, value) => widths[key] || value;
    return <div className="ca-table-scroll"><table className="ca-table" aria-label="校准明细" style={{ minWidth: 60 + columns.reduce((sum, [key, , value]) => sum + width(key, value), 0) }}><thead><tr>
      {columns.map(([key, title, value]) => <th key={key} style={{ width: width(key, value) }} aria-sort={scope.sort === key ? scope.direction === 'asc' ? 'ascending' : 'descending' : 'none'}>
        <window.ResourceTableHeader column={{ key, title }} kind="calibration" scope={scope} adapter={adapter} sort={scope.sort} direction={scope.direction} sortActive
          onSort={onSort} onFilter={rule => onFilter(key, rule)} filter={scope.column_filters[key]} matchingCount={total}
          width={width(key, value)} onResize={value => onResize(key, Math.min(16384, value))} disabled={disabled} scopeTransform={window.CalibrationAPI.facetScope} />
      </th>)}<th className="ca-action">详情</th>
    </tr></thead><tbody>{rows.map(row => <tr key={row.suggestion_ref} data-ref={row.suggestion_ref} data-selected={selected === row.suggestion_ref}>
      <td><Button className="lnk" aria-label={'查看零件 ' + row.part_no} disabled={disabled || !canView || row.capabilities.view !== true || typeof onPart !== 'function'}
        onClick={() => onPart(row)}>{row.part_no}</Button><small>{row.part_name}</small></td><td>{row.sequence} · {row.operation_label}<small>{source(row.source)}</small></td>
      <td className="ca-number">{text(row.old_unit_hours, '未提供')}</td><td className="ca-number">{text(row.suggested_unit_hours, '暂无建议')}</td><td className="ca-number">{row.sample_count}</td>
      <td className="ca-number" style={{ color: row.over_20_percent ? 'var(--ui-danger-text)' : 'var(--ui-info-muted)' }}>{row.deviation_percent === null ? '未计算' : (row.deviation_percent > 0 ? '+' : '') + row.deviation_percent + '%'}</td>
      <td>{row.status === 'insufficient_data' ? '数据不足' : '待复核'}</td><td><Button icon="arrow-right" className="mini" aria-label={'查看 ' + row.part_no + ' ' + row.sequence + ' ' + row.operation_label}
        disabled={disabled} reason={canView && row.capabilities.view === true ? '' : '查看权限尚未确认，暂不能打开。'} onClick={() => onSelect(row.suggestion_ref)} /></td>
    </tr>)}</tbody></table>{!rows.length && <div className="ca-empty" role="status">当前筛选没有记录。</div>}</div>;
  }
  window.CalibrationControls = { Button, Icon, ErrorBox, Styles, Filters, Page, Table, useRead, text, hours, source, writeReason };
})();
