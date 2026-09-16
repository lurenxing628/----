(function () {
  'use strict';
  const C = window.APSResourceContract;
  // 报工状态与报工类型的唯一词表：现场记录、现场实际甘特、报表中心、工时校准都从这里取，不再各自造词。
  const states = { unreported: '待报工', started: '已开工', partial: '部分完成', paused: '已暂停', exception: '异常', complete: '已完工' };
  const reportActions = window.WorkbenchTerms.report_actions;
  const fields = ['completed_quantity', 'actual_start', 'actual_end', 'effective_processing_hours', 'actual_machine_ref', 'actual_operator_ref', 'remark'];
  const ref = value => typeof value === 'string' && /^[0-9a-f]{48}$/.test(value);
  const nullable = value => value === null || Number.isFinite(value) && value >= 0;
  const time = value => value === null || typeof value === 'string' && /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d$/.test(value);
  const validTime = value => typeof value === 'string' && time(value) && Number.isFinite(Date.parse(value + 'Z')) && new Date(value + 'Z').toISOString().slice(0, 19) === value;
  const quantityReasons = { plan_target_not_recorded: '旧计划未记录原数量证据', plan_target_unavailable: '原计划数量证据不可用', plan_target_invalid: '原计划数量证据无效' };
  const quantity = value => window.WorkbenchFormat.number(value, { digits: 0 });
  const pieceLabel = value => value.piece_id === null ? '共同工序' : '分件 ' + value.piece_id;
  function planQuantity(value) {
    const valid = n => Number.isSafeInteger(n) && n >= 0;
    if (!(value.piece_id === null || typeof value.piece_id === 'string' && value.piece_id.trim() && !value.piece_id.includes('\0'))
      || ![value.quantity, value.batch_quantity].every(n => n === null || valid(n))) return false;
    if (value.quantity_basis === 'unknown') return value.quantity === null && value.batch_quantity === null
      && ['plan_target_not_recorded', 'plan_target_unavailable'].includes(value.quantity_reason);
    return ['run_admission', 'trial_creation'].includes(value.quantity_basis)
      && (value.quantity_reason === null ? valid(value.quantity) && valid(value.batch_quantity) : value.quantity_reason === 'plan_target_invalid');
  }
  function planned(value) {
    const row = { ...value, start: value.planned_start, end: value.planned_end };
    const validTime = at => typeof at === 'string' && time(at) && Number.isFinite(Date.parse(at + 'Z')) && new Date(at + 'Z').toISOString().slice(0, 19) === at;
    return validTime(row.start) && validTime(row.end) && window.PointContract.arrangement(row);
  }
  function report(value) {
    return C.object(value) && ref(value.report_ref) && ref(value.revision_ref) && ref(value.operation_ref) && ref(value.recorded_against_task_ref) && ref(value.recorded_against_plan_ref)
      && typeof value.report_no === 'string' && nullable(value.completed_quantity) && nullable(value.effective_processing_hours)
      && time(value.actual_start) && time(value.actual_end) && Array.isArray(value.correction_history) && C.object(value.write_context);
  }
  function task(value) {
    const p = value && value.execution;
    return C.object(value) && ref(value.task_ref) && ref(value.plan_ref) && planned(value) && planQuantity(value) && typeof value.batch_id === 'string' && typeof value.operation_label === 'string'
      && C.object(p) && ref(p.operation_ref) && p.operation_ref === value.operation_ref && (p.comparison_task_ref === null || p.comparison_task_ref === value.task_ref) && Object.hasOwnProperty.call(states, p.execution_state)
      && ['complete', 'incomplete', 'legacy_incomplete', 'invalid'].includes(p.data_quality) && nullable(p.target_quantity)
      && nullable(p.known_completed_quantity) && nullable(p.remaining_quantity) && typeof p.records_complete === 'boolean'
      && typeof p.quantity_complete === 'boolean' && Number.isInteger(p.unknown_record_count) && Array.isArray(p.data_gaps)
      && Array.isArray(p.reports) && p.reports.every(row => report(row) && row.operation_ref === p.operation_ref) && Array.isArray(p.legacy_facts) && C.object(p.write_context);
  }
  function query(result, mode, expected) {
    if (!result || result.ok !== true || result.schema_version !== 1 || !result.meta || result.meta.source !== 'production' || result.meta.time_basis !== 'factory_local'
      || !result.meta.snapshot_ref || !result.meta.as_of || !C.object(result.data)) throw C.failure('读到的现场记录不完整，请刷新重试。');
    const d = result.data;
    if (mode === 'list' && (!Array.isArray(d.tasks) || !d.tasks.every(task) || !C.object(d.page) || !Number.isInteger(d.page.total) || !C.object(d.summary))) throw C.failure('读到的现场任务列表不完整，请刷新重试。');
    if (mode === 'list' && d.tasks.some(row => !d.plan || row.plan_ref !== d.plan.plan_ref)) throw C.failure('现场任务与所选计划不一致。');
    if (mode === 'detail' && (!task(d.task) || d.task.task_ref !== expected)) throw C.failure('现场任务详情不匹配，请刷新后重选。');
    if (mode === 'preview' && (!/^[A-Za-z0-9_-]{32}$/.test(d.preview_ref) || !Array.isArray(d.rows) || typeof d.can_confirm !== 'boolean' || d.commit_policy !== 'atomic' || !C.object(d.write_context))) throw C.failure('读到的文件预检结果不完整，请刷新重试。');
    return result;
  }
  function blocked(context, action) {
    if (!context || !context.write_token || !context.capabilities || context.capabilities[action] !== true)
      return (context && context.blocked_reasons || []).map(item => item.message).join('；') || '本页数据已过期，请刷新后重试。';
    return '';
  }
  function draft(record) {
    return Object.fromEntries(fields.map(key => [key, record && record[key] != null ? String(record[key]) : '']).concat([['reason', ''], ['declared_operator', '']]));
  }
  function input(value, record, action) {
    const result = {}, errors = [];
    const bad = (path, message) => errors.push({ path, message });
    fields.forEach(key => {
      let v = value[key];
      if (['completed_quantity', 'effective_processing_hours'].includes(key)) {
        if (v !== '' && (!Number.isFinite(Number(v)) || Number(v) < 0 || key === 'completed_quantity' && !Number.isSafeInteger(Number(v)))) bad(key, key === 'completed_quantity' ? '数量必须为非负整数。' : '工时必须是 0 或正数。');
        v = v === '' ? null : Number(v);
      } else if (key === 'actual_start' || key === 'actual_end') {
        v = v ? v.length === 16 ? v + ':00' : v : null;
        if (v !== null && !validTime(v)) bad(key, '请按 2026-09-13 08:30 这样填写；未知时请清除。');
      }
      else if (key.endsWith('_ref')) v = v || null;
      if (!record || v !== record[key]) result[key] = v;
    });
    if (record) {
      if (!value.reason.trim()) bad('reason', '请填写补齐或更正原因。');
      if (!Object.keys(result).length) throw C.failure('内容没有变化。');
      result.original_revision_ref = record.revision_ref; result.reason = value.reason.trim();
    } else result.source = 'manual';
    if (action === 'supplement') fields.filter(key => Object.prototype.hasOwnProperty.call(result, key) && record[key] !== null && record[key] !== '' && result[key] !== record[key]).forEach(key => bad(key, '补齐不能改动已有记录，请改用「更正」。'));
    const start = value.actual_start ? Date.parse(value.actual_start + 'Z') : NaN, end = value.actual_end ? Date.parse(value.actual_end + 'Z') : NaN;
    if (Number.isFinite(start) && Number.isFinite(end) && start > end) bad('actual_end', '本次实际完工不能早于实际开工。');
    if (Number.isFinite(start) && Number.isFinite(end) && end >= start && value.effective_processing_hours !== '' && Number(value.effective_processing_hours) > (end - start) / 3600000)
      bad('effective_processing_hours', '有效工时不能超过本次实际起止的时长。');
    if (errors.length) throw C.failure('请核对标红的项。', errors);
    result.declared_operator = value.declared_operator.trim();
    return result;
  }
  function saveFile(file, fallback) {
    if (!file || !(file.blob instanceof Blob) || !file.blob.size || !file.contentType.includes('spreadsheetml')) throw C.failure('下载不是有效 XLSX 文件。');
    const match = /filename\*=UTF-8''([^;]+)/i.exec(file.disposition || '');
    const url = URL.createObjectURL(file.blob), link = document.createElement('a');
    link.href = url; link.download = match ? decodeURIComponent(match[1]) : fallback;
    document.body.appendChild(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  const display = value => value === null || value === undefined || value === '' ? '未知' : String(value);
  // Report times are second-precision facts (see the time pattern and step="1" inputs); never drop the seconds.
  const date = value => window.WorkbenchFormat.dateTime(value, { seconds: true });
  window.FieldContract = { states, reportActions, fields, ref, task, report, query, blocked, draft, input, saveFile, display, date, quantity, pieceLabel, planQuantity, quantityReasons, validTime };
})();
