(function () {
  'use strict';
  const C = window.APSMasterOverviewContract, { Button } = window.ResourceControls;
  function Tabs({ values, value, onChange, label, disabled }) {
    function key(event, index) {
      if (event.altKey || event.ctrlKey || event.metaKey) return;
      if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
      event.preventDefault();
      const next = event.key === 'Home' ? 0 : event.key === 'End' ? values.length - 1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + values.length) % values.length;
      onChange(values[next][0]); event.currentTarget.parentElement.children[next].focus();
    }
    return <div className="mo-tabs" role="tablist" aria-label={label}>{values.map(([id, title, count], index) => <button key={id} type="button" role="tab"
      aria-selected={id === value} disabled={disabled} tabIndex={id === value ? 0 : -1} onKeyDown={event => key(event, index)} onClick={() => onChange(id)}>{title}{count !== undefined && <span>{count}</span>}</button>)}</div>;
  }
  function Pager({ page, onPage, onSize, disabled, detail = false }) {
    return <window.WorkbenchListControls.Pager page={page} sizes={detail ? [10] : [20, 50, 100]} onPage={onPage} onSize={onSize} disabled={disabled} unit="条" label={detail ? '详情' : '基础资料'} />;
  }
  function Table({ data, selected, onSelect, onMaintain, onFilter, onClear, onRetry, loading, error, navigation }) {
    const columns = C.columns[data.scope.view], rows = data.rows;
    const filtered = data.scope.query !== '' || data.scope.domain !== 'all' || data.scope.status !== 'all' || Object.keys(data.scope.column_filters).length > 0;
    return <div className="wb-table-frame" data-sticky-head data-sticky-actions><table className="wb-table mo-table" aria-label="资料清单" aria-busy={loading}
      style={{ minWidth: columns.reduce((sum, item) => sum + item[2], 64) }}><caption className="wb-sr-only">资料清单</caption><colgroup>{columns.map(([key, , width]) => <col key={key} style={{ width }} />)}<col style={{ width: 64 }} /></colgroup>
      <thead><tr>{columns.map(([key, title]) => <th scope="col" key={key} className={key === 'business_code' ? 'wb-col-key' : ''}><div className="mo-column"><span>{title}</span><Button className="btn mo-icon wb-column-filter" icon="search" aria-label={'筛选列 ' + title}
        title={'筛选列 ' + title} aria-pressed={!!data.scope.column_filters[key]} onClick={() => onFilter(key)} disabled={loading} /></div></th>)}<th scope="col" className="wb-col-actions">维护</th></tr></thead>
      <tbody>{rows.map(item => <tr key={item.key} aria-selected={!!selected && selected.key === item.key} data-master-ref={item.entity_ref || item.ref}>{columns.map(([key]) => <td key={key} className={key === 'business_code' ? 'wb-col-key' : ''}>
        {key === 'business_code' ? <button type="button" className="mo-link" aria-label={'查看 ' + item.business_code + (item.title ? ' ' + item.title : '')} onClick={event => onSelect(item, event.currentTarget)} disabled={loading}>{item.business_code}</button>
          : key === 'status' ? <span className="mo-status" data-status={item.status}>{C.cell(item, key)}</span> : C.cell(item, key)}</td>)}
        <td className="wb-col-actions"><Button className="btn mo-icon" icon="arrow-right" aria-label={'维护 ' + item.business_code} reasonDisplay="inline" reason={item.target.unavailable_reason || (!navigation ? window.WorkbenchTerms.outcomes.unavailable : '')} disabled={loading} onClick={() => onMaintain(item.target)} /></td></tr>)}</tbody></table>
      {!rows.length && <window.WorkbenchListControls.EmptyState kind={loading ? 'loading' : error ? 'error' : filtered ? 'filtered' : 'empty'} title={loading ? '正在读取基础资料' : error ? '基础资料读取失败' : '当前范围没有记录'} action={error ? <Button onClick={onRetry}>刷新基础资料</Button> : filtered ? <Button onClick={onClear}>清除筛选并查看清单</Button> : null} />}</div>;
  }
  window.MasterOverviewTable = { Tabs, Pager, Table };
})();
