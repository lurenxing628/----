(function () {
  'use strict';
  // Load after the foundation (APSSystemWorkbench.csvCell) and TrialContract, before TrialControls.
  const C = window.TrialContract;
  const headers = ['方案', '方案状态', '约束说明（非取舍评估）', '基准方案', '换型次数（次）',
    '批次', '产品', '数量（件）', '优先级', '交期（截至日）', '基准完工（工厂本地时间）', '方案完工（工厂本地时间）',
    '延期（h）', '完工提前（h，负数为延后）', '工序调整', '换设备', '交付风险',
    '草稿引用', '场景引用', '原来源引用', '场景保存时间（工厂本地时间）', '核对提示'];
  const states = { editing: '可继续试调', saved: '已保存', discarded: '已放弃', valid: '通过', warning: '有提示', blocked: '有阻断' };
  const priorities = { normal: '普通', urgent: '急件', critical: '特急' };
  const risks = { on_time: '可按期', overdue: '预计晚交', unavailable: '约束阻断，不可评估', invalid_data: '交期数据无效' };
  const label = (value, labels) => value == null ? null : Object.prototype.hasOwnProperty.call(labels, value) ? labels[value] : '未识别（' + String(value) + '）';

  function checkBatches(data) {
    C.workspace(data);
    const groups = new Map();
    data.tasks.forEach(task => { if (!groups.has(task.batch_ref)) groups.set(task.batch_ref, []); groups.get(task.batch_ref).push(task); });
    const batches = data.comparison.batches;
    C.check(batches.length === groups.size && new Set(batches.map(batch => batch.batch_ref)).size === groups.size,
      '批次对比未覆盖完整任务，未导出部分结果。');
    batches.forEach(batch => {
      const tasks = groups.get(batch.batch_ref);
      C.check(tasks && batch.changed === tasks.some(task => task.changed)
        && batch.moved === tasks.some(task => task.machine_ref !== task.original.machine_ref),
      '批次调整或换设备标记与完整任务不一致，未导出替代结果。');
    });
  }
  function note(data) {
    return '完整' + data.comparison.batches.length + '批次、' + data.task_count + '道安排、' + data.unplanned_operations.length + '道未排；不受分页或显示筛选限制。' +
      '基准为原试调来源；交期截至日次日零点不含；时间为工厂本地，不换时区；负数提前量表示延后。' +
      (data.scenario_ref ? '事实为场景保存时快照。' : '事实为本次页面读取内容，导出时不刷新。') +
      '未知不等于0，空白为不适用；数值保留原精度。' + data.comparison.changeover_reason +
      '文字统一加一位单引号防公式及编号转换，标准CSV解码后仅移除一位首引号。完整任务、真实资源变更、容量日历、执行及调整记录见“导出原始数据”（不含写凭证）。';
  }
  function cell(value) {
    if (value === undefined) return '""';
    if (typeof value === 'number') { C.check(Number.isFinite(value), '导出含无效数值，未替换为0。'); return String(value); }
    const text = value === null ? '未知' : typeof value === 'boolean' ? value ? '是' : '否' : value;
    C.check(typeof text === 'string' && !text.includes('\u0000'), '导出文字无效或含NUL，未删除或替换原文。');
    // Same reversible text prefix as material_file_codec._write_csv; existing helper owns RFC quoting.
    return window.APSSystemWorkbench.csvCell("'" + text);
  }
  function csv(data) {
    checkBatches(data);
    const c = data.comparison;
    const constraints = '试调约束：' + label(data.validation.constraints_status, states) + '；整体状态：' + label(data.validation.status, states) +
      '；问题' + data.validation.issues.length + '项，完整原因见原始数据；未评估方案取舍。';
    const common = [data.name || '未命名试调草稿', label(data.status, states), constraints,
      data.base_identity.display_name || '原排产候选', c.changeovers === null ? '未评估' : c.changeovers];
    const evidence = [data.draft_ref, data.scenario_ref,
      (data.base.plan_ref ? '计划：' + data.base.plan_ref : '排产候选：' + data.base.candidate_ref),
      data.scenario_ref ? data.saved_at || '未记录' : undefined, note(data)];
    const rows = c.batches.map(batch => common.concat([batch.batch_id, batch.part_name, batch.quantity, label(batch.priority, priorities),
      batch.due_date, batch.baseline_finish, batch.finish, batch.late_hours, batch.improvement_hours, batch.changed, batch.moved, label(batch.risk, risks)], evidence));
    return { filename: '方案试调对比.csv', mime: 'text/csv;charset=utf-8',
      text: '\uFEFF' + headers.map(header => window.APSSystemWorkbench.csvCell(header)).join(',') + '\r\n' +
        rows.map(row => row.map(cell).join(',')).join('\r\n') + '\r\n' };
  }
  function raw(data) {
    C.workspace(data);
    return { filename: '试调原始数据.json', mime: 'application/json;charset=utf-8',
      text: JSON.stringify(data, (key, value) => key === 'write_context' ? undefined : value, 2) };
  }
  window.TrialExport = { csv, raw };
})();
