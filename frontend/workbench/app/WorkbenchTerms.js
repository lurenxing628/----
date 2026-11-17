// 用户可见文案的前端词表与句式模板。词表决策：.codestable/compound/2026-09-13-decision-ui-copy-glossary.md
import WorkbenchFormat from './WorkbenchFormat.js';
import { objectiveLabel } from './RunGenerationContract.js';

const sentence = text => /[。！？；]$/.test(text) ? text : text + '。';
const countText = value => WorkbenchFormat.number(value, { digits: 0 });

// 缺料和其他未安排工序可以出现在同一批次，摘要按工序分别列出。
function missingArrangements(unplannedCount, deferredCount) {
  if (unplannedCount == null && deferredCount == null) return '未安排工序数待确认，请查看原因';
  const items = [];
  if (unplannedCount > 0) items.push(countText(unplannedCount) + ' 道工序' + (deferredCount > 0 ? '因其他原因未安排' : '未安排'));
  if (deferredCount > 0) items.push(countText(deferredCount) + ' 道工序因缺料暂未安排');
  return items.join('；');
}

function completionSummary(scope) {
  if (scope.state === 'not_applicable') return '本次没有需要安排的批次';
  const items = [];
  if (scope.complete_batch_count > 0) items.push(countText(scope.complete_batch_count) + ' 批工序已排齐');
  const missing = missingArrangements(scope.unplanned_operation_count, scope.deferred_operation_count);
  if (missing) items.push(missing);
  if (scope.unknown_batch_count > 0) items.push(countText(scope.unknown_batch_count) + ' 批工序安排待确认，请查看原因');
  return items.join('；');
}

const materialStrategies = Object.freeze({ strict: '等整批物料齐套', stage: '按工序物料齐套' });
// 排产输入的缺设备人员规则与执行记录规则（PreflightContract 准入的取值）：排产检查、排产任务、排产记录、候选方案、值班台和历史条件共用。
const missingResourcePolicies = Object.freeze({ auto_assign: '自动分配', exclude: '暂不排' });
const completedPolicies = Object.freeze({ preserve_actuals: '保留开工和完工记录' });
// 批次优先级、批次状态与齐套（Batches 与 BatchMaterials 的取值）：批次资料、排产检查、值班台、试调和历史条件共用。
const batchPriorities = Object.freeze({ normal: '普通', urgent: '急件', critical: '特急' });
const batchStatuses = Object.freeze({ pending: '待排', scheduled: '已排', processing: '加工中', completed: '已完成', cancelled: '已取消' });
const readyStatuses = Object.freeze({ yes: '齐套', partial: '部分齐套', no: '未齐套' });
// 批次工序状态（BatchOperations.status 的完整取值）：与批次状态是两个概念，不混用批次状态词表。
const operationStatuses = Object.freeze({ pending: '待排', scheduled: '已排', processing: '加工中', completed: '已完工', skipped: '已跳过' });
// 工序来源（BatchOperations.source）。
const operationSources = Object.freeze({ internal: '自制', external: '外协' });
// 设备、人员、供应商原资料行的启停状态（历史条件比对保存时的资料行）；资料页按资料类型投影的状态另见 resource-contract。
const resourceStatuses = Object.freeze({ active: '启用', inactive: '停用', maintain: '停机' });
const mergeModes = Object.freeze({ separate: '分别设置', merged: '合并设置' });
const primaryMachine = Object.freeze({ no: '否', yes: '是' });
// 报工执行状态：现场记录、实际甘特、报表、校准、排产候选、试调和值班台共用；与后端导出的“排产时报工状态”一致。
const executionStates = Object.freeze({ unreported: '待报工', started: '已开工', partial: '部分完成', complete: '已完工' });
const effortQuantityBases = Object.freeze({ piece: '分件工序数量', batch: '批次目标数量', unknown: '数量依据待确认' });

const deliveryIssues = Object.freeze({
  no_admission_baseline: '排产时没有正式计划可供对比', saved_plan_incomplete: '保存的工序安排记录不完整',
  operations_unscheduled: '尚有工序未安排', material_deferred: '工序因缺料暂未安排', operations_missing: '排产时工序资料未记录',
  due_date_missing: '交期未记录', due_date_invalid: '交期无效', part_label_missing: '图号或零件名称未填写',
  deferred_operation_source_missing: '待料工序的来源批次未知', trial_constraints_blocked: '试调安排有约束冲突'
});

const yesNo = Object.freeze({ yes: '是', no: '否' });
// 保存条件的受控取值按字段登记业务词表：排产配置（后端 scheduler/config/config_field_spec.py 的 choice_labels）、排产输入、
// 批次、工序、物料外协、资源与报工。同名的 status 在批次、工序、供应商、设备人员上取值不同，按条件分类再分一层。
// 没登记的字段是数字、日期、编号或自由文本（图号、分件编号等），照原值显示；历史条件详情、候选来源记录、计算过程共用。
const conditionValues = Object.freeze({
  sort_strategy: Object.freeze({ priority_first: '优先级优先', due_date_first: '交期优先', weighted: '综合优先级和交期', fifo: '先进先出' }),
  dispatch_mode: Object.freeze({ batch_order: '按批次顺序排', sgs: '智能派工' }),
  dispatch_rule: Object.freeze({ slack: '时间余量少的先做', cr: '交期更紧、剩余时间更吃紧的先做', atc: '综合判断更紧急的先做' }),
  algo_mode: Object.freeze({ greedy: '快速计算', improve: '精细计算' }),
  graph_analysis_mode: Object.freeze({ off: '关闭', report: '只看分析报告', on: '参与排产' }),
  auto_assign_enabled: yesNo, freeze_window_enabled: yesNo, graph_block_on_cycle: yesNo,
  material_strategy: materialStrategies, missing_resource_policy: missingResourcePolicies, completed_policy: completedPolicies,
  priority: batchPriorities, ready_status: readyStatuses, source: operationSources, merge_mode: mergeModes,
  is_primary: primaryMachine, execution_state: executionStates, target_basis: effortQuantityBases,
  status: Object.freeze({ batch: batchStatuses, requirements: operationStatuses, materials_outsource: resourceStatuses, resource_qualifications: resourceStatuses })
});
// 优化目标名（配置的 objective、所选方案的 objective_name、保存的主目标与同时探索方向）沿用排产生成契约的目标词表。
const objectiveFields = Object.freeze(['objective', 'objective_name', 'primary_objective', 'target_objectives']);
// 派工规则令牌：atc 可带交期视野参数（atc:k=<值>），其余规则不带参数。
function dispatchRule(token) {
  const match = /^atc:k=([0-9.]+)$/.exec(token);
  if (match) return conditionValues.dispatch_rule.atc + '（交期视野 ' + match[1] + '）';
  return conditionValues.dispatch_rule[token] || '其他派工规则';
}
// 保存的条件值：登记过的字段显示中文，词表外的码显示“其他取值”，不显示原文；category 只给 status 选批次、工序或资料的词表。
function conditionValue(field, value, category) {
  if (value === null || value === undefined || value === '') return '未记录';
  if (field === 'dispatch_rule') return dispatchRule(value);
  if (objectiveFields.includes(field)) return objectiveLabel(value);
  if (!Object.prototype.hasOwnProperty.call(conditionValues, field)) return String(value);
  const table = field === 'status' ? conditionValues.status[category] : conditionValues[field];
  return table[value] || '其他取值';
}
// 搜索阶段与候选来源类型（origin 与 phase 同一套取值）：计算过程、候选来源记录共用。
const searchStages = Object.freeze({ baseline: '起始排法', initial: '起始排法', multi_start: '尝试不同排法', multi_start_search: '尝试不同排法', profiles: '按规则生成排法',
  elite_repair: '局部调整排法', iterated_greedy: '继续调整工序顺序', graph_ready: '按优先顺序安排工序', graph_ready_search: '按优先顺序安排工序',
  graph_ready_elite_repair: '局部调整排法', graph_ready_iterated_greedy: '继续调整工序顺序', graph_ready_v2_generated: '生成优化排法',
  graph_ready_v2_repaired: '修整优化排法', graph_ready_v2_iterated_greedy: '继续改进排法', heuristic_candidate_search: '尝试不同工序顺序',
  grasp_ig_candidate_construction: '构建并调整排法', local_search: '调整已有排法', local_search_restart: '重新调整已有排法', completed: '计算结束' });
// 一次排法计算的执行方式（共享解码回执 execution_kind）。
const executionKinds = Object.freeze({ new_decision: '新算一次', trial_decode: '尝试调整后重算', capture_checkpoints: '补记中间状态', validation_decode: '复核计算',
  restore_parent: '恢复上一排法', decision_reused: '沿用已算结果', local_trial_reused: '沿用本轮计算', reference_reused: '沿用参照结果', decode_skipped: '未计算' });
// 排产记录状态（后端 RunState）：值班台、执行排产、排产记录、方案对比、历史与试调来源列表共用；词表外的码显示“其他状态”，不显示原文。
// 键序就是排产记录状态筛选的选项顺序。兜底的来源：历史列表与详情读的 WorkbenchHistoryEntries.state 没有枚举 CHECK，读取时也不准入取值。
const runStatuses = Object.freeze({ queued: '等待计算', running: '正在计算', complete: '计算完成', partial: '已产出部分结果', failed: '计算失败', interrupted: '已中断' });
// 候选方案状态（后端 facts/candidate_projection.py 按排齐程度派生 completed/partial）：候选目录、值班台、执行排产页头与
// 试调来源列表共用；写法同排产记录状态，词表外的码显示“其他状态”，不显示原文。兜底的来源：候选目录读的是保存的
// summary.catalog.status，读取只核身份和安排数、不准入状态取值（run/decision_source.py 的 _load_candidate_models、saved_candidate_catalog）。
const candidateStatuses = Object.freeze({ completed: '计算完成', partial: '工序未排齐' });
// 试调草稿状态：草稿表的 status 有枚举 CHECK；保存的试调方案读回的是快照里存的 status，读取时不准入取值，所以词表外的码显示“其他状态”。
const trialDraftStatuses = Object.freeze({ editing: '可继续试调', saved: '已保存', discarded: '已放弃' });
// 试调约束检查结果（validation.constraints_status）：草稿每次读取时现算；保存的试调方案快照与调整记录（WorkbenchTrialChanges.validation_json）
// 读回保存值，读取时不准入取值，所以词表外的码显示“其他状态”。
const trialConstraintStatuses = Object.freeze({ valid: '通过', warning: '有提示', blocked: '有冲突，不能采用' });
const processFlags = Object.freeze({ first_valid: '首次有效结果', first_expected_complete: '本次计算范围首次排齐', final: '最终记录', strict_improvement: '评分改善', segment_start: '开始新的比较' });

const WorkbenchTerms = Object.freeze({
  overdue_count: '预计超期批次', delay_hours: '超期时长', total_tardiness_hours: '总拖期',
  utilization: '利用率', candidate: '候选方案', official_plan: '正式计划', trial: '试调',
  resource_kinds: Object.freeze({ machine: '设备', operator: '人员' }),
  // 指标覆盖与缺项计数的对象单位（member_unit）：方案比较与历史走势共用。
  member_units: Object.freeze({ batch: '批', operation: '道工序', machine: '台设备', operator: '人', record: '项' }),
  // 人员技能等级与主操设备：可操作设备、人员资料文件与关联资料文件共用。
  skill_levels: Object.freeze({ beginner: '初级', normal: '普通', expert: '熟练' }),
  primary_machine: primaryMachine,
  resource_views: Object.freeze({ selected_batches: '本次选中批次', full_candidate: '整份候选方案' }),
  resource_metric_labels: Object.freeze({
    available_hours: '可排总时长', occupied_hours: '班表内已占时间', summed_load_hours: '班表内逐工序占用合计',
    overlap_hours: '班表内重复计入时长', outside_calendar_hours: '安排跨度跨非工作时段', utilization_ratio: '班表内占用比例', demand_ratio: '工序合计占用比例',
    span_occupied_hours: '全部已占时间', span_summed_hours: '逐工序占用合计', span_overlap_hours: '重复计入时长',
    peak_utilization: '单日最高占用比例', balance_cv: '资源占用差异', unknown_days: '班表待确认天数'
  }),
  resource_states: Object.freeze({ complete: '资料齐全', partial: '部分资料缺失', unavailable: '资料待确认', not_applicable: '不适用' }),
  changeover_count: '工种切换次数', algorithm_changeover_count: '算法工种切换',
  operation_effort_labels: Object.freeze({
    setup_standard_hours: '准备标准工时', processing_standard_hours: '加工标准工时', required_standard_hours: '所需标准工时',
    unit_standard_hours: '保存的单件加工定额', standard_total_hours: '保存的总标准工时', target_quantity: '排产目标量', execution_target_quantity: '报工目标量', remaining_quantity: '报工剩余量',
    quantity_basis: '排产数量依据', execution_quantity_basis: '报工数量依据', setup_state: '准备状态', requirement_role: '本次安排方式', external_cycle_days: '外协周期（天）'
  }),
  effort_basis_labels: Object.freeze({ runtime_requirement_v1: '排产时保存的工时需求', archived_operation_standard: '保存的工序标准' }),
  setup_states: Object.freeze({ pending: '尚需准备', retained_in_execution: '沿用开工时的准备', already_completed: '准备已完成', external: '外协按周期', unknown: '准备记录缺失' }),
  effort_roles: Object.freeze({ new_schedule: '本次需安排', retained: '保留原安排', execution: '已开工工序', completed: '已报完工工序', not_scheduled: '本次未安排', unknown: '安排方式待确认' }),
  preparation_allocations: Object.freeze({ new_schedule: '本次新排', unplanned: '其他未安排', deferred: '缺料未安排', retained: '保留原安排', execution: '已开工工序', completed: '已报完工工序', external: '外协按周期', unknown: '安排方式待确认' }),
  effort_quantity_bases: effortQuantityBases,
  changeover_sides: Object.freeze({ selected: '所选候选', reference: '比较基准' }),
  trial_draft: '试调草稿', trial_scenario: '试调方案', hours_unit: '小时',
  handler: '经办人', recorder: '记录人', owner: '责任人',
  // 2026-09-21 全站收口：同一概念只留一个叫法，各工作区从这里取，不再各写一份。
  refresh_latest: '刷新最新资料', accept_latest: '已核对，继续编辑', personal_calendar: '个人日历',
  name_missing: '名称未填写', shared_operation: '共同工序', overdue: '超期',
  current_official: '当前正式', historical_official: '历史正式',
  baseline_plan: '排产时的正式计划', initial_plan: '初始计划',
  batch_priorities: batchPriorities, batch_statuses: batchStatuses, ready_statuses: readyStatuses,
  operation_statuses: operationStatuses, operation_sources: operationSources, resource_statuses: resourceStatuses,
  missing_resource_policies: missingResourcePolicies, completed_policies: completedPolicies,
  // 排产记录状态与候选方案状态：值班台、执行排产、排产记录、试调列表共用同一套叫法。
  run_statuses: runStatuses,
  run_status: code => runStatuses[code] || '其他状态',
  candidate_statuses: candidateStatuses,
  candidate_status: code => candidateStatuses[code] || '其他状态',
  // 试调草稿状态与约束检查结果：试调列表、试调页、试调结果与试调导出共用同一套叫法。
  trial_draft_statuses: trialDraftStatuses,
  trial_draft_status: code => trialDraftStatuses[code] || '其他状态',
  trial_constraint_status: code => trialConstraintStatuses[code] || '其他状态',
  material_strategies: materialStrategies,
  yes_no: yesNo,
  condition_value: conditionValue,
  search_stage: value => value === null ? '阶段未记录' : searchStages[value] || '其他搜索阶段',
  execution_kind: value => value === null ? '未记录' : executionKinds[value] || '其他执行方式',
  process_flag: flag => processFlags[flag] || '其他标记',
  // 工种归属与外协周期规则：资料、工艺、候选工时依据共用。
  op_type_categories: Object.freeze({ internal: '自制', external: '外协', both: '自制和外协都可' }),
  merge_modes: mergeModes,
  material_descriptions: Object.freeze({ strict: '这批全部用料到齐后，再安排工序开工。', stage: '每道工序只等本序和前序用料，不等后续用料。' }),
  // 值来自排产检查规范后的输入或排产记录存下的规范输入：规则恒为 strict/stage，齐套检查恒为是或否。
  material_strategy: (value, readyCheck) => readyCheck === false ? '未启用（齐套检查已关闭）' : materialStrategies[value],
  // 不重排时段：排产检查、排产任务、排产记录、候选方案的回显用同一套说法。没带这一项表示按当时的交付设置推算。
  hold_window: value => value === undefined ? '未记录（按当时的交付设置）' : value === null ? '不设'
    : value.start.replace('T', ' ') + ' 至 ' + value.end.replace('T', ' '),
  execution_states: executionStates,
  // 报工记录的数据完整性：与后端报表、实际甘特导出的叫法一致。complete 在这里是“完整”，不是执行状态的“已完工”。
  data_quality: Object.freeze({ complete: '完整', incomplete: '不完整', invalid: '需复核' }),
  // 交付判断：计划详情、执行排产、值班台、试调共用；与正式计划导出一致。
  delivery_risks: Object.freeze({ overdue: '预计超期', on_time: '预计按期', unknown: '交付待确认', not_applicable: '未指定交期' }),
  arrangement_labels: Object.freeze({
    status: '工序安排', planned_finish: '预计完工', partial_finish: '已安排工序预计结束',
    complete: '工序已排齐', unplanned: '未安排', other_unplanned: '其他未安排', deferred: '缺料未安排'
  }),
  // 逐批交付的原因码（后端 facts/delivery_projection.py 的批次原因，加上 plan/delivery.py 的范围原因与 trial/projection.py 的试调约束原因）：
  // 计划详情、候选方案、方案决策共用一张表；不认识的码不显示原文。
  delivery_issue: code => deliveryIssues[code] || '原因说明缺失',
  delivery_completion_states: Object.freeze({ complete: '工序已排齐', deferred: '因缺料暂未安排', incomplete: '工序未排齐', unknown: '工序安排待确认' }),
  missing_arrangements: missingArrangements,
  completion_summary: completionSummary,
  due_states: Object.freeze({ specified: '明确交期', unspecified: '未指定交期', invalid: '交期无效' }),
  due_issues: Object.freeze({ due_date_missing: '交期缺失', due_date_invalid: '交期无效' }),
  due_date: (value, state, issue) => state === 'unspecified' ? '未指定交期' : state === 'invalid'
    ? issue === 'due_date_missing' ? '交期缺失' : '交期无效' : WorkbenchFormat.date(value),
  delivery_coverage: summary => '明确交期 ' + summary.due_eligible_count + ' 批 · 已知 ' + summary.known_due_count +
    ' 批 · 未知 ' + summary.unknown_due_count + ' 批 · 未指定交期排除 ' + summary.excluded_due_count +
    ' 批 · 交期无效 ' + summary.invalid_due_count + ' 批',
  // 页头身份标签允许 v3；句子里写“第 3 版”。
  plan_version: version => '正式 v' + version,
  download_started: name => '已交给浏览器下载：' + name,
  data_as_of: time => '本次刷新 ' + time,
  // 逐次报工的动作名：现场、报表、校准三个工作区共用，不再各写一份。
  report_actions: Object.freeze({ create: '新增', supplement: '补齐', correct: '更正' }),
  actions: Object.freeze({
    add: '新增', save: '保存', confirm: '确认', cancel: '取消', clear: '清除',
    import: '导入', export: '导出', download: '下载', refresh: '刷新', query_result: '查询结果', adopt: '采用'
  }),
  // 结果未知这一族提示只从这里取，各工作区不再自己写。
  outcomes: Object.freeze({
    pending: action => '上次' + action + '的结果还没查到，可能已经生效。请点「查询结果」，不要重复提交。',
    // Omit reason when an adjacent error box already owns the failure details.
    rejected: (action, reason) => '上次' + action + '没有生效' + (reason ? '：' + sentence(reason) : '。') + '填写内容已保留，改好后重新提交。',
    done: (action, next) => action + '已完成。' + (next ? sentence(next) : ''),
    unknown: action => action + '结果不确定，可能已经生效。请刷新后核对，不要重复提交。',
    stale: '数据已更新，请刷新后重试。刚才的选择已保留。',
    unavailable: '此功能尚未开通。',
    failure: '操作没有完成。请刷新重试；仍不行请联系维护人员，并告知下方编号。'
  })
});

export { WorkbenchTerms };
export default WorkbenchTerms;
