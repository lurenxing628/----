'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { compile } = require('../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '..');
const appDir = path.join(root, 'frontend/workbench/app');
const compiledMap = new Map(
  compile({
    sources: [
      'WorkbenchTerms.js',
      'WorkbenchReferences.jsx',
      'PreflightContract.js',
      'PreflightControls.jsx',
      'PreflightWorkspace.jsx',
      'BatchSplitPanel.jsx',
      'WorkbenchFormat.js',
      'FieldContract.js',
      'FieldControls.jsx',
    ].map(name => ({ path: name, code: fs.readFileSync(path.join(appDir, name), 'utf8') })),
    check_combined: false,
  }).outputs.map(out => [out.path, out.code])
);
const React = { createElement(type, props, ...children) {
  const values = { ...props, children: children.flat(Infinity) };
  return typeof type === 'function' ? type(values) : { type, props: values };
} };
const context = vm.createContext({ window: {}, React });
for (const name of ['WorkbenchTerms.js', 'WorkbenchReferences.jsx']) {
  vm.runInContext(compiledMap.get(name), context, { filename: name });
}
const T = context.__wbRuntime.getModule('WorkbenchTerms.js').default;
const { WorkbenchReference: Ref, WorkbenchError: ErrorBox } = context.__wbRuntime.getModule('WorkbenchReferences.jsx');
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
  name_missing: '名称未填写', shared_operation: '共同工序', overdue: '超期',
  current_official: '当前正式', historical_official: '历史正式', baseline_plan: '排产时的正式计划', initial_plan: '初始计划',
  run_statuses: { queued: '等待计算', running: '正在计算', complete: '计算完成', partial: '已产出部分结果', failed: '计算失败', interrupted: '已中断' },
  candidate_statuses: { completed: '计算完成', partial: '工序未排齐' },
  trial_draft_statuses: { editing: '可继续试调', saved: '已保存', discarded: '已放弃' },
  material_strategies: { strict: '等整批物料齐套', stage: '按工序物料齐套' },
  material_descriptions: { strict: '这批全部用料到齐后，再安排工序开工。', stage: '每道工序只等本序和前序用料，不等后续用料。' },
  execution_states: { unreported: '待报工', started: '已开工', partial: '部分完成', complete: '已完工' },
  data_quality: { complete: '完整', incomplete: '不完整', invalid: '需复核' },
  delivery_risks: { overdue: '预计超期', on_time: '预计按期', unknown: '交付待确认', not_applicable: '未指定交期' },
  arrangement_labels: { status: '工序安排', planned_finish: '预计完工', partial_finish: '已安排工序预计结束',
    complete: '工序已排齐', unplanned: '未安排', other_unplanned: '其他未安排', deferred: '缺料未安排' },
  delivery_completion_states: { complete: '工序已排齐', deferred: '因缺料暂未安排', incomplete: '工序未排齐', unknown: '工序安排待确认' },
  resource_kinds: { machine: '设备', operator: '人员' },
  member_units: { batch: '批', operation: '道工序', machine: '台设备', operator: '人', record: '项' },
  skill_levels: { beginner: '初级', normal: '普通', expert: '熟练' }, primary_machine: { no: '否', yes: '是' },
  yes_no: { yes: '是', no: '否' }, op_type_categories: { internal: '自制', external: '外协', both: '自制和外协都可' },
  merge_modes: { separate: '分别设置', merged: '合并设置' },
  operation_statuses: { pending: '待排', scheduled: '已排', processing: '加工中', completed: '已完工', skipped: '已跳过' },
  batch_priorities: { normal: '普通', urgent: '急件', critical: '特急' },
  batch_statuses: { pending: '待排', scheduled: '已排', processing: '加工中', completed: '已完成', cancelled: '已取消' },
  ready_statuses: { yes: '齐套', partial: '部分齐套', no: '未齐套' }, operation_sources: { internal: '自制', external: '外协' },
  resource_statuses: { active: '启用', inactive: '停用', maintain: '停机' },
  missing_resource_policies: { auto_assign: '自动分配', exclude: '暂不排' }, completed_policies: { preserve_actuals: '保留开工和完工记录' },
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
// 取值词表：已知字段显示中文，派工规则令牌带参数也能读，不认识的码不显示原文。
assert.equal(T.condition_value('dispatch_mode', 'sgs'), '智能派工');
assert.equal(T.condition_value('dispatch_rule', 'atc:k=4.0'), '综合判断更紧急的先做（交期视野 4.0）');
assert.equal(T.condition_value('dispatch_rule', 'unknown_rule'), '其他派工规则');
assert.equal(T.condition_value('sort_strategy', 'unknown'), '其他取值');
assert.equal(T.condition_value('freeze_window_enabled', 'yes'), '是');
assert.equal(T.condition_value('time_budget_seconds', 10), '10');
assert.equal(T.condition_value('algo_mode', null), '未记录');
// 是/否只给登记过的开关字段；图号、分件编号这类自由文本恰好写成 yes/no 也照原值显示。
assert.equal(T.condition_value('graph_block_on_cycle', 'no'), '否');
assert.equal(T.condition_value('auto_assign_enabled', 'yes'), '是');
assert.equal(T.condition_value('part_no', 'yes'), 'yes');
assert.equal(T.condition_value('piece_id', 'no'), 'no');
// 历史条件的受控枚举按业务概念显示中文；同名 status 按条件分类取批次、工序或资料的词表。
assert.deepEqual([['material_strategy', 'strict'], ['missing_resource_policy', 'auto_assign'], ['completed_policy', 'preserve_actuals'],
  ['priority', 'urgent'], ['ready_status', 'partial'], ['source', 'internal'], ['merge_mode', 'merged'], ['is_primary', 'yes'],
  ['execution_state', 'started'], ['target_basis', 'piece'], ['objective', 'min_overdue'], ['objective_name', 'min_tardiness']]
  .map(([field, value]) => T.condition_value(field, value)),
  ['等整批物料齐套', '自动分配', '保留开工和完工记录', '急件', '部分齐套', '自制', '合并设置', '是', '已开工', '分件工序数量', '交期优先', '拖期更轻']);
assert.deepEqual([['batch', 'pending'], ['batch', 'cancelled'], ['requirements', 'completed'], ['materials_outsource', 'inactive'], ['resource_qualifications', 'maintain']]
  .map(([category, value]) => T.condition_value('status', value, category)), ['待排', '已取消', '已完工', '停用', '停机']);
assert.equal(T.condition_value('priority', 'new_priority'), '其他取值');
assert.equal(T.condition_value('status', 'archived', 'batch'), '其他取值');
assert.equal(T.condition_value('objective', 'new_objective'), '其他优化目标');
assert.equal(T.search_stage('graph_ready_v2_repaired'), '修整优化排法');
assert.equal(T.search_stage('new_stage'), '其他搜索阶段');
assert.equal(T.execution_kind('decision_reused'), '沿用已算结果');
assert.equal(T.process_flag('final'), '最终记录');
assert.equal(T.process_flag('new_flag'), '其他标记');
assert.equal(T.run_status('interrupted'), '已中断');
assert.equal(T.run_status('new_state'), '其他状态');
// 试调草稿状态与约束检查结果是两张表；保存的试调方案读回的保存值不准入，词表外的码也显示中文。
assert.deepEqual(['editing', 'discarded', 'valid'].map(T.trial_draft_status), ['可继续试调', '已放弃', '其他状态']);
assert.deepEqual(['valid', 'blocked', 'saved'].map(T.trial_constraint_status), ['通过', '有冲突，不能采用', '其他状态']);
assert.equal(T.delivery_issue('no_admission_baseline'), '排产时没有正式计划可供对比');
assert.equal(T.delivery_issue('new_reason'), '原因说明缺失');
// 计划的范围原因与试调的约束原因也在同一张表里。
assert.equal(T.delivery_issue('deferred_operation_source_missing'), '待料工序的来源批次未知');
assert.equal(T.delivery_issue('trial_constraints_blocked'), '试调安排有约束冲突');
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
const { failure } = context.__wbRuntime.getModule('shared/contract/kit.js');
const original = failure('请先填写批次数量。', { code: 'quantity.required', requestKey: hash });
const business = ErrorBox({ error: original, fields: [{ path: 'quantity', message: original.message }] });
assert.equal(text(business, true).match(/请先填写批次数量。/g).length, 1);
assert(!text(business, true).includes(hash));
assert(!text(business, true).includes('quantity.required'));
assert(text(business).includes(hash));
assert(text(business).includes('quantity.required'));
for (const message of ['工艺表.xlsx 缺少工序列，请修正后重试。', 'route_template.xlsx 缺少工序列，请修正后重试。', '无法读取 aps.db，请检查文件是否仍在原位置。']) {
  const tree = ErrorBox({ error: failure(message, { code: 'file.invalid' }) });
  assert(text(tree, true).includes(message), 'Keep actionable file context');
  assert(!text(tree, true).includes('file.invalid'));
  assert(text(tree).includes('file.invalid'));
}
// kit 文案里夹着编码、JSON 或异常名时同样只显示兜底句，原文进折叠区。
for (const message of ['HTTP 503: request_failed', 'TypeError: 无法读取', '{"message":"bad"}', '[1,2]', '{}', '引用 ' + hash + ' 已过期', 'request_failed', '资格检查 qualification.empty']) {
  const tree = ErrorBox({ error: failure(message), fallback: '保存未完成，请重试。' });
  assert(text(tree, true).includes('保存未完成，请重试。'));
  assert(!text(tree, true).includes(message));
  assert(text(tree).includes(message));
}
// 不是 kit 统一错误对象的（程序内部 TypeError、浏览器异常、别处 new 出来的 Error），原文再像中文也不当用户文案：
// 界面只显示中文兜底句，原文和错误类型只进折叠的“原始错误信息”。
for (const error of [new TypeError("Cannot read properties of undefined (reading 'data')"), new DOMException('The user aborted a request.', 'AbortError'),
  new Error('请先填写批次数量。')]) {
  const tree = ErrorBox({ error });
  assert.equal(text(tree, true).trim(), '操作未完成，请核对后重试。');
  assert(text(tree).includes('原始错误信息') && text(tree).includes(error.message));
  if (error.name !== 'Error') assert(text(tree).includes(error.name));
}
assert.equal(text(ErrorBox({ error: new RangeError('Invalid time value'), fallback: '候选方案读取失败，请刷新后重试。' }), true).trim(), '候选方案读取失败，请刷新后重试。');
// 只能放一句话的地方（禁用理由）用 errorText，与错误框同一条规则。
const { errorText } = context.__wbRuntime.getModule('WorkbenchReferences.jsx');
assert.equal(errorText(failure('计划已经更新，请刷新后重试。'), '维护状态查询失败。'), '计划已经更新，请刷新后重试。');
assert.equal(errorText(failure('HTTP 503: request_failed'), '维护状态查询失败。'), '维护状态查询失败。');
assert.equal(errorText(new TypeError('Failed to fetch'), '维护状态查询失败。'), '维护状态查询失败。');
assert.equal(errorText(new TypeError('Failed to fetch')), '操作未完成，请核对后重试。');
// 就地标红项由调用方（ResourceControls.ErrorBox）先滤掉；这里只收到剩下的字段行，同一句只显示一次。
const filtered = ErrorBox({ error: failure('必填项未完成。'), hideMessage: true, fields: [
  { path: 'due_date', message: '请选择交期。' }, { path: 'due_date', message: '请选择交期。' }
] });
assert(!text(filtered, true).includes('必填项未完成。'));
assert.equal(text(filtered, true).match(/请选择交期。/g).length, 1);
const diagnosticOnly = ErrorBox({ error: original, hideMessage: true });
assert.equal(text(diagnosticOnly, true).trim(), '');
assert(text(diagnosticOnly).includes(hash));
// 齐套规则只有 strict 和 stage；值域外的 split 按记录无效显示，关闭检查时也不能回显成正在生效。
assert.equal(T.material_strategy('strict', false), '未启用（齐套检查已关闭）');
assert(Object.isFrozen(T.material_descriptions));

function load(name) {
  vm.runInContext(compiledMap.get(name), context, { filename: name });
}
function nodes(tree, predicate) {
  if (!tree || typeof tree !== 'object') return [];
  return (predicate(tree) ? [tree] : []).concat(tree.props.children.flatMap(child => nodes(child, predicate)));
}
let id = 0;
React.useId = () => 'material-test-' + ++id;
context.__wbRuntime.setStub('ResourceControls.jsx', {
  ErrorBox,
  Button: props => React.createElement('button', props, ...props.children),
  Field: props => React.createElement('label', props, ...props.children),
  FieldCell: props => props.children,
});
load('PreflightContract.js'); load('PreflightControls.jsx');
const C = context.__wbRuntime.getModule('PreflightContract.js'), refA = 'a'.repeat(48), refB = 'b'.repeat(48);
const input = { ...C.defaults(), batch_refs: [refA], start_date: '2026-10-08', end_date: '2026-10-14', material_strategy: 'stage' };
const removed = Object.freeze({ ...input, material_strategy: 'split' });
assert.throws(() => C.initial(removed), /请核对已选批次/, 'A split entry is rejected, never rewritten to strict');
assert.throws(() => C.input(removed), /请核对已选批次/, 'Saved input outside strict/stage is rejected');
const patches = [], props = { value: input, onChange: value => patches.push(JSON.parse(JSON.stringify(value))), onInspectMaterials() {}, disabled: false };
const ruleTree = context.__wbRuntime.getModule('PreflightControls.jsx').Rules(props);
const materialGroup = nodes(ruleTree, node => node.type === 'fieldset')[0];
const materialRadios = nodes(materialGroup, node => node.type === 'input' && node.props.type === 'radio');
assert.equal(materialRadios.length, 2, 'Quantity splitting is not a third material rule');
materialRadios[0].props.onChange();
assert.deepEqual(patches.pop(), { material_strategy: 'strict' }, 'Choosing a rule must not secretly enable readiness checking');
assert.equal(nodes(ruleTree, node => node.type === 'button' && text(node) === '检查物料可做数量').length, 1);
const uncheckedTree = context.__wbRuntime.getModule('PreflightControls.jsx').Rules({ ...props, value: { ...input, ready_check: false, material_strategy: 'strict' } });
assert(nodes(uncheckedTree, node => node.type === 'fieldset')[0].props.disabled);
assert(nodes(nodes(uncheckedTree, node => node.type === 'fieldset')[0], node => node.type === 'input').every(node => node.props.disabled));
assert(nodes(uncheckedTree, node => node.type === 'button' && text(node) === '检查物料可做数量')[0].props.disabled);

// 用同一个组件的实际回调确认：拆批只改选批次，保留用户选定的 stage / ready_check。
let stateCursor = 0; const states = [], remembered = [];
React.useState = initial => { const slot = stateCursor++; if (!(slot in states)) states[slot] = typeof initial === 'function' ? initial() : initial;
  return [states[slot], value => { states[slot] = typeof value === 'function' ? value(states[slot]) : value; }]; };
React.useMemo = fn => fn(); React.useCallback = fn => fn; React.useRef = value => ({ current: value }); React.useEffect = () => {};
context.__wbRuntime.setStubs({
  'PreflightAPI.js': { create: () => ({}) },
  'WorkbenchPageContext.jsx': { useSnapshot: value => remembered.push(value) },
  'RunPresentation.js': { step: () => 1 },
  'BatchSplitPanel.jsx': 'SplitPanelFixture',
});
load('PreflightWorkspace.jsx');
const render = () => { stateCursor = 0; return context.__wbRuntime.getModule('PreflightWorkspace.jsx')({ initialContext: input, renderRunPanel: () => null }); };
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
context.__wbRuntime.setStubs({
  'BatchSplitPanel.jsx': undefined,
  'BatchAPI.js': { create: () => ({ detail() { reads++; throw new Error('Disabled panel must not read'); } }) },
  'BatchContract.js': {},
  'shared/session/query.js': { useCommand: () => ({ locked: false }) },
  'WorkbenchGuards.js': { useDirtyGuard: () => ({}) },
  'ResourceForms.jsx': { Feedback: () => null },
});
load('BatchSplitPanel.jsx'); stateCursor = 0; states.length = 0;
const disabledPanel = context.__wbRuntime.getModule('BatchSplitPanel.jsx')({ refs: [refA], day: input.start_date, disabled: true });
assert(nodes(disabledPanel, node => node.type === 'input')[0].props.disabled);
nodes(disabledPanel, node => node.type === 'button' && text(node) === '查看可做数量')[0].props.onClick();
assert.equal(reads, 0);

// Report rejections, withdrawal preview and import rows share complete, readable conflict facts.
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
// The transport's unified error is the kit failure: conflicts sit beside message and code.
const rejected = { phase: 'idle', locked: false, error: failure('请先处理下面列出的影响。', { code: 'constraint_conflict', conflicts, status: 409 }) };
const failureTree = context.__wbRuntime.getModule('FieldControls.jsx').Feedback({ command: rejected }), visibleFailure = text(failureTree, true);
for (const label of ['20 热处理', '30 检验', '分件 A']) assert(visibleFailure.includes(label));
assert.equal((visibleFailure.match(/后道工序的执行或正式安排依赖本工序完工/g) || []).length, 2);
assert.equal((visibleFailure.match(/请先处理下面列出的影响/g) || []).length, 1);
assert(visibleFailure.includes('正式 v') && visibleFailure.includes('08:30:17.123456') && visibleFailure.includes('2026-10-26'));
for (const conflict of conflicts) {
  assert(text(failureTree).includes(conflict.operation_ref) && text(failureTree).includes(conflict.plan.task_ref));
  assert(!visibleFailure.includes(conflict.operation_ref) && !visibleFailure.includes(conflict.code));
}
assert.equal(context.__wbRuntime.getModule('FieldControls.jsx').Conflicts({ rows: [] }), null);
process.stdout.write('WorkbenchTerms, references and material rule contracts passed (isolated React element fixture).\n');
