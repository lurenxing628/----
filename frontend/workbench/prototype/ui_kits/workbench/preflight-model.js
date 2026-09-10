(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.APSPreflight = api;
})(typeof window === 'object' ? window : globalThis, function () {
  'use strict';
  function evaluate(batches, settings, batchApi) {
    const rows = batches.filter(b => !['completed', 'cancelled'].includes(b.status) && (!settings.picked || settings.picked.includes(b.batch_id)));
    const result = { rows, noRoute: rows.filter(b => !b.ops.length), included: [], skipped: [], missing: [], invalid: [], operations: 0, eligible: 0, autoAssign: 0, blocked: [] };
    if (!settings.start || !settings.end || !batchApi.validDate(settings.start) || !batchApi.validDate(settings.end) || settings.start > settings.end) result.blocked.push('请选择有效的开始和结束日期，结束日期不能早于开始日期。');
    rows.forEach(batch => {
      const ops = settings.lockStarted ? batch.ops.filter(o => !o.done) : batch.ops;
      result.operations += ops.length;
      if (settings.readyCheck && batch.ready_status !== 'yes') { result.skipped.push({ batch: batch.batch_id, reason: '未齐套', count: ops.length }); return; }
      if (!ops.length) { result.skipped.push({ batch: batch.batch_id, reason: batch.ops.length ? '没有待排工序' : '工艺未生成', count: 0 }); return; }
      let eligible = 0;
      ops.forEach(op => {
        const errors = batchApi.opErrors(op), keys = Object.keys(errors);
        const bad = keys.filter(k => !['machine', 'operator'].includes(k));
        if (bad.length) { result.invalid.push({ batch: batch.batch_id, op: op.seq, reasons: bad.map(k => errors[k]) }); return; }
        if (keys.length) {
          result.missing.push({ batch: batch.batch_id, op: op.seq });
          if (!settings.autoFill) { result.skipped.push({ batch: batch.batch_id, reason: '缺设备 / 人员 · 工序 ' + op.seq, count: 1 }); return; }
          result.autoAssign++;
        }
        eligible++;
      });
      if (eligible) result.included.push({ batch: batch.batch_id, count: eligible });
      result.eligible += eligible;
    });
    if (!rows.length) result.blocked.push('尚未选择待排批次。');
    if (result.invalid.length) result.blocked.push(result.invalid.length + ' 道工序存在工时、工种或外协资料缺项，自动分配不能补齐这些字段。');
    if (!result.eligible) result.blocked.push('当前范围没有可进入排产的工序。');
    return result;
  }
  return { evaluate };
});
