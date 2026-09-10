(function () {
  'use strict';
  const B = window.APSBatchContract, C = window.APSResourceContract, S = window.APSResourceSession;
  const { Button, Modal, ErrorBox } = window.ResourceControls;
  function ColumnFilter({ adapter, scope, field, onApply, onClose }) {
    const [selected, setSelected] = React.useState(null), [search, setSearch] = React.useState('');
    const read = S.useQuery(async signal => {
      const result = await adapter.facets(scope, field, signal), data = result && result.data;
      if (!data || data.field !== field || !Array.isArray(data.values) || result.meta.snapshot_ref !== scope.snapshot_ref) throw C.failure('列筛选与列表范围不一致。');
      return result;
    }, [adapter, scope, field]);
    const all = read.result && read.result.data.values, chosen = selected || scope.column_filters && scope.column_filters[field] || all || [];
    return <Modal title={'筛选' + B.columns.find(row => row[0] === field)[1]} icon="filter" onClose={onClose} footer={<>
      <Button onClick={() => onApply(undefined)}>清除本列</Button><Button onClick={onClose}>取消</Button><Button icon="check" disabled={!all} onClick={() => onApply(chosen)}>完成</Button></>}>
      <div className="modal-b"><input type="search" aria-label="搜索列值" value={search} onChange={event => setSearch(event.target.value)} /><ErrorBox error={read.error} />
        {all && <><Button onClick={() => setSelected(all)}>全选列值</Button><Button onClick={() => setSelected([])}>全部不选</Button><div className="batch-value-list">
          {all.filter(value => B.label(field, value).toLowerCase().includes(search.toLowerCase())).map((value, index) => <label key={index}><input type="checkbox" checked={chosen.includes(value)} onChange={event => setSelected(event.target.checked ? chosen.concat([value]) : chosen.filter(item => item !== value))} />{B.label(field, value)}</label>)}
        </div></>}
      </div>
    </Modal>;
  }
  function BatchTable({ rows, scope, selected, setSelected, onOpen, onDelete, onSort, onFilter, loading, disabled }) {
    const checkbox = React.useRef(null), all = rows.length > 0 && rows.every(row => selected.includes(row.ref));
    const [widths, setWidths] = React.useState(Object.fromEntries(B.columns.map(([key, , width]) => [key, width]))), drag = React.useRef(null);
    function resize(key, value) { setWidths(current => ({ ...current, [key]: Math.max(80, Math.min(600, value)) })); }
    React.useEffect(() => { if (checkbox.current) checkbox.current.indeterminate = !all && rows.some(row => selected.includes(row.ref)); }, [rows, selected, all]);
    return <div className="wb-table-frame card-scroll"><table className="tbl wb-table" style={{ width: Object.values(widths).reduce((sum, width) => sum + width, 204), minWidth: '100%' }} aria-label="批次列表" aria-busy={loading}>
      <thead><tr><th style={{ width: 44 }}><input ref={checkbox} type="checkbox" aria-label="全选当前页" checked={all} disabled={disabled || !rows.length} onChange={event => setSelected(event.target.checked ? Array.from(new Set(selected.concat(rows.map(row => row.ref)))) : selected.filter(ref => !rows.some(row => row.ref === ref)))} /></th>
        {B.columns.map(([key, name]) => <th key={key} style={{ width: widths[key], position: 'relative' }} aria-sort={scope.sort === key ? scope.direction === 'asc' ? 'ascending' : 'descending' : 'none'}>
          {key === 'progress' ? name : <div className="batch-head"><Button className="linkbtn" disabled={disabled} onClick={() => onSort(key)} title={'排序' + name}>{name}</Button>
            <Button className="linkbtn" icon="filter" aria-label={'筛选' + name} onClick={() => onFilter(key)} disabled={disabled} /></div>}
          <span role="separator" tabIndex={disabled ? -1 : 0} aria-label={'调整' + name + '列宽'} aria-orientation="vertical" aria-valuenow={widths[key]} aria-valuemin={80} aria-valuemax={600}
            className="batch-column-resizer" onKeyDown={event => { if (!disabled && ['ArrowLeft', 'ArrowRight'].includes(event.key)) { event.preventDefault(); resize(key, widths[key] + (event.key === 'ArrowLeft' ? -12 : 12)); } }}
            onPointerDown={event => { if (disabled || event.button !== 0) return; drag.current = { key, x: event.clientX, width: widths[key] }; event.currentTarget.setPointerCapture(event.pointerId); event.preventDefault(); }}
            onPointerMove={event => { if (drag.current && drag.current.key === key) resize(key, drag.current.width + event.clientX - drag.current.x); }} onPointerUp={() => { drag.current = null; }} onPointerCancel={() => { drag.current = null; }} />
        </th>)}<th style={{ width: 160 }}>操作</th></tr></thead>
      <tbody>{rows.map(row => <tr key={row.ref}><td><input type="checkbox" aria-label={'选择 ' + row.business_code} checked={selected.includes(row.ref)} disabled={disabled} onChange={event => setSelected(event.target.checked ? selected.concat(row.ref) : selected.filter(ref => ref !== row.ref))} /></td>
        <td><Button className="linkbtn" onClick={() => onOpen(row.ref)} disabled={disabled}>{row.business_code}</Button></td><td><strong>{row.relationships.part_no}</strong><div className="muted">{row.label}</div></td>
        <td>{B.label('', row.fields.quantity)}</td><td>{B.label('', row.fields.due_date)}</td><td><div className="batch-progress"><progress value={row.relationships.completed_count} max={row.relationships.operation_count || 1} /><span>{row.relationships.completed_count} / {row.relationships.operation_count}</span></div>
          <details><summary>工序概况{row.relationships.gap_count ? ' · 待补 ' + row.relationships.gap_count : ''}</summary>{row.operations.length ? row.operations.map(op => <div key={op.ref}>{op.sequence} · {op.label}{op.issues.length ? ' · 待补齐' : ''}</div>) : '尚未生成工序'}</details></td>
        {['priority', 'ready_status', 'status'].map(key => <td key={key}><span className={'pill ' + (key === 'ready_status' ? row.fields[key] === 'yes' ? 'ok' : 'warn' : key === 'priority' ? row.fields[key] === 'normal' ? 'off' : 'warn' : row.status === 'completed' ? 'ok' : row.status === 'processing' ? 'warn' : 'off')}>{B.label(key, key === 'status' ? row.status : row.fields[key])}</span></td>)}
        <td><div className="batch-head"><Button icon="square-pen" onClick={() => onOpen(row.ref)} disabled={disabled}>查看/编辑</Button><Button icon="x" aria-label={'删除批次 ' + row.business_code} onClick={() => onDelete(row)} disabled={disabled} reason={B.reason(row.write_context, 'delete', 'production')} /></div></td>
      </tr>)}{!rows.length && <tr><td colSpan={10} style={{ padding: 24, textAlign: 'center' }}>{loading ? '正在读取批次…' : '当前条件下暂无批次'}</td></tr>}</tbody>
    </table></div>;
  }
  BatchTable.ColumnFilter = ColumnFilter;
  window.BatchTable = BatchTable;
})();
