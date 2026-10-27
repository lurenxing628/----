'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const { compile } = require('../../scripts/workbench/compile.cjs');
const { routeFetch, browser, loadTransport, json, file, failure } = require('./route_fetch.cjs');
const root = path.resolve(__dirname, '../..'), app = path.join(root, 'frontend/workbench/app');
const runRef = 'a'.repeat(48), first = 'b'.repeat(48), recommended = 'c'.repeat(48), third = 'd'.repeat(48);
const snapshot = 's'.repeat(32), range_start = '2026-10-01T00:00:00', range_end = '2026-10-05T00:00:00';
const coreMetricKeys = ['expected_operation_count', 'scheduled_operation_count', 'unplanned_operation_count', 'deferred_operation_count', 'overdue_count', 'total_tardiness_hours', 'makespan_hours', 'weighted_tardiness_hours', 'elapsed_seconds', 'changeover_count', 'machine_used_count', 'operator_used_count', 'machine_busy_hours_total', 'operator_busy_hours_total', 'machine_util_avg', 'operator_util_avg'];
// Transport contracts send requests through the real RunDecisionAPI, APSWorkbenchTransport and validators; only the network answer comes from these routes.
const routes = {}, network = routeFetch(routes), DECISION = 'GET /api/workbench/v1/scheduling/runs/*/decision';
const h = (type, props, ...children) => ({ type, props: props || {}, children: children.flat(Infinity).filter(value => value !== null && value !== false && value !== undefined) });
const writes = [], navigation = [], remembered = [];
const React = { createElement: h, Fragment: 'fragment', useId: () => 'process-chart', useMemo: fn => fn(), useState: initial => { let value = typeof initial === 'function' ? initial() : initial; return [value, update => { value = typeof update === 'function' ? update(value) : update; writes.push(value); }]; }, useRef: initial => ({ current: initial }), useEffect: () => {}, useReducer: () => [0, () => {}] };
const window = { ResourceControls: { Button: 'button', Modal: 'modal' }, WorkbenchReference: 'reference', PointContract: {},
  RunCandidateControls: { Button: 'button', Pager: 'pager', Status: 'candidate-status', ErrorBox: 'error-box', Reasons: 'reasons' }, RunCandidateModel: { number: String, timeLabel: value => value || '未记录' },
  WorkbenchPageContext: { useSnapshot: value => remembered.push(value) }, WorkbenchCaption: { useCaption: () => {} },
  APSResourceSession: { useQuery: (load, deps, enabled = true) => ({ result: enabled ? load() : null, loading: false, error: null }) }, RunCandidateAnalysis: {}, RunDecisionDetails: { Pane: 'detail-pane' } };
const files = ['WorkbenchFormat.js', 'WorkbenchTerms.js', 'resource-contract.js', 'FieldContract.js', 'PointContract.js', 'DeliveryProjectionContract.js', 'RunGenerationContract.js', 'RunCandidateAPI.js', 'RunBaselineAPI.js', 'RecommendationContract.js', 'EffortProjectionContract.js', 'RunDecisionAPI.js', 'RunDecisionRecommendation.jsx', 'RunDecisionComparison.jsx', 'RunDecisionCompletion.jsx', 'RunDecisionProcessChart.jsx', 'RunDecisionProcess.jsx'];
const built = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources: files.map(name => ({ path: name, code: fs.readFileSync(path.join(app, name), 'utf8') })) });
{ const transport = vm.createContext({ window }); browser(transport, network); loadTransport(transport); }
for (const file of built.outputs) vm.runInNewContext(file.code, { React, window, AbortController, setTimeout, clearTimeout, URLSearchParams });
const definitions = [
  ['overdue_count', '超期批次', 'delivery', '批'], ['total_tardiness_hours', '总拖期', 'delivery', '小时'],
  ['makespan_hours', '安排时长', 'time', '小时'], ['changeover_count', '换型次数', 'preparation', '次'],
  ['changed_operation_count', '安排变化', 'stability', '道'], ['scheduled_setup_hours', '已排准备标准工时', 'preparation', '小时'],
  ['machine_high_pressure_count', '设备高压力资源', 'resources', '台'], ['operator_high_pressure_count', '人员高压力资源', 'resources', '人'], ['type_changeover_count', '工种切换次数', 'preparation', '次'],
  ...coreMetricKeys.filter(key => !['overdue_count', 'total_tardiness_hours', 'makespan_hours', 'changeover_count'].includes(key)).map(key => [key, key, 'time', ''])
].map(([key, label, group, unit], index) => ({ key, label, group, unit, precision: 3, common: index !== 2, metric_version: 'decision-preparation-v4',
  scope: group === 'resources' ? 'fixed_resource_window' : key === 'type_changeover_count' ? 'fixed_changeover_window' : ['makespan_hours', 'changeover_count'].includes(key) ? 'full_candidate' : 'full_admission',
  source: group === 'resources' ? 'archived_resource_calendar' : key === 'changed_operation_count' ? 'candidate_comparison' : key === 'scheduled_setup_hours' ? 'runtime_operation_effort' : key === 'type_changeover_count' ? 'archived_changeover_events' : ['makespan_hours', 'changeover_count'].includes(key) ? 'saved_algorithm' : 'archived_delivery' }));
const metric = { scope: 'full_admission', value: 2, state: 'complete', known_subtotal: 2, known_count: 3, unknown_count: 0, total_count: 3, reason: null, metric_version: 'decision-preparation-v4' };
const delta = { value: -1, state: 'comparable', direction: 'better', reference_value: 3, selected_value: 2 };
const clone = value => JSON.parse(JSON.stringify(value));
const G = window.RunGenerationContract;
// Candidates come only from the unified search by business objective, carrying its generation metadata (RunGenerationContract.metadataKeys).
const objectives = ['min_overdue', 'min_tardiness', 'min_changeover'];
const scoringScope = { scheduled_operation_refs: [], complete_batch_refs: ['e'.repeat(48)], objective_scope: 'all_batches', components_known: true, is_complete: true };
const score = (objective, index) => G.fieldOrders[objective].map((_, field) => field ? index + 1 : 0);
const generation = (objective, index) => ({ generation_policy_version: 'unified_search_v1', representative_objectives: [objective],
  evaluations: { [objective]: { field_order: G.fieldOrders[objective], score: score(objective, index), scoring_scope: clone(scoringScope) } },
  origin: { search_objective: objective, phase: 'construct', origin: 'seed', dispatch_mode: null, dispatch_rule: null, strategy: 'greedy', repair_decision: null },
  first_found_elapsed_ms: 10 * (index + 1), search_evidence_ref: { run_ref: runRef, source_event_id: null } });
const candidateObjectives = ['min_tardiness', 'min_overdue', 'min_changeover'];
const candidates = [first, recommended, third].map((candidate_ref, index) => ({ candidate_ref, label: ['拖期更轻方案', '交期优先方案', '切换更少方案'][index], kind: 'business_objective', status: 'completed', persisted_status: 'completed', completeness: 'complete', task_count: 3,
  ...generation(candidateObjectives[index], index), selection_role: index === 1 ? ['recommended', 'min_overdue'] : [candidateObjectives[index]],
  capabilities: { view: true, compare: true, gantt: true, adoption_preview: true, adopt: false },
  coverage: { search: { state: 'complete', completed_count: 3, total_count: 3 }, schedulable: { state: 'complete', scheduled_count: 3, expected_count: 3, missing_count: 0, deferred_count: 1 }, delivery: { complete_batch_count: 1, batch_count: 2, deferred_batch_count: 1 } },
  metrics: Object.fromEntries(definitions.map(row => [row.key, { ...metric }])), deltas: Object.fromEntries(definitions.map(row => [row.key, { ...delta }])) }));
// Recommendation follows business_objectives_v1: the saved primary objective, per-objective winners and the selected score; the old health evidence slots stay null.
const basis = { generation_policy_version: 'unified_search_v1', selection_policy_version: 'business_objectives_v1', primary_objective: 'min_overdue', target_objectives: objectives,
  selected_candidate_ref: recommended, objective_winners: { min_overdue: recommended, min_tardiness: first, min_changeover: null }, objective_winner_reasons: { min_overdue: null, min_tardiness: null, min_changeover: '本轮未保存该方向的代表方案。' },
  objective_field_order: Object.fromEntries(objectives.map(name => [name, G.fieldOrders[name]])), selected_score: score('min_overdue', 1), reason_code: 'primary_objective_best_found',
  scoring_scope: clone(scoringScope), evidence_state: 'partial',
  explanation: { headline: '按“最少超期”推荐本次找到的最佳完整方案。', entries: [
    { key: 'shared_objectives', label: '共同优化', text: '多个业务方向共用一次求解和一份安排档案。', state: 'complete', unit: null, selected_value: null, source: 'saved_selection', scope: 'shared_search' },
    { key: 'score_failed_ops', label: '未安排工序', text: '按计算时保存的完整指标顺序选择。', state: 'complete', unit: '道', selected_value: 0, source: 'saved_selection', scope: 'saved_scoring_scope' },
    { key: 'score_total_tardiness_hours', label: '总拖期', text: '按计算时保存的完整指标顺序选择。', state: 'complete', unit: '小时', selected_value: 2, source: 'saved_selection', scope: 'saved_scoring_scope' }
  ], issues: [{ code: 'score_components_unavailable', message: '所选范围缺少完整评分分量。' }] } };
const runOptions = { generation_policy_version: 'unified_search_v1', primary_objective: 'min_overdue', target_objectives: objectives, time_budget_seconds: 10, algo_mode: 'improve', graph_analysis_mode: 'off' };
const prepKeys = ['pending_setup_hours', 'scheduled_setup_hours', 'unplanned_setup_hours', 'deferred_setup_hours', 'pending_processing_hours', 'scheduled_processing_hours', 'unplanned_processing_hours', 'deferred_processing_hours'];
const completionScope = { scope: 'full_admission', state: 'partial', source_available: true, complete_batch_count: 1, incomplete_batch_count: 1, ordinary_incomplete_batch_count: 0, deferred_batch_count: 1, unknown_batch_count: 0,
  unplanned_operation_count: 0, deferred_operation_count: 1, sample_batch_refs: { complete: ['e'.repeat(48)], incomplete: [], deferred: [], unknown: [] },
  remaining_work: { metrics: Object.fromEntries(prepKeys.map(key => [key, { ...metric }])), operation_count: 1, unplanned_operation_count: 0, deferred_operation_count: 1 },
  drill: { run_ref: runRef, candidate_ref: recommended, reference_candidate_ref: first, comparison_mode: 'candidates', resource_view: 'selected_batches', range_start, range_end, selected_candidate_ref: recommended, comparison_tab: 'preparation', detail_query: { work_scope: 'remaining' } } };
const allDifferences = definitions.map((definition, index) => {
  const neutral = definition.key === 'scheduled_setup_hours', direction = neutral ? 'neutral' : index < 4 ? 'better' : 'worse';
  const tab = definition.group === 'delivery' || definition.group === 'time' ? 'batches' : definition.group === 'resources' ? 'resources' : definition.group === 'stability' ? 'operations' : definition.key === 'type_changeover_count' ? 'changeovers' : 'preparation';
  return { metric_key: definition.key, label: neutral ? '少安排的准备需求' : definition.label, unit: definition.unit, precision: definition.precision,
    value: direction === 'worse' ? 1 : -1, reference_value: 3, selected_value: direction === 'worse' ? 4 : 2, state: neutral ? 'different_coverage' : 'comparable', direction,
    scope: definition.group === 'delivery' ? 'common_completed_batches' : definition.scope, source: definition.source, metric_version: 'decision-preparation-v4', reason: neutral ? { code: 'fewer_arranged_operations', message: '减少来自未安排需求，具体剩余工序另列。' } : null,
    text: neutral ? '少安排的准备需求；减少来自未安排工序，方向保持中性。' : definition.label + '按本次保存差值核对。', compared_batch_count: definition.group === 'delivery' ? 1 : null, sample_compared_batch_refs: definition.group === 'delivery' ? ['e'.repeat(48)] : [],
    supporting_refs: [{ kind: { batches: 'batch', resources: 'resource', operations: 'operation', preparation: 'preparation', changeovers: 'changeover' }[tab], ref: 'e'.repeat(48), candidate_ref: recommended,
      drill: { run_ref: runRef, candidate_ref: recommended, reference_candidate_ref: first, comparison_mode: 'candidates', resource_view: 'selected_batches', range_start, range_end, comparison_tab: tab, detail_query: {} } }] };
});
const data = { run: { run_ref: runRef, accepted_at: range_start, finished_at: range_end }, scope: { run_ref: runRef, comparison_mode: 'candidates', resource_view: 'selected_batches', resource_refs: { machine: [], operator: [] }, selected_candidate_ref: third, reference: { kind: 'candidate', candidate_ref: first }, reference_state: 'available', range_start, range_end, batch_refs: ['e'.repeat(48)], operation_refs: ['f'.repeat(48)], run_options: runOptions }, candidates, metric_definitions: definitions, metric_version: 'decision-preparation-v4', catalog_complete: true,
  baseline: { kind: 'candidate', candidate_ref: first, baseline_ref: null, version: null, label: candidates[0].label, state: 'available', source_candidate_ref: null },
  completion_groups: [{ group_index: 1, source_available: true, candidate_refs: [first, recommended, third], complete_batch_count: 1, sample_complete_batch_refs: ['e'.repeat(48)] }],
  recommendation: { recommendation_version: 'decision-recommendation-v1', candidate_ref: recommended, viewed_candidate_ref: third, state: 'available', recommendation_type: 'schedulable_scope', headline: '本次应排工序已安排，待料工序继续暂缓。',
    axes: { algorithm: { state: 'selected', reason_code: basis.reason_code, evidence_state: basis.evidence_state }, completion: { search: candidates[1].coverage.search, schedulable: candidates[1].coverage.schedulable, delivery: completionScope }, preflight: { state: 'not_checked', source: 'existing_adoption_preview' } }, completion_scope: completionScope,
    current_comparison: { state: 'available', candidate_ref: recommended, viewed_candidate_ref: third, reference: { kind: 'candidate', candidate_ref: first }, benefits: allDifferences.filter(row => row.direction === 'better').slice(0, 3), costs: allDifferences.filter(row => row.direction === 'worse').slice(0, 3), all_differences: allDifferences,
      common_completed_delivery: { scope: 'common_completed_batches', state: 'complete', batch_count: 1, sample_batch_refs: ['e'.repeat(48)], before: { total_tardiness_hours: 3 }, after: { total_tardiness_hours: 2 }, delay_delta_hours: -1, overdue_delta_count: -1 } } }, selection_basis: basis };
data.baseline.metrics = JSON.parse(JSON.stringify(candidates[0].metrics)); data.baseline.coverage = JSON.parse(JSON.stringify(candidates[0].coverage));
data.difference_summary = { scope: 'full_admission', items: ['overdue_count', 'total_tardiness_hours', 'makespan_hours'].map(key => ({ ...definitions.find(row => row.key === key), ...delta, reference_coverage: { ...metric }, selected_coverage: { ...metric } })) };
const payload = { ok: true, schema_version: 1, data, warnings: [], meta: { request_ref: '1'.repeat(32), source: 'production', time_basis: 'factory_local', snapshot_ref: snapshot, as_of: range_end } };
const summaryPayload = clone(payload); delete summaryPayload.data.completion_groups;
for (const row of [...summaryPayload.data.candidates, summaryPayload.data.baseline]) { row.metrics = Object.fromEntries(coreMetricKeys.map(key => [key, row.metrics[key]])); if (row.deltas) row.deltas = Object.fromEntries(coreMetricKeys.map(key => [key, row.deltas[key]])); }
delete summaryPayload.data.baseline.coverage.search;
function bindRecommendationScope(value) {
  const { scope, recommendation: rec } = value.data, current = rec.current_comparison;
  rec.viewed_candidate_ref = current.viewed_candidate_ref = scope.selected_candidate_ref; current.reference = clone(scope.reference);
  const targets = [...current.all_differences, ...current.benefits, ...current.costs].flatMap(row => row.supporting_refs).map(row => row.drill);
  if (rec.completion_scope && rec.completion_scope.drill) targets.push(rec.completion_scope.drill);
  for (const target of targets) {
    target.comparison_mode = scope.comparison_mode; target.resource_view = scope.resource_view;
    target.range_start = scope.range_start; target.range_end = scope.range_end;
    if (scope.comparison_mode === 'candidates') target.reference_candidate_ref = scope.reference.candidate_ref;
    else delete target.reference_candidate_ref;
  }
  return value;
}
function expand(node) { if (!node || typeof node !== 'object') return node; if (typeof node.type === 'function') return expand(node.type({ ...node.props, children: node.children })); return { ...node, children: node.children.map(expand) }; }
function nodes(node) { return !node || typeof node !== 'object' ? [] : [node, ...node.children.flatMap(nodes)]; }
function text(node) { return node == null ? '' : typeof node !== 'object' ? String(node) : node.children.map(text).join(' '); }
function visibleText(node) { if (node == null || typeof node !== 'object') return node == null ? '' : String(node); return node.type === 'details' && !node.props.open ? visibleText(node.children.find(child => child && child.type === 'summary')) : node.children.map(visibleText).join(' '); }
const D = window.RunDecisionComparison, API = window.RunDecisionAPI;
const comparisonCode = built.outputs.find(output => output.path === 'RunDecisionComparison.jsx').code;
// Component-ownership renders answer the Workspace's own reads on its RunDecisionAPI object (a deviation from fetch-level stubs for synchronous renders);
// the HTTP path and validators of decisionSummary/decision/resourceWorkspace are covered by transportContracts.
function comparisonWindow(reads, extra = {}, react = React) {
  const local = { ...window, ...extra, RunDecisionAPI: { ...API, ...reads } };
  vm.runInNewContext(comparisonCode, { React: react, window: local, AbortController, DOMException });
  return local;
}
const comparisonWorkspace = (reads, extra) => comparisonWindow(reads, extra).RunDecisionComparison.Workspace;
// The single production mount (SchedulingWorkspace) always passes these props.
const workspaceDefaults = { onNavigate: () => {}, renderAdoption: () => null, renderTrial: () => null, runHistoryReturn: { view: 'analysis', context: {} } };
// The resource workspace answer carries the embedded resource read and its effective filters inside data.
function resourceWorkspaceFixture(value, saved = {}) {
  return { ...value, data: { ...value.data, resource_query: API.resourceFilters(API.savedResourceView(API.resourceFilters(saved), value.data.scope.resource_refs, value.data.scope)),
    resource_result: { ok: false, committed: false, status: 409, error: { code: 'snapshot_stale', message: '资源快照已变化，请刷新资源影响。', fields: [], retryable: false, request_ref: '1'.repeat(32) } } } };
}
const query = { selected_candidate_ref: third, reference_candidate_ref: first, range_start, range_end };
assert.strictEqual(API.validateDecision(payload, runRef, query), data);
const wrongRun = clone(payload); wrongRun.data.run.run_ref = third;
assert.throws(() => API.validateDecision(wrongRun, runRef, query), /排产记录/);
const wrongReference = clone(payload); wrongReference.data.scope.reference.candidate_ref = third;
assert.throws(() => API.validateDecision(wrongReference, runRef, query), /基准/);
const wrongSelected = clone(payload); wrongSelected.data.scope.selected_candidate_ref = recommended;
assert.throws(() => API.validateDecision(wrongSelected, runRef, query), /查看方案/);
const table = expand(h(D.CandidateTable, { data, selectedRef: third, referenceRef: first, onSelect: row => writes.push(row.candidate_ref), onReference: row => writes.push(row.candidate_ref), busy: false }));
assert.equal(nodes(table).filter(node => node.props['data-decision-candidate']).length, 3, '全部候选始终进入真实方案卡片');
assert.equal(nodes(table).filter(node => node.props.className === 'rd-candidate-choice' && node.props['aria-pressed']).length, 1);
assert(!text(table).includes('正在查看') && !nodes(table).some(node => node.type === 'candidate-status'), '选中由aria与外框表达，完成候选卡省去重复成功状态');
const baselineCard = nodes(table).find(node => node.props['data-decision-candidate'] === first);
assert(text(baselineCard).includes('对照'));
const partialData = clone(data), longReason = '部分批次的全链安排或交期资料缺失，已知小计列出当前可核对的交付结果。';
partialData.candidates.forEach(candidate => { for (const [key, subtotal] of [['overdue_count', 1], ['total_tardiness_hours', 11.61]]) {
  candidate.metrics[key] = { ...candidate.metrics[key], value: null, state: 'partial', known_subtotal: subtotal, known_count: 9, unknown_count: 1, total_count: 10, reason: { code: 'delivery_incomplete', message: longReason } };
  candidate.deltas[key] = { value: null, state: 'unavailable', direction: 'neutral', reference_value: null, selected_value: null };
} });
const partialTable = expand(h(D.CandidateTable, { data: partialData, selectedRef: third, referenceRef: first, onSelect: () => {}, onReference: () => {}, busy: false }));
const partialVisible = visibleText(partialTable).replace(/\s+/g, ' ');
assert(partialVisible.includes('1 批待确认') && partialVisible.includes('已知拖期 11.61 小时'), '常用行保留实际待确认批次与有单位的已知交付小计');
const partialCard = nodes(partialTable).find(node => node.props['data-decision-candidate'] === third);
assert.equal(visibleText(partialCard).split('1 批待确认').length - 1, 1, '同卡只提示一次未知交付范围');
for (const [key, expected] of [['overdue_count', '1 批'], ['total_tardiness_hours', '11.61 小时']]) {
  const field = nodes(partialCard).find(node => node.props['data-card-metric'] === key);
  assert.equal(text(nodes(field).find(node => node.type === 'strong')).trim(), expected, '已知小计作为主值并保留单位：' + key);
}
const zeroAndUnknown = clone(partialData);
for (const key of ['overdue_count', 'total_tardiness_hours']) {
  zeroAndUnknown.candidates[0].metrics[key] = { ...zeroAndUnknown.candidates[0].metrics[key], value: null, known_count: 0, unknown_count: 10, known_subtotal: 0, state: 'unavailable' };
  zeroAndUnknown.candidates[1].metrics[key] = { ...zeroAndUnknown.candidates[1].metrics[key], value: 0, known_count: 10, unknown_count: 0, known_subtotal: 0, state: 'complete' };
}
const zeroCards = expand(h(D.CandidateTable, { data: zeroAndUnknown, selectedRef: third, referenceRef: first, onSelect: () => {}, onReference: () => {}, busy: false }));
const unknownCard = nodes(zeroCards).find(node => node.props['data-decision-candidate'] === first), actualZeroCard = nodes(zeroCards).find(node => node.props['data-decision-candidate'] === recommended);
assert(nodes(unknownCard).filter(node => node.props['data-card-metric']).every(node => text(nodes(node).find(field => field.type === 'strong')).trim() === '未知'), '没有已知对象时保存小计0继续显示未知');
assert(!visibleText(unknownCard).includes('已知超期') && !visibleText(unknownCard).includes('已知拖期'));
assert.deepEqual(nodes(actualZeroCard).filter(node => node.props['data-card-metric']).map(node => text(nodes(node).find(field => field.type === 'strong')).trim()), ['0 批', '0 小时'], '真实完整零值保留零与单位');
assert(partialVisible.includes(window.WorkbenchTerms.missing_arrangements(0, 1)), '缺料未安排仍由共同工序摘要展示');
const partialFacts = expand(h(D.CandidateFacts, { data: partialData, candidate: partialData.candidates[2] }));
assert(!partialVisible.includes(longReason) && text(partialFacts).includes(longReason), '完整缺项理由在当前候选全宽原生依据中保留');
assert.equal(nodes(partialTable).filter(node => node.type === 'details').length, 0, '方案卡片只承载候选身份与共同核心事实');
const fullMetrics = expand(h(D.Details, { data: partialData, selectedRef: third })); assert(text(fullMetrics).includes(longReason) && !visibleText(fullMetrics).includes(longReason), '原全部指标矩阵保留可展开完整依据，默认省略长原因');
const Recommendation = window.RunDecisionRecommendation.Panel, recommendedLabel = data.candidates.find(candidate => candidate.candidate_ref === recommended).label;
const recommendation = expand(h(Recommendation, { data, onSelect: row => writes.push(row.candidate_ref), onSupport: () => {} }));
assert(text(recommendation).includes(recommendedLabel), '查看第三候选仍展示保存的推荐');
assert(text(recommendation).includes('共同优化') && text(recommendation).includes('未安排工序'), '推荐详情展示保存的共同优化选择依据');
nodes(recommendation).find(node => node.type === 'button' && node.props['aria-label'] === '查看推荐方案：' + recommendedLabel).props.onClick();
assert.equal(writes.at(-1), recommended);
const original = { run_ref: runRef, candidate_ref: third, selected_batch_ref: 'e'.repeat(48), return_history_context: { accepted_from: '2026-10-01', accepted_to: '2026-10-14', state: 'complete', sort: 'accepted_at', order: 'asc', page: 2, size: 20 }, range_start, range_end, reference_candidate_ref: first };
const runHistoryReturn = { view: 'analysis', context: { source: 'run_history', history_topic: 'run_catalog', history_query: original.return_history_context } };
const workspace = expand(h(comparisonWorkspace({ decisionSummary: () => payload }), { ...workspaceDefaults, initialContext: original, runHistoryReturn, onNavigate: (page, context) => navigation.push({ page, context }), renderAdoption: (ref, metadata) => h('adoption', { candidateRef: ref, ...metadata }) }));
const workspaceRemembered = remembered.at(-1);
window.RunDecisionResources = { Pane: 'resource-pane' };
const resourceEntry = expand(h(comparisonWorkspace({ resourceWorkspace: (reference, q, saved) => resourceWorkspaceFixture(summaryPayload, saved) }), { ...workspaceDefaults, initialContext: { ...original, comparison_tab: 'resources', resource_kind: 'operator', resource_ref: '0'.repeat(48) } }));
assert.equal(nodes(resourceEntry).find(node => node.type === 'resource-pane').props.query.resource_kind, 'operator', '显式分析入口消费公有资源种类');
assert.equal(nodes(resourceEntry).find(node => node.type === 'resource-pane').props.query.resource_ref, '0'.repeat(48), '显式分析入口消费公有资源身份');
assert.equal(nodes(workspace).filter(node => node.props['data-decision-candidate']).length, 3, '默认展示全部候选卡片');
assert.equal(nodes(workspace).find(node => node.type === 'detail-pane').props.section, 'delivery', '默认阅读当前交期与未排');
assert.equal(nodes(workspace).filter(node => node.type === 'table' && node.props['aria-label'] === '全部候选详细指标比较').length, 0, '全部指标表按需打开');
assert.equal(nodes(workspace).filter(node => node.props.className === 'rd-run-coverage').length, 1, '本次搜索覆盖只在共同范围栏展示一次');
const gantt = nodes(workspace).find(node => node.type === 'button' && text(node) === '看甘特');
gantt.props.onClick();
const target = navigation.at(-1);
assert.equal(target.page, 'gantt'); assert.equal(target.context.candidate_ref, third); assert.equal(target.context.reference_candidate_ref, first);
assert.deepEqual(clone(target.context.return_decision_context), clone(workspaceRemembered), '甘特返回上下文完整保留基准、查看候选、时间窗和来源');
assert.equal(target.context.return_decision_context.range_start, range_start); assert.deepEqual(clone(target.context.return_decision_context.return_history_context), original.return_history_context);
assert.equal(target.context.return_decision_context.selected_batch_ref, original.selected_batch_ref, '返回同一批次阅读锚');
assert.equal(nodes(workspace).find(node => node.type === 'adoption').props.candidateRef, third, '采用入口对应当前查看候选');
assert.deepEqual(clone(nodes(workspace).find(node => node.type === 'adoption').props.candidateDisplay), { candidate_ref: third, label: candidates[2].label, batch_count: 1, operation_count: 1 }, '采用名称、候选身份与计算范围来自同份共同选择资料');
const batchRef = 'e'.repeat(48), operationRef = 'f'.repeat(48), resourceRef = '0'.repeat(48), planRef = '1'.repeat(48);
const rowRef = '2'.repeat(48), secondSegmentRef = '3'.repeat(48), otherRowRef = '4'.repeat(48), missingOperationRef = '5'.repeat(48);
const readOnly = { view: true, export: false, edit_draft: false, adopt: false, report_actual: false };
const candidateBaseline = clone(data.baseline);
const officialBaseline = { kind: 'admission_official', candidate_ref: null, baseline_ref: planRef, plan_ref: planRef, version: 7,
  label: '受理时正式计划 v7', state: 'available', source_candidate_ref: recommended, source_run_ref: first };
function comparisonScope(query = {}) {
  const formal = query.comparison_mode === 'admission_official';
  return { ...clone(data.scope), selected_candidate_ref: query.selected_candidate_ref || third,
    comparison_mode: formal ? 'admission_official' : 'candidates',
    reference: formal ? { kind: 'admission_official', baseline_ref: planRef } : { kind: 'candidate', candidate_ref: query.reference_candidate_ref || first },
    range_start: query.range_start || range_start, range_end: query.range_end || range_end };
}
function detailsFixture(section, query = {}) {
  const formal = query.comparison_mode === 'admission_official', scope = comparisonScope(query);
  const drill = { run_ref: runRef, candidate_ref: scope.selected_candidate_ref, comparison_mode: scope.comparison_mode,
    ...(formal ? {} : { reference_candidate_ref: scope.reference.candidate_ref }), range_start: scope.range_start, range_end: scope.range_end, batch_ref: batchRef, operation_ref: operationRef };
  return { ...clone(payload), data: { run_ref: runRef, scope, baseline: formal ? clone(officialBaseline) : clone(candidateBaseline),
    candidate: { candidate_ref: scope.selected_candidate_ref, label: '均衡候选' },
    filters: { section, batch_ref: query.batch_ref || null, resource_ref: section === 'operations' ? query.resource_ref || null : null,
      change_kind: query.change_kind || 'all', sort: query.sort || (section === 'batches' ? 'worsened' : 'sequence'), order: query.order || (section === 'batches' ? 'desc' : 'asc') },
    filter_options: { batches: [{ ref: batchRef, label: 'B-001' }], resources: section === 'operations' ? [{ ref: resourceRef, label: '车床', kind: 'machine' }] : [] },
    items: [{ batch_ref: batchRef, operation_ref: operationRef, before: { row_ref: otherRowRef }, after: { row_ref: rowRef }, change_kinds: ['moved'],
      drill: { selected: drill, reference: formal ? { ...drill, reference_view: true, plan_ref: planRef } : { ...drill, candidate_ref: first } } }],
    page: { number: query.page || 1, size: query.size || 20, total: 21, has_more: (query.page || 1) === 1 },
    summary: { operation_changes: { changed_operation_count: { ...metric }, machine_change_count: { ...metric } }, before: {}, after: {}, common_completed_batch_refs: [batchRef], common_delivery: { before: {}, after: {}, delay_delta_hours: 0, overdue_delta_count: 0 } },
    metric_version: 'decision-delivery-v2' } };
}
function referenceFixture(query = {}) {
  return { ...clone(payload), data: { plan_ref: planRef, candidate: { candidate_ref: third, run_ref: runRef, label: officialBaseline.label,
    status: 'completed', capabilities: { ...readOnly } }, reference: { ...officialBaseline }, capabilities: { ...readOnly },
    scope: { resource_view: query.resource_view || 'selected_batches' }, tasks: [], task_count: 0, candidate_task_count: 0, unplanned_operations: [], unplanned_operation_count: 0,
    gantt_graph: { state: 'unavailable', reason: 'No captured process order', scope: 'full_candidate', nodes: [], critical_task_refs: [], critical_edges: [] },
    batch_ref: query.batch_ref || null, time_scope: { range_start: query.range_start || null, range_end: query.range_end || null,
      interval: 'half_open_overlap', time_basis: 'factory_local', unplanned_policy: 'included_without_time_interval' }, blocked_reasons: [] } };
}
function rejected(value, change, read, message) {
  const wrong = clone(value); change(wrong); assert.throws(() => read(wrong), /.+/, message);
}
function detailContracts() {
  const batchQuery = { ...query, batch_ref: batchRef, change_kind: 'later', sort: 'delay_delta_hours', order: 'asc', page: 2, size: 50, snapshot_ref: snapshot };
  const batchPayload = detailsFixture('batches', batchQuery), readBatch = value => API.details(value, runRef, batchQuery, 'batches');
  assert.strictEqual(readBatch(batchPayload), batchPayload.data);
  for (const key of ['batch_ref', 'change_kind', 'sort', 'order'])
    rejected(batchPayload, value => { value.data.filters[key] = key === 'batch_ref' ? recommended : 'changed'; }, readBatch, '批次筛选和排序必须按请求回显：' + key);
  rejected(batchPayload, value => { value.data.page.number = 1; }, readBatch, '第 2 页不能接受第 1 页响应');
  rejected(batchPayload, value => { value.data.scope.reference.candidate_ref = recommended; }, readBatch, '明细保留独立候选基准');
  rejected(batchPayload, value => { value.data.scope.range_end = '2026-10-06T00:00:00'; }, readBatch, '返回时间窗须与当前比较一致');
  rejected(batchPayload, value => { value.meta.snapshot_ref = 't'.repeat(32); }, readBatch, '翻页须继续读取同一份明细快照');
  rejected(batchPayload, value => { delete value.data.summary.operation_changes; }, readBatch, '批次安排提示要求全范围共同工序变化');
  rejected(batchPayload, value => { value.data.summary.operation_changes.changed_operation_count.value = undefined; }, readBatch, '变化未到达不当作零');
  rejected(batchPayload, value => { value.data.summary.operation_changes.machine_change_count.scope = 'page'; }, readBatch, '安排变化不能从当前筛选页推全范围');
  assert.throws(() => API.detailScope(runRef, {}, 'batches'), /候选|方案/, '明细必须显式选择候选');
  for (const paging of [{ page: 0 }, { size: 10 }]) assert.throws(() => API.detailScope(runRef, { ...query, ...paging }, 'operations'), /20|页码/);
  const operationQuery = { ...query, resource_ref: resourceRef, change_kind: 'machine_changed', sort: 'end_delta_hours', order: 'desc' };
  const operations = detailsFixture('operations', operationQuery);
  assert.strictEqual(API.details(operations, runRef, operationQuery, 'operations'), operations.data);
  rejected(operations, value => { value.data.filters.resource_ref = recommended; }, value => API.details(value, runRef, operationQuery, 'operations'), '设备/人员筛选须按当前资源回显');
  const formalQuery = { comparison_mode: 'admission_official', selected_candidate_ref: third, range_start, range_end };
  const formal = detailsFixture('operations', formalQuery), readFormal = value => API.details(value, runRef, formalQuery, 'operations');
  assert.strictEqual(readFormal(formal), formal.data);
  rejected(formal, value => { value.data.scope.reference.kind = 'candidate'; }, readFormal, '正式比较不能接受候选基准身份');
  rejected(formal, value => { value.data.baseline.baseline_ref = first; }, readFormal, '正式归档编号须与 scope 一致');
  rejected(formal, value => { value.data.baseline.state = 'absent'; }, readFormal, '正式归档存在性须与 scope 一致');
  assert.throws(() => API.scope(runRef, { ...formalQuery, reference_candidate_ref: first }), /正式|基准/);
  const absent = clone(formal); absent.data.scope.reference = { kind: 'admission_official', baseline_ref: null }; absent.data.scope.reference_state = 'absent';
  absent.data.baseline = { ...officialBaseline, baseline_ref: null, plan_ref: null, version: null, state: 'absent', source_candidate_ref: null, source_run_ref: null };
  absent.data.items[0].before = null; absent.data.items[0].start_delta_hours = null; absent.data.items[0].end_delta_hours = null; absent.data.items[0].drill.reference = null;
  assert.equal(readFormal(absent).items[0].after.row_ref, rowRef, '无正式归档仍查看所选方案保存的安排');
  const overview = { ...clone(payload), data: { ...clone(data), scope: comparisonScope(formalQuery), baseline: clone(officialBaseline) } };
  bindRecommendationScope(overview);
  assert.equal(API.validateDecision(overview, runRef, formalQuery).scope.reference.kind, 'admission_official');
  rejected(overview, value => { value.data.scope.range_start = '2026-10-02T00:00:00'; }, value => API.validateDecision(value, runRef, formalQuery), '概览回显当前甘特时间窗');
}
function referenceContracts() {
  const q = { comparison_mode: 'admission_official', selected_candidate_ref: third, plan_ref: planRef, batch_ref: batchRef, range_start, range_end, snapshot_ref: snapshot };
  const value = referenceFixture(q), read = result => API.validateReferenceWorkspace(result, runRef, q);
  assert.strictEqual(read(value), value.data);
  assert.equal(value.data.candidate.candidate_ref, third); assert.equal(value.data.reference.source_candidate_ref, recommended, '导航候选身份和正式归档来源分别保存');
  rejected(value, result => { result.data.candidate.candidate_ref = recommended; }, read, '正式归档保留当前比较的所选候选身份');
  rejected(value, result => { result.data.reference.plan_ref = first; }, read, '正式归档的 plan_ref 与 baseline_ref 一致');
  rejected(value, result => { result.data.plan_ref = first; }, read, '正式甘特必须使用 drill 指定的保存归档');
  rejected(value, result => { result.data.plan_ref = result.data.reference.plan_ref = result.data.reference.baseline_ref = first; }, read, '返回的完整正式身份仍须与 drill 指定归档一致');
  rejected(value, result => { result.meta.snapshot_ref = 't'.repeat(32); }, read, '正式甘特刷新快照身份不得串范围');
  rejected(value, result => { result.data.batch_ref = null; }, read, '正式甘特保持当前批次筛选');
  rejected(value, result => { result.data.time_scope.range_end = '2026-10-06T00:00:00'; }, read, '正式甘特保持当前查看时间窗');
  for (const level of ['capabilities', 'candidate']) for (const key of ['edit_draft', 'adopt', 'report_actual'])
    rejected(value, result => { (level === 'candidate' ? result.data.candidate.capabilities : result.data.capabilities)[key] = true; }, read, '正式归档写能力须关闭：' + level + '.' + key);
  {
    const fixture = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures/decision_candidate_baseline.json'), 'utf8')), { baseline, workspace } = fixture;
    const saved = clone(baseline), readBaseline = result => window.RunBaselineAPI.validate(result, workspace);
    assert.strictEqual(readBaseline(baseline), baseline.data, '真实HTTP200原安排对照接受保存工种字段');
    assert(baseline.data.comparisons.some(row => row.process_type_ref && row.process_type_label), '实际响应包含保存工种身份与名称');
    rejected(baseline, result => { result.data.comparisons[0].process_type_ref = 'current-live-id'; }, readBaseline, '新增工种身份字段存在时保持合法保存引用');
    rejected(baseline, result => { result.data.comparisons[0].process_type_label = {}; }, readBaseline, '新增工种名称字段存在时保持字符串或缺项');
    rejected(baseline, result => { delete result.data.comparisons[0].process_type_ref; }, readBaseline, '原安排对照必须包含工种身份字段');
    rejected(baseline, result => { delete result.data.comparisons[0].process_type_label; }, readBaseline, '原安排对照必须包含工种名称字段');
    const unknown = clone(baseline); unknown.data.comparisons.forEach(row => { row.process_type_ref = null; row.process_type_label = null; });
    assert.strictEqual(readBaseline(unknown), unknown.data, '历史工种缺项保持null可读');
    assert.deepEqual(clone(baseline), saved, '原安排校验保持真实DTO原值');
    console.log('actual saved candidate baseline: typed and unknown process-type fields passed');
  }
}
function recommendationContracts() {
  const read = value => API.validateDecision(value, runRef, query);
  const readSummary = value => API.validateDecisionSummary(value, runRef, query), savedSummary = clone(summaryPayload);
  assert.strictEqual(readSummary(summaryPayload), summaryPayload.data, '首屏使用独立core合同，推荐真实重指标由共同目录验证');
  assert.deepEqual(clone(summaryPayload), savedSummary, '摘要校验保留候选原数、范围、推荐和导出快照');
  rejected(summaryPayload, value => { delete value.data.candidates[0].metrics.overdue_count; }, readSummary, '首屏缺交期核心值须报告真实资料错误');
  rejected(summaryPayload, value => { value.data.candidates[0].metrics.changed_operation_count = clone(metric); }, readSummary, '未计算的矩阵字段不伪装为首屏指标');
  rejected(summaryPayload, value => { value.data.recommendation.current_comparison.all_differences.find(row => row.metric_key === 'type_changeover_count').metric_version = 'old'; }, readSummary, '推荐重指标版本由同份目录核对');
  rejected(summaryPayload, value => { value.data.scope.selected_candidate_ref = first; }, readSummary, '首屏拒绝其他当前候选的响应');
  assert.throws(() => read(summaryPayload), /指标|分类/, '摘要不进入完整矩阵validator');
  rejected(payload, value => { delete value.data.completion_groups; }, read, '完整概览仍要求全部完成组');
  rejected(payload, value => { delete value.data.candidates[0].metrics.type_changeover_count; }, read, '完整概览仍要求每个候选的重指标');
  const unselectedSummary = clone(summaryPayload);
  unselectedSummary.data.candidates = [];
  unselectedSummary.data.scope.selected_candidate_ref = null;
  unselectedSummary.data.scope.reference_state = 'selection_required';
  unselectedSummary.data.scope.reference = { kind: 'candidate', candidate_ref: null };
  unselectedSummary.data.baseline = { kind: 'candidate', candidate_ref: null, label: null, state: 'selection_required', metrics: {}, coverage: { schedulable: { state: 'unavailable' } } };
  unselectedSummary.data.selection_basis = { generation_policy_version: null, selection_policy_version: null, primary_objective: null, target_objectives: [],
    selected_candidate_ref: null, objective_winners: {}, objective_winner_reasons: {}, objective_field_order: {}, selected_score: [], reason_code: null,
    scoring_scope: null, evidence_state: 'unavailable', explanation: { headline: '本次排产尚未保存推荐方案。', entries: [], issues: [] } };
  unselectedSummary.data.recommendation = { ...unselectedSummary.data.recommendation, state: 'unavailable', candidate_ref: null, viewed_candidate_ref: null,
    recommendation_type: null, completion_scope: null, axes: { ...unselectedSummary.data.recommendation.axes, algorithm: { state: 'unavailable', reason_code: null, evidence_state: 'unavailable' } },
    current_comparison: { state: 'selection_required', candidate_ref: null, viewed_candidate_ref: null, reference: { kind: 'candidate', candidate_ref: null }, benefits: [], costs: [], all_differences: [], common_completed_delivery: null } };
  assert.strictEqual(API.validateDecisionSummary(unselectedSummary, runRef, { range_start, range_end }), unselectedSummary.data, '未产出候选的运行摘要通过空selection_basis校验');
  rejected(unselectedSummary, value => { value.data.selection_basis.primary_objective = 'min_overdue'; }, value => API.validateDecisionSummary(value, runRef, { range_start, range_end }), '无候选时拒绝非空选择目标');
  const statusWindow = { ...window }, partialCandidate = { ...data.candidates[0], status: 'partial', persisted_status: 'completed', completeness: 'partial' };
  for (const output of compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources: ['RunCandidateControls.jsx', 'RunDecisionRecommendation.jsx'].map(name => ({ path: name, code: fs.readFileSync(path.join(app, name), 'utf8') })) }).outputs)
    vm.runInNewContext(output.code, { React, window: statusWindow });
  const unselectedPanel = expand(h(statusWindow.RunDecisionRecommendation.Panel, { data: unselectedSummary.data, onSelect: () => {}, onSupport: () => {} }));
  assert(visibleText(unselectedPanel).includes('本次排产暂无推荐方案') && text(unselectedPanel).includes('共同优化的推荐规则与数值') && !text(unselectedPanel).includes('推荐评分范围'), '未产出候选时推荐面板与依据渲染不读取空scoring_scope');
  const status = expand(h(statusWindow.RunCandidateControls.Status, { candidate: partialCandidate }));
  assert.equal(window.WorkbenchTerms.candidate_statuses.partial, window.WorkbenchTerms.delivery_completion_states.incomplete, 'partial候选沿共同工序安排状态表达');
  assert(nodes(status).some(node => node.props['data-candidate-status'] === partialCandidate.status) && nodes(status).some(node => node.props['data-candidate-persisted-status'] === partialCandidate.persisted_status), '计算完成与工序未排齐分别绑定原始状态');
  assert(text(status).includes(window.WorkbenchTerms.candidate_statuses.partial) && text(status).includes(window.WorkbenchTerms.candidate_statuses.completed));
  for (const kind of ['complete', 'schedulable_scope', 'partial']) {
    const value = clone(data); value.recommendation.recommendation_type = kind;
    const tree = expand(h(Recommendation, { data: value, onSelect: () => {}, onSupport: () => {} }));
    assert.equal(tree.props['data-recommendation-type'], kind); assert(visibleText(tree).includes(value.candidates.find(candidate => candidate.candidate_ref === value.recommendation.candidate_ref).label), '推荐类别和候选身份沿用后端保存结果');
    assert(!visibleText(tree).includes('建议采用'), '算法推荐标题与当前采用预检分别表达');
  }
  // The comparison page mounts only the compact panel: one summary line, with tradeoffs and evidence inside 推荐详情.
  const tree = expand(h(Recommendation, { data, onSelect: () => {}, onSupport: () => {} })), full = text(tree), shown = visibleText(tree), compact = tree, compactShown = shown;
  assert(compactShown.includes('本次建议') && compactShown.includes(data.baseline.label) && compactShown.includes(data.recommendation.current_comparison.benefits[0].label) && compactShown.includes(data.recommendation.current_comparison.costs[0].label), '顶区固定推荐与当前真实收益、代价分别显示');
  assert(compactShown.includes(basis.explanation.headline), '推荐主文使用保存的推荐主因，完整目标、容差和原数继续保留');
  assert(!compactShown.includes('主要收益') && text(compact).includes('主要收益') && text(compact).includes('主要代价'), '紧凑入口仍在原生详情内保留全部当前取舍');
  const summaryData = clone(data);
  summaryData.difference_summary = { scope: 'full_admission', items: ['overdue_count', 'total_tardiness_hours', 'makespan_hours'].map((key, index) => ({ ...definitions.find(row => row.key === key), value: [0, null, 0.00009][index], state: index === 1 ? 'unavailable' : 'comparable', direction: ['equal', 'neutral', 'worse'][index], reference_value: [2, null, 12][index], selected_value: [2, null, 12.00009][index], reference_coverage: clone(metric), selected_coverage: clone(metric) })) };
  const summarySaved = clone(summaryData), summary = expand(h(D.DifferenceSummary, { data: summaryData }));
  const zero = nodes(summary).find(row => row.props['data-summary-metric'] === 'overdue_count'), unknown = nodes(summary).find(row => row.props['data-summary-metric'] === 'total_tardiness_hours'), tiny = nodes(summary).find(row => row.props['data-summary-metric'] === 'makespan_hours');
  assert(zero.props.className.endsWith('rd-equal') && visibleText(zero).includes('持平'), '真实零差值保持中性');
  assert(visibleText(unknown).includes('待确认') && !visibleText(unknown).includes('0 小时'), '完整未知值不补零');
  assert(visibleText(tiny).replace(/\s+/g, '').includes('+<0.001小时') && nodes(tiny).some(row => row.props.title === '0.00009'), '微小真实差值保留方向、量级与完整原值');
  assert.deepEqual(clone(summaryData), summarySaved, '三项摘要直接消费DTO，不重算指标');
  for (const tab of ['delivery', 'differences']) {
    const page = expand(h(comparisonWorkspace({ decisionSummary: () => ({ ...payload, data: summaryData }) }), { ...workspaceDefaults, initialContext: { run_ref: runRef, candidate_ref: third, reference_candidate_ref: first, range_start, range_end, comparison_tab: tab } }));
    assert.equal(nodes(page).filter(node => node.props.className === 'rd-difference-summary').length, tab === 'differences' ? 1 : 0, '三项差异只在差异页出现：' + tab);
  }
  assert.equal(nodes(tree).filter(row => row.props['data-recommendation-metric']).length, 6, '首屏采用后端最多3+3主要条目');
  assert.equal(nodes(tree).filter(row => row.props['data-recommendation-difference']).length, definitions.length, '原生展开保留全部差值');
  assert(full.includes('共同优化') && full.includes('未安排工序') && full.includes('所选范围缺少完整评分分量。'), '推荐详情保留保存的选择依据与缺项说明');
  const floatingBasis = clone(basis), floatingEntry = floatingBasis.explanation.entries.find(row => row.key === 'score_total_tardiness_hours');
  floatingEntry.selected_value = 17.24000000000001;
  const floatingSaved = clone(floatingBasis), floatingTree = expand(h(window.RunDecisionRecommendation.SelectionEvidence, { basis: floatingBasis, data }));
  const floatingField = nodes(floatingTree).find(row => row.props['data-selection-evidence'] === 'score_total_tardiness_hours');
  assert(text(floatingField).replace(/\s+/g, ' ').includes('本项值 17.24 小时') && !text(floatingField).includes('17.24000000000001'), '真实浮点尾差按共同格式显示');
  assert(nodes(floatingField).some(row => row.props.title === '17.24000000000001'), '原保存数值仍可悬停核对');
  assert.deepEqual(clone(floatingBasis), floatingSaved, '显示格式保留DTO原值');
  assert(!shown.includes('所选范围缺少完整评分分量。'), '长选择缺项位于原生展开中');
  assert(shown.includes(basis.explanation.headline) && full.includes(basis.explanation.headline), '默认推荐区保留唯一真实选择主因，展开继续完整保存依据');
  const recommendationCause = tree.children.find(row => row && row.props && row.props.className === 'rd-recommend-cause');
  assert.equal(text(recommendationCause), basis.explanation.headline, '原推荐主因逐字保留在全宽独立正文，未截断或页面重算');
  const comparisonTitles = nodes(tree).filter(row => row.props.className === 'rd-tradeoffs-title');
  assert.equal(comparisonTitles.length, 1); assert.equal(text(comparisonTitles[0]).replace(/\s+/g, ''), '当前比较：推荐方案相对' + data.baseline.label, '收益与代价共用一个真实当前基准标题');
  assert(!nodes(tree).some(row => row.props.className === 'rd-tradeoff-reference'), '两个取舍栏保留各自标题，比较对象不逐栏重复');
  assert(full.includes('少安排的准备需求') && !nodes(tree).filter(row => row.props['data-recommendation-metric']).some(row => row.props['data-recommendation-metric'] === 'scheduled_setup_hours'), '漏排造成的少安排准备保留在中性完整差值中');
  const partial = clone(data); partial.recommendation.recommendation_type = 'partial'; partial.recommendation.completion_scope.unplanned_operation_count = 2; partial.recommendation.completion_scope.unknown_batch_count = 1;
  const partialShown = text(expand(h(Recommendation, { data: partial, onSelect: () => {}, onSupport: () => {} }))).replace(/\s+/g, ' ');
  assert(partialShown.includes(window.WorkbenchTerms.completion_summary(partial.recommendation.completion_scope)), '部分结果推荐详情沿共同摘要明确未安排与待确认批次');
  rejected(payload, value => { value.data.recommendation.candidate_ref = third; }, read, '推荐身份不能随当前查看改写');
  rejected(payload, value => { value.data.recommendation.current_comparison.reference.candidate_ref = third; }, read, '推荐取舍必须消费实际查看基准');
  rejected(payload, value => { value.data.recommendation.current_comparison.viewed_candidate_ref = recommended; }, read, '当前查看身份完整回显');
  rejected(payload, value => { delete value.data.recommendation.current_comparison.all_differences[0].value; }, read, '未知差值须明确null和state');
  rejected(payload, value => { value.data.recommendation.current_comparison.benefits.push(value.data.recommendation.current_comparison.all_differences[3]); }, read, '主要收益最多三项');
  rejected(payload, value => { value.data.recommendation.current_comparison.benefits[0].value = -999; }, read, '主要条目必须与全部同源差值一致');
  rejected(payload, value => { value.data.recommendation.current_comparison.all_differences[0].supporting_refs[0].drill.candidate_ref = third; }, read, '支撑必须指向保存推荐候选');
  rejected(payload, value => { value.data.completion_groups[0].candidate_refs.pop(); }, read, '完成集合分组不得丢候选');
  const noDue = clone(payload), currentNoDue = noDue.data.recommendation.current_comparison;
  for (const entry of currentNoDue.all_differences.filter(row => row.scope === 'common_completed_batches')) Object.assign(entry, { value: null, reference_value: null, selected_value: null, state: 'not_applicable', direction: 'neutral', text: '共同完成批次未指定交期。', reason: { code: 'due_unspecified', message: '共同完成批次未指定交期。' } });
  currentNoDue.benefits = currentNoDue.all_differences.filter(row => row.direction === 'better').slice(0, 3); currentNoDue.costs = currentNoDue.all_differences.filter(row => row.direction === 'worse').slice(0, 3);
  Object.assign(currentNoDue.common_completed_delivery, { state: 'not_applicable', delay_delta_hours: null, overdue_delta_count: null });
  assert.strictEqual(read(noDue), noDue.data);
  const noDueTree = expand(h(window.RunDecisionRecommendation.Differences, { items: currentNoDue.all_differences }));
  assert(text(nodes(noDueTree).find(row => row.props['data-recommendation-difference'] === 'overdue_count')).includes('本范围不适用'), '未指定交期独立表达不适用，不转成零或未知');
  assert.equal(nodes(noDueTree).filter(row => row.type === 'p' && row.props.id && row.props.id.startsWith('rd-recommend-reason-')).length, 2, '全部差值中的重复理由按实际不同原因保留一次');
  const remainingWork = clone(completionScope.remaining_work), remainingDefinitions = prepKeys.map(key => ({ key, label: key, unit: '小时', precision: 3, source: 'runtime_operation_effort', scope: 'full_admission' }));
  for (const key of prepKeys) remainingWork.metrics[key] = { ...remainingWork.metrics[key], value: null, state: 'partial', known_count: 2, unknown_count: 1, reason: { code: 'remaining_requirement_missing', message: longReason } };
  const sharedRemaining = window.RunDecisionRecommendation.RemainingMetrics({ work: remainingWork, definitions: remainingDefinitions, label: '剩余工时' }), remainingMetrics = nodes(sharedRemaining).filter(row => row.type === D.Metric);
  assert.equal(remainingMetrics.length, prepKeys.length);
  remainingMetrics.forEach((row, index) => assert.strictEqual(row.props.metric, remainingWork.metrics[prepKeys[index]], '共同剩余工时表沿用原metric'));
  assert.equal(nodes(expand(sharedRemaining)).filter(row => row.type === 'p' && text(row) === longReason).length, 1, '共同剩余工时表只显示一次完整缺项原因');
  for (const [key, unit] of [['overdue_count', '批'], ['scheduled_setup_hours', '道工序'], ['machine_high_pressure_count', '台设备'], ['operator_high_pressure_count', '人'], ['makespan_hours', '份统计记录']]) {
    const definition = definitions.find(row => row.key === key), empty = { ...metric, value: null, state: 'unavailable', known_count: 0, known_subtotal: 0, unknown_count: 1, total_count: 1 }, savedEmpty = clone(empty);
    for (const Component of [D.Metric, D.CompactValue]) {
      const shownEmpty = expand(h(Component, { metric: empty, definition })), primary = nodes(shownEmpty).find(row => row.type === 'strong');
      assert.equal(text(primary).trim(), '1 ' + unit + '待确认', '覆盖人数沿实际对象grain显示：' + key);
      assert(!visibleText(shownEmpty).includes('已知'), '没有已知对象时保存小计0只保留在资料和title中');
      assert(primary.props.title.includes('已知 0 / 1 ' + unit));
      assert(primary.props.title.includes('保存小计 0') || text(shownEmpty).replace(/\s+/g, ' ').includes('保存小计 0'), '原保存0与完整计数仍可查');
      const knownZero = expand(h(Component, { metric: { ...empty, state: 'partial', known_count: 1, total_count: 2 }, definition }));
      assert(nodes(knownZero).some(row => row.type === 'small' && text(row).startsWith('已知') && /\s0(?:\s|$)/.test(text(row))), '有已知对象的真实0小计继续显示');
    }
    assert.deepEqual(clone(empty), savedEmpty);
  }
  const original = { run_ref: runRef, candidate_ref: third, reference_candidate_ref: first, comparison_mode: 'candidates', resource_view: 'selected_batches', range_start, range_end, metric_view: 'all', comparison_tab: 'delivery',
    return_history_context: { query: '第5验收' }, detail_queries: { 'completion-batches': { completion_filter: 'ordinary', open: false, page: 2, size: 50, snapshot_ref: snapshot }, operations: { page: 2, size: 50, batch_ref: batchRef, snapshot_ref: snapshot }, resources: { page: 3, heatmap_page: 2, day_page: 4, resource_kind: 'operator', resource_ref: resourceRef, snapshot_ref: snapshot, day_snapshot_ref: 't'.repeat(32) }, preparation: { page: 2, size: 20, allocation_state: 'unplanned', snapshot_ref: snapshot }, changeovers: { event_side: 'reference', sort: 'machine_label', order: 'desc', snapshot_ref: snapshot } } };
  const links = [], main = expand(h(comparisonWorkspace({ decisionSummary: () => payload }), { ...workspaceDefaults, initialContext: original, onNavigate: (page, context) => links.push({ page, context }) }));
  const originalRemembered = clone(remembered.at(-1)), differences = nodes(main).filter(row => row.props['data-recommendation-difference']);
  const seen = new Set();
  for (const row of differences) {
    const button = nodes(row).find(node => node.type === 'button'); if (!button) continue;
    button.props.onClick(); const target = links.at(-1), pane = target.context.comparison_tab; seen.add(pane);
    assert.equal(target.page, 'analysis'); assert.equal(target.context.candidate_ref, recommended); assert.equal(target.context.reference_candidate_ref, first);
    assert.equal(target.context.range_start, range_start); assert.equal(target.context.resource_view, 'selected_batches');
    assert.deepEqual(clone(target.context.return_recommendation_context), originalRemembered, '返回保留第三候选、基准、窗口、指标、页签、所有筛选/页码/快照');
    assert.equal(target.context.detail_queries[pane].page, 1);
    for (const query of Object.values(target.context.detail_queries)) { assert.equal(query.snapshot_ref, undefined); assert.equal(query.day_snapshot_ref, undefined, '新推荐支撑范围清除原候选各页签快照'); }
  }
  assert.deepEqual([...seen].sort(), ['changeovers', 'delivery', 'differences', 'preparation', 'resources'], '五类聚合支撑进入实际独立页签');
  const direct = clone(payload), directEntry = direct.data.recommendation.current_comparison.all_differences.find(row => row.metric_key === 'changed_operation_count');
  Object.assign(directEntry.supporting_refs[0].drill, { operation_ref: operationRef, selected_row_ref: rowRef, selected_candidate_ref: recommended, range_start: '2026-09-30T00:00:00', range_end: '2026-10-06T00:00:00', drill_range_adjusted: true });
  delete directEntry.supporting_refs[0].drill.comparison_tab; delete directEntry.supporting_refs[0].drill.detail_query;
  assert.strictEqual(read(direct), direct.data, '真实工序支撑复用既有准确定位与合法扩窗');
  rejected(direct, value => { value.data.recommendation.current_comparison.all_differences.find(row => row.metric_key === 'changed_operation_count').supporting_refs[0].drill.range_start = '2026-10-02T00:00:00'; }, read, '工序定位扩窗必须保留原共同窗口');
  const directPage = expand(h(comparisonWorkspace({ decisionSummary: () => direct }), { ...workspaceDefaults, initialContext: original, onNavigate: (page, context) => links.push({ page, context }) }));
  nodes(nodes(directPage).find(row => row.props['data-recommendation-difference'] === 'changed_operation_count')).find(node => node.type === 'button').props.onClick();
  assert.equal(links.at(-1).page, 'gantt'); assert.equal(links.at(-1).context.candidate_ref, recommended); assert.equal(links.at(-1).context.operation_ref, operationRef); assert.equal(links.at(-1).context.selected_row_ref, rowRef);
  assert.deepEqual(clone(links.at(-1).context.return_decision_context), originalRemembered, '真实工序甘特返回原第三候选比较，保留原窗口');
  const referenceSupport = clone(direct), beforeTarget = referenceSupport.data.recommendation.current_comparison.all_differences.find(row => row.metric_key === 'changed_operation_count').supporting_refs[0];
  beforeTarget.side = 'reference'; beforeTarget.drill.candidate_ref = first;
  assert.strictEqual(read(referenceSupport), referenceSupport.data, '已移除工序支撑使用实际候选基准侧，推荐锚点仍固定');
  rejected(referenceSupport, value => { delete value.data.recommendation.current_comparison.all_differences.find(row => row.metric_key === 'changed_operation_count').supporting_refs[0].side; }, read, '基准侧必须明确声明，不能冒充推荐侧');
  const referencePage = expand(h(comparisonWorkspace({ decisionSummary: () => referenceSupport }), { ...workspaceDefaults, initialContext: original, onNavigate: (page, context) => links.push({ page, context }) }));
  const beforeButton = nodes(nodes(referencePage).find(row => row.props['data-recommendation-difference'] === 'changed_operation_count')).find(node => node.type === 'button');
  assert(text(beforeButton).includes('基准')); beforeButton.props.onClick();
  assert.equal(links.at(-1).page, 'gantt'); assert.equal(links.at(-1).context.candidate_ref, first); assert.equal(links.at(-1).context.selected_candidate_ref, recommended); assert.equal(links.at(-1).context.selected_row_ref, rowRef);
  assert.deepEqual(clone(links.at(-1).context.return_decision_context), originalRemembered, '基准侧定位返回原第三查看与比较范围');
  const formalSupport = bindRecommendationScope({ ...clone(referenceSupport), data: { ...clone(referenceSupport.data), scope: comparisonScope({ comparison_mode: 'admission_official' }), baseline: clone(officialBaseline) } });
  const formalBefore = formalSupport.data.recommendation.current_comparison.all_differences.find(row => row.metric_key === 'changed_operation_count').supporting_refs[0];
  Object.assign(formalBefore.drill, { candidate_ref: recommended, reference_view: true, plan_ref: planRef });
  assert.strictEqual(API.validateDecision(formalSupport, runRef, { comparison_mode: 'admission_official', selected_candidate_ref: third }), formalSupport.data, '正式基准保留推荐锚点与真实只读计划身份');
  rejected(formalSupport, value => { value.data.recommendation.current_comparison.all_differences.find(row => row.metric_key === 'changed_operation_count').supporting_refs[0].drill.plan_ref = first; }, value => API.validateDecision(value, runRef, { comparison_mode: 'admission_official', selected_candidate_ref: third }), '正式基准支撑不能串其他计划');
  window.RunDecisionDetails = { Pane: 'detail-pane' };
  const supportContext = links.find(row => row.context.comparison_tab === 'differences').context;
  const supportData = bindRecommendationScope({ ...clone(payload), data: { ...clone(data), scope: { ...clone(data.scope), selected_candidate_ref: recommended } } });
  const supportPage = expand(h(comparisonWorkspace({ decisionSummary: () => supportData }), { ...workspaceDefaults, initialContext: supportContext, onNavigate: (page, context) => links.push({ page, context }) }));
  nodes(supportPage).find(node => node.type === 'detail-pane').props.onDrill({ run_ref: runRef, candidate_ref: recommended, reference_candidate_ref: first, comparison_mode: 'candidates', batch_ref: batchRef, operation_ref: operationRef, range_start, range_end });
  assert.equal(links.at(-1).page, 'gantt'); assert.deepEqual(clone(links.at(-1).context.return_decision_context.return_recommendation_context), originalRemembered, '第二层甘特完整携带返回原比较链');
  nodes(supportPage).find(node => node.type === 'button' && text(node) === '返回原比较').props.onClick();
  assert.deepEqual(clone(links.at(-1).context), originalRemembered);
}
function hooks() {
  let cursor = 0; const slots = [], effects = [];
  const same = (a, b) => a && b && a.length === b.length && a.every((value, index) => value === b[index]);
  const useMemo = (make, deps) => { const index = cursor++; if (!slots[index] || !same(slots[index].deps, deps)) slots[index] = { deps, value: make() }; return slots[index].value; };
  const useEffect = (effect, deps) => { const index = cursor++, old = slots[index]; if (!old || !same(old.deps, deps)) { slots[index] = { deps, cleanup: old && old.cleanup }; effects.push(() => { if (slots[index].cleanup) slots[index].cleanup(); slots[index].cleanup = effect(); }); } };
  return { React: { createElement: h, Fragment: 'fragment', useId: () => 'process-chart', useMemo, useEffect,
    useRef(initial) { const index = cursor++; if (!slots[index]) slots[index] = { current: initial }; return slots[index]; },
    useState(initial) { const index = cursor++; if (!slots[index]) slots[index] = { value: typeof initial === 'function' ? initial() : initial }; return [slots[index].value, update => { slots[index].value = typeof update === 'function' ? update(slots[index].value) : update; }]; },
    useReducer(reducer, initial) { const [value, set] = this.useState(initial); return [value, action => set(old => reducer(old, action))]; } },
    render(fn) { cursor = 0; return fn(); }, flush() { while (effects.length) effects.shift()(); },
    unmount() { effects.length = 0; slots.forEach(slot => { if (slot.cleanup) { slot.cleanup(); slot.cleanup = null; } }); } };
}
function schedulingNavigationContracts() {
  const localReact = { ...React, useMemo: make => make() }, links = [], historyQuery = { state: 'complete', sort: 'accepted_at', order: 'desc', page: 2, size: 20 };
  const local = { ...window, ResourceControls: { ...window.ResourceControls, Icon: 'icon' }, WorkbenchTerms: { ...window.WorkbenchTerms, candidate: '候选方案' }, RunJobAPI: {}, RunJobControls: { Button: 'button' },
    RunCandidateWorkspace: 'candidate-workspace', RunHistoryWorkspace: 'history-workspace', PlanWorkspace: 'formal-workspace',
    RunDecisionComparison: { Workspace: 'comparison-workspace' } };
  const load = name => {
    for (const output of compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources: [{ path: name, code: fs.readFileSync(path.join(app, name), 'utf8') }] }).outputs)
      vm.runInNewContext(output.code, { React: localReact, window: local });
  };
  load('RunHistoryAPI.js'); load('SchedulingWorkspace.jsx');
  const onNavigate = (page, context) => links.push({ page, context }), context = { ...original, return_history_context: historyQuery };
  const analysis = local.PlanCenterWorkspace({ view: 'analysis', initialContext: context, onNavigate });
  const candidate = nodes(analysis).find(node => node.type === 'candidate-workspace'), navigation = candidate.props.navigation;
  assert(navigation, '候选分析页将唯一计划中心导航交给比较工作区');
  assert.strictEqual(candidate.props.initialContext, context); assert.strictEqual(candidate.props.onNavigate, onNavigate);
  assert.deepEqual(clone(candidate.props.runHistoryReturn), { view: 'analysis', context: { source: 'run_history', history_topic: 'run_catalog', history_query: historyQuery } }, '共同列表上下文由Scheduling生成并去掉run/candidate选择');
  assert.equal(nodes(expand(analysis)).filter(node => node.props.className === 'scheduling-navigation').length, 0, '比较页外层保留内容入口，不再创建第二个导航条');
  const navigationTree = expand(navigation), buttons = nodes(navigationTree).filter(node => node.type === 'button');
  assert.equal(nodes(navigationTree).filter(node => node.props.className === 'scheduling-navigation').length, 1);
  buttons.find(node => node.props.icon === 'files').props.onClick(); assert.deepEqual(clone(links.at(-1)), { page: 'analysis', context: {} });
  assert(!buttons.some(node => node.props.icon === 'history'), '候选外层导航的记录入口由工作区唯一返回列表承接');
  for (const view of ['gantt', 'delay']) {
    const tree = expand(local.PlanCenterWorkspace({ view, initialContext: context, onNavigate })), work = nodes(tree).find(node => node.type === 'candidate-workspace');
    assert.equal(nodes(tree).filter(node => node.props.className === 'scheduling-navigation').length, 0, '候选甘特/交付页外层由工作区页头承接导航：' + view);
    assert(work.props.navigation); assert.equal(nodes(expand(work.props.navigation)).filter(node => node.props.className === 'scheduling-navigation').length, 1); assert.equal(work.props.view, view); assert.strictEqual(work.props.initialContext, context);
  }
  for (const view of ['analysis', 'gantt', 'delay']) {
    const tree = expand(local.PlanCenterWorkspace({ view, initialContext: { plan_ref: planRef }, onNavigate })), work = nodes(tree).find(node => node.type === 'formal-workspace');
    assert(work && work.props.navigation); assert.equal(nodes(tree).filter(node => node.props.className === 'scheduling-navigation').length, 0);
    assert.equal(nodes(expand(work.props.navigation)).filter(node => node.props.className === 'scheduling-navigation').length, 1, '正式计划工作区继续拥有原导航：' + view);
  }
  const history = expand(local.PlanCenterWorkspace({ view: 'analysis', initialContext: { source: 'run_history', history_query: historyQuery }, onNavigate }));
  const historyWork = nodes(history).find(node => node.type === 'history-workspace'); assert.equal(nodes(history).filter(node => node.props.className === 'scheduling-navigation').length, 0); assert(historyWork.props.navigation); assert.equal(nodes(expand(historyWork.props.navigation)).filter(node => node.props.className === 'scheduling-navigation').length, 1); assert.deepEqual(clone(historyWork.props.initialContext), historyQuery);
  load('RunCandidateWorkspace.jsx');
  const comparison = local.RunCandidateWorkspace(candidate.props);
  assert.equal(comparison.type, 'comparison-workspace'); assert.strictEqual(comparison.props.navigation, navigation, '实际候选分发器继续透传导航到比较组件');
  return { navigation, runHistoryReturn: candidate.props.runHistoryReturn };
}
function comparisonHeaderContracts({ navigation, runHistoryReturn }) {
  for (const times of [[range_start, range_end], ['2026-10-01T08:30:12.250', '2026-10-05T18:45:00'], ['2026-12-31T23:59:45.250', '2027-01-01T08:00:05']]) {
    const state = hooks(), queries = [], snapshots = [], links = [], value = bindRecommendationScope(clone(payload));
    value.data.scope.range_start = times[0]; value.data.scope.range_end = times[1]; bindRecommendationScope(value);
    const local = { ...window, WorkbenchPageContext: { useSnapshot: current => snapshots.push(clone(current)) },
      APSResourceSession: { useQuery: (load, deps, enabled = true) => ({ result: enabled ? load() : null, loading: false, error: null }) },
      RunDecisionAPI: { ...API, decisionSummary: (run, current) => { queries.push(clone(current)); return value; } } };
    for (const output of compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources: [{ path: 'RunDecisionComparison.jsx', code: fs.readFileSync(path.join(app, 'RunDecisionComparison.jsx'), 'utf8') }] }).outputs)
      vm.runInNewContext(output.code, { React: state.React, window: local, AbortController });
    const returnRun = { run_ref: first, range_start: '2026-09-30T00:00:00', range_end }, props = { navigation, runHistoryReturn, initialContext: { ...original, range_start: times[0], range_end: times[1], return_run_context: returnRun },
      onNavigate: (page, context) => links.push({ page, context }), renderAdoption: () => null, renderTrial: () => null };
    let tree;
    const render = () => { tree = state.render(() => expand(local.RunDecisionComparison.Workspace(props))); state.flush(); };
    render(); const untouched = clone(value), originalSnapshot = clone(snapshots.at(-1));
    const header = nodes(tree).find(node => node.props.className === 'rc-heading rd-heading scheduling-page-tools');
    assert(header); assert.equal(nodes(header).filter(node => node.props.className === 'scheduling-navigation').length, 1);
    assert(!header.children.some(node => node && typeof node === 'object' && node.children.length === 0), '工具区只承载导航和操作组，空标题容器退出布局');
    assert(nodes(tree).some(node => node.type === 'h2' && node.props.className === 'rd-page-title'), '结果页主标题保留可见的语义入口');
    const headerTools = nodes(header).find(node => node.props.className === 'rc-tools rd-header-tools'), scopeTools = nodes(headerTools).find(node => node.props.className === 'rc-tools rd-scope-tools');
    assert(headerTools && scopeTools);
    const back = nodes(headerTools).find(node => node.type === 'button' && node.props.icon === 'chevron-left'), rangeButton = nodes(tree).find(node => node.type === 'button' && node.props.icon === 'calendar-days');
    assert(back && rangeButton); assert(nodes(scopeTools).some(node => node.type === 'button' && node.props.icon === 'download')); assert(nodes(scopeTools).some(node => node.type === 'button' && node.props.icon === 'refresh-cw'));
    back.props.onClick(); assert.deepEqual(clone(links.at(-1)), clone({ page: runHistoryReturn.view, context: runHistoryReturn.context }), '页头直接使用共同列表目标，保留原筛选与列表页签');
    for (const time of times) {
      const completeTime = window.WorkbenchFormat.dateTime(time, { seconds: true, fractions: true });
      assert(rangeButton.props.title.includes(completeTime) && rangeButton.props['aria-label'].includes(completeTime), '紧凑显示保留完整起止时间的可访问说明');
    }
    assert(rangeButton.props.title.includes('包含') && rangeButton.props.title.includes('不含'), '完整说明保留左闭右开边界');
    const shownRange = text(rangeButton).replace(/\s+/g, ' ').trim();
    assert.equal(shownRange, window.WorkbenchFormat.compactRange(times[0], times[1]), '页面沿共同格式显示分钟，原秒与小数保留在完整说明');
    if (times[0].slice(0, 4) === times[1].slice(0, 4)) assert(!shownRange.includes(times[0].slice(0, 4)), '同年窗口沿共同格式简洁展示');
    else assert(shownRange.includes('2026') && shownRange.includes('2027'), '跨年窗口保留两个年份');
    rangeButton.props.onClick(); render();
    assert.equal(nodes(tree).find(node => node.props['aria-label'] === '资源比较时间窗开始').props.value, times[0]);
    assert.equal(nodes(tree).find(node => node.props['aria-label'] === '资源比较时间窗结束').props.value, times[1]);
    assert(queries.every(current => current.range_start === times[0] && current.range_end === times[1]), '打开紧凑时间窗保持原API查询值');
    assert.deepEqual(snapshots.at(-1), originalSnapshot); assert.deepEqual(clone(value), untouched, '页头布局与显示精简保持原导航快照和业务DTO');
  }
}
const turns = async () => { for (let i = 0; i < 8; i++) await Promise.resolve(); };
async function candidateWorkspace(context, value, loadWorkspace = () => value) {
  const state = hooks(), calls = [], recalled = [], links = [], captions = [], controls = { ...window.RunCandidateControls, Catalog: 'catalog', Generation: 'generation', Detail: 'candidate-detail' };
  const gantt = 'candidate-gantt', ganttComponent = props => h(gantt, props); ganttComponent.TaskList = 'candidate-task-list';
  // The candidate workspace's own reads are answered on its API module objects (component ownership); their HTTP paths belong to the API contracts.
  const record = name => async (...args) => { calls.push({ name, args }); return ['workspace', 'referenceWorkspace'].includes(name) ? loadWorkspace(...args) : null; };
  const local = { ...window, RunCandidateControls: controls, RunCandidateModel: { ...window.RunCandidateModel, matching: values => values },
    RunCandidateGantt: ganttComponent, WorkbenchControls: { usePrintLayout: () => false }, WorkbenchListControls: { EmptyState: 'empty-state' },
    RunCandidateAPI: { ...window.RunCandidateAPI, catalog: record('catalog'), workspace: record('workspace') }, RunCandidateAnalysisAPI: { analysis: record('analysis'), adoptions: record('adoptions') },
    RunDecisionAPI: { ...API, referenceWorkspace: record('referenceWorkspace') },
    WorkbenchPageContext: { useSnapshot: current => recalled.push(current) }, WorkbenchCaption: { useCaption: current => captions.push(current) }, RunCandidateAnalysis: {} };
  const sources = ['resource-session.js', 'WorkbenchFormat.js', 'WorkbenchDatePickerModel.js', 'PointContract.js', 'PointGanttModel.js', 'GanttGraph.js', 'PlanGanttModel.js', 'RunCandidateModel.js', 'RunBaselineControls.jsx', 'RunCandidateGantt.jsx', 'RunCandidateWorkspace.jsx'].map(name => ({ path: name, code: fs.readFileSync(path.join(app, name), 'utf8') }));
  for (const output of compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources }).outputs)
    vm.runInNewContext(output.code, { React: state.React, window: local, AbortController, DOMException });
  const createGraph = local.GanttGraph.create; let graphBuilds = 0;
  local.GanttGraph.create = graph => { graphBuilds++; return createGraph(graph); };
  ganttComponent.TaskList = local.RunCandidateGantt.TaskList; local.RunCandidateGantt = ganttComponent;
  const props = { view: 'gantt', initialContext: context, onNavigate: (page, current) => links.push({ page, context: current }),
    renderAdoption: () => h('adoption'), renderTrial: () => h('trial'), navigation: null, runHistoryReturn: { view: 'analysis', context: {} } };
  let tree;
  const render = async () => { for (let i = 0; i < 4; i++) { tree = state.render(() => expand(h(local.RunCandidateWorkspace, props))); state.flush(); await turns(); } return tree; };
  await render();
  return { get tree() { return tree; }, get graphBuilds() { return graphBuilds; }, render, calls, recalled, links, captions, baselineSource: local.RunBaselineControls.Source, chosen: nodes(tree).find(node => node.type === gantt)?.props.selected };
}
async function workspaceContracts() {
  {
    // The Workspace's own reads are answered on its RunDecisionAPI object; their HTTP path and validators are covered by transportContracts.
    const state = hooks(), reads = [], decisionReads = { ...API }, local = { ...window, RunDecisionAPI: decisionReads, RunDecisionResources: { Pane: 'resource-pane' }, RunDecisionDetails: { Pane: 'detail-pane' } };
    for (const name of ['resource-session.js', 'RunDecisionComparison.jsx']) for (const output of compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources: [{ path: name, code: fs.readFileSync(path.join(app, name), 'utf8') }] }).outputs)
      vm.runInNewContext(output.code, { React: state.React, window: local, AbortController, DOMException });
    const response = q => { const value = clone(summaryPayload); value.data.scope = { ...comparisonScope(q), resource_refs: { machine: [], operator: [] }, batch_refs: [batchRef], operation_refs: [operationRef] };
      value.data.baseline.candidate_ref = value.data.scope.reference.candidate_ref; return bindRecommendationScope(value); };
    const saved = { resource_kind: 'operator', pressure_threshold: 0.8, page: 2, heatmap_page: 2, snapshot_ref: 'r'.repeat(32) };
    Object.assign(decisionReads, {
      resourceWorkspace: async (run, q, leaf, signal) => { reads.push({ name: 'combined', query: clone(q), leaf: clone(leaf), signal }); return resourceWorkspaceFixture(response(q), leaf); },
      decisionSummary: async (_, q) => { reads.push({ name: 'summary', query: clone(q) }); return response(q); }
    });
    const props = { ...workspaceDefaults, initialContext: { ...original, comparison_tab: 'resources', detail_queries: { resources: saved } } };
    let tree; const render = async () => { for (let index = 0; index < 3; index++) { tree = state.render(() => expand(local.RunDecisionComparison.Workspace(props))); state.flush(); await turns(); } };
    await render(); assert.deepEqual(reads.map(row => row.name), ['combined']); assert.deepEqual(reads[0].leaf, saved);
    const pane = nodes(tree).find(row => row.type === 'resource-pane'); assert.equal(pane.props.result.data.resource_result.ok, false);
    assert.equal(nodes(tree).filter(row => row.props['data-decision-candidate']).length, 3, '资源明确失败时成功的摘要候选与推荐继续展示');
    nodes(tree).find(row => row.props.id === 'rd-tab-delivery').props.onClick(); await render();
    nodes(tree).find(row => row.props.id === 'rd-tab-resources').props.onClick(); await render(); assert.equal(reads.length, 1, '普通页签切换保留同一父读取，不为切换重读摘要');
    nodes(tree).find(row => row.type === 'resource-pane').props.onQuery({ ...saved, page: 3 }); await render(); assert.equal(reads.length, 1, '资源叶分页由自身读 owner 处理');
    nodes(tree).find(row => row.props['aria-label'] === '刷新方案对比').props.onClick(); await render();
    assert.equal(reads.length, 2); assert.equal(reads[1].name, 'combined'); assert.equal(reads[1].leaf.page, 1); assert.equal(reads[1].leaf.snapshot_ref, undefined, '上层刷新沿用既有清分页与旧令牌规则');
    nodes(nodes(tree).find(row => row.props['data-decision-candidate'] === first)).find(row => row.props.className === 'rd-candidate-choice').props.onClick(); await render();
    assert.equal(reads.length, 3); assert.equal(reads[2].name, 'combined'); assert.equal(reads[2].query.selected_candidate_ref, first); assert.equal(reads[0].signal.aborted, true);
    console.log(JSON.stringify({ u5_resource_workspace_parent_reads: { cold_resources: 1, cold_summary: 0, tab_reopen: 0, resource_leaf_page: 0, header_refresh: 1, selected_candidate_change: 1 } }));
  }
  {
    const state = hooks(), requests = [], summaries = [], decisionReads = { ...API }, local = { ...window, RunDecisionAPI: decisionReads, RunDecisionDetails: { Pane: 'detail-pane' } };
    for (const name of ['resource-session.js', 'RunDecisionComparison.jsx']) for (const output of compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources: [{ path: name, code: fs.readFileSync(path.join(app, name), 'utf8') }] }).outputs)
      vm.runInNewContext(output.code, { React: state.React, window: local, AbortController, DOMException });
    const responseFor = (q, summary = false) => {
      const next = clone(summary ? summaryPayload : payload); next.data.scope = comparisonScope(q); next.data.scope.resource_view = q.resource_view || 'selected_batches';
      next.meta.snapshot_ref = summary ? String(summaries.length).padStart(32, '0') : q.snapshot_ref;
      if (summary) next.meta.as_of = '2026-10-05T00:00:' + String(summaries.length).padStart(2, '0');
      next.data.baseline.candidate_ref = next.data.scope.reference.candidate_ref; return bindRecommendationScope(next);
    };
    Object.assign(decisionReads, {
      decisionSummary: async (run, q) => { summaries.push(clone(q)); return responseFor(q, true); },
      decision: (run, q, signal) => new Promise((resolve, reject) => requests.push({ q: clone(q), signal, resolve, reject }))
    });
    const props = { ...workspaceDefaults, initialContext: original };
    let tree;
    const render = async () => { for (let i = 0; i < 3; i++) { tree = state.render(() => expand(local.RunDecisionComparison.Workspace(props))); state.flush(); await turns(); } };
    await render();
    assert.equal(summaries.length, 1); assert.equal(requests.length, 0, '关闭全部指标和数据来源时只读首屏，不预取完整概览');
    assert(!nodes(tree).some(row => row.props.className === 'rd-candidate-facts'), '关闭来源不挂载要求重矩阵的CandidateFacts');
    nodes(tree).find(row => row.props.className === 'rd-official rd-data-source').props.onToggle({ currentTarget: { open: true } }); await render();
    assert.equal(requests.length, 1); assert(text(tree).includes('正在读取全部方案指标'));
    nodes(tree).find(row => row.props.id === 'rd-tab-metrics').props.onClick(); await render();
    assert.equal(requests.length, 1, '全部指标与已展开来源共用一次完整读取');
    assert.deepEqual(requests[0].q, { comparison_mode: 'candidates', resource_view: 'selected_batches', selected_candidate_ref: third, reference_candidate_ref: first, range_start, range_end, snapshot_ref: String(1).padStart(32, '0') }, '完整读取使用同份精确候选、固定基准、时间、资源范围与首屏快照');
    assert.strictEqual(nodes(tree).find(row => row.props['aria-label'] === '刷新全部方案指标').props.onClick,
      nodes(tree).find(row => row.props['aria-label'] === '刷新方案对比').props.onClick, '完整区域和顶部刷新共用工作区reload');
    requests[0].resolve(responseFor(requests[0].q)); await render();
    assert(nodes(tree).some(row => row.props.className === 'rd-candidate-facts') && nodes(tree).some(row => row.props.className === 'rd-details'));
    nodes(nodes(tree).find(row => row.props['data-decision-candidate'] === first)).find(row => row.props.className === 'rd-candidate-choice').props.onClick();
    tree = state.render(() => expand(local.RunDecisionComparison.Workspace(props)));
    assert(!nodes(tree).some(row => row.props.className === 'rd-details' || row.props.className === 'rd-candidate-facts'), '候选身份变化同一渲染即清空旧完整结果');
    state.flush(); await render(); assert.equal(requests.length, 2); assert(requests[0].signal.aborted);
    nodes(tree).find(row => row.type === 'button' && row.props.icon === 'x' && text(row) === '取消读取').props.onClick(); await render();
    assert(requests[1].signal.aborted && text(tree).includes('全部方案指标读取已取消'));
    assert.equal(nodes(tree).filter(row => row.props['data-decision-candidate']).length, 3, '取消完整读取保持已读候选和推荐可用');
    const summaryReads = summaries.length;
    nodes(tree).find(row => row.props['aria-label'] === '刷新全部方案指标').props.onClick(); await render();
    assert.equal(summaries.length, summaryReads + 1, '取消后刷新先读取新summary');
    assert.equal(requests.length, 3); assert.equal(summaries.at(-1).snapshot_ref, undefined);
    assert.notEqual(requests[2].q.snapshot_ref, requests[1].q.snapshot_ref, '新summary令牌随后绑定当前开启的完整读取');
    const previousToken = requests[2].q.snapshot_ref, previousSummaryCount = summaries.length;
    const previousRefreshTime = window.WorkbenchFormat.dateTime(responseFor(requests[2].q, true).meta.as_of, { seconds: true, fractions: true });
    const stale = Object.assign(new Error('比较资料已变化，请刷新后重新读取。'), { code: 'snapshot_stale', status: 409 });
    requests[2].reject(stale); await render();
    assert(nodes(tree).some(row => row.type === 'error-box' && row.props.error === stale), '完整区域保留实际snapshot_stale错误');
    assert.equal(summaries.length, previousSummaryCount); assert.equal(requests.length, 3, '快照失效等待用户刷新，不自动重试旧令牌');
    assert(text(tree).includes(previousRefreshTime), '完整快照失效保留摘要原刷新时间');
    assert.equal(nodes(tree).filter(row => row.props['data-decision-candidate']).length, 3, '完整区域失败保持候选目录可用');
    nodes(tree).find(row => row.props['aria-label'] === '刷新全部方案指标').props.onClick(); await render();
    assert.equal(summaries.length, previousSummaryCount + 1); assert.notEqual(requests[3].q.snapshot_ref, previousToken, '完整区域刷新经过新summary使用新令牌');
    nodes(nodes(tree).find(row => row.props['data-decision-candidate'] === third)).find(row => row.props.className === 'rd-candidate-choice').props.onClick(); await render();
    assert.equal(requests.length, 5); assert(requests[3].signal.aborted);
    requests[3].resolve(responseFor(requests[3].q)); await render();
    assert(!nodes(tree).some(row => row.props.className === 'rd-details'), '旧候选迟到完整响应保持失效');
    requests[4].resolve(responseFor(requests[4].q)); await render();
    assert(nodes(tree).some(row => row.props.className === 'rd-details'));
    nodes(tree).find(row => row.props.id === 'rd-tab-delivery').props.onClick(); await render();
    nodes(tree).find(row => row.props.className === 'rd-official rd-data-source').props.onToggle({ currentTarget: { open: false } }); await render();
    assert.equal(requests.length, 5); assert(requests[4].signal.aborted);
    assert(!nodes(tree).some(row => row.props.className === 'rd-candidate-facts') && !text(tree).includes('正在读取全部方案指标'));
    const metricsPanel = nodes(tree).find(row => row.props['data-decision-panel'] === 'metrics');
    assert(metricsPanel.props.hidden, '已访问指标面板隐藏后保留原组件身份');
    nodes(tree).find(row => row.props.id === 'rd-tab-metrics').props.onClick(); await render();
    assert.equal(requests.length, 5, '同摘要快照重开指标直接复用已成功完整读取');
    assert.equal(nodes(tree).find(row => row.props['data-decision-panel'] === 'metrics').props.key, metricsPanel.props.key);
    assert.equal(nodes(tree).find(row => row.type === 'detail-pane').props.enabled, false, '已访问交付面板保留且关闭内部读取');
    assert(!nodes(tree).some(row => row.props['data-decision-panel'] === 'resources'), '尚未访问的资源面板保持未挂载');
    nodes(tree).find(row => row.props.id === 'rd-tab-delivery').props.onClick(); await render();
    const hiddenSummaryReads = summaries.length;
    nodes(tree).find(row => row.props['aria-label'] === '刷新方案对比').props.onClick(); await render();
    assert.equal(summaries.length, hiddenSummaryReads + 1); assert.equal(requests.length, 5, '摘要刷新时隐藏指标不提前读取');
    nodes(tree).find(row => row.props.id === 'rd-tab-metrics').props.onClick(); await render();
    assert.equal(requests.length, 6, '重开刷新后的指标只读当前摘要快照一次');
    requests[5].resolve(responseFor(requests[5].q)); await render();
    console.log(JSON.stringify({ r18_full_read: { same_snapshot_reopen: 0, hidden_refresh: 0, refreshed_reopen: 1 } }));
  }
  const task = (ref, op) => ({ row_ref: ref, operation_ref: op, batch_ref: batchRef, batch_label: 'B-001', process_label: '车削', sequence: 1, start: range_start, end: range_end, source: 'internal', machine: null, operator: null, data_gaps: [] });
  const value = referenceFixture(); value.data.tasks = [task(otherRowRef, missingOperationRef), task(rowRef, operationRef), task(secondSegmentRef, operationRef)];
  value.data.task_count = value.data.candidate_task_count = 3;
  const capacityError = Object.assign(new Error('候选方案超过 32 MB，请缩小读取范围。'), { code: 'candidate_capacity_exceeded', status: 413 });
  const capacity = await candidateWorkspace({ candidate_ref: third }, value, (_ref, scope) => {
    if (!scope.range_start) throw capacityError;
    return value;
  });
  const workspaceReads = () => capacity.calls.filter(call => call.name === 'workspace');
  assert.equal(workspaceReads().length, 1);
  assert.equal(capacity.graphBuilds, 0, 'A failed workspace read does not prepare a graph');
  assert(nodes(capacity.tree).some(node => node.type === 'error-box' && node.props.error === capacityError));
  assert(!nodes(capacity.tree).some(node => node.type === 'candidate-gantt' || node.props.transfer === 'export'));
  const rangeButton = nodes(capacity.tree).find(node => node.type === 'button' && text(node) === '读取范围');
  assert(rangeButton, '首次容量错误后仍可从同一候选直接调整读取范围');
  rangeButton.props.onClick(); await capacity.render();
  nodes(capacity.tree).find(node => node.type === 'form' && node.props.className === 'rc-range').props.onSubmit({ preventDefault() {} }); await capacity.render();
  assert(nodes(capacity.tree).some(node => node.type === 'error-box' && node.props.error && /读取范围需要成对时间/.test(node.props.error.message)), '失败外壳继续呈现同一范围表单的校验错误');
  nodes(capacity.tree).find(node => node.props['aria-label'] === '候选读取开始').props.onChange({ target: { value: '2026-10-01 00:00:00' } }); await capacity.render();
  nodes(capacity.tree).find(node => node.props['aria-label'] === '候选读取结束').props.onChange({ target: { value: '2026-10-02 00:00:00' } }); await capacity.render();
  assert.equal(workspaceReads().length, 1, '打开范围与填写日期均保持本地状态，不提前读取或自动重试');
  nodes(capacity.tree).find(node => node.type === 'form' && node.props.className === 'rc-range').props.onSubmit({ preventDefault() {} }); await capacity.render();
  assert.equal(workspaceReads().length, 2, '应用手动范围仅重新读取一次');
  assert.equal(capacity.graphBuilds, 1, 'The candidate workspace prepares its graph once after the successful read');
  assert.equal(workspaceReads()[1].args[0], third, '缩窗保留同一候选编号');
  assert.deepEqual(clone(workspaceReads()[1].args[1]), { sort: 'sequence', order: 'asc', range_start, range_end: '2026-10-02T00:00:00' });
  assert(nodes(capacity.tree).some(node => node.type === 'candidate-gantt'));
  assert(nodes(capacity.tree).some(node => node.props.transfer === 'export'));
  assert(!nodes(capacity.tree).some(node => node.type === 'error-box' && node.props.error));
  assert(text(capacity.tree).includes('当前显示 3 道安排'));
  const candidateOnly = await candidateWorkspace({ candidate_ref: third }, value);
  assert.equal(candidateOnly.graphBuilds, 1);
  assert.equal(candidateOnly.calls.filter(call => call.name === 'workspace').length, 1, '只有候选编号时发现排产编号仍只读一次workspace');
  assert.equal(candidateOnly.calls.filter(call => call.name === 'catalog').length, 1, '发现排产编号只启动一次目录读取');
  nodes(candidateOnly.tree).find(row => row.props.id === 'rc-detail-tab-history').props.onClick(); await candidateOnly.render();
  assert.equal(candidateOnly.calls.filter(call => call.name === 'adoptions').length, 1);
  nodes(candidateOnly.tree).find(row => row.props.id === 'rc-detail-tab-tasks').props.onClick(); await candidateOnly.render();
  nodes(candidateOnly.tree).find(row => row.props.id === 'rc-detail-tab-history').props.onClick(); await candidateOnly.render();
  assert.equal(candidateOnly.calls.filter(call => call.name === 'adoptions').length, 1, '候选采用记录同workspace快照重开不重复读取');
  assert.equal(candidateOnly.graphBuilds, 1, 'Local tabs reuse the graph prepared by the workspace');
  nodes(candidateOnly.tree).find(row => row.props['aria-label'] === '刷新候选方案').props.onClick(); await candidateOnly.render();
  assert.equal(candidateOnly.calls.filter(call => call.name === 'workspace').length, 2);
  assert.equal(candidateOnly.calls.filter(call => call.name === 'adoptions').length, 2, '显式刷新候选后重读当前采用记录');
  console.log(JSON.stringify({ r18_candidate: { first_workspace: 1, discovered_catalog: 1, history_reopen: 0, refreshed_workspace: 1, refreshed_history: 1 } }));
  const base = { run_ref: runRef, candidate_ref: third, operation_ref: operationRef, selected_row_ref: otherRowRef };
  const candidate = await candidateWorkspace(base, value);
  assert.equal(candidate.chosen.row_ref, rowRef, 'rowRef 指向其他工序时按 operation_ref 定位目标工序');
  assert(!candidate.captions.at(-1).range, '共享页头保持唯一候选身份，时间范围由甘特读取工具负责');
  const gantt = nodes(candidate.tree).find(node => node.type === 'candidate-gantt'), detailToggle = nodes(expand(gantt.props.toolbarActions)).find(node => node.type === 'button'), reads = candidate.calls.length;
  assert.equal(detailToggle.props['aria-expanded'], true); detailToggle.props.onClick(); await candidate.render();
  assert(!nodes(candidate.tree).some(node => node.type === 'candidate-detail')); assert.equal(candidate.calls.length, reads, '甘特工具栏详情开关只切换展示，不重读或改变工序定位');
  assert.strictEqual(nodes(candidate.tree).find(node => node.type === 'candidate-gantt').props.selected, candidate.chosen);
  nodes(candidate.tree).find(node => node.type === 'candidate-gantt').props.onSelect(value.data.tasks[2]); await candidate.render();
  assert(!nodes(candidate.tree).some(node => node.type === 'candidate-detail'), '普通甘特选择保持收起详情');
  const taskRow = nodes(candidate.tree).find(node => node.props['data-row-ref'] === secondSegmentRef);
  nodes(taskRow).find(node => node.type === 'button' && node.props.icon === 'search').props.onClick(); await candidate.render();
  const reopened = nodes(candidate.tree).find(node => node.type === 'candidate-detail'); assert.strictEqual(reopened.props.task, value.data.tasks[2], '现有任务表详情按钮选中原工序并展开');
  const reopenedGantt = nodes(candidate.tree).find(node => node.type === 'candidate-gantt'), openToggle = nodes(expand(reopenedGantt.props.toolbarActions)).find(node => node.type === 'button');
  assert.equal(openToggle.props['aria-expanded'], true); openToggle.props.onClick(); await candidate.render();
  assert(!nodes(candidate.tree).some(node => node.type === 'candidate-detail')); assert.strictEqual(nodes(candidate.tree).find(node => node.type === 'candidate-gantt').props.selected, value.data.tasks[2]);
  assert.equal(candidate.calls.length, reads, '明确展开与再收起详情保留所选工序且不重复读取');
  const returnContext = { run_ref: runRef, candidate_ref: third, comparison_mode: 'admission_official', comparison_tab: 'operations', metric_view: 'all',
    detail_queries: { operations: { batch_ref: batchRef, resource_ref: resourceRef, page: 2, size: 50, snapshot_ref: snapshot } }, range_start, range_end };
  const formal = await candidateWorkspace({ ...base, selected_row_ref: secondSegmentRef, reference_view: true, comparison_mode: 'admission_official', plan_ref: planRef,
    return_decision_context: returnContext }, value);
  assert.equal(formal.chosen.row_ref, secondSegmentRef, 'rowRef 属于目标工序时保留指定正式 segment');
  assert.equal(formal.calls.filter(call => call.name === 'referenceWorkspace').length, 1);
  assert.equal(formal.calls.filter(call => ['catalog', 'workspace', 'analysis', 'adoptions'].includes(call.name)).length, 0, '正式甘特读取受理时 reference-workspace');
  assert(!nodes(formal.tree).some(node => ['adoption', 'trial', 'catalog'].includes(node.type)), '受理时正式甘特保持只读入口');
  nodes(formal.tree).find(node => node.type === 'button' && text(node) === '返回方案对比').props.onClick();
  assert.deepEqual(clone(formal.links.at(-1).context), returnContext, '返回比较完整保留页签、指标、筛选、页码和时间窗');
  const missing = clone(value); missing.data.tasks = []; missing.data.task_count = 0; missing.data.unplanned_operations = [{ operation_ref: operationRef, batch_ref: batchRef, row_ref: null, reason: { message: '保存记录中的未安排工序' } }]; missing.data.unplanned_operation_count = 1;
  const unplanned = await candidateWorkspace({ ...base, selected_row_ref: rowRef }, missing);
  assert.equal(unplanned.chosen.operation_ref, operationRef, '旧 rowRef 失效时可按 operation_ref 定位未安排工序');
  assert.equal(nodes(unplanned.tree).find(node => node.props.id === 'rc-detail-tab-unplanned').props['aria-selected'], true);
  const rowOnly = await candidateWorkspace({ run_ref: runRef, candidate_ref: third, selected_row_ref: secondSegmentRef }, value);
  assert.equal(rowOnly.chosen.row_ref, secondSegmentRef, '原 rowRef 单独钻取继续定位具体安排');
  const sourceFixture = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures/decision_candidate_baseline.json'), 'utf8')), sourceSaved = clone(sourceFixture);
  const source = expand(h(candidate.baselineSource, { workspace: sourceFixture.workspace, comparison: sourceFixture.baseline.data }));
  assert.equal(source.children.filter(row => row && row.type === 'span').length, 2, '新旧来源各保留一句');
  assert(text(source.children[0]).includes(sourceFixture.workspace.candidate.label));
  assert(source.children[0].props.title.includes(sourceFixture.workspace.generation.algorithm.mode_label), '原算法方式保留在title');
  assert(!/\d{2}:\d{2}:\d{2}/.test(text(source.children[1])) && /\d{2}:\d{2}:\d{2}/.test(source.children[1].props.title), '原安排默认分钟，完整秒值仍可悬停查看');
  assert.deepEqual(clone(sourceFixture), sourceSaved);
}
// The single production mount (RunDecisionComparison.Workspace) always passes these props.
const detailPaneDefaults = { selectedBatchRef: null, onSelectBatch() {}, chainQuery: {}, onChainQuery() {}, onDrill() {}, onChooseReference() {}, enabled: true };
async function paneContracts() {
  {
    // The pane reads RunDecisionAPI.decisionDetails itself; this ownership check answers it on the module object (its HTTP path is in transportContracts).
    const state = hooks(), waiting = [], local = { ...window, RunDecisionAPI: { ...API, decisionDetails: (run, q, section) => new Promise(resolve => waiting.push({ q: clone(q), section, resolve })) }, APSResourceContract: {} };
    for (const name of ['resource-session.js', 'RunDecisionDetails.jsx']) for (const output of compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources: [{ path: name, code: fs.readFileSync(path.join(app, name), 'utf8') }] }).outputs)
      vm.runInNewContext(output.code, { React: state.React, window: local, AbortController, DOMException });
    const props = { result: clone(summaryPayload), section: 'differences', query: {}, onQuery: value => { props.query = value; }, ...detailPaneDefaults };
    let tree;
    const render = async () => { for (let i = 0; i < 3; i++) { tree = state.render(() => local.RunDecisionDetails.Pane(props)); state.flush(); await turns(); } };
    await render();
    assert(!text(tree).includes('工序安排一致') && text(tree).replace(/\s+/g, '').includes('正在读取方案差异批次'), '摘要没有重指标时等待批次明细，缺值不补零');
    const equal = detailsFixture('batches', waiting[0].q); equal.data.items = []; equal.data.page.total = 0;
    equal.data.summary.operation_changes.changed_operation_count = { ...metric, value: 0, known_subtotal: 0 };
    waiting[0].resolve(equal); await render();
    assert(text(tree).includes('工序安排一致'), '安排一致取全范围批次明细共同metric');
    nodes(tree).find(row => row.type === 'button' && row.props.icon === 'refresh-cw').props.onClick(); await render();
    assert(!text(tree).includes('工序安排一致'), '刷新明细清除旧的安排一致判断');
    const unknown = detailsFixture('batches', waiting[1].q); unknown.data.items = []; unknown.data.page.total = 0;
    unknown.data.summary.operation_changes.changed_operation_count = { ...metric, value: null, state: 'partial', unknown_count: 1, known_count: 2, known_subtotal: 0,
      reason: { code: 'arrangement_comparison_incomplete', message: '保存工序安排差值待确认。' } };
    waiting[1].resolve(unknown); await render();
    assert(text(tree).includes('保存工序安排差值待确认。') && !text(tree).includes('工序安排一致'), '未知变化仍显示明细真实原因');
    props.result.data.scope.selected_candidate_ref = first; await render();
    assert(text(tree).includes('正在查看同一个方案') && waiting.length === 2, '相同方案判断继续使用永久候选身份');
  }
  const calls = [], state = hooks(), local = { ...window, APSResourceContract: {}, RunOperationEffort: { Effort: 'effort-facts', Standard: 'standard-facts' },
    RunDecisionAPI: { ...API, decisionDetails: async (run, q, section) => { calls.push(clone(q)); if (calls.length === 1) throw new Error('读取失败'); return detailsFixture(section, q); } } };
  const sources = ['resource-session.js', 'BatchContract.js', 'PlanGanttModel.js', 'RunCandidateModel.js', 'RunDecisionDetails.jsx'].map(name => ({ path: name, code: fs.readFileSync(path.join(app, name), 'utf8') }));
  for (const output of compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources }).outputs)
    vm.runInNewContext(output.code, { React: state.React, window: local, AbortController, DOMException });
  const props = { result: payload, section: 'delivery', query: {}, onQuery: next => { props.query = next; }, ...detailPaneDefaults };
  let tree;
  async function render() {
    for (let i = 0; i < 3; i++) { tree = state.render(() => local.RunDecisionDetails.Pane(props)); state.flush(); await turns(); }
  }
  await render();
  assert.equal(calls.length, 1); assert(nodes(tree).some(node => node.type === 'error-box' && node.props.error));
  assert.equal(calls[0].delivery_filter, 'attention'); assert.equal(calls[0].change_kind, 'all'); assert.equal(calls[0].sort, 'current_priority');
  nodes(tree).find(node => node.type === 'button' && node.props.icon === 'refresh-cw').props.onClick(); await render();
  assert.equal(calls.length, 2, '第 1 页无 snapshot 的首读失败，刷新必须重新发送请求');
  assert(!nodes(tree).some(node => node.type === 'error-box' && node.props.error));
  props.query = { ...API.detailScope(runRef, query, 'batches'), batch_ref: batchRef, page: 1 };
  props.result = { ...clone(payload), data: { ...clone(data), scope: comparisonScope({ comparison_mode: 'admission_official' }), baseline: clone(officialBaseline) } };
  await render();
  assert.equal(calls.at(-1).comparison_mode, 'admission_official');
  assert.equal(calls.at(-1).reference_candidate_ref, undefined, '恢复的候选明细参数转正式比较后清除旧候选基准');
  assert.equal(calls.at(-1).batch_ref, batchRef, '比较模式变化仍保留批次筛选');
  props.section = 'differences'; props.query = {}; props.selectedBatchRef = batchRef; await render();
  assert.equal(calls.at(-1).delivery_filter, 'all'); assert.equal(calls.at(-1).change_kind, 'changed'); assert.equal(calls.at(-1).selected_batch_ref, batchRef, '差异页通过独立锚保留同一批次，列表筛选与锚分别回显');
  const deferred = detailsFixture('batches').data, finish = '2026-10-01T13:45:12.250';
  Object.assign(deferred.items[0], { batch_id: 'B-001', quantity: 1, priority: 'normal', due_date: '2026-10-05', due_state: 'specified', due_issue: null });
  deferred.items[0].before = { operation_count: 2, scheduled_operation_count: 1, ordinary_unscheduled_operation_count: 0, deferred_operation_count: 1, completion_state: 'deferred', planned_finish: null, partial_planned_finish: finish, risk: 'unknown', delay_hours: null };
  deferred.items[0].after = clone(deferred.items[0].before);
  Object.assign(deferred.items[0], { finish_delta_hours: 0, delay_delta_hours: null, operation_change_count: 1, operation_unknown_count: 1, operation_changes_state: 'partial', attention_kinds: ['deferred'] });
  const selected = [], master = expand(h(local.RunDecisionDetails.BatchList, { data: deferred, difference: true, selectedRef: batchRef, onSelect: ref => selected.push(ref) }));
  const masterText = visibleText(master).replace(/\s+/g, ' ');
  assert(masterText.includes('1 道工序有变化') && masterText.includes('批次末端 持平'), '批次末端相同仍明确保留中间工序变化');
  assert(masterText.includes('1 道工序差值待确认') && !masterText.includes('预计按期'), '待料缺项保留真实未知交付');
  nodes(master).find(row => row.type === 'button').props.onClick(); assert.equal(selected.at(-1), batchRef);
  const arrangement = (start, end) => ({ row_ref: rowRef, start, end, machine: { ref: resourceRef, label: '设备 1' }, operator: null, source: 'internal', locked: false, data_gaps: [] });
  const known = { operation_ref: operationRef, batch_ref: batchRef, batch_label: 'B-001', part_label: '零件', sequence: 1, process_label: '车削', piece_id: null, quantity: 1,
    before: arrangement('2026-10-01T11:06:00', '2026-10-01T13:00:00'), after: arrangement('2026-10-01T11:10:48', '2026-10-01T13:00:00'),
    before_state: { status: 'arranged', reason: null }, after_state: { status: 'arranged', reason: null }, start_delta_hours: 0.08, end_delta_hours: 0, changed_fields: ['start'], change_kinds: ['moved'],
    runtime_effort: { before: {}, after: {} }, effort: {}, constraints: { execution_state: 'unreported', data_quality: 'complete', protected_at_admission: false, selected_locked: false, reference_locked: false, known_completed_quantity: null, remaining_quantity: null, first_actual_start: null, confirmed_finish: null, reasons: [] }, data_gaps: [], drill: deferred.items[0].drill };
  const unknown = { ...clone(known), operation_ref: missingOperationRef, sequence: 2, before: null, after: null, before_state: { status: 'deferred', reason: { code: 'material_deferred', message: '排产时保存的待料原因。' } }, after_state: { status: 'deferred', reason: { code: 'material_deferred', message: '排产时保存的待料原因。' } }, start_delta_hours: null, end_delta_hours: null, changed_fields: [], change_kinds: ['unknown'] };
  const chainData = { ...deferred, items: [known, unknown] }, savedChain = clone(chainData), chain = expand(h(local.RunDecisionDetails.OperationChain, { data: chainData, difference: true }));
  assert.equal(nodes(chain).filter(row => row.props['data-decision-operation']).length, 2, '完整工序链保留已安排与待料工序');
  assert(nodes(chain).some(row => row.props.title && row.props.title.includes('11:10:48')), '变化安排保留真实秒值');
  const unknownRow = nodes(chain).find(row => row.props['data-decision-operation'] === missingOperationRef);
  assert(visibleText(unknownRow).includes('待料未排') && visibleText(unknownRow).includes('差值待确认') && visibleText(unknownRow).includes('排产时保存的待料原因。'), '双方都未排继续展示未知时间及真实原因');
  assert(!visibleText(unknownRow).includes('持平')); assert.deepEqual(clone(chainData), savedChain, '时间轴和阅读布局保留保存DTO原值');
}
function completionFixture(q = {}, state = 'complete', persisted = 'completed') {
  // The batch list belongs to the current candidate itself (selected_candidate_ref); there is no second anchor.
  q = API.completionScope(runRef, { ...query, ...q });
  const refs = Array.from({ length: 21 }, (_, index) => (index + 100).toString(16).padStart(48, '0'));
  const savedMetric = { ...metric, value: 0, known_subtotal: 0 };
  const metrics = Object.fromEntries(prepKeys.map(key => [key, clone(savedMetric)]));
  const remaining = state === 'ordinary' ? 1 : 0;
  const drill = remaining ? { run_ref: runRef, candidate_ref: q.selected_candidate_ref, selected_candidate_ref: q.selected_candidate_ref, reference_candidate_ref: first, comparison_mode: 'candidates', resource_view: q.resource_view, range_start, range_end, comparison_tab: 'preparation', detail_query: { work_scope: 'remaining' } } : null;
  let items = refs.map((batch_ref, index) => {
    const unfinished = state !== 'complete' && index === 0, count = unfinished && state === 'ordinary' ? 1 : 0;
    return { batch_ref, batch_label: 'B-' + String(index + 1).padStart(3, '0'), part_no: 'P-001', part_label: null, quantity: 1,
      completion_state: unfinished && state === 'unknown' ? 'unknown' : unfinished ? 'incomplete' : 'complete', schedule_complete: !unfinished,
      scheduled_operation_count: 1, unplanned_operation_count: count, deferred_operation_count: 0,
      remaining_work: { operation_count: count, metrics: clone(metrics) }, issues: unfinished ? ['schedule_time_invalid'] : [],
      remaining_drill: count ? { ...clone(drill), detail_query: { work_scope: 'remaining', batch_ref } } : null };
  });
  const incomplete = items.filter(row => row.schedule_complete !== true), complete = items.filter(row => row.schedule_complete === true), ordinary = items.filter(row => row.completion_state === 'incomplete'), unknown = items.filter(row => row.completion_state === 'unknown');
  const summary = { ...clone(completionScope), state: incomplete.length ? state === 'unknown' ? 'unavailable' : 'partial' : 'complete', source_available: true,
    complete_batch_count: complete.length, incomplete_batch_count: incomplete.length, ordinary_incomplete_batch_count: ordinary.length, deferred_batch_count: 0, unknown_batch_count: unknown.length,
    unplanned_operation_count: remaining, deferred_operation_count: 0,
    sample_batch_refs: { complete: complete.slice(0, 3).map(row => row.batch_ref), incomplete: incomplete.slice(0, 3).map(row => row.batch_ref), deferred: [], unknown: unknown.slice(0, 3).map(row => row.batch_ref) },
    remaining_work: { operation_count: remaining, unplanned_operation_count: remaining, deferred_operation_count: 0, metrics: clone(metrics) }, drill };
  items = items.filter(row => q.completion_filter === 'all' || q.completion_filter === 'complete' && row.schedule_complete === true || q.completion_filter === 'unfinished' && row.schedule_complete !== true || q.completion_filter === 'ordinary' && row.completion_state === 'incomplete' || q.completion_filter === 'unknown' && row.completion_state === 'unknown');
  if (q.order === 'desc') items.reverse();
  const total = items.length;
  return { ...clone(payload), data: { run_ref: runRef, scope: { ...clone(data.scope), selected_candidate_ref: q.selected_candidate_ref, batch_refs: refs }, baseline: clone(data.baseline),
    candidate: { candidate_ref: q.selected_candidate_ref, label: '完成集合成员', persisted_status: persisted },
    source: { role: 'completion_anchor', grain: 'full_admission_per_candidate_batch', candidate_ref: q.selected_candidate_ref, available: true, reason: null },
    filters: { section: 'completion-batches', completion_filter: q.completion_filter, sort: q.sort, order: q.order },
    summary, items: items.slice((q.page - 1) * q.size, q.page * q.size), page: { number: q.page, size: q.size, total, has_more: q.page * q.size < total }, metric_version: 'decision-preparation-v4' } };
}
async function completionContracts() {
  const q = { ...query, selected_candidate_ref: recommended, completion_filter: 'complete' }, read = value => API.validateCompletionBatches(value, runRef, q);
  const one = completionFixture(q), two = completionFixture({ ...q, page: 2, snapshot_ref: snapshot }), all = completionFixture({ ...q, size: 50 });
  assert.strictEqual(read(one), one.data);
  assert.strictEqual(API.validateCompletionBatches(two, runRef, { ...q, page: 2, snapshot_ref: snapshot }), two.data);
  assert.strictEqual(API.validateCompletionBatches(all, runRef, { ...q, size: 50 }), all.data);
  assert.equal(one.data.items.length, 20); assert.equal(two.data.items.length, 1);
  assert.deepEqual([...one.data.items, ...two.data.items], all.data.items, '同一成员的完整集合逐页20+1与50条一页保持同源、完整且无重复');
  rejected(one, value => { value.data.scope.selected_candidate_ref = third; }, read, '批次清单只属于当前查看方案');
  rejected(one, value => { value.data.filters.completion_candidate_ref = recommended; }, read, '筛选回显只有分区、批次安排筛选与排序');
  assert.throws(() => API.completionScope(runRef, { range_start, range_end }), /请选择要查看批次安排的方案/, '批次清单必须显式选择当前方案');
  rejected(one, value => { value.data.source.candidate_ref = third; }, read, '批次来源必须属于集合锚点');
  const remainingQuery = { ...q, completion_filter: 'ordinary' }, remaining = completionFixture(remainingQuery, 'ordinary');
  assert.strictEqual(API.validateCompletionBatches(remaining, runRef, remainingQuery), remaining.data);
  rejected(remaining, value => { value.data.items[0].remaining_drill.detail_query.work_scope = 'all'; }, value => API.validateCompletionBatches(value, runRef, remainingQuery), '剩余需求只准进入精确剩余工序');
  const unknownQuery = { ...q, completion_filter: 'unknown' }, unknown = completionFixture(unknownQuery, 'unknown');
  assert.strictEqual(API.validateCompletionBatches(unknown, runRef, unknownQuery), unknown.data);
  assert.equal(unknown.data.items[0].remaining_work.operation_count, 0); assert.equal(unknown.data.items[0].remaining_drill, null, '已安排但时间未知的批次保持零剩余，不推断漏排');
  for (const persisted of ['failed', 'skipped']) {
    const invalidStatus = completionFixture(unknownQuery, 'unknown', persisted);
    assert.throws(() => API.validateCompletionBatches(invalidStatus, runRef, unknownQuery), /批次安排资料/);
  }
  // The pane reads RunDecisionAPI.completionBatches itself; this ownership check answers it on the module object.
  const state = hooks(), calls = [], links = [], local = { ...window, RunDecisionAPI: { ...API, completionBatches: (run, value, signal) => { calls.push({ value: clone(value), signal }); return Promise.resolve(completionFixture(value, value.completion_filter === 'ordinary' ? 'ordinary' : 'complete')); } } };
  for (const name of ['resource-session.js', 'RunDecisionCompletion.jsx']) {
    const outputs = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources: [{ path: name, code: fs.readFileSync(path.join(app, name), 'utf8') }] }).outputs;
    for (const output of outputs) vm.runInNewContext(output.code, { React: state.React, window: local, AbortController, DOMException });
  }
  const props = { result: clone(payload), query: { completion_filter: 'complete' }, enabled: true,
    onQuery: value => { props.query = value; }, onSupport: value => links.push(value) };
  let tree;
  async function render() { for (let i = 0; i < 3; i++) { tree = state.render(() => expand(local.RunDecisionCompletion.Pane(props))); state.flush(); await turns(); } }
  await render();
  assert.equal(calls[0].value.selected_candidate_ref, third, '工序安排锚点由共同当前方案派生'); assert(!('completion_candidate_ref' in calls[0].value), '批次清单请求不带第二条候选选择');
  assert(!nodes(tree).some(row => row.type === 'button' && row.props.icon === 'search'), '零剩余工序不生成活动剩余需求跳转');
  assert(!nodes(tree).some(row => row.type === 'details' && row.props.className === 'rd-completion-demand'), '零剩余工序不生成默认需求入口');
  assert(nodes(tree).some(row => row.props['data-completion-metric']), '零剩余的原metric仍保留在原生数量资料中');
  nodes(tree).find(row => row.type === 'pager').props.onPage(2); await render();
  assert.equal(calls.at(-1).value.page, 2); assert.equal(calls.at(-1).value.snapshot_ref, snapshot);
  props.result.data.scope.selected_candidate_ref = first; bindRecommendationScope(props.result); props.query = { ...props.query, page: 1 }; delete props.query.snapshot_ref; await render();
  assert.equal(calls.at(-1).value.page, 1); assert.equal(calls.at(-1).value.snapshot_ref, undefined); assert.equal(calls.at(-1).value.selected_candidate_ref, first);
  assert.equal(props.query.completion_candidate_ref, undefined, '工序安排叶不保存第二条候选选择');
  nodes(tree).find(row => row.type === 'select' && row.props.value === 'complete').props.onChange({ target: { value: 'ordinary' } }); await render();
  nodes(tree).find(row => row.type === 'button' && row.props.icon === 'search' && typeof row.props.onClick === 'function').props.onClick();
  assert.equal(links.at(-1).candidate_ref, first); assert.equal(links.at(-1).drill.detail_query.work_scope, 'remaining');
  props.enabled = false; await render();
  assert.equal(tree, null); assert(calls.at(-1).signal.aborted, '折叠集合取消挂起的同源读取');
  const closed = expand(h(comparisonWorkspace({ decisionSummary: () => payload }), { ...workspaceDefaults, initialContext: { run_ref: runRef, candidate_ref: third } }));
  assert(!nodes(closed).some(row => row.props['data-completion-anchor']), '总览集合默认折叠，首屏不读取集合明细');
}
async function processPaneContracts() {
  const currentProcess = window.RunDecisionProcess;
  const closed = expand(h(comparisonWorkspace({ decisionSummary: () => payload }), { ...workspaceDefaults, initialContext: original }));
  assert(!nodes(closed).some(node => node.props['data-process-anchor']), '默认交期页不读取过程reader');
  window.RunDecisionProcess = { Pane: 'process-pane' };
  const leaf = { open: true, process_candidate_ref: first, record_kind: 'progress', sort: 'event_index', order: 'desc', page: 2, size: 20, snapshot_ref: snapshot };
  const context = { ...original, comparison_tab: 'process', detail_queries: { process: leaf, operations: { page: 3, snapshot_ref: 't'.repeat(32) } } }, targets = [];
  const mainState = hooks(), mainQueries = [], mainReads = { ...API }, mainLocal = { ...window, RunDecisionAPI: mainReads, RunDecisionCompletion: { Pane: 'completion-pane' } };
  for (const output of compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources: [{ path: 'RunDecisionComparison.jsx', code: fs.readFileSync(path.join(app, 'RunDecisionComparison.jsx'), 'utf8') }] }).outputs)
    vm.runInNewContext(output.code, { React: mainState.React, window: mainLocal, AbortController });
  const mainProps = { initialContext: context, runHistoryReturn, onNavigate: (page, value) => targets.push({ page, value }), renderAdoption: (ref, metadata) => h('adoption', { candidateRef: ref, ...metadata }), renderTrial: () => null };
  Object.assign(mainReads, { decisionSummary: (run, value) => {
    mainQueries.push(clone(value)); const next = clone(payload); next.data.scope.selected_candidate_ref = value.selected_candidate_ref || third;
    if (value.comparison_mode === 'admission_official') { next.data.scope = comparisonScope(value); next.data.baseline = clone(officialBaseline); }
    else { next.data.scope.reference.candidate_ref = value.reference_candidate_ref || first; next.data.baseline.candidate_ref = next.data.scope.reference.candidate_ref; next.data.baseline.label = next.data.candidates.find(row => row.candidate_ref === next.data.scope.reference.candidate_ref).label; }
    return bindRecommendationScope(next);
  } });
  mainReads.decision = (run, value) => mainReads.decisionSummary(run, value);
  let main, mainRaw;
  const renderMain = () => { mainRaw = mainState.render(() => mainLocal.RunDecisionComparison.Workspace(mainProps)); main = expand(mainRaw); mainState.flush(); };
  renderMain();
  // Changing the viewed candidate keeps the process source anchor and record filters, and releases the old page snapshot.
  const normalizedLeaf = { open: true, process_candidate_ref: first, record_kind: 'progress', sort: 'event_index', order: 'desc', page: 1, size: 20 };
  nodes(nodes(main).find(node => node.props['data-decision-candidate'] === first)).find(node => node.props.className === 'rd-candidate-choice').props.onClick(); renderMain();
  assert.equal(mainQueries.at(-1).selected_candidate_ref, first); assert.equal(mainQueries.at(-1).reference_candidate_ref, first);
  assert.equal(nodes(main).find(node => node.type === 'adoption').props.candidateRef, first, '在过程页切换查看方案进入共同工作区，采用对象随之更新');
  assert.equal(nodes(main).find(node => node.type === 'adoption').props.candidateDisplay.label, data.candidates[0].label);
  assert.equal(nodes(main).find(node => node.props.className === 'rd-recommend-cause').children[0], data.selection_basis.explanation.headline, '切换共同查看方案保留保存的推荐原因');
  const savedContext = clone(remembered.at(-1)); nodes(main).find(node => node.type === 'button' && text(node) === '看甘特').props.onClick();
  assert.equal(targets.at(-1).page, 'gantt'); assert.equal(targets.at(-1).value.candidate_ref, first);
  assert.equal(targets.at(-1).value.return_decision_context.candidate_ref, first); assert.equal(targets.at(-1).value.return_decision_context.reference_candidate_ref, first);
  assert.deepEqual(clone(targets.at(-1).value.return_decision_context), savedContext, '过程甘特返回同一共同方案、固定对照、窗口及记录筛选');
  assert.deepEqual(clone(targets.at(-1).value.return_decision_context.detail_queries.process), normalizedLeaf);
  nodes(main).find(node => node.props['aria-label'] === '候选比较基准').props.onChange({ target: { value: 'admission_official' } }); renderMain();
  assert.equal(mainQueries.at(-1).comparison_mode, 'admission_official'); assert.equal(mainQueries.at(-1).reference_candidate_ref, undefined); assert.equal(mainQueries.at(-1).selected_candidate_ref, first, '同一对照入口切正式基准时保留共同查看对象');
  nodes(main).find(node => node.props['aria-label'] === '候选比较基准').props.onChange({ target: { value: first } }); renderMain();
  assert.equal(mainQueries.at(-1).comparison_mode, 'candidates'); assert.equal(mainQueries.at(-1).reference_candidate_ref, first);
  nodes(main).find(node => node.props.className === 'rd-official rd-data-source').props.onToggle({ currentTarget: { open: true } }); renderMain();
  nodes(mainRaw).find(node => node.type === mainLocal.RunDecisionComparison.CandidateFacts).props.onCompletion(data.candidates[2], 'deferred'); renderMain();
  const completion = nodes(main).find(node => node.type === 'completion-pane');
  assert.equal(completion.props.result.data.scope.selected_candidate_ref, third); assert.equal(completion.props.query.completion_filter, 'deferred'); assert.equal(completion.props.query.completion_candidate_ref, undefined);
  assert.equal(nodes(main).find(node => node.type === 'adoption').props.candidateRef, third, '打开目标工序安排同步共同当前方案与采用对象');
  const pending = { schema_version: 2, candidate_ref: first, request_key: 'adoption-' + 'a'.repeat(48), phase: 'pending', input: { confirm: true, reason: '原采用原因', declared_operator: '原经办人' },
    preview: { candidate_ref: first, run_ref: runRef, baseline: { plan_ref: planRef, version: 7 }, task_count: 3, scope_complete: true }, data_context_ref: JSON.stringify({ database_scope: '/current.db', successful_restores: [] }) }, savedPending = clone(pending);
  for (const candidateCatalog of [[], data.candidates]) {
    const adoptionState = hooks(), adoptionLocal = { ...window, WorkbenchHandlerMemory: { read: () => ({ value: '经办人' }) }, addEventListener() {}, removeEventListener() {},
      RunAdoptionControls: { Button: 'button', Dialog: 'adoption-dialog' }, RunAdoptionAPI: { ref: window.RunCandidateAPI.ref, pending: () => ({ read: () => pending }), lookup: async () => null, EVENT: 'adoption-event', PENDING_KEY: 'adoption-pending' } };
    for (const output of compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources: [{ path: 'RunAdoptionAction.jsx', code: fs.readFileSync(path.join(app, 'RunAdoptionAction.jsx'), 'utf8') }] }).outputs)
      vm.runInNewContext(output.code, { React: adoptionState.React, window: adoptionLocal, AbortController, DOMException });
    const adoptionProps = { candidateRef: third, candidateDisplay: { candidate_ref: third, label: data.candidates[2].label }, candidateCatalog };
    const renderAdoption = async () => { const value = adoptionState.render(() => expand(adoptionLocal.RunAdoptionAction(adoptionProps))); adoptionState.flush(); await turns(); return value; };
    let adoption = await renderAdoption(); nodes(adoption).find(node => node.type === 'button').props.onClick(); adoption = await renderAdoption();
    const dialog = nodes(adoption).find(node => node.type === 'adoption-dialog'); assert.equal(dialog.props.value.candidate_ref, first);
    if (candidateCatalog.length) assert.deepEqual(clone(dialog.props.candidateDisplay), { candidate_ref: first, label: data.candidates[0].label }, '旧待确认采用按实际对象从已有目录解析业务名');
    else assert.equal(dialog.props.candidateDisplay, undefined, '旧待确认对象无同ref展示资料时不套当前名称');
  }
  assert.deepEqual(clone(pending), savedPending, '名称解析保留原待确认操作、输入与预检事实');
  window.RunDecisionProcess = currentProcess;
  const returned = await candidateWorkspace(targets.at(-1).value, referenceFixture());
  nodes(returned.tree).find(node => node.type === 'button' && text(node) === '返回方案对比').props.onClick();
  assert.deepEqual(clone(returned.links.at(-1).context), savedContext, '真实候选甘特返回入口沿用原过程叶，不切到保存推荐');
}
async function processTransportContracts() {
  // The captured unified process answer travels through the real RunDecisionAPI.process, APSWorkbenchTransport and processDetails.
  const processRaw = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures/unified_process_http.json'), 'utf8'));
  const native = processRaw.decision_summary, nativeRun = native.run.run_ref, nativeCandidate = native.scope.selected_candidate_ref;
  const envelope = value => ({ ok: true, schema_version: 1, data: value, warnings: [], meta: { request_ref: '1'.repeat(32), source: 'production', time_basis: 'factory_local', snapshot_ref: snapshot, as_of: '2026-10-15T02:00:00' } });
  const calls = network.calls, responses = [], process = processRaw.process_by_objective.min_tardiness;
  routes[DECISION + '/**'] = () => responses.shift();
  const q = { selected_candidate_ref: nativeCandidate, objective: 'min_tardiness', snapshot_ref: snapshot };
  responses.push(envelope(process)); const read = await API.process(nativeRun, q);
  assert.deepEqual(clone(read.data), process, '真实共同优化过程经过传输层与公开 DTO 校验');
  const params = calls.at(-1).url.searchParams;
  assert.equal(calls.at(-1).url.pathname, '/api/workbench/v1/scheduling/runs/' + nativeRun + '/decision/process');
  assert.equal(params.get('snapshot_ref'), snapshot); assert.equal(params.get('objective'), 'min_tardiness'); assert.equal(params.get('page'), '1');
  assert.equal(params.get('selected_candidate_ref'), nativeCandidate); assert.equal(params.get('process_candidate_ref'), nativeCandidate, '过程来源默认取当前查看方案');
  responses.push(envelope({ ...clone(process), process_version: 'decision-process-v1' }));
  await assert.rejects(() => API.process(nativeRun, q), /共同优化过程/, '过程存档只认共同优化一种版本');
  for (const format of ['csv', 'xlsx']) {
    responses.push(file(format === 'xlsx' ? Uint8Array.from([0x50, 0x4b, 0x03, 0x04, 0x00]) : '﻿saved process',
      format === 'csv' ? 'text/csv' : 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      { 'Content-Disposition': "attachment; filename*=UTF-8''" + encodeURIComponent('排产方案对比.' + format), 'X-Workbench-Run-Ref': nativeRun, 'X-Workbench-Snapshot-Ref': snapshot, 'X-Workbench-Row-Count': '69' }));
    const exported = await API.decisionExport(nativeRun, { ...q, record_kind: 'progress', sort: 'event_index', order: 'desc', page: 2, size: 50 }, snapshot, format, undefined, 'process');
    assert.equal(exported.filename, '排产方案对比.' + format); assert.equal(exported.row_count, 69);
    const sent = calls.at(-1).url.searchParams;
    assert.equal(sent.get('filter_section'), 'process'); assert.equal(sent.get('process_candidate_ref'), nativeCandidate); assert.equal(sent.get('record_kind'), 'progress'); assert.equal(sent.get('sort'), 'event_index');
    assert.equal(sent.get('objective'), 'min_tardiness'); assert.equal(sent.get('selected_candidate_ref'), nativeCandidate); assert.equal(sent.get('snapshot_ref'), snapshot);
    assert.equal(sent.has('page'), false); assert.equal(sent.has('size'), false, '过程导出覆盖所选方向全部保存页');
  }
}
async function transportContracts() {
  const calls = network.calls, start = calls.length, request = index => calls[start + index], responses = [];
  routes[DECISION + '/**'] = () => responses.shift();
  // Backend export (core/services/workbench/run/decision_export.py): attachment with its own filename, magic bytes and three business headers.
  const exportFile = (format, rowCount, snapshotRef = snapshot) => file(format === 'xlsx' ? Uint8Array.from([0x50, 0x4b, 0x03, 0x04, 0x00]) : '﻿fixture',
    format === 'xlsx' ? 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' : 'text/csv',
    { 'Content-Disposition': "attachment; filename*=UTF-8''" + encodeURIComponent('排产方案对比.' + format), 'X-Workbench-Run-Ref': runRef, 'X-Workbench-Snapshot-Ref': snapshotRef, 'X-Workbench-Row-Count': rowCount });
  const batchQuery = { ...query, batch_ref: batchRef, change_kind: 'later', sort: 'batch_id', order: 'asc', snapshot_ref: snapshot };
  for (const page of [1, 2]) { responses.push(detailsFixture('batches', { ...batchQuery, page })); await API.decisionDetails(runRef, { ...batchQuery, page }, 'batches'); }
  assert.equal(request(0).url.pathname, '/api/workbench/v1/scheduling/runs/' + runRef + '/decision/batches');
  assert.equal(request(1).url.searchParams.get('snapshot_ref'), request(0).url.searchParams.get('snapshot_ref'), '翻页沿用同一明细筛选快照');
  assert.equal(request(1).url.searchParams.get('page'), '2'); assert.equal(request(1).url.searchParams.get('batch_ref'), batchRef);
  const exportQuery = { ...batchQuery, page: 2, size: 50, filter_section: 'batches' };
  responses.push(exportFile('xlsx', '21')); const detailExport = await API.decisionExport(runRef, exportQuery, snapshot, 'xlsx', undefined, 'all');
  assert.equal(detailExport.filename, '排产方案对比.xlsx'); assert.equal(detailExport.row_count, 21, '导出文件名与行数取后端附件和业务头');
  const exported = calls.at(-1).url.searchParams;
  assert.equal(exported.get('snapshot_ref'), snapshot); assert.equal(exported.get('filter_section'), 'batches'); assert.equal(exported.get('batch_ref'), batchRef);
  assert.equal(exported.has('page'), false); assert.equal(exported.has('size'), false, '明细导出读取当前筛选全部页');
  const formalQuery = { comparison_mode: 'admission_official', selected_candidate_ref: third, batch_ref: batchRef, range_start, range_end };
  responses.push(referenceFixture(formalQuery)); await API.referenceWorkspace(runRef, formalQuery);
  assert.equal(calls.at(-1).url.pathname, '/api/workbench/v1/scheduling/runs/' + runRef + '/decision/reference-workspace');
  assert.equal(calls.at(-1).url.searchParams.get('selected_candidate_ref'), third); assert.equal(calls.at(-1).url.searchParams.get('batch_ref'), batchRef);
  responses.push(summaryPayload); const summary = await API.decisionSummary(runRef, query);
  assert.equal(calls.at(-1).url.pathname, '/api/workbench/v1/scheduling/runs/' + runRef + '/decision/summary');
  assert.equal(calls.at(-1).url.searchParams.get('range_start'), range_start); assert.equal(calls.at(-1).url.searchParams.get('range_end'), range_end);
  responses.push(summaryPayload);
  await assert.rejects(() => API.decisionSummary(runRef, { ...query, selected_candidate_ref: first }), /查看方案/, '摘要读取拒绝其他当前候选的响应');
  const reads = calls.length;
  responses.push(exportFile('csv', '21', summary.meta.snapshot_ref));
  assert.equal((await API.decisionExport(runRef, query, summary.meta.snapshot_ref, 'csv')).filename, '排产方案对比.csv');
  assert.equal(calls.length, reads + 1, '摘要令牌直接导出，前置完整概览零请求');
  assert.equal(calls.at(-1).url.pathname, '/api/workbench/v1/scheduling/runs/' + runRef + '/decision/export');
  assert.equal(calls.at(-1).url.searchParams.get('snapshot_ref'), summary.meta.snapshot_ref);
  const savedResources = { resource_kind: 'operator', grain: 'day', pressure_threshold: 0.8, page: 2, heatmap_page: 2,
    snapshot_ref: 'r'.repeat(32), heatmap_mode: 'after', day_resource_ref: '0'.repeat(48), day_page: 2 };
  const combined = resourceWorkspaceFixture(summaryPayload, savedResources), controller = new AbortController();
  responses.push(combined); const resourceWorkspace = await API.resourceWorkspace(runRef, { ...query, snapshot_ref: snapshot }, savedResources, controller.signal);
  assert.deepEqual(clone(resourceWorkspace), clone(combined));
  assert.strictEqual(API.validateResourceWorkspace(combined, runRef, query, savedResources), combined.data);
  const resourceRequest = calls.at(-1), params = resourceRequest.url.searchParams;
  assert.equal(resourceRequest.url.pathname, '/api/workbench/v1/scheduling/runs/' + runRef + '/decision/resource-workspace');
  assert.equal(params.get('snapshot_ref'), snapshot); assert.equal(params.get('resource_snapshot_ref'), savedResources.snapshot_ref, '摘要和旧资源 token 在各自字段传递');
  assert.equal(params.get('resource_kind'), 'operator'); assert.equal(params.get('pressure_threshold'), '0.8'); assert.equal(params.get('page'), '2'); assert.equal(params.get('heatmap_page'), '2');
  for (const key of ['heatmap_mode', 'day_resource_ref', 'day_page']) assert.equal(params.has(key), false, '呈现状态不带入服务查询：' + key);
  assert.equal(resourceRequest.method, 'GET'); assert.equal(resourceRequest.init.cache, 'no-store'); assert.equal(resourceRequest.init.credentials, 'same-origin');
  assert.equal(resourceRequest.signal.aborted, false);
  for (const mutate of [value => { value.data.resource_result = null; }, value => { delete value.data.resource_query.heatmap_size; },
    value => { value.data.resource_query.snapshot_ref = 'q'.repeat(32); }, value => { value.data.scope.selected_candidate_ref = first; }]) {
    const invalid = clone(combined); mutate(invalid); assert.throws(() => API.validateResourceWorkspace(invalid, runRef, query, savedResources));
  }
  // An embedded failure is left to the resource tab, which parses it at the single failure point (APSWorkbenchTransport.failure).
  const embedded = clone(combined.data.resource_result), parsed = window.APSWorkbenchTransport.failure(embedded, embedded.status);
  assert.deepEqual([parsed.code, parsed.status, parsed.committed], ['snapshot_stale', 409, false]);
  embedded.error.fields = [{}]; assert.equal(window.APSWorkbenchTransport.failure(embedded, embedded.status).code, 'invalid_response', '内嵌失败的字段错误形态不合法时按无效响应处理');
  responses.push(combined);
  await assert.rejects(() => API.resourceWorkspace(runRef, query, { ...savedResources, pressure_threshold: 0.7 }), /筛选/, '资源首屏读取核对实际采用的资源筛选');
  // The embedded resource read lives only in data; the old top-level placement is an envelope the transport rejects.
  responses.push({ ...summaryPayload, resource_query: combined.data.resource_query, resource_result: combined.data.resource_result });
  await assert.rejects(() => API.resourceWorkspace(runRef, query, savedResources), error => error.code === 'invalid_response', '信封顶层多出资源字段时整份拒绝');
}
async function unifiedGenerationContracts() {
  const raw = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures/unified_generation_http.json'), 'utf8'));
  const local = { ...window }, savedRun = raw.candidate_catalog.run_ref, savedCandidate = raw.candidate_workspace.candidate.candidate_ref;
  const names = ['resource-contract.js', 'WorkbenchFormat.js', 'WorkbenchTerms.js', 'RunGenerationContract.js', 'PointContract.js',
    'DeliveryProjectionContract.js', 'EffortProjectionContract.js', 'GanttGraph.js', 'RunCandidateAPI.js', 'RunJobAPI.js', 'RunAdoptionAPI.js',
    'PlanContract.js', 'RunCandidateControls.jsx', 'RunDecisionRecommendation.jsx', 'RunDecisionComparison.jsx'];
  const outputs = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'),
    sources: names.map(name => ({ path: name, code: fs.readFileSync(path.join(app, name), 'utf8') })) }).outputs;
  for (const output of outputs) vm.runInNewContext(output.code, { React, window: local, AbortController, setTimeout, clearTimeout, URLSearchParams });
  // The capture saved public data bodies. This harness supplies the opaque transport metadata.
  const envelope = value => ({ ok: true, schema_version: 1, data: value, warnings: [], meta: { request_ref: '1'.repeat(32),
    source: 'production', time_basis: 'factory_local', snapshot_ref: snapshot, as_of: '2026-10-15T02:00:00' } });
  const catalog = envelope(raw.candidate_catalog), workspace = envelope(raw.candidate_workspace), plan = envelope(raw.adopted_plan_workspace);
  assert.strictEqual(local.RunCandidateAPI.validateCatalog(catalog, savedRun, {}), raw.candidate_catalog);
  assert.strictEqual(local.RunCandidateAPI.validateWorkspace(workspace, savedCandidate, {}), raw.candidate_workspace);
  assert.strictEqual(local.APSPlanContract.workspace(plan, raw.adopted_plan_workspace.plan.plan_ref, {}), plan);
  const algorithm = raw.candidate_workspace.generation.algorithm;
  assert.deepEqual(algorithm.target_objectives, ['min_overdue', 'min_tardiness', 'min_changeover'], '真实 canonical JSON 往返保留保存的主目标优先顺序');
  assert.deepEqual(algorithm, raw.adopted_plan_workspace.provenance.algorithm, '真实候选和正式采用计划沿同一份共同算法元数据');
  for (const value of [workspace, plan]) {
    const wrong = clone(value), item = wrong.data.generation ? wrong.data.generation.algorithm : wrong.data.provenance.algorithm;
    item.target_objectives.reverse();
    assert.throws(() => wrong.data.generation ? local.RunCandidateAPI.validateWorkspace(wrong, savedCandidate, {})
      : local.APSPlanContract.workspace(wrong, raw.adopted_plan_workspace.plan.plan_ref, {}), undefined, '两消费者均拒绝错序算法合同');
  }
  const extra = clone(plan); extra.data.provenance.algorithm.unrecorded = true;
  assert.throws(() => local.APSPlanContract.workspace(extra, raw.adopted_plan_workspace.plan.plan_ref, {}), undefined, '新采用来源不接未声明字段');
  const metadataTree = expand(h(local.RunCandidateControls.GenerationMetadata, { value: algorithm, runRef: savedRun }));
  assert.equal(nodes(metadataTree).find(node => node.props['data-first-found-elapsed-ms'] !== undefined).props['data-first-found-elapsed-ms'], algorithm.first_found_elapsed_ms);
  assert(text(metadataTree).includes('共同优化') && text(metadataTree).includes('代表方向'));
  const identity = envelope({ candidate_ref: savedCandidate, run_ref: savedRun, label: raw.candidate_workspace.candidate.label, status: 'completed' });
  // The lightweight identity read goes through the real RunCandidateAPI.identity and APSWorkbenchTransport.
  const identityAnswers = [identity], start = network.calls.length, owner = new AbortController();
  routes['GET /api/workbench/v1/scheduling/candidates/*/identity'] = () => identityAnswers.shift();
  assert.deepEqual(clone(await local.RunCandidateAPI.identity(savedCandidate, owner.signal)), identity);
  const calls = network.calls.slice(start);
  assert.equal(calls.length, 1); assert(calls[0].path.endsWith('/candidates/' + savedCandidate + '/identity') && !calls[0].path.includes('/workspace'));
  assert.equal(calls[0].init.cache, 'no-store'); assert.equal(calls[0].init.credentials, 'same-origin');
  const badIdentity = clone(identity); badIdentity.data.candidate_ref = first; identityAnswers.push(badIdentity);
  await assert.rejects(() => local.RunCandidateAPI.identity(savedCandidate), /身份|方案/, 'identity 读取同样绑定永久候选编号');
  // Component ownership: the Workspace's identity lookup and summary read are answered on its own API module objects.
  const state = hooks(), lookups = [], summaries = [], ui = { ...local,
    APSResourceSession: { useQuery: (load, deps, enabled = true) => ({ result: enabled ? load() : null, loading: false, error: null }) },
    RunCandidateAPI: { ...local.RunCandidateAPI, identity: (reference, signal) => { lookups.push({ reference, signal }); return identity; },
      workspace: () => { throw new Error('比较入口的运行编号查找只调用轻量 identity'); } },
    RunDecisionAPI: { ...API, decisionSummary: (reference, query) => { summaries.push({ reference, query }); return null; } } };
  vm.runInNewContext(outputs.find(output => output.path === 'RunDecisionComparison.jsx').code, { React: state.React, window: ui, AbortController });
  const props = { ...workspaceDefaults, initialContext: { candidate_ref: savedCandidate } };
  state.render(() => ui.RunDecisionComparison.Workspace(props)); state.flush(); state.render(() => ui.RunDecisionComparison.Workspace(props));
  assert.equal(lookups.length, 1); assert.equal(summaries[0].reference, savedRun, '仅候选编号打开比较页由轻量身份结果取得 run_ref');
  const processRaw = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures/unified_process_http.json'), 'utf8'));
  const native = processRaw.decision_summary, nativeRun = native.run.run_ref, nativeCandidate = native.scope.selected_candidate_ref;
  assert.strictEqual(API.validateDecisionSummary(envelope(native), nativeRun, { selected_candidate_ref: nativeCandidate }), native);
  for (const [objective, process] of Object.entries(processRaw.process_by_objective)) {
    assert.strictEqual(API.processDetails(envelope(process), nativeRun, { selected_candidate_ref: nativeCandidate, objective }), process);
    assert.deepEqual(Object.keys(process.summary).sort(), ['elapsed_ms', 'first_complete_elapsed_ms', 'first_improvement_elapsed_ms', 'last_improvement_elapsed_ms'].sort());
    assert.equal(process.summary.last_improvement_elapsed_ms, null, '真实快速生成未改善，按保存事实显示');
  }
  const controlledRaw = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures/unified_process_controlled.json'), 'utf8'));
  assert.equal(controlledRaw.provenance.actual_http, false); assert.equal(controlledRaw.provenance.solver_calls, 0);
  const improved = controlledRaw.improvement, improvementQuery = { ...improved.filters,
    selected_candidate_ref: improved.scope.selected_candidate_ref, reference_candidate_ref: improved.scope.reference.candidate_ref };
  delete improvementQuery.section;
  const acceptedImprovement = API.processDetails(envelope(improved), improved.run_ref, improvementQuery);
  assert.strictEqual(acceptedImprovement, improved, '真实metrics→SharedSearch→build_shared_process→projection先经过严格公开DTO边界');
  assert.deepEqual(improved.progress.points.map(point => [point.elapsed_ms, point.flags]), [[10, ['first_valid', 'first_expected_complete']], [15, ['strict_improvement']], [100, ['final']]]);
  const badMandatory = clone(improved); badMandatory.progress.sampling.mandatory.push('strict_improvement');
  assert.throws(() => API.processDetails(envelope(badMandatory), improved.run_ref, improvementQuery), /采样/, '真实改善允许作为点标记，三个必要锚点合同保持');
  const curveState = hooks(), curve = { ...window };
  for (const output of compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'),
    sources: [{ path: 'RunDecisionProcessChart.jsx', code: fs.readFileSync(path.join(app, 'RunDecisionProcessChart.jsx'), 'utf8') }] }).outputs)
    vm.runInNewContext(output.code, { React: curveState.React, window: curve });
  const curveProps = { progress: acceptedImprovement.progress, objective: acceptedImprovement.selected_objective, scopes: acceptedImprovement.scopes,
    elapsedMs: acceptedImprovement.summary.elapsed_ms, lastImprovementElapsedMs: acceptedImprovement.summary.last_improvement_elapsed_ms };
  let curveTree; const renderCurve = () => { curveTree = curveState.render(() => expand(curve.RunDecisionProcessChart.Chart(curveProps))); };
  renderCurve(); assert.equal(nodes(curveTree).find(node => node.props['data-process-last-improvement-ms'] !== undefined).props['data-process-last-improvement-ms'], 15);
  const improvementButton = nodes(curveTree).find(node => node.type === 'button' && text(node).includes('改善阶段'));
  assert.equal(improvementButton.props.disabled, false); assert(text(improvementButton).includes('15 毫秒'));
  assert(nodes(curveTree).some(node => node.type === 'circle' && node.props['data-progress-flags'] === 'strict_improvement'), '真实15ms改善点标签显示');
  improvementButton.props.onClick(); renderCurve(); assert.equal(curveTree.props['data-process-window'], 'improvements');
  assert.equal(nodes(curveTree).filter(node => node.type === 'circle' && node.props['data-progress-flags'] === 'final').length, 0, '改善阶段采用15ms真实截止，100ms final留在全过程');
  const noGain = processRaw.process_by_objective.min_overdue;
  Object.assign(curveProps, { progress: noGain.progress, objective: noGain.selected_objective, scopes: noGain.scopes, elapsedMs: noGain.summary.elapsed_ms,
    lastImprovementElapsedMs: noGain.summary.last_improvement_elapsed_ms });
  renderCurve(); assert.equal(curveTree.props['data-process-window'], 'full'); assert(!nodes(curveTree).some(node => node.props['data-process-last-improvement-ms'] !== undefined));
  assert.equal(nodes(curveTree).find(node => node.type === 'button' && text(node).includes('改善阶段')).props.disabled, true, '真实native无改善采用null事实');
  const sampled = controlledRaw.sampled_improvement, sampledQuery = { ...sampled.filters,
    selected_candidate_ref: sampled.scope.selected_candidate_ref, reference_candidate_ref: sampled.scope.reference.candidate_ref };
  delete sampledQuery.section;
  const acceptedSampled = API.processDetails(envelope(sampled), sampled.run_ref, sampledQuery);
  assert.strictEqual(acceptedSampled, sampled); assert.equal(controlledRaw.sampled_provenance.actual_http, false);
  assert.equal(controlledRaw.sampled_provenance.decoder_calls, 0); assert(!sampled.progress.points.some(point => point.flags.includes('strict_improvement')), '实际sampler将999ms改善点和1000ms final放入同桶，保留final');
  assert.deepEqual(sampled.progress.points.map(point => point.elapsed_ms), [10, 1000]); assert.equal(sampled.summary.first_improvement_elapsed_ms, 999); assert.equal(sampled.summary.last_improvement_elapsed_ms, 999);
  Object.assign(curveProps, { progress: acceptedSampled.progress, objective: acceptedSampled.selected_objective, scopes: acceptedSampled.scopes,
    elapsedMs: acceptedSampled.summary.elapsed_ms, lastImprovementElapsedMs: acceptedSampled.summary.last_improvement_elapsed_ms });
  renderCurve(); assert.equal(nodes(curveTree).find(node => node.props['data-process-last-improvement-ms'] !== undefined).props['data-process-last-improvement-ms'], 999);
  const sampledWindow = nodes(curveTree).find(node => node.type === 'button' && text(node).includes('改善阶段'));
  assert.equal(sampledWindow.props.disabled, false); assert(text(sampledWindow).includes('999 毫秒'), '抽样省略末改善点仍显示真实保存时刻');
  sampledWindow.props.onClick(); renderCurve(); assert.equal(curveTree.props['data-process-window'], 'improvements');
  assert.equal(nodes(curveTree).filter(node => node.type === 'circle' && node.props['data-progress-flags'] === 'final').length, 0);
  const withoutInitial = { ...acceptedSampled.progress, points: acceptedSampled.progress.points.map(point => ({ ...point, flags: point.flags.filter(flag => flag !== 'first_valid') })) };
  Object.assign(curveProps, { progress: withoutInitial, objective: acceptedSampled.selected_objective, scopes: acceptedSampled.scopes,
    elapsedMs: acceptedSampled.summary.elapsed_ms, lastImprovementElapsedMs: acceptedSampled.summary.last_improvement_elapsed_ms });
  renderCurve();
  nodes(curveTree).find(node => node.type === 'select' && node.props['aria-label'] === '计算过程观察指标').props.onChange({ target: { value: 'makespan_hours' } });
  renderCurve();
  assert.equal(curveTree.props['data-process-metric'], 'makespan_hours', '缺少first_valid锚点时切换次要指标不抛错');
  // These card-count variants exercise presentation only; they reuse the captured business facts.
  for (const count of [1, 2, 3]) {
    const shown = clone(native); shown.candidates = Array.from({ length: count }, (_, index) => ({ ...clone(native.candidates[0]),
      candidate_ref: String(index + 80).padStart(48, '0'), representative_objectives: index === 0 ? ['min_overdue', 'min_tardiness'] : ['min_changeover'] }));
    const cards = expand(h(local.RunDecisionComparison.CandidateTable, { data: shown, selectedRef: shown.candidates[0].candidate_ref, referenceRef: nativeCandidate, onSelect: () => {} }));
    assert.equal(cards.props['data-unified-candidates'], count); assert.equal(nodes(cards).filter(node => node.props['data-decision-candidate']).length, count);
    assert(text(cards).includes('交期优先 · 拖期更轻') && text(cards).includes('推荐'), '合并代表方向与保存的推荐标记共同显示');
  }
  const partial = clone(native); partial.candidates[0].representative_objectives = []; partial.candidates[0].label = '算法选中的部分结果';
  const partialCards = expand(h(local.RunDecisionComparison.CandidateTable, { data: partial, onSelect: () => {} }));
  assert.equal(text(nodes(partialCards).find(node => node.props.className === 'rd-candidate-choice-heading').children[0]), '算法选中的部分结果', '未知评分的合法空代表方向保留保存名称');
  const weighted = clone(native); weighted.selection_basis.primary_objective = 'min_weighted_tardiness';
  Object.assign(weighted.candidates[0].metrics.weighted_tardiness_hours, { value: null, known_subtotal: 7, known_count: 2, unknown_count: 1, total_count: 3, state: 'partial' });
  const weightedCards = expand(h(local.RunDecisionComparison.CandidateTable, { data: weighted, onSelect: () => {} }));
  const weightedMetric = nodes(weightedCards).find(node => node.props['data-card-metric'] === 'weighted_tardiness_hours');
  assert(weightedMetric && text(weightedMetric).includes('已知加权拖期') && text(weightedMetric).includes('7'));
  const weightedText = text(weightedMetric).replace(/\s+/g, ' ');
  assert(weightedText.includes('计算时保存的批次优先级') && weightedText.includes('2 / 3') && weightedText.includes('1 批待确认'), '加权主要指标展示已知小计、保存优先级依据和覆盖范围');
  const evidence = expand(h(local.RunDecisionRecommendation.SelectionEvidence, { basis: native.selection_basis, data: native }));
  assert(text(evidence).includes('主目标') && !text(evidence).includes('健康比较原方案'), '新版推荐展示真实业务规则');
  assert(nodes(evidence).some(node => node.type === 'reference' && (node.props.value === native.selection_basis.selected_candidate_ref || node.props.entries && Object.values(node.props.entries).includes(native.selection_basis.selected_candidate_ref))), '推荐详情保留永久编号');
  const compareState = hooks(), compareQueries = [], returns = [], display = clone(native), fullDisplay = clone(processRaw.decision_overview);
  assert.strictEqual(API.validateDecision(envelope(processRaw.decision_overview), nativeRun, { selected_candidate_ref: nativeCandidate }), processRaw.decision_overview);
  for (const container of [display, fullDisplay]) container.candidates.push(...[first, third].map((reference, index) => ({ ...clone(container.candidates[0]), candidate_ref: reference,
    label: ['拖期更轻代表方案', '切换更少代表方案'][index], selection_role: [], representative_objectives: [['min_tardiness'], ['min_changeover']][index] })));
  const compareReads = { ...API }, compare = { ...local, RunDecisionAPI: compareReads, RunDecisionProcess: { Pane: 'process-pane' }, RunDecisionResources: { Pane: 'resource-pane' },
    RunDecisionDetails: { Pane: 'detail-pane' }, RunDecisionCompletion: { Pane: 'completion-pane' },
    APSResourceSession: { useQuery: (load, deps, enabled = true) => ({ result: enabled ? load() : null, loading: false, error: null }) } };
  vm.runInNewContext(outputs.find(output => output.path === 'RunDecisionComparison.jsx').code, { React: compareState.React, window: compare, AbortController });
  const readDisplay = (reference, q, full = false) => { compareQueries.push(clone(q)); const value = clone(full ? fullDisplay : display);
    value.scope.selected_candidate_ref = q.selected_candidate_ref || nativeCandidate;
    value.scope.resource_view = q.resource_view; value.scope.comparison_mode = q.comparison_mode;
    value.scope.reference.candidate_ref = q.reference_candidate_ref || nativeCandidate; return envelope(value); };
  const compareProps = { initialContext: { run_ref: nativeRun, candidate_ref: nativeCandidate, reference_candidate_ref: nativeCandidate, comparison_tab: 'process',
      detail_queries: { process: { objective: 'min_changeover', process_candidate_ref: first, page: 2, size: 20, snapshot_ref: snapshot } } },
    onNavigate: (page, context) => returns.push({ page, context }), renderAdoption: reference => h('adoption', { candidateRef: reference }), renderTrial: () => null, runHistoryReturn: workspaceDefaults.runHistoryReturn };
  Object.assign(compareReads, { decisionSummary: readDisplay, resourceWorkspace: (reference, q, saved) => resourceWorkspaceFixture(readDisplay(reference, q), saved), decision: (reference, q) => readDisplay(reference, q, true) });
  let compareTree, compareRaw;
  const renderCompare = () => { compareRaw = compareState.render(() => compare.RunDecisionComparison.Workspace(compareProps)); compareTree = expand(compareRaw); compareState.flush(); };
  const processLeaf = () => nodes(compareTree).find(node => node.type === 'process-pane').props;
  renderCompare(); assert.equal(processLeaf().query.process_candidate_ref, first); assert.equal(processLeaf().query.objective, 'min_changeover'); assert.equal(processLeaf().query.page, 2, '新版甘特返回保留独立过程来源页');
  processLeaf().onQuery({ ...processLeaf().query, objective: 'min_tardiness', page: 1 }); renderCompare();
  assert.equal(compareQueries.at(-1).selected_candidate_ref, nativeCandidate); assert.equal(compareQueries.at(-1).reference_candidate_ref, nativeCandidate);
  nodes(nodes(compareTree).find(node => node.props['data-decision-candidate'] === third)).find(node => node.props.className === 'rd-candidate-choice').props.onClick(); renderCompare();
  assert.equal(compareQueries.at(-1).selected_candidate_ref, third); assert.equal(processLeaf().query.process_candidate_ref, first); assert.equal(processLeaf().query.objective, 'min_tardiness');
  nodes(compareTree).find(node => node.props['aria-label'] === '候选比较基准').props.onChange({ target: { value: first } }); renderCompare();
  nodes(compareTree).find(node => node.props.id === 'rd-tab-resources').props.onClick(); renderCompare();
  nodes(compareTree).find(node => node.type === 'resource-pane').props.onView('full_candidate'); renderCompare();
  assert.equal(compareQueries.at(-1).selected_candidate_ref, third); assert.equal(compareQueries.at(-1).reference_candidate_ref, first); assert.equal(processLeaf().query.objective, 'min_tardiness');
  nodes(compareTree).find(node => node.type === 'button' && text(node) === '看甘特').props.onClick();
  assert.equal(returns.at(-1).context.candidate_ref, third); assert.equal(returns.at(-1).context.return_decision_context.detail_queries.process.process_candidate_ref, first);
  assert.equal(returns.at(-1).context.return_decision_context.detail_queries.process.objective, 'min_tardiness'); assert.equal(nodes(compareTree).find(node => node.type === 'adoption').props.candidateRef, third, '采用对象继续绑定当前查看方案');
  nodes(compareTree).find(node => node.props.className === 'rd-official rd-data-source').props.onToggle({ currentTarget: { open: true } }); renderCompare();
  nodes(compareRaw).find(node => node.type === compare.RunDecisionComparison.CandidateFacts).props.onProcess(display.candidates[0]); renderCompare();
  assert.equal(compareQueries.at(-1).selected_candidate_ref, third); assert.equal(processLeaf().query.process_candidate_ref, nativeCandidate, '候选保存依据定位来源保持查看和采用对象');
  const processState = hooks(), processCalls = [], pane = { ...window, RunDecisionAPI: { ...API, process: (reference, q) => { processCalls.push(clone(q)); return envelope(processRaw.process_by_objective[q.objective || native.selection_basis.primary_objective]); } },
    APSResourceSession: { useQuery: (load, deps, enabled = true) => ({ result: enabled ? load() : null, loading: false, error: null }) } };
  for (const name of ['RunDecisionProcessChart.jsx', 'RunDecisionProcess.jsx']) for (const output of compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'),
    sources: [{ path: name, code: fs.readFileSync(path.join(app, name), 'utf8') }] }).outputs) vm.runInNewContext(output.code, { React: processState.React, window: pane, AbortController });
  const paneProps = { result: envelope(native), query: {}, enabled: true, onQuery: value => { paneProps.query = value; } };
  let paneTree; const renderProcess = () => { paneTree = processState.render(() => expand(pane.RunDecisionProcess.Pane(paneProps))); processState.flush(); };
  renderProcess(); nodes(paneTree).find(node => node.props['aria-label'] === '优化方向').props.onChange({ target: { value: 'min_changeover' } }); renderProcess();
  assert.equal(processCalls.at(-1).objective, 'min_changeover'); assert.equal(processCalls.at(-1).selected_candidate_ref, nativeCandidate); assert.equal(processCalls.at(-1).process_candidate_ref, nativeCandidate);
  assert.equal(nodes(paneTree).filter(node => node.props['data-unified-count']).length, 6, '共同真实计数只显示一次');
  for (const [key, label] of [['skipped_requests', '跳过执行次数'], ['request_count', '不同计算请求']]) {
    const countRow = nodes(paneTree).find(node => node.props['data-unified-count'] === key);
    assert.equal(text(nodes(countRow).find(node => node.type === 'dt')), label);
    assert.equal(text(nodes(countRow).find(node => node.type === 'dd')), String(processRaw.process_by_objective.min_changeover.counts[key]), '统计名称同步保留保存值');
  }
  assert(text(paneTree).includes('本次预算内未探索此方向') && nodes(paneTree).filter(node => node.type === 'circle' && node.props['data-progress-event-index'] !== undefined).length > 0, '真实未探索方向仍有共同初始评价点');
  const exportState = hooks(), exportWindow = { ...window };
  vm.runInNewContext(outputs.find(output => output.path === 'RunDecisionComparison.jsx').code, { React: exportState.React, window: exportWindow, AbortController });
  let exportTree; const renderExport = () => { exportTree = exportState.render(() => expand(exportWindow.RunDecisionComparison.Export({
    result: envelope(noGain), initialSection: 'process', filterQuery: {} }))); };
  renderExport(); nodes(exportTree).find(node => node.type === 'button' && node.props.icon === 'download').props.onClick(); renderExport();
  assert(text(exportTree).includes('当前方向曲线'));
  nodes(exportTree).find(node => node.props['aria-label'] === '方案对比导出内容').props.onChange({ target: { value: 'all' } }); renderExport();
  assert(text(exportTree).includes('本轮全部优化目标') && !text(exportTree).includes('当前方向曲线'), '整份导出的说明准确包含全部目标，单张过程说明对应当前方向');
  console.log(JSON.stringify({ u4_actual_public_generation: { candidate_catalog: true, candidate_workspace: true, adopted_plan_workspace: true,
    target_objectives: algorithm.target_objectives, algorithm_metadata_equal: true, identity_reads: calls.length, decision_summary: true, process_directions: 3,
    real_improvement_ms: improved.summary.last_improvement_elapsed_ms, sampled_improvement_ms: sampled.summary.last_improvement_elapsed_ms } }));
}
async function adoptionContextContracts() {
  const state = hooks(), values = new Map(), listeners = new Map(), calls = [];
  let random = 0;
  const storage = { getItem: key => values.has(key) ? values.get(key) : null, setItem: (key, value) => values.set(key, value), removeItem: key => values.delete(key) };
  const local = { ...window, localStorage: storage, crypto: { getRandomValues(bytes) { bytes.fill(++random); return bytes; } },
    WorkbenchHandlerMemory: { read: () => ({ value: '经办人' }), write() {}, useHint: () => '' },
    addEventListener(type, fn) { if (!listeners.has(type)) listeners.set(type, new Set()); listeners.get(type).add(fn); },
    removeEventListener(type, fn) { if (listeners.has(type)) listeners.get(type).delete(fn); },
    dispatchEvent(event) { for (const fn of listeners.get(event.type) || []) fn(event); } };
  class CustomEvent { constructor(type, options) { this.type = type; this.detail = options.detail; } }
  const outputs = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'),
    sources: ['RunAdoptionAPI.js', 'RunAdoptionControls.jsx', 'RunAdoptionAction.jsx'].map(name => ({ path: name, code: fs.readFileSync(path.join(app, name), 'utf8') })) }).outputs;
  const context = vm.createContext({ React: state.React, window: local, AbortController, DOMException, CustomEvent, URLSearchParams, setTimeout, clearTimeout });
  browser(context, network); loadTransport(context);
  outputs.forEach(output => vm.runInContext(output.code, context, { filename: output.path }));
  const A = local.RunAdoptionAPI, oldContext = JSON.stringify({ database_scope: '/old.db', successful_restores: [] }),
    newContext = JSON.stringify({ database_scope: '/current.db', successful_restores: ['e'.repeat(32)] });
  const summary = { candidate_ref: first, run_ref: runRef, baseline: { plan_ref: planRef, version: 7 }, task_count: 3, scope_complete: true },
    input = { confirm: true, reason: '核对后采用', declared_operator: '经办人' };
  const status = (intent, resolution) => ({ ok: true, result: 'not_recorded', request_key: intent.request_key,
    may_be_in_flight: resolution === 'unresolved', resolution, data_context_ref: newContext,
    message: resolution === 'context_replaced' ? '数据库已切换或恢复，请切回原来源查询，或结束旧来源记录。' : '采用结果仍待确认。' });
  const receipt = intent => ({ ok: true, result: 'committed', receipt_ref: '9'.repeat(32), replayed: true, warnings: [],
    data: { candidate_ref: intent.candidate_ref, run_ref: intent.preview.run_ref, row_count: intent.preview.task_count,
      official_plan: { plan_ref: '8'.repeat(48), version: 8, kind: 'official', is_current_official: true, display_name: '正式计划 v8',
        source_run_ref: intent.preview.run_ref, baseline_ref: intent.preview.baseline.plan_ref, completeness: 'complete',
        capabilities: { view: true, edit_draft: false, adopt: false, report_actual: true }, blocked_reasons: [] } } });
  const preview = candidateRef => ({ ok: true, schema_version: 1, data: { ...summary, candidate_ref: candidateRef, data_context_ref: newContext,
    validation: { status: 'valid', can_adopt: true, issues: [] }, write_context: { write_token: 'w'.repeat(32), expires_at: '2026-10-20T10:00:00',
      capabilities: { 'scheduling.candidate.adopt': true }, blocked_reasons: [] } },
    warnings: [], meta: { request_ref: '1'.repeat(32), source: 'production', time_basis: 'factory_local', snapshot_ref: snapshot, as_of: '2026-10-20T09:00:00' } });
  // Lookups and previews go through the real RunAdoptionAPI and APSWorkbenchTransport; only the network answer comes from these routes.
  let lookupAnswer = null, previews = 0;
  routes['GET /api/workbench/v1/scheduling/candidates/*/adoption-commands/*'] = call => { calls.push(call.path.split('/').pop()); return lookupAnswer; };
  routes['POST /api/workbench/v1/scheduling/candidates/*/adopt-preview'] = call => { previews++; return preview(call.path.split('/').at(-2)); };
  // Every saved intent carries its data source (schema_version 2); records without it are no longer readable.
  assert.throws(() => A.pending().begin(summary, input, null), undefined, '没有数据来源的采用意图不能开始');
  const modern = A.pending().begin({ ...summary, data_context_ref: oldContext }, input, null);
  assert.equal(modern.schema_version, 2); assert.equal(modern.data_context_ref, oldContext); assert(A.validIntent(modern));
  for (const legacy of [{ ...modern, schema_version: 1 }, (({ data_context_ref, ...rest }) => ({ ...rest, schema_version: 1 }))(modern), { ...modern, data_context_ref: 'd'.repeat(64) }])
    assert.equal(A.validIntent(legacy), false, '旧版或散列来源的采用意图不再可读');
  storage.setItem(A.PENDING_KEY, JSON.stringify({ ...modern, schema_version: 1 }));
  assert.throws(() => A.pending().read(), /不完整/, '本机存着旧版采用记录时拦下新采用'); storage.setItem(A.PENDING_KEY, JSON.stringify(modern));
  assert(!A.validIntent({ ...modern, data_context_ref: JSON.stringify({ database_scope: '/old.db', successful_restores: [true] }) }));
  lookupAnswer = status(modern, 'context_replaced'); const lookupStart = network.calls.length, proof = await A.lookup(modern);
  assert.equal(proof.resolution, 'context_replaced');
  const lookupRequest = network.calls[lookupStart];
  assert.equal(lookupRequest.path, '/api/workbench/v1/scheduling/candidates/' + first + '/adoption-commands/' + modern.request_key);
  assert.equal(lookupRequest.query.run_ref, runRef); assert.equal(lookupRequest.query.data_context_ref, oldContext); assert.equal(lookupRequest.method, 'GET');
  lookupAnswer = status(modern, 'unresolved'); assert.equal(await A.lookup(modern), null, 'An in-flight record remains protected');
  assert.throws(() => A.pending().dismissReplaced(modern, clone(proof)), /不能丢弃/, 'A copied or forged proof cannot authorize dismissal');
  const changed = { ...modern, input: { ...modern.input, reason: '另一个提交内容' } };
  storage.setItem(A.PENDING_KEY, JSON.stringify(changed));
  assert.throws(() => A.pending().dismissReplaced(changed, proof), /不能丢弃/, 'Proofs bind the entire original intent, not just its request key');
  assert.throws(() => A.pending().dismissReplaced(modern, proof), /记录已变化/, 'CAS preserves a newer stored record');
  assert.deepEqual(clone(A.pending().read()), clone(changed));
  storage.setItem(A.PENDING_KEY, JSON.stringify(modern));
  const blockedStorage = { ...storage, removeItem() { throw new Error('disk full'); } };
  assert.throws(() => A.pending(blockedStorage).dismissReplaced(modern, proof), /存不下/);
  assert.equal(A.pending().read().request_key, modern.request_key);
  A.pending().dismissReplaced(clone(modern), proof); assert.equal(A.pending().read(), null);
  lookupAnswer = receipt(modern);
  assert.strictEqual((await A.lookup(modern)).data.candidate_ref, first, 'Committed results from another candidate remain recoverable');
  storage.setItem(A.PENDING_KEY, JSON.stringify(modern)); calls.length = 0;
  let lookupValue = status(modern, 'context_replaced');
  routes['GET /api/workbench/v1/scheduling/candidates/*/adoption-commands/*'] = call => { calls.push(call.path.split('/').pop()); return lookupValue; };
  const props = { candidateRef: third, candidateCatalog: data.candidates };
  let tree;
  const render = () => { tree = state.render(() => { const session = local.RunAdoptionAction(props); return session.type(session.props); }); state.flush(); return tree; };
  const settle = async () => { for (let index = 0; index < 3; index++) { render(); await turns(); } return render(); };
  const dialog = () => nodes(tree).find(node => node.type === local.RunAdoptionControls.Dialog);
  const footer = () => nodes(expand(dialog().type(dialog().props).props.footer));
  await settle(); nodes(tree).find(node => node.type === 'button').props.onClick(); await settle();
  assert(dialog().props.notice.includes('另一个候选方案') && dialog().props.notice.includes('数据库已切换或恢复'),
    'Cross-candidate notices do not hide the source-replacement explanation');
  assert(footer().some(node => node.type === 'button' && text(node) === '结束旧来源待确认记录'));
  let resolveLookup;
  lookupValue = new Promise(resolve => { resolveLookup = resolve; });
  dialog().props.onLookup(); render(); render();
  assert.equal(dialog().props.replacedInfo, null, 'Starting a new query invalidates the previous dismissal proof');
  resolveLookup(status(modern, 'unresolved')); await settle();
  assert.equal(dialog().props.replacedInfo, null); assert(!footer().some(node => text(node) === '结束旧来源待确认记录'));
  assert.equal(A.pending().read().request_key, modern.request_key);
  lookupValue = status(modern, 'context_replaced'); dialog().props.onLookup(); await settle();
  const next = { ...modern, request_key: 'adoption-' + 'f'.repeat(48), candidate_ref: third, preview: { ...modern.preview, candidate_ref: third } };
  lookupValue = status(next, 'unresolved'); storage.setItem(A.PENDING_KEY, JSON.stringify(next));
  local.dispatchEvent(new CustomEvent(A.EVENT, { detail: next })); render(); render();
  assert.equal(dialog().props.replacedInfo, null, 'A storage event cannot transfer source-replacement proof to another pending record');
  await settle(); assert(!dialog().props.notice.includes('数据库已切换或恢复'));
  lookupValue = receipt(next); dialog().props.onLookup(); await settle();
  assert(dialog().props.result); assert.equal(dialog().props.replacedInfo, null);
  dialog().props.onFinish(); await settle(); assert.equal(A.pending().read(), null);
  storage.setItem(A.PENDING_KEY, JSON.stringify(modern)); lookupValue = status(modern, 'context_replaced');
  local.dispatchEvent(new CustomEvent(A.EVENT, { detail: modern })); await settle();
  nodes(tree).find(node => node.type === 'button').props.onClick(); await settle();
  nodes(expand(dialog().type(dialog().props).props.footer)).find(node => node.type === 'button' && text(node) === '结束旧来源待确认记录').props.onClick();
  await settle(); assert.equal(A.pending().read(), null); assert.equal(dialog(), undefined);
  nodes(tree).find(node => node.type === 'button').props.onClick(); await settle();
  assert.equal(previews, 1); assert.equal(dialog().props.preview.candidate_ref, third, 'Ending the proven old-source record restores current-candidate actions');
  state.unmount();
}
async function dashboardReadContracts() {
  // Dashboard reads go through the real DashboardContract / DashboardAnalysisAPI and an APSWorkbenchTransport bound to this context's timers.
  const state = hooks(), timers = new Map(), dashboardRoutes = {}, requests = routeFetch(dashboardRoutes);
  let timerId = 0;
  const local = { ...window }, context = vm.createContext({ window: local, React: state.React, AbortController, DOMException, URLSearchParams,
    setTimeout(fn, delay) { const id = ++timerId; timers.set(id, { fn, delay }); return id; }, clearTimeout(id) { timers.delete(id); } });
  browser(context, requests); const T = loadTransport(context);
  const outputs = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'),
    sources: ['resource-session.js', 'DashboardContract.js', 'DashboardAnalysisAPI.js'].map(name => ({ path: name, code: fs.readFileSync(path.join(app, name), 'utf8') })) }).outputs;
  outputs.forEach(output => vm.runInContext(output.code, context, { filename: output.path }));
  const C = local.DashboardContract, Q = local.DashboardAnalysisAPI, LIST = 'GET /api/workbench/v1/dashboard', ANALYSIS = 'GET /api/workbench/v1/dashboard/analysis';
  for (const analysis of [false, true]) {
    dashboardRoutes[analysis ? ANALYSIS : LIST] = () => new Promise(() => {});
    const read = signal => analysis ? Q.read(null, signal, {}) : C.list(C.scope({}), signal);
    const waiting = read();
    assert.equal(timers.size, 1); const timer = [...timers.values()][0]; assert.equal(timer.delay, 60000);
    timer.fn();
    await assert.rejects(waiting, error => error.code === 'timeout' && error.message === '值班台读取超时（超过 60 秒），请重试或缩小筛选范围。');
    assert.equal(timers.size, 0);
    const controller = new AbortController(), cancelled = read(controller.signal); controller.abort();
    await assert.rejects(cancelled, error => error.name === 'AbortError' && error.code !== 'timeout', 'An external abort is not misreported as a timeout');
    assert.equal(timers.size, 0);
    dashboardRoutes[analysis ? ANALYSIS : LIST] = () => { throw new Error('offline'); };
    await assert.rejects(read(), error => error.committed === false && error.status === null && error.message !== 'offline', '断网按传输层的读取失败报告，不外泄底层错误');
    delete dashboardRoutes[analysis ? ANALYSIS : LIST];
  }
  const refusal = failure('snapshot_stale', '快照已变化。');
  dashboardRoutes[LIST] = () => json(refusal, 409);
  await assert.rejects(C.list(C.scope({})), error => error.code === 'snapshot_stale' && T.rejected(error), 'Business rejection identity survives the timeout catch');
  const lane = requests.calls.at(-1).headers['X-Workbench-Read-Lane'];
  assert.match(lane, /^dashboard-list:[A-Za-z0-9-]+$/);
  await assert.rejects(C.list(C.scope({})));
  assert.equal(requests.calls.at(-1).headers['X-Workbench-Read-Lane'], lane, 'The page lane stays the same for every list read');
  dashboardRoutes['GET /api/workbench/v1/dashboard/items/*'] = () => json(refusal, 409);
  await assert.rejects(C.detail(first, C.scope({}), undefined), error => T.rejected(error));
  assert.equal(requests.calls.at(-1).headers['X-Workbench-Read-Lane'], undefined, 'Detail and history reads never replace the list lane');
  dashboardRoutes['POST /api/workbench/v1/dashboard/items/*/*'] = () => json(refusal, 409);
  await assert.rejects(C.command({ item_ref: first, action: 'transition', request_key: 'dashboard-' + first, input: {} }, 'token'), error => T.rejected(error));
  assert.equal(requests.calls.at(-1).headers['X-Workbench-Read-Lane'], undefined);
  assert.equal(requests.calls.at(-1).headers['Content-Type'], 'application/json');
  const superseded = failure('request_superseded', 'replaced');
  dashboardRoutes[LIST] = () => json(superseded, 499);
  await assert.rejects(C.list(C.scope({})), error => error.name === 'AbortError' && !T.rejected(error));
  let resolveOld, version = 0;
  dashboardRoutes[LIST] = () => new Promise(resolve => { resolveOld = resolve; });
  const render = () => state.render(() => local.APSResourceSession.useQuery(signal => version === 0 ? C.list(C.scope({}), signal) : Promise.resolve('latest'), [version]));
  render(); state.flush(); await turns(); version = 1; render(); state.flush(); await turns();
  resolveOld(json(superseded, 499)); await turns();
  const current = render(); assert.equal(current.result, 'latest'); assert.equal(current.error, null, 'A superseded old read cannot overwrite the current query');
  state.unmount(); assert.equal(timers.size, 0);
}
async function main() {
  comparisonHeaderContracts(schedulingNavigationContracts());
  detailContracts(); referenceContracts(); recommendationContracts(); await transportContracts(); await workspaceContracts(); await paneContracts(); await completionContracts();
  await processPaneContracts(); await processTransportContracts(); await unifiedGenerationContracts();
  await adoptionContextContracts(); await dashboardReadContracts();
  console.log('decision comparison contract: unified candidates/formal scope, business-objective recommendation/completion, unified process read/export, single-leaf paging/export, verified curve segments, cancellation and original-viewer gantt return passed');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
