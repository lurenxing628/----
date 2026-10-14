(function () {
  'use strict';
  const completionKeys = ['expected_operation_count', 'missing_operation_count', 'unexpected_result_count', 'complete_batch_count', 'incomplete_batch_count'];
  const known = value => typeof value === 'number' && Number.isFinite(value);
  const knownDimension = value => value !== null && value !== undefined && value !== '' && value !== 'unknown' && (typeof value !== 'number' || known(value));
  const flagLabels = { first_valid: '首次有效结果', first_expected_complete: '本次计算范围首次排齐', final: '最终记录', strict_improvement: '评分改善', segment_start: '开始新的比较' };
  const phaseLabels = { baseline: '起始排法', initial: '起始排法', multi_start: '尝试不同排法', multi_start_search: '尝试不同排法', profiles: '按规则生成排法', elite_repair: '局部调整排法', iterated_greedy: '继续调整工序顺序', graph_ready: '按优先顺序安排工序', graph_ready_search: '按优先顺序安排工序', graph_ready_elite_repair: '局部调整排法', graph_ready_iterated_greedy: '继续调整工序顺序', graph_ready_v2_generated: '生成优化排法', graph_ready_v2_repaired: '修整优化排法', graph_ready_v2_iterated_greedy: '继续改进排法', ortools_warmstart: '生成优化起点', heuristic_candidate_search: '尝试不同工序顺序', grasp_ig_candidate_construction: '构建并调整排法', local_search: '调整已有排法', completed: '计算结束' };
  const phaseText = value => value === null ? '阶段未记录' : phaseLabels[value] || '其他搜索阶段';
  const anchorFlags = ['first_valid', 'first_expected_complete', 'final'];
  const flagsText = point => point.flags.map(flag => flagLabels[flag] || flag).join('、');
  const formatter = new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 6 });
  const number = value => known(value) ? formatter.format(value) : '—';
  const elapsed = value => !known(value) ? '—' : value >= 1000 ? number(value / 1000) + ' 秒' : number(value) + ' 毫秒';
  const metricLabel = objective => objective && objective.primary_metric_label || '主指标（名称未记录）';
  const metricUnit = objective => objective && objective.unit || '';
  const metricValue = (value, objective) => (known(value) ? String(value) : '—') + (known(value) && metricUnit(objective) ? ' ' + metricUnit(objective) : '');
  const verifiedLabel = point => point.verified === true ? '已核验' : point.verified === false ? '未核验' : '核验 —';
  function scopeText(value) {
    switch (value) {
      case 'all_batches': return '本次参与计算的全部批次';
      case 'completed_batches_only': return '本次计算范围内工序已排齐的批次';
      case 'unknown': return '未知';
      case null: case undefined: return '评价范围未记录';
      default: return '其他评价范围（' + value + '）';
    }
  }
  function sameScope(left, right) {
    const scopeKeys = ['source_candidate_ref', 'objective_scope'];
    const before = left.evaluation_scope, after = right.evaluation_scope;
    return !!(scopeKeys.every(key => knownDimension(left[key]) && left[key] === right[key])
      && before && after && Array.isArray(before.incomplete_batch_ids) && Array.isArray(after.incomplete_batch_ids)
      && before.incomplete_batch_ids.length === after.incomplete_batch_ids.length
      && before.incomplete_batch_ids.every((batch, index) => batch === after.incomplete_batch_ids[index])
      && completionKeys.every(key => known(left.completion[key]) && known(right.completion[key])
      && left.completion[key] === right.completion[key]));
  }
  // Saved incumbent events stay continuous across search phases; evaluation coverage remains separate.
  function segments(progress, value = point => point.primary_value) {
    if (progress.mode !== 'curve') return [];
    const groups = []; let group = [];
    const finish = () => { if (group.length > 1) groups.push(group); group = []; };
    progress.points.forEach(point => {
      if (!known(point.elapsed_ms) || !known(value(point)) || point.verified !== true) { finish(); return; }
      if (group.length && !sameScope(group[group.length - 1], point)) finish();
      group.push(point);
    });
    finish(); return groups;
  }
  // Actual boundaries between adjacent saved points with time/value coordinates on both sides.
  function markers(progress) {
    if (!['curve', 'discrete'].includes(progress.mode)) return [];
    const result = [];
    progress.points.forEach((point, index) => {
      if (!index) return;
      const before = progress.points[index - 1];
      if (![before.elapsed_ms, point.elapsed_ms, before.primary_value, point.primary_value].every(known)) return;
      const changes = [];
      if (knownDimension(before.phase) && knownDimension(point.phase) && before.phase !== point.phase) changes.push('phase');
      if (knownDimension(before.phase) && before.phase === point.phase && known(before.phase_visit) && known(point.phase_visit) && before.phase_visit !== point.phase_visit) changes.push('phase_visit');
      if (knownDimension(before.segment) && knownDimension(point.segment) && before.segment !== point.segment) changes.push('segment');
      if (before.evaluation_scope && point.evaluation_scope
        && (before.evaluation_scope.incomplete_batch_ids.length !== point.evaluation_scope.incomplete_batch_ids.length
          || before.evaluation_scope.incomplete_batch_ids.some((batch, member) => batch !== point.evaluation_scope.incomplete_batch_ids[member]))) changes.push('evaluation_scope');
      if (completionKeys.every(key => known(before.completion[key]) && known(point.completion[key]))
        && completionKeys.some(key => before.completion[key] !== point.completion[key])) changes.push('completion');
      if (changes.length) result.push({ before, point, changes });
    });
    return result;
  }
  function markerText({ before, point, changes }) {
    const labels = { expected_operation_count: '参与计算工序', missing_operation_count: '计算范围内未安排工序', unexpected_result_count: '计算范围外结果', complete_batch_count: '计算范围内已排齐批次', incomplete_batch_count: '计算范围内未排齐批次' };
    const descriptions = changes.map(change => change === 'phase' ? '阶段：' + phaseText(before.phase) + ' → ' + phaseText(point.phase)
      : change === 'phase_visit' ? '搜索次数：' + phaseText(point.phase) + '，' + before.phase_visit + ' → ' + point.phase_visit
      : change === 'segment' ? '开始新的比较' : change === 'evaluation_scope' ? '评价排除批次：' + (before.evaluation_scope.incomplete_batch_ids.join('、') || '无') + ' → ' + (point.evaluation_scope.incomplete_batch_ids.join('、') || '无')
        : '工序安排：' + completionKeys.filter(key => before.completion[key] !== point.completion[key]).map(key => labels[key] + ' ' + before.completion[key] + ' → ' + point.completion[key]).join('、'));
    return '事件 ' + number(point.event_index) + '，累计求解 ' + elapsed(point.elapsed_ms) + '（' + point.elapsed_ms + ' ms）；' + descriptions.join('；') + '。';
  }
  function pointText(point, index, total, objective) {
    const completion = point.completion, scopeDescription = scopeText(point.objective_scope);
    return '第 ' + (index + 1) + ' / ' + total + ' 个保存点，事件 ' + number(point.event_index)
      + '；累计计算 ' + elapsed(point.elapsed_ms) + (known(point.elapsed_ms) ? '（' + point.elapsed_ms + ' ms）' : '')
      + '；' + metricLabel(objective) + ' ' + metricValue(point.primary_value, objective)
      + '；' + (scopeDescription.startsWith('评价范围') ? scopeDescription : '评价范围：' + scopeDescription)
      + '；评价集合：' + (point.evaluation_scope ? point.evaluation_scope.incomplete_batch_ids.length ? '排除批次 ' + point.evaluation_scope.incomplete_batch_ids.join('、') : '没有排除批次' : '未记录')
      + '；阶段 ' + phaseText(point.phase)
      + '；本次参与计算 ' + number(completion.expected_operation_count) + ' 道工序，其中未安排 ' + number(completion.missing_operation_count)
      + ' 道；本次计算范围内已排齐 ' + number(completion.complete_batch_count) + ' 批、未排齐 ' + number(completion.incomplete_batch_count) + ' 批；本次计算范围外结果 ' + number(completion.unexpected_result_count) + '；' + verifiedLabel(point)
      + (point.flags.length ? '；事件标记：' + flagsText(point) : '') + '。';
  }
  const businessMetrics = ['overdue_count', 'total_tardiness_hours', 'weighted_tardiness_hours', 'makespan_hours', 'changeover_count'];
  const metricLabels = { overdue_count: '算法超期批次', total_tardiness_hours: '算法拖期小计', weighted_tardiness_hours: '算法加权拖期', makespan_hours: '已排跨度', changeover_count: '算法工种切换' };
  function metricChoices(objective) {
    const primary = { key: objective.primary_metric_key, label: metricLabels[objective.primary_metric_key] || metricLabel(objective), unit: metricUnit(objective), primary: true };
    return [primary, ...objective.score_fields.filter(field => businessMetrics.includes(field.key) && field.key !== primary.key && Number.isInteger(field.index)).map(field => ({ ...field, label: metricLabels[field.key] || field.label }))];
  }
  function savedValue(point, definition) { return definition.primary ? point.primary_value : Number.isInteger(definition.index) && known(point.score[definition.index]) ? point.score[definition.index] : null; }
  function pointName(point, index, mode) {
    if (point.flags.includes('first_valid') && point.flags.includes('final')) return '首个有效方案 / 最终结果';
    if (point.flags.includes('first_valid')) return '首个有效方案';
    if (point.flags.includes('final')) return '最终结果';
    if (point.flags.includes('strict_improvement')) return '评分改善';
    return (mode === 'discrete' ? '旧保存点 ' : '保存点 ') + (index + 1);
  }
  function timeRange(progress, elapsedMs) {
    const times = progress.points.map(point => point.elapsed_ms).filter(known);
    const full = Math.max(0, ...(known(elapsedMs) ? [elapsedMs] : []), ...times);
    const last = progress.points.filter(point => point.flags.includes('strict_improvement') && known(point.elapsed_ms)).slice(-1)[0];
    return { full, improvements: last && last.elapsed_ms > 0 ? Math.min(full, last.elapsed_ms * 1.5) : full, lastImprovement: last || null };
  }
  function nearestPoint(plotted, value, xValue) {
    if (!plotted.length) return null;
    return plotted.reduce((best, item) => Math.abs(xValue(item.point) - value) < Math.abs(xValue(best.point) - value) ? item : best, plotted[0]);
  }
  function stepPath(group, x, y, end = null) {
    let path = group.map((point, index) => index ? 'H' + x(point).toFixed(3) + ' V' + y(point).toFixed(3) : 'M' + x(point).toFixed(3) + ' ' + y(point).toFixed(3)).join(' ');
    if (group.length && end !== null && x(group[group.length - 1]) < end) path += ' H' + end.toFixed(3);
    return path;
  }
  function domain(values) {
    if (!values.length) return null;
    const min = Math.min(...values), max = Math.max(...values), padding = Math.max((max - min) * 0.12, max === min ? Math.max(Math.abs(min) * 0.02, 0.5) : 0);
    return { min: Math.max(0, min - padding), max: max + padding };
  }
  function ticks(range) { return range ? Array.from({ length: 5 }, (_, index) => range.min + (range.max - range.min) * index / 4) : []; }
  function ratio(value, range) { return range.min === range.max ? 0.5 : (value - range.min) / (range.max - range.min); }
  function Chart({ progress, objective, elapsedMs = null, attempts = [] }) {
    const id = React.useId(), svg = React.useRef(null), [selection, setSelection] = React.useState(null), [metricKey, setMetricKey] = React.useState(objective.primary_metric_key), [windowMode, setWindowMode] = React.useState('full'), [showAttempts, setShowAttempts] = React.useState(false);
    const points = progress.points, mode = progress.mode, definitions = metricChoices(objective), definition = definitions.find(field => field.key === metricKey) || definitions[0];
    const value = point => savedValue(point, definition), viewedObjective = { ...objective, primary_metric_label: definition.label, unit: definition.unit };
    const eventAxis = mode === 'discrete' && points.length > 0 && points.every(point => !known(point.elapsed_ms));
    const xValue = point => eventAxis ? point.event_index : point.elapsed_ms, range = timeRange(progress, elapsedMs), activeWindow = mode === 'curve' && range.lastImprovement ? windowMode : 'full', limit = activeWindow === 'improvements' ? range.improvements : range.full;
    const plotted = mode === 'none' ? [] : points.map((point, index) => ({ point, index })).filter(item => known(xValue(item.point)) && known(value(item.point)) && (eventAxis || xValue(item.point) <= limit));
    const scatter = showAttempts && !eventAxis ? attempts.filter(point => known(point.elapsed_ms) && point.elapsed_ms <= limit && known(value(point))) : [];
    const eventValues = eventAxis ? points.map(xValue).filter(known) : [];
    const xDomain = eventAxis ? { min: eventValues.length ? Math.min(...eventValues) : 0, max: eventValues.length ? Math.max(...eventValues) : 1 } : { min: 0, max: limit || 1 };
    const yDomain = domain([...plotted.map(item => value(item.point)), ...scatter.map(value)]);
    const cursor = selection && selection.progress === progress ? Math.min(selection.index, Math.max(0, points.length - 1)) : 0, selected = points[cursor];
    const x = point => 8 + ratio(xValue(point), xDomain) * 784, y = point => 232 - ratio(value(point), yDomain) * 224;
    const sampled = mode === 'curve' && progress.sampling && known(progress.sampling.event_total_count) && progress.sampling.event_total_count > points.length;
    function choose(index) {
      if (windowMode === 'improvements' && points[index] && known(points[index].elapsed_ms) && points[index].elapsed_ms > limit) setWindowMode('full');
      if (!selection || selection.progress !== progress || index !== cursor) setSelection({ progress, index });
    }
    function keyboard(event) {
      if (!points.length || event.altKey || event.metaKey) return;
      let next;
      if (event.key === 'ArrowRight' || event.key === 'ArrowDown') next = Math.min(cursor + 1, points.length - 1);
      else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') next = Math.max(cursor - 1, 0);
      else if (event.key === 'Home') next = 0;
      else if (event.key === 'End') next = points.length - 1;
      else return;
      event.preventDefault(); choose(next);
    }
    function pointer(event) {
      if (!svg.current || !plotted.length) return;
      const box = svg.current.getBoundingClientRect(), relative = (event.clientX - box.left) / box.width * 800;
      if (relative < 8 || relative > 792) return;
      const found = nearestPoint(plotted, xDomain.min + (relative - 8) / 784 * (xDomain.max - xDomain.min), xValue);
      if (found) choose(found.index);
    }
    const lineGroups = segments(progress, value).map(group => group.filter(point => point.elapsed_ms <= limit)).filter(group => group.length > 1);
    const phaseMarkers = markers(progress).filter(marker => known(value(marker.point)) && marker.point.elapsed_ms <= limit);
    const xTicks = eventAxis && plotted.length ? [...new Set([0, Math.floor((plotted.length - 1) / 4), Math.floor((plotted.length - 1) / 2), Math.floor((plotted.length - 1) * 3 / 4), plotted.length - 1].map(index => xValue(plotted[index].point)))] : ticks(xDomain);
    const xLabel = eventAxis ? '已保存事件顺序（累计计算耗时未记录）' : '累计计算耗时', chartLabel = definition.label + (definition.unit ? '（' + definition.unit + '）' : '');
    const initial = points.find(point => point.flags.includes('first_valid')), final = points.find(point => point.flags.includes('final'));
    const selectedPlotted = plotted.find(item => item.index === cursor), selectionText = selected ? pointText({ ...selected, primary_value: value(selected) }, cursor, points.length, viewedObjective) : '当前没有保存的过程点。';
    const lastVisible = plotted.length ? plotted[plotted.length - 1].point : null, nextSaved = lastVisible ? points[points.indexOf(lastVisible) + 1] : null;
    const continueToEnd = lastVisible === final || windowMode === 'improvements' && nextSaved && nextSaved.verified === true && sameScope(lastVisible, nextSaved);
    return <figure className="rd-process-chart" data-progress-mode={mode} data-progress-axis={eventAxis ? 'event_index' : 'elapsed_ms'} data-process-metric={definition.key} data-process-window={activeWindow}>
      <div className="rd-process-chart-toolbar"><figcaption className="rd-process-chart-caption" id={id + '-caption'}>{mode === 'curve' ? '保留方案的计算过程' : '已保存过程记录'}</figcaption><label>观察指标<select aria-label="计算过程观察指标" value={definition.key || ''} onChange={event => setMetricKey(event.target.value)}>{definitions.map(field => <option key={field.key || 'unknown'} value={field.key || ''}>{field.label}{field.unit ? '（' + field.unit + '）' : ''}</option>)}</select></label></div>
      <div className="rd-process-chart-summary"><div><span>{mode === 'discrete' ? '首个保存点' : '首个有效方案'}</span><strong>{number(value(mode === 'discrete' ? points[0] || { primary_value: null, score: [] } : initial || { primary_value: null, score: [] }))}</strong>{definition.unit && ' ' + definition.unit}</div><div><span>{mode === 'discrete' ? '末个保存点' : '最终结果'}</span><strong>{number(value(mode === 'discrete' ? points[points.length - 1] || { primary_value: null, score: [] } : final || { primary_value: null, score: [] }))}</strong>{definition.unit && ' ' + definition.unit}</div>{range.lastImprovement && <div><span>最后一次评分改善</span><strong>{number(range.lastImprovement.elapsed_ms / 1000)}</strong> 秒</div>}</div>
      {mode !== 'curve' && <p className="rd-process-chart-note">{mode === 'discrete' ? '旧记录按已保存的离散结果点显示，首末点按保存顺序表示。' : '计算进展未保存。'}</p>}
      {mode === 'curve' && points.some(point => !point.evaluation_scope) && <p className="rd-process-chart-note" data-process-scope-missing>部分保存点的评价集合未记录，按离散点显示；保存事件条数和采样覆盖在记录说明中单列。</p>}
      {(mode === 'curve' || !eventAxis && attempts.some(point => known(point.elapsed_ms))) && <div className="rd-process-chart-controls">{mode === 'curve' ? <div className="rc-tabs" role="group" aria-label="计算过程显示范围">{[['improvements', '改善阶段', range.improvements], ['full', '全过程', range.full]].map(([key, label, end]) => <window.RunCandidateControls.Button key={key} aria-pressed={activeWindow === key} disabled={key === 'improvements' && !range.lastImprovement} onClick={() => setWindowMode(key)}>{label} · {key === 'improvements' && !range.lastImprovement ? '无改善记录' : elapsed(end)}</window.RunCandidateControls.Button>)}</div> : <span>按真实保存时刻显示</span>}{attempts.length > 0 && <label><input type="checkbox" checked={showAttempts} onChange={event => setShowAttempts(event.target.checked)} />显示代表尝试点（{attempts.length} 条）</label>}</div>}
      {mode !== 'none' && points.length > 0 && <>
        <div className="rd-process-plot">
          <div className="rd-process-y-axis" aria-hidden="true">{ticks(yDomain).map(tick => <span key={tick} style={{ top: (8 + (1 - ratio(tick, yDomain)) * 224) / 240 * 100 + '%' }} title={String(tick) + (definition.unit ? ' ' + definition.unit : '')}>{window.WorkbenchFormat.number(tick, { digits: 1, trim: true })}</span>)}</div>
          <div className="rd-process-svg-host"><svg ref={svg} className="rd-process-svg" viewBox="0 0 800 240" preserveAspectRatio="none" role="group" tabIndex={0} aria-labelledby={id + '-caption'} aria-describedby={id + '-keys ' + id + '-selected'} onKeyDown={keyboard} onPointerMove={pointer}>
            <title>{chartLabel}；{xLabel}</title>
            {ticks(yDomain).map(tick => <line className="rd-process-gridline" key={tick} x1="8" x2="792" y1={232 - ratio(tick, yDomain) * 224} y2={232 - ratio(tick, yDomain) * 224} vectorEffect="non-scaling-stroke" aria-hidden="true" />)}
            {phaseMarkers.map((marker, index) => <line className="rd-process-phase-marker" key={index} x1={x(marker.point)} x2={x(marker.point)} y1="8" y2="232" strokeWidth="1" strokeDasharray="3 4" vectorEffect="non-scaling-stroke" aria-hidden="true" data-process-phase={marker.point.phase} data-process-changes={marker.changes.join(' ')}><title>{markerText(marker)}</title></line>)}
            {lineGroups.map((group, index) => <path className="rd-process-line" key={index} data-sampled={sampled || undefined} d={stepPath(group, x, y, continueToEnd && group[group.length - 1] === lastVisible ? 792 : null)} fill="none" vectorEffect="non-scaling-stroke" aria-hidden="true" />)}
            {scatter.map(point => <circle className="rd-process-attempt-point" key={point.saved_index} cx={x(point)} cy={y(point)} r="3" vectorEffect="non-scaling-stroke" aria-hidden="true" data-process-attempt-index={point.saved_index}><title>已保存代表尝试 {point.saved_index} · {elapsed(point.elapsed_ms)} · {definition.label} {number(value(point))}{definition.unit && ' ' + definition.unit} · {verifiedLabel(point)}</title></circle>)}
            {selectedPlotted && <line className="rd-process-guide" x1={x(selected)} x2={x(selected)} y1="8" y2="232" strokeDasharray="3 4" vectorEffect="non-scaling-stroke" aria-hidden="true" />}
            {plotted.map(({ point, index }) => <circle className="rd-process-point" key={index} cx={x(point)} cy={y(point)} r={index === cursor ? 6 : 4} vectorEffect="non-scaling-stroke" focusable="false" aria-hidden="true" data-progress-event-index={point.event_index} data-progress-flags={point.flags.join(' ')} data-primary-value={point.primary_value} data-metric-value={value(point)} data-verified={point.verified === null ? 'unknown' : String(point.verified)} data-selected={index === cursor || undefined} onClick={() => { choose(index); if (svg.current) svg.current.focus({ preventScroll: true }); }}><title>{pointText({ ...point, primary_value: value(point) }, index, points.length, viewedObjective)}{' '}观察值原数：{String(value(point))}。</title></circle>)}
          </svg></div>
          <div className="rd-process-x-axis" aria-hidden="true">{xTicks.map(tick => <span key={tick} style={{ left: (8 + ratio(tick, xDomain) * 784) / 800 * 100 + '%' }} title={String(tick) + (eventAxis ? '（事件顺序）' : ' ms')}>{eventAxis ? number(tick) : elapsed(tick)}</span>)}</div>
        </div>
        <p className="rd-process-axis-title">{xLabel} · {chartLabel}</p>
        <div className="rd-process-chart-legend"><span>{lineGroups.length ? sampled ? '采样后的保留方案趋势' : '当时保留的方案' : '真实保存点'}</span>{showAttempts && <span>灰点：已保存代表尝试</span>}{sampled && <span>已保存 {points.length} / {progress.sampling.event_total_count} 个事件；虚线间存在未保存变化。</span>}<span>选择或悬停定位真实保存时刻。</span></div>
        {!plotted.length && <p className="rd-process-chart-note">所选指标或耗时缺项，当前没有可定位的点；仍可用键盘查看保存详情。</p>}
        <div className="rd-process-point-picker"><window.RunCandidateControls.Button aria-label="上一个过程保存点" disabled={cursor === 0} onClick={() => choose(Math.max(0, cursor - 1))}>←</window.RunCandidateControls.Button><label htmlFor={id + '-point'}>记录点</label><input id={id + '-point'} type="range" min="0" max={points.length - 1} step="1" value={cursor} aria-label="查看过程保存点" onChange={event => choose(Number(event.target.value))} /><span>{cursor + 1} / {points.length}</span><window.RunCandidateControls.Button aria-label="下一个过程保存点" disabled={cursor === points.length - 1} onClick={() => choose(Math.min(points.length - 1, cursor + 1))}>→</window.RunCandidateControls.Button></div>
        <p className="rd-process-chart-keys wb-visually-hidden" id={id + '-keys'}>聚焦图表后，用方向键选择保存点，Home / End 到首末点；点击、悬停和记录点选择均定位真实保存时刻。</p>
      </>}
      {selected && <div className="rd-process-point-card"><div><strong>{pointName(selected, cursor, mode)} · 保存于 {elapsed(selected.elapsed_ms)}</strong><span>{phaseText(selected.phase)}</span></div><div className="rd-process-point-values">{definitions.map(field => <div key={field.key || 'unknown'}><span>{field.label}</span><strong title={known(savedValue(selected, field)) ? String(savedValue(selected, field)) : undefined}>{number(savedValue(selected, field))}{known(savedValue(selected, field)) && field.unit && ' ' + field.unit}</strong></div>)}</div><small>本次计算范围：{number(selected.completion.expected_operation_count)} 道参与工序，其中未安排 {number(selected.completion.missing_operation_count)} 道；{scopeText(selected.objective_scope)}。完整交付和待料工序在“交期与未排”中查看。</small></div>}
      <p className="rd-process-selected wb-visually-hidden" id={id + '-selected'} aria-live="polite" aria-atomic="true">{selectionText}</p>
      {mode === 'curve' && <p className="rd-process-chart-note">图中各指标沿同一保留方案的保存事件显示，评分改善时次要指标仍可能增加。</p>}
    </figure>;
  }
  window.RunDecisionProcessChart = { Chart, segments, markers, flagLabels, scopeText, phaseText, stepPath };
})();
