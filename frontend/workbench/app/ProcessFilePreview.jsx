(function () {
  'use strict';
  const { Button, Issues, Icon } = window.ResourceControls;
  function HoursFacts({ value, fields, changes }) {
    if (value === null) return <span className="muted">未取得记录</span>;
    const keys = Object.keys(fields).filter(key => Object.prototype.hasOwnProperty.call(value, key) && !['business_code', 'sequence'].includes(key));
    return <dl className="rm-facts">{keys.filter(key => value[key] !== null || Object.prototype.hasOwnProperty.call(changes, key)).map(key => <React.Fragment key={key}><dt>{fields[key]}</dt>
      <dd className={Object.prototype.hasOwnProperty.call(changes, key) ? 'rm-changed' : undefined}>{value[key] === null ? '未填写' : key === 'source' ? window.APSProcessContract.sourceLabel(value[key]) : String(value[key])}</dd></React.Fragment>)}</dl>;
  }
  function HoursRows({ data, receipt = false }) {
    const [filter, setFilter] = React.useState('all'), [page, setPage] = React.useState(1), [search, setSearch] = React.useState('');
    React.useEffect(() => { setPage(1); setFilter('all'); setSearch(''); }, [data]);
    const counts = window.APSProcessFiles.hoursCounts(data), skips = new Map(data.skipped_rows.map(row => [row.row, row]));
    const status = row => skips.has(row.row) ? 'skipped' : ['update', 'new', 'committed'].includes(row.result) ? 'changed' : row.result;
    const labels = { changed: receipt ? '已导入' : '待导入', skipped: '单件工时已锁定 · 本行跳过', unchanged: '原值相同 · 无需导入', rejected: '不能提交' };
    const rows = data.rows.filter(row => (filter === 'all' || status(row) === filter) &&
      (String(row.business_code || '') + ' ' + String(row.sequence || '')).toLowerCase().includes(search.trim().toLowerCase()));
    const pages = Math.max(1, Math.ceil(rows.length / 20)), current = Math.min(page, pages);
    const fields = !receipt && Object.fromEntries(data.columns.map(row => [row.key, row.label]));
    return <section className="rm-preview" aria-label={receipt ? '工时导入结果' : '工时导入预检'}>
      <div className="rm-summary" role="status"><span>{receipt ? '已导入' : data.can_confirm ? '可导入' : '待处理更新'} <b>{counts.changed}</b> 行</span>
        <span>锁定跳过 <b>{counts.skipped}</b> 行</span><span>原值相同 <b>{counts.unchanged}</b> 行</span>{counts.rejected > 0 && <span className="rm-danger">不能提交 <b>{counts.rejected}</b> 行</span>}</div>
      <p role="status">{receipt ? counts.changed ? '仅已导入行发生修改，其余行未修改。' : '本次没有导入任何工时，业务数据未变化。' :
        !data.can_confirm ? '本批存在不能提交的行，当前不能导入任何工时。' : counts.skipped === data.rows.length ? '全部行的单件工时都已锁定，本次跳过；确认只记录结果，不修改工时。' : '尚未导入；确认后只写入可导入行。'}</p>
      {counts.skipped > 0 && <p>定额锁定只保护单件工时（来自工时校准）。锁定行若要修改单件工时，本行全部跳过，换型时间也不会随本行导入；只改换型时间时，保留原单件工时或把该列留空即可。</p>}
      <div className="rm-preview-toolbar"><h3>{receipt ? '逐行导入结果' : '逐行核对'}</h3>
        <label>查找 <input type="search" aria-label="查找图号或工序" value={search} onChange={event => { setSearch(event.target.value); setPage(1); }} /></label>
        <label>显示 <select aria-label="工时明细筛选" value={filter} onChange={event => { setFilter(event.target.value); setPage(1); }}>
          <option value="all">全部 {data.rows.length} 行</option><option value="skipped">锁定跳过 {counts.skipped} 行</option>
          <option value="changed">{receipt ? '已导入' : '待导入'} {counts.changed} 行</option><option value="unchanged">原值相同 {counts.unchanged} 行</option>
          {!receipt && <option value="rejected">不能提交 {counts.rejected} 行</option>}</select></label></div>
      <div className="rm-table-wrap" tabIndex="0" role="region" aria-label="完整工时明细"><table className="rm-table" aria-label={receipt ? '工时导入结果明细' : '工时导入预检明细'}><caption className="wb-visually-hidden">{receipt ? '工时导入结果明细' : '工时导入预检明细'}</caption>
        <thead><tr><th scope="col" style={{ width: '8%' }}>行号</th><th scope="col" style={{ width: receipt ? '28%' : '24%' }}>零件 / 工序</th><th scope="col" style={{ width: receipt ? '64%' : '24%' }}>处理结果</th>
          {!receipt && <><th scope="col" style={{ width: '22%' }}>原记录</th><th scope="col" style={{ width: '22%' }}>导入后</th></>}</tr></thead>
        <tbody>{rows.slice((current - 1) * 20, current * 20).map(row => { const skip = skips.get(row.row); return <tr key={row.row} data-quota-row={row.row} data-quota-result={status(row)}>
          <td>{row.row}</td><td><strong>{row.business_code || '图号未识别'}</strong><div>工序 {row.sequence === undefined ? '未识别' : row.sequence}</div></td>
          <td><div>{skip && <Icon name="lock" />} {labels[status(row)]}</div>{skip && <><div>已采用校准结果，单件工时不能被本文件覆盖。</div><div style={{ whiteSpace: 'pre-wrap' }}>采用原因：{skip.reason}</div></>}
            {!receipt && row.errors.map((error, index) => <div className="rm-danger" key={index}>{error.message}</div>)}</td>
          {!receipt && <><td><HoursFacts value={row.before} fields={fields} changes={row.changes} /></td><td><HoursFacts value={row.after} fields={fields} changes={row.changes} /></td></>}</tr>; })}
          {!rows.length && <tr><td colSpan={receipt ? 3 : 5}>没有匹配的工时记录。</td></tr>}</tbody></table></div>
      <div className="rm-pagination"><span>共 {rows.length} 行 · 第 {current} / {pages} 页</span><span>每页 20 行</span>
        <Button icon="chevron-left" aria-label="工时明细上一页" disabled={current <= 1} onClick={() => setPage(current - 1)} />
        <Button icon="chevron-right" aria-label="工时明细下一页" disabled={current >= pages} onClick={() => setPage(current + 1)} /></div>
    </section>;
  }
  function RouteSummary({ value }) {
    if (!value) return null;
    return <details><summary>路线识别结果</summary><p>工序 {value.counts.operations} · 已识别 {value.counts.recognized} · 未识别 {value.counts.unknown}</p>
      <p>{value.can_confirm_route ? '路线识别检查通过，尚未执行本次导入。' : '路线仍有待处理问题，本次不能确认。'}</p>
      {value.diagnostics.map((row, index) => <div key={index} className={row.severity === 'error' ? 'rm-danger' : undefined}>{row.sequence === undefined ? '' : '工序 ' + row.sequence + '：'}{row.message}</div>)}</details>;
  }
  function Groups({ rows, selected, onChange, disabled }) {
    const [page, setPage] = React.useState(1), pages = Math.max(1, Math.ceil(rows.length / 50)), current = Math.min(page, pages);
    if (!rows.length) return null;
    const all = rows.every(row => selected.includes(row.ref));
    return <section aria-label="受影响的外协组"><h3>需明确解除的原外协组</h3>
      <label className="rm-check"><input type="checkbox" checked={all} disabled={disabled} onChange={event => onChange(event.target.checked ? rows.map(row => row.ref) : [])} />已核对全部 {rows.length} 组，同意解除这些原外协组。</label>
      <div className="rm-table-wrap"><table className="rm-table" aria-label="原外协组规则"><caption className="wb-visually-hidden">{"原外协组规则"}</caption><thead><tr><th scope="col" style={{ width: '8%' }}>解除</th><th scope="col">零件</th><th scope="col">工序范围</th><th scope="col">周期方式</th><th scope="col">原周期</th><th scope="col">供应商</th><th scope="col">原备注</th></tr></thead><tbody>
        {rows.slice((current - 1) * 50, current * 50).map(row => <tr key={row.ref}><td><input type="checkbox" aria-label={'解除 ' + row.business_code + ' 工序 ' + row.start_sequence + ' 至 ' + row.end_sequence + ' 的外协组'} checked={selected.includes(row.ref)} disabled={disabled}
          onChange={event => onChange(event.target.checked ? selected.concat(row.ref) : selected.filter(ref => ref !== row.ref))} /></td><td>{row.business_code}</td><td>{row.start_sequence} 至 {row.end_sequence}</td>
          <td>{row.merge_mode === 'merged' ? '合并周期' : row.merge_mode === 'separate' ? '逐序周期' : row.merge_mode === null ? '未填写' : row.merge_mode}</td>
          <td>{row.total_days === null ? '未填写' : row.total_days + ' 天'}</td><td>{row.supplier_label === null ? '未选' : row.supplier_label}</td><td>{row.remark === null ? '未填写' : row.remark}<Issues issues={row.issues} /></td></tr>)}
      </tbody></table></div><div className="rm-pagination"><span>共 {rows.length} 组 · 第 {current} / {pages} 页</span><span>每页 50 组</span><Button icon="chevron-left" aria-label="外协组上一页" disabled={current <= 1} onClick={() => setPage(current - 1)} /><Button icon="chevron-right" aria-label="外协组下一页" disabled={current >= pages} onClick={() => setPage(current + 1)} /></div>
    </section>;
  }
  function ProcessFilePreview({ data, groups, onGroups, disabled }) {
    if (data.kind === 'hours') return <HoursRows data={data} />;
    const fields = Object.fromEntries(data.columns.map(row => [row.key, row.label]));
    return <><window.ProcessActionPreview data={data} fields={fields} renderDetails={row => <RouteSummary value={row.route_summary} />} />
      <Groups rows={data.affected_groups} selected={groups} onChange={onGroups} disabled={disabled} /></>;
  }
  window.ProcessFilePreview = ProcessFilePreview;
  window.ProcessFileReceipt = props => <HoursRows {...props} receipt />;
})();
