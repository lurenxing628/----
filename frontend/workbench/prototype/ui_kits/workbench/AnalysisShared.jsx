(function () {
  const emptyScope = { source: 'current', dateFrom: '', dateTo: '', batch: '', resourceType: 'all', resource: '', search: '', focus: 'all' };
  const workspaces = {};
  const scopeKey = scope => JSON.stringify(Object.keys(emptyScope).map(key => scope && scope[key]));
  function workspaceState(defaults, previous, context, scope) {
    let state = { ...defaults, ...(previous && previous.state) };
    const sameScope = previous && previous.scopeKey === scopeKey(scope);
    if (!sameScope) state = { ...state, page: 1, selected: null, recordPage: 1, resourcePage: 1 };
    if (context && context.topic && context.topic !== state.topic) state = { ...defaults };
    Object.keys(defaults).forEach(key => { if (context && context[key] !== undefined) state[key] = context[key]; });
    return { state, dom: context && context.dom || (sameScope && previous.dom) || null };
  }
  function captureWorkspace(root) {
    const dom = { scrolls: {}, disclosures: {} };
    if (!root) return dom;
    root.querySelectorAll('[data-analysis-scroll]').forEach(node => {
      dom.scrolls[node.dataset.analysisScroll] = { left: node.scrollLeft, top: node.scrollTop };
    });
    root.querySelectorAll('details[data-analysis-disclosure]').forEach(node => {
      dom.disclosures[node.dataset.analysisDisclosure] = node.open;
    });
    return dom;
  }
  function restoreWorkspace(root, dom) {
    if (!root || !dom) return;
    root.querySelectorAll('details[data-analysis-disclosure]').forEach(node => {
      const open = dom.disclosures && dom.disclosures[node.dataset.analysisDisclosure];
      if (typeof open === 'boolean') node.open = open;
    });
    root.querySelectorAll('[data-analysis-scroll]').forEach(node => {
      const scroll = dom.scrolls && dom.scrolls[node.dataset.analysisScroll];
      if (scroll) { node.scrollLeft = scroll.left; node.scrollTop = scroll.top; }
    });
  }
  function useWorkspaceState(view, defaults, scope, initialContext) {
    const contextKey = JSON.stringify(initialContext || {}), currentScopeKey = scopeKey(scope);
    const rootRef = React.useRef(null), latest = React.useRef(null);
    const [entry, setEntry] = React.useState(() => {
      const saved = workspaces[view], context = saved && saved.contextKey === contextKey ? null : initialContext;
      return { ...workspaceState(defaults, saved, context, scope), contextKey, scopeKey: currentScopeKey };
    });
    let active = entry;
    // Prop changes and restoration are one transition, never a second reset effect.
    if (entry.contextKey !== contextKey || entry.scopeKey !== currentScopeKey) {
      active = { ...workspaceState(defaults, entry, entry.contextKey !== contextKey ? initialContext : null, scope), contextKey, scopeKey: currentScopeKey };
      setEntry(active);
    }
    const update = patch => setEntry(old => ({ ...old, state: { ...old.state, ...(typeof patch === 'function' ? patch(old.state) : patch) } }));
    const snapshot = () => ({ ...active.state, scope: { ...scope }, dom: captureWorkspace(rootRef.current) });
    React.useLayoutEffect(() => {
      latest.current = { ...active, scope: { ...scope } };
      workspaces[view] = latest.current;
    });
    React.useLayoutEffect(() => { restoreWorkspace(rootRef.current, active.dom); }, [contextKey, currentScopeKey]);
    React.useLayoutEffect(() => () => {
      if (latest.current) workspaces[view] = { ...latest.current, dom: captureWorkspace(rootRef.current) };
    }, [view]);
    return { state: active.state, update, snapshot, rootRef };
  }
  function Icon({ name }) {
    // Local Lucide subset, licensed by assets/lucide-LICENSE.
    const extra = {
      'arrow-up-right': [['path', { d: 'M7 7h10v10' }], ['path', { d: 'M7 17 17 7' }]],
      'refresh-cw': [['path', { d: 'M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8' }], ['path', { d: 'M21 3v5h-5' }], ['path', { d: 'M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16' }], ['path', { d: 'M8 16H3v5' }]]
    };
    const nodes = extra[name] || window.APSFieldReports.iconNodes[name];
    if (!nodes) throw new Error('未加载图标：' + name);
    return <svg className="aw-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{nodes.map(([tag, attrs], i) => React.createElement(tag, { ...attrs, key: i }))}</svg>;
  }
  function ScopeBar({ analysis, scope, onChange, idPrefix, expanded, onExpandedChange }) {
    const [localExpanded, setLocalExpanded] = React.useState(false);
    const isExpanded = expanded === undefined ? localExpanded : expanded;
    const api = window.APSExecutionAnalysis, values = { ...emptyScope, ...(analysis ? analysis.scope : {}), ...scope };
    const sources = window.APSReportWorkbench.sources(), validSource = sources.some(s => s.id === values.source && s.available);
    const choices = analysis ? analysis.choices : { batches: [], machines: [], people: [] };
    const related = values.resourceType === 'person' ? choices.people : choices.machines;
    const change = patch => onChange({ ...values, ...patch });
    const defaults = analysis ? api.defaults(values.source) : null;
    const active = [];
    if (defaults) ['dateFrom', 'dateTo'].forEach(key => {
      if (values[key] !== defaults[key]) active.push([key, (key === 'dateFrom' ? '起日：' : '止日：') + values[key], { [key]: defaults[key] }]);
    });
    if (values.batch) active.push(['batch', '批次：' + values.batch, { batch: '' }]);
    if (values.search) active.push(['search', '搜索：' + values.search, { search: '' }]);
    if (values.resourceType !== 'all') active.push(['resource', (values.resourceType === 'person' ? '人员：' : '设备：') + (values.resource === '__unassigned__' ? '未填写资源' : values.resource || '全部对象'), { resourceType: 'all', resource: '' }]);
    if (values.focus !== 'all') active.push(['focus', '范围：' + (api.focuses[values.focus] || values.focus), { focus: 'all' }]);
    const input = (key, label, type = 'date') => <label htmlFor={idPrefix + '-' + key}>{label}<input id={idPrefix + '-' + key} name={idPrefix + '-' + key} type={type} value={values[key]} title={values[key]} onChange={e => change({ [key]: e.target.value })} /></label>;
    const select = (key, label, options, disabled = false) => <label htmlFor={idPrefix + '-' + key}>{label}<select id={idPrefix + '-' + key} name={idPrefix + '-' + key} value={values[key]} title={(options.find(([id]) => id === values[key]) || ['', values[key]])[1]} disabled={disabled} onChange={e => change({ [key]: e.target.value })}>
      {values[key] && !options.some(([id]) => id === values[key]) && <option value={values[key]}>{values[key]}（当前无匹配）</option>}
      {options.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
    </select></label>;
    return <div className="aw-scope" role="group" aria-label="分析范围">
      <div className="aw-scope-main">
        <label htmlFor={idPrefix + '-source'}>数据来源<select id={idPrefix + '-source'} name={idPrefix + '-source'} value={values.source} onChange={e => onChange(api.defaults(e.target.value))}>
          {!sources.some(s => s.id === values.source) && <option value={values.source}>无效来源</option>}
          {sources.map(s => <option key={s.id} value={s.id} disabled={!s.available}>{s.label}</option>)}
        </select></label>
        {input('dateFrom', '计划完工起日')}{input('dateTo', '计划完工止日')}
        {select('batch', '批次', [['', '全部批次'], ...choices.batches.map(v => [v, v])])}
        <label htmlFor={idPrefix + '-search'} className="aw-search">搜索<span><Icon name="search" /><input id={idPrefix + '-search'} name={idPrefix + '-search'} type="search" placeholder="批次、工序、资源或报工号" value={values.search} onChange={e => change({ search: e.target.value })} /></span></label>
        <div className="aw-scope-tools"><button type="button" className="aw-more" aria-expanded={isExpanded} aria-controls={idPrefix + '-more-filters'} onClick={() => (onExpandedChange || setLocalExpanded)(!isExpanded)}>{isExpanded ? '收起条件' : '更多条件'}<Icon name="chevron-down" /></button>
          <button type="button" className="aw-reset" title="重置为本数据源全部范围" aria-label="重置分析范围" disabled={!validSource} onClick={() => onChange(api.defaults(values.source))}><Icon name="refresh-cw" /></button></div>
      </div>
      <div className="aw-scope-filters" id={idPrefix + '-more-filters'} hidden={!isExpanded}>
        <label htmlFor={idPrefix + '-resourceType'}>关联资源<select id={idPrefix + '-resourceType'} name={idPrefix + '-resourceType'} value={values.resourceType} onChange={e => change({ resourceType: e.target.value, resource: '' })}>
          <option value="all">全部资源</option><option value="machine">设备</option><option value="person">人员</option>
        </select></label>
        {select('resource', '资源对象', [['', '全部对象'], ...related.map(v => [v, v === '__unassigned__' ? '未填写资源' : v])], values.resourceType === 'all')}
        {select('focus', '分析范围', Object.entries(api.focuses))}
      </div>
      {active.length > 0 && <div className="aw-scope-summary"><ul aria-label="已生效条件">{active.map(([key, label, patch]) => <li key={key}><span>{label}</span><button type="button" aria-label={'清除' + label} title={'清除' + label} onClick={() => change(patch)}><Icon name="x" /></button></li>)}</ul></div>}
    </div>;
  }
  function DataDisclosure({ points, label }) {
    return <details className="aw-data" data-analysis-disclosure={label}><summary>图表数据</summary><div className="aw-data-scroll" data-analysis-scroll={label}><table><thead><tr><th>时刻</th><th>计划已到期工序</th><th>已确认完成工序</th><th>到期未确认完成</th></tr></thead><tbody>{points.map(p => <tr key={p.time}><th>{p.label}</th><td>{p.planned}</td><td>{p.actual === null ? '未知' : p.actual}</td><td>{p.unclosed === null ? '未知' : p.unclosed}</td></tr>)}</tbody></table></div></details>;
  }
  function TrendChart({ points, label }) {
    const id = React.useId(), fmt = window.APSExecutionAnalysis.formatNumber;
    if (!points.length) return <figure className="aw-chart aw-trend" aria-label={label}><figcaption className="aw-caption">{label}</figcaption><p className="aw-empty">当前范围无工序，无法形成趋势。</p></figure>;
    const largest = Math.max(1, ...points.flatMap(p => [p.planned, p.actual || 0, p.unclosed || 0]));
    const step = Math.max(1, Math.ceil(largest / 4)), max = step * Math.ceil(largest / step);
    const ticks = Array.from({ length: max / step + 1 }, (_, i) => i * step);
    const start = points[0].time, duration = points[points.length - 1].time - start || 1;
    const x = p => (p.time - start) / duration * 600, y = value => 200 - value / max * 200;
    const series = [['planned', '计划已到期工序'], ['actual', '已确认完成工序'], ['unclosed', '到期未确认完成']];
    const paths = key => {
      const segments = []; let segment = [];
      points.forEach(p => { if (p[key] === null) { if (segment.length) segments.push(segment); segment = []; } else segment.push(p); });
      if (segment.length) segments.push(segment);
      return segments.map(list => list.map((p, i) => (i ? 'L' : 'M') + x(p).toFixed(2) + ' ' + y(p[key]).toFixed(2)).join(' '));
    };
    const labels = [...new Set([0, Math.floor((points.length - 1) / 4), Math.floor((points.length - 1) / 2), Math.floor((points.length - 1) * 3 / 4), points.length - 1])].map(i => points[i]);
    const lastActual = points.filter(p => p.actual !== null).slice(-1)[0];
    return <figure className="aw-chart aw-trend" aria-labelledby={id}>
      <figcaption id={id} className="aw-caption">{label}</figcaption>
      <div className="aw-legend">{series.map(([key, title]) => <span key={key}><i className={'aw-swatch aw-' + key} />{title}</span>)}<small>道</small></div>
      <div className="aw-chart-body"><div className="aw-y-axis">{ticks.map(v => <span key={v} style={{ top: (1 - v / max) * 100 + '%' }}>{fmt(v)}</span>)}</div>
        <div className="aw-plot"><svg className="aw-plot-svg" viewBox="0 0 600 200" preserveAspectRatio="none" role="img" aria-label={label + '；具体值见图表数据'}>
          {ticks.map(v => <line key={v} x1="0" x2="600" y1={y(v)} y2={y(v)} className="aw-gridline" vectorEffect="non-scaling-stroke" />)}
          {lastActual && <line x1={x(lastActual)} x2={x(lastActual)} y1="0" y2="200" className="aw-clock-line" vectorEffect="non-scaling-stroke"><title>{lastActual.label} · 实际数据截至</title></line>}
          {series.map(([key, title]) => <g key={key} className={'aw-series aw-' + key} data-series={key}>{paths(key).map((d, i) => <path key={i} d={d} fill="none" vectorEffect="non-scaling-stroke" />)}
            {points.filter(p => p[key] !== null).map(p => <circle key={p.time} cx={x(p)} cy={y(p[key])} r="2.5" vectorEffect="non-scaling-stroke"><title>{p.label} · {title} {p[key]} 道</title></circle>)}
          </g>)}
        </svg></div>
      </div>
      <div className="aw-x-axis">{labels.map((p, i) => <span className={i % 2 ? 'aw-minor-tick' : ''} key={p.time}>{p.label.slice(0, 5)}<small>{p.label.slice(6)}</small></span>)}</div>
      <DataDisclosure points={points} label={label} />
    </figure>;
  }
  function DistributionChart({ items, label, onSelect }) {
    const id = React.useId(), fmt = window.APSExecutionAnalysis.formatNumber;
    const maximum = Math.max(1, ...items.filter(p => Number.isFinite(p.count)).map(p => p.count));
    return <figure className="aw-chart aw-distribution" aria-labelledby={id}><figcaption className="aw-caption" id={id}>{label}</figcaption>
      {items.length ? <ul className="aw-bars">{items.map(item => {
        const known = Number.isFinite(item.count) && item.count >= 0;
        const body = <><span className="aw-bar-label">{item.label}</span><span className="aw-bar-track" aria-hidden="true">{known && <i data-tone={item.tone || 'notice'} style={{ width: item.count / maximum * 100 + '%' }} />}</span><strong>{known ? fmt(item.count) : '未知'}</strong></>;
        return <li key={item.id} data-chart-item={item.id}>{onSelect ? <button type="button" className="aw-bar-row" onClick={() => onSelect(item)} aria-label={item.label + '：' + (known ? fmt(item.count) : '未知')}>{body}</button> : <div className="aw-bar-row">{body}</div>}</li>;
      })}</ul> : <p className="aw-empty">当前范围没有可比较数据。</p>}
    </figure>;
  }
  window.APSAnalysisUI = { ScopeBar, Icon, TrendChart, DistributionChart, useWorkspaceState };
})();
