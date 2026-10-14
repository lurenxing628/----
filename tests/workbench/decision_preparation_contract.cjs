'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..'), app = path.join(root, 'frontend/workbench/app');
const ref = n => n.toString(16).padStart(48, '0'), run = ref(1), chosen = ref(2), baseline = ref(3), plan = ref(4), batch = ref(5), machine = ref(6), token = 's'.repeat(32);
const start = '2026-12-01T08:00:00', end = '2026-12-08T08:00:00', clone = value => JSON.parse(JSON.stringify(value));
const h = (type, props, ...children) => ({ type, props: props || {}, children: children.flat(Infinity).filter(value => value != null && value !== false) });
const nodes = node => !node || typeof node !== 'object' ? [] : [node, ...node.children.flatMap(nodes)];
const text = node => node == null ? '' : typeof node !== 'object' ? String(node) : node.children.map(text).join(' ');
const visibleText = node => node == null ? '' : typeof node !== 'object' ? String(node) : node.type === 'details' && !node.props.open ? visibleText(node.children.find(child => child && child.type === 'summary')) : node.children.map(visibleText).join(' ');
const fieldText = (tree, label) => text(nodes(tree).find(node => node.type === 'div' && node.children.some(child => child && child.type === 'dt' && text(child) === label)).children.find(child => child && child.type === 'dd'));
function expand(node) { if (!node || typeof node !== 'object') return node; if (typeof node.type === 'function') return expand(node.type({ ...node.props, children: node.children })); return { ...node, children: node.children.map(expand) }; }
function hooks() {
  let cursor = 0; const slots = [], effects = [], same = (a, b) => a && b && a.length === b.length && a.every((value, i) => value === b[i]);
  return { React: { createElement: h, Fragment: 'fragment', useRef(initial) { const i = cursor++; if (!slots[i]) slots[i] = { current: initial }; return slots[i]; },
    useState(initial) { const i = cursor++; if (!slots[i]) slots[i] = { value: typeof initial === 'function' ? initial() : initial }; return [slots[i].value, update => { slots[i].value = typeof update === 'function' ? update(slots[i].value) : update; }]; },
    useMemo(make, deps) { const i = cursor++; if (!slots[i] || !same(slots[i].deps, deps)) slots[i] = { deps, value: make() }; return slots[i].value; },
    useEffect(effect, deps) { const i = cursor++, old = slots[i]; if (!old || !same(old.deps, deps)) { slots[i] = { deps, cleanup: old && old.cleanup }; effects.push(() => { if (slots[i].cleanup) slots[i].cleanup(); slots[i].cleanup = effect(); }); } },
    useReducer(reducer, initial) { const [value, set] = this.useState(initial); return [value, action => set(old => reducer(old, action))]; } },
    render(fn) { cursor = 0; return fn(); }, flush() { while (effects.length) effects.shift()(); } };
}
const sources = ['resource-contract.js', 'resource-session.js', 'WorkbenchFormat.js', 'WorkbenchTerms.js', 'EffortProjectionContract.js', 'PointContract.js', 'GanttGraph.js', 'PlanGanttModel.js', 'RunCandidateModel.js', 'RunCandidateAPI.js', 'RunOperationEffort.jsx', 'RecommendationContract.js', 'RunDecisionAPI.js', 'RunDecisionRecommendation.jsx', 'RunDecisionComparison.jsx', 'RunDecisionPreparation.jsx'];
const built = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources: sources.map(name => ({ path: name, code: fs.readFileSync(path.join(app, name), 'utf8') })) }).outputs;
function runtime(state = hooks()) {
  const window = { ResourceControls: { Button: 'button', Modal: 'modal' }, WorkbenchReference: 'reference', PointContract: {},
    RunCandidateControls: { Button: 'button', Pager: 'pager', Status: 'candidate-status', ErrorBox: 'error-box', Reasons: 'reasons' } };
  for (const output of built) vm.runInNewContext(output.code, { React: state.React, window, AbortController, DOMException, Blob, setTimeout, clearTimeout, URLSearchParams });
  return { window, state };
}
const initialRuntime = runtime(), { window } = initialRuntime, A = window.RunDecisionAPI, P = window.RunDecisionPreparation, E = window.RunOperationEffort, D = window.RunDecisionComparison;
const prepKeys = ['pending_setup_hours', 'scheduled_setup_hours', 'unplanned_setup_hours', 'deferred_setup_hours', 'pending_processing_hours', 'scheduled_processing_hours', 'unplanned_processing_hours', 'deferred_processing_hours'];
const common = { selected_candidate_ref: chosen, reference_candidate_ref: baseline, resource_view: 'selected_batches', range_start: start, range_end: end };
const metric = value => ({ value, state: 'complete', known_subtotal: value, known_count: 23, unknown_count: 0, total_count: 23, reason: null });
const delta = value => ({ value, state: 'comparable', direction: value === 0 ? 'equal' : 'neutral', reference_value: 2, selected_value: 2 + value });
function effort() { return { source: 'internal', quantity_basis: 'piece', target_quantity: 10, execution_target_quantity: 20, execution_quantity_basis: 'piece', remaining_quantity: 8,
  setup_standard_hours: 2, processing_standard_hours: 5, required_standard_hours: 7, setup_state: 'retained_in_execution', requirement_role: 'retained', allocation_state: 'retained',
  external_cycle_days: null, external_group_id: null, external_merge_mode: null, effort_basis: 'runtime_requirement_v1', evidence_source: { kind: 'run', run_ref: run, candidate_ref: baseline }, state: 'complete', data_gaps: [],
  standard: { basis: 'archived_operation_standard', setup_standard_hours: 3, unit_standard_hours: 0.4, standard_total_hours: 11, target_quantity: 20, remaining_quantity: 8, state: 'complete', reason: null },
  machines: [{ ref: machine, label: '车床01' }], machine: { ref: machine, label: '车床01' }, arrangements: [] }; }
function drill(q, operation, side = 'selected') { const official = side === 'reference' && q.comparison_mode === 'admission_official'; return { run_ref: run, candidate_ref: side === 'reference' && !official ? baseline : chosen,
  operation_ref: operation, comparison_mode: q.comparison_mode || 'candidates', resource_view: q.resource_view || 'selected_batches', range_start: start, range_end: end,
  ...(official ? { reference_view: true, plan_ref: plan } : {}) }; }
function fixture(query = {}, section = 'preparation') {
  query = { ...common, ...query }; if (query.comparison_mode === 'admission_official') delete query.reference_candidate_ref; const q = A.preparationScope(run, query, section), official = q.comparison_mode === 'admission_official';
  const scope = { run_ref: run, selected_candidate_ref: chosen, comparison_mode: q.comparison_mode, resource_view: q.resource_view, range_start: start, range_end: end, batch_refs: [batch], operation_refs: Array.from({ length: 23 }, (_, i) => ref(100 + i)), resource_refs: { machine: [machine], operator: [] },
    reference_state: 'available', reference: official ? { kind: 'admission_official', baseline_ref: plan } : { kind: 'candidate', candidate_ref: baseline } };
  const fields = ['sort', 'order', 'machine_ref', ...(section === 'preparation' ? ['batch_ref', 'allocation_state', 'work_scope'] : ['event_side'])], filters = { section, ...Object.fromEntries(fields.map(key => [key, q[key] || null])) };
  const values = Object.fromEntries((section === 'preparation' ? prepKeys : ['type_changeover_count', 'changed_machine_count']).map(key => [key, metric(2)]));
  const roles = Object.fromEntries(['retained', 'execution', 'completed'].map(role => [role, { count: 1, setup_standard_hours: metric(2), processing_standard_hours: metric(5), required_standard_hours: metric(7) }]));
  let items = scope.operation_refs.map((operation_ref, i) => ({ operation_ref, batch_ref: batch, batch_label: 'B-01', batch_id: 'B-01', part_label: '分件轴', process_label: '车削', piece_id: 'A', sequence: i + 1,
    before: effort(), after: effort(), deltas: Object.fromEntries(['setup_standard_hours', 'processing_standard_hours', 'required_standard_hours'].map(key => [key, delta(0)])), data_gaps: [], drill: { selected: drill(q, operation_ref), reference: drill(q, operation_ref, 'reference') } }));
  if (section === 'changeovers') items = [{ event_ref: 'reference:' + ref(700) + ':' + ref(701), event_side: 'reference', machine_ref: machine, machine_label: '车床01', sequence: 1,
    previous_operation_ref: ref(90), next_operation_ref: ref(100), previous_row_ref: ref(700), next_row_ref: ref(701), previous_type: '磨削', next_type: '车削', previous_start: '2026-11-30T08:00:00', previous_end: '2026-11-30T12:00:00', next_start: start, next_end: '2026-12-01T12:00:00',
    previous: { operation_ref: ref(90), batch_ref: ref(91), batch_label: '旧正式批次', process_label: '磨削', type_ref: ref(600), type_label: '磨削工种' }, next: { operation_ref: ref(100), batch_ref: batch, batch_label: 'B-01', process_label: '车削', type_ref: ref(601), type_label: '车削工种' },
    predecessor_outside_window: true, overlap: false, state: 'complete', data_gaps: [], drill: { previous: drill(q, ref(90), 'reference'), next: drill(q, ref(100), 'reference') } }];
  return { ok: true, schema_version: 1, warnings: [], meta: { request_ref: '1'.repeat(32), source: 'production', time_basis: 'factory_local', snapshot_ref: token, as_of: end }, data: { run_ref: run, scope,
    candidate: { candidate_ref: chosen, label: '所选候选' }, baseline: official ? { kind: 'admission_official', baseline_ref: plan, label: '受理时正式计划 v2', state: 'available' } : { kind: 'candidate', candidate_ref: baseline, label: '候选基准', state: 'available' },
    filters, filter_options: { batches: [{ ref: batch, label: 'B-01' }], machines: [{ ref: machine, label: '车床01', kind: 'machine' }] }, items: items.slice((q.page - 1) * q.size, q.page * q.size), page: { number: q.page, size: q.size, total: items.length, has_more: q.page * q.size < items.length },
    metric_version: 'decision-preparation-v4', summary: { scope: section === 'preparation' ? 'full_admission' : 'fixed_changeover_window', before: clone(values), after: clone(values), deltas: Object.fromEntries(Object.keys(values).map(key => [key, delta(0)])), ...(section === 'preparation' ? { role_totals: { before: clone(roles), after: clone(roles) } } : {}) } } };
}
function identities() {
  const archive = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures/decision_preparation_workspace.json'), 'utf8'));
  assert.strictEqual(window.RunCandidateAPI.workspace(archive.payload, archive.candidate_ref, { batch_ref: archive.batch_ref }), archive.payload.data, '实际已排和待料workspace保留永久工种与compact需求');
  for (const section of ['tasks', 'unplanned_operations']) {
    const wrong = clone(archive.payload); wrong.data[section][0].process_type_ref = 'current-live-id';
    assert.throws(() => window.RunCandidateAPI.workspace(wrong, archive.candidate_ref, { batch_ref: archive.batch_ref }));
  }
  const legacy = clone(archive.payload); [...legacy.data.tasks, ...legacy.data.unplanned_operations].forEach(row => { delete row.process_type_ref; delete row.process_type_label; delete row.operation_effort; });
  assert.strictEqual(window.RunCandidateAPI.workspace(legacy, archive.candidate_ref, { batch_ref: archive.batch_ref }), legacy.data, '旧workspace可继续缺少新增工种及需求字段');
  const compact = value => Object.fromEntries(Object.entries(value).filter(([key]) => !['machine', 'machines', 'arrangements'].includes(key)));
  const operationPayload = fixture(); operationPayload.data.filters = { section: 'operations', sort: 'sequence', order: 'asc', change_kind: 'all', batch_ref: null, resource_ref: null };
  operationPayload.data.items.forEach(row => { row.runtime_effort = { before: compact(row.before), after: compact(row.after) }; });
  assert.strictEqual(A.details(operationPayload, run, common, 'operations'), operationPayload.data, '工序变化沿用已单列的安排，需求字段采用compact合同');
  const badOperation = clone(operationPayload); delete badOperation.data.items[0].runtime_effort.after.execution_target_quantity;
  assert.throws(() => A.details(badOperation, run, common, 'operations'), /工序工时/);
  const badPreparation = fixture(); badPreparation.data.items[0].after = compact(badPreparation.data.items[0].after);
  assert.throws(() => A.preparationDetails(badPreparation, run, common), /准备与加工工时/, '准备页完整side仍要求机器与安排字段');
  for (const section of ['preparation', 'changeovers']) for (const comparison_mode of ['candidates', 'admission_official']) {
    const q = { ...common, comparison_mode, ...(comparison_mode === 'admission_official' ? { reference_candidate_ref: undefined } : {}) }, value = fixture(q, section);
    assert.strictEqual(A.preparationDetails(value, run, q, section), value.data);
    for (const mutate of [x => { x.data.filters.machine_ref = chosen; }, x => { x.data.page.number = 2; }, x => { x.data.scope.range_end = '2026-12-09T08:00:00'; },
      x => { (section === 'preparation' ? x.data.items[0].drill.reference : x.data.items[0].drill.previous).candidate_ref = run; }]) {
      const wrong = clone(value); mutate(wrong);
      assert.throws(() => A.preparationDetails(wrong, run, q, section));
    }
    if (comparison_mode === 'admission_official') { const wrong = clone(value), nav = section === 'preparation' ? wrong.data.items[0].drill.reference : wrong.data.items[0].drill.previous; nav.plan_ref = chosen; assert.throws(() => A.preparationDetails(wrong, run, q, section), /定位资料|事件/); }
  }
  const bad = effort(); bad.execution_target_quantity = undefined; assert(!window.EffortProjectionContract.compact(bad), '执行目标与原需求目标必须分别具备字段');
  assert.equal(A.preparationScope(run, common).work_scope, 'all', '准备需求默认读取全部受理工序');
  assert.equal(A.preparationScope(run, { ...common, work_scope: 'remaining' }).work_scope, 'remaining');
  assert.equal(A.preparationScope(run, { ...common, work_scope: 'remaining' }, 'changeovers').work_scope, undefined, '剩余需求筛选只属于准备需求');
  assert.throws(() => A.preparationScope(run, { ...common, work_scope: 'unfinished' }), /筛选/);
  for (const work_scope of ['all', 'remaining']) {
    const q = { ...common, work_scope }, value = fixture(q);
    assert.strictEqual(A.preparationDetails(value, run, q), value.data);
    const wrong = clone(value); wrong.data.filters.work_scope = work_scope === 'all' ? 'remaining' : 'all';
    assert.throws(() => A.preparationDetails(wrong, run, q), /筛选/, '准备响应必须保留精确需求范围');
  }
  const remainingQuery = { ...common, work_scope: 'remaining', batch_ref: batch, machine_ref: machine, allocation_state: 'unplanned', size: 50 }, remaining = fixture(remainingQuery);
  remaining.data.items = [remaining.data.items.at(-1)]; remaining.data.items[0].after.allocation_state = 'unplanned';
  remaining.data.page.total = 1; remaining.data.page.has_more = false;
  assert.strictEqual(A.preparationDetails(remaining, run, remainingQuery), remaining.data);
  assert.equal(remaining.data.summary.scope, 'full_admission', '剩余明细保留完整受理汇总');
  const located = [], tableRuntime = runtime(), tableProps = { data: remaining.data, onDrill: value => located.push(value) };
  let remainingTree = tableRuntime.state.render(() => expand(h(tableRuntime.window.RunDecisionPreparation.PreparationTable, tableProps)));
  assert.deepEqual(nodes(remainingTree).filter(node => node.props['data-decision-preparation']).map(node => node.props['data-decision-preparation']), [ref(122)], '准备页精确展示服务返回的单行，不扩宽到全部受理工序');
  nodes(remainingTree).find(node => node.type === 'button' && text(node) === '看甘特').props.onClick();
  assert.strictEqual(located[0], remaining.data.items[0].drill.selected); assert.equal(located[0].operation_ref, ref(122)); assert.equal(located[0].candidate_ref, chosen);
  nodes(remainingTree).find(node => node.props['data-preparation-operation'] === ref(122)).props.onClick();
  assert.strictEqual(located[1], remaining.data.items[0].drill.selected, '点击工序名直接走同一永久工序定位路径');
  assert.equal(text(nodes(remainingTree).find(node => node.props['data-decision-preparation']).children[1]), '2', '相同准备工时主行显示一次');
  nodes(remainingTree).find(node => node.props['data-preparation-detail'] === ref(122)).props.onClick();
  remainingTree = tableRuntime.state.render(() => expand(h(tableRuntime.window.RunDecisionPreparation.PreparationTable, tableProps)));
  assert(nodes(remainingTree).some(node => node.props.className === 'rd-preparation-expanded'), '工时详情在紧邻全宽行打开完整需求');
  assert.throws(() => A.preparationScope(run, { ...common, allocation_state: 'saved_locked' }), /筛选/);
  assert.throws(() => A.preparationScope(run, { ...common, sort: 'after_setup_hours' }, 'changeovers'), /排序/);
  const original = effort(), originalJson = JSON.stringify(original), originalTree = expand(h(E.Effort, { value: original, showMachines: true })), labels = window.WorkbenchTerms.operation_effort_labels;
  assert(fieldText(originalTree, labels.target_quantity).startsWith('10'), '原保存10件需求单独显示');
  assert(fieldText(originalTree, labels.execution_target_quantity).startsWith('20'), '当前AJ20件目标单独显示');
  assert.equal(fieldText(originalTree, labels.remaining_quantity), '8', '当前AJ余8件独立显示');
  assert(nodes(originalTree).some(node => node.type === 'small' && text(node).replace(/\s+/g, ' ').includes(labels.required_standard_hours + ' 7 小时')), '原7h直接显示不从AJ目标改算');
  assert.equal(fieldText(originalTree, labels.standard_total_hours), '11 小时', '原标准单列不冒充运行需求'); assert.equal(JSON.stringify(original), originalJson);
  const requirement = effort(); requirement.allocation_state = 'unplanned'; requirement.machine_basis = 'admission_requirement';
  const requirementText = text(expand(h(E.Effort, { value: requirement, showMachines: true })));
  assert(requirementText.includes('所需设备') && requirementText.includes(requirement.machines[0].label) && !requirementText.includes('安排设备'), '未安排工序的设备要求与保存安排设备分开标明');
  const large = effort(); large.execution_target_quantity = '9223372036854775807'; assert(text(expand(h(E.Effort, { value: large }))).includes('9,223,372,036,854,775,807'), '大整数量保留原十进制文本');
  const old = effort(); Object.assign(old, { effort_basis: null, target_quantity: null, quantity_basis: 'unknown', setup_standard_hours: null, processing_standard_hours: null, required_standard_hours: null, state: 'unavailable' });
  const oldTree = expand(h(E.Effort, { value: old })), oldRequired = nodes(oldTree).find(node => node.type === 'small' && text(node).includes(labels.required_standard_hours));
  assert(fieldText(oldTree, labels.execution_target_quantity).startsWith('20')); assert.equal(fieldText(oldTree, labels.standard_total_hours), '11 小时');
  assert(!text(oldRequired).includes('11'), '旧标准不回填缺失runtime需求');
  const deferred = clone(old); Object.assign(deferred, { effort_basis: 'runtime_requirement_v1', allocation_state: 'deferred', requirement_role: 'not_scheduled', data_gaps: [{ code: 'runtime_requirement_not_constructed', message: '工序未进入本次排槽需求构造，实际标准需求未知。' }] }); deferred.standard.setup_standard_hours = 0.5;
  const deferredTree = expand(h(E.Effort, { value: deferred })), deferredRequired = nodes(deferredTree).find(node => node.type === 'small' && text(node).includes(labels.required_standard_hours));
  assert(!text(deferredRequired).includes('0.5') && !text(deferredRequired).includes('11'), '未构造的本轮需求保持缺项');
  assert.equal(visibleText(deferredTree).split('工时需求未生成').length - 1, 1, '未生成工时需求只保留一处默认状态');
  assert.equal(deferred.setup_standard_hours, null); assert.equal(deferred.processing_standard_hours, null); assert.equal(deferred.required_standard_hours, null, '未生成需求保持null');
  assert(text(deferredRequired).includes('—') && !text(deferredRequired).includes('0 小时'), '原生工时资料保持缺项，不补零');
  assert(text(deferredTree).includes('0.5'), '未进入排槽的已保存账与已知标准0.5h分别显示');
  assert.strictEqual(nodes(deferredTree).find(node => node.type === 'reasons').props.rows, deferred.data_gaps, '缺项原因直接沿用保存记录');
  const changed = { ...delta(-2), state: 'different_coverage', direction: 'neutral' }, changeText = D.deltaText(changed, { source: 'runtime_operation_effort', precision: 3, unit: '小时' });
  assert(changeText.includes('减少 2 小时') && changeText.includes('工序计量对象不同')); assert(!changeText.includes('节省')); assert.equal(D.deltaText(delta(0), { source: 'runtime_operation_effort' }), '相同');
  const event = fixture({ comparison_mode: 'admission_official' }, 'changeovers').data, clicks = [], eventTree = initialRuntime.state.render(() => expand(h(P.ChangeoverTable, { data: event, onDrill: value => clicks.push(value) })));
  assert(text(eventTree).includes('前序在范围外')); nodes(eventTree).find(node => node.type === 'button' && text(node) === '看前序甘特').props.onClick(); assert.equal(clicks[0].operation_ref, ref(90)); assert.equal(clicks[0].plan_ref, plan); assert.equal(clicks[0].reference_view, true);
  assert.equal(text(nodes(eventTree).find(node => node.props['data-decision-changeover']).children[1]), window.WorkbenchFormat.dateTime(event.items[0].next_start), '切换主时间取后序开始，前序完整时间留详情');
  nodes(eventTree).find(node => node.props['data-changeover-operation'] === ref(90)).props.onClick();
  assert.strictEqual(clicks[1], event.items[0].drill.previous, '前序工序名保留正式基准身份和定位');
  event.summary.after.issues = [{ code: 'process_type_unknown', message: '保存安排缺少实际工种身份，切换次数保留已知小计。', operation_ref: ref(101) }];
  const diagnostics = expand(h(P.Summary, { data: event, definitions: [], section: 'changeovers' })); assert(nodes(diagnostics).some(node => node.props.className === 'rd-changeover-diagnostics')); assert.equal(nodes(diagnostics).find(node => node.type === 'reasons').props.rows[0].code, 'process_type_unknown');
  const absent = fixture({ comparison_mode: 'admission_official' }).data; absent.baseline.state = 'absent'; absent.scope.reference_state = 'absent';
  const missing = text(expand(h(P.Summary, { data: absent, definitions: [], section: 'preparation' }))); assert(missing.includes('排产时尚无正式计划')); assert(!missing.includes('基准 1 道工序'));
  const partial = fixture().data, fullReason = '部分工序未保存实际运行需求分解；已知小计与原标准分别列出。';
  for (const side of ['before', 'after']) for (const key of prepKeys) partial.summary[side][key] = { ...metric(14.5), value: null, state: 'partial', known_count: 28, unknown_count: 1, total_count: 29, reason: { code: 'runtime_requirement_missing', message: fullReason } };
  const summaryTable = expand(h(P.Summary, { data: partial, definitions: [], section: 'preparation' })), summaryVisible = visibleText(summaryTable).replace(/\s+/g, ' ');
  assert.equal(nodes(summaryTable).filter(node => node.type === 'tr' && node.props['data-preparation-summary']).length, 8, '完整八项准备汇总保留在原生资料展开中');
  const summaryHeaders = nodes(summaryTable).find(node => node.type === 'thead').children[0].children;
  assert.equal(text(summaryHeaders[1]), '比较基准'); assert.equal(text(summaryHeaders[2]), '当前方案', '双方角色由汇总表头清楚标明');
  assert(summaryVisible.includes('1 道工序待确认') && summaryVisible.includes('已知准备 14.5 小时') && text(summaryTable).includes('已知加工 14.5 小时'));
  assert(!summaryVisible.includes(fullReason) && text(summaryTable).includes(fullReason), '两侧完整理由由原生依据展开保留');
  const zeroSummary = fixture().data;
  for (const key of prepKeys) { zeroSummary.summary.before[key] = metric(0); zeroSummary.summary.after[key] = metric(0); zeroSummary.summary.deltas[key] = delta(0); }
  const zeroTable = expand(h(P.Summary, { data: zeroSummary, definitions: [], section: 'preparation' }));
  assert.equal(nodes(zeroTable).filter(node => node.props['data-preparation-highlight']).length, 0, '普通零工时不进入默认摘要');
  assert.equal(nodes(zeroTable).filter(node => node.props['data-preparation-summary']).length, 8, '普通零工时的完整八项原值仍可展开');
  const missingDifference = fixture().data; missingDifference.items = [missingDifference.items[0]];
  for (const key of ['setup_standard_hours', 'processing_standard_hours', 'required_standard_hours']) missingDifference.items[0].deltas[key] = { value: null, reference_value: null, selected_value: null, state: 'unavailable', direction: 'neutral', reason: { code: 'runtime_requirement_not_constructed', message: deferred.data_gaps[0].message } };
  const savedDifference = clone(missingDifference), differenceCell = expand(h(P.Difference, { value: missingDifference.items[0].deltas }));
  assert.equal(visibleText(differenceCell).split('差值待确认').length - 1, 1, '三项需求差值缺项集中为一个默认状态');
  assert.equal(nodes(differenceCell).filter(node => node.type === 'reasons').length, 1, '同一需求缺项原因在原生依据中只保留一次');
  assert.equal(nodes(differenceCell).filter(node => node.type === 'dd').length, 9);
  assert(nodes(differenceCell).filter(node => node.type === 'dd').every(node => text(node).trim() === '—' && node.props.title === undefined), '基准、所选与差值原null全部可查');
  assert.deepEqual(clone(missingDifference), savedDifference);
  const controls = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources: [{ path: 'RunCandidateControls.jsx', code: fs.readFileSync(path.join(app, 'RunCandidateControls.jsx'), 'utf8') }] }).outputs[0];
  vm.runInNewContext(controls.code, { React: initialRuntime.state.React, window }); window.GanttRouteList = 'routes';
  const task = { operation_ref: ref(100), row_ref: ref(700), batch_ref: batch, batch_label: 'B-01', process_label: '车削', part_label: '分件轴', sequence: 1, piece_id: 'A', quantity: 20, batch_quantity: 50,
    start, end, machine: { ref: machine, label: '车床01' }, operator: null, supplier: null, source: 'internal', locked: true, due_date: '2026-12-10', due_state: 'specified', due_issue: null, data_gaps: [], operation_effort: original };
  const target = [], second = { ...task, row_ref: ref(701), start: '2026-12-02T08:00:00' };
  const inspector = initialRuntime.state.render(() => expand(h(window.RunCandidateControls.Detail, { data: { tasks: [task, second], gantt_graph: {} }, task, onClose: () => {}, onRelated: row => target.push(row) })));
  const inspectorText = text(inspector).replace(/\s+/g, ' ');
  assert(inspectorText.includes('准备与加工需求') && fieldText(inspector, labels.target_quantity).startsWith('10') && fieldText(inspector, labels.execution_target_quantity).startsWith('20') && fieldText(inspector, labels.remaining_quantity) === '8', '甘特详情直接读取同一份保存需求');
  const segments = nodes(inspector).filter(node => node.props.className === 'rc-saved-segment'); assert.equal(segments.length, 2, '需求来源接入保留全部分段安排');
  nodes(segments.find(node => node.props.key === second.row_ref)).find(node => node.type === 'button').props.onClick(); assert.equal(target[0], second.row_ref);
  const full = fixture({ comparison_mode: 'admission_official' });
  const candidate = { candidate_ref: chosen, label: '所选候选', kind: 'candidate', status: 'completed', persisted_status: 'completed', completeness: 'complete', task_count: 23,
    selection_role: [], equivalent_source_ref: null, metrics: {}, deltas: {},
    coverage: { search: { state: 'complete', completed_count: 1, failed_count: 0, skipped_count: 0, total_count: 1 },
      schedulable: { state: 'complete', expected_count: 23, scheduled_count: 23, missing_count: 0, deferred_count: 0 },
      delivery: { complete_batch_count: 1, batch_count: 1, deferred_batch_count: 0 } },
    capabilities: { view: true, compare: true, gantt: true, adoption_preview: true, adopt: false }, source: { reason: null } };
  const basis = { selected_candidate_ref: null, raw_score_best_candidate_ref: null, health_reference_candidate_ref: null, evidence_state: 'unavailable', reason_code: 'selection_not_recorded',
    decision_evidence: null, health_decision_evidence: null, selection_evidence_version: null,
    explanation: { headline: '排产时未保存选择记录。', entries: [], issues: [] } };
  const coreDefinitions = ['expected_operation_count', 'scheduled_operation_count', 'unplanned_operation_count', 'deferred_operation_count',
    'overdue_count', 'total_tardiness_hours', 'makespan_hours', 'weighted_tardiness_hours', 'elapsed_seconds', 'changeover_count',
    'machine_used_count', 'operator_used_count', 'machine_busy_hours_total', 'operator_busy_hours_total', 'machine_util_avg', 'operator_util_avg']
    .map(key => ({ key, label: key, metric_version: 'decision-preparation-v4', precision: 2,
      scope: ['makespan_hours', 'changeover_count'].includes(key) ? 'full_candidate' : key === 'weighted_tardiness_hours' ? 'saved_algorithm_batches'
        : key === 'elapsed_seconds' ? 'candidate_search' : key.startsWith('machine_') || key.startsWith('operator_') ? 'saved_schedule_resources' : 'full_admission',
      source: ['overdue_count', 'total_tardiness_hours'].includes(key) ? 'archived_delivery' : ['expected_operation_count', 'deferred_operation_count'].includes(key) ? 'admission'
        : ['scheduled_operation_count', 'unplanned_operation_count'].includes(key) ? 'candidate_tasks' : 'saved_algorithm' }));
  candidate.metrics = Object.fromEntries(coreDefinitions.map(definition => [definition.key, { ...metric(2), scope: definition.scope, metric_version: definition.metric_version }]));
  candidate.deltas = Object.fromEntries(coreDefinitions.map(definition => [definition.key, delta(0)]));
  const overview = { ...full, data: { run: { run_ref: run, accepted_at: start, finished_at: end }, scope: full.data.scope, baseline: full.data.baseline,
    candidates: [candidate], metric_definitions: coreDefinitions, catalog_complete: true, selection_basis: basis,
    completion_groups: [{ group_index: 1, source_available: true, candidate_refs: [chosen], complete_batch_count: 1, sample_complete_batch_refs: [batch] }],
    recommendation: { recommendation_version: 'decision-recommendation-v1', state: 'unavailable', candidate_ref: null, viewed_candidate_ref: chosen,
      recommendation_type: null, headline: '本次排产尚未保存推荐方案。', completion_scope: null,
      axes: { algorithm: { state: 'unavailable', reason_code: basis.reason_code, evidence_state: basis.evidence_state },
        completion: { search: null, schedulable: null, delivery: null }, preflight: { state: 'not_checked', source: 'existing_adoption_preview' } },
      current_comparison: { state: 'unavailable', candidate_ref: null, viewed_candidate_ref: chosen, reference: full.data.scope.reference,
        benefits: [], costs: [], all_differences: [], common_completed_delivery: null } } } };
  assert.strictEqual(A.decision(overview, run, { comparison_mode: 'admission_official', selected_candidate_ref: chosen, range_start: start, range_end: end }), overview.data,
    '准备需求回跳的总览夹具先通过真实比较DTO校验');
  const recalled = [], navigation = [], detailQueries = { preparation: { page: 2, size: 20, machine_ref: machine, batch_ref: batch, allocation_state: 'unplanned', work_scope: 'remaining', snapshot_ref: token }, changeovers: { event_side: 'reference', sort: 'machine_label', order: 'desc' } };
  const mainRuntime = runtime(), mainWindow = mainRuntime.window;
  mainWindow.WorkbenchPageContext = { useSnapshot: value => recalled.push(value) }; mainWindow.WorkbenchCaption = { useCaption: () => {} };
  mainWindow.APSResourceSession = { useQuery: (load, deps, enabled = true) => ({ result: enabled ? overview : null, loading: false, error: null }) };
  mainWindow.RunDecisionPreparation.Pane = 'preparation-pane';
  const comparison = mainRuntime.state.render(() => expand(h(mainWindow.RunDecisionComparison.Workspace, { adapter: {}, initialContext: { run_ref: run, candidate_ref: chosen, comparison_mode: 'admission_official', comparison_tab: 'preparation', resource_kind: 'machine', resource_ref: machine, detail_queries: detailQueries }, onNavigate: (page, context) => navigation.push({ page, context }) })));
  const pane = nodes(comparison).find(node => node.type === 'preparation-pane'); assert.equal(pane.props.query.page, 2); assert.equal(pane.props.query.snapshot_ref, token); assert.equal(pane.props.query.work_scope, 'remaining');
  pane.props.onDrill(full.data.items[0].drill.reference); assert.equal(navigation[0].context.plan_ref, plan); assert.equal(navigation[0].context.resource_view, 'selected_batches');
  const returned = navigation[0].context.return_decision_context;
  assert.deepEqual(clone(returned.detail_queries.preparation), detailQueries.preparation); assert.deepEqual(clone(returned.detail_queries.changeovers), { machine_ref: machine, ...detailQueries.changeovers });
  assert.equal(returned.detail_queries.resources.resource_ref, machine); assert.equal(returned.comparison_tab, 'preparation');
}
const turns = () => new Promise(resolve => setImmediate(resolve));
async function session() {
  for (const section of ['preparation', 'changeovers']) {
    const state = hooks(), { window: local } = runtime(state), calls = [], signals = [], overview = { data: { run: { run_ref: run }, scope: fixture().data.scope, metric_definitions: [] } };
    const props = { result: overview, section, query: {}, onQuery: q => { props.query = q; }, adapter: { [section]: async (run, q, signal) => { calls.push(clone(q)); signals.push(signal); if (calls.length === 1) throw new Error('首读失败'); return fixture(q, section); } } };
    let tree; async function render() { for (let i = 0; i < 3; i++) { tree = state.render(() => local.RunDecisionPreparation.Pane(props)); state.flush(); await turns(); } }
    await render(); assert.equal(calls.length, 1); assert(nodes(tree).some(node => node.type === 'error-box' && node.props.error));
    nodes(tree).find(node => node.props['aria-label'] === '刷新准备与切换明细').props.onClick(); await render(); assert.equal(calls.length, 2);
    nodes(tree).find(node => node.type === 'pager').props.onPage(2); await render(); assert.equal(calls.at(-1).page, 2); assert.equal(calls.at(-1).snapshot_ref, token);
    nodes(tree).find(node => node.props['aria-label'] === '准备与切换设备').props.onChange({ target: { value: machine } }); await render(); assert.equal(calls.at(-1).page, 1); assert.equal(calls.at(-1).snapshot_ref, undefined); assert.equal(calls.at(-1).machine_ref, machine);
    const filterValue = section === 'preparation' ? 'unplanned' : 'reference'; nodes(tree).find(node => node.type === 'select' && node.children.some(child => child && child.type === 'option' && child.props.value === filterValue)).props.onChange({ target: { value: filterValue } }); await render();
    assert.equal(calls.at(-1)[section === 'preparation' ? 'allocation_state' : 'event_side'], section === 'preparation' ? 'unplanned' : 'reference');
    if (section === 'preparation') {
      nodes(tree).find(node => node.type === 'pager').props.onPage(2); await render();
      assert.equal(calls.at(-1).snapshot_ref, token); assert.equal(calls.at(-1).work_scope, 'all');
      nodes(tree).find(node => node.props['aria-label'] === '准备需求范围').props.onChange({ target: { value: 'remaining' } }); await render();
      assert.equal(calls.at(-1).work_scope, 'remaining'); assert.equal(calls.at(-1).page, 1); assert.equal(calls.at(-1).snapshot_ref, undefined);
      assert.equal(calls.at(-1).machine_ref, machine); assert.equal(calls.at(-1).allocation_state, 'unplanned', '剩余需求范围保留当前设备与归属筛选');
      assert.equal(props.query.work_scope, 'remaining', '剩余需求筛选回写独立查询快照');
    }
    props.adapter[section] = (run, q, signal) => { calls.push(clone(q)); signals.push(signal); return new Promise(() => {}); };
    nodes(tree).find(node => node.props['aria-label'] === '刷新准备与切换明细').props.onClick(); await render(); nodes(tree).find(node => node.type === 'button' && text(node) === '取消读取').props.onClick(); await render(); assert(signals.at(-1).aborted);
  }
}
async function transport() {
  const calls = [], responses = [], adapter = A.create(async (url, options) => { calls.push({ url: new URL(url, 'http://localhost'), options }); return responses.shift(); });
  const json = value => ({ ok: true, headers: { get: key => key === 'Content-Type' ? 'application/json' : null }, json: async () => value });
  const download = { ok: true, headers: { get: key => ({ 'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'Content-Disposition': 'attachment; filename=decision.xlsx', 'X-Workbench-Run-Ref': run, 'X-Workbench-Snapshot-Ref': token, 'X-Workbench-Row-Count': '23' })[key] || null }, blob: async () => new Blob(['fixture']) };
  for (const section of ['preparation', 'changeovers']) {
    const q = { ...common, machine_ref: machine, page: 2, size: 20, snapshot_ref: token, ...(section === 'preparation' ? { allocation_state: 'unplanned', batch_ref: batch, work_scope: 'remaining' } : { event_side: 'reference' }) };
    responses.push(json(fixture(q, section))); await adapter[section](run, q); assert(calls.at(-1).url.pathname.endsWith('/' + section));
    responses.push(download); await adapter.decisionExport(run, { ...q, filter_section: section }, token, 'xlsx', undefined, 'all'); const params = calls.at(-1).url.searchParams;
    assert.equal(params.get('machine_ref'), machine); assert.equal(params.get('filter_section'), section); assert.equal(params.get('snapshot_ref'), token); assert.equal(params.has('page'), false); assert.equal(params.has('size'), false);
    assert.equal(params.get(section === 'preparation' ? 'allocation_state' : 'event_side'), section === 'preparation' ? 'unplanned' : 'reference');
    assert.equal(params.get('work_scope'), section === 'preparation' ? 'remaining' : null); assert.equal(params.get('batch_ref'), section === 'preparation' ? batch : null);
  }
}
async function main() { identities(); await session(); await transport(); console.log('decision preparation contract: saved target/effort vs AJ execution facts, legacy nulls, neutral coverage, exact remaining row/drill, work scope paging/filters/export, retry/cancellation passed'); }
main().catch(error => { console.error(error); process.exitCode = 1; });
