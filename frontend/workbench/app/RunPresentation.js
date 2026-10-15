(function () {
  'use strict';
  const stages = { queued: '等待计算', computing: '正在计算', awaiting_reconciliation: '核对排产记录', finished: '排产已结束' };
  function step(input, checked) { return !input || !input.batch_refs.length ? 1 : checked ? 3 : 2; }
  function elapsed(run, now = Date.now()) {
    const start = run.started_at || run.accepted_at, finish = run.finished_at;
    function local(value) {
      if (typeof value !== 'string' || !value) return null;
      const normalized = window.WorkbenchDatePickerModel.factoryTime(value), fraction = normalized.split('.')[1] || '';
      const fields = normalized.slice(0, 19).split(/[-T:]/).map(Number);
      // UTC supplies an ordinal for naive factory fields, without applying the browser's timezone or DST.
      return { whole: Date.UTC(fields[0], fields[1] - 1, fields[2], fields[3], fields[4], fields[5]),
        fraction: Number(fraction.padEnd(6, '0')) / 1000000, precision: (value.split('.')[1] || '').length };
    }
    const begin = local(start), current = !finish && Number.isFinite(now)
      ? local(window.WorkbenchFormat.instant(new Date(now).toISOString(), { seconds: true })) : null;
    const end = finish ? local(finish) : current && { ...current, fraction: now % 1000 / 1000, precision: 3 };
    if (!begin || !end || !Number.isFinite(begin.whole) || !Number.isFinite(end.whole)) return '未记录';
    const elapsed = (end.whole - begin.whole) / 1000 + end.fraction - begin.fraction;
    if (elapsed < 0) return '时间记录待核对';
    const precision = Math.min(begin.precision, end.precision);
    if (elapsed < 1 && !precision) return finish
      ? begin.whole === end.whole ? '起止记录在同一秒（记录精确到秒）' : '起止记录相差不足 1 秒（记录精确到秒）'
      : '不到 1 秒（起始记录精确到秒）';
    const seconds = precision ? Number(elapsed.toFixed(precision)) : Math.floor(elapsed);
    const hours = Math.floor(seconds / 3600), minutes = Math.floor(seconds % 3600 / 60);
    return (hours ? hours + ' 小时 ' : '') + (minutes || hours ? minutes + ' 分钟 ' : '')
      + window.WorkbenchFormat.number(seconds - hours * 3600 - minutes * 60, { digits: precision, trim: true }) + ' 秒';
  }
  function stage(run) {
    if (run.stage === 'computing' && window.RunGenerationContract.unified(run.scope_summary && run.scope_summary.run_options)) return '正在共同优化方案';
    return stages[run.stage] || '排产阶段未知';
  }
  window.RunPresentation = { step, stage, elapsed };
})();
