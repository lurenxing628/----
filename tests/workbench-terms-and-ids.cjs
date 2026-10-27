'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
const babel = require(path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'));
const React = { createElement(type, props, ...children) {
  const values = { ...props, children: children.flat(Infinity) };
  return typeof type === 'function' ? type(values) : { type, props: values };
} };
const context = vm.createContext({ window: {}, React });
for (const name of ['WorkbenchTerms.js', 'WorkbenchReferences.jsx']) {
  const source = fs.readFileSync(path.join(root, 'frontend/workbench/app', name), 'utf8');
  vm.runInContext(name.endsWith('.jsx') ? babel.transform(source, { presets: ['react'] }).code : source, context);
}
const T = context.window.WorkbenchTerms, Ref = context.window.WorkbenchReference, ErrorBox = context.window.WorkbenchError;
function text(tree, omitReferences = false) {
  if (tree === null || tree === undefined || tree === false) return '';
  if (typeof tree !== 'object') return String(tree);
  if (omitReferences && tree.type === 'details' && tree.props.className === 'wb-ref') return '';
  return tree.props.children.map(child => text(child, omitReferences)).join('\n');
}
assert.equal(T.overdue_count, '预计超期批次');
assert.equal(T.total_tardiness_hours, '总拖期');
assert.equal(T.candidate, '候选方案');
assert.equal(T.actions.save, '保存');
assert.deepEqual(JSON.parse(JSON.stringify(T)), {
  overdue_count: '预计超期批次', delay_hours: '超期时长', total_tardiness_hours: '总拖期', utilization: '利用率',
  candidate: '候选方案', official_plan: '正式计划', trial: '试调', trial_draft: '试调草稿', trial_scenario: '试调方案',
  hours_unit: '小时', handler: '经办人', recorder: '记录人', owner: '责任人',
  refresh_latest: '刷新最新资料', accept_latest: '已核对，继续编辑', personal_calendar: '个人日历',
  name_missing: '名称未填写', legacy_field_records: '历史现场记录', shared_operation: '共同工序', overdue: '超期',
  current_official: '当前正式', historical_official: '历史正式', baseline_plan: '排产时的正式计划', initial_plan: '初始计划',
  run_statuses: { queued: '等待计算', running: '正在计算', complete: '计算完成', partial: '已产出部分结果', failed: '计算失败', interrupted: '已中断' },
  candidate_statuses: { completed: '计算完成', partial: '工序未排齐', failed: '计算失败', skipped: '未计算' },
  material_strategies: { strict: '等整批物料齐套', stage: '按工序物料齐套' },
  material_descriptions: { strict: '这批全部用料到齐后，再安排工序开工。', stage: '每道工序只等本序和前序用料，不等后续用料。' },
  execution_states: { unreported: '待报工', started: '已开工', partial: '部分完成', paused: '已暂停', exception: '异常', complete: '已完工' },
  data_quality: { complete: '完整', incomplete: '不完整', legacy_incomplete: '历史资料不完整', invalid: '需复核' },
  delivery_risks: { overdue: '预计超期', on_time: '预计按期', unknown: '交付待确认', not_applicable: '未指定交期' },
  arrangement_labels: { status: '工序安排', planned_finish: '预计完工', partial_finish: '已安排工序预计结束',
    complete: '工序已排齐', unplanned: '未安排', other_unplanned: '其他未安排', deferred: '缺料未安排' },
  delivery_completion_states: { complete: '工序已排齐', deferred: '因缺料暂未安排', incomplete: '工序未排齐', unknown: '工序安排待确认' },
  resource_kinds: { machine: '设备', operator: '人员' },
  resource_views: { selected_batches: '本次选中批次', full_candidate: '整份候选方案' },
  resource_metric_labels: { available_hours: '可排总时长', occupied_hours: '班表内已占时间', summed_load_hours: '班表内逐工序占用合计',
    overlap_hours: '班表内重复计入时长', outside_calendar_hours: '安排跨度跨非工作时段', utilization_ratio: '班表内占用比例', demand_ratio: '工序合计占用比例',
    span_occupied_hours: '全部已占时间', span_summed_hours: '逐工序占用合计', span_overlap_hours: '重复计入时长',
    peak_utilization: '单日最高占用比例', balance_cv: '资源占用差异', unknown_days: '班表待确认天数' },
  resource_states: { complete: '资料齐全', partial: '部分资料缺失', unavailable: '资料待确认', not_applicable: '不适用' },
  changeover_count: '工种切换次数', algorithm_changeover_count: '算法工种切换',
  operation_effort_labels: { setup_standard_hours: '准备标准工时', processing_standard_hours: '加工标准工时', required_standard_hours: '所需标准工时',
    unit_standard_hours: '保存的单件加工定额', standard_total_hours: '保存的总标准工时', target_quantity: '排产目标量', execution_target_quantity: '报工目标量', remaining_quantity: '报工剩余量',
    quantity_basis: '排产数量依据', execution_quantity_basis: '报工数量依据', setup_state: '准备状态', requirement_role: '本次安排方式', external_cycle_days: '外协周期（天）' },
  effort_basis_labels: { runtime_requirement_v1: '排产时保存的工时需求', archived_operation_standard: '保存的工序标准' },
  setup_states: { pending: '尚需准备', retained_in_execution: '沿用开工时的准备', already_completed: '准备已完成', external: '外协按周期', unknown: '准备记录缺失' },
  effort_roles: { new_schedule: '本次需安排', retained: '保留原安排', execution: '已开工工序', completed: '已报完工工序', not_scheduled: '本次未安排', unknown: '安排方式待确认' },
  preparation_allocations: { new_schedule: '本次新排', unplanned: '其他未安排', deferred: '缺料未安排', retained: '保留原安排', execution: '已开工工序', completed: '已报完工工序', external: '外协按周期', unknown: '安排方式待确认' },
  effort_quantity_bases: { piece: '分件工序数量', batch: '批次目标数量', unknown: '数量依据待确认' },
  changeover_sides: { selected: '所选候选', reference: '比较基准' },
  due_states: { specified: '明确交期', unspecified: '未指定交期', invalid: '交期无效' },
  due_issues: { due_date_missing: '交期缺失', due_date_invalid: '交期无效' },
  report_actions: { create: '新增', supplement: '补齐', correct: '更正' },
  actions: { add: '新增', save: '保存', confirm: '确认', cancel: '取消', clear: '清除', import: '导入', export: '导出', download: '下载',
    refresh: '刷新', query_result: '查询结果', adopt: '采用' },
  outcomes: { stale: '数据已更新，请刷新后重试。刚才的选择已保留。', unavailable: '此功能尚未开通。',
    failure: '操作没有完成。请刷新重试；仍不行请联系维护人员，并告知下方编号。' }
});
assert(Object.isFrozen(T.outcomes));
// 执行状态、数据完整性、交付判断各只留一套叫法：现场记录、排产候选、试调、值班台都从这里取。
assert(Object.isFrozen(T.execution_states) && Object.isFrozen(T.data_quality) && Object.isFrozen(T.delivery_risks));
assert.equal(T.outcomes.pending('保存'), '上次保存的结果还没查到，可能已经生效。请点「查询结果」，不要重复提交。');
assert.equal(T.outcomes.rejected('采用', '批次号重复'), '上次采用没有生效：批次号重复。填写内容已保留，改好后重新提交。');
assert.equal(T.outcomes.rejected('采用', '批次号重复。'), '上次采用没有生效：批次号重复。填写内容已保留，改好后重新提交。');
assert.equal(T.outcomes.done('导入'), '导入已完成。');
assert.equal(T.outcomes.done('导入', '请到批次管理查看'), '导入已完成。请到批次管理查看。');
assert.equal(T.outcomes.unknown('提交'), '提交结果不确定，可能已经生效。请刷新后核对，不要重复提交。');
assert.equal(T.plan_version(3), '正式 v3');
assert.equal(T.download_started('批次.xlsx'), '已交给浏览器下载：批次.xlsx');
assert.equal(T.data_as_of('2026-09-21 16:00'), '本次刷新 2026-09-21 16:00');
assert(Object.isFrozen(T));
assert(Object.isFrozen(T.actions));
assert.equal(Ref({}), null);
assert.equal(Ref({ entries: { '资源编号': null, '操作编号': '' } }), null);
const hash = '0123456789abcdef'.repeat(3);
const refs = Ref({ entries: { '排产编号': hash, '操作编号': 'request-123' } });
assert.equal(refs.type, 'details');
assert.equal(refs.props.className, 'wb-ref');
assert.equal(refs.props.open, undefined);
assert(text(refs).includes(hash));
assert.equal(text(refs, true), '');
assert(text(Ref({ value: 0 })).includes('0'));
assert(text(Ref({ value: '<script>bad()</script>' })).includes('<script>bad()</script>'));
assert.equal(Ref({ value: 'r1' }).props.dangerouslySetInnerHTML, undefined);
assert.equal(ErrorBox({ error: null }), null);
const original = Object.freeze({ message: '请先填写批次数量。', code: 'quantity.required', requestKey: hash });
const business = ErrorBox({ error: original, fields: [{ path: 'quantity', message: original.message }] });
assert.equal(text(business, true).match(/请先填写批次数量。/g).length, 1);
assert(!text(business, true).includes(hash));
assert(!text(business, true).includes('quantity.required'));
assert(text(business).includes(hash));
assert(text(business).includes('quantity.required'));
for (const message of ['工艺表.xlsx 缺少工序列，请修正后重试。', 'route_template.xlsx 缺少工序列，请修正后重试。', '无法读取 aps.db，请检查文件是否仍在原位置。']) {
  const tree = ErrorBox({ error: { message, code: 'file.invalid' } });
  assert(text(tree, true).includes(message), 'Keep actionable file context');
  assert(!text(tree, true).includes('file.invalid'));
  assert(text(tree).includes('file.invalid'));
}
for (const message of ['HTTP 503: request_failed', 'TypeError: 无法读取', '{"message":"bad"}', '[1,2]', '{}', '引用 ' + hash + ' 已过期', 'request_failed', '资格检查 qualification.empty']) {
  const tree = ErrorBox({ error: { message }, fallback: '保存未完成，请重试。' });
  assert(text(tree, true).includes('保存未完成，请重试。'));
  assert(!text(tree, true).includes(message));
  assert(text(tree).includes(message));
}
const filtered = ErrorBox({ error: { message: '必填项未完成。' }, hideMessage: true, fields: [
  { path: 'quantity', message: '请填写数量。' }, { path: 'due_date', message: '请选择交期。' }, { path: 'due_date', message: '请选择交期。' }
], excludePaths: ['quantity'] });
assert(!text(filtered, true).includes('请填写数量。'));
assert(!text(filtered, true).includes('必填项未完成。'));
assert.equal(text(filtered, true).match(/请选择交期。/g).length, 1);
const diagnosticOnly = ErrorBox({ error: original, hideMessage: true });
assert.equal(text(diagnosticOnly, true).trim(), '');
assert(text(diagnosticOnly).includes(hash));
// 齐套规则只有 strict 和 stage；值域外的 split 按记录无效显示，关闭检查时也不能回显成正在生效。
assert.equal(T.material_strategy('split', true), '记录无效');
assert.equal(T.material_strategy('stage', false), '未启用（齐套检查已关闭）');
assert.equal(T.material_strategy(null, true), '未记录');
assert.equal(T.material_strategy('stage', null), '未记录');
assert(Object.isFrozen(T.material_descriptions));

function load(name) {
  const source = fs.readFileSync(path.join(root, 'frontend/workbench/app', name), 'utf8');
  vm.runInContext(name.endsWith('.jsx') ? babel.transform(source, { presets: ['react'] }).code : source, context);
}
function nodes(tree, predicate) {
  if (!tree || typeof tree !== 'object') return [];
  return (predicate(tree) ? [tree] : []).concat(tree.props.children.flatMap(child => nodes(child, predicate)));
}
let id = 0;
React.useId = () => 'material-test-' + ++id;
context.window.ResourceControls = { ErrorBox, Button: props => React.createElement('button', props, ...props.children),
  Field: props => React.createElement('label', props, ...props.children) };
load('PreflightContract.js'); load('PreflightControls.jsx');
const C = context.window.PreflightContract, refA = 'a'.repeat(48), refB = 'b'.repeat(48);
const input = { ...C.defaults(), batch_refs: [refA], start_date: '2026-10-08', end_date: '2026-10-14', material_strategy: 'stage' };
const removed = Object.freeze({ ...input, material_strategy: 'split' });
assert.throws(() => C.initial(removed), /请核对已选批次/, 'A split entry is rejected, never rewritten to strict');
assert.throws(() => C.input(removed), /请核对已选批次/, 'Saved input outside strict/stage is rejected');
const patches = [], props = { value: input, onChange: value => patches.push(JSON.parse(JSON.stringify(value))), onInspectMaterials() {}, disabled: false };
const ruleTree = context.window.PreflightControls.Rules(props);
const materialGroup = nodes(ruleTree, node => node.type === 'fieldset')[0];
const materialRadios = nodes(materialGroup, node => node.type === 'input' && node.props.type === 'radio');
assert.equal(materialRadios.length, 2, 'Quantity splitting is not a third material rule');
materialRadios[0].props.onChange();
assert.deepEqual(patches.pop(), { material_strategy: 'strict' }, 'Choosing a rule must not secretly enable readiness checking');
assert.equal(nodes(ruleTree, node => node.type === 'button' && text(node) === '检查物料可做数量').length, 1);
const uncheckedTree = context.window.PreflightControls.Rules({ ...props, value: { ...input, ready_check: false, material_strategy: 'strict' } });
assert(nodes(uncheckedTree, node => node.type === 'fieldset')[0].props.disabled);
assert(nodes(nodes(uncheckedTree, node => node.type === 'fieldset')[0], node => node.type === 'input').every(node => node.props.disabled));
assert(nodes(uncheckedTree, node => node.type === 'button' && text(node) === '检查物料可做数量')[0].props.disabled);

// 用同一个组件的实际回调确认：拆批只改选批次，保留用户选定的 stage / ready_check。
let stateCursor = 0; const states = [], remembered = [];
React.useState = initial => { const slot = stateCursor++; if (!(slot in states)) states[slot] = typeof initial === 'function' ? initial() : initial;
  return [states[slot], value => { states[slot] = typeof value === 'function' ? value(states[slot]) : value; }]; };
React.useMemo = fn => fn(); React.useCallback = fn => fn; React.useRef = value => ({ current: value }); React.useEffect = () => {};
context.window.PreflightAPI = { create: () => ({}) };
context.window.WorkbenchPageContext = { useSnapshot: value => remembered.push(value) };
context.window.RunPresentation = { step: () => 1 };
context.window.BatchSplitPanel = 'SplitPanelFixture';
load('PreflightWorkspace.jsx');
const render = () => { stateCursor = 0; return context.window.PreflightWorkspace({ initialContext: input, renderRunPanel: () => null }); };
let workspace = render();
nodes(workspace, node => node.type === 'button' && text(node) === '检查物料可做数量')[0].props.onClick();
workspace = render();
let panel = nodes(workspace, node => node.type === 'SplitPanelFixture')[0];
const ruleRows = nodes(workspace, node => node.props.className === 'pf-rows')[0], actionRow = ruleRows.props.children.findIndex(node => node && node.props && node.props.className === 'pf-split-action');
assert.equal(ruleRows.props.children[actionRow + 1], panel, 'Quantity inputs appear directly beside the action, inside the rule column');
panel.props.onCommitted(refB, refA); workspace = render();
assert.deepEqual(Array.from(remembered.at(-1).batch_refs), [refB]);
assert.equal(remembered.at(-1).material_strategy, 'stage'); assert.equal(remembered.at(-1).ready_check, true);
panel = nodes(workspace, node => node.type === 'SplitPanelFixture')[0]; panel.props.onActivityChange(true); workspace = render();
assert(nodes(workspace, node => node.type === 'input' && node.props.type === 'date').every(node => node.props.disabled));
assert(nodes(workspace, node => node.type === 'button' && text(node) === '收起数量检查')[0].props.disabled, 'Do not unmount a pending split command');
assert(nodes(workspace, node => node.type === 'button' && text(node) === '开始排产检查')[0].props.disabled);

let reads = 0;
context.window.APSBatchAPI = { create: () => ({ detail() { reads++; throw new Error('Disabled panel must not read'); } }) };
context.window.APSBatchContract = {};
context.window.APSResourceSession = { useCommand: () => ({ locked: false }) };
context.window.WorkbenchGuards = { useDirtyGuard: () => ({}) };
context.window.ResourceForms = { Feedback: () => null };
load('BatchSplitPanel.jsx'); stateCursor = 0; states.length = 0;
const disabledPanel = context.window.BatchSplitPanel({ refs: [refA], day: input.start_date, disabled: true });
assert(nodes(disabledPanel, node => node.type === 'input')[0].props.disabled);
nodes(disabledPanel, node => node.type === 'button' && text(node) === '查看可做数量')[0].props.onClick();
assert.equal(reads, 0);

// Report rejections, withdrawal preview and import rows share complete, readable conflict facts.
context.window.ResourceControls.ErrorBox = ErrorBox;
load('WorkbenchFormat.js'); load('FieldContract.js'); load('FieldControls.jsx');
const conflicts = [
  { code: 'downstream_requires_completion', operation_ref: 'c'.repeat(48), operation_code: 'STRESS-B-001_20',
    batch_id: 'STRESS-B-001', operation_label: '20 热处理', piece_id: null,
    message: '后道工序的执行或正式安排依赖本工序完工',
    plan: { plan_ref: 'd'.repeat(48), task_ref: 'e'.repeat(48), version: 5, start: '2026-10-20T08:30:17.123456', end: '2026-10-23T08:00:00' } },
  { code: 'downstream_requires_completion', operation_ref: 'f'.repeat(48), operation_code: 'STRESS-B-001_30',
    batch_id: 'STRESS-B-001', operation_label: '30 检验', piece_id: 'A',
    message: '后道工序的执行或正式安排依赖本工序完工',
    plan: { plan_ref: 'd'.repeat(48), task_ref: '1'.repeat(48), version: 5, start: '2026-10-26T10:44:00', end: '2026-10-26T13:44:00' } }
];
// The transport's unified error is flat: conflicts sit beside message and code.
const rejected = { phase: 'idle', locked: false, error: { message: '请先处理下面列出的影响。', code: 'constraint_conflict', fields: [], conflicts,
  committed: false, status: 409, requestRef: null, requestKey: null, resultTarget: null } };
const failureTree = context.window.FieldControls.Feedback({ command: rejected }), visibleFailure = text(failureTree, true);
for (const label of ['20 热处理', '30 检验', '分件 A']) assert(visibleFailure.includes(label));
assert.equal((visibleFailure.match(/后道工序的执行或正式安排依赖本工序完工/g) || []).length, 2);
assert.equal((visibleFailure.match(/请先处理下面列出的影响/g) || []).length, 1);
assert(visibleFailure.includes('正式 v') && visibleFailure.includes('08:30:17.123456') && visibleFailure.includes('2026-10-26'));
for (const conflict of conflicts) {
  assert(text(failureTree).includes(conflict.operation_ref) && text(failureTree).includes(conflict.plan.task_ref));
  assert(!visibleFailure.includes(conflict.operation_ref) && !visibleFailure.includes(conflict.code));
}
assert.equal(context.window.FieldControls.Conflicts({ rows: [] }), null);
process.stdout.write('WorkbenchTerms, references and material rule contracts passed (isolated React element fixture).\n');
