(function () {
  'use strict';
  const { Button, Icon, ErrorBox } = window.ResourceControls;
  const missingValue = value => value === null || value === undefined;
  const text = (value, missing = '未知') => missingValue(value) ? missing : String(value);
  // 数字一律走 WorkbenchFormat：小时最多 3 位小数、去掉尾零；缺值只写缺值说明，不拼单位。
  const amount = (value, missing = '未知') => missingValue(value) ? missing : window.WorkbenchFormat.number(value, { digits: 3, trim: true });
  const hours = (value, missing = '未填写') => missingValue(value) ? missing : window.WorkbenchFormat.hours(value, { digits: 3, trim: true });
  const unitHours = (value, missing = '未填写') => missingValue(value) ? missing : hours(value) + '/件';
  const percent = (value, missing = '未计算') => missingValue(value) ? missing
    : (value > 0 ? '+' : '') + window.WorkbenchFormat.percent(value / 100, { digits: 1, trim: true });
  const source = value => ({ internal: '自制', external: '外协', unknown: '未确认' })[value] || '未确认';
  const statusText = value => value === 'insufficient_data' ? '数据不足' : '已有建议';
  const writeReason = '请先检查所选模板是否可采用。';
  const viewReason = '当前来源暂不能查看。';
  function useRead(load, identity, adapter, enabled = true) {
    const read = window.APSResourceSession.useQuery(load, [identity, adapter], enabled);
    return { ...read, busy: read.loading };
  }
  function Filters({ value, onChange, disabled }) {
    const [query, setQuery] = React.useState(value.query);
    React.useEffect(() => setQuery(value.query), [value.query]);
    return <form className="ca-tools" aria-label="校准筛选" onSubmit={event => { event.preventDefault(); onChange({ query }); }}>
      <label className="ca-search"><input type="search" aria-label="搜索校准明细" placeholder="搜索图号、零件名、工序或序号" maxLength={200} value={query} disabled={disabled} onChange={event => setQuery(event.target.value)} /></label>
      <Button icon="search" type="submit" aria-label="搜索" className="primary" disabled={disabled} />
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
    // 默认列宽（B1 样式包 2026-09-21 核定）：905 + 详情列 60 = 965，1280 视口整表放得下；
    // 每个表头文字按 13px 字号加 16px 内距都放得进对应宽度，放不下时缩短文案而不是压宽度。
    const columns = [['part_no', '图号 / 零件', 190], ['operation_label', '工序 / 来源', 160], ['old_unit_hours', '原定额（小时/件）', 145],
      ['suggested_unit_hours', '建议（小时/件）', 130], ['sample_count', '可用记录数', 95], ['absolute_deviation_percent', '偏差', 90], ['status', '状态', 95]];
    const actionWidth = 60;
    const width = (key, value) => widths[key] || value;
    return <div className="ca-table-scroll wb-table-frame" tabIndex={0} role="region" aria-label="校准明细滚动区域"><table className="ca-table" aria-label="校准明细" style={{ minWidth: actionWidth + columns.reduce((sum, [key, , value]) => sum + width(key, value), 0) }}><caption className="wb-visually-hidden">当前筛选范围的校准建议；建议不直接修改已有批次定额。</caption><thead><tr>
      {columns.map(([key, title, value]) => <th key={key} scope="col" style={{ width: width(key, value) }} aria-sort={scope.sort === key ? scope.direction === 'asc' ? 'ascending' : 'descending' : 'none'}>
        <window.ResourceTableHeader column={{ key, title }} kind="calibration" scope={scope} adapter={adapter} sort={scope.sort} direction={scope.direction} sortActive
          onSort={onSort} onFilter={rule => onFilter(key, rule)} filter={scope.column_filters[key]} matchingCount={total}
          width={width(key, value)} onResize={value => onResize(key, Math.min(16384, value))} disabled={disabled} scopeTransform={window.CalibrationAPI.facetScope} />
      </th>)}<th scope="col" className="ca-action" style={{ width: actionWidth }}>详情</th>
    </tr></thead><tbody>{rows.map(row => <tr key={row.suggestion_ref} data-ref={row.suggestion_ref} data-selected={selected === row.suggestion_ref}>
      <td><Button className="lnk" aria-label={'查看零件 ' + row.part_no} disabled={disabled || !canView || row.capabilities.view !== true || typeof onPart !== 'function'}
        onClick={() => onPart(row)}>{row.part_no}</Button><small>{row.part_name}</small></td><td>{row.sequence} · {row.operation_label}<small>{source(row.source)}</small></td>
      <td className="ca-number">{amount(row.old_unit_hours, '未填写')}</td><td className="ca-number">{amount(row.suggested_unit_hours, '暂无建议')}</td><td className="ca-number">{row.sample_count}</td>
      <td className={'ca-number ' + (row.over_20_percent ? 'ca-deviation-over' : 'ca-deviation-within')}>{percent(row.deviation_percent)}</td>
      <td>{statusText(row.status)}</td><td className="ca-action"><Button icon="arrow-right" className="mini" aria-label={'查看 ' + row.part_no + ' ' + row.sequence + ' ' + row.operation_label}
        disabled={disabled} reasonDisplay="tooltip" reason={canView && row.capabilities.view === true ? '' : viewReason} onClick={() => onSelect(row.suggestion_ref)} /></td>
    </tr>)}</tbody></table>{!rows.length && <window.WorkbenchListControls.EmptyState kind="empty" title="当前筛选没有记录" hint="调整图号、工序来源或建议状态后重新查询。" />}</div>;
  }
  window.CalibrationControls = { Button, Icon, ErrorBox, Filters, Page, Table, useRead, text, amount, hours, unitHours, percent, source, statusText, writeReason, viewReason };
})();
