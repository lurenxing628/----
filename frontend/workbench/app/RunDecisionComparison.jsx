(function () {
  'use strict';
  const A = window.RunCandidateAPI, N = window.RunCandidateAnalysisAPI, D = window.RunDecisionAPI, C = window.RunCandidateControls, M = window.RunCandidateModel, G = window.RunGenerationContract;
  const roles = { recommended: '计算时推荐', algorithm_baseline: '原算法', raw_score_best: '目标最优', health_reference: '健康比较原方案' };
  const groups = { completeness: '工序安排', delivery: '批次交付', time: '时间与目标', preparation: '准备与工种切换', resources: '设备与人员', stability: '安排变化' };
  const metricState = { unavailable: '资料未记录', not_applicable: '本范围不适用', partial: '完整值待确认' };
  const scopeLabels = { full_admission: '本次选中的全部批次和工序', full_candidate: '整份候选安排', completed_batches_only: '工序已排齐的批次', saved_algorithm_batches: '计算时比较的批次', candidate_search: '本次候选搜索', saved_schedule_resources: '计算时保存的时间范围和资源', fixed_resource_window: '当前时间范围和设备、人员', fixed_changeover_window: '当前时间范围内的设备工序顺序' };
  const metricSources = { archived_delivery: '保存的交付计算', saved_algorithm: '计算时保存的统计', candidate_comparison: '保存的安排对照', archived_resource_calendar: '排产时的班表', runtime_operation_effort: '排产时保存的工时需求', archived_changeover_events: '设备工种切换记录', admission: '本次选中的工序', candidate_tasks: '保存的候选安排' };
  const countText = value => value === null || value === undefined ? '资料未记录' : M.number(value);
  // RunDecisionAPI.scope 只保留非空的范围键；未设置范围时输入框显示为空。
  const rangeDraft = value => ({ start: value.range_start === undefined ? '' : value.range_start, end: value.range_end === undefined ? '' : value.range_end });
  const comparisonTabs = [['delivery', '交期与未排'], ['differences', '方案差异'], ['resources', '资源占用'], ['process', '计算过程'], ['preparation', '准备与切换']];
  const secondaryTabs = [['metrics', '全部指标'], ['completion', '工序安排']];
  // 后端甘特/明细定位用 batches、operations 命名页签，这里换成本页的交付与差异页签。
  const tabAliases = { batches: 'delivery', operations: 'differences' };
  function referenceNotice(data) { return data.scope.comparison_mode === 'admission_official' ? '排产时尚无正式计划。' : '选定比较基准后显示差值。'; }
  function metricText(metric, definition) {
    if (metric.value === null) return metricState[metric.state] || '完整值待确认';
    return definition.unit === '%' ? window.WorkbenchFormat.percent(metric.value)
      : window.WorkbenchFormat.number(metric.value, { digits: definition.precision, trim: true }) + (definition.unit ? ' ' + definition.unit : '');
  }
  function deltaText(delta, definition) {
    const effort = definition.source === 'runtime_operation_effort', different = delta.state === 'different_coverage';
    if (different && !effort) return definition.source === 'archived_changeover_events' ? '比较的安排不同' : '工序已排齐的批次不同';
    if (delta.value === null || delta.state !== 'comparable' && !different) return '差值待确认';
    if (delta.value === 0) return (effort ? '相同' : '持平') + (different ? ' · 工序计量对象不同' : '');
    const value = Math.abs(delta.value) * (definition.unit === '%' ? 100 : 1), unit = definition.unit === '%' ? ' 个百分点' : definition.unit ? ' ' + definition.unit : '';
    const tiny = Number(value.toFixed(definition.precision)) === 0;
    const amount = window.WorkbenchFormat.number(tiny ? Math.pow(10, -definition.precision) : value, { digits: definition.precision, trim: true }) + unit;
    return (delta.value > 0 ? '增加' : '减少') + (tiny ? '不到 ' : ' ') + amount + (different ? ' · 工序计量对象不同' : '');
  }
  function metricCoverage(metric, definition) {
    const resource = metric.resource_kind || (definition.key && definition.key.startsWith('machine_') ? 'machine' : definition.key && definition.key.startsWith('operator_') ? 'operator' : null);
    const operations = ['admission', 'candidate_tasks', 'candidate_comparison', 'runtime_operation_effort', 'archived_changeover_events'];
    const resourceUnit = resource === 'machine' ? '台设备' : resource === 'operator' ? '人' : '项资源';
    const unit = Array.isArray(metric.covered_batch_refs) ? '批' : Array.isArray(metric.covered_operation_refs) ? '道工序'
      : Array.isArray(metric.covered_resource_refs) ? resourceUnit : definition.source === 'archived_delivery' ? '批'
      : operations.includes(definition.source) ? '道工序' : definition.source === 'archived_resource_calendar' ? resourceUnit : '份统计记录';
    const label = definition.key === 'weighted_tardiness_hours' ? '加权拖期' : definition.key === 'overdue_count' ? '超期' : definition.key === 'total_tardiness_hours' ? '拖期'
      : definition.key && definition.key.includes('setup_hours') ? '准备' : definition.key && definition.key.includes('processing_hours') ? '加工' : definition.label || '小计';
    return { unit, pending: metric.unknown_count > 0 ? countText(metric.unknown_count) + ' ' + unit + '待确认' : metricText(metric, definition),
      known: metric.known_count > 0 && metric.known_subtotal !== null ? '已知' + label + ' ' + metricText({ ...metric, value: metric.known_subtotal }, definition) : null,
      title: '已知 ' + countText(metric.known_count) + ' / ' + countText(metric.total_count) + ' ' + unit + '；待确认 ' + countText(metric.unknown_count) + ' ' + unit };
  }
  function Metric({ metric, definition, delta }) {
    const reasons = [...new Set([metric.reason && metric.reason.message, delta && delta.reason && delta.reason.message].filter(Boolean))];
    const coverage = metricCoverage(metric, definition);
    return <><strong title={coverage.title}>{metric.value === null ? coverage.pending : metricText(metric, definition)}</strong>
      {metric.value === null && coverage.known && <small>{coverage.known}</small>}
      {metric.value !== null && delta && <small className={'rd-change rd-' + delta.direction}>{deltaText(delta, definition)}</small>}
      {(metric.value === null || reasons.length > 0) && <details className="rd-metric-reasons"><summary>资料说明</summary>{metric.value === null && <><small>{coverage.title}</small><small>保存小计 {metric.known_subtotal === null ? '未记录' : metricText({ ...metric, value: metric.known_subtotal }, definition)}</small>{delta && <small className={'rd-change rd-' + delta.direction}>{deltaText(delta, definition)}</small>}</>}{reasons.map(message => <small key={message}>{message}</small>)}</details>}</>;
  }
  function CompactValue({ metric, definition }) {
    const coverage = metricCoverage(metric, definition), label = metric.value === null ? coverage.pending : metricText(metric, definition);
    return <span className="rd-compact-value" data-metric-state={metric.state}><strong title={metric.value === null ? coverage.title + '；保存小计 ' + (metric.known_subtotal === null ? '未记录' : metricText({ ...metric, value: metric.known_subtotal }, definition)) : label}>{label}</strong>
      {metric.value === null && coverage.known && <small>{coverage.known}</small>}</span>;
  }
  function CandidateBasis({ candidate, definitions, onCompletion, onProcess }) {
    return <details className="rd-candidate-basis"><summary aria-label={candidate.label + '指标依据'}>指标依据</summary><div><C.Button className="btn link" aria-label={candidate.label + '批次工序安排'} onClick={() => onCompletion(candidate)}>查看批次工序安排</C.Button><C.Button className="btn link" aria-label={candidate.label + '优化过程'} onClick={() => onProcess(candidate)}>优化过程</C.Button>{definitions.map(definition => <div key={definition.key}><strong>{definition.label}</strong><Metric metric={candidate.metrics[definition.key]} definition={definition} delta={candidate.deltas[definition.key]} /></div>)}</div></details>;
  }
  function Coverage({ candidate }) {
    const { schedulable, delivery } = candidate.coverage;
    const missing = window.WorkbenchTerms.missing_arrangements(schedulable.missing_count, schedulable.deferred_count);
    return <div className="rd-coverage"><span>已安排 <strong>{countText(schedulable.scheduled_count)} / {countText(schedulable.expected_count)}</strong> 道</span>
      {missing && <span>{missing}</span>}<span>工序已排齐 <strong>{countText(delivery.complete_batch_count)} / {countText(delivery.batch_count)}</strong> 批</span></div>;
  }
  function RunCoverage({ data }) {
    const candidate = data.candidates[0], search = candidate && candidate.coverage.search;
    return search ? <span className="rd-run-coverage">搜索 {countText(search.completed_count)} / {countText(search.total_count)} · 失败 {countText(search.failed_count)} · 跳过 {countText(search.skipped_count)}</span> : null;
  }
  function recommendationLabel(data, candidateRef) { const row = data.candidates.find(candidate => candidate.candidate_ref === candidateRef); return row ? row.label || '候选名称未填写' : '资料未记录'; }
  function CandidateReuse({ candidate, data }) {
    const source = data.candidates.find(row => row.candidate_ref === candidate.equivalent_source_ref);
    const fields = [['algo_mode', '算法方式'], ['used_strategy', '使用策略'], ['dispatch_mode', '调度模式'], ['dispatch_rule', '调度规则']];
    return <details className="rd-candidate-basis rd-candidate-reuse"><summary>复用来源与策略记录</summary><div>
      <p>复用同次“{recommendationLabel(data, candidate.equivalent_source_ref)}”的排产结果。</p>
      <window.WorkbenchReference entries={{ '复用候选': candidate.candidate_ref, '来源候选': candidate.equivalent_source_ref }} />
      {[['本候选', candidate], ['来源候选', source]].map(([label, row]) => <section key={label}><strong>{label}：{row ? row.label || '候选名称未填写' : '资料未记录'}</strong><dl>{fields.map(([key, title]) => {
        const value = row && row.source && row.source[key];
        return <div key={key} data-reuse-field={key}><dt>{title} <code>{key}</code></dt><dd>{value === null || value === undefined || value === '' ? '未记录' : String(value)}</dd></div>;
      })}</dl></section>)}
    </div></details>;
  }
  function CandidateTable({ data, selectedRef, referenceRef, onSelect, busy }) {
    const weighted = data.selection_basis.primary_objective === 'min_weighted_tardiness';
    const definitions = (weighted ? ['weighted_tardiness_hours', 'overdue_count', 'total_tardiness_hours'] : ['overdue_count', 'total_tardiness_hours']).map(key => data.metric_definitions.find(row => row.key === key)).filter(Boolean);
    return <div className="rd-candidate-grid" data-unified-candidates={data.candidates.length} aria-label="本次全部候选方案">{data.candidates.map(candidate => {
      const { schedulable } = candidate.coverage, missing = window.WorkbenchTerms.missing_arrangements(schedulable.missing_count, schedulable.deferred_count);
      const pending = [...new Set(definitions.filter(definition => candidate.metrics[definition.key].value === null && candidate.metrics[definition.key].state !== 'not_applicable').map(definition => metricCoverage(candidate.metrics[definition.key], definition).pending))].join('；');
      const fixed = data.scope.comparison_mode === 'candidates' && candidate.candidate_ref === referenceRef, recommended = candidate.selection_role.includes('recommended');
      const knownPending = definitions.some(definition => candidate.metrics[definition.key].value === null && candidate.metrics[definition.key].known_count > 0 && candidate.metrics[definition.key].unknown_count > 0);
      const completion = '已排 ' + countText(schedulable.scheduled_count) + ' / ' + countText(schedulable.expected_count) + ' 道' + (missing ? ' · ' + missing : '') + (pending ? ' · ' + (knownPending ? '另有 ' : '') + pending : '');
      return <section className="rd-candidate-card" key={candidate.candidate_ref} data-decision-candidate={candidate.candidate_ref} data-selected={candidate.candidate_ref === selectedRef || undefined}>
      <C.Button className="rd-candidate-choice" aria-label={'查看' + (candidate.label || '候选方案')} aria-pressed={candidate.candidate_ref === selectedRef} disabled={busy} onClick={() => onSelect(candidate)}>
        <span className="rd-candidate-choice-heading"><strong>{candidate.representative_objectives.length ? candidate.representative_objectives.map(G.objectiveLabel).join(' · ') : candidate.label || '候选名称未填写'}</strong>{(fixed || recommended) && <span className="rd-candidate-identities">
          {fixed && <span className="rd-badge rd-reference">对照</span>}{recommended && <span className="rd-badge rd-recommended">推荐</span>}</span>}</span>
        <span className="rd-candidate-card-metrics">{definitions.map(definition => {
          const metric = candidate.metrics[definition.key], known = metric.value === null && metric.known_count > 0 && metric.known_subtotal !== null, coverage = metricCoverage(metric, definition);
          const label = known ? definition.key === 'overdue_count' ? '已知超期' : definition.key === 'weighted_tardiness_hours' ? '已知加权拖期' : '已知拖期' : definition.label;
          const value = known ? metric.known_subtotal : metric.value;
          return <span key={definition.key} data-card-metric={definition.key}><span className="rd-candidate-metric-label">{label}</span><span className="rd-card-metric-value" data-metric-state={metric.state}><strong title={coverage.title + '；保存小计 ' + (metric.known_subtotal === null ? '未记录' : metricText({ value: metric.known_subtotal }, definition))}>{value === null ? metric.state === 'not_applicable' ? '不适用' : '未知' : <>{metricText({ value }, { ...definition, unit: '' })}<span className="rd-card-unit">{definition.unit}</span></>}</strong></span>{weighted && definition.key === 'weighted_tardiness_hours' && <small className="rd-weighted-basis">按计算时保存的批次优先级加权 · 已知 {countText(metric.known_count)} / {countText(metric.total_count)} 批{metric.unknown_count > 0 && ' · ' + countText(metric.unknown_count) + ' 批待确认'}</small>}</span>;
        })}</span>
        <span className="rd-card-completion">{candidate.persisted_status === 'completed' ? completion : <><C.Status candidate={candidate} />{candidate.source && candidate.source.reason && <small>{candidate.source.reason.message}</small>}</>}</span>
      </C.Button>
    </section>; })}</div>;
  }
  function CandidateFacts({ data, candidate, onCompletion, onProcess }) {
    return candidate ? <section className="rd-candidate-facts" aria-label="当前候选的完整保存依据"><h3>{candidate.label || '当前候选'} · 保存依据</h3>
      <p>{candidate.selection_role.map(role => roles[role] || (G.objective(role) ? G.objectiveLabel(role) + '代表方案' : null)).filter(Boolean).join(' · ')}</p>
      <C.GenerationMetadata value={candidate} runRef={data.run.run_ref} />
      <Coverage candidate={candidate} />{candidate.source && candidate.source.reason && <p>{candidate.source.reason.message}</p>}
      {candidate.representative_objectives.map(name => <div key={name} className="rd-saved-score-scope"><strong>{G.objectiveLabel(name)}的保存评价范围</strong><C.ScoringScope value={candidate.evaluations[name].scoring_scope} /></div>)}
      <CandidateBasis candidate={candidate} definitions={data.metric_definitions} onCompletion={onCompletion} onProcess={onProcess} />
      {candidate.equivalent_source_ref && <CandidateReuse candidate={candidate} data={data} />}
    </section> : null;
  }
  function Details({ data, selectedRef }) {
    return <section aria-label="全部候选详细指标比较" className="rd-details"><div className="rc-heading"><h3>详细比较</h3><span className="rc-muted">差值 = 各方案 − 对照方案</span></div>
      <div className="rc-table wb-table-frame" data-sticky-head><table className="wb-table rd-metric-table" aria-label="全部候选详细指标比较"><caption className="wb-visually-hidden">同次全部候选的完成性与业务指标</caption>
        <thead><tr><th scope="col">指标</th>{data.candidates.map(candidate => <th scope="col" key={candidate.candidate_ref} data-selected={candidate.candidate_ref === selectedRef || undefined}>{candidate.label || '候选名称未填写'}{candidate.selection_role.includes('recommended') && <small>计算时推荐</small>}{candidate.candidate_ref === data.scope.reference.candidate_ref && <small>当前比较基准</small>}</th>)}</tr></thead>
        <tbody>{data.metric_definitions.map((definition, index) => <tr key={definition.key} data-metric-key={definition.key} className={index === 0 || data.metric_definitions[index - 1].group !== definition.group ? 'rd-group-start' : ''}>
          <th scope="row"><strong>{definition.label}</strong><details><summary>指标说明</summary><small>{groups[definition.group]} · {metricSources[definition.source] || '本次保存的资料'}</small><small>{scopeLabels[definition.scope] || '本次保存的候选安排'}</small></details></th>
          {data.candidates.map(candidate => <td key={candidate.candidate_ref} data-selected={candidate.candidate_ref === selectedRef || undefined}><Metric metric={candidate.metrics[definition.key]} definition={definition} delta={candidate.deltas[definition.key]} /></td>)}</tr>)}</tbody>
      </table></div>
    </section>;
  }
  function FullReadStatus({ read, paused, onCancel, onReload }) {
    return <><div className="rc-tools"><C.Button icon="refresh-cw" aria-label="刷新全部方案指标" disabled={read.loading} onClick={onReload} />
      {read.loading && <><span role="status">正在读取全部方案指标。</span><C.Button icon="x" onClick={onCancel}>取消读取</C.Button></>}</div>
      <C.ErrorBox error={read.error} />{paused && <p className="rc-muted" role="status">全部方案指标读取已取消，点击刷新继续。</p>}</>;
  }
  function Export({ result, initialSection, filterQuery }) {
    const [format, setFormat] = React.useState(null), [busy, setBusy] = React.useState(false), [error, setError] = React.useState(null), [done, setDone] = React.useState('');
    const [section, setSection] = React.useState(initialSection), active = React.useRef(null), data = result.data;
    const labels = { overview: '方案总览', recommendation: '推荐说明与未安排工序', batches: '批次对照', operations: '工序变化', resources: '资源影响', 'resource-days': '资源逐日明细', preparation: '准备需求', changeovers: '工种切换', process: '优化过程' }, runRef = data.run_ref || data.run.run_ref;
    const description = section === 'all' ? '导出整份方案对照与本轮全部优化目标的过程记录，保留当前候选来源定位。'
      : initialSection === 'process' ? '导出本轮共同优化的摘要、当前方向曲线、阶段和全部实际动作，保留候选来源定位。'
        : section === 'recommendation' ? '导出推荐原因、相对当前基准的差值、批次工序安排和未安排工时。'
          : initialSection === 'overview' ? '导出本次全部 ' + data.candidates.length + ' 个候选和 ' + data.metric_definitions.length + ' 项指标。' : '导出当前筛选的全部明细。';
    React.useEffect(() => () => { if (active.current) active.current.abort(); }, []);
    function cancel() { if (active.current) active.current.abort(); active.current = null; setBusy(false); setFormat(null); }
    async function save() {
      if (active.current || !format) return;
      const controller = new AbortController(); active.current = controller; setBusy(true); setError(null);
      const query = { ...filterQuery, comparison_mode: data.scope.comparison_mode, resource_view: data.scope.resource_view, selected_candidate_ref: data.scope.selected_candidate_ref,
        ...(data.scope.comparison_mode === 'candidates' ? { reference_candidate_ref: data.scope.reference.candidate_ref } : {}),
        range_start: data.scope.range_start, range_end: data.scope.range_end, ...(initialSection !== 'overview' ? { filter_section: initialSection } : {}) };
      try {
        const file = await D.decisionExport(runRef, query, result.meta.snapshot_ref, format, controller.signal, section);
        if (controller.signal.aborted) return;
        window.APSWorkbenchTransport.saveBlob(file.filename, file.blob); setDone(window.WorkbenchTerms.download_started(file.filename) + ' · ' + file.row_count + ' 条记录'); setFormat(null);
      } catch (problem) { if (!controller.signal.aborted) setError(problem); }
      finally { if (!controller.signal.aborted) { active.current = null; setBusy(false); } }
    }
    return <><C.Button icon="download" busy={busy} onClick={() => { setFormat('xlsx'); setSection(initialSection); setError(null); setDone(''); }}>{initialSection === 'overview' ? '导出方案对比' : '导出' + labels[initialSection]}</C.Button>{done && <small role="status">{done}</small>}
      {format && <window.ResourceControls.Modal title={'导出' + labels[initialSection]} icon="download" onClose={cancel} footer={<><C.Button onClick={cancel}>{busy ? '取消导出' : '取消'}</C.Button><C.Button transfer="export" className="btn primary" busy={busy} onClick={save}>下载 {format.toUpperCase()}</C.Button></>}>
        <div className="modal-b"><p>{description}</p>
          <div className="rc-tools" role="radiogroup" aria-label="方案对比导出格式">{['xlsx', 'csv'].map(value => <label key={value}><input type="radio" name="decision-export-format" checked={format === value} disabled={busy} onChange={() => { setFormat(value); if (value === 'csv' && section === 'all') setSection(initialSection); }} />{value.toUpperCase()}</label>)}</div>
          <label className="rd-export-section">导出内容<select aria-label="方案对比导出内容" value={section} disabled={busy} onChange={event => setSection(event.target.value)}><option value={initialSection}>{labels[initialSection]}</option>{initialSection === 'overview' && <option value="recommendation">{labels.recommendation}</option>}{format === 'xlsx' && data.scope.selected_candidate_ref && <option value="all">整份对照：推荐与全部方案明细</option>}</select></label>
          {section === 'all' && initialSection !== 'overview' && <p className="rc-muted">{initialSection === 'process' ? '整份导出包含本轮全部优化目标，保留当前候选来源和固定对照。优化方向筛选只用于单张过程导出。' : ['preparation', 'changeovers'].includes(initialSection) ? '当前明细保留筛选；另一张表按当前设备导出。' : ['resources', 'resource-days'].includes(initialSection) ? '资源明细保留当前粒度、关注线与时段筛选。' : '当前明细保留筛选，批次条件同时应用于批次和工序明细。'}</p>}<C.ErrorBox error={error} /></div>
      </window.ResourceControls.Modal>}</>;
  }
  function comparisonContext(data, original = {}) {
    const value = { ...original, run_ref: data.run.run_ref, candidate_ref: data.scope.selected_candidate_ref, comparison_mode: data.scope.comparison_mode, resource_view: data.scope.resource_view };
    delete value.return_decision_context; delete value.batch_ref; delete value.selected_row_ref;
    ['reference_candidate_ref', 'range_start', 'range_end'].forEach(key => delete value[key]);
    if (data.scope.comparison_mode === 'candidates' && data.scope.reference_state === 'available') value.reference_candidate_ref = data.scope.reference.candidate_ref;
    if (data.scope.range_start && data.scope.range_end) { value.range_start = data.scope.range_start; value.range_end = data.scope.range_end; }
    return value;
  }
  function freshDetailQueries(values) {
    return Object.fromEntries(Object.entries(values).map(([key, value]) => {
      const next = { ...value, page: 1 }; delete next.snapshot_ref;
      if (key === 'resources') { next.heatmap_page = 1; next.day_page = 1; delete next.day_snapshot_ref; }
      return [key, next];
    }));
  }
  function DifferenceSummary({ data }) {
    const summary = data.difference_summary;
    if (!summary || summary.items.every(item => item.value === 0)) return null;
    const numeric = item => item.value === null ? '待确认' : item.value !== 0 && Number(Math.abs(item.value).toFixed(item.precision)) === 0 ? (item.value > 0 ? '+' : '−') + '<' + window.WorkbenchFormat.number(Math.pow(10, -item.precision), { digits: item.precision, trim: true }) : (item.value > 0 ? '+' : '') + window.WorkbenchFormat.number(item.value, { digits: item.precision, trim: true });
    return <div className="rd-difference-summary" aria-label="当前方案相对固定对照的三项变化">{summary.items.map(item => <div key={item.key} data-summary-metric={item.key} className={'rd-summary-metric rd-' + item.direction}>
      <span>{item.label}</span><strong title={item.value === null ? '完整差值未确认' : String(item.value)}>{numeric(item)}<small>{item.value === null ? '' : item.unit}</small></strong>
      <span>{item.value === null ? '完整差值待确认' : item.direction === 'equal' ? '持平' : item.direction === 'better' ? '改善' : item.direction === 'worse' ? '增加代价' : '变化'}</span>
      <details><summary>数值与范围</summary><small>{scopeLabels[item.scope] || '保存的共同比较范围'}</small><small>固定对照 {item.reference_value === null ? '待确认' : metricText({ value: item.reference_value }, item)} → 当前查看 {item.selected_value === null ? '待确认' : metricText({ value: item.selected_value }, item)}</small>{[['reference_coverage', '固定对照'], ['selected_coverage', '当前查看']].map(([key, label]) => item[key] && <small key={key}>{label}：已知 {countText(item[key].known_count)} / {countText(item[key].total_count)}；待确认 {countText(item[key].unknown_count)}{item[key].known_subtotal !== null && '；保存小计 ' + metricText({ value: item[key].known_subtotal }, item)}</small>)}</details>
    </div>)}</div>;
  }
  function Workspace({ initialContext, onNavigate, renderAdoption, renderTrial, navigation, runHistoryReturn, headerTitle = '方案对比', runStatus, runTiming }) {
    const [runRef, setRunRef] = React.useState(initialContext.run_ref === undefined ? null : initialContext.run_ref), [query, setQuery] = React.useState(() => {
      const value = { comparison_mode: initialContext.comparison_mode === 'admission_official' ? 'admission_official' : 'candidates', resource_view: initialContext.resource_view === 'full_candidate' ? 'full_candidate' : 'selected_batches' }; ['range_start', 'range_end', ...(value.comparison_mode === 'candidates' ? ['reference_candidate_ref'] : [])].forEach(key => { if (initialContext[key]) value[key] = initialContext[key]; });
      if (initialContext.candidate_ref) value.selected_candidate_ref = initialContext.candidate_ref; return value;
    });
    const [revision, refresh] = React.useReducer(value => value + 1, 0), [rangeOpen, setRangeOpen] = React.useState(false), [range, setRange] = React.useState(() => rangeDraft(query));
    const [rangeError, setRangeError] = React.useState(null), [historyOpen, setHistoryOpen] = React.useState(false);
    const [sourceOpen, setSourceOpen] = React.useState(false), [fullPaused, setFullPaused] = React.useState(false);
    const workspaceRef = React.useRef(null), rangeReturnFocus = React.useRef(null), referenceChoice = React.useRef(null);
    const metricView = initialContext.metric_view === 'all' ? 'all' : 'common';
    const initialDetails = initialContext.detail_queries === undefined ? {} : initialContext.detail_queries;
    const [tab, updateTab] = React.useState(() => { const requested = tabAliases[initialContext.comparison_tab] || initialContext.comparison_tab;
      return [...comparisonTabs, ...secondaryTabs, ['changeovers']].some(row => row[0] === requested) ? requested : 'delivery'; });
    const [visitedPanels, setVisitedPanels] = React.useState(() => [tab]);
    function setTab(value) { updateTab(value); setVisitedPanels(current => current.includes(value) ? current : [...current, value]); }
    const [selectedBatchRef, setSelectedBatchRef] = React.useState(initialContext.selected_batch_ref !== undefined ? initialContext.selected_batch_ref : initialContext.batch_ref !== undefined ? initialContext.batch_ref : null);
    const [detailQueries, setDetailQueries] = React.useState(() => { const initial = initialDetails, resources = { ...(initialContext.resource_kind ? { resource_kind: initialContext.resource_kind } : {}), ...(initialContext.resource_ref ? { resource_ref: initialContext.resource_ref } : {}), ...initial.resources };
      const machine = initialContext.resource_kind === 'machine' && initialContext.resource_ref ? { machine_ref: initialContext.resource_ref } : {};
      return { ...initial, ...(Object.keys(resources).length ? { resources } : {}), ...(Object.keys(machine).length ? { preparation: { ...machine, ...initial.preparation }, changeovers: { ...machine, ...initial.changeovers } } : {}) }; });
    // 各明细分区的查询条件按需出现；还没打开过的分区按空条件读取。
    const leafQuery = key => detailQueries[key] === undefined ? {} : detailQueries[key];
    const lookup = window.APSResourceSession.useQuery(signal => A.identity(initialContext.candidate_ref, signal), [initialContext.candidate_ref], !runRef && A.ref(initialContext.candidate_ref));
    React.useEffect(() => { if (lookup.result) setRunRef(lookup.result.data.run_ref); }, [lookup.result]);
    const read = window.APSResourceSession.useQuery(signal => tab === 'resources'
      ? D.resourceWorkspace(runRef, query, leafQuery('resources'), signal) : D.decisionSummary(runRef, query, signal),
    [runRef, query, revision], A.ref(runRef));
    const result = read.result, data = result && result.data, selected = data && data.candidates.find(row => row.candidate_ref === data.scope.selected_candidate_ref);
    const fullQuery = data && { comparison_mode: data.scope.comparison_mode, resource_view: data.scope.resource_view,
      selected_candidate_ref: data.scope.selected_candidate_ref, range_start: data.scope.range_start, range_end: data.scope.range_end, snapshot_ref: result.meta.snapshot_ref,
      ...(data.scope.comparison_mode === 'candidates' ? { reference_candidate_ref: data.scope.reference.candidate_ref } : {}) };
    const fullRead = window.APSResourceSession.useQuery(signal => D.decision(runRef, fullQuery, signal),
      [runRef, JSON.stringify(query), JSON.stringify(fullQuery), revision], !!data && (tab === 'metrics' || sourceOpen) && !fullPaused);
    const fullData = fullRead.result && fullRead.result.data, fullSelected = fullData && fullData.candidates.find(row => row.candidate_ref === data.scope.selected_candidate_ref);
    React.useEffect(() => {
      const root = workspaceRef.current; if (!root) return undefined;
      const moved = event => { const intent = rangeReturnFocus.current; if (intent && !(event.type === 'focusin' && event.target === root.ownerDocument.body) && event.target !== intent.entry) rangeReturnFocus.current = null; };
      root.ownerDocument.addEventListener('focusin', moved); root.ownerDocument.addEventListener('pointerdown', moved);
      return () => { root.ownerDocument.removeEventListener('focusin', moved); root.ownerDocument.removeEventListener('pointerdown', moved); };
    }, []);
    React.useEffect(() => {
      const intent = rangeReturnFocus.current; if (!intent) return;
      if (intent.tab !== tab || read.error) { rangeReturnFocus.current = null; return; }
      if (data && workspaceRef.current) { const entry = workspaceRef.current.querySelector('[data-resource-range-entry]'); rangeReturnFocus.current = null; if (entry) entry.focus(); }
    }, [data, read.error, tab]);
    const history = window.APSResourceSession.useQuery(signal => N.adoptions(selected.candidate_ref, runRef, signal), [selected && selected.candidate_ref, runRef, revision, result && result.meta.snapshot_ref], !!selected && selected.persisted_status === 'completed' && historyOpen);
    const processQuery = leafQuery('process');
    const remembered = data ? comparisonContext(data, { ...initialContext, metric_view: metricView, comparison_tab: tab, selected_batch_ref: selectedBatchRef, detail_queries: detailQueries }) : initialContext;
    window.WorkbenchPageContext.useSnapshot(remembered, !!data);
    window.WorkbenchCaption.useCaption(data && selected ? { reference: runRef, label: '当前比较', name: selected.label, status: '同次候选 · ' + data.candidates.length + ' 项' } : null);
    function resetDetailPages() { setDetailQueries(freshDetailQueries); setFullPaused(false); }
    function choose(candidate) {
      if (data && candidate.candidate_ref === data.scope.selected_candidate_ref) return;
      setQuery(value => ({ ...value, selected_candidate_ref: candidate.candidate_ref }));
      setRangeOpen(false); setRangeError(null); setHistoryOpen(false); setFullPaused(false);
      setDetailQueries(freshDetailQueries);
    }
    function reference(candidate) { setQuery(value => ({ ...value, comparison_mode: 'candidates', reference_candidate_ref: candidate.candidate_ref })); resetDetailPages(); }
    function mode(value) { setQuery(current => { const next = { ...current, comparison_mode: value }; delete next.reference_candidate_ref; return next; }); resetDetailPages(); }
    function resourceView(value) { setQuery(current => ({ ...current, resource_view: value })); resetDetailPages(); }
    const historyReturn = initialContext.return_decision_history_context || initialContext.return_decision_context && initialContext.return_decision_context.return_decision_history_context;
    const historyOrigin = historyReturn ? { return_decision_history_context: historyReturn } : {};
    function gantt(candidate) { onNavigate('gantt', { ...historyOrigin, run_ref: runRef, candidate_ref: candidate.candidate_ref, comparison_mode: data.scope.comparison_mode, resource_view: data.scope.resource_view, ...(data.scope.comparison_mode === 'candidates' ? { reference_candidate_ref: data.scope.reference.candidate_ref } : {}), ...(data.scope.range_start ? { range_start: data.scope.range_start, range_end: data.scope.range_end } : {}), return_decision_context: remembered }); }
    function drill(context) { onNavigate('gantt', { ...historyOrigin, resource_view: data.scope.resource_view, ...context, return_decision_context: remembered }); }
    function support(target) {
      const context = target.drill, pane = tabAliases[context.comparison_tab] || context.comparison_tab;
      if (!pane) { drill(context); return; }
      const detail = pane === 'differences' && context.comparison_tab === 'operations' ? { batch_ref: context.batch_ref || context.detail_query && context.detail_query.batch_ref, change_kind: 'changed', delivery_filter: 'all', sort: 'current_priority', order: 'asc', page: 1 } : { ...context.detail_query, page: 1 };
      onNavigate('analysis', { ...comparisonContext(data), ...context, ...historyOrigin, comparison_tab: pane, metric_view: metricView, selected_batch_ref: context.batch_ref || selectedBatchRef,
        detail_queries: { ...freshDetailQueries(detailQueries), [pane]: detail, ...(context.comparison_tab === 'operations' ? { 'difference-chain': { ...context.detail_query, page: 1 } } : {}) },
        return_recommendation_context: remembered });
    }
    function selectBatch(ref) {
      if (ref === selectedBatchRef) return;
      setSelectedBatchRef(ref);
      setDetailQueries(queries => {
        if ((!queries.delivery || queries.delivery.snapshot_ref === undefined) && (!queries.differences || queries.differences.snapshot_ref === undefined)) return queries;
        const next = { ...queries };
        for (const key of ['delivery', 'differences']) if (next[key] && next[key].snapshot_ref !== undefined) {
          next[key] = { ...next[key] }; delete next[key].snapshot_ref;
        }
        return next;
      });
    }
    function detailQuery(section, value) { setDetailQueries(queries => ({ ...queries, [section]: value })); }
    function chainQuery(section, value) { setDetailQueries(queries => ({ ...queries, [section === 'differences' ? 'difference-chain' : 'delivery-chain']: value })); }
    const completionQuery = leafQuery('completion-batches');
    function completionQueryChange(value) { setDetailQueries(queries => ({ ...queries, 'completion-batches': value })); }
    function openCompletion(candidate, filter) { choose(candidate); setDetailQueries(queries => {
      const next = { ...queries['completion-batches'] };
      if (filter && filter !== next.completion_filter) { next.completion_filter = filter; next.page = 1; delete next.snapshot_ref; }
      return { ...queries, 'completion-batches': next };
    }); setTab('completion'); }
    function processQueryChange(value) { setDetailQueries(queries => ({ ...queries, process: value })); }
    function openProcess(candidate) { setDetailQueries(queries => {
      const next = { ...queries.process, page: 1, process_candidate_ref: candidate.candidate_ref }; delete next.snapshot_ref;
      return { ...queries, process: next };
    }); setTab('process'); }
    function reload() { resetDetailPages(); refresh(); }
    function changeRange(nextRange) {
      const value = window.RunDecisionAPI.scope(runRef, { ...query, ...nextRange });
      const root = workspaceRef.current, entry = root && root.ownerDocument.activeElement;
      if (entry && entry.matches('[data-resource-range-entry]')) rangeReturnFocus.current = { tab, entry };
      setQuery(value); setRange(rangeDraft(value)); setRangeError(null);
      setFullPaused(false);
      setDetailQueries(values => { const next = freshDetailQueries(values), resource = next.resources;
        if (resource) { const start = M.instant(value.range_start), end = M.instant(value.range_end), focus = resource.heatmap_focus;
          if (!value.range_start || !value.range_end || resource.display_start && M.instant(resource.display_start) < start || resource.display_end && M.instant(resource.display_end) > end || focus && (M.instant(focus.start) < start || M.instant(focus.end) > end)) {
            ['display_start', 'display_end', 'day_bucket_start', 'day_bucket_end', 'day_grain', 'heatmap_focus'].forEach(key => delete resource[key]);
          }
        } return next; });
    }
    function applyRange(event, useDefault = false) {
      event.preventDefault();
      try { const time = window.WorkbenchDatePickerModel.factoryTime, next = useDefault ? { range_start: undefined, range_end: undefined } : { range_start: time(range.start), range_end: time(range.end) }, entry = workspaceRef.current && workspaceRef.current.querySelector('[data-resource-range-entry]'); if (entry) entry.focus(); changeRange(next); setRangeOpen(false); }
      catch (problem) { setRangeError(problem); }
    }
    const windowTitle = data && '统计时间：开始（包含）' + window.WorkbenchFormat.dateTime(data.scope.range_start, { seconds: true, fractions: true }) + '，结束（不含）' + window.WorkbenchFormat.dateTime(data.scope.range_end, { seconds: true, fractions: true });
    const primaryTab = tab === 'changeovers' ? 'preparation' : tab;
    const sameCandidate = data && data.scope.comparison_mode === 'candidates' && data.scope.selected_candidate_ref === data.scope.reference.candidate_ref;
    return <div className="plana run-candidate-workspace rd-workspace" ref={workspaceRef} data-run-decision-workspace><div className="rc-heading rd-heading scheduling-page-tools"><div className="rd-page-heading"><h2 className="rd-page-title">{headerTitle}</h2>{(runStatus || data && data.run.state) && <span className="rd-run-state">{window.WorkbenchTerms.run_statuses[runStatus || data.run.state] || runStatus || data.run.state}</span>}{runTiming && <span className="rd-run-state">处理用时 {window.RunPresentation.elapsed(runTiming)}</span>}</div><div className="rc-tools rd-header-tools">{navigation}<div className="rc-tools rd-return-tools">
      <C.Button icon="chevron-left" className="btn link" onClick={() => onNavigate(runHistoryReturn.view, runHistoryReturn.context)}>返回排产记录</C.Button>
      {initialContext.return_plan_context && <C.Button icon="chevron-left" className="btn link" onClick={() => onNavigate('analysis', initialContext.return_plan_context)}>返回正式计划</C.Button>}
      {initialContext.return_recommendation_context && <C.Button icon="chevron-left" className="btn link" onClick={() => onNavigate('analysis', initialContext.return_recommendation_context)}>返回原比较</C.Button>}
      </div><div className="rc-tools rd-scope-tools">
      {data && <Export key={result.meta.snapshot_ref} result={result} initialSection="overview" filterQuery={{}} />}<C.Button icon="refresh-cw" aria-label="刷新方案对比" disabled={!runRef} busy={read.loading} onClick={reload} /></div></div></div>
      <C.ErrorBox error={lookup.error || read.error} />{(read.loading || lookup.loading) && <p className="rc-muted" role="status">正在读取本次全部候选及推荐依据。</p>}
      {!runRef && !initialContext.candidate_ref && <p className="rc-empty">请从排产记录打开需要比较的候选方案。</p>}
      {data && <><div className="rd-candidate-strip-heading">{tab !== 'resources' ? <C.Button icon="calendar-days" data-resource-range-entry aria-label={windowTitle} title={windowTitle} aria-expanded={rangeOpen} onClick={() => { if (!rangeOpen) setRange({ start: data.scope.range_start, end: data.scope.range_end }); setRangeOpen(!rangeOpen); }}><span className="rd-window-value">{window.WorkbenchFormat.compactRange(data.scope.range_start, data.scope.range_end)}</span></C.Button> : <span title={windowTitle}>{window.WorkbenchFormat.compactRange(data.scope.range_start, data.scope.range_end)}</span>}<span>{data.scope.batch_refs.length} 批 / {data.scope.operation_refs.length} 道工序 · {data.candidates.length} 个候选</span></div>
        {rangeOpen && tab !== 'resources' && <form className="rc-range" onSubmit={applyRange}><label>开始（包含）<input type="text" data-picker-type="factory-local" aria-label="资源比较时间窗开始" value={range.start} onChange={event => setRange({ ...range, start: event.target.value })} /></label><label>结束（不含）<input type="text" data-picker-type="factory-local" aria-label="资源比较时间窗结束" value={range.end} onChange={event => setRange({ ...range, end: event.target.value })} /></label><C.Button icon="check" type="submit">应用时间窗</C.Button><C.Button onClick={event => applyRange(event, true)}>默认时间窗</C.Button></form>}
        <C.ErrorBox error={rangeError} /><C.Reasons rows={result.warnings} />{!data.catalog_complete && <p className="rc-notice">排产正在运行，已保存 {data.candidates.length} 个候选。刷新查看新增候选。</p>}
        <CandidateTable data={data} selectedRef={data.scope.selected_candidate_ref} referenceRef={data.scope.reference.candidate_ref} onSelect={choose} busy={read.loading} />
        <window.RunDecisionRecommendation.Panel data={data} onSelect={choose} onSupport={support} />
        <div className="rd-choice"><div className="rd-current-context">{selected && <div className="rd-selected-name"><span className="rc-muted">查看：</span><strong>{selected.label || '候选名称未填写'}</strong>{selected.persisted_status !== 'completed' && <C.Status candidate={selected} />}</div>}
          <label className="rd-reference-choice" ref={referenceChoice}>对照方案<select aria-label="候选比较基准" value={data.scope.comparison_mode === 'admission_official' ? 'admission_official' : data.scope.reference_state === 'available' ? data.scope.reference.candidate_ref : ''} onChange={event => event.target.value === 'admission_official' ? mode('admission_official') : reference(data.candidates.find(row => row.candidate_ref === event.target.value))}>
            {data.scope.comparison_mode === 'candidates' && data.scope.reference_state === 'selection_required' && <option value="">请选择对照方案</option>}{data.candidates.filter(row => row.persisted_status === 'completed').map(row => <option key={row.candidate_ref} value={row.candidate_ref}>{row.label || '候选名称未填写'}</option>)}<option value="admission_official">{data.scope.comparison_mode === 'admission_official' && data.scope.reference_state === 'available' ? data.baseline.label : '排产时的正式计划'}</option></select></label>
          {data.scope.comparison_mode === 'admission_official' && data.scope.reference_state !== 'available' && <span className="rd-official-baseline">{referenceNotice(data)}</span>}</div>{selected && <div className="rc-tools rd-current-actions">
          <C.Button icon="chart-gantt" disabled={selected.persisted_status !== 'completed'} onClick={() => gantt(selected)}>看甘特</C.Button>{renderTrial({ candidateRef: selected.candidate_ref, scope: data.scope, query: '', disabled: selected.persisted_status !== 'completed' })}
          {selected.persisted_status === 'completed' && <div className="rd-adoption-status">{renderAdoption(selected.candidate_ref, { candidateDisplay: { candidate_ref: selected.candidate_ref, label: selected.label || '候选名称未填写', batch_count: data.scope.batch_refs.length, operation_count: data.scope.operation_refs.length }, candidateCatalog: data.candidates })}</div>}</div>}</div>
        <section className="rd-candidate-section" aria-label="方案对比结果"><div className="rc-heading rd-result-nav">
          <div className="rc-tabs rd-result-tabs" role="tablist" aria-label="方案对比明细" onKeyDown={event => {
            const index = Math.max(0, comparisonTabs.findIndex(row => row[0] === primaryTab)), next = event.key === 'ArrowRight' ? (index + 1) % comparisonTabs.length : event.key === 'ArrowLeft' ? (index + comparisonTabs.length - 1) % comparisonTabs.length : event.key === 'Home' ? 0 : event.key === 'End' ? comparisonTabs.length - 1 : null;
            if (next !== null) { event.preventDefault(); setTab(comparisonTabs[next][0]); event.currentTarget.querySelector('#rd-tab-' + comparisonTabs[next][0]).focus(); }
          }}>{comparisonTabs.map(([value, label]) => <C.Button key={value} role="tab" id={'rd-tab-' + value} aria-selected={primaryTab === value} aria-controls="rd-result-panel" tabIndex={primaryTab === value ? 0 : -1} onClick={() => setTab(value === 'preparation' && primaryTab === 'preparation' ? tab : value)}>{label}</C.Button>)}</div>
          <div className="rc-tools rd-secondary-views" role="group" aria-label="更多结果">{secondaryTabs.map(([value, label]) => <C.Button key={value} className="btn link" id={'rd-tab-' + value} aria-pressed={tab === value} aria-controls="rd-result-panel" onClick={() => { setTab(value); if (value === 'metrics') setFullPaused(false); }}>{label}</C.Button>)}</div>
        </div><div id="rd-result-panel" role="tabpanel" aria-labelledby={'rd-tab-' + primaryTab}>
          {primaryTab === 'preparation' && <div className="rc-tabs rd-preparation-tabs" role="group" aria-label="准备与切换内容">{[['preparation', '准备需求'], ['changeovers', '工种切换']].map(([value, label]) => <C.Button key={value} aria-pressed={tab === value} onClick={() => setTab(value)}>{label}</C.Button>)}</div>}
          {tab === 'differences' && !sameCandidate && <DifferenceSummary data={data} />}
          {[...comparisonTabs, ...secondaryTabs, ['changeovers']].filter(([panel]) => visitedPanels.includes(panel)).map(([panel]) => <div key={panel + ':' + (data.scope.selected_candidate_ref || 'no-candidate') + ':' + data.scope.comparison_mode} hidden={tab !== panel} data-decision-panel={panel}>
            {panel === 'metrics' ? <><FullReadStatus read={fullRead} paused={fullPaused} onCancel={() => setFullPaused(true)} onReload={reload} />{fullData && <Details data={fullData} selectedRef={data.scope.selected_candidate_ref} />}</>
              : panel === 'process' ? <window.RunDecisionProcess.Pane result={result} query={processQuery} onQuery={processQueryChange} enabled={tab === panel} />
              : panel === 'completion' ? selected ? <window.RunDecisionCompletion.Pane result={result} query={completionQuery} onQuery={completionQueryChange} onSupport={support} enabled={tab === panel} /> : <p className="rc-empty">选择当前方案查看工序安排。</p>
              : selected && selected.persisted_status === 'completed' ? panel === 'resources' ? <window.RunDecisionResources.Pane result={result} query={leafQuery(panel)} onQuery={value => detailQuery(panel, value)} onView={resourceView} onRange={changeRange} onDrill={drill} enabled={tab === panel} />
                : ['preparation', 'changeovers'].includes(panel) ? <window.RunDecisionPreparation.Pane result={result} section={panel} query={leafQuery(panel)} onQuery={value => detailQuery(panel, value)} onDrill={drill} enabled={tab === panel} />
                  : <window.RunDecisionDetails.Pane result={result} section={panel === 'differences' ? 'differences' : 'delivery'} query={leafQuery(panel)} onQuery={value => detailQuery(panel, value)} selectedBatchRef={selectedBatchRef} onSelectBatch={selectBatch} chainQuery={leafQuery(panel === 'differences' ? 'difference-chain' : 'delivery-chain')} onChainQuery={value => chainQuery(panel, value)} onDrill={drill} onChooseReference={() => { const target = referenceChoice.current && referenceChoice.current.querySelector('select'); if (target) target.focus(); }} enabled={tab === panel} />
                : <div className="rc-empty"><p>{selected ? (selected.label || '当前候选') + '：' + window.WorkbenchTerms.candidate_statuses[selected.persisted_status] : '请选择候选查看明细。'}</p>{selected && selected.source && selected.source.reason && <p>{selected.source.reason.message}</p>}</div>}
          </div>)}
        </div></section>
        {selected && selected.persisted_status === 'completed' && <details className="rd-official" open={historyOpen} onToggle={event => setHistoryOpen(event.currentTarget.open)}><summary>此方案的采用记录</summary><C.ErrorBox error={history.error} />{history.loading && <p role="status">正在读取此方案的采用记录。</p>}{history.result && <window.RunCandidateAnalysis.History data={history.result.data} onPlan={plan => onNavigate('analysis', { ...historyOrigin, plan_ref: plan.plan_ref, return_decision_context: remembered })} />}</details>}
        <details className="rd-official rd-data-source" open={sourceOpen} onToggle={event => { setSourceOpen(event.currentTarget.open); if (event.currentTarget.open) setFullPaused(false); }}><summary>数据来源</summary>{sourceOpen && <><FullReadStatus read={fullRead} paused={fullPaused} onCancel={() => setFullPaused(true)} onReload={reload} />{fullSelected && <CandidateFacts data={fullData} candidate={fullSelected} onCompletion={openCompletion} onProcess={openProcess} />}</>}<dl className="rc-meta"><div><dt>开始计算</dt><dd>{M.timeLabel(data.run.accepted_at)}</dd></div><div><dt>计算结束</dt><dd>{M.timeLabel(data.run.finished_at)}</dd></div><div><dt>候选搜索</dt><dd><RunCoverage data={data} /></dd></div><div><dt>资料依据</dt><dd>排产时选中的批次和工序、保存的候选安排与推荐原因</dd></div><div><dt>资源和切换比较范围</dt><dd>{windowTitle}</dd></div><div><dt>本次刷新时间</dt><dd>{window.WorkbenchFormat.dateTime(result.meta.as_of, { seconds: true, fractions: true })}</dd></div></dl><window.WorkbenchReference entries={{ '排产记录': runRef, '当前查看候选': data.scope.selected_candidate_ref, '比较基准': data.scope.reference.candidate_ref }} /></details>
      </>}</div>;
  }
  window.RunDecisionComparison = { Workspace, CandidateTable, CandidateFacts, DifferenceSummary, Details, Coverage, RunCoverage, Export, Metric, CompactValue, metricText, deltaText, comparisonContext, referenceNotice };
})();
