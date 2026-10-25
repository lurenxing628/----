'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..'), app = path.join(root, 'frontend/workbench/app');
const runRef = 'a'.repeat(48), first = 'b'.repeat(48), recommended = 'c'.repeat(48), third = 'd'.repeat(48);
const snapshot = 's'.repeat(32), range_start = '2026-10-01T00:00:00', range_end = '2026-10-05T00:00:00';
const coreMetricKeys = ['expected_operation_count', 'scheduled_operation_count', 'unplanned_operation_count', 'deferred_operation_count', 'overdue_count', 'total_tardiness_hours', 'makespan_hours', 'weighted_tardiness_hours', 'elapsed_seconds', 'changeover_count', 'machine_used_count', 'operator_used_count', 'machine_busy_hours_total', 'operator_busy_hours_total', 'machine_util_avg', 'operator_util_avg'];
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
const candidates = [first, recommended, third].map((candidate_ref, index) => ({ candidate_ref, label: ['原算法', '重点工序优先', '均衡候选'][index], kind: index === 0 ? 'baseline' : 'candidate', status: 'completed', persisted_status: 'completed', completeness: 'complete',
  selection_role: index === 0 ? ['algorithm_baseline', 'health_reference'] : index === 1 ? ['recommended'] : ['raw_score_best'],
  coverage: { search: { completed_count: 3, failed_count: 0, skipped_count: 0, total_count: 3 }, schedulable: { scheduled_count: 3, expected_count: 3, missing_count: 0, deferred_count: 1 }, delivery: { complete_batch_count: 1, batch_count: 2, deferred_batch_count: 1 } },
  metrics: Object.fromEntries(definitions.map(row => [row.key, { ...metric }])), deltas: Object.fromEntries(definitions.map(row => [row.key, { ...delta }])) }));
const basis = { selected_candidate_ref: recommended, raw_score_best_candidate_ref: third, health_reference_candidate_ref: first, selection_policy: 'balanced', reason_code: 'balanced_health', overdue_tolerance_count: 0, tardiness_tolerance_ratio: 0.1,
  evidence_state: 'partial', selection_evidence_version: null, decision_evidence: null, health_decision_evidence: null,
  explanation: { headline: '按本次保存的交期与关键链健康依据选择。', entries: [
    { key: 'raw', label: '目标最优候选', text: '均衡候选', state: 'complete', unit: '', reference_value: null, selected_value: null, value: null, limit: null, tolerance: null, source: 'saved_selection', scope: 'candidate_search' },
    { key: 'health', label: '健康比较原方案', text: '原算法；实际健康改善与当时接受的交期差额已保存。', state: 'partial', unit: '小时', reference_value: 3, selected_value: 2, value: -1, limit: 3.3, tolerance: 0.1, source: 'saved_health', scope: 'candidate_search' },
    { key: 'tie', label: '目标指标并列', text: '按完整评分、原算法优先与计算顺序裁决。', state: 'complete', unit: '', reference_value: null, selected_value: null, value: null, limit: null, tolerance: null, source: 'saved_tiebreak', scope: 'candidate_search' },
    { key: 'reuse', label: '等价复用', text: '本候选复用同次原算法安排，策略记录保留。', state: 'complete', unit: '', reference_value: null, selected_value: null, value: null, limit: null, tolerance: null, source: 'saved_strategy', scope: 'candidate_search' }
  ], issues: [{ code: 'historical_health_levels_missing', message: '旧记录未保存未舍入的健康分量，两侧具体值待补齐。' }] } };
basis.explanation.entries.forEach(entry => { entry.tolerance_unit = entry.unit; });
basis.explanation.entries.push({ key: 'tolerance_total_tardiness_hours', label: '总拖期容差', text: '实际检查关键链候选，相对目标评分最优参考；增加1小时在保存的10%比例限制内。', state: 'complete', unit: '小时', tolerance_unit: '%', reference_value: 10, selected_value: 11, value: 1, limit: 11, tolerance: 0.1, source: 'saved_selection', scope: 'fixed_algorithm_selection' });
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
const data = { run: { run_ref: runRef, accepted_at: range_start, finished_at: range_end }, scope: { run_ref: runRef, comparison_mode: 'candidates', resource_view: 'selected_batches', resource_refs: { machine: [], operator: [] }, selected_candidate_ref: third, reference: { kind: 'candidate', candidate_ref: first }, reference_state: 'available', range_start, range_end, batch_refs: ['e'.repeat(48)], operation_refs: ['f'.repeat(48)] }, candidates, metric_definitions: definitions, metric_version: 'decision-preparation-v4', catalog_complete: true,
  baseline: { kind: 'candidate', candidate_ref: first, baseline_ref: null, version: null, label: '原算法', state: 'available', source_candidate_ref: null },
  completion_groups: [{ group_index: 1, source_available: true, candidate_refs: [first, recommended, third], complete_batch_count: 1, sample_complete_batch_refs: ['e'.repeat(48)] }],
  recommendation: { recommendation_version: 'decision-recommendation-v1', candidate_ref: recommended, viewed_candidate_ref: third, state: 'available', recommendation_type: 'schedulable_scope', headline: '本次应排工序已安排，待料工序继续暂缓。',
    axes: { algorithm: { state: 'selected', reason_code: basis.reason_code, evidence_state: basis.evidence_state }, completion: { search: candidates[1].coverage.search, schedulable: candidates[1].coverage.schedulable, delivery: completionScope }, preflight: { state: 'not_checked', source: 'existing_adoption_preview' } }, completion_scope: completionScope,
    current_comparison: { state: 'available', candidate_ref: recommended, viewed_candidate_ref: third, reference: { kind: 'candidate', candidate_ref: first }, benefits: allDifferences.filter(row => row.direction === 'better').slice(0, 3), costs: allDifferences.filter(row => row.direction === 'worse').slice(0, 3), all_differences: allDifferences,
      common_completed_delivery: { scope: 'common_completed_batches', state: 'complete', batch_count: 1, sample_batch_refs: ['e'.repeat(48)], before: { total_tardiness_hours: 3 }, after: { total_tardiness_hours: 2 }, delay_delta_hours: -1, overdue_delta_count: -1 } } }, selection_basis: basis };
data.baseline.metrics = JSON.parse(JSON.stringify(candidates[0].metrics)); data.baseline.coverage = JSON.parse(JSON.stringify(candidates[0].coverage));
data.difference_summary = { scope: 'full_admission', items: ['overdue_count', 'total_tardiness_hours', 'makespan_hours'].map(key => ({ ...definitions.find(row => row.key === key), ...delta, reference_coverage: { ...metric }, selected_coverage: { ...metric } })) };
const payload = { ok: true, schema_version: 1, data, warnings: [], meta: { request_ref: '1'.repeat(32), source: 'production', time_basis: 'factory_local', snapshot_ref: snapshot, as_of: range_end } };
const h = (type, props, ...children) => ({ type, props: props || {}, children: children.flat(Infinity).filter(value => value !== null && value !== false && value !== undefined) });
const writes = [], navigation = [], remembered = [];
const React = { createElement: h, Fragment: 'fragment', useId: () => 'process-chart', useMemo: fn => fn(), useState: initial => { let value = typeof initial === 'function' ? initial() : initial; return [value, update => { value = typeof update === 'function' ? update(value) : update; writes.push(value); }]; }, useRef: initial => ({ current: initial }), useEffect: () => {}, useReducer: () => [0, () => {}] };
const window = { ResourceControls: { Button: 'button', Modal: 'modal' }, WorkbenchReference: 'reference', PointContract: {},
  RunCandidateControls: { Button: 'button', Pager: 'pager', Status: 'candidate-status', ErrorBox: 'error-box', Reasons: 'reasons' }, RunCandidateModel: { number: String, timeLabel: value => value || '未记录' },
  WorkbenchPageContext: { useSnapshot: value => remembered.push(value) }, WorkbenchCaption: { useCaption: () => {} },
  APSResourceSession: { useQuery: (load, deps, enabled = true) => ({ result: enabled ? load() : null, loading: false, error: null }) }, RunCandidateAnalysis: {}, RunDecisionDetails: { Pane: 'detail-pane' } };
const files = ['WorkbenchFormat.js', 'WorkbenchTerms.js', 'resource-contract.js', 'PointContract.js', 'DeliveryProjectionContract.js', 'RunGenerationContract.js', 'RunCandidateAPI.js', 'RunBaselineAPI.js', 'RecommendationContract.js', 'EffortProjectionContract.js', 'RunDecisionAPI.js', 'RunDecisionRecommendation.jsx', 'RunDecisionComparison.jsx', 'RunDecisionCompletion.jsx', 'RunDecisionProcessChart.jsx', 'RunDecisionProcess.jsx'];
const built = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources: files.map(name => ({ path: name, code: fs.readFileSync(path.join(app, name), 'utf8') })) });
for (const file of built.outputs) vm.runInNewContext(file.code, { React, window, AbortController, setTimeout, clearTimeout, URLSearchParams });
const clone = value => JSON.parse(JSON.stringify(value));
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
function resourceWorkspaceFixture(value, saved = {}) {
  return { ...value, resource_query: API.resourceFilters(API.savedResourceView(API.resourceFilters(saved), value.data.scope.resource_refs, value.data.scope)),
    resource_result: { ok: false, committed: false, status: 409, error: { code: 'snapshot_stale', message: '资源快照已变化，请刷新资源影响。', fields: [], retryable: false, request_ref: '1'.repeat(32) } } };
}
const query = { selected_candidate_ref: third, reference_candidate_ref: first, range_start, range_end };
assert.strictEqual(API.decision(payload, runRef, query), data);
const wrongRun = clone(payload); wrongRun.data.run.run_ref = third;
assert.throws(() => API.decision(wrongRun, runRef, query), /排产记录/);
const wrongReference = clone(payload); wrongReference.data.scope.reference.candidate_ref = third;
assert.throws(() => API.decision(wrongReference, runRef, query), /基准/);
const wrongSelected = clone(payload); wrongSelected.data.scope.selected_candidate_ref = recommended;
assert.throws(() => API.decision(wrongSelected, runRef, query), /查看方案/);
const table = expand(h(D.CandidateTable, { data, selectedRef: third, referenceRef: first, onSelect: row => writes.push(row.candidate_ref), onReference: row => writes.push(row.candidate_ref), busy: false }));
assert.equal(nodes(table).filter(node => node.props['data-decision-candidate']).length, 3, '全部候选始终进入真实方案卡片');
assert.equal(nodes(table).filter(node => node.props.className === 'rd-candidate-choice' && node.props['aria-pressed']).length, 1);
assert(!text(table).includes('正在查看') && !nodes(table).some(node => node.type === 'candidate-status'), '选中由aria与外框表达，完成候选卡省去重复成功状态');
const baselineCard = nodes(table).find(node => node.props['data-decision-candidate'] === first);
assert(text(baselineCard).includes('对照'));
const unavailableCards = clone(data);
for (const [index, status] of [[0, 'failed'], [2, 'skipped']]) { unavailableCards.candidates[index].persisted_status = status; unavailableCards.candidates[index].status = status; }
const actualCards = expand(h(D.CandidateTable, { data: unavailableCards, selectedRef: third, referenceRef: first, onSelect: row => writes.push(row), onReference: () => {}, busy: false }));
for (const index of [0, 2]) { const card = nodes(actualCards).find(node => node.props['data-decision-candidate'] === unavailableCards.candidates[index].candidate_ref), choice = nodes(card).find(node => node.props.className === 'rd-candidate-choice'); assert.equal(choice.props.disabled, false); choice.props.onClick(); assert.strictEqual(writes.at(-1), unavailableCards.candidates[index], '失败、跳过候选仍查看真实候选身份'); }
const reusedData = clone(data), reused = reusedData.candidates[2], origin = reusedData.candidates[0];
reused.equivalent_source_ref = origin.candidate_ref;
reused.source = { algo_mode: 'critical', used_strategy: 'priority-then-due', dispatch_mode: 'adaptive', dispatch_rule: 'SPT' };
origin.source = { algo_mode: 'baseline', used_strategy: 'baseline-due-first', dispatch_mode: 'stable', dispatch_rule: 'EDD' };
const savedReuse = clone(reused), savedOrigin = clone(origin);
const reuseTable = expand(h(D.CandidateTable, { data: reusedData, selectedRef: third, referenceRef: first, onSelect: row => writes.push(row), onReference: row => writes.push(row.candidate_ref), busy: false }));
const reuseRow = nodes(reuseTable).find(row => row.props['data-decision-candidate'] === third), reuseFacts = expand(h(D.CandidateFacts, { data: reusedData, candidate: reused })), reuseDetails = nodes(reuseFacts).find(row => row.type === 'details' && row.props.className.includes('rd-candidate-reuse'));
assert(reuseDetails && !reuseDetails.props.open && visibleText(reuseDetails).includes('复用来源与策略记录'), '当前候选完整依据保留键盘可展开的复用记录入口');
for (const key of ['algo_mode', 'used_strategy', 'dispatch_mode', 'dispatch_rule']) {
  const values = nodes(reuseDetails).filter(row => row.props['data-reuse-field'] === key).map(text);
  assert(values[0].includes(reused.source[key]) && values[1].includes(origin.source[key]), '复用与来源策略直接取各自保存字段：' + key);
}
assert.deepEqual(clone(nodes(reuseDetails).find(row => row.type === 'reference').props.entries), { '复用候选': third, '来源候选': first });
nodes(reuseRow).find(row => row.props.className === 'rd-candidate-choice').props.onClick();
assert.strictEqual(writes.at(-1), reused, '点击复用行仍查看这个兄弟候选，保留原选择回调与身份');
assert.deepEqual(clone(reused), savedReuse); assert.deepEqual(clone(origin), savedOrigin, '展开与查看保留双方原保存字段');
const partialData = clone(data), longReason = '部分批次的全链安排或交期资料缺失，已知小计列出当前可核对的交付结果。';
partialData.candidates.push({ ...clone(partialData.candidates[2]), candidate_ref: '9'.repeat(48), label: '重点工序优先方案 3/3' });
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
const recommendation = expand(h(D.Recommendation, { data, onSelect: row => writes.push(row.candidate_ref), onGantt: row => navigation.push(row.candidate_ref) }));
assert(text(recommendation).includes(data.candidates.find(candidate => candidate.candidate_ref === recommended).label), '查看第三候选仍展示保存的推荐');
assert(text(recommendation).includes('目标最优候选') && text(recommendation).includes('健康比较原方案'));
nodes(recommendation).find(node => node.type === 'button' && text(node) === '查看推荐方案').props.onClick();
assert.equal(writes.at(-1), recommended);
const original = { run_ref: runRef, candidate_ref: third, selected_batch_ref: 'e'.repeat(48), return_history_context: { accepted_from: '2026-10-01', accepted_to: '2026-10-14', state: 'complete', sort: 'accepted_at', order: 'asc', page: 2, size: 20 }, range_start, range_end, reference_candidate_ref: first };
const runHistoryReturn = { view: 'analysis', context: { source: 'run_history', history_topic: 'run_catalog', history_query: original.return_history_context } };
const workspace = expand(h(D.Workspace, { adapter: { decisionSummary: () => payload }, initialContext: original, runHistoryReturn, onNavigate: (page, context) => navigation.push({ page, context }), renderAdoption: (ref, metadata) => h('adoption', { candidateRef: ref, ...metadata }) }));
const workspaceRemembered = remembered.at(-1);
window.RunDecisionResources = { Pane: 'resource-pane' };
const resourceEntry = expand(h(D.Workspace, { adapter: { resourceWorkspace: (reference, q, saved) => resourceWorkspaceFixture(summaryPayload, saved) }, initialContext: { ...original, comparison_tab: 'resources', resource_kind: 'operator', resource_ref: '0'.repeat(48) } }));
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
const readOnly = { view: true, export: false, edit_draft: false, adopt: false, report_actual: false, trial: false };
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
  assert.equal(API.decision(overview, runRef, formalQuery).scope.reference.kind, 'admission_official');
  rejected(overview, value => { value.data.scope.range_start = '2026-10-02T00:00:00'; }, value => API.decision(value, runRef, formalQuery), '概览回显当前甘特时间窗');
}
function referenceContracts() {
  const q = { comparison_mode: 'admission_official', selected_candidate_ref: third, plan_ref: planRef, batch_ref: batchRef, range_start, range_end, snapshot_ref: snapshot };
  const value = referenceFixture(q), read = result => API.referenceWorkspace(result, runRef, q);
  assert.strictEqual(read(value), value.data);
  assert.equal(value.data.candidate.candidate_ref, third); assert.equal(value.data.reference.source_candidate_ref, recommended, '导航候选身份和正式归档来源分别保存');
  rejected(value, result => { result.data.candidate.candidate_ref = recommended; }, read, '正式归档保留当前比较的所选候选身份');
  rejected(value, result => { result.data.reference.plan_ref = first; }, read, '正式归档的 plan_ref 与 baseline_ref 一致');
  rejected(value, result => { result.data.plan_ref = first; }, read, '正式甘特必须使用 drill 指定的保存归档');
  rejected(value, result => { result.data.plan_ref = result.data.reference.plan_ref = result.data.reference.baseline_ref = first; }, read, '返回的完整正式身份仍须与 drill 指定归档一致');
  rejected(value, result => { result.meta.snapshot_ref = 't'.repeat(32); }, read, '正式甘特刷新快照身份不得串范围');
  rejected(value, result => { result.data.batch_ref = null; }, read, '正式甘特保持当前批次筛选');
  rejected(value, result => { result.data.time_scope.range_end = '2026-10-06T00:00:00'; }, read, '正式甘特保持当前查看时间窗');
  for (const level of ['capabilities', 'candidate']) for (const key of ['edit_draft', 'adopt', 'report_actual', 'trial'])
    rejected(value, result => { (level === 'candidate' ? result.data.candidate.capabilities : result.data.capabilities)[key] = true; }, read, '正式归档写能力须关闭：' + level + '.' + key);
  {
    const fixture = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures/decision_candidate_baseline.json'), 'utf8')), { baseline, workspace } = fixture;
    const saved = clone(baseline), readBaseline = result => window.RunBaselineAPI.validate(result, workspace);
    assert.strictEqual(readBaseline(baseline), baseline.data, '真实HTTP200原安排对照接受保存工种字段');
    assert(baseline.data.comparisons.some(row => row.process_type_ref && row.process_type_label), '实际响应包含保存工种身份与名称');
    rejected(baseline, result => { result.data.comparisons[0].process_type_ref = 'current-live-id'; }, readBaseline, '新增工种身份字段存在时保持合法保存引用');
    rejected(baseline, result => { result.data.comparisons[0].process_type_label = {}; }, readBaseline, '新增工种名称字段存在时保持字符串或缺项');
    const unknown = clone(baseline); unknown.data.comparisons.forEach(row => { row.process_type_ref = null; row.process_type_label = null; });
    assert.strictEqual(readBaseline(unknown), unknown.data, '历史工种缺项保持null可读');
    const legacy = clone(baseline); legacy.data.comparisons.forEach(row => { delete row.process_type_ref; delete row.process_type_label; });
    assert.strictEqual(readBaseline(legacy), legacy.data, '旧响应缺少新增工种字段仍可读');
    const missingInput = clone(baseline); missingInput.data.generation.source_verification.input_source_verified = false;
    assert.strictEqual(readBaseline(missingInput), missingInput.data, '旧来源缺原输入事实仍按明确内容状态读取');
    rejected(baseline, result => { result.data.generation.source_verification.facts_content_verified = false; }, readBaseline, '归档内容核验失败时停止读取');
    rejected(baseline, result => { result.data.generation.source_verification.candidate_content_verified = false; }, readBaseline, '候选内容核验失败时停止读取');
    assert.deepEqual(clone(baseline), saved, '原安排校验保持真实DTO原值');
    console.log('actual saved candidate baseline: typed and legacy process-type fields passed');
  }
}
function recommendationContracts() {
  const read = value => API.decision(value, runRef, query);
  const readSummary = value => API.decisionSummary(value, runRef, query), savedSummary = clone(summaryPayload);
  assert.strictEqual(readSummary(summaryPayload), summaryPayload.data, '首屏使用独立core合同，推荐真实重指标由共同目录验证');
  assert.deepEqual(clone(summaryPayload), savedSummary, '摘要校验保留候选原数、范围、推荐和导出快照');
  rejected(summaryPayload, value => { delete value.data.candidates[0].metrics.overdue_count; }, readSummary, '首屏缺交期核心值须报告真实资料错误');
  rejected(summaryPayload, value => { value.data.candidates[0].metrics.changed_operation_count = clone(metric); }, readSummary, '未计算的矩阵字段不伪装为首屏指标');
  rejected(summaryPayload, value => { value.data.recommendation.current_comparison.all_differences.find(row => row.metric_key === 'type_changeover_count').metric_version = 'old'; }, readSummary, '推荐重指标版本由同份目录核对');
  rejected(summaryPayload, value => { value.data.scope.selected_candidate_ref = first; }, readSummary, '首屏拒绝其他当前候选的响应');
  assert.throws(() => read(summaryPayload), /指标|分类/, '摘要不进入完整矩阵validator');
  rejected(payload, value => { delete value.data.completion_groups; }, read, '完整概览仍要求全部完成组');
  rejected(payload, value => { delete value.data.candidates[0].metrics.type_changeover_count; }, read, '完整概览仍要求每个候选的重指标');
  const statusWindow = { ...window }, partialCandidate = { ...data.candidates[0], status: 'partial', persisted_status: 'completed', completeness: 'partial' };
  for (const output of compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources: [{ path: 'RunCandidateControls.jsx', code: fs.readFileSync(path.join(app, 'RunCandidateControls.jsx'), 'utf8') }] }).outputs)
    vm.runInNewContext(output.code, { React, window: statusWindow });
  const status = expand(h(statusWindow.RunCandidateControls.Status, { candidate: partialCandidate }));
  assert.equal(window.WorkbenchTerms.candidate_statuses.partial, window.WorkbenchTerms.delivery_completion_states.incomplete, 'partial候选沿共同工序安排状态表达');
  assert(nodes(status).some(node => node.props['data-candidate-status'] === partialCandidate.status) && nodes(status).some(node => node.props['data-candidate-persisted-status'] === partialCandidate.persisted_status), '计算完成与工序未排齐分别绑定原始状态');
  assert(text(status).includes(window.WorkbenchTerms.candidate_statuses.partial) && text(status).includes(window.WorkbenchTerms.candidate_statuses.completed));
  for (const kind of ['complete', 'schedulable_scope', 'partial']) {
    const value = clone(data); value.recommendation.recommendation_type = kind;
    const tree = expand(h(D.Recommendation, { data: value, onSelect: () => {} }));
    assert.equal(tree.props['data-recommendation-type'], kind); assert(visibleText(tree).includes(value.candidates.find(candidate => candidate.candidate_ref === value.recommendation.candidate_ref).label), '推荐类别和候选身份沿用后端保存结果');
    assert(!visibleText(tree).includes('建议采用'), '算法推荐标题与当前采用预检分别表达');
  }
  for (const compact of [false, true]) {
    const unavailable = clone(data);
    unavailable.recommendation.candidate_ref = null;
    unavailable.recommendation.headline = '所有候选均未完成计算，暂无可推荐方案。';
    const panel = expand(h(D.Recommendation, { data: unavailable, onSelect: () => {}, compact }));
    assert.equal(text(nodes(panel).find(node => node.type === 'h3')), '本次排产暂无推荐方案');
    assert.equal(text(nodes(panel).find(node => node.props.className === 'rd-recommend-cause')), unavailable.recommendation.headline,
      'Without a selected recommendation, its actual outcome takes precedence over saved selection-basis wording');
    assert(!nodes(panel).some(node => node.type === 'button' && node.props.icon === 'search'));
  }
  const tree = expand(h(D.Recommendation, { data, onSelect: () => {} })), full = text(tree), shown = visibleText(tree);
  const compact = expand(h(D.Recommendation, { data, onSelect: () => {}, compact: true })), compactShown = visibleText(compact);
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
    const page = expand(h(D.Workspace, { adapter: { decisionSummary: () => ({ ...payload, data: summaryData }) }, initialContext: { run_ref: runRef, candidate_ref: third, reference_candidate_ref: first, range_start, range_end, comparison_tab: tab } }));
    assert.equal(nodes(page).filter(node => node.props.className === 'rd-difference-summary').length, tab === 'differences' ? 1 : 0, '三项差异只在差异页出现：' + tab);
  }
  assert.equal(nodes(tree).filter(row => row.props['data-recommendation-metric']).length, 6, '首屏采用后端最多3+3主要条目');
  assert.equal(nodes(tree).filter(row => row.props['data-recommendation-difference']).length, definitions.length, '原生展开保留全部差值');
  assert(full.includes('目标指标并列') && full.includes('等价复用') && full.includes('旧记录未保存未舍入的健康分量'));
  const ratioEvidence = text(nodes(tree).find(row => row.props['data-selection-evidence'] === 'tolerance_total_tardiness_hours')).replace(/\s+/g, ' ');
  assert(/采用容差 10(?:\.0+)?%/.test(ratioEvidence) && ratioEvidence.includes('采用上限 11 小时') && !ratioEvidence.includes('0.1 小时'), '拖期差额与上限用小时，保存比例容差独立显示百分比');
  const floatingBasis = clone(basis), floatingEntry = floatingBasis.explanation.entries.find(row => row.key === 'tolerance_total_tardiness_hours');
  floatingEntry.value = 17.24000000000001;
  const floatingSaved = clone(floatingBasis), floatingTree = expand(h(window.RunDecisionRecommendation.SelectionEvidence, { basis: floatingBasis, data }));
  const floatingField = nodes(floatingTree).find(row => row.props['data-selection-evidence'] === 'tolerance_total_tardiness_hours');
  assert(text(floatingField).replace(/\s+/g, ' ').includes('记录值 17.24 小时') && !text(floatingField).includes('17.24000000000001'), '真实浮点尾差按共同格式显示');
  assert(nodes(floatingField).some(row => row.props.title === '17.24000000000001'), '原保存数值仍可悬停核对');
  assert.deepEqual(clone(floatingBasis), floatingSaved, '显示格式保留DTO原值');
  assert(!shown.includes('旧记录未保存未舍入的健康分量'), '长选择缺项位于原生展开中');
  assert(shown.includes(basis.explanation.headline) && full.includes(basis.explanation.headline), '默认推荐区保留唯一真实选择主因，展开继续完整保存依据');
  const recommendationHeader = tree.children.find(row => row && row.props && row.props.className === 'rd-recommend-main'), recommendationCause = tree.children.find(row => row && row.props && row.props.className === 'rd-recommend-cause');
  assert(recommendationHeader && text(recommendationHeader).includes('查看推荐方案') && text(recommendationHeader).includes(window.WorkbenchTerms.completion_summary(data.recommendation.completion_scope)), '推荐标题、查看操作与工序摘要组成共同头部');
  assert.equal(text(recommendationCause), basis.explanation.headline, '原推荐主因逐字保留在全宽独立正文，未截断或页面重算');
  const comparisonTitles = nodes(tree).filter(row => row.props.className === 'rd-tradeoffs-title');
  assert.equal(comparisonTitles.length, 1); assert.equal(text(comparisonTitles[0]).replace(/\s+/g, ''), '当前比较：推荐方案相对' + data.baseline.label, '收益与代价共用一个真实当前基准标题');
  assert(!nodes(tree).some(row => row.props.className === 'rd-tradeoff-reference'), '两个取舍栏保留各自标题，比较对象不逐栏重复');
  assert(shown.replace(/\s+/g, '').includes('推荐方案相对' + data.baseline.label), '收益与代价列头可视显示推荐方案相对当前查看基准的关系');
  assert(full.includes('少安排的准备需求') && !nodes(tree).filter(row => row.props['data-recommendation-metric']).some(row => row.props['data-recommendation-metric'] === 'scheduled_setup_hours'), '漏排造成的少安排准备保留在中性完整差值中');
  const partial = clone(data); partial.recommendation.recommendation_type = 'partial'; partial.recommendation.completion_scope.unplanned_operation_count = 2; partial.recommendation.completion_scope.unknown_batch_count = 1;
  const partialShown = visibleText(expand(h(D.Recommendation, { data: partial, onSelect: () => {} }))).replace(/\s+/g, ' ');
  assert(partialShown.includes(window.WorkbenchTerms.completion_summary(partial.recommendation.completion_scope)), '部分结果首屏沿共同摘要明确未安排与待确认批次');
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
  remainingMetrics.forEach((row, index) => { assert.strictEqual(row.props.metric, remainingWork.metrics[prepKeys[index]]); assert.equal(row.props.showReason, false, '共同剩余工时表沿用原metric且集中显示原因'); });
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
  const original = { run_ref: runRef, candidate_ref: third, reference_candidate_ref: first, comparison_mode: 'candidates', resource_view: 'selected_batches', range_start, range_end, metric_view: 'all', comparison_tab: 'overview',
    return_history_context: { query: '第5验收' }, detail_queries: { 'completion-batches': { completion_candidate_ref: first, completion_filter: 'ordinary', open: false, page: 2, size: 50, snapshot_ref: snapshot }, operations: { page: 2, size: 50, batch_ref: batchRef, snapshot_ref: snapshot }, resources: { page: 3, heatmap_page: 2, day_page: 4, resource_kind: 'operator', resource_ref: resourceRef, snapshot_ref: snapshot, day_snapshot_ref: 't'.repeat(32) }, preparation: { page: 2, size: 20, allocation_state: 'unplanned', snapshot_ref: snapshot }, changeovers: { event_side: 'reference', sort: 'machine_label', order: 'desc', snapshot_ref: snapshot } } };
  const links = [], main = expand(h(D.Workspace, { adapter: { decisionSummary: () => payload }, initialContext: original, onNavigate: (page, context) => links.push({ page, context }) }));
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
  const directPage = expand(h(D.Workspace, { adapter: { decisionSummary: () => direct }, initialContext: original, onNavigate: (page, context) => links.push({ page, context }) }));
  nodes(nodes(directPage).find(row => row.props['data-recommendation-difference'] === 'changed_operation_count')).find(node => node.type === 'button').props.onClick();
  assert.equal(links.at(-1).page, 'gantt'); assert.equal(links.at(-1).context.candidate_ref, recommended); assert.equal(links.at(-1).context.operation_ref, operationRef); assert.equal(links.at(-1).context.selected_row_ref, rowRef);
  assert.deepEqual(clone(links.at(-1).context.return_decision_context), originalRemembered, '真实工序甘特返回原第三候选比较，保留原窗口');
  const referenceSupport = clone(direct), beforeTarget = referenceSupport.data.recommendation.current_comparison.all_differences.find(row => row.metric_key === 'changed_operation_count').supporting_refs[0];
  beforeTarget.side = 'reference'; beforeTarget.drill.candidate_ref = first;
  assert.strictEqual(read(referenceSupport), referenceSupport.data, '已移除工序支撑使用实际候选基准侧，推荐锚点仍固定');
  rejected(referenceSupport, value => { delete value.data.recommendation.current_comparison.all_differences.find(row => row.metric_key === 'changed_operation_count').supporting_refs[0].side; }, read, '基准侧必须明确声明，不能冒充推荐侧');
  const referencePage = expand(h(D.Workspace, { adapter: { decisionSummary: () => referenceSupport }, initialContext: original, onNavigate: (page, context) => links.push({ page, context }) }));
  const beforeButton = nodes(nodes(referencePage).find(row => row.props['data-recommendation-difference'] === 'changed_operation_count')).find(node => node.type === 'button');
  assert(text(beforeButton).includes('基准')); beforeButton.props.onClick();
  assert.equal(links.at(-1).page, 'gantt'); assert.equal(links.at(-1).context.candidate_ref, first); assert.equal(links.at(-1).context.selected_candidate_ref, recommended); assert.equal(links.at(-1).context.selected_row_ref, rowRef);
  assert.deepEqual(clone(links.at(-1).context.return_decision_context), originalRemembered, '基准侧定位返回原第三查看与比较范围');
  const formalSupport = bindRecommendationScope({ ...clone(referenceSupport), data: { ...clone(referenceSupport.data), scope: comparisonScope({ comparison_mode: 'admission_official' }), baseline: clone(officialBaseline) } });
  const formalBefore = formalSupport.data.recommendation.current_comparison.all_differences.find(row => row.metric_key === 'changed_operation_count').supporting_refs[0];
  Object.assign(formalBefore.drill, { candidate_ref: recommended, reference_view: true, plan_ref: planRef });
  assert.strictEqual(API.decision(formalSupport, runRef, { comparison_mode: 'admission_official', selected_candidate_ref: third }), formalSupport.data, '正式基准保留推荐锚点与真实只读计划身份');
  rejected(formalSupport, value => { value.data.recommendation.current_comparison.all_differences.find(row => row.metric_key === 'changed_operation_count').supporting_refs[0].drill.plan_ref = first; }, value => API.decision(value, runRef, { comparison_mode: 'admission_official', selected_candidate_ref: third }), '正式基准支撑不能串其他计划');
  window.RunDecisionDetails = { Pane: 'detail-pane' };
  const supportContext = links.find(row => row.context.comparison_tab === 'differences').context;
  const supportData = bindRecommendationScope({ ...clone(payload), data: { ...clone(data), scope: { ...clone(data.scope), selected_candidate_ref: recommended } } });
  const supportPage = expand(h(D.Workspace, { adapter: { decisionSummary: () => supportData }, initialContext: supportContext, onNavigate: (page, context) => links.push({ page, context }) }));
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
    RunCandidateAnalysisAPI: { adapter: value => value, create: () => ({}) }, RunDecisionAPI: { adapter: value => value, create: () => ({}) },
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
      APSResourceSession: { useQuery: (load, deps, enabled = true) => ({ result: enabled ? load() : null, loading: false, error: null }) } };
    for (const output of compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources: [{ path: 'RunDecisionComparison.jsx', code: fs.readFileSync(path.join(app, 'RunDecisionComparison.jsx'), 'utf8') }] }).outputs)
      vm.runInNewContext(output.code, { React: state.React, window: local, AbortController });
    const returnRun = { run_ref: first, range_start: '2026-09-30T00:00:00', range_end }, props = { navigation, runHistoryReturn, initialContext: { ...original, range_start: times[0], range_end: times[1], return_run_context: returnRun },
      onNavigate: (page, context) => links.push({ page, context }), adapter: { decisionSummary: (run, current) => { queries.push(clone(current)); return value; } } };
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
  const local = { ...window, RunCandidateControls: controls, RunCandidateModel: { ...window.RunCandidateModel, matching: values => values },
    RunCandidateGantt: ganttComponent, WorkbenchControls: { usePrintLayout: () => false }, WorkbenchListControls: { EmptyState: 'empty-state' }, RunCandidateAnalysisAPI: { adapter: adapter => adapter }, RunDecisionAPI: { adapter: adapter => adapter },
    WorkbenchPageContext: { useSnapshot: current => recalled.push(current) }, WorkbenchCaption: { useCaption: current => captions.push(current) }, RunCandidateAnalysis: {} };
  const sources = ['resource-session.js', 'WorkbenchFormat.js', 'WorkbenchDatePickerModel.js', 'PointContract.js', 'PointGanttModel.js', 'GanttGraph.js', 'PlanGanttModel.js', 'RunCandidateModel.js', 'RunBaselineControls.jsx', 'RunCandidateGantt.jsx', 'RunCandidateWorkspace.jsx'].map(name => ({ path: name, code: fs.readFileSync(path.join(app, name), 'utf8') }));
  for (const output of compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources }).outputs)
    vm.runInNewContext(output.code, { React: state.React, window: local, AbortController, DOMException });
  const createGraph = local.GanttGraph.create; let graphBuilds = 0;
  local.GanttGraph.create = graph => { graphBuilds++; return createGraph(graph); };
  ganttComponent.TaskList = local.RunCandidateGantt.TaskList; local.RunCandidateGantt = ganttComponent;
  const adapter = Object.fromEntries(['catalog', 'workspace', 'referenceWorkspace', 'analysis', 'adoptions'].map(name => [name, async (...args) => {
    calls.push({ name, args }); return ['workspace', 'referenceWorkspace'].includes(name) ? loadWorkspace(...args) : null;
  }]));
  const props = { view: 'gantt', initialContext: context, adapter, onNavigate: (page, current) => links.push({ page, context: current }),
    renderAdoption: () => h('adoption'), renderTrial: () => h('trial') };
  let tree;
  const render = async () => { for (let i = 0; i < 4; i++) { tree = state.render(() => expand(h(local.RunCandidateWorkspace, props))); state.flush(); await turns(); } return tree; };
  await render();
  return { get tree() { return tree; }, get graphBuilds() { return graphBuilds; }, render, calls, recalled, links, captions, baselineSource: local.RunBaselineControls.Source, chosen: nodes(tree).find(node => node.type === gantt)?.props.selected };
}
async function workspaceContracts() {
  {
    const state = hooks(), reads = [], local = { ...window, RunDecisionResources: { Pane: 'resource-pane' }, RunDecisionDetails: { Pane: 'detail-pane' } };
    for (const name of ['resource-session.js', 'RunDecisionComparison.jsx']) for (const output of compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources: [{ path: name, code: fs.readFileSync(path.join(app, name), 'utf8') }] }).outputs)
      vm.runInNewContext(output.code, { React: state.React, window: local, AbortController, DOMException });
    const response = q => { const value = clone(summaryPayload); value.data.scope = { ...comparisonScope(q), resource_refs: { machine: [], operator: [] }, batch_refs: [batchRef], operation_refs: [operationRef] };
      value.data.baseline.candidate_ref = value.data.scope.reference.candidate_ref; return bindRecommendationScope(value); };
    const saved = { resource_kind: 'operator', pressure_threshold: 0.8, page: 2, heatmap_page: 2, snapshot_ref: 'r'.repeat(32) };
    const props = { initialContext: { ...original, comparison_tab: 'resources', detail_queries: { resources: saved } }, adapter: API.adapter({
      resourceWorkspace: async (run, q, leaf, signal) => { reads.push({ name: 'combined', query: clone(q), leaf: clone(leaf), signal }); return resourceWorkspaceFixture(response(q), leaf); },
      decisionSummary: async (_, q) => { reads.push({ name: 'summary', query: clone(q) }); return response(q); }
    }) };
    let tree; const render = async () => { for (let index = 0; index < 3; index++) { tree = state.render(() => expand(local.RunDecisionComparison.Workspace(props))); state.flush(); await turns(); } };
    await render(); assert.deepEqual(reads.map(row => row.name), ['combined']); assert.deepEqual(reads[0].leaf, saved);
    const pane = nodes(tree).find(row => row.type === 'resource-pane'); assert.equal(pane.props.result.resource_result.ok, false);
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
    const state = hooks(), requests = [], summaries = [], local = { ...window, RunDecisionDetails: { Pane: 'detail-pane' } };
    for (const name of ['resource-session.js', 'RunDecisionComparison.jsx']) for (const output of compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources: [{ path: name, code: fs.readFileSync(path.join(app, name), 'utf8') }] }).outputs)
      vm.runInNewContext(output.code, { React: state.React, window: local, AbortController, DOMException });
    const responseFor = (q, summary = false) => {
      const next = clone(summary ? summaryPayload : payload); next.data.scope = comparisonScope(q); next.data.scope.resource_view = q.resource_view || 'selected_batches';
      next.meta.snapshot_ref = summary ? String(summaries.length).padStart(32, '0') : q.snapshot_ref;
      if (summary) next.meta.as_of = '2026-10-05T00:00:' + String(summaries.length).padStart(2, '0');
      next.data.baseline.candidate_ref = next.data.scope.reference.candidate_ref; return bindRecommendationScope(next);
    };
    const props = { initialContext: original, adapter: API.adapter({
      decisionSummary: async (run, q) => { summaries.push(clone(q)); return responseFor(q, true); },
      decision: (run, q, signal) => new Promise((resolve, reject) => requests.push({ q: clone(q), signal, resolve, reject }))
    }) };
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
async function paneContracts() {
  {
    const state = hooks(), waiting = [], local = { ...window, RunDecisionAPI: API, APSResourceContract: {} };
    for (const name of ['resource-session.js', 'RunDecisionDetails.jsx']) for (const output of compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources: [{ path: name, code: fs.readFileSync(path.join(app, name), 'utf8') }] }).outputs)
      vm.runInNewContext(output.code, { React: state.React, window: local, AbortController, DOMException });
    const props = { result: clone(summaryPayload), section: 'differences', query: {}, onQuery: value => { props.query = value; },
      adapter: { decisionDetails: (run, q, section) => new Promise(resolve => waiting.push({ q: clone(q), section, resolve })) } };
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
  const state = hooks(), local = { ...window, APSResourceContract: {}, RunDecisionAPI: API, RunOperationEffort: { Effort: 'effort-facts', Standard: 'standard-facts' } }, calls = [];
  const sources = ['resource-session.js', 'BatchContract.js', 'PlanGanttModel.js', 'RunCandidateModel.js', 'RunDecisionDetails.jsx'].map(name => ({ path: name, code: fs.readFileSync(path.join(app, name), 'utf8') }));
  for (const output of compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources }).outputs)
    vm.runInNewContext(output.code, { React: state.React, window: local, AbortController, DOMException });
  const props = { result: payload, section: 'delivery', query: {}, onQuery: next => { props.query = next; },
    adapter: { decisionDetails: async (run, q, section) => { calls.push(clone(q)); if (calls.length === 1) throw new Error('读取失败'); return detailsFixture(section, q); } } };
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
  deferred.items[0].after = clone(deferred.items[0].before); const savedDeferred = clone(deferred);
  const deliveryRow = nodes(expand(h(local.RunDecisionDetails.BatchTable, { data: deferred }))).find(row => row.props['data-decision-batch'] === batchRef);
  for (const cell of deliveryRow.children.slice(2, 4)) {
    const missing = window.WorkbenchTerms.missing_arrangements(0, 1), cellText = text(cell).replace(/\s+/g, ' ');
    assert.equal(cellText.split(missing).length - 1, 1, '缺料未安排只保留一份真实安排摘要');
    assert.equal(cellText.split('批次完工待确认').length - 1, 1, '完整批次预计完工缺项只表达一次');
    const partial = nodes(cell).find(row => row.props.title === window.WorkbenchFormat.dateTime(finish, { seconds: true, fractions: true }));
    assert(partial && text(partial).includes(window.WorkbenchTerms.arrangement_labels.partial_finish) && !text(partial).includes('12.250'), '部分安排结束按分钟显示，完整秒和小数留在title');
  }
  assert.deepEqual(clone(deferred), savedDeferred);
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
  q = API.completionScope(runRef, { ...query, completion_candidate_ref: recommended, ...q });
  const available = persisted === 'completed', refs = Array.from({ length: 21 }, (_, index) => (index + 100).toString(16).padStart(48, '0'));
  const savedMetric = available ? { ...metric, value: 0, known_subtotal: 0 } : { ...metric, value: null, known_subtotal: null, known_count: 0, unknown_count: 1, total_count: 1, state: 'unavailable', reason: { code: 'candidate_result_missing', message: '候选没有产出保存安排。' } };
  const metrics = Object.fromEntries(prepKeys.map(key => [key, clone(savedMetric)]));
  const remaining = available && state === 'ordinary' ? 1 : available ? 0 : null;
  const drill = remaining ? { run_ref: runRef, candidate_ref: q.completion_candidate_ref, selected_candidate_ref: q.completion_candidate_ref, reference_candidate_ref: first, comparison_mode: 'candidates', resource_view: q.resource_view, range_start, range_end, comparison_tab: 'preparation', detail_query: { work_scope: 'remaining' } } : null;
  let items = refs.map((batch_ref, index) => {
    const unfinished = !available || state !== 'complete' && index === 0, count = available ? unfinished && state === 'ordinary' ? 1 : 0 : null;
    return { batch_ref, batch_label: 'B-' + String(index + 1).padStart(3, '0'), part_no: 'P-001', part_label: null, quantity: 1,
      completion_state: !available || unfinished && state === 'unknown' ? 'unknown' : unfinished ? 'incomplete' : 'complete', schedule_complete: available ? !unfinished : null,
      scheduled_operation_count: available ? 1 : null, unplanned_operation_count: count, deferred_operation_count: available ? 0 : null,
      remaining_work: { operation_count: count, metrics: clone(metrics) }, issues: unfinished ? ['schedule_time_invalid'] : [],
      remaining_drill: count ? { ...clone(drill), detail_query: { work_scope: 'remaining', batch_ref } } : null };
  });
  const incomplete = items.filter(row => row.schedule_complete !== true), complete = items.filter(row => row.schedule_complete === true), ordinary = items.filter(row => row.completion_state === 'incomplete'), unknown = items.filter(row => row.completion_state === 'unknown');
  const summary = { ...clone(completionScope), state: available ? incomplete.length ? state === 'unknown' ? 'unavailable' : 'partial' : 'complete' : 'unavailable', source_available: available,
    complete_batch_count: complete.length, incomplete_batch_count: incomplete.length, ordinary_incomplete_batch_count: ordinary.length, deferred_batch_count: 0, unknown_batch_count: unknown.length,
    unplanned_operation_count: remaining, deferred_operation_count: available ? 0 : null,
    sample_batch_refs: { complete: complete.slice(0, 3).map(row => row.batch_ref), incomplete: incomplete.slice(0, 3).map(row => row.batch_ref), deferred: [], unknown: unknown.slice(0, 3).map(row => row.batch_ref) },
    remaining_work: { operation_count: remaining, unplanned_operation_count: remaining, deferred_operation_count: available ? 0 : null, metrics: clone(metrics) }, drill };
  items = items.filter(row => q.completion_filter === 'all' || q.completion_filter === 'complete' && row.schedule_complete === true || q.completion_filter === 'unfinished' && row.schedule_complete !== true || q.completion_filter === 'ordinary' && row.completion_state === 'incomplete' || q.completion_filter === 'unknown' && row.completion_state === 'unknown');
  if (q.order === 'desc') items.reverse();
  const total = items.length;
  return { ...clone(payload), data: { run_ref: runRef, scope: { ...clone(data.scope), batch_refs: refs }, baseline: clone(data.baseline),
    candidate: { candidate_ref: q.completion_candidate_ref, label: persisted === 'completed' ? '完成集合成员' : '未产出成员', persisted_status: persisted },
    source: { role: 'completion_anchor', grain: 'full_admission_per_candidate_batch', candidate_ref: q.completion_candidate_ref, available, reason: available ? null : { code: 'candidate_result_missing', message: '候选没有产出保存安排。' } },
    filters: { section: 'completion-batches', completion_candidate_ref: q.completion_candidate_ref, completion_filter: q.completion_filter, sort: q.sort, order: q.order },
    summary, items: items.slice((q.page - 1) * q.size, q.page * q.size), page: { number: q.page, size: q.size, total, has_more: q.page * q.size < total }, metric_version: 'decision-preparation-v4' } };
}
async function completionContracts() {
  const q = { ...query, completion_candidate_ref: recommended, completion_filter: 'complete' }, read = value => API.completionBatches(value, runRef, q);
  const one = completionFixture(q), two = completionFixture({ ...q, page: 2, snapshot_ref: snapshot }), all = completionFixture({ ...q, size: 50 });
  assert.strictEqual(read(one), one.data);
  assert.strictEqual(API.completionBatches(two, runRef, { ...q, page: 2, snapshot_ref: snapshot }), two.data);
  assert.strictEqual(API.completionBatches(all, runRef, { ...q, size: 50 }), all.data);
  assert.equal(one.data.items.length, 20); assert.equal(two.data.items.length, 1);
  assert.deepEqual([...one.data.items, ...two.data.items], all.data.items, '同一成员的完整集合逐页20+1与50条一页保持同源、完整且无重复');
  rejected(one, value => { value.data.scope.selected_candidate_ref = recommended; }, read, '集合锚点独立于原第三查看');
  rejected(one, value => { value.data.source.candidate_ref = third; }, read, '批次来源必须属于集合锚点');
  const remainingQuery = { ...q, completion_filter: 'ordinary' }, remaining = completionFixture(remainingQuery, 'ordinary');
  assert.strictEqual(API.completionBatches(remaining, runRef, remainingQuery), remaining.data);
  rejected(remaining, value => { value.data.items[0].remaining_drill.detail_query.work_scope = 'all'; }, value => API.completionBatches(value, runRef, remainingQuery), '剩余需求只准进入精确剩余工序');
  const unknownQuery = { ...q, completion_filter: 'unknown' }, unknown = completionFixture(unknownQuery, 'unknown');
  assert.strictEqual(API.completionBatches(unknown, runRef, unknownQuery), unknown.data);
  assert.equal(unknown.data.items[0].remaining_work.operation_count, 0); assert.equal(unknown.data.items[0].remaining_drill, null, '已安排但时间未知的批次保持零剩余，不推断漏排');
  for (const persisted of ['failed', 'skipped']) {
    const unavailable = completionFixture(unknownQuery, 'unknown', persisted);
    assert.strictEqual(API.completionBatches(unavailable, runRef, unknownQuery), unavailable.data);
    assert.equal(unavailable.data.items[0].remaining_work.operation_count, null); assert.equal(unavailable.data.summary.drill, null);
    const unavailableTree = expand(h(window.RunDecisionCompletion.Pane, { result: payload, query: unknownQuery, enabled: true, onQuery: () => {}, onSupport: () => {}, adapter: { completionBatches: (run, value) => completionFixture(value, 'unknown', persisted) } }));
    assert(!nodes(unavailableTree).some(row => row.type === 'button' && row.props.icon === 'search'), '缺少剩余资料不生成活动需求跳转');
    assert(!nodes(unavailableTree).some(row => row.type === 'details' && row.props.className === 'rd-completion-demand'));
    assert(nodes(unavailableTree).some(row => row.props['data-completion-metric']), '剩余metric的null缺项仍保留在原生数量资料中');
  }
  const state = hooks(), calls = [], links = [], local = { ...window, RunDecisionAPI: API };
  for (const name of ['resource-session.js', 'RunDecisionCompletion.jsx']) {
    const outputs = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources: [{ path: name, code: fs.readFileSync(path.join(app, name), 'utf8') }] }).outputs;
    for (const output of outputs) vm.runInNewContext(output.code, { React: state.React, window: local, AbortController, DOMException });
  }
  const props = { result: clone(payload), query: { completion_candidate_ref: recommended, completion_filter: 'complete' }, enabled: true,
    onQuery: value => { props.query = value; }, onSupport: value => links.push(value), adapter: { completionBatches: (run, value, signal) => { calls.push({ value: clone(value), signal }); return Promise.resolve(completionFixture(value, value.completion_filter === 'ordinary' ? 'ordinary' : 'complete')); } } };
  let tree;
  async function render() { for (let i = 0; i < 3; i++) { tree = state.render(() => expand(local.RunDecisionCompletion.Pane(props))); state.flush(); await turns(); } }
  await render();
  assert.equal(calls[0].value.selected_candidate_ref, third); assert.equal(calls[0].value.completion_candidate_ref, third, '工序安排锚点由共同当前方案派生');
  assert(!nodes(tree).some(row => row.type === 'button' && row.props.icon === 'search'), '零剩余工序不生成活动剩余需求跳转');
  assert(!nodes(tree).some(row => row.type === 'details' && row.props.className === 'rd-completion-demand'), '零剩余工序不生成默认需求入口');
  assert(nodes(tree).some(row => row.props['data-completion-metric']), '零剩余的原metric仍保留在原生数量资料中');
  nodes(tree).find(row => row.type === 'pager').props.onPage(2); await render();
  assert.equal(calls.at(-1).value.page, 2); assert.equal(calls.at(-1).value.snapshot_ref, snapshot);
  props.result.data.scope.selected_candidate_ref = first; bindRecommendationScope(props.result); props.query = { ...props.query, page: 1 }; delete props.query.snapshot_ref; await render();
  assert.equal(calls.at(-1).value.page, 1); assert.equal(calls.at(-1).value.snapshot_ref, undefined); assert.equal(calls.at(-1).value.selected_candidate_ref, first); assert.equal(calls.at(-1).value.completion_candidate_ref, first);
  assert.equal(props.query.completion_candidate_ref, undefined, '工序安排叶不保存第二条候选选择');
  nodes(tree).find(row => row.type === 'select' && row.props.value === 'complete').props.onChange({ target: { value: 'ordinary' } }); await render();
  nodes(tree).find(row => row.type === 'button' && row.props.icon === 'search' && typeof row.props.onClick === 'function').props.onClick();
  assert.equal(links.at(-1).candidate_ref, first); assert.equal(links.at(-1).drill.detail_query.work_scope, 'remaining');
  props.enabled = false; await render();
  assert.equal(tree, null); assert(calls.at(-1).signal.aborted, '折叠集合取消挂起的同源读取');
  const closed = expand(h(D.Workspace, { adapter: { decisionSummary: () => payload }, initialContext: { run_ref: runRef, candidate_ref: third } }));
  assert(!nodes(closed).some(row => row.props['data-completion-anchor']), '总览集合默认折叠，首屏不读取集合明细');
}
const legacyProcessRef = '6'.repeat(48), notStartedProcessRef = '7'.repeat(48), budgetProcessRef = '8'.repeat(48), failedProcessRef = '9'.repeat(48);
const processCountKeys = ['evaluated', 'accepted', 'current_accepted', 'strict_improvements', 'rejected', 'unverified_trials', 'decoder_invocations'];
const processCompletionKeys = ['expected_operation_count', 'missing_operation_count', 'unexpected_result_count', 'complete_batch_count', 'incomplete_batch_count'];
const processMetricKeys = ['changeover_count', 'makespan_hours', 'overdue_count', 'total_tardiness_hours', 'weighted_tardiness_hours'];
const processCounts = value => Object.fromEntries(processCountKeys.map(key => [key, value]));
const processCompletion = value => Object.fromEntries(processCompletionKeys.map(key => [key, value]));
const processMetrics = value => Object.fromEntries(processMetricKeys.map(key => [key, value]));
const processObjective = { name: 'min_tardiness', label: '最少总拖期', primary_metric_key: 'total_tardiness_hours', primary_metric_label: '总拖期', unit: '小时',
  score_fields: [{ index: 0, key: 'failed_ops', label: '失败工序', unit: '道', direction: 'lower' }, { index: 1, key: 'total_tardiness_hours', label: '总拖期', unit: '小时', direction: 'lower' }] };
function processFixture(input = {}, options = {}) {
  const q = API.processScope(runRef, { ...query, ...input, ...(options.nullViewer ? { selected_candidate_ref: null } : {}) });
  const complete = { expected_operation_count: 3, missing_operation_count: 0, unexpected_result_count: 0, complete_batch_count: 1, incomplete_batch_count: 0 };
  const counts = { evaluated: 45, accepted: 20, current_accepted: 10, strict_improvements: 9, rejected: 25, unverified_trials: 2, decoder_invocations: 50 };
  let members = [first, recommended, third, legacyProcessRef, notStartedProcessRef, budgetProcessRef, failedProcessRef].map(candidate_ref => {
    const legacy = candidate_ref === legacyProcessRef, notStarted = candidate_ref === notStartedProcessRef, unavailable = [budgetProcessRef, failedProcessRef].includes(candidate_ref), reused = candidate_ref === third;
    const solver = legacy ? { ...processCounts(null), evaluated: 7, decoder_invocations: 4 } : notStarted ? processCounts(0) : unavailable ? processCounts(null) : clone(counts);
    const status = unavailable ? candidate_ref === failedProcessRef ? 'failed' : 'skipped' : notStarted ? 'skipped' : 'completed';
    return { candidate_ref, label: candidate_ref === first ? '原算法过程' : candidate_ref === recommended ? '搜索候选过程' : candidate_ref === third ? '复用兄弟' : legacy ? '旧保存过程' : notStarted ? '未开始成员' : candidate_ref === budgetProcessRef ? '预算跳过成员' : '失败成员',
      status, persisted_status: status, kind: candidate_ref === first ? 'baseline' : 'candidate', algo_mode: 'greedy', used_strategy: reused ? 'priority-then-due' : 'due-first', dispatch_mode: 'stable', configured_dispatch_rule: 'EDD', adopted_dispatch_rule: notStarted || unavailable ? null : 'EDD',
      source_kind: reused ? 'reused' : legacy ? 'own_search' : notStarted ? 'not_started' : candidate_ref === budgetProcessRef ? 'budget_skipped' : candidate_ref === failedProcessRef ? 'failed' : 'own_search',
      source_candidate_ref: reused ? first : candidate_ref, own_elapsed_ms: legacy || unavailable ? null : reused || notStarted ? 0 : 1500, source_solver_elapsed_ms: legacy || unavailable ? null : notStarted ? 0 : 1125,
      own_counts: reused ? processCounts(0) : clone(solver), solver_counts: solver,
      stop_reason: unavailable ? { code: 'candidate_time_budget_reached', message: '预算结束，保存当前状态。' } : notStarted ? { code: 'reserved_for_later_phases', message: '为后续阶段保留预算。' } : { code: 'search_exhausted', message: '保存搜索已结束。' },
      final_metrics: legacy || unavailable || notStarted ? processMetrics(null) : { ...processMetrics(0), total_tardiness_hours: 2, makespan_hours: 4 },
      completion: legacy || unavailable || notStarted ? processCompletion(null) : clone(complete), algorithm_profile: legacy || unavailable || notStarted ? null : 'balanced', legacy_best_updates: legacy ? 2 : null,
      evidence_state: legacy ? 'partial' : unavailable ? 'unavailable' : 'complete', evidence_version: legacy ? null : 'optimization-process-v1' };
  });
  if (options.allFailed) members = members.filter(row => row.candidate_ref === failedProcessRef);
  const selected = options.nullViewer ? null : q.selected_candidate_ref || third;
  const anchor = q.process_candidate_ref || selected || members[0].candidate_ref, candidate = members.find(row => row.candidate_ref === anchor);
  assert(candidate, 'fixture的过程锚点须属于保存目录');
  const legacy = candidate.evidence_version === null, unavailable = candidate.evidence_state === 'unavailable', noRecords = unavailable || candidate.source_kind === 'not_started';
  const reason = candidate.evidence_state === 'complete' ? null : { code: legacy ? 'legacy_process_coverage' : 'process_not_recorded', message: legacy ? '旧记录保存代表尝试与离散事件，阶段计数缺项。' : '本成员的完整求解过程未保存。' };
  const points = noRecords ? [] : Array.from({ length: legacy ? 2 : 45 }, (_, index) => ({ source_candidate_ref: candidate.source_candidate_ref, event_index: index + 1, elapsed_ms: legacy ? index === 0 ? 50 : null : index * 25,
    phase: legacy ? null : index < 3 ? 'baseline' : 'local_search', phase_visit: legacy ? null : 0, segment: legacy ? null : index < 3 ? 0 : 1,
    flags: legacy ? [] : [index === 0 ? 'first_valid' : index === 3 ? 'first_expected_complete' : index === 44 ? 'final' : 'strict_improvement'], score: [3, index],
    primary_value: legacy ? index === 0 ? 5 : null : index, objective_scope: legacy ? null : 'all_batches', evaluation_scope: legacy ? null : { incomplete_batch_ids: [] }, completion: legacy ? processCompletion(null) : clone(complete), verified: legacy ? null : true }));
  const attempts = noRecords ? [] : Array.from({ length: legacy ? 2 : 21 }, (_, index) => ({ source_candidate_ref: candidate.source_candidate_ref, saved_index: index + 1, rank: legacy ? null : index + 1,
    strategy: 'due-first', dispatch_mode: 'stable', dispatch_rule: 'EDD', candidate_status: 'completed', source_label: '保存代表尝试', score: [3, index], failed_ops: 3,
    metrics: { ...processMetrics(0), total_tardiness_hours: legacy && index === 1 ? null : index }, primary_value: legacy && index === 1 ? null : index,
    objective_scope: legacy ? null : 'all_batches', completion: legacy ? processCompletion(null) : clone(complete), elapsed_ms: legacy ? null : index * 25, accepted: legacy ? null : index % 2 === 0,
    candidate_origin: null, weight_profile_slug: null, event_index: null, verified: null, strict_improved: null, comparison: null }));
  const sampling = { policy: legacy ? 'legacy_saved_events' : noRecords ? 'not_applicable' : 'elapsed_equal_width_bucket_end_best_v1', point_budget: 200, event_total_count: legacy || unavailable ? null : points.length,
    retained_point_count: points.length, bucket_count: legacy || noRecords ? null : 197, bucket_width_ms: legacy || noRecords ? null : 1125 / 197, mandatory: legacy || noRecords ? [] : ['first_valid', 'first_expected_complete', 'final'] };
  const endpoints = Object.fromEntries(['first_valid', 'first_expected_complete', 'final'].map(flag => [flag, legacy || unavailable ? null : points.some(point => point.flags.includes(flag))]));
  const rejection = legacy || unavailable ? null : { schedule_incomplete: 2 };
  const scope = { ...comparisonScope(q), selected_candidate_ref: selected };
  if (options.allFailed) { scope.reference = { kind: 'candidate', candidate_ref: null }; scope.reference_state = 'selection_required'; }
  const baseline = options.allFailed ? { ...clone(candidateBaseline), candidate_ref: null, state: 'selection_required' } : q.comparison_mode === 'admission_official' ? clone(officialBaseline) : { ...clone(candidateBaseline), candidate_ref: scope.reference.candidate_ref };
  const source = { role: 'process_anchor', grain: 'saved_candidate_solver_process', kind: candidate.source_kind, candidate_ref: anchor, source_candidate_ref: candidate.source_candidate_ref, available: !unavailable,
    evidence_state: candidate.evidence_state, evidence_version: candidate.evidence_version, reason, profile: legacy || noRecords ? {} : { profile: 'balanced', seed: 7, effective_time_budget_seconds: 3, effective_max_iterations: 50, effective_neighborhoods: ['move', 'swap'], enabled: true }, rejection_summary: clone(rejection) };
  const summary = { own_elapsed_ms: candidate.own_elapsed_ms, source_solver_elapsed_ms: candidate.source_solver_elapsed_ms, own_counts: clone(candidate.own_counts), solver_counts: clone(candidate.solver_counts),
    saved_attempt_count: attempts.length, retained_point_count: points.length, stop_reason: clone(candidate.stop_reason), coverage: { state: candidate.evidence_state, reason: clone(reason) }, sampling: clone(sampling), legacy_best_updates: candidate.legacy_best_updates, rejection_summary: clone(rejection) };
  const progress = { mode: points.length ? legacy ? 'discrete' : 'curve' : 'none', points, source_candidate_ref: source.source_candidate_ref, sampling: clone(sampling), coverage: { ...clone(summary.coverage), endpoint_coverage: endpoints } };
  const rows = q.record_kind === 'progress' ? points : attempts, identity = q.record_kind === 'progress' ? 'event_index' : 'saved_index';
  const sorted = [...rows].sort((left, right) => {
    if (left[q.sort] === null) return right[q.sort] === null ? left[identity] - right[identity] : 1;
    if (right[q.sort] === null) return -1;
    return (left[q.sort] - right[q.sort]) * (q.order === 'desc' ? -1 : 1) || left[identity] - right[identity];
  });
  const stages = noRecords ? [] : legacy ? [{ phase: 'local_search', start_elapsed_ms: null, end_elapsed_ms: null, elapsed_ms: null, visits: null, evaluated: null, accepted: null, strict_improvements: null, rejected: null, stop_reason: 'reserved_for_later_phases', status: 'skipped' }]
    : [{ phase: 'baseline', start_elapsed_ms: 0, end_elapsed_ms: 50, elapsed_ms: 50, visits: 1, evaluated: 3, accepted: 1, strict_improvements: 0, rejected: 2, stop_reason: 'baseline_scheduled', status: 'completed' },
      { phase: 'local_search', start_elapsed_ms: 75, end_elapsed_ms: 1100, elapsed_ms: 1025, visits: 1, evaluated: 42, accepted: 19, strict_improvements: 9, rejected: 23, stop_reason: 'search_exhausted', status: 'completed' }];
  return { ...clone(payload), data: { run_ref: runRef, capture_ref: runRef, scope, baseline, candidates: members, candidate: clone(candidate), source, summary, objective: clone(processObjective), progress, attempts, stages,
    items: clone(sorted.slice((q.page - 1) * q.size, q.page * q.size)), page: { number: q.page, size: q.size, total: rows.length, has_more: q.page * q.size < rows.length },
    filters: { section: 'process', process_candidate_ref: anchor, record_kind: q.record_kind, sort: q.sort, order: q.order }, process_version: 'decision-process-v1' } };
}
function processReadContracts() {
  const q = { ...query, process_candidate_ref: recommended }, value = processFixture(q), read = result => API.processDetails(result, runRef, q);
  assert.strictEqual(read(value), value.data); assert.equal(value.data.scope.selected_candidate_ref, third); assert.equal(value.data.candidate.candidate_ref, recommended);
  for (const kind of ['attempts', 'progress']) {
    const selected = { ...q, record_kind: kind }, one = processFixture(selected), two = processFixture({ ...selected, page: 2, snapshot_ref: snapshot }), all = processFixture({ ...selected, size: 50 });
    for (const [response, paging] of [[one, {}], [two, { page: 2, snapshot_ref: snapshot }], [all, { size: 50 }]]) assert.strictEqual(API.processDetails(response, runRef, { ...selected, ...paging }), response.data);
    assert.deepEqual([...one.data.items, ...two.data.items, ...(kind === 'progress' ? processFixture({ ...selected, page: 3 }).data.items : [])], all.data.items, '过程叶按类别完整分页，20与50同源无重复');
    assert.equal(one.data.progress.points.length, all.data.progress.points.length, '曲线点保留完整采样，与单叶页容量分开');
  }
  for (const [change, message] of [
    [v => { v.data.scope.selected_candidate_ref = recommended; }, '过程锚点保留原第三查看'],
    [v => { v.data.scope.range_end = '2026-10-06T00:00:00'; }, '过程保留共同时间窗'],
    [v => { v.data.source.candidate_ref = third; }, '来源属于过程锚点'],
    [v => { v.data.source.source_candidate_ref = third; }, '求解owner属于同次真实保存来源'],
    [v => { v.data.source.profile.seed = '7'; }, '公开profile保持字段真实类型'],
    [v => { v.data.source.profile.raw_solver_state = {}; }, 'profile只接受公开求解字段'],
    [v => { v.data.summary.solver_counts.accepted += 1; }, '摘要计数与候选同源'],
    [v => { v.data.summary.rejection_summary.schedule_incomplete += 1; }, '拒绝原因与来源同源'],
    [v => { v.data.progress.points[0].source_candidate_ref = first; }, '每个点保持永久owner'],
    [v => { v.data.progress.points[0].evaluation_scope = { incomplete_batch_ids: ['B1', 'B1'] }; }, '评价集合成员按真实唯一业务身份表示'],
    [v => { v.data.items[0].source_candidate_ref = first; }, '代表尝试保持永久owner'],
    [v => { v.data.progress.sampling.event_total_count += 1; }, '曲线与摘要采样同源'],
    [v => { v.data.summary.retained_point_count += 1; }, '采样数匹配保存点'],
    [v => { v.data.progress.coverage.endpoint_coverage.final = false; }, '终点覆盖取保存flags'],
    [v => { v.data.filters.record_kind = 'progress'; }, '响应类别匹配当前单叶'],
    [v => { v.data.page.number = 2; }, '响应页码匹配当前请求'],
    [v => { v.data.process_version = 'decision-process-v0'; }, '公共过程版本固定'],
    [v => { v.data.source.evidence_version = 'optimization-process-v0'; }, '新证据版本固定']
  ]) rejected(value, change, read, message);
  const page2 = processFixture({ ...q, page: 2, snapshot_ref: snapshot });
  rejected(page2, v => { v.meta.snapshot_ref = 't'.repeat(32); }, v => API.processDetails(v, runRef, { ...q, page: 2, snapshot_ref: snapshot }), '翻页继续同一过程快照');
  const progressQuery = { ...q, record_kind: 'progress' }, progress = processFixture(progressQuery);
  rejected(progress, v => { v.data.items[0].primary_value += 1; }, v => API.processDetails(v, runRef, progressQuery), '分页数值与SVG全量点来自同一保存值');
  const reused = processFixture({ ...q, process_candidate_ref: third });
  assert.strictEqual(API.processDetails(reused, runRef, { ...q, process_candidate_ref: third }), reused.data);
  assert.equal(reused.data.source.source_candidate_ref, first); assert.deepEqual(reused.data.summary.own_counts, processCounts(0));
  assert(reused.data.progress.points.every(point => point.source_candidate_ref === first), '复用兄弟保留源求解点身份，当前查看仍第三');
  rejected(reused, v => { v.data.candidate.own_counts.evaluated = 1; }, v => API.processDetails(v, runRef, { ...q, process_candidate_ref: third }), '复用成员自身求解计数为保存零');
  const legacyQuery = { ...q, process_candidate_ref: legacyProcessRef }, legacy = processFixture(legacyQuery);
  assert.strictEqual(API.processDetails(legacy, runRef, legacyQuery), legacy.data); assert.equal(legacy.data.progress.mode, 'discrete');
  assert.equal(legacy.data.summary.legacy_best_updates, 2); assert.equal(legacy.data.summary.solver_counts.strict_improvements, null); assert.equal(legacy.data.items[1].accepted, null);
  assert.equal(legacy.data.items[1].primary_value, null); assert.equal(legacy.data.candidate.final_metrics.makespan_hours, null); assert.equal(legacy.data.summary.own_elapsed_ms, null);
  rejected(legacy, v => { v.data.summary.sampling.event_total_count = 2; v.data.progress.sampling.event_total_count = 2; }, v => API.processDetails(v, runRef, legacyQuery), '旧记录保留未记录的全过程事件总量');
  for (const ref of [notStartedProcessRef, budgetProcessRef, failedProcessRef]) {
    const memberQuery = { ...q, process_candidate_ref: ref }, member = processFixture(memberQuery);
    assert.strictEqual(API.processDetails(member, runRef, memberQuery), member.data); assert.equal(member.data.progress.mode, 'none');
    assert.equal(member.data.source.available, ref === notStartedProcessRef);
    assert.equal(member.data.summary.solver_counts.evaluated, ref === notStartedProcessRef ? 0 : null, '保存未开始的零与失败/预算跳过的未知求解量区分');
  }
  const allFailed = processFixture({ selected_candidate_ref: null, reference_candidate_ref: null }, { nullViewer: true, allFailed: true });
  assert.strictEqual(API.processDetails(allFailed, runRef, {}), allFailed.data); assert.equal(allFailed.data.scope.selected_candidate_ref, null);
  assert.equal(allFailed.data.candidate.candidate_ref, failedProcessRef, '没有可查看结果时仍可读取失败成员的保存过程状态');
  assert.equal(API.processScope(runRef, { ...q, record_kind: 'progress' }).sort, 'elapsed_ms');
  for (const invalid of [{ size: 10 }, { page: 0 }, { record_kind: 'other' }, { record_kind: 'attempts', sort: 'event_index' }]) assert.throws(() => API.processScope(runRef, { ...q, ...invalid }), /.+/);
}
function attemptComparisonContracts() {
  const q = { ...query, process_candidate_ref: recommended }, value = processFixture(q), read = result => API.processDetails(result, runRef, q);
  const metricKeys = ['failed_ops', ...processMetricKeys], metrics = amount => Object.fromEntries(metricKeys.map(key => [key, amount])), sameCompletion = clone(value.data.progress.points[0].completion);
  value.data.items.slice(0, 6).forEach((row, index) => {
    row.failed_ops = 0; row.score[0] = 0; row.candidate_origin = 'local_search'; row.weight_profile_slug = 'balanced'; row.event_index = 101 + index; row.verified = true;
    row.comparison = { kind: 'incumbent', state: 'comparable', objective_name: value.data.objective.name, objective_scope: row.objective_scope, reference_scope: row.objective_scope,
      reference_score: [0, row.primary_value], reference_metrics: { failed_ops: 0, ...clone(row.metrics) }, reference_completion: clone(row.completion), metric_deltas: metrics(0) };
  });
  const [improved, tie, partial, unknown, unverified, initial] = value.data.items;
  improved.accepted = true; improved.strict_improved = true; improved.comparison.reference_score[1] = 2; improved.comparison.reference_metrics.total_tardiness_hours = 2; improved.comparison.metric_deltas.total_tardiness_hours = -2;
  tie.accepted = true; tie.strict_improved = false; tie.comparison.kind = 'current_solution';
  partial.objective_scope = partial.comparison.objective_scope = 'completed_batches_only'; partial.completion = { ...clone(sameCompletion), missing_operation_count: 1, incomplete_batch_count: 1 };
  partial.accepted = true; partial.strict_improved = null; Object.assign(partial.comparison, { kind: 'reference_capture', state: 'different_coverage', reference_scope: 'all_batches', reference_completion: clone(sameCompletion), metric_deltas: metrics(null) });
  unknown.objective_scope = unknown.comparison.objective_scope = 'unknown'; unknown.primary_value = null; unknown.score = [0, null]; unknown.metrics = processMetrics(null); unknown.completion = processCompletion(null);
  unknown.accepted = null; unknown.verified = null; unknown.strict_improved = null; Object.assign(unknown.comparison, { state: 'unavailable', reference_scope: 'all_batches', metric_deltas: metrics(null) });
  unverified.accepted = false; unverified.verified = false; unverified.strict_improved = null; Object.assign(unverified.comparison, { kind: 'current_solution', state: 'unverified', metric_deltas: metrics(null) });
  initial.accepted = true; initial.strict_improved = null; Object.assign(initial.comparison, { kind: 'none', state: 'no_reference', reference_scope: null, reference_score: null, reference_metrics: null, reference_completion: null, metric_deltas: metrics(null) });
  value.data.attempts = value.data.attempts.map(row => clone(value.data.items.find(saved => saved.saved_index === row.saved_index) || row));
  const untouched = clone(value);
  assert.strictEqual(read(value), value.data);
  assert.equal(improved.comparison.metric_deltas.total_tardiness_hours, -2, '保存的当时参考差值允许真实负值');
  assert.equal(tie.accepted, true); assert.equal(tie.strict_improved, false); assert.deepEqual(tie.score, tie.comparison.reference_score, '同分接受保留accepted与strict不同职责');
  assert(Object.values(tie.comparison.metric_deltas).every(delta => delta === 0));
  for (const row of [partial, unknown, unverified, initial]) {
    assert.equal(row.strict_improved, null); assert(Object.values(row.comparison.metric_deltas).every(delta => delta === null), '覆盖不同、未知、未核验或无参考保留未知改善与差值');
  }
  assert.equal(unknown.primary_value, null); assert.deepEqual(unknown.score, [0, null]); assert.deepEqual(unknown.comparison.reference_score, [0, 3], '未知自身目标保留当时参考解事实');
  assert(value.data.items.slice(0, 6).every(row => row.event_index !== row.rank && !value.data.progress.points.some(point => point.event_index === row.event_index)), '保存尝试事件ID与排名、采样保留点分别表达，未入采样仍可查看');
  assert(value.data.items.every(row => row.source_candidate_ref === recommended));
  const rawRecords = window.RunDecisionProcess.Records({ data: value.data }), rawRows = nodes(rawRecords).filter(node => node.props['data-process-attempt']), rawComparisons = nodes(rawRecords).filter(node => node.props['data-process-attempt-comparison']);
  assert.equal(rawRows.length, value.data.items.length); assert.equal(rawComparisons.length, 6, '只为已保存当时比较的尝试生成详情行');
  rawComparisons.forEach((row, index) => {
    assert.equal(row.props['data-process-attempt-comparison'], value.data.items[index].saved_index); assert.equal(row.children.length, 1); assert.equal(row.children[0].props.colSpan, 5);
    assert.strictEqual(nodes(row).find(node => node.type === window.RunDecisionProcess.AttemptComparison).props.row, value.data.items[index], '独立整行详情绑定实际保存尝试，保留接受、核验和参考事实');
  });
  const rendered = expand(rawRecords), renderedRows = nodes(rendered).filter(node => node.props['data-process-attempt']);
  renderedRows.slice(0, 6).forEach((row, index) => {
    assert.equal(row.props['data-process-attempt-event'], value.data.items[index].event_index);
    assert.equal(text(row.children[4].children[0]).trim(), value.data.items[index].accepted === null ? '—' : value.data.items[index].accepted ? '已留作继续搜索' : '未留作继续搜索', '搜索保留结果直接绑定accepted，独立于评分改善');
    assert(nodes(row).some(node => node.props.title === String(value.data.items[index].elapsed_ms) + ' ms'), '累计耗时读取原保存时刻');
    const comparisonRow = nodes(rendered).find(node => node.props['data-process-attempt-comparison'] === value.data.items[index].saved_index), metricRow = nodes(comparisonRow).find(node => node.props['data-attempt-comparison-metric'] === 'total_tardiness_hours');
    assert.equal(metricRow.children[3].props.title, value.data.items[index].comparison.metric_deltas.total_tardiness_hours === null ? undefined : String(value.data.items[index].comparison.metric_deltas.total_tardiness_hours), '原生比较详情保留signed差值与未知');
  });
  assert.notEqual(text(renderedRows[1].children[4].children[2]).trim(), '—', '已保存的同分未改善false保持已知状态');
  for (const [change, message] of [
    [v => { v.data.items[0].event_index = '101'; }, '事件编号保留数值类型'],
    [v => { v.data.items[0].strict_improved = 'true'; }, '严格改善保留布尔或未知'],
    [v => { v.data.items[0].comparison.reference_score[0] = -1; }, '参考评分各分量非负或明确缺项'],
    [v => { v.data.items[0].comparison.metric_deltas.total_tardiness_hours = '-2'; }, '差值保留signed数值类型'],
    [v => { v.data.items[0].comparison.reference_completion.expected_operation_count = '3'; }, '参考完成数量采用共同数值协议'],
    [v => { v.data.items[0].comparison.reference_metrics.internal_debug = 1; }, '参考指标仅公开六项'],
    [v => { v.data.items[0].comparison.state = 'accepted'; }, '比较状态与接受状态分别表达']
  ]) rejected(value, change, read, message);
  assert.deepEqual(clone(value), untouched, '读取当时参考、严格改善与差值保留全部原保存事实');
  const legacyQuery = { ...q, process_candidate_ref: legacyProcessRef }, legacy = processFixture(legacyQuery);
  assert.strictEqual(API.processDetails(legacy, runRef, legacyQuery), legacy.data);
  for (const key of ['candidate_origin', 'weight_profile_slug', 'event_index', 'verified', 'strict_improved', 'comparison']) assert.equal(legacy.data.items[0][key], null, '旧尝试未记录的新字段保持null：' + key);
  return value;
}
function processEvaluationScopeContracts() {
  const scopes = [
    { value: 'all_batches', clues: ['全部', '批次'], primary: 0 },
    { value: 'completed_batches_only', clues: ['工序已排齐', '批次'], primary: 0 },
    { value: 'unknown', clues: ['未知'], primary: null },
    { value: null, clues: ['未记录'], primary: null }
  ];
  const q = { ...query, process_candidate_ref: legacyProcessRef, record_kind: 'progress' }, saved = processFixture(q);
  const sourcePoint = saved.data.progress.points[0];
  saved.data.progress.points = scopes.map((scope, index) => ({ ...clone(sourcePoint), event_index: index + 1, elapsed_ms: index * 50, primary_value: scope.primary, objective_scope: scope.value,
    score: [3, scope.primary], completion: scope.primary === null ? processCompletion(null) : { expected_operation_count: 3, missing_operation_count: index === 1 ? 2 : 0, unexpected_result_count: 0, complete_batch_count: 1, incomplete_batch_count: index === 1 ? 2 : 0 } }));
  saved.data.items = clone(saved.data.progress.points); saved.data.page.total = 4;
  saved.data.summary.retained_point_count = saved.data.summary.sampling.retained_point_count = saved.data.progress.sampling.retained_point_count = 4;
  const untouched = clone(saved);
  assert.strictEqual(API.processDetails(saved, runRef, q), saved.data, '旧完整子集的合法零和unknown投影null都保持可读');
  assert.equal(saved.data.progress.points[1].primary_value, 0); assert.equal(saved.data.candidate.final_metrics.total_tardiness_hours, null, '子集主值保留零，候选全业务统计缺项保持null');
  const attemptsQuery = { ...q, record_kind: 'attempts' }, attempts = processFixture(attemptsQuery), sourceAttempt = attempts.data.items[0];
  attempts.data.items = scopes.map((scope, index) => ({ ...clone(sourceAttempt), saved_index: index + 1, primary_value: scope.primary, objective_scope: scope.value, score: [3, scope.primary],
    metrics: { ...clone(sourceAttempt.metrics), total_tardiness_hours: scope.primary }, completion: clone(saved.data.progress.points[index].completion) }));
  attempts.data.summary.saved_attempt_count = attempts.data.page.total = 4;
  attempts.data.attempts = clone(attempts.data.items);
  const untouchedAttempts = clone(attempts);
  assert.strictEqual(API.processDetails(attempts, runRef, attemptsQuery), attempts.data);
  for (const response of [saved, attempts]) {
    const table = expand(h(window.RunDecisionProcess.Records, { data: response.data }));
    const rows = nodes(table).filter(node => node.props['data-process-point'] || node.props['data-process-attempt']);
    assert.equal(rows.length, 4);
    rows.forEach((row, index) => {
      const primaryCell = visibleText(row.children[2]);
      for (const clue of scopes[index].clues) assert(primaryCell.includes(clue), '主值同行保留实际评价范围：' + scopes[index].value);
      if (scopes[index].primary === 0) assert(primaryCell.includes('0') && primaryCell.includes('小时'), '完整子集合法零保持主值与单位');
      else { const primary = row.children[2].children[0]; assert.equal(text(primary).trim(), '—'); assert.equal(primary.props.title, undefined, '未知目标值保持缺项，评分哨兵不进入业务主值'); }
    });
  }
  const evaluated = expand(h(window.RunDecisionProcess.Completion, { value: saved.data.progress.points[1].completion }));
  const completionFacts = evaluated.children.find(node => node.type === 'details'), operationSummary = text(completionFacts.children.find(node => node.type === 'summary')), batchSummary = text(evaluated.children.find(node => node.type === 'small'));
  assert(operationSummary.includes('本次参与计算') && operationSummary.includes('3') && operationSummary.includes('2'), '应排3道与未安排2道明确指向本次计算工序');
  assert(batchSummary.includes('本次计算范围') && batchSummary.includes('1') && batchSummary.includes('2'), '已排齐1批与未排齐2批属于本次计算范围');
  assert.deepEqual(nodes(completionFacts).filter(node => node.type === 'dd').map(node => node.props.title), processCompletionKeys.map(key => String(saved.data.progress.points[1].completion[key])), '完整五项完成数量含正常0保留原值可查');
  const missingCompletion = expand(h(window.RunDecisionProcess.Completion, { value: saved.data.progress.points[2].completion }));
  assert(nodes(missingCompletion).filter(node => node.type === 'dd').every(node => node.props.title === undefined && text(node).trim() === '—'), '完成数量null保留缺项且有原生资料入口');
  const catalog = expand(h(window.RunDecisionProcess.CandidateTable, { data: saved.data, overview: data, anchorRef: legacyProcessRef, onAnchor() {} }));
  const member = nodes(catalog).find(node => node.props['data-process-candidate'] === legacyProcessRef), statistics = nodes(member.children[3]).find(node => node.type === 'details' && node.props.className === 'rd-process-facts');
  assert(visibleText(statistics).includes('计算') && visibleText(statistics).includes('统计'), '原生统计入口保留计算保存值的明确职责');
  assert.equal(nodes(statistics).filter(node => node.type === 'dd').length, processMetricKeys.length);
  const state = hooks(), local = { ...window };
  for (const output of compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources: [{ path: 'RunDecisionProcessChart.jsx', code: fs.readFileSync(path.join(app, 'RunDecisionProcessChart.jsx'), 'utf8') }] }).outputs)
    vm.runInNewContext(output.code, { React: state.React, window: local });
  let tree;
  const render = () => { tree = state.render(() => expand(local.RunDecisionProcessChart.Chart({ progress: saved.data.progress, objective: saved.data.objective }))); };
  render(); const circles = nodes(tree).filter(node => node.type === 'circle');
  assert.deepEqual(circles.map(node => node.props['data-primary-value']), [0, 0], '图表保留全部范围零与子集零，未知点保持无坐标');
  circles.forEach((circle, index) => { for (const clue of scopes[index].clues) assert(text(circle).includes(clue), '点详情与坐标原值同时保留评价范围'); });
  for (const scope of scopes) {
    const announcement = text(nodes(tree).find(node => node.props['aria-live'] === 'polite'));
    for (const clue of scope.clues) assert(announcement.includes(clue), '键盘播报携带所选保存点的评价范围');
    if (scope.primary === 0) assert(announcement.includes('算法拖期小计 0 小时'));
    nodes(tree).find(node => node.type === 'svg').props.onKeyDown({ key: 'ArrowRight', preventDefault() {} }); render();
  }
  assert.deepEqual(clone(saved), untouched); assert.deepEqual(clone(attempts), untouchedAttempts, '范围展示保留原DTO、主值、算法指标与保存评分');
}
function processChartContracts() {
  const chart = window.RunDecisionProcessChart, base = { source_candidate_ref: first, event_index: 0, elapsed_ms: 0, phase: 'baseline', phase_visit: 0, segment: 0, flags: [], score: [7, 99], primary_value: 0,
    objective_scope: 'all_batches', evaluation_scope: { incomplete_batch_ids: [] }, completion: processCompletion(0), verified: true };
  const phases = ['profiles', 'elite_repair', 'iterated_greedy'], stops = ['disabled', 'stages_exhausted', 'graph_ready_uses_graph_candidate_phase'];
  const savedStages = phases.map((phase, index) => ({ ...processFixture().data.stages[0], phase, stop_reason: stops[index] })), untouchedStages = clone(savedStages);
  const stageTree = expand(h(window.RunDecisionProcess.Stages, { values: savedStages })), stageRows = nodes(stageTree).filter(row => row.props['data-process-phase']);
  stageRows.forEach((row, index) => {
    assert.notEqual(chart.phaseText(phases[index]), chart.phaseText('future_phase')); assert(text(row.children[0]).includes(chart.phaseText(phases[index])), '实际保存阶段使用共同中文映射');
    assert.notEqual(text(row.children[4]).trim(), '其他停止原因'); assert(!text(row.children[4]).includes(stops[index]), '已知停止原因中文显示');
    assert.deepEqual(clone(nodes(row.children[4]).find(node => node.type === 'reference').props.entries), { '搜索阶段': phases[index], '停止原因': stops[index] }, '阶段与停止原码仍保存在编号资料');
  });
  assert.deepEqual(clone(savedStages), untouchedStages);
  const rejection = expand(h(window.RunDecisionProcess.Rejections, { values: { no_strict_improvement: 28 } }));
  assert(!text(rejection).includes('no_strict_improvement')); assert(nodes(rejection).some(row => row.type === 'reference' && row.props.entries['保存原因码'] === 'no_strict_improvement'), '拒绝原因中文显示且保留原码');
  const pair = [clone(base), { ...clone(base), event_index: 1, elapsed_ms: 10, primary_value: 2 }], before = clone(pair);
  const groups = chart.segments({ mode: 'curve', points: pair });
  assert.equal(groups.length, 1); assert.strictEqual(groups[0][0], pair[0]); assert.strictEqual(groups[0][1], pair[1], '零时间、零主值、零完成数有效，并保留原点');
  for (const key of ['source_candidate_ref', 'objective_scope']) {
    const different = clone(pair); different[1][key] = typeof different[1][key] === 'number' ? 1 : 'changed';
    assert.equal(chart.segments({ mode: 'curve', points: different }).length, 0, '真实来源/阶段/口径变化断线：' + key);
    const unknown = clone(pair); unknown.forEach(point => { point[key] = null; });
    assert.equal(chart.segments({ mode: 'curve', points: unknown }).length, 0, '共同null仍是未知：' + key);
  }
  for (const key of ['phase', 'phase_visit', 'segment']) {
    const changedStage = clone(pair); changedStage[1][key] = typeof changedStage[1][key] === 'number' ? 1 : 'local_search';
    assert.equal(chart.segments({ mode: 'curve', points: changedStage }).length, 1, '同一保留方案跨搜索阶段与尝试分段继续：' + key);
  }
  const partialPair = pair.map(point => ({ ...clone(point), phase: 'profiles', phase_visit: 1, objective_scope: 'completed_batches_only', completion: { expected_operation_count: 3, missing_operation_count: 1, unexpected_result_count: 0, complete_batch_count: 1, incomplete_batch_count: 1 } }));
  partialPair[0].segment = 1; partialPair[0].evaluation_scope = { incomplete_batch_ids: ['B1'] };
  partialPair[1].segment = 2; partialPair[1].evaluation_scope = { incomplete_batch_ids: ['B2'] };
  assert.equal(chart.segments({ mode: 'curve', points: partialPair }).length, 0, '同阶段/visit与相同完成计数下，真实评价成员B1→B2保持断线');
  assert(chart.markers({ mode: 'curve', points: partialPair })[0].changes.includes('evaluation_scope'), '真实评价成员变化标明独立于搜索阶段的边界');
  const missingMembers = partialPair.map(point => ({ ...clone(point), evaluation_scope: null }));
  assert.equal(chart.segments({ mode: 'curve', points: missingMembers }).length, 0, '旧部分评价点缺成员身份时，只保留离散坐标，不据相同非零未排批次计数连接');
  const missingMemberTree = expand(h(chart.Chart, { progress: { mode: 'curve', points: missingMembers, sampling: { event_total_count: 2 } }, objective: processObjective }));
  assert(nodes(missingMemberTree).some(node => node.props['data-process-scope-missing'] !== undefined && text(node).includes('评价集合未记录')) && nodes(missingMemberTree).filter(node => node.type === 'circle').length === 2, '保存事件条数完整仍独立提示评价集合缺项，真实坐标与原值保留');
  assert.equal(chart.stepPath(pair, point => point.elapsed_ms, point => point.primary_value), 'M0.000 0.000 H10.000 V2.000', '真实保存事件使用横后竖的阶梯，不画斜线');
  const unknownScope = clone(pair); unknownScope.forEach(point => { point.objective_scope = 'unknown'; });
  assert.equal(chart.segments({ mode: 'curve', points: unknownScope }).length, 0);
  for (const key of processCompletionKeys) {
    const incomplete = clone(pair); incomplete[1].completion[key] = 1;
    assert.equal(chart.segments({ mode: 'curve', points: incomplete }).length, 0, '完整完成集合变化断线：' + key);
    incomplete.forEach(point => { point.completion[key] = null; });
    assert.equal(chart.segments({ mode: 'curve', points: incomplete }).length, 0, '完成数缺项断线：' + key);
  }
  for (const key of ['elapsed_ms', 'primary_value', 'verified']) {
    const unknown = { ...clone(base), event_index: 1, [key]: null }, after = { ...clone(base), event_index: 2, elapsed_ms: 20, primary_value: 4 };
    assert.equal(chart.segments({ mode: 'curve', points: [pair[0], unknown, after] }).length, 0, '不跨过缺项点连接：' + key);
  }
  assert.equal(chart.segments({ mode: 'discrete', points: pair }).length, 0, '旧离散记录始终只画点');
  const decreasingTime = [pair[1], pair[0]], saved = clone(decreasingTime);
  chart.segments({ mode: 'curve', points: decreasingTime }); assert.deepEqual(clone(decreasingTime), saved, '曲线分析保留实际保存顺序'); assert.deepEqual(clone(pair), before);
  const changed = { ...clone(pair[1]), phase: 'local_search', segment: 1, completion: { ...processCompletion(0), complete_batch_count: 1 } };
  const boundary = chart.markers({ mode: 'curve', points: [pair[0], changed] });
  assert.equal(boundary.length, 1); assert.strictEqual(boundary[0].before, pair[0]); assert.strictEqual(boundary[0].point, changed);
  assert.deepEqual(clone(boundary[0].changes), ['phase', 'segment', 'completion'], '边界来自相邻保存点的已知阶段、分段与完整集合变化');
  const unknownBoundary = { ...clone(changed), elapsed_ms: null };
  assert.equal(chart.markers({ mode: 'curve', points: [pair[0], unknownBoundary] }).length, 0, '未知耗时只断线，不造阶段坐标');
  const scopeOnly = { ...clone(pair[1]), objective_scope: 'completed_batches' };
  assert.equal(chart.markers({ mode: 'curve', points: [pair[0], scopeOnly] }).length, 0, '目标口径单独变化不冒充阶段边界');
  const markedPoints = [clone(pair[0]), { ...changed, flags: ['first_expected_complete', 'final', 'strict_improvement', 'segment_start'] }]; markedPoints[0].flags = ['first_valid'];
  const markedTree = expand(h(chart.Chart, { progress: { mode: 'curve', points: markedPoints }, objective: processObjective }));
  const marker = nodes(markedTree).find(node => node.props.className === 'rd-process-phase-marker');
  assert(marker && marker.props['data-process-phase'] === 'local_search');
  assert.equal(marker.props.x1, nodes(markedTree).find(node => node.type === 'circle' && node.props['data-progress-event-index'] === 1).props.cx, '阶段线使用保存点的实际累计耗时坐标');
  const markedCircle = nodes(markedTree).find(node => node.type === 'circle' && node.props['data-progress-event-index'] === 1);
  assert.equal(markedCircle.props['data-progress-flags'], markedPoints[1].flags.join(' '));
  for (const flag of markedPoints[1].flags) assert(text(markedCircle).includes(chart.flagLabels[flag]), '实际保存标记进入可读详情：' + flag);
  const tree = expand(h(chart.Chart, { progress: { mode: 'curve', points: pair }, objective: processObjective }));
  const circles = nodes(tree).filter(node => node.type === 'circle');
  assert.deepEqual(circles.map(node => node.props['data-primary-value']), [0, 2]); assert.equal(nodes(tree).filter(node => node.type === 'path' && node.props.className === 'rd-process-line').length, 1);
  assert(circles.every(node => text(node).includes('算法拖期小计') && !text(node).includes('算法拖期小计 7')), 'SVG使用明确主值，score[0]失败数保留在评分详情');
  const state = hooks(); let keyboardTree;
  const local = { ...window }; for (const output of compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources: [{ path: 'RunDecisionProcessChart.jsx', code: fs.readFileSync(path.join(app, 'RunDecisionProcessChart.jsx'), 'utf8') }] }).outputs)
    vm.runInNewContext(output.code, { React: state.React, window: local });
  const props = { progress: { mode: 'discrete', points: [pair[0], { ...pair[1], primary_value: null, elapsed_ms: null }] }, objective: processObjective };
  const render = () => { keyboardTree = state.render(() => expand(local.RunDecisionProcessChart.Chart(props))); };
  render(); let prevented = 0; nodes(keyboardTree).find(node => node.type === 'svg').props.onKeyDown({ key: 'End', preventDefault: () => prevented++ }); render();
  const announced = text(nodes(keyboardTree).find(node => node.props['aria-live'] === 'polite'));
  assert.equal(prevented, 1); assert(announced.includes('事件 1') && announced.includes('算法拖期小计 —') && announced.includes('累计计算 —'), '键盘仍能选择无坐标的缺项点并播报真实缺项');
  assert.equal(nodes(keyboardTree).filter(node => node.type === 'circle').length, 1, '部分缺耗时只定位已知横坐标');
  const timeless = pair.map(point => ({ ...clone(point), elapsed_ms: null, verified: null }));
  const timelessTree = expand(h(chart.Chart, { progress: { mode: 'discrete', points: timeless }, objective: processObjective }));
  assert.equal(timelessTree.props['data-progress-axis'], 'event_index'); assert.equal(nodes(timelessTree).filter(node => node.type === 'circle').length, 2);
  assert(text(timelessTree).includes('已保存事件顺序') && !nodes(timelessTree).some(node => node.type === 'path' && node.props.className === 'rd-process-line'), '全缺耗时只显示明确事件顺序与离散点');
  props.objective = { ...processObjective, score_fields: [...processObjective.score_fields, { index: 2, key: 'makespan_hours', label: '安排时长', unit: '小时', direction: 'lower' }] };
  props.elapsedMs = 1000;
  props.progress = { mode: 'curve', sampling: { event_total_count: 3 }, points: [{ ...clone(base), flags: ['first_valid'], primary_value: 10, score: [0, 10, 20] }, { ...clone(base), event_index: 10, elapsed_ms: 200, flags: ['final', 'strict_improvement'], primary_value: 8, score: [0, 8, 25] }] };
  props.attempts = [{ ...clone(props.progress.points[1]), saved_index: 13, elapsed_ms: 500, score: [0, 9, 27] }];
  render(); nodes(keyboardTree).find(node => node.props['aria-label'] === '计算过程观察指标').props.onChange({ target: { value: 'makespan_hours' } }); render();
  const progressCircles = () => nodes(keyboardTree).filter(node => node.props['data-progress-event-index'] !== undefined);
  assert.deepEqual(progressCircles().map(node => node.props['data-metric-value']), [20, 25], '切次要指标沿同一方案事件，保留真实反向增加');
  assert(nodes(keyboardTree).some(node => node.type === 'path' && node.props['data-sampled'] === true) && text(keyboardTree).replace(/\s+/g, ' ').includes('已保存 2 / 3 个事件'), '采样缺口只按真实保存总量表达，事件索引跳号不补点');
  let hoveredSvg = nodes(keyboardTree).find(node => node.type === 'svg'); hoveredSvg.props.ref.current = { getBoundingClientRect: () => ({ left: 0, width: 800 }) };
  hoveredSvg.props.onPointerMove({ clientX: 700 }); render();
  const selectedCircle = progressCircles().find(node => node.props['data-selected']), guide = nodes(keyboardTree).find(node => node.props.className === 'rd-process-guide');
  assert.equal(selectedCircle.props['data-progress-event-index'], 10); assert.equal(guide.props.x1, selectedCircle.props.cx, '采样悬停的标记和说明吸附真实保存点，不使用鼠标时间捏造值');
  nodes(keyboardTree).find(node => node.type === 'button' && text(node).includes('改善阶段')).props.onClick(); render();
  assert.equal(keyboardTree.props['data-process-window'], 'improvements');
  nodes(keyboardTree).find(node => node.type === 'button' && text(node).includes('全过程')).props.onClick(); render();
  nodes(keyboardTree).find(node => node.type === 'input' && node.props.type === 'checkbox').props.onChange({ target: { checked: true } }); render();
  assert.equal(nodes(keyboardTree).filter(node => node.props['data-process-attempt-index'] === 13).length, 1, '代表尝试取完整同源列表，与下表类别/分页独立');
  props.elapsedMs = 251; props.attempts = [];
  props.progress = { mode: 'curve', sampling: { event_total_count: 2 }, points: [{ ...clone(base), event_index: 1, elapsed_ms: 30, flags: ['first_valid'], primary_value: 12, score: [0, 12, 48] }, { ...clone(base), event_index: 9, elapsed_ms: 251, flags: ['final'], primary_value: 12, score: [0, 12, 48] }] };
  render(); const unchangedPath = nodes(keyboardTree).find(node => node.type === 'path' && node.props.className === 'rd-process-line').props.d;
  const unavailableImprovement = nodes(keyboardTree).find(node => node.type === 'button' && text(node).includes('改善阶段'));
  assert.equal(unavailableImprovement.props.disabled, true, '无保存改善记录时保留全过程，改善阶段入口明确不可用');
  unavailableImprovement.props.onClick(); render();
  assert.equal(keyboardTree.props['data-process-window'], 'full'); assert.equal(nodes(keyboardTree).find(node => node.type === 'path' && node.props.className === 'rd-process-line').props.d, unchangedPath, '30ms/251ms相同结果的真实平坦线保留，不因45ms单点窗口消失');
  assert.deepEqual(progressCircles().map(node => node.props['data-progress-event-index']), [1, 9], '无改善阅读保留原两事件，不补造中间点');
  const records = processFixture({ process_candidate_ref: first, record_kind: 'progress' });
  const table = expand(h(window.RunDecisionProcess.Records, { data: records.data }));
  const values = nodes(table).filter(node => node.props['data-process-point']).map(node => Number(node.props['data-process-point']));
  assert.deepEqual(values, records.data.items.map(row => row.event_index), '等价数据表使用当前分页保存点，原评分只作展开依据');
  const legacy = processFixture({ process_candidate_ref: legacyProcessRef }), legacyTree = expand(h(window.RunDecisionProcess.Records, { data: legacy.data }));
  assert.equal(nodes(legacyTree).filter(node => node.props['data-process-missing'] !== undefined).length, 1, '本页实际缺项集中提示一次');
  assert.equal(nodes(legacyTree).filter(node => node.props['data-process-attempt-comparison']).length, 0, '旧当时比较未保存时不生成空详情入口');
  const legacyRows = nodes(legacyTree).filter(node => node.props['data-process-attempt']);
  legacyRows.forEach(row => assert.equal(text(row.children[4].children[0]).trim(), '—', '旧接受状态保持缺项'));
  assert.equal(text(legacyRows[1].children[2].children[0]).trim(), '—', '旧主值缺项保持明确占位');
  const legacyCoverage = expand(h(window.RunDecisionProcess.Coverage, { data: legacy.data }));
  assert.equal(legacyCoverage.children.filter(node => node && node.type === 'small' && text(node) === legacy.data.source.reason.message).length, 1, '来源与汇总、曲线同一缺项原因只显示一次');
}
async function processPaneContracts() {
  const state = hooks(), calls = [], links = [], local = { ...window, RunDecisionAPI: API };
  for (const name of ['resource-session.js', 'RunDecisionProcessChart.jsx', 'RunDecisionProcess.jsx']) for (const output of compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources: [{ path: name, code: fs.readFileSync(path.join(app, name), 'utf8') }] }).outputs)
    vm.runInNewContext(output.code, { React: state.React, window: local, AbortController, DOMException });
  const props = { result: clone(payload), query: { process_candidate_ref: recommended }, enabled: false, onQuery: value => { props.query = value; }, onSelectCandidate: value => {
    links.push(value); props.result = clone(props.result); props.result.data.scope.selected_candidate_ref = value.candidate_ref; bindRecommendationScope(props.result);
    props.query = { ...props.query, page: 1 }; delete props.query.snapshot_ref;
  },
    adapter: { process: (run, value, signal) => { calls.push({ value: clone(value), signal }); return Promise.resolve(processFixture(value)); } } };
  let tree;
  async function render() { for (let index = 0; index < 3; index++) { tree = state.render(() => expand(local.RunDecisionProcess.Pane(props))); state.flush(); await turns(); } }
  await render(); assert.equal(tree, null); assert.equal(calls.length, 0, '过程面板关闭时不启动reader');
  props.enabled = true; await render(); assert.equal(calls[0].value.selected_candidate_ref, third); assert.equal(calls[0].value.process_candidate_ref, third, '过程锚点由共同当前方案派生');
  nodes(tree).find(node => node.type === 'pager').props.onPage(2); await render();
  assert.equal(calls.at(-1).value.page, 2); assert.equal(calls.at(-1).value.snapshot_ref, snapshot);
  nodes(nodes(tree).find(node => node.props.className === 'rd-process-record-tools')).filter(node => node.type === 'button')[1].props.onClick(); await render();
  assert.equal(calls.at(-1).value.record_kind, 'progress'); assert.equal(calls.at(-1).value.sort, 'elapsed_ms'); assert.equal(calls.at(-1).value.page, 1); assert.equal(calls.at(-1).value.snapshot_ref, undefined);
  assert.equal(nodes(tree).filter(node => node.type === 'circle').length, 45, '切换类别仍画全量保存点，下表独立按20条分页');
  nodes(tree).find(node => node.type === 'pager').props.onPage(2); await render();
  nodes(tree).find(node => node.props['aria-label'] === '优化过程排序').props.onChange({ target: { value: 'event_index' } }); await render();
  assert.equal(calls.at(-1).value.page, 1); assert.equal(calls.at(-1).value.snapshot_ref, undefined);
  nodes(tree).find(node => node.type === 'pager').props.onPage(2); await render();
  nodes(nodes(tree).find(node => node.props['data-process-candidate'] === first)).find(node => node.type === 'button').props.onClick(); await render();
  assert.equal(calls.at(-1).value.process_candidate_ref, first); assert.equal(calls.at(-1).value.page, 1); assert.equal(calls.at(-1).value.snapshot_ref, undefined);
  assert.equal(calls.at(-1).value.selected_candidate_ref, first); assert.equal(calls.at(-1).value.reference_candidate_ref, first); assert.equal(calls.at(-1).value.range_end, range_end);
  assert.equal(props.query.process_candidate_ref, undefined, '过程叶只保留记录筛选，不保存第二条候选选择');
  nodes(tree).find(node => node.props['aria-label'] === '优化过程每页条数').props.onChange({ target: { value: '50' } }); await render();
  assert.equal(calls.at(-1).value.size, 50); assert.equal(nodes(tree).filter(node => node.props['data-process-point']).length, 45);
  const circles = nodes(tree).filter(node => node.type === 'circle'), rows = nodes(tree).filter(node => node.props['data-process-point']);
  rows.forEach((row, index) => {
    const value = circles[index].props['data-primary-value'], primary = nodes(row.children[2]).find(node => node.type === 'span' && node.props.title === String(value));
    assert(primary); assert.equal(text(primary).replace(/\s+/g, ' ').trim(), String(value) + ' 小时', '表格与图表对应同一primary_value');
  });
  assert.equal(links.at(-1).candidate_ref, first, '过程目录选择回调提交同一当前候选');
  props.enabled = false; await render(); assert.equal(tree, null); assert(calls.at(-1).signal.aborted);
  const lateState = hooks(), waiting = [], lateLocal = { ...window, RunDecisionAPI: API };
  for (const name of ['resource-session.js', 'RunDecisionProcessChart.jsx', 'RunDecisionProcess.jsx']) for (const output of compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources: [{ path: name, code: fs.readFileSync(path.join(app, name), 'utf8') }] }).outputs)
    vm.runInNewContext(output.code, { React: lateState.React, window: lateLocal, AbortController, DOMException });
  const lateProps = { ...props, result: clone(payload), enabled: true, query: { process_candidate_ref: recommended }, onQuery: value => { lateProps.query = value; }, onSelectCandidate: value => {
    lateProps.result = clone(lateProps.result); lateProps.result.data.scope.selected_candidate_ref = value.candidate_ref; bindRecommendationScope(lateProps.result);
    lateProps.query = { ...lateProps.query, page: 1 }; delete lateProps.query.snapshot_ref;
  }, adapter: { process: (run, value, signal) => new Promise(resolve => waiting.push({ value, signal, resolve })) } };
  async function lateRender() { for (let index = 0; index < 3; index++) { tree = lateState.render(() => expand(lateLocal.RunDecisionProcess.Pane(lateProps))); lateState.flush(); await turns(); } }
  await lateRender(); nodes(tree).find(node => node.type === 'button' && node.props.icon === 'x').props.onClick(); await lateRender();
  assert(waiting[0].signal.aborted); waiting[0].resolve(processFixture(waiting[0].value)); await lateRender();
  assert(!nodes(tree).some(node => node.props['data-process-candidate']), '取消后迟到响应不回填成员与曲线');
  nodes(tree).find(node => node.type === 'button' && node.props.icon === 'refresh-cw').props.onClick(); await lateRender();
  lateProps.onSelectCandidate(data.candidates[0]); await lateRender();
  assert(waiting[1].signal.aborted); waiting[1].resolve(processFixture(waiting[1].value)); await lateRender();
  assert(!nodes(tree).some(node => node.props['data-process-candidate']), '换锚点后旧候选迟到数据保持清空');
  waiting.at(-1).resolve(processFixture(waiting.at(-1).value)); await lateRender();
  assert.equal(tree.props['data-process-anchor'], first); assert.equal(nodes(tree).filter(node => node.type === 'circle').length, 45);
  const currentProcess = window.RunDecisionProcess;
  const closed = expand(h(D.Workspace, { adapter: { decisionSummary: () => payload, process: () => { throw new Error('关闭的过程不应读取'); } }, initialContext: original }));
  assert(!nodes(closed).some(node => node.props['data-process-anchor']), '默认交期页不读取过程reader');
  window.RunDecisionProcess = { Pane: 'process-pane' };
  const leaf = { open: true, process_candidate_ref: first, record_kind: 'progress', sort: 'event_index', order: 'desc', page: 2, size: 20, snapshot_ref: snapshot };
  const context = { ...original, comparison_tab: 'process', detail_queries: { process: leaf, operations: { page: 3, snapshot_ref: 't'.repeat(32) } } }, targets = [];
  const mainState = hooks(), mainQueries = [], mainLocal = { ...window, RunDecisionCompletion: { Pane: 'completion-pane' } };
  for (const output of compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources: [{ path: 'RunDecisionComparison.jsx', code: fs.readFileSync(path.join(app, 'RunDecisionComparison.jsx'), 'utf8') }] }).outputs)
    vm.runInNewContext(output.code, { React: mainState.React, window: mainLocal, AbortController });
  const mainProps = { initialContext: context, runHistoryReturn, onNavigate: (page, value) => targets.push({ page, value }), renderAdoption: (ref, metadata) => h('adoption', { candidateRef: ref, ...metadata }), adapter: { decisionSummary: (run, value) => {
    mainQueries.push(clone(value)); const next = clone(payload); next.data.scope.selected_candidate_ref = value.selected_candidate_ref || third;
    if (value.comparison_mode === 'admission_official') { next.data.scope = comparisonScope(value); next.data.baseline = clone(officialBaseline); }
    else { next.data.scope.reference.candidate_ref = value.reference_candidate_ref || first; next.data.baseline.candidate_ref = next.data.scope.reference.candidate_ref; next.data.baseline.label = next.data.candidates.find(row => row.candidate_ref === next.data.scope.reference.candidate_ref).label; }
    return bindRecommendationScope(next);
  } } };
  mainProps.adapter.decision = (run, value) => mainProps.adapter.decisionSummary(run, value);
  let main, mainRaw;
  const renderMain = () => { mainRaw = mainState.render(() => mainLocal.RunDecisionComparison.Workspace(mainProps)); main = expand(mainRaw); mainState.flush(); };
  renderMain();
  const legacyReturn = expand(h(D.Workspace, { adapter: { decisionSummary: () => payload }, initialContext: { ...context, comparison_tab: 'overview' } }));
  const normalizedLeaf = { open: true, record_kind: 'progress', sort: 'event_index', order: 'desc', page: 1, size: 20 };
  assert.deepEqual(clone(nodes(legacyReturn).find(node => node.type === 'process-pane').props.query), normalizedLeaf, '旧总览恢复共同候选，保留记录筛选并释放原候选快照');
  nodes(main).find(node => node.type === 'process-pane').props.onSelectCandidate(data.candidates[0]); renderMain();
  assert.equal(mainQueries.at(-1).selected_candidate_ref, first); assert.equal(mainQueries.at(-1).reference_candidate_ref, first);
  assert.equal(nodes(main).find(node => node.type === 'adoption').props.candidateRef, first, '过程选择进入共同工作区，采用对象随之更新');
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
  const pending = { candidate_ref: first, request_key: 'previous-adoption', phase: 'pending', input: { reason: '原采用原因', declared_operator: '原经办人' }, preview: { candidate_ref: first, run_ref: runRef, baseline: { plan_ref: planRef, version: 7 }, task_count: 3, scope_complete: true } }, savedPending = clone(pending);
  for (const candidateCatalog of [[], data.candidates]) {
    const adoptionState = hooks(), adoptionLocal = { ...window, WorkbenchHandlerMemory: { read: () => ({ value: '经办人' }) }, addEventListener() {}, removeEventListener() {},
      RunAdoptionControls: { Button: 'button', Dialog: 'adoption-dialog' }, RunAdoptionAPI: { ref: window.RunCandidateAPI.ref, pending: () => ({ read: () => pending }), lookup: value => value, EVENT: 'adoption-event', PENDING_KEY: 'adoption-pending' } };
    for (const output of compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources: [{ path: 'RunAdoptionAction.jsx', code: fs.readFileSync(path.join(app, 'RunAdoptionAction.jsx'), 'utf8') }] }).outputs)
      vm.runInNewContext(output.code, { React: adoptionState.React, window: adoptionLocal, AbortController, DOMException });
    const adoptionProps = { candidateRef: third, candidateDisplay: { candidate_ref: third, label: data.candidates[2].label }, candidateCatalog, adapter: { lookup: async () => null } };
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
  const calls = [], responses = [], fetcher = async (url, options) => { calls.push({ url: new URL(url, 'http://localhost'), options }); return responses.shift(); }, transport = API.create(fetcher);
  const q = { ...query, process_candidate_ref: first, record_kind: 'progress', sort: 'event_index', order: 'desc' };
  for (const page of [1, 2]) { responses.push({ ok: true, headers: { get: key => key === 'Content-Type' ? 'application/json' : null }, json: async () => processFixture({ ...q, page, snapshot_ref: snapshot }) }); await transport.process(runRef, { ...q, page, snapshot_ref: snapshot }); }
  assert.equal(calls[0].url.pathname, '/api/workbench/v1/scheduling/runs/' + runRef + '/decision/process');
  assert.equal(calls[1].url.searchParams.get('snapshot_ref'), snapshot); assert.equal(calls[1].url.searchParams.get('page'), '2');
  assert.equal(calls[1].url.searchParams.get('selected_candidate_ref'), third); assert.equal(calls[1].url.searchParams.get('process_candidate_ref'), first);
  for (const format of ['csv', 'xlsx']) {
    responses.push({ ok: true, headers: { get: key => ({ 'Content-Type': format === 'csv' ? 'text/csv' : 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'Content-Disposition': 'attachment; filename=process.' + format,
      'X-Workbench-Run-Ref': runRef, 'X-Workbench-Snapshot-Ref': snapshot, 'X-Workbench-Row-Count': '69' })[key] || null }, blob: async () => new Blob(['saved process']) });
    await transport.decisionExport(runRef, { ...q, page: 2, size: 50 }, snapshot, format, undefined, 'process');
    const exported = calls.at(-1).url.searchParams;
    assert.equal(exported.get('filter_section'), 'process'); assert.equal(exported.get('process_candidate_ref'), first); assert.equal(exported.get('record_kind'), 'progress'); assert.equal(exported.get('sort'), 'event_index');
    assert.equal(exported.get('selected_candidate_ref'), third); assert.equal(exported.get('snapshot_ref'), snapshot); assert.equal(exported.has('page'), false); assert.equal(exported.has('size'), false, '过程导出覆盖所选锚点全部保存页');
  }
  const missingViewer = { process_candidate_ref: failedProcessRef, record_kind: 'attempts' };
  responses.push({ ok: true, headers: { get: key => key === 'Content-Type' ? 'application/json' : null }, json: async () => processFixture(missingViewer, { allFailed: true, nullViewer: true }) });
  await transport.process(runRef, missingViewer); assert.equal(calls.at(-1).url.searchParams.has('selected_candidate_ref'), false);
  responses.push({ ok: true, headers: { get: key => ({ 'Content-Type': 'text/csv', 'Content-Disposition': 'attachment; filename=process.csv', 'X-Workbench-Run-Ref': runRef, 'X-Workbench-Snapshot-Ref': snapshot, 'X-Workbench-Row-Count': '1' })[key] || null }, blob: async () => new Blob(['failure summary']) });
  await transport.decisionExport(runRef, missingViewer, snapshot, 'csv', undefined, 'process');
  assert.equal(calls.at(-1).url.searchParams.has('selected_candidate_ref'), false, '全失败仍可导出独立过程锚点');
}
async function transportContracts() {
  const calls = [], responses = [], fetcher = async (url, options) => { calls.push({ url: new URL(url, 'http://localhost'), options }); return responses.shift(); };
  const json = body => ({ ok: true, headers: { get: key => key === 'Content-Type' ? 'application/json' : null }, json: async () => body });
  const transport = API.create(fetcher), batchQuery = { ...query, batch_ref: batchRef, change_kind: 'later', sort: 'batch_id', order: 'asc', snapshot_ref: snapshot };
  for (const page of [1, 2]) { responses.push(json(detailsFixture('batches', { ...batchQuery, page }))); await transport.decisionDetails(runRef, { ...batchQuery, page }, 'batches'); }
  assert.equal(calls[0].url.pathname, '/api/workbench/v1/scheduling/runs/' + runRef + '/decision/batches');
  assert.equal(calls[1].url.searchParams.get('snapshot_ref'), calls[0].url.searchParams.get('snapshot_ref'), '翻页沿用同一明细筛选快照');
  assert.equal(calls[1].url.searchParams.get('page'), '2'); assert.equal(calls[1].url.searchParams.get('batch_ref'), batchRef);
  const exportQuery = { ...batchQuery, page: 2, size: 50, filter_section: 'batches' };
  responses.push({ ok: true, headers: { get: key => ({ 'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'Content-Disposition': 'attachment; filename=decision.xlsx',
    'X-Workbench-Run-Ref': runRef, 'X-Workbench-Snapshot-Ref': snapshot, 'X-Workbench-Row-Count': '21' })[key] || null }, blob: async () => new Blob(['fixture']) });
  await transport.decisionExport(runRef, exportQuery, snapshot, 'xlsx', undefined, 'all');
  const exported = calls.at(-1).url.searchParams;
  assert.equal(exported.get('snapshot_ref'), snapshot); assert.equal(exported.get('filter_section'), 'batches'); assert.equal(exported.get('batch_ref'), batchRef);
  assert.equal(exported.has('page'), false); assert.equal(exported.has('size'), false, '明细导出读取当前筛选全部页');
  const formalQuery = { comparison_mode: 'admission_official', selected_candidate_ref: third, batch_ref: batchRef, range_start, range_end };
  responses.push(json(referenceFixture(formalQuery))); await transport.referenceWorkspace(runRef, formalQuery);
  assert.equal(calls.at(-1).url.pathname, '/api/workbench/v1/scheduling/runs/' + runRef + '/decision/reference-workspace');
  assert.equal(calls.at(-1).url.searchParams.get('selected_candidate_ref'), third); assert.equal(calls.at(-1).url.searchParams.get('batch_ref'), batchRef);
  responses.push(json(summaryPayload)); const summary = await transport.decisionSummary(runRef, query);
  assert.equal(calls.at(-1).url.pathname, '/api/workbench/v1/scheduling/runs/' + runRef + '/decision/summary');
  assert.equal(calls.at(-1).url.searchParams.get('range_start'), range_start); assert.equal(calls.at(-1).url.searchParams.get('range_end'), range_end);
  const reads = calls.length;
  responses.push({ ok: true, headers: { get: key => ({ 'Content-Type': 'text/csv', 'Content-Disposition': 'attachment; filename=decision.csv',
    'X-Workbench-Run-Ref': runRef, 'X-Workbench-Snapshot-Ref': summary.meta.snapshot_ref, 'X-Workbench-Row-Count': '21' })[key] || null }, blob: async () => new Blob(['fixture']) });
  await transport.decisionExport(runRef, query, summary.meta.snapshot_ref, 'csv');
  assert.equal(calls.length, reads + 1, '摘要令牌直接导出，前置完整概览零请求');
  assert.equal(calls.at(-1).url.pathname, '/api/workbench/v1/scheduling/runs/' + runRef + '/decision/export');
  assert.equal(calls.at(-1).url.searchParams.get('snapshot_ref'), summary.meta.snapshot_ref);
  const savedResources = { resource_kind: 'operator', grain: 'day', pressure_threshold: 0.8, page: 2, heatmap_page: 2,
    snapshot_ref: 'r'.repeat(32), heatmap_mode: 'after', day_resource_ref: '0'.repeat(48), day_page: 2 };
  const combined = resourceWorkspaceFixture(summaryPayload, savedResources), controller = new AbortController();
  responses.push(json(combined)); const resourceWorkspace = await transport.resourceWorkspace(runRef, { ...query, snapshot_ref: snapshot }, savedResources, controller.signal);
  assert.strictEqual(resourceWorkspace, combined); assert.strictEqual(API.resourceWorkspace(combined, runRef, query, savedResources), combined.data);
  const resourceRequest = calls.at(-1), params = resourceRequest.url.searchParams;
  assert.equal(resourceRequest.url.pathname, '/api/workbench/v1/scheduling/runs/' + runRef + '/decision/resource-workspace');
  assert.equal(params.get('snapshot_ref'), snapshot); assert.equal(params.get('resource_snapshot_ref'), savedResources.snapshot_ref, '摘要和旧资源 token 在各自字段传递');
  assert.equal(params.get('resource_kind'), 'operator'); assert.equal(params.get('pressure_threshold'), '0.8'); assert.equal(params.get('page'), '2'); assert.equal(params.get('heatmap_page'), '2');
  for (const key of ['heatmap_mode', 'day_resource_ref', 'day_page']) assert.equal(params.has(key), false, '呈现状态不带入服务查询：' + key);
  assert.equal(resourceRequest.options.method, 'GET'); assert.equal(resourceRequest.options.cache, 'no-store'); assert.equal(resourceRequest.options.credentials, 'same-origin');
  assert.equal(resourceRequest.options.signal.aborted, false);
  for (const mutate of [value => { value.resource_result = null; }, value => { delete value.resource_query.heatmap_size; },
    value => { value.resource_query.snapshot_ref = 'q'.repeat(32); }, value => { value.resource_result.error.retryable = 'false'; },
    value => { value.resource_result.error.fields = [{}]; }, value => { value.resource_result.fallback = true; }, value => { value.data.scope.selected_candidate_ref = first; }]) {
    const invalid = clone(combined); mutate(invalid); assert.throws(() => API.resourceWorkspace(invalid, runRef, query, savedResources));
  }
  const resourceInjected = API.adapter({ resourceWorkspace: async () => combined });
  assert.strictEqual(await resourceInjected.resourceWorkspace(runRef, query, savedResources), combined, '组合注入 reader 仍走公共 DTO 读取边界');
  await assert.rejects(() => resourceInjected.resourceWorkspace(runRef, query, { ...savedResources, pressure_threshold: 0.7 }), /筛选/);
  const injected = API.adapter({ decisionSummary: async () => summaryPayload });
  assert.strictEqual(await injected.decisionSummary(runRef, query), summaryPayload, '实际adapter公共读取边界绑定摘要校验');
  await assert.rejects(() => injected.decisionSummary(runRef, { ...query, selected_candidate_ref: first }), /查看方案/, '注入摘要reader也拒绝旧候选响应');
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
  assert.strictEqual(local.RunCandidateAPI.catalog(catalog, savedRun, {}), raw.candidate_catalog);
  assert.strictEqual(local.RunJobAPI.catalog(catalog, savedRun), raw.candidate_catalog, 'Job 与 candidate 目录共用真实新版候选合同');
  assert.strictEqual(local.RunCandidateAPI.workspace(workspace, savedCandidate, {}), raw.candidate_workspace);
  assert.strictEqual(local.APSPlanContract.workspace(plan, raw.adopted_plan_workspace.plan.plan_ref, {}), plan);
  const algorithm = raw.candidate_workspace.generation.algorithm;
  assert.deepEqual(algorithm.target_objectives, ['min_overdue', 'min_tardiness', 'min_changeover'], '真实 canonical JSON 往返保留保存的主目标优先顺序');
  assert.deepEqual(algorithm, raw.adopted_plan_workspace.provenance.algorithm, '真实候选和正式采用计划沿同一份共同算法元数据');
  for (const value of [workspace, plan]) {
    const wrong = clone(value), item = wrong.data.generation ? wrong.data.generation.algorithm : wrong.data.provenance.algorithm;
    item.target_objectives.reverse();
    assert.throws(() => wrong.data.generation ? local.RunCandidateAPI.workspace(wrong, savedCandidate, {})
      : local.APSPlanContract.workspace(wrong, raw.adopted_plan_workspace.plan.plan_ref, {}), undefined, '两消费者均拒绝错序算法合同');
  }
  const extra = clone(plan); extra.data.provenance.algorithm.unrecorded = true;
  assert.throws(() => local.APSPlanContract.workspace(extra, raw.adopted_plan_workspace.plan.plan_ref, {}), undefined, '新采用来源不接未声明字段');
  const metadataTree = expand(h(local.RunCandidateControls.GenerationMetadata, { value: algorithm, runRef: savedRun }));
  assert.equal(nodes(metadataTree).find(node => node.props['data-first-found-elapsed-ms'] !== undefined).props['data-first-found-elapsed-ms'], algorithm.first_found_elapsed_ms);
  assert(text(metadataTree).includes('共同优化') && text(metadataTree).includes('代表方向'));
  const elapsedTree = expand(h(local.RunCandidateControls.Metric, { metric: raw.candidate_catalog.candidates[0].metrics.elapsed_seconds }));
  assert.equal(text(nodes(elapsedTree).find(node => node.type === 'summary')), 'N/A'); assert(text(elapsedTree).includes('本轮共同优化'));
  const identity = envelope({ candidate_ref: savedCandidate, run_ref: savedRun, label: raw.candidate_workspace.candidate.label, status: 'completed' });
  const calls = [], owner = new AbortController(), transport = local.RunCandidateAPI.create(async (url, options) => {
    calls.push({ url, options }); return { ok: true, status: 200, headers: { get: key => key === 'Content-Type' ? 'application/json' : null }, json: async () => identity };
  });
  assert.strictEqual(await transport.identity(savedCandidate, owner.signal), identity);
  assert.equal(calls.length, 1); assert(calls[0].url.endsWith('/candidates/' + savedCandidate + '/identity') && !calls[0].url.includes('/workspace'));
  assert.equal(calls[0].options.cache, 'no-store'); assert.equal(calls[0].options.credentials, 'same-origin');
  const badIdentity = clone(identity); badIdentity.data.candidate_ref = first;
  await assert.rejects(() => local.RunCandidateAPI.adapter({ identity: async () => badIdentity }).identity(savedCandidate), /身份|方案/, '注入 identity reader 同样绑定永久候选编号');
  const state = hooks(), lookups = [], summaries = [], ui = { ...local,
    APSResourceSession: { useQuery: (load, deps, enabled = true) => ({ result: enabled ? load() : null, loading: false, error: null }) } };
  vm.runInNewContext(outputs.find(output => output.path === 'RunDecisionComparison.jsx').code, { React: state.React, window: ui, AbortController });
  const props = { initialContext: { candidate_ref: savedCandidate }, adapter: {
    identity: (reference, signal) => { lookups.push({ reference, signal }); return identity; },
    workspace: () => { throw new Error('比较入口的运行编号查找只调用轻量 identity'); },
    decisionSummary: (reference, query) => { summaries.push({ reference, query }); return null; }
  } };
  state.render(() => ui.RunDecisionComparison.Workspace(props)); state.flush(); state.render(() => ui.RunDecisionComparison.Workspace(props));
  assert.equal(lookups.length, 1); assert.equal(summaries[0].reference, savedRun, '仅候选编号打开比较页由轻量身份结果取得 run_ref');
  const processRaw = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures/unified_process_http.json'), 'utf8'));
  const native = processRaw.decision_summary, nativeRun = native.run.run_ref, nativeCandidate = native.scope.selected_candidate_ref;
  assert.strictEqual(API.decisionSummary(envelope(native), nativeRun, { selected_candidate_ref: nativeCandidate }), native);
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
  // These card-count variants exercise presentation only; they reuse the captured business facts.
  for (const count of [1, 2, 3]) {
    const shown = clone(native); shown.candidates = Array.from({ length: count }, (_, index) => ({ ...clone(native.candidates[0]),
      candidate_ref: String(index + 80).padStart(48, '0'), representative_objectives: index === 0 ? ['min_overdue', 'min_tardiness'] : ['min_changeover'] }));
    const cards = expand(h(local.RunDecisionComparison.CandidateTable, { data: shown, selectedRef: shown.candidates[0].candidate_ref, referenceRef: nativeCandidate, onSelect: () => {} }));
    assert.equal(cards.props['data-unified-candidates'], count); assert.equal(nodes(cards).filter(node => node.props['data-decision-candidate']).length, count);
    assert(text(cards).includes('交期优先 · 拖期更轻') && text(cards).includes('推荐'), '合并代表方向与保存的推荐标记共同显示');
  }
  for (const count of [4, 6, 8]) {
    const old = clone(data); old.candidates = Array.from({ length: count }, (_, index) => ({ ...clone(data.candidates[index % data.candidates.length]), candidate_ref: String(index + 90).padStart(48, '0') }));
    const cards = expand(h(local.RunDecisionComparison.CandidateTable, { data: old, onSelect: () => {} }));
    assert.equal(cards.props['data-unified-candidates'], undefined); assert.equal(nodes(cards).filter(node => node.props['data-decision-candidate']).length, count, '旧候选集合全部保留');
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
  assert.strictEqual(API.decision(envelope(processRaw.decision_overview), nativeRun, { selected_candidate_ref: nativeCandidate }), processRaw.decision_overview);
  for (const container of [display, fullDisplay]) container.candidates.push(...[first, third].map((reference, index) => ({ ...clone(container.candidates[0]), candidate_ref: reference,
    label: ['拖期更轻代表方案', '切换更少代表方案'][index], selection_role: [], representative_objectives: [['min_tardiness'], ['min_changeover']][index] })));
  const compare = { ...local, RunDecisionProcess: { Pane: 'process-pane' }, RunDecisionResources: { Pane: 'resource-pane' },
    RunDecisionDetails: { Pane: 'detail-pane' }, RunDecisionCompletion: { Pane: 'completion-pane' },
    APSResourceSession: { useQuery: (load, deps, enabled = true) => ({ result: enabled ? load() : null, loading: false, error: null }) } };
  vm.runInNewContext(outputs.find(output => output.path === 'RunDecisionComparison.jsx').code, { React: compareState.React, window: compare, AbortController });
  const readDisplay = (reference, q, full = false) => { compareQueries.push(clone(q)); const value = clone(full ? fullDisplay : display);
    value.scope.selected_candidate_ref = q.selected_candidate_ref || nativeCandidate;
    value.scope.resource_view = q.resource_view; value.scope.comparison_mode = q.comparison_mode;
    value.scope.reference.candidate_ref = q.reference_candidate_ref || nativeCandidate; return envelope(value); };
  const compareProps = { initialContext: { run_ref: nativeRun, candidate_ref: nativeCandidate, reference_candidate_ref: nativeCandidate, comparison_tab: 'process',
      detail_queries: { process: { objective: 'min_changeover', process_candidate_ref: first, page: 2, size: 20, snapshot_ref: snapshot } } },
    adapter: { decisionSummary: readDisplay, resourceWorkspace: (reference, q, saved) => resourceWorkspaceFixture(readDisplay(reference, q), saved), decision: (reference, q) => readDisplay(reference, q, true) }, onNavigate: (page, context) => returns.push({ page, context }),
    renderAdoption: reference => h('adoption', { candidateRef: reference }) };
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
  const processState = hooks(), processCalls = [], pane = { ...window, RunDecisionAPI: API,
    APSResourceSession: { useQuery: (load, deps, enabled = true) => ({ result: enabled ? load() : null, loading: false, error: null }) } };
  for (const name of ['RunDecisionProcessChart.jsx', 'RunDecisionProcess.jsx']) for (const output of compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'),
    sources: [{ path: name, code: fs.readFileSync(path.join(app, name), 'utf8') }] }).outputs) vm.runInNewContext(output.code, { React: processState.React, window: pane, AbortController });
  const paneProps = { result: envelope(native), query: {}, enabled: true, onQuery: value => { paneProps.query = value; },
    adapter: { process: (reference, q) => { processCalls.push(clone(q)); return envelope(processRaw.process_by_objective[q.objective || native.selection_basis.primary_objective]); } } };
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
    adapter: {}, result: envelope(noGain), initialSection: 'process' }))); };
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
  const legacy = A.pending().begin(summary, input);
  assert.equal(legacy.schema_version, 1); assert.equal(A.validIntent(legacy), true);
  const proof = A.lookup(status(legacy, 'context_replaced'), legacy);
  assert.equal(A.lookup(status(legacy, 'unresolved'), legacy), null, 'An in-flight record remains protected');
  assert.throws(() => A.pending().dismissReplaced(legacy, clone(proof)), /不能丢弃/, 'A copied or forged proof cannot authorize dismissal');
  const changed = { ...legacy, input: { ...legacy.input, reason: '另一个提交内容' } };
  storage.setItem(A.PENDING_KEY, JSON.stringify(changed));
  assert.throws(() => A.pending().dismissReplaced(changed, proof), /不能丢弃/, 'Proofs bind the entire original intent, not just its request key');
  assert.throws(() => A.pending().dismissReplaced(legacy, proof), /记录已变化/, 'CAS preserves a newer stored record');
  assert.deepEqual(clone(A.pending().read()), clone(changed));
  storage.setItem(A.PENDING_KEY, JSON.stringify(legacy));
  const blockedStorage = { ...storage, removeItem() { throw new Error('disk full'); } };
  assert.throws(() => A.pending(blockedStorage).dismissReplaced(legacy, proof), /存不下/);
  assert.equal(A.pending().read().request_key, legacy.request_key);
  A.pending().dismissReplaced(clone(legacy), proof); assert.equal(A.pending().read(), null);
  const modern = A.pending().begin({ ...summary, data_context_ref: oldContext }, input);
  assert.equal(modern.schema_version, 2); assert.equal(modern.data_context_ref, oldContext); assert(A.validIntent(modern));
  assert(!A.validIntent({ ...modern, data_context_ref: JSON.stringify({ database_scope: '/old.db', successful_restores: [true] }) }));
  assert(A.validIntent({ ...modern, data_context_ref: 'd'.repeat(64) }), 'Existing hashed source identities remain readable');
  const transportCalls = [], transport = A.create(async (url, options) => {
    transportCalls.push({ url: new URL(url, 'http://localhost'), options });
    return { ok: true, status: 200, headers: { get: () => 'application/json' }, json: async () => status(modern, 'context_replaced') };
  });
  const raw = await transport.lookup(modern);
  assert.equal(raw.resolution, 'context_replaced');
  assert.equal(transportCalls[0].url.pathname, '/api/workbench/v1/scheduling/candidates/' + first + '/adoption-commands/' + modern.request_key);
  assert.equal(transportCalls[0].url.searchParams.get('run_ref'), runRef);
  assert.equal(transportCalls[0].url.searchParams.get('data_context_ref'), oldContext);
  assert.equal(transportCalls[0].options.method, 'GET');
  await transport.lookup(legacy);
  assert.equal(transportCalls.at(-1).url.searchParams.has('data_context_ref'), false);
  A.preview(preview(third), third);
  assert.strictEqual(A.lookup(receipt(modern), modern).data.candidate_ref, first, 'Committed results from another candidate remain recoverable');
  storage.setItem(A.PENDING_KEY, JSON.stringify(legacy));
  let lookupValue = status(legacy, 'context_replaced'), previews = 0;
  const props = { candidateRef: third, candidateCatalog: data.candidates, adapter: {
    async lookup(intent) { calls.push(intent.request_key); return lookupValue; },
    async preview(candidateRef) { previews++; return preview(candidateRef); }
  } };
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
  resolveLookup(status(legacy, 'unresolved')); await settle();
  assert.equal(dialog().props.replacedInfo, null); assert(!footer().some(node => text(node) === '结束旧来源待确认记录'));
  assert.equal(A.pending().read().request_key, legacy.request_key);
  lookupValue = status(legacy, 'context_replaced'); dialog().props.onLookup(); await settle();
  const next = { ...legacy, request_key: 'adoption-' + 'f'.repeat(48), candidate_ref: third, preview: { ...legacy.preview, candidate_ref: third } };
  lookupValue = status(next, 'unresolved'); storage.setItem(A.PENDING_KEY, JSON.stringify(next));
  local.dispatchEvent(new CustomEvent(A.EVENT, { detail: next })); render(); render();
  assert.equal(dialog().props.replacedInfo, null, 'A storage event cannot transfer source-replacement proof to another pending record');
  await settle(); assert(!dialog().props.notice.includes('数据库已切换或恢复'));
  lookupValue = receipt(next); dialog().props.onLookup(); await settle();
  assert(dialog().props.result); assert.equal(dialog().props.replacedInfo, null);
  dialog().props.onFinish(); await settle(); assert.equal(A.pending().read(), null);
  storage.setItem(A.PENDING_KEY, JSON.stringify(legacy)); lookupValue = status(legacy, 'context_replaced');
  local.dispatchEvent(new CustomEvent(A.EVENT, { detail: legacy })); await settle();
  nodes(tree).find(node => node.type === 'button').props.onClick(); await settle();
  nodes(expand(dialog().type(dialog().props).props.footer)).find(node => node.type === 'button' && text(node) === '结束旧来源待确认记录').props.onClick();
  await settle(); assert.equal(A.pending().read(), null); assert.equal(dialog(), undefined);
  nodes(tree).find(node => node.type === 'button').props.onClick(); await settle();
  assert.equal(previews, 1); assert.equal(dialog().props.preview.candidate_ref, third, 'Ending the proven old-source record restores current-candidate actions');
  state.unmount();
}
async function dashboardReadContracts() {
  const state = hooks(), timers = new Map(), requests = [];
  let timerId = 0;
  const local = { ...window }, context = vm.createContext({ window: local, React: state.React, AbortController, DOMException, URLSearchParams,
    setTimeout(fn, delay) { const id = ++timerId; timers.set(id, { fn, delay }); return id; }, clearTimeout(id) { timers.delete(id); } });
  const outputs = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'),
    sources: ['resource-session.js', 'DashboardContract.js', 'DashboardAnalysisAPI.js'].map(name => ({ path: name, code: fs.readFileSync(path.join(app, name), 'utf8') })) }).outputs;
  outputs.forEach(output => vm.runInContext(output.code, context, { filename: output.path }));
  const C = local.DashboardContract, Q = local.DashboardAnalysisAPI;
  for (const analysis of [false, true]) {
    const abortError = new DOMException('cancelled', 'AbortError');
    const fetcher = (url, options) => new Promise((resolve, reject) => {
      requests.push({ url, options }); options.signal.addEventListener('abort', () => reject(abortError), { once: true });
    });
    const read = signal => analysis ? Q.request('/api/workbench/v1/dashboard/analysis', fetcher, signal) : C.create(fetcher).list(C.scope(), signal);
    const waiting = read();
    assert.equal(timers.size, 1); const timer = [...timers.values()][0]; assert.equal(timer.delay, 60000);
    timer.fn();
    await assert.rejects(waiting, error => error !== abortError && error.message === '值班台读取超时（超过 60 秒），请重试或缩小筛选范围。');
    assert.equal(timers.size, 0);
    const controller = new AbortController(), cancelled = read(controller.signal); controller.abort();
    await assert.rejects(cancelled, error => error === abortError, 'An external abort is not misreported as a timeout');
    assert.equal(timers.size, 0);
    const networkError = new Error('offline');
    const failed = () => { throw networkError; };
    await assert.rejects(analysis ? Q.request('/analysis', failed) : C.create(failed).list(C.scope()), error => error === networkError);
  }
  const response = (value, status) => ({ ok: status === 200, status, headers: { get: () => 'application/json' }, json: async () => value });
  const refusal = { ok: false, committed: false, error: { code: 'snapshot_stale', message: '快照已变化。', fields: [] } };
  const denied = C.create(async (url, options) => { requests.push({ url, options }); return response(refusal, 409); });
  await assert.rejects(denied.list(C.scope()), error => error.code === 'snapshot_stale' && C.isRejected(error), 'Business rejection identity survives the timeout catch');
  const lane = requests.at(-1).options.headers['X-Workbench-Read-Lane'];
  assert.match(lane, /^dashboard-list:[A-Za-z0-9-]+$/);
  await assert.rejects(C.create(async (url, options) => { requests.push({ url, options }); return response(refusal, 409); }).list(C.scope()));
  assert.equal(requests.at(-1).options.headers['X-Workbench-Read-Lane'], lane, 'The page lane is shared across adapter recreation');
  await assert.rejects(denied.detail(first, C.scope()), error => C.isRejected(error));
  assert.equal(requests.at(-1).options.headers, undefined, 'Detail and history reads never replace the list lane');
  await assert.rejects(denied.command({ item_ref: first, action: 'transition', request_key: 'dashboard-' + first }, 'token'), error => C.isRejected(error));
  assert.equal(requests.at(-1).options.headers['X-Workbench-Read-Lane'], undefined);
  assert.equal(requests.at(-1).options.headers['Content-Type'], 'application/json');
  const superseded = { ok: false, committed: false, error: { code: 'request_superseded', message: 'replaced', fields: [] } };
  await assert.rejects(C.create(async () => response(superseded, 499)).list(C.scope()), error => error.name === 'AbortError' && !C.isRejected(error));
  let resolveOld, version = 0;
  const api = C.create(() => new Promise(resolve => { resolveOld = resolve; }));
  const render = () => state.render(() => local.APSResourceSession.useQuery(signal => version === 0 ? api.list(C.scope(), signal) : Promise.resolve('latest'), [version]));
  render(); state.flush(); await turns(); version = 1; render(); state.flush(); await turns();
  resolveOld(response(superseded, 499)); await turns();
  const current = render(); assert.equal(current.result, 'latest'); assert.equal(current.error, null, 'A superseded old read cannot overwrite the current query');
  state.unmount(); assert.equal(timers.size, 0);
}
async function main() {
  comparisonHeaderContracts(schedulingNavigationContracts());
  detailContracts(); referenceContracts(); recommendationContracts(); await transportContracts(); await workspaceContracts(); await paneContracts(); await completionContracts();
  processReadContracts(); attemptComparisonContracts(); processEvaluationScopeContracts(); processChartContracts(); await processPaneContracts(); await processTransportContracts(); await unifiedGenerationContracts();
  await adoptionContextContracts(); await dashboardReadContracts();
  console.log('decision comparison contract: candidate/formal scope, recommendation/completion, process owners/unknowns, single-leaf paging/export, verified curve segments, cancellation and original-viewer gantt return passed');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
