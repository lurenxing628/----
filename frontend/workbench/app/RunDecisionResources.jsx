(function () {
  'use strict';
  const C = window.RunCandidateControls, D = window.RunDecisionComparison, M = window.RunCandidateModel, T = window.WorkbenchTerms, A = window.RunDecisionAPI, F = window.WorkbenchFormat;
  const leafKeys = ['resource_kind', 'resource_ref', 'pressure_filter', 'pressure_threshold', 'grain', 'display_start', 'display_end', 'sort', 'order', 'page', 'size', 'snapshot_ref', 'heatmap_page', 'heatmap_size', 'heatmap_mode', 'heatmap_focus', 'day_resource_ref', 'day_page', 'day_size', 'day_snapshot_ref', 'day_bucket_start', 'day_bucket_end', 'day_grain'];
  const ratios = new Set(['utilization_ratio', 'demand_ratio', 'peak_utilization', 'known_utilization_ratio']);
  const sorts = [['after_peak_utilization', '当前单日最高占用比例'], ['after_utilization', '当前班表内占用比例'], ['utilization_delta', '占用比例增幅'], ['after_demand_hours', '当前逐工序占用合计'], ['after_available_hours', '当前可排总时长'], ['label', '资源名称']];
  const pressureFilters = [['all', '全部资源'], ['high_pressure', '高负荷'], ['demand_overload', '需求超载'], ['zero_capacity', '无可排时段仍有工作'], ['conflicts', '班表内冲突'], ['unknown', '班表待确认']];
  const grains = [['hour', '小时'], ['shift', '班次'], ['day', '天'], ['week', '周']];
  function storedQuery(query, cohort, scope) {
    const stored = Object.fromEntries(Object.entries(query).filter(([key]) => leafKeys.includes(key))), next = A.savedResourceView(stored, cohort, scope), refs = cohort[next.resource_kind || 'machine'];
    if (next.day_resource_ref && !refs.includes(next.day_resource_ref)) { delete next.day_resource_ref; delete next.day_snapshot_ref; delete next.day_bucket_start; delete next.day_bucket_end; delete next.day_grain; next.day_page = 1; }
    if (next.heatmap_focus && !refs.includes(next.heatmap_focus.resource_ref)) delete next.heatmap_focus;
    if (scope && next.day_bucket_start && (next.day_bucket_start < scope.range_start || next.day_bucket_end > scope.range_end)) {
      delete next.day_bucket_start; delete next.day_bucket_end; delete next.day_grain; delete next.day_snapshot_ref; delete next.heatmap_focus; next.day_page = 1;
    }
    return next;
  }
  function scalar(value, key) { return value === null || value === undefined ? '未知' : ratios.has(key) ? window.WorkbenchFormat.percent(value) : M.number(value); }
  function metricState(value, key) { return value[key] !== null ? value.state : key === 'balance_cv' ? value.balance_state : ratios.has(key) && value.available_hours === 0 ? 'not_applicable' : value.state; }
  function metricText(value, key) { return value[key] === null && metricState(value, key) === 'not_applicable' ? ratios.has(key) && value.available_hours === 0 ? '不适用（无可排时段）' : '不适用' : scalar(value[key], key); }
  function deltaText(value, key) {
    if (value === null || value === undefined) return '差值未知';
    if (value === 0) return '持平';
    return D.deltaText({ value, state: 'comparable' }, { unit: ratios.has(key) ? '%' : key.endsWith('_hours') ? '小时' : '', precision: 3 });
  }
  function metricDefinition(field, kind, definitions = []) {
    const labels = { high_pressure_count: '高负荷' + (T.resource_kinds[kind] || '资源'), zero_capacity_task_count: '无可排时段仍有安排', conflict_resource_count: '安排重叠', unknown_day_resource_count: '班表待确认' };
    return definitions.find(row => row.key === kind + '_' + field) || { label: T.resource_metric_labels[field] || labels[field], unit: field.endsWith('_count') ? kind === 'machine' ? '台' : kind === 'operator' ? '人' : '项' : field.endsWith('_hours') ? '小时' : ratios.has(field) ? '%' : '' };
  }
  function metricLabel(field) { return field === 'outside_calendar_hours' ? '安排跨度跨非工作时段' : T.resource_metric_labels[field]; }
  function Metric({ value, field }) {
    const subtotal = value['known_' + field];
    return <><strong title={value[field] == null ? undefined : String(value[field])}>{metricText(value, field)}</strong>{value[field] === null && subtotal !== null && subtotal !== undefined && <small>已知小计 {scalar(subtotal, field)}</small>}
      {field === 'utilization_ratio' && value.numerator_hours !== null && value.denominator_hours !== null && <details className="rd-summary-basis"><summary>计算</summary><span>{scalar(value.numerator_hours)} / {scalar(value.denominator_hours)} 小时</span></details>}
      {field === 'balance_cv' && value.balance_reason && <small>{value.balance_reason.message}</small>}</>;
  }
  function Pair({ row, field, absent }) {
    return <><Metric value={row.after} field={field} /><small>基准 {absent && field !== 'available_hours' ? '缺失' : metricText(row.before, field)}</small><small>{deltaText(row.deltas[field], field)}</small></>;
  }
  function Flags({ value, kind, definitions }) {
    return <div className="rres-flags">{value.high_pressure === true && <span className="rd-badge rres-pressure">{metricDefinition('high_pressure_count', kind, definitions).label}</span>}{value.demand_overload === true && <span className="rd-badge rres-pressure">需求超载</span>}{value.zero_capacity_task === true && <span className="rd-badge rres-zero">无可排时段仍有工作</span>}{value.conflict === true && <span className="rd-badge rres-conflict">班表内安排冲突</span>}{value.unknown_days > 0 && <span className="rd-badge">班表待确认 {value.unknown_days} 天</span>}</div>;
  }
  function Summary({ data, definitions }) {
    const fields = ['available_hours', 'occupied_hours', 'utilization_ratio'];
    const kind = data.filters.resource_kind, unit = metricDefinition('used_resource_count', kind, definitions).unit;
    return <div className="rres-summary"><div className="wb-table-frame" data-sticky-head><table className="wb-table rres-summary-table" aria-label="资源使用汇总"><caption className="wb-visually-hidden">本次涉及资源在所选时间范围内的汇总</caption>
      <thead><tr><th scope="col">方案 / 涉及资源</th>{fields.map(field => <th scope="col" key={field}>{T.resource_metric_labels[field]}{field.endsWith('_hours') && <small>小时</small>}</th>)}<th scope="col">需关注的资源</th></tr></thead>
      <tbody>{[['before', '比较基准'], ['after', '当前方案']].map(([side, label]) => { const value = data.summary[side], absent = side === 'before' && data.baseline.state !== 'available'; return <tr key={side}><th scope="row">{label}<small>{absent ? '比较基准缺失' : '已安排 ' + scalar(value.used_resource_count) + ' / 涉及 ' + scalar(value.resource_count) + ' ' + unit}</small></th>
        {fields.map(field => <td key={field}>{absent && field !== 'available_hours' ? '比较基准缺失' : <Metric value={value} field={field} />}{side === 'after' && <small>{deltaText(data.summary.deltas[field], field)}</small>}</td>)}
        <td>{['high_pressure_count', 'zero_capacity_task_count', 'conflict_resource_count', 'unknown_day_resource_count'].map(field => { const def = metricDefinition(field, kind, definitions); return (value[field] === null || value[field] > 0) && <span key={field}>{def.label} {scalar(value[field])} {def.unit}{field === 'high_pressure_count' && value[field] === null && value.known_high_pressure_count !== null && <small>已知 {scalar(value.known_high_pressure_count)} {def.unit}</small>}</span>; })}</td></tr>; })}</tbody></table></div></div>;
  }
  function Calculation({ data, definitions }) {
    const fields = ['summed_load_hours', 'demand_ratio', 'balance_cv'];
    return <details className="rres-basis"><summary>详细占用统计与计算说明</summary><div className="wb-table-frame"><table className="wb-table"><thead><tr><th scope="col">方案</th>{fields.map(field => <th scope="col" key={field}>{T.resource_metric_labels[field]}{field.endsWith('_hours') && <small>小时</small>}</th>)}<th scope="col">班表资料</th></tr></thead><tbody>{[['before', '比较基准'], ['after', '当前方案']].map(([side, label]) => { const value = data.summary[side], absent = side === 'before' && data.baseline.state !== 'available'; return <tr key={side}><th scope="row">{label}</th>{fields.map(field => <td key={field}>{absent ? '比较基准缺失' : <Metric value={value} field={field} />}{side === 'after' && <small>{deltaText(data.summary.deltas[field], field)}</small>}</td>)}<td>已保存 {scalar(value.known_capacity_count)} · 待确认 {scalar(value.unknown_capacity_count)} 个</td></tr>; })}</tbody></table></div>
      <p>可排总时长来自保存的资源班表，未乘效率。班表内已占时间将同时占用的时段计一次；逐工序占用合计分别计算各道工序，重叠时会重复计入。两项除以可排总时长得到占用比例和需求比例，需求比例可超过 100%。高负荷用于关注资源使用情况，需求超载与资源冲突分别核对。</p>
      <p>本明细的高负荷关注线为 ≥{F.percent(data.filters.pressure_threshold)}。统计范围详细统计按单日班表内占用达到关注线的资源计一次；热力图按当前时间粒度展开，周保留高负荷天数。资源均衡度（CV）使用固定集合全部正容量资源，并按可排总时长加权，正容量空闲资源以 0 参与。</p>
      <p>安排保留跨度跨越休息时段时，跨休息部分继续保留在详情；其中可包含正常跨夜暂停。休息时段不计班表内加工占用，实际班外加工需保存的真实工作片段依据。统计范围占用比例按占用工时之和除以可排工时之和计算，热力图分页只改变当前显示时段。</p></details>;
  }
  function Coverage({ data }) {
    return <details className="rres-coverage"><summary>正式安排对照与未安排工序</summary>{[['before', '基准'], ['after', '当前方案']].map(([side, label]) => { const value = data.coverage[side], missing = T.missing_arrangements(value.unplanned_operation_refs.length, value.deferred_operation_refs.length);
      if (side === 'before' && data.baseline.state !== 'available') return <div key={side}><strong>{label}：</strong><span>{D.referenceNotice(data)}未安排工序与正式安排对照待确认。</span></div>;
      return <div key={side}><strong>{label}：</strong>{value.formal_state === 'absent' ? '排产时尚无正式计划。' : <>包含正式计划工序 {scalar(value.covered_formal_operation_count)} / {scalar(value.formal_operation_count)} 道{!value.formal_coverage_complete && ' · 还有正式工序未包含在内'}</>}
      {missing && <span>{missing}</span>}
      {value.missing_formal_arrangements.length > 0 && <details><summary>缺失的正式安排 · {value.missing_formal_operation_refs.length} 道工序</summary>{value.missing_formal_arrangements.map((item, index) => <div key={item.row_ref || item.operation_ref + ':' + index}>{item.batch_label} · {item.process_label || T.name_missing}</div>)}</details>}</div>; })}
      </details>;
  }
  function Locate({ row, onDrill }) {
    return onDrill && <div className="rd-locate"><C.Button icon="chart-gantt" className="mini" onClick={() => onDrill(row.drill.selected)}>查看当前甘特</C.Button><C.Button icon="chart-gantt" className="mini" disabled={!row.drill.reference} onClick={() => onDrill(row.drill.reference)}>查看对照甘特</C.Button></div>;
  }
  function ResourceTable({ data, definitions, onFocus, onDrill }) {
    const fields = ['available_hours', 'occupied_hours', 'utilization_ratio'], extraFields = ['summed_load_hours', 'demand_ratio', 'outside_calendar_hours', 'overlap_hours'];
    return <div className="rc-table wb-table-frame rres-table-frame" data-sticky-head data-sticky-actions><table className="wb-table rres-resource-table" aria-label="逐项资源影响"><caption className="wb-visually-hidden">当前方案、比较基准及差值，范围沿用上方时间选择</caption>
      <thead><tr><th scope="col" className="wb-col-key">{T.resource_kinds[data.filters.resource_kind]} / 逐日明细</th>{fields.map(field => <th scope="col" key={field}>{T.resource_metric_labels[field]}{field.endsWith('_hours') && <small>小时</small>}</th>)}<th scope="col">详细占用统计</th><th scope="col">单日最高占用比例 / 异常</th><th scope="col" className="wb-col-actions">定位甘特</th></tr></thead>
      <tbody>{data.items.map(row => <tr key={row.resource_ref} data-decision-resource={row.resource_ref}><td className="wb-col-key"><strong>{row.label || T.name_missing}</strong><C.Button icon="calendar-days" className="mini" onClick={() => onFocus(row)}>查看逐日</C.Button></td>
        {fields.map(field => <td key={field}><Pair row={row} field={field} absent={data.baseline.state !== 'available'} /></td>)}<td><details className="rres-day-facts"><summary>查看统计</summary>{extraFields.map(field => <div key={field}><strong>{metricLabel(field)}{field.endsWith('_hours') && ' · 小时'}</strong><Pair row={row} field={field} absent={data.baseline.state !== 'available'} /></div>)}</details></td><td><Pair row={row} field="peak_utilization" absent={data.baseline.state !== 'available'} /><Flags value={row.after} kind={data.filters.resource_kind} definitions={definitions} /><C.Reasons rows={row.after.issues} /></td>
        <td className="wb-col-actions"><Locate row={row} onDrill={onDrill} /></td></tr>)}</tbody></table></div>;
  }
  function Rankings({ data, onFocus, onAll }) {
    return <div className="rres-rankings">{[['top_pressure', '单日占用比例最高', 'after_peak_utilization'], ['top_increase', '占用比例增幅最大', 'utilization_delta']].map(([key, label, sort]) => <details key={key}><summary>{label} · 前 {data.rankings.limit} 个</summary><ol>{data.rankings[key].map(row => <li key={row.resource_ref}><C.Button className="btn link" onClick={() => onFocus(row)}>{row.label || T.name_missing}</C.Button><span>{key === 'top_pressure' ? metricText(row.after, 'peak_utilization') : deltaText(row.deltas.utilization_ratio, 'utilization_ratio')}</span></li>)}</ol><C.Button className="btn link" onClick={() => onAll(sort)}>在资源表展开全部</C.Button></details>)}</div>;
  }
  function DayFacts({ value, label, onDrill }) {
    return <details className="rres-day-facts"><summary>{label}：{value.tasks.length} 段安排记录{value.conflicts.length > 0 && ' · ' + value.conflicts.length + ' 段重叠'}</summary>
      {value.conflicts.map((item, index) => <div key={'conflict:' + index}><strong>重叠时段</strong><span title={F.dateTime(item.start, { seconds: true, fractions: true }) + ' 至 ' + F.dateTime(item.end, { seconds: true, fractions: true })}>{F.compactRange(item.start, item.end)}</span>{onDrill && <C.Button icon="chart-gantt" className="mini" onClick={() => onDrill(item.drill)}>定位重叠</C.Button>}</div>)}
      {value.tasks.map((item, index) => <div key={item.row_ref || item.operation_ref + ':' + index}>{item.batch_label} · {item.process_label || T.name_missing}<small title={F.dateTime(item.start, { seconds: true, fractions: true }) + ' 至 ' + F.dateTime(item.end, { seconds: true, fractions: true })}>{F.compactRange(item.start, item.end)}</small>{onDrill && <C.Button icon="chart-gantt" className="mini" onClick={() => onDrill(item.drill)}>定位工序</C.Button>}</div>)}{value.zero_capacity_reason && <p>{value.zero_capacity_reason.message}</p>}<C.Reasons rows={value.issues} /></details>;
  }
  function Days({ result, query, adapter, definitions, onQuery, onClose, onDrill }) {
    const data = result.data, fields = ['available_hours', 'occupied_hours', 'utilization_ratio'], extraFields = ['summed_load_hours', 'demand_ratio', 'outside_calendar_hours', 'overlap_hours'];
    return <section className="rres-days" aria-label="资源逐日数值明细"><div className="rc-heading"><h3>{T.resource_kinds[data.resource.kind]} · {data.resource.label || T.name_missing} · 逐日数值明细</h3><div className="rc-tools"><D.Export key={result.meta.snapshot_ref} adapter={adapter} result={result} initialSection="resource-days" filterQuery={{ ...query, ...data.filters }} /><C.Button icon="x" aria-label="关闭资源逐日明细" onClick={onClose} /></div></div>
      <div className="rc-table wb-table-frame rres-table-frame" data-sticky-head data-sticky-actions><table className="wb-table rres-days-table" aria-label="单资源逐日占用与重叠"><caption className="wb-visually-hidden">逐日数值明细、保存的工序安排与重叠定位</caption><thead><tr><th scope="col" className="wb-col-key">日期</th>{fields.map(field => <th key={field} scope="col">{T.resource_metric_labels[field]}{field.endsWith('_hours') && <small>小时</small>}</th>)}<th scope="col">详细占用统计</th><th scope="col">安排明细 / 异常</th><th scope="col" className="wb-col-actions">定位</th></tr></thead>
        <tbody>{data.items.map(day => <tr key={day.date} data-resource-date={day.date} data-selected={query.focus_date === day.date || undefined}><td className="wb-col-key"><strong>{F.date(day.date)}</strong><details className="rres-day-facts"><summary>计算时段</summary><span title={F.dateTime(day.start, { seconds: true, fractions: true }) + ' 至 ' + F.dateTime(day.end, { seconds: true, fractions: true })}>{F.compactRange(day.start, day.end)}</span><small>包含开始时间，结束时间不包含在内。</small></details></td>{fields.map(field => <td key={field}><Pair row={day} field={field} absent={data.baseline.state !== 'available'} /></td>)}
          <td><details className="rres-day-facts"><summary>查看统计</summary>{extraFields.map(field => <div key={field}><strong>{metricLabel(field)}{field.endsWith('_hours') && ' · 小时'}</strong><Pair row={day} field={field} absent={data.baseline.state !== 'available'} /></div>)}</details></td><td><Flags value={day.after} kind={data.resource.kind} definitions={definitions} /><DayFacts value={day.after} label="当前方案" onDrill={onDrill} /><DayFacts value={day.before} label="基准" onDrill={onDrill} /></td><td className="wb-col-actions"><Locate row={day} onDrill={onDrill} /></td></tr>)}</tbody></table></div>
      <div className="rc-heading"><label>每页 <select aria-label="资源逐日每页条数" value={data.page.size} onChange={event => onQuery({ size: Number(event.target.value) })}><option value="20">20 天</option><option value="50">50 天</option></select></label><C.Pager label="资源逐日" page={data.page.number} pages={Math.max(1, Math.ceil(data.page.total / data.page.size))} onPage={page => onQuery({ page }, true)} /></div></section>;
  }
  function SelectedWindow({ result, query, adapter, definitions, whole = false, onQuery, onClose, onWhole, onDrill, enabled = true }) {
    const data = result.data, cell = whole ? { ...data.summary, start: data.scope.range_start, end: data.scope.range_end } : data.items[0], value = cell.after, heading = React.useRef(null);
    const periods = whole ? data.items : [cell], hasTasks = periods.some(period => period.after.tasks.length > 0);
    React.useEffect(() => { if (enabled && heading.current) { heading.current.focus({ preventScroll: true }); heading.current.scrollIntoView({ block: 'start' }); } }, [enabled, data.resource.ref, cell.start, cell.end, whole]);
    return <section className="rres-selected-window" aria-label="所选资源时段安排"><div className="rc-heading"><div><h3 ref={heading} tabIndex={-1}>{data.resource.label || T.name_missing} · {whole ? '整个统计范围' : F.compactRange(cell.start, cell.end)}</h3>{whole && <p className="rres-window-note">{F.compactRange(cell.start, cell.end)}</p>}</div><div className="rc-tools"><D.Export key={result.meta.snapshot_ref} adapter={adapter} result={result} initialSection="resource-days" filterQuery={{ ...query, ...data.filters }} />{!whole && <C.Button icon="calendar-days" onClick={onWhole}>查看整个范围</C.Button>}<C.Button icon="x" aria-label="关闭资源时段安排" onClick={onClose} /></div></div>
      <div className="rres-contribution-summary"><div>班内已占 / 可排时长<strong>{scalar(value.occupied_hours)} / {scalar(value.available_hours)} 小时</strong></div><div>对照已占 · {data.baseline.label || '比较基准'}<strong>{data.baseline.state === 'available' ? scalar(cell.before.occupied_hours) + ' 小时' : '对照未记录'}</strong></div><div>{whole ? '占用比例' : '关联工序（道）'}<Metric value={value} field={whole ? 'utilization_ratio' : 'contribution_operation_count'} /></div></div>
      <Flags value={value} kind={data.resource.kind} definitions={definitions} />
      {whole && <p className="rres-window-note">以下为本页日期范围 · {data.display_scope ? F.compactRange(data.display_scope.start, data.display_scope.end) : '没有日期记录'}</p>}
      {hasTasks ? <div className="rres-contributions">{periods.map(period => period.after.tasks.length > 0 && <div className="rres-contribution-period" key={period.bucket_key || period.date}>{whole && <h4>{F.compactRange(period.start, period.end)}</h4>}{period.after.tasks.map((item, index) => <div className="rres-contribution-row" key={item.row_ref || item.operation_ref + ':' + index}>
        <div>{onDrill ? <C.Button className="btn link" data-resource-batch={item.batch_ref} onClick={() => onDrill({ ...item.drill, batch_ref: item.batch_ref, operation_ref: undefined, selected_row_ref: undefined })}>{item.batch_label || T.name_missing}</C.Button> : <strong>{item.batch_label || T.name_missing}</strong>}<span>{item.process_label || T.name_missing}</span></div><div><span title={F.dateTime(item.start, { seconds: true, fractions: true }) + ' 至 ' + F.dateTime(item.end, { seconds: true, fractions: true })}>{F.compactRange(item.start, item.end)}</span><small>本时段班内占用 {scalar(item.occupied_hours)} 小时</small></div>
        {onDrill && <C.Button icon="chart-gantt" className="mini" onClick={() => onDrill(item.drill)}>看甘特</C.Button>}</div>)}</div>)}</div> : <p className="rc-empty">{whole ? '当前显示日期' : '这个时段'}没有班表内工序占用。</p>}
      {whole && <div className="rc-heading rres-contribution-pages"><label>每页<select aria-label="资源贡献日期每页" value={data.page.size} onChange={event => onQuery({ size: Number(event.target.value) })}><option value="20">20 天</option><option value="50">50 天</option></select></label><C.Pager label="资源贡献日期" page={data.page.number} pages={Math.max(1, Math.ceil(data.page.total / data.page.size))} onPage={page => onQuery({ page }, true)} /></div>}
      {whole ? <details className="rres-basis"><summary>逐日数值</summary><Days adapter={adapter} result={result} definitions={definitions} query={query} onQuery={onQuery} onClose={onClose} onDrill={onDrill} /></details> : <details className="rres-basis"><summary>占用详情</summary><DayFacts value={cell.before} label="对照" onDrill={onDrill} />{value.conflicts.length > 0 && <div className="rres-day-facts"><strong>班内冲突 · {value.conflicts.length} 段</strong>{value.conflicts.map((item, index) => <div key={index}><span>{F.compactRange(item.start, item.end)}</span>{onDrill && <C.Button icon="chart-gantt" className="mini" onClick={() => onDrill(item.drill)}>看冲突甘特</C.Button>}</div>)}</div>}<p>占用按安排与已保存可排班段的交集计算。跨非工作时段的保留跨度 {scalar(value.outside_calendar_hours)} 小时；班内逐工序占用合计 {scalar(value.summed_load_hours)} 小时。</p>
        {value.reservations.length > 0 && <details className="rres-day-facts"><summary>保留安排记录与跨度 · {value.reservations.length} 段</summary>{value.reservations.map((item, index) => <div key={item.row_ref || index}><strong>{item.batch_label} · {item.process_label || T.name_missing}</strong><span>{F.compactRange(item.start, item.end)}</span><small>本时段保留跨度 {scalar(item.span_hours)} 小时 · 班内占用 {scalar(item.occupied_hours)} 小时</small></div>)}<Locate row={cell} onDrill={onDrill} /></details>}
        {value.reservation_overlaps.length > 0 && <div>{value.reservation_overlaps.map((item, index) => <p key={index}>保留安排重叠：{F.compactRange(item.start, item.end)}</p>)}</div>}{value.zero_capacity_reason && <p>{value.zero_capacity_reason.message}</p>}</details>}<C.Reasons rows={value.issues} />
    </section>;
  }
  function RangeControls({ scope, onRange, title = '资源范围', actionLabel = '应用范围' }) {
    const [value, setValue] = React.useState({ range_start: F.dateTime(scope.range_start, { seconds: true, fractions: true }), range_end: F.dateTime(scope.range_end, { seconds: true, fractions: true }) }), [error, setError] = React.useState(null), [open, setOpen] = React.useState(false), entry = React.useRef(null);
    React.useEffect(() => { setValue({ range_start: F.dateTime(scope.range_start, { seconds: true, fractions: true }), range_end: F.dateTime(scope.range_end, { seconds: true, fractions: true }) }); setError(null); }, [scope.range_start, scope.range_end]);
    function close() { setOpen(false); const button = entry.current && entry.current.querySelector('button'); if (button) button.focus({ preventScroll: true }); }
    function apply(event) {
      event.preventDefault();
      try {
        const time = window.WorkbenchDatePickerModel.factoryTime;
        const range_start = time(value.range_start), range_end = time(value.range_end);
        if (range_start >= range_end) throw new Error('请选择开始早于结束的资源时间范围。');
        setError(null); close(); onRange({ range_start, range_end });
      } catch (problem) { setError(problem); }
    }
    return <div className="rres-range-editor"><span ref={entry}><C.Button icon="calendar-days" data-resource-range-entry aria-expanded={open} onClick={() => setOpen(!open)}>统计时间 · {F.compactRange(scope.range_start, scope.range_end)}</C.Button></span>{open && <form className="rres-range-controls" onSubmit={apply} onKeyDown={event => { if (event.key === 'Escape') { event.preventDefault(); close(); } }}><label>开始（包含）<input type="text" data-picker-type="factory-local" aria-label={title + '开始'} value={value.range_start} onChange={event => setValue({ ...value, range_start: event.target.value.replace('T', ' ') })} /></label>
      <label>结束（不含）<input type="text" data-picker-type="factory-local" aria-label={title + '结束'} value={value.range_end} onChange={event => setValue({ ...value, range_end: event.target.value.replace('T', ' ') })} /></label><C.Button icon="check" type="submit">{actionLabel}</C.Button><C.Button onClick={close}>收起</C.Button><C.ErrorBox error={error} /></form>}</div>;
  }
  function Pane({ adapter, result, query = {}, onQuery, onView, onRange, onDrill, enabled = true }) {
    const overview = result.data, scope = overview.scope, runRef = overview.run.run_ref, host = React.useRef(null);
    const shared = { comparison_mode: scope.comparison_mode, resource_view: scope.resource_view, selected_candidate_ref: scope.selected_candidate_ref, range_start: scope.range_start, range_end: scope.range_end,
      ...(scope.comparison_mode === 'candidates' ? { reference_candidate_ref: scope.reference.candidate_ref } : {}) };
    const stored = storedQuery(query, scope.resource_refs, scope), q = A.resourceScope(runRef, { ...stored, heatmap_size: stored.heatmap_size || 7, ...shared });
    const storedKey = JSON.stringify(stored);
    React.useEffect(() => { if (!enabled) return; const prior = Object.fromEntries(Object.entries(query).filter(([key]) => leafKeys.includes(key))); if (JSON.stringify(prior) !== storedKey) onQuery(stored); }, [enabled, storedKey, JSON.stringify(query)]);
    const [paused, setPaused] = React.useState(false), [daysPaused, setDaysPaused] = React.useState(false);
    const consumed = React.useRef(null), qKey = JSON.stringify(q);
    const read = window.APSResourceSession.useQuery(signal => {
      if (signal && signal.aborted) throw new DOMException('读取已取消', 'AbortError');
      if (result.resource_result && consumed.current !== result
          && JSON.stringify(A.resourceScope(runRef, { ...result.resource_query, ...shared })) === qKey) {
        consumed.current = result;
        if (result.resource_result.ok === false) throw A.resourceError(result.resource_result);
        return result.resource_result;
      }
      return adapter.resources(runRef, { ...q, expected_resource_refs: scope.resource_refs }, signal);
    }, [adapter, runRef, qKey, result], enabled && !paused);
    const data = read.result && read.result.data;
    const activeFilters = [q.resource_ref && data && data.filter_options.resources.find(row => row.ref === q.resource_ref)?.label, !['all', 'high_pressure', 'conflicts'].includes(q.pressure_filter) && pressureFilters.find(row => row[0] === q.pressure_filter)[1]].filter(Boolean);
    const dayRef = stored.day_resource_ref, dayQ = dayRef ? A.resourceScope(runRef, { ...shared, resource_kind: q.resource_kind, resource_ref: dayRef, grain: stored.day_grain || 'day', bucket_start: stored.day_bucket_start, bucket_end: stored.day_bucket_end, pressure_threshold: q.pressure_threshold, page: stored.day_page || 1, size: stored.day_size || 20, snapshot_ref: stored.day_snapshot_ref }, 'resource-days') : null;
    const days = window.APSResourceSession.useQuery(signal => adapter.resourceDays(runRef, { ...dayQ, expected_resource_refs: scope.resource_refs }, signal), [adapter, runRef, JSON.stringify(dayQ), result], enabled && !!dayQ && !daysPaused);
    function change(value, type = 'filter') {
      const next = { ...stored, ...value };
      if (type === 'filter') { next.page = 1; delete next.snapshot_ref; }
      if (value.pressure_threshold !== undefined) delete next.day_snapshot_ref;
      if (['page', 'heatmap'].includes(type) && read.result) next.snapshot_ref = read.result.meta.snapshot_ref;
      if (type === 'heatmap' && q.grain === 'hour') { next.page = 1; delete next.snapshot_ref; }
      if (value.resource_kind || value.grain) { if (value.resource_kind) delete next.resource_ref; delete next.day_resource_ref; delete next.day_snapshot_ref; delete next.day_bucket_start; delete next.day_bucket_end; delete next.day_grain; delete next.heatmap_focus; next.day_page = 1; next.heatmap_page = 1; }
      if (value.grain && value.grain !== 'hour') { delete next.display_start; delete next.display_end; }
      setPaused(false); onQuery(next);
    }
    function refresh() { change({}); read.reload(); }
    function focus(row, cell) {
      const next = { ...stored, day_resource_ref: row.resource_ref, day_page: 1, day_grain: cell ? q.grain : 'day' };
      delete next.day_snapshot_ref;
      if (cell) { next.heatmap_focus = window.RunDecisionResourceHeatmap.cursor(row, cell); next.day_bucket_start = cell.start; next.day_bucket_end = cell.end; }
      else { next.heatmap_focus = { resource_ref: row.resource_ref }; delete next.day_bucket_start; delete next.day_bucket_end; }
      setDaysPaused(false); onQuery(next);
    }
    function dayQuery(value, paging = false) { const next = { ...stored, day_page: paging ? value.page : 1, ...(value.size ? { day_size: value.size } : {}) }; delete next.day_snapshot_ref; if (paging && days.result) next.day_snapshot_ref = days.result.meta.snapshot_ref; setDaysPaused(false); onQuery(next); }
    function closeDays() {
      const next = { ...stored }, owner = host.current, focus = stored.heatmap_focus;
      delete next.day_resource_ref; delete next.day_snapshot_ref; delete next.day_bucket_start; delete next.day_bucket_end; delete next.day_grain;
      if (owner) {
        const cell = focus && focus.resource_ref === dayRef && Array.from(owner.querySelectorAll('.rres-day-cell')).find(item => item.dataset.resourceRef === dayRef && item.dataset.resourceBucket === focus.bucket_key);
        const entry = Array.from(owner.querySelectorAll('[data-resource-entry]')).find(item => item.dataset.resourceEntry === dayRef);
        const target = cell || entry || owner.querySelector('select[aria-label="资源影响筛选资源"]:not(:disabled)') || owner;
        target.focus({ preventScroll: true }); target.scrollIntoView({ block: 'nearest', inline: 'nearest' });
      }
      onQuery(next);
    }
    function wholeDays() { const next = { ...stored, day_page: 1, day_grain: 'day', heatmap_focus: { resource_ref: dayRef } }; delete next.day_bucket_start; delete next.day_bucket_end; delete next.day_snapshot_ref; setDaysPaused(false); onQuery(next); }
    return <section ref={host} className="rres-pane" aria-label="资源使用对照" tabIndex={-1}><div className="rc-heading rres-business-heading"><div><h3>{scope.resource_view === 'selected_batches' ? '本次批次' : '完整安排'} · {T.resource_kinds[q.resource_kind]}占用</h3>{data && <p className="rc-muted">班内已排 <strong>{scalar(data.summary.after.occupied_hours)}</strong> / 可排 <strong>{scalar(data.summary.after.available_hours)}</strong> 小时</p>}</div><div className="rres-segment" role="group" aria-label="资源影响种类">{Object.entries(T.resource_kinds).map(([value, label]) => <C.Button key={value} aria-pressed={q.resource_kind === value} disabled={read.loading} onClick={() => change({ resource_kind: value })}>{label}</C.Button>)}</div></div>
      <div className="rres-time-controls"><div className="rres-grain-controls"><span>时间粒度</span><div className="rres-segment" role="group" aria-label="资源时间粒度">{grains.map(([value, label]) => <C.Button key={value} aria-pressed={q.grain === value} disabled={read.loading} onClick={() => change({ grain: value })}>{label}</C.Button>)}</div></div>{onRange && <RangeControls scope={scope} title="统计时间" onRange={onRange} />}</div>
      <div className="rd-detail-filters rres-primary-controls"><div className="rres-segment" role="group" aria-label="资源压力筛选">{[['all', '全部'], ['high_pressure', '高负荷'], ['conflicts', '冲突']].map(([value, label]) => <C.Button key={value} aria-pressed={q.pressure_filter === value} disabled={read.loading} onClick={() => change({ pressure_filter: value })}>{label}</C.Button>)}</div>
      <label>关注线<select aria-label="资源高负荷关注线" value={q.pressure_threshold} disabled={read.loading} onChange={event => change({ pressure_threshold: Number(event.target.value) })}>{Array.from(new Set([0.8, 0.85, 0.9, 0.95, 1, q.pressure_threshold])).sort((a, b) => a - b).map(value => <option key={value} value={value}>≥{F.percent(value)}</option>)}</select></label>
      <details className="rres-filter-details"><summary>更多筛选{activeFilters.length > 0 && ' · ' + activeFilters.join(' · ')}</summary><div className="rd-detail-filters">
      <label>统计对象<select aria-label="资源贡献范围" value={scope.resource_view} disabled={read.loading} onChange={event => { setPaused(false); setDaysPaused(false); onView(event.target.value); }}>{Object.entries(T.resource_views).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      <label>资源<select aria-label="资源影响筛选资源" value={q.resource_ref || ''} disabled={read.loading || !data} onChange={event => change({ resource_ref: event.target.value || undefined })}><option value="">全部{T.resource_kinds[q.resource_kind]}</option>{data && data.filter_options.resources.filter(row => row.kind === q.resource_kind).map(row => <option key={row.ref} value={row.ref}>{row.label || T.name_missing}</option>)}</select></label>
      <label>状态<select aria-label="资源全部状态筛选" value={q.pressure_filter} disabled={read.loading} onChange={event => change({ pressure_filter: event.target.value })}>{pressureFilters.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      <label>排序<select aria-label="资源影响排序" value={q.sort} disabled={read.loading} onChange={event => change({ sort: event.target.value })}>{sorts.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      <label>顺序<select aria-label="资源影响顺序" value={q.order} disabled={read.loading} onChange={event => change({ order: event.target.value })}><option value="desc">降序</option><option value="asc">升序</option></select></label>
      <label>每页<select aria-label="资源影响每页条数" value={q.size} disabled={read.loading} onChange={event => change({ size: Number(event.target.value) })}><option value="20">20 个</option><option value="50">50 个</option></select></label></div></details>
      <div className="rc-tools rd-detail-actions">{data && <D.Export key={read.result.meta.snapshot_ref} adapter={adapter} result={read.result} initialSection="resources" filterQuery={{ ...q, ...data.filters }} />}<C.Button icon="refresh-cw" aria-label="刷新资源影响" disabled={read.loading} onClick={refresh} /></div></div>
      {q.grain === 'hour' && stored.display_start && <C.Button className="btn link" disabled={read.loading} onClick={() => change({ display_start: undefined, display_end: undefined, heatmap_page: 1 })}>恢复整个统计范围</C.Button>}
      <C.ErrorBox error={read.error} />{read.loading && <div className="rc-tools"><span role="status">正在读取所选时间范围的资源使用情况。</span><C.Button icon="x" onClick={() => setPaused(true)}>取消读取</C.Button></div>}{paused && <p className="rc-muted" role="status">资源影响读取已取消，点击刷新继续。</p>}
      {data && <><C.Reasons rows={read.result.warnings} />
        <window.RunDecisionResourceHeatmap.Heatmap data={data} definitions={overview.metric_definitions} mode={stored.heatmap_mode || 'after'} focus={stored.heatmap_focus} onMode={heatmap_mode => change({ heatmap_mode }, 'presentation')} onCursor={heatmap_focus => change({ heatmap_focus }, 'presentation')} onFocus={focus} onPage={heatmap_page => change({ heatmap_page }, 'heatmap')} onSize={heatmap_size => change({ heatmap_size, heatmap_page: 1 }, 'heatmap')} />
        <div className="rc-heading rres-resource-pages"><span className="rc-muted">当前筛选 {data.page.total} 个资源</span><C.Pager label="资源影响" page={data.page.number} pages={Math.max(1, Math.ceil(data.page.total / data.page.size))} onPage={page => change({ page }, 'page')} /></div>
      </>}
      <C.ErrorBox error={days.error} />{days.loading && <div className="rc-tools"><span role="status">正在读取资源逐日数值与重叠安排。</span><C.Button icon="x" onClick={() => setDaysPaused(true)}>取消逐日读取</C.Button></div>}
      {daysPaused && <div className="rc-tools"><span role="status">资源逐日读取已取消。</span><C.Button icon="refresh-cw" onClick={() => { setDaysPaused(false); days.reload(); }}>继续读取逐日</C.Button></div>}
      {days.error && <div className="rc-tools"><C.Button icon="refresh-cw" onClick={() => { setDaysPaused(false); days.reload(); }}>重试逐日读取</C.Button><C.Button onClick={closeDays}>关闭逐日明细</C.Button></div>}
      {days.result && <SelectedWindow adapter={adapter} result={days.result} definitions={overview.metric_definitions} query={{ ...dayQ, focus_date: stored.heatmap_focus && stored.heatmap_focus.resource_ref === dayRef ? stored.heatmap_focus.date : null }} whole={!stored.day_bucket_start} onQuery={dayQuery} onClose={closeDays} onWhole={wholeDays} onDrill={onDrill} enabled={enabled} />}
      {data && <details className="rres-statistics"><summary>数据来源</summary><div className="rres-full-table"><h3>统计范围详细对照 · {data.page.total} 个资源</h3><Summary data={data} definitions={overview.metric_definitions} />
        {data.items.length ? <ResourceTable data={data} definitions={overview.metric_definitions} onFocus={focus} onDrill={onDrill} /> : <p className="rc-empty">当前筛选没有资源记录。</p>}</div>
        <Coverage data={data} /><Calculation data={data} definitions={overview.metric_definitions} /><Rankings data={data} onFocus={focus} onAll={sort => change({ sort, order: 'desc', resource_ref: undefined })} /></details>}
    </section>;
  }
  window.RunDecisionResources = { Pane, ResourceTable, Days, SelectedWindow, Summary, Coverage, RangeControls, scalar, metricState, metricText, deltaText, metricDefinition, Flags, storedQuery };
})();
