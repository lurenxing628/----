(function () {
  'use strict';
  const M = window.APSResourceMaterial;
  const { Button } = window.ResourceControls;
  function value(key, item, contract) {
    if (item === null) return '空值';
    if (item === '') return '空白';
    if (contract.displayValue) {
      const formatted = contract.displayValue(key, item);
      if (formatted !== undefined) return formatted;
    }
    if (Array.isArray(item)) return item.length ? item.join('、') : '未绑定';
    if (typeof item === 'boolean') return item ? '是' : '否';
    if (contract.kind !== 'material') return window.APSResourceContract.fieldValue(contract.kind, key, item);
    if (key === 'status') return window.APSResourceContract.fieldValue('material', key, item);
    return String(item);
  }
  function Facts({ facts, empty, changes, fields, contract }) {
    if (facts === null) return <span className="muted">{empty}</span>;
    return <dl className="rm-facts">{Object.keys(facts).map(key => <React.Fragment key={key}>
      <dt>{fields[key] || '数据'}</dt><dd className={Object.prototype.hasOwnProperty.call(changes, key) ? 'rm-changed' : ''}>{value(key, facts[key], contract)}</dd>
    </React.Fragment>)}</dl>;
  }
  function Preview({ data, mode, contract = M, label = '物料' }) {
    const fields = data.columns ? Object.fromEntries(data.columns.map(item => [item.key, item.label])) : contract.fields;
    const [filter, setFilter] = React.useState('all'), [page, setPage] = React.useState(1), [size, setSize] = React.useState(20);
    React.useEffect(() => { setFilter('all'); setPage(1); }, [data.preview_ref]);
    const rows = data.rows.filter(row => filter === 'all' || (filter === 'rejected' ? row.result === 'rejected' : row.requires_confirmation));
    const pages = Math.max(1, Math.ceil(rows.length / size)), current = Math.min(page, pages);
    return <section className="rm-preview" aria-label={label + '预检明细'}>
      <div className="rm-summary" role="status">{Object.keys(M.results).filter(key => key !== (mode === 'bulk' ? 'new' : 'delete') && (mode !== 'bulk' || !['update', 'unchanged'].includes(key))).map(key =>
        <span key={key}>{M.results[key]} <b className={key === 'rejected' && data.summary[key] ? 'rm-danger' : ''}>{data.summary[key]}</b></span>)}</div>
      <div className="rm-preview-toolbar"><h3>逐行预检</h3><label>显示 <select aria-label="预检明细筛选" value={filter} onChange={event => { setFilter(event.target.value); setPage(1); }}>
        <option value="all">全部 {data.rows.length} 行</option><option value="rejected">拒绝行 {data.summary.rejected}</option>
        {mode === 'import' && <option value="confirmation">涉及引用的更新 {data.rows.filter(row => row.requires_confirmation).length}</option>}</select></label></div>
      <div className="rm-table-wrap wb-table-frame" data-sticky-head tabIndex="0" role="region" aria-label="完整修改前后明细"><table className="rm-table wb-table">
        <caption className="wb-visually-hidden">{label}预检修改前后明细</caption><thead><tr><th scope="col" style={{ width: '7%' }}>行号</th><th scope="col" style={{ width: '15%' }}>{label} / 结果</th><th scope="col" style={{ width: '34%' }}>修改前</th><th scope="col" style={{ width: '34%' }}>修改后</th><th scope="col" style={{ width: '10%' }}>引用</th></tr></thead>
        <tbody>{rows.slice((current - 1) * size, current * size).map(row => <React.Fragment key={row.row}>
          <tr data-material-row={contract.kind === 'material' ? row.row : undefined} data-resource-row={row.row}><td>{row.row}</td><td><strong>{row.business_code || '编号无效'}</strong><div className={row.result === 'rejected' ? 'rm-danger' : ''}>{M.results[row.result]}</div></td>
            <td><Facts facts={row.before} empty={row.result === 'new' ? '尚不存在' : '未取得原记录'} changes={row.changes} fields={fields} contract={contract} /></td>
            <td><Facts facts={row.after} empty={row.action === 'delete' ? '删除后不再存在' : '未形成可提交内容'} changes={row.changes} fields={fields} contract={contract} /></td><td>{row.reference_count} 项</td></tr>
          {(row.errors.length > 0 || row.requires_confirmation) && <tr className="rm-row-note"><td /><td colSpan="4">
            {row.errors.map((error, index) => <div className="rm-danger" key={index}>第 {row.row} 行 · {fields[error.field] || '数据'}：{error.message}</div>)}
            {row.requires_confirmation && <div>{contract.kind === 'material' ? '涉及已有物料需求' : '涉及关键字段或已有引用'}，需核对修改前后内容。</div>}</td></tr>}
        </React.Fragment>)}{!rows.length && <tr><td colSpan="5"><window.WorkbenchControls.EmptyState kind={filter === 'all' ? 'empty' : 'filtered'} title={filter === 'all' ? '暂无预检行' : undefined}
          action={filter === 'all' ? undefined : <Button onClick={() => { setFilter('all'); setPage(1); }}>清除筛选</Button>} /></td></tr>}</tbody></table></div>
      <window.WorkbenchControls.Pager page={current} pages={pages} total={rows.length} size={size} sizes={[20, 50, 100]} unit="行" label="预检" sizeLabel="预检每页行数"
        onPage={setPage} onSize={next => { setSize(next); setPage(1); }} />
    </section>;
  }
  function Styles() {
    return null;
  }
  window.ResourceMaterialPreview = Preview;
  window.ResourceMaterialPreview.Styles = Styles;
})();
