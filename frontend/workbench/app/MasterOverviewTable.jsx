(function () {
  'use strict';
  const C = window.APSMasterOverviewContract, { Button } = window.ResourceControls;
  function Tabs({ values, value, onChange, label, disabled }) {
    function key(event, index) {
      if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
      event.preventDefault();
      const next = event.key === 'Home' ? 0 : event.key === 'End' ? values.length - 1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + values.length) % values.length;
      onChange(values[next][0]); event.currentTarget.parentElement.children[next].focus();
    }
    return <div className="mo-tabs" role="tablist" aria-label={label}>{values.map(([id, title, count], index) => <button key={id} type="button" role="tab"
      aria-selected={id === value} disabled={disabled} tabIndex={id === value ? 0 : -1} onKeyDown={event => key(event, index)} onClick={() => onChange(id)}>{title}{count !== undefined && <span>{count}</span>}</button>)}</div>;
  }
  function Pager({ page, onPage, onSize, disabled, detail = false }) {
    return <div className="mo-pager"><span>{page.total} 条 · 第 {page.number} / {page.pages} 页</span>
      {onSize && <label>每页<select aria-label="主数据每页条数" value={page.size} disabled={disabled} onChange={event => onSize(Number(event.target.value))}>{[20, 50, 100].map(size => <option key={size} value={size}>{size}</option>)}</select></label>}
      <Button className="btn mo-icon" icon="chevron-left" aria-label={detail ? '详情上一页' : '主数据上一页'} disabled={disabled || page.number <= 1} onClick={() => onPage(page.number - 1)} />
      <Button className="btn mo-icon" icon="chevron-right" aria-label={detail ? '详情下一页' : '主数据下一页'} disabled={disabled || page.number >= page.pages} onClick={() => onPage(page.number + 1)} /></div>;
  }
  function Table({ data, selected, onSelect, onMaintain, onFilter, loading, error, navigation }) {
    const columns = C.columns[data.scope.view], rows = data.rows;
    return <div className="wb-table-frame"><div className="wb-table-shell"><table className="wb-table mo-table" aria-label="主数据清单" aria-busy={loading}
      style={{ minWidth: columns.reduce((sum, item) => sum + item[2], 48) }}><colgroup>{columns.map(([key, , width]) => <col key={key} style={{ width }} />)}<col style={{ width: 48 }} /></colgroup>
      <thead><tr>{columns.map(([key, title]) => <th key={key}><div className="mo-column"><span>{title}</span><Button className="btn mo-icon" icon="search" aria-label={'筛选列 ' + title}
        title={'筛选列 ' + title} aria-pressed={!!data.scope.column_filters[key]} onClick={() => onFilter(key)} disabled={loading} /></div></th>)}<th>维护</th></tr></thead>
      <tbody>{rows.map(item => <tr key={item.key} aria-selected={!!selected && selected.key === item.key} data-master-ref={item.entity_ref || item.ref}>{columns.map(([key]) => <td key={key}>
        {key === 'business_code' ? <button type="button" className="mo-link" aria-label={'查看 ' + item.business_code + (item.title ? ' ' + item.title : '')} onClick={event => onSelect(item, event.currentTarget)} disabled={loading}>{item.business_code}</button>
          : key === 'status' ? <span className="mo-status" data-status={item.status}>{C.cell(item, key)}</span> : C.cell(item, key)}</td>)}
        <td><Button className="btn mo-icon" icon="arrow-right" aria-label={'维护 ' + item.business_code} reason={item.target.unavailable_reason || (!navigation ? '维护导航尚未接入。' : '')} disabled={loading} onClick={() => onMaintain(item.target)} /></td></tr>)}</tbody></table></div>
      {!rows.length && <div className="mo-empty"><strong>{loading ? '正在读取主数据' : error ? '主数据读取失败' : '当前范围没有记录'}</strong></div>}</div>;
  }
  window.MasterOverviewTable = { Tabs, Pager, Table };
})();
