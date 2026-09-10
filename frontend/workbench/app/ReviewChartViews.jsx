(function () {
  'use strict';
  function DistributionChart({ items, label }) {
    const id = React.useId(), maximum = Math.max(1, ...items.map(row => row.count || 0));
    return <figure className="aw-chart aw-distribution" aria-labelledby={id}><figcaption className="aw-caption" id={id}>{label}</figcaption>
      <ul className="aw-bars">{items.map(row => <li key={row.id}><div className="aw-bar-row"><span className="aw-bar-label">{row.label}</span>
        <span className="aw-bar-track" aria-hidden="true"><i data-tone={row.tone} style={{ width: row.count / maximum * 100 + '%' }} /></span><strong>{row.count}</strong></div></li>)}</ul></figure>;
  }
  function TrendChart({ points, label }) {
    const id = React.useId();
    if (!points.length) return <p className="aw-empty">当前范围无可比较趋势。</p>;
    const max = Math.max(1, ...points.flatMap(row => [row.planned, row.actual || 0]));
    const start = points[0].time, span = points[points.length - 1].time - start || 1;
    const x = row => 10 + (row.time - start) / span * 580, y = value => 190 - value / max * 180;
    const series = [['planned', '计划累计完工'], ['actual', '已确认整道完工']];
    return <figure className="aw-chart aw-trend" aria-labelledby={id}><figcaption id={id} className="aw-caption">{label}</figcaption>
      <div className="aw-legend">{series.map(([key, title]) => <span key={key}><i className={'aw-swatch aw-' + key} />{title}</span>)}</div>
      <div className="aw-chart-body"><div className="aw-y-axis"><span style={{ top: 0 }}>{max}</span><span style={{ bottom: 0 }}>0</span></div>
        <div className="aw-plot"><svg className="aw-plot-svg" viewBox="0 0 600 200" preserveAspectRatio="none" role="img" aria-label={label}>
          {[0, max / 2, max].map(value => <line key={value} className="aw-gridline" x1={0} x2={600} y1={y(value)} y2={y(value)} />)}
          {series.map(([key, title]) => { const known = points.filter(row => row[key] !== null); return <g key={key} className={'aw-series aw-' + key}>
            <path d={known.map((row, index) => (index ? 'L' : 'M') + x(row) + ' ' + y(row[key])).join(' ')} fill="none" vectorEffect="non-scaling-stroke" />
            {known.map(row => <circle key={row.time} cx={x(row)} cy={y(row[key])} r={3} vectorEffect="non-scaling-stroke"><title>{row.label} · {title} {row[key]} 道</title></circle>)}</g>; })}
        </svg></div></div>
      <div className="aw-x-axis"><span>{points[0].label}</span><span>{points[points.length - 1].label}</span></div>
      <details className="aw-data"><summary>图表数据</summary><div className="aw-data-scroll"><table><thead><tr><th>日期</th><th>计划累计完工</th><th>已确认整道完工</th></tr></thead><tbody>{points.map(row => <tr key={row.time}><th>{row.label}</th><td>{row.planned}</td><td>{row.actual == null ? '未知' : row.actual}</td></tr>)}</tbody></table></div></details>
    </figure>;
  }
  const resourceColumns = [['resource_label', '实际资源'], ['operations', '涉及工序'], ['events', '旧现场事件数'],
    ['production_reports', '逐次报工数'], ['records', '全部记录数'], ['effective_processing_hours', '有效加工工时(h)'],
    ['known_effective_processing_hours', '已知工时小计(h)'], ['unknown_hour_events', '工时未知记录数']].map(([key, label]) => ({ key, label }));
  window.ReviewChartViews = { DistributionChart, TrendChart, resourceColumns };
})();
