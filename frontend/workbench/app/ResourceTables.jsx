(function () {
  'use strict';
  const C = window.APSResourceContract;
  const { Button, Status, Relation } = window.ResourceControls;
  const cell = (entity, key) => entity.fields[key] == null ? <span className="muted">未知</span> : String(entity.fields[key]);
  const columns = {
    material: [
      { key: 'spec', title: '规格', render: entity => cell(entity, 'spec') },
      { key: 'stock_qty', title: '库存', width: 135, numeric: true, render: entity => <>{cell(entity, 'stock_qty')}{entity.fields.stock_qty != null && entity.fields.unit ? ' ' + entity.fields.unit : ''}</> }
    ],
    machine: [
      { key: 'op_type_ref', title: '绑定工种', render: entity => <Relation entity={entity} field="op_type_ref" /> },
      { key: 'group_ref', title: '设备组', width: 130, render: entity => <Relation entity={entity} field="group_ref" /> }
    ],
    operator: [
      { key: 'skill_refs', title: '技能工种', render: entity => <Relation entity={entity} field="skill_refs" /> },
      { key: 'shift_profile_ref', title: '班次', width: 130, render: entity => <Relation entity={entity} field="shift_profile_ref" /> }
    ],
    supplier: [
      { key: 'op_type_refs', title: '可做外协工种', render: entity => <Relation entity={entity} field="op_type_refs" /> },
      { key: 'default_days', title: '默认周期（天）', width: 125, numeric: true, render: entity => cell(entity, 'default_days') }
    ]
  };
  function available(entity, key) {
    if (!C.availability(entity.availability)) {
      const issue = entity.issues.find(item => item.code === 'resource_availability_unavailable');
      return <span className="muted" title={issue ? issue.message : '可用数量尚未读取，不能以引用总数代替。'}>{issue ? '无法核实' : '待读取'}</span>;
    }
    return <span title={key === 'machines' ? '启用且绑定此工种的设备；不代表当日日历空闲。' : '启用、具有匹配设备授权且工种资格合格的去重人数；不代表当日日历空闲。'}>{entity.availability[key]}</span>;
  }
  function opColumns(category) {
    if (category === 'internal') return [
      { key: 'available_machines', title: '可用设备', width: 110, numeric: true, render: entity => available(entity, 'machines') },
      { key: 'available_operators', title: '可用人员', width: 110, numeric: true, render: entity => available(entity, 'operators') },
      { key: 'remark', title: '产能备注', render: entity => cell(entity, 'remark') }
    ];
    if (category === 'external') return [
      { key: 'default_merge_mode', title: '默认周期策略', width: 150, render: entity => C.fieldValue('op_type', 'default_merge_mode', entity.fields.default_merge_mode) },
      { key: 'remark', title: '备注', render: entity => cell(entity, 'remark') }
    ];
    return [
      { key: 'category', title: '归属', width: 90, render: entity => entity.fields.category === 'internal' ? '自制' : entity.fields.category === 'external' ? '外协' : '待归类' },
      { key: 'remark', title: '备注', render: entity => cell(entity, 'remark') }
    ];
  }
  function ResourceTables({ kind, category, entities, source, selected = [], onSelect, onOpen, onDelete, disabled = false, headerDisabled = disabled,
    loading = false, error, adapter, scope, matchingCount, sort = 'business_code', direction = 'asc', sortActive = true, onSort, onColumnFilter }) {
    const selectAll = React.useRef(null), all = entities.length > 0 && entities.every(item => selected.includes(item.ref));
    const table = React.useRef(null), [widths, setWidths] = React.useState(null);
    React.useEffect(() => { if (selectAll.current) selectAll.current.indeterminate = !all && entities.some(item => selected.includes(item.ref)); }, [all, entities, selected]);
    const opCategory = category || (entities.length && entities.every(item => item.fields.category === entities[0].fields.category) ? entities[0].fields.category : null);
    const cols = [
      { key: 'business_code', title: C.codeLabel(kind), width: 130, sortable: true, render: entity => <button type="button" className="lnk" style={{ border: 0, padding: 0, background: 'none', font: 'inherit', textAlign: 'left' }} disabled={disabled} onClick={() => onOpen(entity.ref)}>{entity.business_code}</button> },
      { key: 'label', title: C.nameLabel(kind), width: 160, sortable: true, render: entity => entity.label },
      ...(kind === 'op_type' ? opColumns(opCategory) : columns[kind] || []),
      ...(kind === 'op_type' ? [] : [{ key: 'status', title: '状态', width: 145, render: entity => <Status kind={kind} entity={entity} /> }])
    ];
    function resize(key, width) {
      if (headerDisabled || !Number.isFinite(width)) return;
      const current = {};
      table.current.querySelectorAll('thead th[data-column]').forEach(cell => { current[cell.dataset.column] = cell.getBoundingClientRect().width; });
      setWidths({ ...current, [key]: Math.max(56, width) });
    }
    return <div className="card wb-table-frame"><div className="card-scroll wb-table-shell"><table ref={table} className="tbl wb-table" aria-label={C.resourceName(kind, opCategory) + '列表'}
      style={widths ? { width: Object.values(widths).reduce((sum, width) => sum + width, 0), minWidth: 0 } : undefined} aria-busy={loading}>
      <thead><tr><th className="cbx" data-column="__selection" style={widths ? { width: widths.__selection } : undefined}><input ref={selectAll} type="checkbox" aria-label="全选当前页" checked={all} disabled={disabled || !entities.length} onChange={event => {
        const visible = new Set(entities.map(item => item.ref));
        onSelect(event.target.checked ? Array.from(new Set(selected.concat(Array.from(visible)))) : selected.filter(ref => !visible.has(ref)));
      }} /></th>
        {cols.map(col => <th key={col.key} data-column={col.key} className={col.numeric ? 'r' : ''} style={{ width: widths ? widths[col.key] : col.width }} aria-sort={sortActive && sort === col.key ? direction === 'asc' ? 'ascending' : 'descending' : 'none'}>
          <window.ResourceTableHeader column={col} kind={kind} scope={scope} adapter={adapter} matchingCount={matchingCount}
            sort={sort} direction={direction} sortActive={sortActive} onSort={onSort} filter={scope && scope.column_filters && scope.column_filters[col.key] || null} onFilter={rule => onColumnFilter(col.key, rule)}
            width={widths ? widths[col.key] : col.width} onResize={width => resize(col.key, width)} disabled={headerDisabled} />
        </th>)}
        <th className="actcol" data-column="__actions" style={{ width: widths ? widths.__actions : 216 }}>操作</th></tr></thead>
      <tbody>{entities.map(entity => <tr key={entity.ref}><td className="cbx"><input type="checkbox" aria-label={'选择 ' + entity.business_code + ' ' + entity.label} checked={selected.includes(entity.ref)} disabled={disabled}
        onChange={event => onSelect(event.target.checked ? selected.concat(entity.ref) : selected.filter(ref => ref !== entity.ref))} /></td>
        {cols.map(col => <td key={col.key} className={col.numeric ? 'r' : ''} style={{ overflowWrap: 'anywhere', whiteSpace: 'normal' }}>{col.render(entity)}
          {col.key === 'label' && entity.issues.some(issue => issue.scope !== 'collection') && <span className="muted" style={{ display: 'block', fontSize: 12 }}>待核对 {entity.issues.filter(issue => issue.scope !== 'collection').length} 项</span>}</td>)}
        <td className="actcol"><div className="rowact" style={{ minWidth: 192 }}>
          <Button className="mini" icon="search" disabled={disabled} onClick={() => onOpen(entity.ref)}>{kind === 'op_type' ? entity.fields.category === 'internal' ? '查看绑定' : entity.fields.category === 'external' ? '查看供应商' : '查看/编辑' : '查看/编辑'}</Button>
          <Button className="mini danger" icon="minus" reason={disabled ? '正在处理，请稍候。' : C.blocked(entity.write_context, kind, 'delete', source)} onClick={() => onDelete(entity.ref)}>删除</Button>
        </div></td></tr>)}{!entities.length && <tr><td colSpan={cols.length + 2} className="muted" style={{ textAlign: 'center', padding: 28 }}>{loading ? '正在读取资料…' : error ? '列表读取失败，请重新读取。' : '当前条件下没有资料。'}</td></tr>}</tbody>
    </table></div></div>;
  }
  function Pager({ page, onPage, onSize, disabled }) {
    const [jump, setJump] = React.useState(String(page.number));
    React.useEffect(() => setJump(String(page.number)), [page.number]);
    const totalPages = Math.max(1, page.pages);
    return <form className="pager" style={{ flexWrap: 'wrap' }} onSubmit={event => { event.preventDefault(); const next = Number(jump); if (!disabled && Number.isInteger(next) && next >= 1 && next <= totalPages) onPage(next); }}>
      <span>共 {page.total} 条</span><label className="field"><select aria-label="每页条数" value={page.size} disabled={disabled} onChange={event => onSize(Number(event.target.value))}>
        {Array.from(new Set([20, 50, 100, page.size])).sort((a, b) => a - b).map(size => <option key={size} value={size}>{size} 条 / 页</option>)}</select></label>
      <span className="grow" /><Button className="pg" icon="chevron-left" aria-label="上一页" reason={page.number <= 1 ? '已经是第一页。' : ''} disabled={disabled} onClick={() => onPage(page.number - 1)} />
      <span>第 {page.number} / {totalPages} 页</span><Button className="pg" icon="chevron-right" aria-label="下一页" reason={page.number >= totalPages ? '已经是最后一页。' : ''} disabled={disabled} onClick={() => onPage(page.number + 1)} />
      <label className="field"><input aria-label="跳转页码" type="number" min="1" max={totalPages} step="1" value={jump} disabled={disabled} onChange={event => setJump(event.target.value)} style={{ width: 74, textAlign: 'right' }} /></label>
      <Button type="submit" disabled={disabled} reason={!Number.isInteger(Number(jump)) || Number(jump) < 1 || Number(jump) > totalPages ? '请输入有效页码。' : ''}>跳转</Button>
    </form>;
  }
  ResourceTables.Pager = Pager;
  window.ResourceTables = ResourceTables;
})();
