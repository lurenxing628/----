(function () {
  'use strict';
  const F = window.WorkbenchFormat, M = window.PlanGanttModel, A = window.DecisionHistoryAPI;
  const known = value => typeof value === 'number' && Number.isFinite(value);
  const hasValue = metric => known(metric.value) && metric.state !== 'unavailable';
  function valueText(metric, definition) {
    return hasValue(metric) ? A.numberText(metric.value, metric.unit, definition.precision) : metric.state === 'not_applicable' ? '不适用' : '待确认';
  }
  function missingText(metric, definition) {
    const state = metric.state === 'not_applicable' ? '不适用' : metric.state === 'partial' || metric.reason && metric.reason.code === 'delivery_evidence_incomplete' ? '资料不全' : metric.reason && ['history_result_missing', 'not_recorded'].includes(metric.reason.code) ? '未保存结果' : '资料缺项';
    const member = metric.covered_batch_refs !== null ? '批' : metric.covered_operation_refs !== null ? '道工序' : metric.covered_resource_refs !== null ? '个资源' : '项';
    const partial = metric.known_count > 0 && known(metric.known_subtotal) ? '已知 ' + A.numberText(metric.known_subtotal, metric.unit, definition.precision) + '，另有 ' + metric.unknown_count + ' ' + member + '待确认' : metric.unknown_count > 0 ? metric.unknown_count + ' ' + member + '待确认' : '';
    return [state, metric.reason && metric.reason.message, partial].filter(Boolean).join('；');
  }
  function pointText(point, metricKey, definition) {
    const metric = point.metrics[metricKey], resourceWindow = point.resource_window;
    return point.label + '；' + (point.occurred_at === null ? '发生时间未记录' : F.dateTime(point.occurred_at, { seconds: true, fractions: true }))
      + '；' + (point.scope.batch_count === null ? '批次数待确认' : '共 ' + F.number(point.scope.batch_count, { digits: 0 }) + ' 批')
      + '；' + (point.scope.operation_count === null ? '工序数待确认' : F.number(point.scope.operation_count, { digits: 0 }) + ' 道工序')
      + '；' + definition.label + '：' + valueText(metric, definition)
      + (!hasValue(metric) ? '；' + missingText(metric, definition) : metric.unknown_count > 0 ? '；' + metric.unknown_count + ' 项待确认' : '')
      + (A.windowMetric(definition) && resourceWindow.start !== null && resourceWindow.end !== null ? '；统计时间：' + F.dateTime(resourceWindow.start) + ' 至 ' + F.dateTime(resourceWindow.end) + '（不含结束）' : '')
      + (point.range_changed ? '；业务范围或资源窗口变化' : '');
  }
  function valueDomain(values, integer) {
    const max = Math.max(0, ...values), step = integer ? Math.max(1, Math.ceil(max / 4)) : max / 4;
    return { min: 0, max: integer ? Math.ceil(max / step) * step : max, step };
  }
  const ticks = domain => domain.max === 0 ? [0] : Array.from({ length: Math.round(domain.max / domain.step) + 1 }, (_, index) => index * domain.step);
  function plotSegments(points, plotted, metricKey) {
    return plotted.slice(1).flatMap((point, index) => {
      const before = plotted[index], between = points.slice(points.indexOf(before), points.indexOf(point) + 1), basis = before.metrics[metricKey];
      if (between.some(row => !known(M.instant(row.occurred_at)) || !A.sameMetricDefinition(basis, row.metrics[metricKey]))) return [];
      return [{ from: index, to: index + 1, gap: between.slice(1, -1).filter(row => !hasValue(row.metrics[metricKey])).length }];
    });
  }
  function Chart({ data, metricKey, selectedEntryRef, onSelect, busy = false, missingOpen = false, onMissingToggle }) {
    const id = React.useId(), points = data.trend.points, definition = data.metric_definitions.find(item => item.key === metricKey);
    const entries = new Map(data.entries.map(entry => [entry.entry_ref, entry])), selectedIndex = points.findIndex(point => point.entry_ref === selectedEntryRef), selected = points[selectedIndex];
    const plotted = points.filter(point => known(M.instant(point.occurred_at)) && hasValue(point.metrics[metricKey])), missing = points.filter(point => !hasValue(point.metrics[metricKey])), untimed = points.filter(point => !known(M.instant(point.occurred_at)) && hasValue(point.metrics[metricKey]));
    const units = [...new Set(plotted.map(point => point.metrics[metricKey].unit))];
    const hasGaps = units.some(unit => plotSegments(points, plotted.filter(point => point.metrics[metricKey].unit === unit), metricKey).some(segment => segment.gap > 0));
    function choose(index, reveal = false) { if (!busy && typeof onSelect === 'function' && points[index]) onSelect(entries.get(points[index].entry_ref), reveal); }
    function keyboard(event) {
      if (event.defaultPrevented || busy || !points.length || event.altKey || event.ctrlKey || event.metaKey) return;
      const button = event.target && event.target.closest && event.target.closest('[data-dh-chart-choice]');
      if (event.target && event.target !== event.currentTarget && !button) return;
      const current = button ? points.findIndex(point => point.entry_ref === button.getAttribute('data-dh-chart-choice')) : selectedIndex;
      let next;
      if (event.key === 'ArrowRight' || event.key === 'ArrowDown') next = Math.min(current + 1, points.length - 1);
      else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') next = current < 0 ? points.length - 1 : Math.max(current - 1, 0);
      else if (event.key === 'Home') next = 0;
      else if (event.key === 'End') next = points.length - 1;
      else if (event.key === 'Enter') next = current < 0 ? 0 : current;
      else return;
      event.preventDefault(); choose(next, event.key === 'Enter');
    }
    return <figure className="dh-chart" data-dh-chart-metric={metricKey} data-dh-chart-timeline={data.filters.timeline} aria-busy={busy}>
      <div className="dh-chart-head"><figcaption className="dh-chart-caption" id={id + '-caption'}>{definition.label}</figcaption><span className="dh-muted">本页 {points.length} 条记录 · 图中 {plotted.length} 条有数值</span></div>
      <p className="dh-chart-note">有数值的记录 · 按发生顺序排列</p>
      {units.length > 1 && <p className="dh-chart-note">记录单位不同，各图保留对应单位的原值。</p>}
      <div className="dh-chart-keyboard" role="group" tabIndex={0} aria-labelledby={id + '-caption'} aria-describedby={id + '-keys ' + id + '-selected'} aria-disabled={busy || undefined} onKeyDown={keyboard}>
        {units.map(unit => {
          const unitPoints = plotted.filter(point => point.metrics[metricKey].unit === unit), segments = plotSegments(points, unitPoints, metricKey), domain = valueDomain(unitPoints.map(point => point.metrics[metricKey].value), definition.precision === 0 && unit !== '%');
          const y = value => domain.max === 0 ? 210 : 210 - value / domain.max * 180, tickText = value => unit === '%' ? F.percent(value, { digits: definition.precision, trim: true }) : F.number(value, { digits: definition.precision, trim: true });
          return <div className="dh-chart-series" key={unit} data-metric-unit={unit}>{unit && <div className="dh-chart-unit">{unit === '%' ? '百分比（%）' : unit}</div>}
            <div className="dh-chart-scroll"><div className="dh-chart-plot"><div className="dh-chart-y-axis" aria-hidden="true">{ticks(domain).map(tick => <span key={tick} style={{ top: y(tick) }} title={A.numberText(tick, unit, definition.precision)}>{tickText(tick)}</span>)}</div>
              <div className="dh-chart-grid" style={{ minWidth: unitPoints.length * 80 }}><div className="dh-chart-gridlines" aria-hidden="true">{ticks(domain).map(tick => <span key={tick} style={{ top: y(tick) }} />)}</div>
                <svg className="dh-chart-lines" viewBox={'0 0 ' + unitPoints.length * 100 + ' 220'} preserveAspectRatio="none" aria-hidden="true">{segments.map(segment => <line key={segment.to} data-from-entry={unitPoints[segment.from].entry_ref} data-to-entry={unitPoints[segment.to].entry_ref} data-gap-count={segment.gap} x1={segment.from * 100 + 50} y1={y(unitPoints[segment.from].metrics[metricKey].value)} x2={segment.to * 100 + 50} y2={y(unitPoints[segment.to].metrics[metricKey].value)} vectorEffect="non-scaling-stroke" />)}</svg>
                <div className="dh-chart-records" style={{ gridTemplateColumns: 'repeat(' + unitPoints.length + ', minmax(80px, 1fr))' }}>{unitPoints.map(point => <button type="button" className="dh-chart-entry" key={point.entry_ref} data-dh-chart-choice={point.entry_ref} data-entry-ref={point.entry_ref} data-metric-value={point.metrics[metricKey].value} data-metric-version={point.metrics[metricKey].metric_version} data-metric-scope={point.metrics[metricKey].scope} aria-pressed={point.entry_ref === selectedEntryRef} disabled={busy} title={pointText(point, metricKey, definition)} aria-label={pointText(point, metricKey, definition)} onClick={() => choose(points.indexOf(point), true)}>
                  <span className="dh-chart-point-space" style={{ '--dh-point-y': y(point.metrics[metricKey].value) + 'px' }}><span className="dh-chart-value">{valueText(point.metrics[metricKey], definition)}</span><span className="dh-chart-point" aria-hidden="true" /></span><span className="dh-chart-label">{point.label}</span><span className="dh-chart-scale">{point.scope.batch_count === null ? '批次数待确认' : '共 ' + F.number(point.scope.batch_count, { digits: 0 }) + ' 批'}</span>
                </button>)}</div>
                {segments.some(segment => segment.gap > 0) && <div className="dh-chart-gap-notes">{segments.filter(segment => segment.gap > 0).map(segment => <span key={segment.to} style={{ left: segment.to / unitPoints.length * 100 + '%', width: 100 / unitPoints.length + '%' }}>{segment.gap} 条待确认／不适用</span>)}</div>}
              </div></div></div>
          </div>;
        })}
        {plotted.length === 0 && <p className="dh-chart-note">本页没有可绘制的数值</p>}{hasGaps && <p className="dh-chart-note">虚线跨过待确认记录。</p>}
        <div className="dh-chart-selected" id={id + '-selected'} aria-live="polite">{selected ? <><div><small className="dh-muted">当前记录</small><strong>{selected.label}</strong><p className="dh-note">{selected.occurred_at === null ? '发生时间未记录' : F.dateTime(selected.occurred_at, { seconds: true, fractions: true })} · {selected.scope.batch_count === null ? '批次数待确认' : F.number(selected.scope.batch_count, { digits: 0 }) + ' 批'} / {selected.scope.operation_count === null ? '工序数待确认' : F.number(selected.scope.operation_count, { digits: 0 }) + ' 道工序'}</p></div><strong className="dh-chart-selected-value">{definition.label}：{valueText(selected.metrics[metricKey], definition)}</strong>{!hasValue(selected.metrics[metricKey]) && <p className="dh-chart-selected-reason">{missingText(selected.metrics[metricKey], definition)}</p>}</> : <p className="dh-note">选择记录查看结果。</p>}</div>
        {missing.length > 0 && <details className="dh-chart-missing" open={missingOpen} onToggle={event => onMissingToggle && onMissingToggle(event.currentTarget.open)}><summary>另外 {missing.length} 条结果待确认／不适用</summary><div className="dh-chart-missing-list">{missing.map(point => <button type="button" className="dh-chart-missing-entry" key={point.entry_ref} data-dh-chart-choice={point.entry_ref} data-entry-ref={point.entry_ref} aria-pressed={point.entry_ref === selectedEntryRef} disabled={busy} title={pointText(point, metricKey, definition)} onClick={() => choose(points.indexOf(point), true)}><span>{point.label}<small>{point.occurred_at === null ? '发生时间未记录' : F.dateTime(point.occurred_at, { seconds: true, fractions: true })}</small></span><span>{definition.label}：{valueText(point.metrics[metricKey], definition)}<small>{missingText(point.metrics[metricKey], definition)}</small></span><span>查看</span></button>)}</div></details>}
        {untimed.length > 0 && <section className="dh-chart-untimed" aria-label="发生时间未记录的历史条目"><h4>发生时间未记录</h4><div className="dh-chart-missing-list">{untimed.map(point => <button type="button" className="dh-chart-missing-entry" key={point.entry_ref} data-dh-chart-choice={point.entry_ref} data-entry-ref={point.entry_ref} aria-pressed={point.entry_ref === selectedEntryRef} disabled={busy} title={pointText(point, metricKey, definition)} onClick={() => choose(points.indexOf(point), true)}><span>{point.label}<small>发生时间未记录</small></span><span>{definition.label}：{valueText(point.metrics[metricKey], definition)}</span><span>查看</span></button>)}</div></section>}
        <p className="wb-visually-hidden" id={id + '-keys'}>方向键切换记录，Home / End 选择首末条，Enter 查看当前记录。</p>
      </div>
    </figure>;
  }
  window.DecisionHistoryChart = { Chart };
})();
