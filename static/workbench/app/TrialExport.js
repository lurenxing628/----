(function () {
  'use strict';

  // Load after the foundation (APSSystemWorkbench.csvCell) and TrialContract, before TrialControls.
  const C = window.TrialContract;
  const headers = ['方案', '方案状态', '约束检查', '对比基准方案', '换型次数（次）', '批次', '产品', '数量（件）', '优先级', '交期（截至日）', '对比基准完工', '方案完工', '超期（小时）', '完工提前（小时，负数为延后）', '工序调整', '换设备', '交付风险', '草稿编号', '试调方案编号', '原来源编号', '试调方案保存时间', '核对提示'];
  const states = {
    editing: '可继续试调',
    saved: '已保存',
    discarded: '已放弃',
    valid: '通过',
    warning: '有提示',
    blocked: '有冲突，不能采用'
  };
  const priorities = {
    normal: '普通',
    urgent: '急件',
    critical: '特急'
  };
  const risks = {
    on_time: '可按期',
    overdue: '预计超期',
    unavailable: '有冲突，不能评估',
    invalid_data: '交期数据无效'
  };
  const label = (value, labels) => value == null ? null : Object.prototype.hasOwnProperty.call(labels, value) ? labels[value] : '未识别（' + String(value) + '）';
  function checkBatches(data) {
    C.workspace(data);
    const groups = new Map();
    data.tasks.forEach(task => {
      if (!groups.has(task.batch_ref)) groups.set(task.batch_ref, []);
      groups.get(task.batch_ref).push(task);
    });
    const batches = data.comparison.batches;
    C.check(batches.length === groups.size && new Set(batches.map(batch => batch.batch_ref)).size === groups.size, '批次对比不完整，无法导出。');
    batches.forEach(batch => {
      const tasks = groups.get(batch.batch_ref);
      C.check(tasks && batch.changed === tasks.some(task => task.changed) && batch.moved === tasks.some(task => task.machine_ref !== task.original.machine_ref), '批次调整或换设备标记与任务不一致，无法导出。');
    });
  }
  function note(data) {
    return '对比方案：' + (data.base_identity.display_name || '原试调来源') + '；更新时间：' + (data.scenario_ref ? data.saved_at || '未记录' : data.updated_at || '未记录') + '；导出 ' + data.comparison.batches.length + ' 批次、' + data.task_count + ' 道安排、' + data.unplanned_operations.length + ' 道未排工序。';
  }
  function cell(value) {
    if (value === undefined) return '""';
    if (typeof value === 'number') {
      C.check(Number.isFinite(value), '导出数据中有无效数值。');
      return String(value);
    }
    const text = value === null ? '未知' : typeof value === 'boolean' ? value ? '是' : '否' : value;
    C.check(typeof text === 'string' && !text.includes('\u0000'), '导出文字无效或含不可见字符。');
    // Same reversible text prefix as material_file_codec._write_csv; existing helper owns RFC quoting.
    return window.APSSystemWorkbench.csvCell("'" + text);
  }
  function csv(data) {
    checkBatches(data);
    const c = data.comparison;
    const issues = data.validation.issues.filter(row => row.code !== 'scenario_adoption_not_connected');
    const constraints = '约束检查：' + label(data.validation.constraints_status, states) + '；整体状态：' + label(data.validation.constraints_status, states) + '；问题 ' + issues.length + ' 项';
    const common = [data.name || '未命名试调草稿', label(data.status, states), constraints, data.base_identity.display_name || '上次排产的候选方案', c.changeovers === null ? '未评估' : c.changeovers];
    const evidence = [data.draft_ref, data.scenario_ref, data.base.plan_ref ? '计划：' + data.base.plan_ref : '排产候选：' + data.base.candidate_ref, data.scenario_ref ? data.saved_at || '未记录' : undefined, note(data)];
    const rows = c.batches.map(batch => common.concat([batch.batch_id, batch.part_name, batch.quantity, label(batch.priority, priorities), batch.due_date, batch.baseline_finish, batch.finish, batch.late_hours, batch.improvement_hours, batch.changed, batch.moved, label(batch.risk, risks)], evidence));
    return {
      filename: '方案试调对比.csv',
      mime: 'text/csv;charset=utf-8',
      text: '\uFEFF' + headers.map(header => window.APSSystemWorkbench.csvCell(header)).join(',') + '\r\n' + rows.map(row => row.map(cell).join(',')).join('\r\n') + '\r\n'
    };
  }
  function raw(data) {
    C.workspace(data);
    return {
      filename: '试调原始数据.json',
      mime: 'application/json;charset=utf-8',
      text: JSON.stringify(data, (key, value) => key === 'write_context' ? undefined : value, 2)
    };
  }
  window.TrialExport = {
    csv,
    raw
  };
})();
