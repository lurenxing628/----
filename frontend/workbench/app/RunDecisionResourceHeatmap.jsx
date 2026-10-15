(function () {
  'use strict';
  const C = window.RunCandidateControls, R = window.RunDecisionResources, T = window.WorkbenchTerms, F = window.WorkbenchFormat;
  const modes = [['after', '当前方案占用'], ['before', '对照占用'], ['delta', '占用差值']];
  const grains = { hour: '小时', shift: '班次', day: '天', week: '周' };
  function exactRange(value) { return F.dateTime(value.start, { seconds: true, fractions: true }) + ' 至 ' + F.dateTime(value.end, { seconds: true, fractions: true }); }
  function cellValue(cell, mode) { return mode === 'delta' ? cell.deltas.utilization_ratio : cell[mode].utilization_ratio; }
  function knownRest(value) { return value.calendar_state === 'complete' && value.available_hours === 0 && value.zero_capacity_task !== true && value.conflict !== true; }
  function cellText(cell, mode, baselineState = 'available') {
    if (mode === 'delta') return cell.deltas.utilization_ratio === null ? '待确认' : R.deltaText(cell.deltas.utilization_ratio, 'utilization_ratio');
    if (mode === 'before' && baselineState !== 'available') return '对照未记录';
    const value = cell[mode];
    if (value.available_hours === 0 && value.utilization_ratio === null) return value.zero_capacity_task === true ? '无可排时段仍有工作' : knownRest(value) ? '休息' : '待确认';
    if (value.utilization_ratio === null) return '待确认';
    return R.metricText(value, 'utilization_ratio');
  }
  function cellPresentation(row, cell, mode, pressureLabel = '高负荷', baselineState = 'available') {
    const missing = mode === 'before' && baselineState !== 'available', value = missing ? null : cellValue(cell, mode), text = cellText(cell, mode, baselineState), side = mode === 'delta' || missing ? null : cell[mode];
    const sides = (mode === 'delta' ? ['after', 'before'] : [mode]).map(key => ({ key, label: key === 'before' ? '固定对照' : '当前方案', value: cell[key] }));
    const warningFields = [
      ['high_pressure', pressureLabel, pressureLabel + '待确认'],
      ['zero_capacity_task', '无可排时段仍有工作', '无可排时段工作是否发生待确认'],
      ['demand_overload', '需求超载', '需求超载待确认'],
      ['conflict', '班表内冲突', '班表内冲突待确认']
    ];
    const signals = sides.flatMap(item => item.key === 'before' && baselineState !== 'available' ? [] : warningFields
      .filter(([field]) => item.value[field] === true || item.value[field] === null)
      .map(([field, known, unknown]) => ({ key: item.key + ':' + field, confirmed: item.value[field] === true, text: (mode === 'delta' ? item.label + '：' : '') + (item.value[field] === null ? unknown : known) })));
    const warnings = signals.filter(item => item.confirmed), unknowns = signals.filter(item => !item.confirmed);
    const facts = sides.map(item => item.label + (item.key === 'before' && baselineState !== 'available' ? '：基准缺失，归档可排 ' + R.scalar(item.value.available_hours) + ' 小时' :
      '：可排 ' + R.scalar(item.value.available_hours) + ' 小时，班表内占用 ' + R.scalar(item.value.occupied_hours) + ' 小时'
      + (mode === 'delta' ? '，占用比例 ' + R.metricText(item.value, 'utilization_ratio') : '')));
    const valueState = value === null ? side && side.available_hours === 0 && (side.zero_capacity_task === true || knownRest(side)) ? 'not_applicable' : 'unknown' : side ? side.state : 'complete';
    const pressure = side && (side.high_pressure === true || side.utilization_ratio >= 1 || cell.grain === 'week' && side.high_pressure_period_count > 0), zeroCapacity = side && side.zero_capacity_task === true, conflict = side && side.conflict === true;
    const status = side ? conflict ? side.overlap_hours === null ? '已确认重叠' : '重叠 ' + R.scalar(side.overlap_hours) + ' 小时' : zeroCapacity ? null : side.utilization_ratio >= 1 ? '满载' : side.high_pressure === true ? '接近满载' : side.demand_overload === true ? '需求超载' : null : null;
    const markers = mode === 'delta' ? sides.flatMap(item => item.key === 'before' && baselineState !== 'available' ? [] : item.value.conflict === true ? [(item.key === 'after' ? '当前' : '对照') + '有重叠'] : item.value.zero_capacity_task === true ? [(item.key === 'after' ? '当前' : '对照') + '无容量仍有工作'] : item.value.high_pressure === true ? [(item.key === 'after' ? '当前' : '对照') + '高负荷'] : []) : [];
    return { value, text, side, sides, warnings, unknowns, valueState, status, pressure, zeroCapacity, conflict, markers,
      name: (row.label || T.name_missing) + '，' + exactRange(cell) + '，' + modes.find(item => item[0] === mode)[1] + ' ' + text
        + '，' + facts.join('；') + (signals.length ? '；' + signals.map(item => item.text).join('，') : '') + '。按 Enter 查看时段安排。' };
  }
  function cellName(row, cell, mode, pressureLabel = '高负荷', baselineState = 'available') {
    return cellPresentation(row, cell, mode, pressureLabel, baselineState).name;
  }
  function cursor(row, cell) { return { resource_ref: row.resource_ref, bucket_key: cell.bucket_key, date: cell.date, start: cell.start, end: cell.end }; }
  function Heatmap({ data, definitions, mode = 'after', focus, onMode, onCursor, onFocus, onPage, onSize }) {
    const heatmap = data.heatmap, host = React.useRef(null), grain = heatmap.grain;
    const pressureLabel = R.metricDefinition('high_pressure_count', data.filters.resource_kind, definitions).label;
    const prepared = React.useMemo(() => {
      const resources = new Map(data.items.map(item => [item.resource_ref, item])), rowIndex = new Map();
      const rows = heatmap.items.map((row, index) => {
        rowIndex.set(row.resource_ref, index);
        const groups = new Map(), columns = new Map();
        row.cells.forEach((cell, column) => {
          columns.set(cell.bucket_key, column);
          if (!groups.has(cell.group_key)) groups.set(cell.group_key, { cells: [], continuations: [], byStart: new Map() });
          const group = groups.get(cell.group_key); group.cells.push({ cell, column }); if (!group.byStart.has(cell.start)) group.byStart.set(cell.start, column);
        });
        row.continuations.forEach(item => {
          if (!groups.has(item.group_key)) groups.set(item.group_key, { cells: [], continuations: [], byStart: new Map() });
          groups.get(item.group_key).continuations.push(item);
        });
        return { row, groups, columns, resource: resources.get(row.resource_ref) };
      });
      return { rows, rowIndex, first: rows.findIndex(value => value.row.cells.length) };
    }, [heatmap, data.items]);
    const presentations = React.useMemo(() => {
      const values = new Map(); let unknown = false;
      for (const { row } of prepared.rows) for (const cell of row.cells) {
        const value = cellPresentation(row, cell, mode, pressureLabel, data.baseline.state);
        values.set(cell, value); if (value.valueState === 'unknown') unknown = true;
      }
      return { values, unknown };
    }, [prepared, mode, pressureLabel, data.baseline.state]);
    const selectedRow = focus && prepared.rowIndex.has(focus.resource_ref) ? prepared.rowIndex.get(focus.resource_ref) : -1;
    const selectedCell = selectedRow >= 0 ? prepared.rows[selectedRow].columns.get(focus.bucket_key) : undefined;
    const cursorRow = selectedRow >= 0 ? selectedRow : prepared.first, cursorCell = selectedCell === undefined ? 0 : selectedCell;
    const shown = heatmap.display_scope, scopeLabel = grain === 'hour' ? '当前显示时段' : '所选日期范围';
    const peakLabel = grain === 'hour' ? '小时峰值' : grain === 'shift' ? '班段峰值' : '日峰值';
    function keyboard(event, row, column) {
      if (event.altKey || event.metaKey) return;
      let nextRow = row, nextColumn = column;
      if (event.key === 'ArrowRight') nextColumn = Math.min(column + 1, heatmap.items[row].cells.length - 1);
      else if (event.key === 'ArrowLeft') nextColumn = Math.max(0, column - 1);
      else if (event.key === 'ArrowDown') nextRow = Math.min(row + 1, heatmap.items.length - 1);
      else if (event.key === 'ArrowUp') nextRow = Math.max(0, row - 1);
      else if (event.key === 'Home') { nextColumn = 0; if (event.ctrlKey) nextRow = 0; }
      else if (event.key === 'End') { if (event.ctrlKey) nextRow = heatmap.items.length - 1; nextColumn = heatmap.items[nextRow].cells.length - 1; }
      else return;
      event.preventDefault();
      if (nextRow !== row && ['ArrowDown', 'ArrowUp'].includes(event.key)) {
        const origin = heatmap.items[row].cells[column], group = origin.group_key;
        const sameGroup = prepared.rows[nextRow].groups.get(group);
        if (sameGroup && sameGroup.cells.length) nextColumn = sameGroup.byStart.has(origin.start) ? sameGroup.byStart.get(origin.start) : sameGroup.cells[0].column;
      }
      nextColumn = Math.min(nextColumn, heatmap.items[nextRow].cells.length - 1);
      const target = host.current.querySelector('[data-heatmap-row="' + nextRow + '"][data-heatmap-column="' + nextColumn + '"]');
      if (target) {
        target.focus({ preventScroll: true }); target.scrollIntoView({ block: 'nearest', inline: 'nearest' });
        const owner = host.current, box = owner.getBoundingClientRect(), key = owner.querySelector('thead th.wb-col-key').getBoundingClientRect(), total = owner.querySelector('thead th.wb-col-actions').getBoundingClientRect(), cell = target.getBoundingClientRect();
        const top = box.top + owner.clientTop + key.height, left = box.left + owner.clientLeft + key.width, right = box.right - owner.clientLeft - total.width;
        if (cell.top < top) owner.scrollTop -= top - cell.top;
        if (cell.left < left) owner.scrollLeft -= left - cell.left;
        if (cell.right > right) owner.scrollLeft += cell.right - right;
        onCursor(cursor(heatmap.items[nextRow], heatmap.items[nextRow].cells[nextColumn]));
      }
    }
    return <section className="rres-heatmap" aria-label="资源时段热力图"><div className="rc-heading rres-display-controls"><span className="rres-window-note">{shown && shown.start && shown.end && <>显示 {F.compactRange(shown.start, shown.end)}{grain === 'hour' && ' · 筛选当前时段'}</>}</span><details className="rres-filter-details"><summary>显示设置</summary><div className="rc-tools"><label>显示<select aria-label="资源热力图指标" value={mode} onChange={event => onMode(event.target.value)}>{modes.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><label>每页<select aria-label="资源热力图日期每页" value={heatmap.page.size} onChange={event => onSize(Number(event.target.value))}>{[7, 14, 31].map(size => <option key={size} value={size}>{size} {grain === 'shift' ? '天' : grains[grain]}</option>)}</select></label></div></details></div>
      {heatmap.items.length && heatmap.buckets.length ? <div ref={host} className="wb-table-frame rres-heatmap-frame" data-sticky-head data-sticky-actions><table className="wb-table rres-heatmap-table" role="grid" aria-label={T.resource_kinds[data.filters.resource_kind] + '时段占用比例与安排'} style={{ '--rres-day-columns': heatmap.buckets.length }}><caption className="wb-visually-hidden">方向键移动，Home / End 到行首尾，Ctrl + Home / End 到图首尾；Enter 查看所选资源的真实时段安排</caption>
        <thead><tr><th scope="col" className="wb-col-key">{T.resource_kinds[data.filters.resource_kind]}</th>{heatmap.buckets.map(bucket => <th key={bucket.key} scope="col" title={exactRange(bucket)}>{bucket.label}</th>)}<th scope="col" className="rres-total-column wb-col-actions">{mode === 'delta' ? '范围占用差值' : mode === 'before' ? '对照范围平均' : '范围平均'}<small>{mode === 'before' ? '当前方案高负荷' : '高负荷时段'}</small></th></tr></thead>
        <tbody>{prepared.rows.map(({ row, groups, resource }, rowIndex) => { const summary = resource.filter_summary;
          return <tr key={row.resource_ref}><th scope="row" className="wb-col-key" data-current={focus && focus.resource_ref === row.resource_ref || undefined}><C.Button className="btn link" data-resource-entry={row.resource_ref} onClick={() => onFocus(row)}>{row.label || T.name_missing}</C.Button></th>{heatmap.buckets.map(bucket => {
            const { cells, continuations } = groups.get(bucket.key) || { cells: [], continuations: [] };
            return <td key={bucket.key} role="gridcell" aria-selected={cells.some(({ cell }) => focus && focus.resource_ref === row.resource_ref && focus.bucket_key === cell.bucket_key)}><div className="rres-period-cells">{continuations.map(item => <C.Button key={item.bucket_key} className="btn link rres-continuation" data-resource-continuation={item.bucket_key}
              aria-label={(row.label || T.name_missing) + '，班段延续 ' + F.compactRange(item.continuation_start, item.continuation_end) + '；查看原完整班段 ' + exactRange(item)} title={'原完整班段：' + exactRange(item)}
              onFocus={() => onCursor(cursor(row, item))} onClick={() => onFocus(row, item)}><span>班段延续</span><small>{F.compactRange(item.continuation_start, item.continuation_end)}</small></C.Button>)}{cells.map(({ cell, column: columnIndex }) => {
              const presentation = presentations.values.get(cell), { value, side } = presentation, selected = focus && focus.resource_ref === row.resource_ref && focus.bucket_key === cell.bucket_key;
              return <button key={cell.bucket_key} type="button" className="rres-day-cell" data-heatmap-row={rowIndex} data-heatmap-column={columnIndex} data-resource-ref={row.resource_ref} data-resource-date={cell.date} data-resource-bucket={cell.bucket_key}
                data-value-state={presentation.valueState} data-pressure={presentation.pressure || undefined} data-zero-capacity={presentation.zeroCapacity || undefined} data-conflict={presentation.conflict || undefined} data-change={mode === 'delta' && value !== null ? value > 0 ? 'increase' : value < 0 ? 'decrease' : 'equal' : undefined}
                style={{ '--rres-intensity': value === null ? 0 : 0.03 + Math.min(Math.abs(value), 1) * 0.22 }} aria-label={presentation.name} title={presentation.name} aria-pressed={!!selected} tabIndex={rowIndex === cursorRow && columnIndex === cursorCell ? 0 : -1}
                onFocus={() => onCursor(cursor(row, cell))} onKeyDown={event => keyboard(event, rowIndex, columnIndex)} onClick={() => onFocus(row, cell, columnIndex)}>
                {grain === 'shift' && <small>{F.compactRange(cell.start, cell.end)}</small>}<span>{presentation.text}</span>
                {grain === 'week' && presentation.sides.map(item => <small key={item.key}>{mode === 'delta' && item.label + '：'}日峰值 {R.scalar(item.value.daily_peak_utilization, 'utilization_ratio')} · 高负荷 {R.scalar(item.value.high_pressure_period_count)} 天</small>)}
                {presentation.status && (grain !== 'week' || presentation.conflict || presentation.zeroCapacity) && <small>{presentation.status}</small>}{presentation.markers.length > 0 && <small>{presentation.markers.join(' · ')}</small>}
              </button>;
            })}</div></td>;
          })}<td className="rres-resource-total wb-col-actions"><strong>{mode === 'delta' ? R.deltaText(resource.deltas.utilization_ratio, 'utilization_ratio') : mode === 'before' && data.baseline.state !== 'available' ? '对照未记录' : R.metricText(resource[mode], 'utilization_ratio')}</strong><small>{summary.high_pressure_period_count === 0 ? '暂无高负荷' : '高负荷 ' + R.scalar(summary.high_pressure_period_count) + ' ' + (grain === 'week' ? '天' : grains[grain])}</small>{grain === 'week' && <small>{peakLabel} {R.scalar(summary.daily_peak_utilization, 'utilization_ratio')}</small>}</td></tr>;
        })}</tbody></table></div> : <p className="rc-empty">{scopeLabel}没有符合筛选的资源记录。</p>}
      <div className="rc-heading"><div className="rres-heatmap-legend"><span><i className="rres-swatch" />班内占用</span><span><i className="rres-swatch rres-swatch-pressure" />高负荷 / 满载</span><span><i className="rres-swatch rres-swatch-conflict" />班内冲突</span><span><i className="rres-swatch rres-swatch-rest" />休息</span>{presentations.unknown && <span>待确认</span>}</div><C.Pager label="热力图日期" page={heatmap.page.number} pages={Math.max(1, Math.ceil(heatmap.page.total / heatmap.page.size))} onPage={onPage} /></div>
    </section>;
  }
  window.RunDecisionResourceHeatmap = { Heatmap, cellValue, cellText, cellName, cellPresentation, cursor };
})();
