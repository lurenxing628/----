(function () {
  'use strict';
  const { Button, Icon, ErrorBox } = window.ResourceControls;
  const text = (value, missing = '未知') => value === null || value === undefined ? missing : String(value);
  const hours = (value, missing = '未填写') => value === null ? missing : text(value) + ' 小时';
  const source = value => ({ internal: '自制', external: '外协', unknown: '未确认' })[value] || '未确认';
  const writeReason = '采用与锁定前要先读取真实预检并确认；只影响以后新增的工序模板，不改已有批次、历史计划和现场记录。';
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
    return null;
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
    return <window.WorkbenchListControls.Pager page={page.number} pages={Math.max(1, page.total_pages)} total={page.total} size={page.size}
      sizes={Array.from(new Set([10, 20, 50, page.size])).sort((a, b) => a - b)} disabled={disabled} label={label}
      onPage={number => onChange({ page: number })} onSize={size => onChange({ size, page: 1 })} />;
  }
  function Table({ rows, selected, onSelect, onPart, disabled, canView, scope, adapter, onSort, onFilter, widths, onResize, total }) {
    const columns = [['part_no', '图号 / 零件', 240], ['operation_label', '工序 / 来源', 210], ['old_unit_hours', '原定额（小时/件）', 175],
      ['suggested_unit_hours', '建议（小时/件）', 160], ['sample_count', '可用记录数', 125], ['absolute_deviation_percent', '偏差', 125], ['status', '状态', 125]];
    const width = (key, value) => widths[key] || value;
    return <div className="ca-table-scroll wb-table-frame" tabIndex={0} role="region" aria-label="校准明细滚动区域"><table className="ca-table" aria-label="校准明细" style={{ minWidth: 60 + columns.reduce((sum, [key, , value]) => sum + width(key, value), 0) }}><caption className="wb-visually-hidden">当前筛选范围的校准建议；建议不直接修改已有批次定额。</caption><thead><tr>
      {columns.map(([key, title, value]) => <th key={key} scope="col" style={{ width: width(key, value) }} aria-sort={scope.sort === key ? scope.direction === 'asc' ? 'ascending' : 'descending' : 'none'}>
        <window.ResourceTableHeader column={{ key, title }} kind="calibration" scope={scope} adapter={adapter} sort={scope.sort} direction={scope.direction} sortActive
          onSort={onSort} onFilter={rule => onFilter(key, rule)} filter={scope.column_filters[key]} matchingCount={total}
          width={width(key, value)} onResize={value => onResize(key, Math.min(16384, value))} disabled={disabled} scopeTransform={window.CalibrationAPI.facetScope} />
      </th>)}<th scope="col" className="ca-action">详情</th>
    </tr></thead><tbody>{rows.map(row => <tr key={row.suggestion_ref} data-ref={row.suggestion_ref} data-selected={selected === row.suggestion_ref}>
      <td><Button className="lnk" aria-label={'查看零件 ' + row.part_no} disabled={disabled || !canView || row.capabilities.view !== true || typeof onPart !== 'function'}
        onClick={() => onPart(row)}>{row.part_no}</Button><small>{row.part_name}</small></td><td>{row.sequence} · {row.operation_label}<small>{source(row.source)}</small></td>
      <td className="ca-number">{text(row.old_unit_hours, '未填写')}</td><td className="ca-number">{text(row.suggested_unit_hours, '暂无建议')}</td><td className="ca-number">{row.sample_count}</td>
      <td className="ca-number" style={{ color: row.over_20_percent ? 'var(--ui-danger-text)' : 'var(--ui-info-muted)' }}>{row.deviation_percent === null ? '未计算' : (row.deviation_percent > 0 ? '+' : '') + row.deviation_percent + '%'}</td>
      <td>{row.status === 'insufficient_data' ? '数据不足' : '待复核'}</td><td><Button icon="arrow-right" className="mini" aria-label={'查看 ' + row.part_no + ' ' + row.sequence + ' ' + row.operation_label}
        disabled={disabled} reasonDisplay="tooltip" reason={canView && row.capabilities.view === true ? '' : '查看权限尚未确认，暂不能打开。'} onClick={() => onSelect(row.suggestion_ref)} /></td>
    </tr>)}</tbody></table>{!rows.length && <window.WorkbenchListControls.EmptyState kind="empty" title="当前筛选没有记录" hint="调整图号、工序来源或建议状态后重新查询。" />}</div>;
  }
  window.CalibrationControls = { Button, Icon, ErrorBox, Styles, Filters, Page, Table, useRead, text, hours, source, writeReason };
})();
