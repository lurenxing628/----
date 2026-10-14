(function () {
  'use strict';
  // 用户可见文案的前端词表与句式模板。词表决策：.codestable/compound/2026-09-13-decision-ui-copy-glossary.md
  const sentence = text => /[。！？；]$/.test(text) ? text : text + '。';
  const countText = value => window.WorkbenchFormat.number(value, { digits: 0 });
  // 缺料和其他未安排工序可以出现在同一批次，摘要按工序分别列出。
  function missingArrangements(unplannedCount, deferredCount) {
    if (unplannedCount == null && deferredCount == null) return '未安排工序数待确认，请查看原因';
    const items = [];
    if (unplannedCount == null) items.push('其他未安排工序数待确认');
    else if (unplannedCount > 0) items.push(countText(unplannedCount) + ' 道工序' + (deferredCount > 0 ? '因其他原因未安排' : '未安排'));
    if (deferredCount == null) items.push('缺料未安排工序数待确认');
    else if (deferredCount > 0) items.push(countText(deferredCount) + ' 道工序因缺料暂未安排');
    return items.join('；');
  }
  function completionSummary(scope) {
    if (scope.state === 'not_applicable') return '本次没有需要安排的批次';
    if (scope.source_available === false) return '工序安排记录未保存，请查看原因';
    const items = [];
    if (scope.complete_batch_count == null) items.push('工序已排齐的批次数待确认');
    else if (scope.complete_batch_count > 0) items.push(countText(scope.complete_batch_count) + ' 批工序已排齐');
    const missing = missingArrangements(scope.unplanned_operation_count, scope.deferred_operation_count);
    if (missing) items.push(missing);
    if (scope.unknown_batch_count == null) items.push('尚待确认工序安排的批次数未记录');
    else if (scope.unknown_batch_count > 0) items.push(countText(scope.unknown_batch_count) + ' 批工序安排待确认，请查看原因');
    return items.join('；');
  }
  window.WorkbenchTerms = Object.freeze({
    overdue_count: '预计超期批次', delay_hours: '超期时长', total_tardiness_hours: '总拖期',
    utilization: '利用率', candidate: '候选方案', official_plan: '正式计划', trial: '试调',
    resource_kinds: Object.freeze({ machine: '设备', operator: '人员' }),
    resource_views: Object.freeze({ selected_batches: '本次选中批次', full_candidate: '整份候选方案' }),
    resource_metric_labels: Object.freeze({ available_hours: '可排总时长', occupied_hours: '班表内已占时间', summed_load_hours: '班表内逐工序占用合计',
      overlap_hours: '班表内重复计入时长', outside_calendar_hours: '安排跨度跨非工作时段', utilization_ratio: '班表内占用比例', demand_ratio: '工序合计占用比例',
      span_occupied_hours: '全部已占时间', span_summed_hours: '逐工序占用合计', span_overlap_hours: '重复计入时长',
      peak_utilization: '单日最高占用比例', balance_cv: '资源占用差异', unknown_days: '班表待确认天数' }),
    resource_states: Object.freeze({ complete: '资料齐全', partial: '部分资料缺失', unavailable: '资料待确认', not_applicable: '不适用' }),
    changeover_count: '工种切换次数', algorithm_changeover_count: '算法工种切换',
    operation_effort_labels: Object.freeze({ setup_standard_hours: '准备标准工时', processing_standard_hours: '加工标准工时', required_standard_hours: '所需标准工时',
      unit_standard_hours: '保存的单件加工定额', standard_total_hours: '保存的总标准工时', target_quantity: '排产目标量', execution_target_quantity: '报工目标量', remaining_quantity: '报工剩余量',
      quantity_basis: '排产数量依据', execution_quantity_basis: '报工数量依据', setup_state: '准备状态', requirement_role: '本次安排方式', external_cycle_days: '外协周期（天）' }),
    effort_basis_labels: Object.freeze({ runtime_requirement_v1: '排产时保存的工时需求', archived_operation_standard: '保存的工序标准' }),
    setup_states: Object.freeze({ pending: '尚需准备', retained_in_execution: '沿用开工时的准备', already_completed: '准备已完成', external: '外协按周期', unknown: '准备记录缺失' }),
    effort_roles: Object.freeze({ new_schedule: '本次需安排', retained: '保留原安排', execution: '已开工工序', completed: '已报完工工序', not_scheduled: '本次未安排', unknown: '安排方式待确认' }),
    preparation_allocations: Object.freeze({ new_schedule: '本次新排', unplanned: '其他未安排', deferred: '缺料未安排', retained: '保留原安排', execution: '已开工工序', completed: '已报完工工序', external: '外协按周期', unknown: '安排方式待确认' }),
    effort_quantity_bases: Object.freeze({ piece: '分件工序数量', batch: '批次目标数量', unknown: '数量依据待确认' }),
    changeover_sides: Object.freeze({ selected: '所选候选', reference: '比较基准' }),
    trial_draft: '试调草稿', trial_scenario: '试调方案', hours_unit: '小时',
    handler: '经办人', recorder: '记录人', owner: '责任人',
    // 2026-09-21 全站收口：同一概念只留一个叫法，各工作区从这里取，不再各写一份。
    refresh_latest: '刷新最新资料', accept_latest: '已核对，继续编辑', personal_calendar: '个人日历',
    name_missing: '名称未填写', legacy_field_records: '历史现场记录', shared_operation: '共同工序', overdue: '超期',
    current_official: '当前正式', historical_official: '历史正式',
    baseline_plan: '排产时的正式计划', initial_plan: '初始计划',
    // 排产记录状态与候选方案状态：值班台、执行排产、排产记录、试调列表共用同一套叫法。
    run_statuses: Object.freeze({ queued: '等待计算', running: '正在计算', complete: '计算完成', partial: '已产出部分结果', failed: '计算失败', interrupted: '已中断' }),
    candidate_statuses: Object.freeze({ completed: '计算完成', partial: '工序未排齐', failed: '计算失败', skipped: '未计算' }),
    // 齐套规则与拆批操作分开。旧 split 记录实际按整批齐套执行，不能据此声称已经拆批。
    material_strategies: Object.freeze({ strict: '等整批物料齐套', stage: '按工序物料齐套', split: '等整批物料齐套（原分批开工入口）' }),
    material_descriptions: Object.freeze({ strict: '这批全部用料到齐后，再安排工序开工。', stage: '每道工序只等本序和前序用料，不等后续用料。' }),
    material_strategy: (value, readyCheck) => readyCheck === false ? '未启用（齐套检查已关闭）'
      : value === null || readyCheck === null ? '未记录' : window.WorkbenchTerms.material_strategies[value || 'strict'] || '记录无效',
    // 不重排时段：排产检查、排产任务、排产记录、候选方案的回显用同一套说法。没有这一项的是旧记录，当时按交付设置。
    hold_window: (value, invalid) => value === undefined ? '未记录（按当时的交付设置）' : invalid ? '记录无效' : value === null ? '不设'
      : value.start.replace('T', ' ') + ' 至 ' + value.end.replace('T', ' '),
    // 报工执行状态：现场记录、实际甘特、报表、校准、排产候选、试调和值班台共用；与后端导出的“排产时报工状态”一致。
    execution_states: Object.freeze({ unreported: '待报工', started: '已开工', partial: '部分完成', paused: '已暂停', exception: '异常', complete: '已完工' }),
    // 报工记录的数据完整性：与后端报表、实际甘特导出的叫法一致。complete 在这里是“完整”，不是执行状态的“已完工”。
    data_quality: Object.freeze({ complete: '完整', incomplete: '不完整', legacy_incomplete: '历史资料不完整', invalid: '需复核' }),
    // 交付判断：计划详情、执行排产、值班台、试调共用；与正式计划导出一致。
    delivery_risks: Object.freeze({ overdue: '预计超期', on_time: '预计按期', unknown: '交付待确认', not_applicable: '未指定交期' }),
    arrangement_labels: Object.freeze({ status: '工序安排', planned_finish: '预计完工', partial_finish: '已安排工序预计结束',
      complete: '工序已排齐', unplanned: '未安排', other_unplanned: '其他未安排', deferred: '缺料未安排' }),
    delivery_completion_states: Object.freeze({ complete: '工序已排齐', deferred: '因缺料暂未安排', incomplete: '工序未排齐', unknown: '工序安排待确认' }),
    missing_arrangements: missingArrangements,
    completion_summary: completionSummary,
    due_states: Object.freeze({ specified: '明确交期', unspecified: '未指定交期', invalid: '交期无效' }),
    due_issues: Object.freeze({ due_date_missing: '交期缺失', due_date_invalid: '交期无效' }),
    due_date: (value, state, issue) => state === 'unspecified' ? '未指定交期' : state === 'invalid'
      ? issue === 'due_date_missing' ? '交期缺失' : '交期无效' : window.WorkbenchFormat.date(value),
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
})();
