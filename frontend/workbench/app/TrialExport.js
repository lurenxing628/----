(function () {
  'use strict';
  // Load after the foundation (APSSystemWorkbench.csvCell) and TrialContract, before TrialControls.
  const C = window.TrialContract, T = window.WorkbenchTerms;
  const headers = ['方案', '方案状态', '约束检查', '对比基准方案', T.changeover_count + '（次）',
    '批次', '产品', '数量（件）', '优先级', '交期（截至日）', '对比基准预计完工', '试调预计完工',
    '超期（小时）', '预计完工提前（小时，负数为延后）', '工序调整', '换设备', '交付风险',
    '交期判定', '原工序安排', '试调工序安排', '原已安排部分预计完工', '试调已安排部分预计完工',
    '原其他未安排工序', '原缺料未安排工序', '试调其他未安排工序', '试调缺料未安排工序',
    '草稿编号', '试调方案编号', '原来源编号', '试调方案保存时间', '核对提示'];
  const states = { editing: '可继续试调', saved: '已保存', discarded: '已放弃', valid: '通过', warning: '有提示', blocked: '有冲突，不能采用' };
  const priorities = { normal: '普通', urgent: '急件', critical: '特急' };
  const risks = T.delivery_risks;
  const label = (value, labels) => value == null ? null : Object.prototype.hasOwnProperty.call(labels, value) ? labels[value] : '未识别（' + String(value) + '）';

  function note(data) {
    return '对比方案：' + (data.base_identity.display_name || '原试调来源') +
      '；更新时间：' + (data.scenario_ref ? data.saved_at || '未记录' : data.updated_at || '未记录') +
      '；导出 ' + data.comparison.batches.length + ' 批次、' + data.task_count + ' 道安排、' + data.unplanned_operations.length + ' 道未安排工序。';
  }
  function cell(value, index, columns = headers) {
    if (value === undefined || value === null) return '""';
    if (typeof value === 'number') { C.check(Number.isFinite(value), '导出数据中有无效数值。'); return String(value); }
    const text = typeof value === 'boolean' ? value ? '是' : '否' : value;
    C.check(typeof text === 'string' && !text.includes('\u0000'), '导出文字无效或含不可见字符。');
    return window.APSSystemWorkbench.csvCell(columns[index].endsWith('编号') && /^\d+$/.test(text) ? "'" + text : text);
  }
  function document(filename, columns, rows) {
    return { filename, mime: 'text/csv;charset=utf-8',
      text: '\uFEFF' + columns.map(header => window.APSSystemWorkbench.csvCell(header)).join(',') + '\r\n' +
        rows.map(row => row.map((value, index) => cell(value, index, columns)).join(',')).join('\r\n') + '\r\n' };
  }
  function csv(data) {
    C.workspace(data);
    const c = data.comparison;
    const issues = data.validation.issues.filter(row => row.code !== 'scenario_adoption_not_connected');
    const constraints = '约束检查：' + label(data.validation.constraints_status, states) + '；整体状态：' + label(data.validation.constraints_status, states) +
      '；问题 ' + issues.length + ' 项';
    const common = [data.name || '未命名试调草稿', label(data.status, states), constraints,
      data.base_identity.display_name || '上次排产的候选方案', c.changeovers];
    const evidence = [data.draft_ref, data.scenario_ref,
      (data.base.plan_ref ? '计划：' + data.base.plan_ref : '排产候选：' + data.base.candidate_ref),
      data.scenario_ref ? data.saved_at || '未记录' : undefined, note(data)];
    const rows = c.batches.map(batch => common.concat([batch.batch_id, batch.part_name, batch.quantity, label(batch.priority, priorities),
      batch.due_date, batch.baseline_finish, batch.finish, batch.late_hours, batch.improvement_hours, batch.changed, batch.moved, label(batch.risk, risks),
      T.due_date(batch.due_date, batch.due_state, batch.due_issue), T.delivery_completion_states[batch.before.completion_state], T.delivery_completion_states[batch.after.completion_state],
      batch.partial_baseline_finish, batch.partial_finish, batch.before.ordinary_unscheduled_operation_count, batch.before.deferred_operation_count,
      batch.after.ordinary_unscheduled_operation_count, batch.after.deferred_operation_count], evidence));
    return document('方案试调对比.csv', headers, rows);
  }
  function preparation(data) {
    C.workspace(data);
    const columns = ['方案', '安排侧', '批次', '工序', '顺序', '分件', '工序安排', '准备状态', '工序类别',
      '原需求目标量', '原需求数量依据', '本次执行目标量', '本次执行数量依据', '本次执行剩余',
      '准备标准工时（小时）', '加工标准工时（小时）', '所需标准工时（小时）',
      '归档标准准备（小时）', '归档单件标准（小时）', '归档标准总需求（小时）',
      '外协周期（天）', '外协组', '外协合并规则', '完整性', '缺项说明',
      '工序编号', '批次编号', '任务编号', '草稿编号', '试调方案编号', '需求来源', '源排产编号', '源候选编号', '源正式计划编号', '源试调方案编号'];
    const rows = [];
    [...data.tasks, ...data.unplanned_operations].forEach(task => ['before', 'after'].forEach(side => {
      const value = task.operation_effort && task.operation_effort[side], standard = value && value.standard, source = value && value.evidence_source;
      rows.push([data.name || '未命名试调草稿', side === 'before' ? '原安排' : '当前试调', task.batch_id, task.process_label, task.sequence, task.piece_id,
        value && T.preparation_allocations[value.allocation_state], value && T.setup_states[value.setup_state], value && T.effort_roles[value.requirement_role],
        value && value.target_quantity, value && T.effort_quantity_bases[value.quantity_basis], value && value.execution_target_quantity,
        value && T.effort_quantity_bases[value.execution_quantity_basis], value && value.remaining_quantity,
        value && value.setup_standard_hours, value && value.processing_standard_hours, value && value.required_standard_hours,
        standard && standard.setup_standard_hours, standard && standard.unit_standard_hours, standard && standard.standard_total_hours,
        value && value.external_cycle_days, value && value.external_group_id, value && value.external_merge_mode,
        value ? T.resource_states[value.state] : '工时需求未保存', value ? value.data_gaps.map(row => row.message).join('；') : '这份历史记录未保存所需标准工时。',
        task.operation_ref, task.batch_ref, task.task_ref, data.draft_ref, data.scenario_ref,
        value && T.effort_basis_labels[value.effort_basis], source && source.run_ref, source && source.candidate_ref, source && source.plan_ref, source && source.scenario_ref]);
    }));
    return document('试调准备需求.csv', columns, rows);
  }
  function changeovers(data) {
    C.workspace(data);
    const columns = ['方案', '安排侧', '记录类型', '工种切换次数（次）', '已知切换（次）', '未知工序数', '冲突数', '设备',
      '前工种', '后工种', '前序预计开工', '前序预计完工', '后序预计开工', '后序预计完工', '重叠', '缺项说明',
      '设备编号', '前工序编号', '后工序编号', '前安排编号', '后安排编号', '草稿编号', '试调方案编号'];
    const common = data.comparison.changeover_common, rows = [];
    ['before', 'after'].forEach(side => {
      const value = common && common[side], identity = [data.name || '未命名试调草稿', side === 'before' ? '原安排' : '当前试调'];
      rows.push([...identity, '汇总', value && value.count, value && value.known_count, value && value.unknown_count, value && value.conflict_count,
        null, null, null, null, null, null, null, null, value ? value.issues.map(row => row.message).join('；') : '工种切换的原保存序列缺失。',
        null, null, null, null, null, data.draft_ref, data.scenario_ref]);
      if (value) value.events.forEach(event => rows.push([...identity, '切换事件', null, null, null, null, event.machine_label,
        event.previous_type, event.next_type, event.previous_start, event.previous_end, event.next_start, event.next_end, event.overlap,
        event.conflict ? '设备安排重叠，完整切换次数未知。' : null, event.machine_ref, event.previous_operation_ref, event.next_operation_ref,
        event.previous_row_ref, event.next_row_ref, data.draft_ref, data.scenario_ref]));
    });
    return document('试调工种切换.csv', columns, rows);
  }
  function raw(data) {
    C.workspace(data);
    return { filename: '试调原始数据.json', mime: 'application/json;charset=utf-8',
      text: JSON.stringify(data, (key, value) => key === 'write_context' ? undefined : value, 2) };
  }
  window.TrialExport = { csv, preparation, changeovers, raw };
})();
