(function () {
  'use strict';
  const { Button } = window.ResourceControls;
  function text(key, value) {
    if (value === null) return '未填写';
    if (value === '') return '空白';
    if (key === 'route_parsed') return value === 'yes' ? '已解析' : value === 'no' ? '未解析' : '原标记：' + String(value);
    if (key === 'source') return value === 'internal' ? '自制' : value === 'external' ? '外协' : String(value);
    if (typeof value === 'boolean') return value ? '是' : '否';
    return String(value);
  }
  function Facts({ value, fields, empty }) {
    if (value === null) return <span className="muted">{empty}</span>;
    return <dl className="rm-facts">{Object.keys(value).map(key => <React.Fragment key={key}><dt>{fields[key]}</dt><dd style={{ whiteSpace: 'pre-wrap' }}>{text(key, value[key])}</dd></React.Fragment>)}</dl>;
  }
  function ProcessActionPreview({ data, fields = window.APSProcessActions.fields, renderDetails }) {
    const [filter, setFilter] = React.useState('all'), [page, setPage] = React.useState(1);
    React.useEffect(() => { setPage(1); setFilter('all'); }, [data.preview_ref]);
    const rows = data.rows.filter(row => filter === 'all' || row.result === filter), pages = Math.max(1, Math.ceil(rows.length / 50)), current = Math.min(page, pages);
    const labels = { new: '新增', update: '更新', unchanged: '不变', delete: '删除', rejected: '不能提交' };
    return <section className="rm-preview" aria-label="零件操作明细"><div className="rm-summary" role="status">{Object.keys(labels).map(key => <span key={key}>{labels[key]} <b>{data.summary[key]}</b></span>)}</div>
      <div className="rm-preview-toolbar"><h3>逐行核对</h3><label>显示 <select aria-label="预检明细筛选" value={filter} onChange={event => { setFilter(event.target.value); setPage(1); }}><option value="all">全部 {data.rows.length} 行</option><option value="rejected">不能提交 {data.summary.rejected} 行</option></select></label></div>
      <div className="rm-table-wrap"><table className="rm-table" aria-label="零件操作预检"><caption className="wb-visually-hidden">{"零件操作预检"}</caption><thead><tr><th scope="col" style={{ width: '8%' }}>行号</th><th scope="col" style={{ width: '18%' }}>零件 / 结果</th><th scope="col" style={{ width: '32%' }}>原记录</th><th scope="col" style={{ width: '32%' }}>修改后</th><th scope="col" style={{ width: '10%' }}>引用</th></tr></thead>
        <tbody>{rows.slice((current - 1) * 50, current * 50).map(row => <React.Fragment key={row.row}><tr><td>{row.row}</td><td>{row.business_code === null ? '原零件已不存在' : row.business_code}<div>{labels[row.result]}</div></td>
          <td><Facts value={row.before} fields={fields} empty="未取得原记录" /></td><td><Facts value={row.after} fields={fields} empty={row.action === 'delete' ? '删除后不再存在' : '未形成修改'} /></td><td>{row.reference_count} 项</td></tr>
          {row.errors.length > 0 && <tr className="rm-row-note"><td colSpan={5}>{row.errors.map((error, index) => <div className="rm-danger" key={index}>第 {row.row} 行：{error.message}</div>)}</td></tr>}
          {renderDetails && row.route_summary && <tr className="rm-row-note"><td colSpan={5}>{renderDetails(row)}</td></tr>}</React.Fragment>)}
          {!rows.length && <tr><td colSpan={5}>没有对应明细。</td></tr>}</tbody></table></div>
      <div className="rm-pagination"><span>共 {rows.length} 行 · 第 {current} / {pages} 页</span><span>每页 50 行</span><Button icon="chevron-left" aria-label="预检上一页" disabled={current <= 1} onClick={() => setPage(current - 1)} /><Button icon="chevron-right" aria-label="预检下一页" disabled={current >= pages} onClick={() => setPage(current + 1)} /></div>
    </section>;
  }
  window.ProcessActionPreview = ProcessActionPreview;
})();
